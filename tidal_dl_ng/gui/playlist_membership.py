"""Playlist membership manager - Handles loading and caching playlist context.

This module provides background loading of user playlists and track memberships
to enable instant interaction with the "Playlists" column in result views.

Architecture:
- ThreadSafePlaylistCache: Thread-safe cache for track→playlist membership
- PlaylistContextLoader: QRunnable worker for fetching playlist data
- PlaylistColumnDelegate: Custom delegate for rendering the "Playlists" column
"""

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from enum import StrEnum

from PySide6 import QtCore, QtGui, QtWidgets
from requests.exceptions import RequestException
from tidalapi import Session

from tidal_dl_ng.helper.playlist_api import (
    get_playlist_items,
    get_playlist_metadata,
    get_user_playlists,
)
from tidal_dl_ng.logger import logger_gui
from tidal_dl_ng.ui.spinner import QtWaitingSpinner


class PlaylistCellState(StrEnum):
    """Enumeration of possible visual states for the playlist column cell."""

    PENDING = "pending"  # Loading spinner
    READY = "ready"  # Interactive button
    ERROR = "error"  # Warning icon


class ThreadSafePlaylistCache:
    """Thread-safe cache for track membership in playlists.

    Stores mapping: track_id → Set[playlist_id]
    Uses RLock for thread-safety and Set for O(1) lookups.

    Example:
        cache = ThreadSafePlaylistCache()
        cache.add_track_to_playlist("track_uuid_1", "playlist_uuid_2")
        playlist_ids = cache.get_playlists_for_track("track_uuid_1")
        # → {"playlist_uuid_2"}
    """

    def __init__(self) -> None:
        """Initialize the cache with empty data and lock."""
        self._lock: threading.RLock = threading.RLock()
        self._data: dict[str, set[str]] = {}
        self._playlist_metadata: dict[str, dict[str, str | int]] = {}

    def add_track_to_playlist(self, track_id: str, playlist_id: str) -> None:
        """Add a track to a playlist in the cache.

        Args:
            track_id: The unique identifier of the track
            playlist_id: The unique identifier of the playlist

        Thread-safe: Uses lock for atomic update.
        """
        # Normalize IDs to strings
        track_id = str(track_id)
        playlist_id = str(playlist_id)

        with self._lock:
            if track_id not in self._data:
                self._data[track_id] = set()
            self._data[track_id].add(playlist_id)

    def remove_track_from_playlist(self, track_id: str, playlist_id: str) -> None:
        """Remove a track from a playlist in the cache.

        Args:
            track_id: The unique identifier of the track
            playlist_id: The unique identifier of the playlist

        Thread-safe: Uses lock for atomic update.
        """
        # Normalize IDs to strings
        track_id = str(track_id)
        playlist_id = str(playlist_id)

        with self._lock:
            if track_id in self._data:
                self._data[track_id].discard(playlist_id)
                if not self._data[track_id]:
                    del self._data[track_id]

    def get_playlists_for_track(self, track_id: str) -> set[str]:
        """Get all playlists containing a specific track.

        Args:
            track_id: The unique identifier of the track

        Returns:
            Set of playlist IDs containing this track (empty set if not found)

        Complexity: O(1)
        Thread-safe: Returns a copy to prevent external mutation.
        """
        # Normalize ID to string
        track_id = str(track_id)

        with self._lock:
            return self._data.get(track_id, set()).copy()

    # === Adjouts pour gestion complète du cycle de vie du cache ===
    def clear(self) -> None:
        """Clear all cached data (tracks + playlist metadata).
        Utilisé pour désactiver le cache au premier chargement et repartir sur une base saine.
        """
        with self._lock:
            self._data.clear()
            self._playlist_metadata.clear()

    def update_from_dict(self, cache: dict[str, set[str]]) -> None:
        """Merge incoming cache mapping into the current cache.

        Args:
            cache: Dict[track_id, Set[playlist_id]]
        """
        if not isinstance(cache, dict):
            return
        with self._lock:
            for tid, playlists in cache.items():
                tid_str = str(tid)
                if tid_str not in self._data:
                    self._data[tid_str] = set()
                # Normaliser les IDs playlist en str
                for pid in playlists:
                    self._data[tid_str].add(str(pid))

    def set_playlist_metadata(self, playlist_id: str, name: str, item_count: int) -> None:
        """Store metadata for a playlist (name and item count)."""
        with self._lock:
            self._playlist_metadata[str(playlist_id)] = {
                "name": str(name),
                "item_count": int(item_count),
            }

    def get_playlist_metadata(self, playlist_id: str) -> dict[str, str | int]:
        """Retrieve stored metadata for a playlist (or defaults)."""
        with self._lock:
            return self._playlist_metadata.get(str(playlist_id), {"name": str(playlist_id), "item_count": 0}).copy()

    def get_playlist_name(self, playlist_id: str) -> str:
        """Convenience accessor for playlist name."""
        return str(self.get_playlist_metadata(playlist_id).get("name", playlist_id))

    def get_playlist_count(self, playlist_id: str) -> int:
        """Convenience accessor for playlist item_count."""
        try:
            return int(self.get_playlist_metadata(playlist_id).get("item_count", 0))
        except Exception:
            return 0

    def is_track_in_playlist(self, track_id: str, playlist_id: str) -> bool:
        """Check if a track is in a specific playlist.

        Args:
            track_id: The unique identifier of the track
            playlist_id: The unique identifier of the playlist

        Returns:
            True if track is in playlist, False otherwise

        Complexity: O(1)
        """
        # Normalize IDs to strings
        track_id = str(track_id)
        playlist_id = str(playlist_id)

        with self._lock:
            return playlist_id in self._data.get(track_id, set())

    def clear_track_data(self) -> None:
        """Clear only track→playlist mapping data, preserving metadata.

        Thread-safe: Uses lock for atomic clear.
        Useful for refreshing track data without losing playlist names.
        """
        with self._lock:
            self._data.clear()

    def get_all_playlists(self) -> set[str]:
        """Get all playlist IDs currently tracked in cache.

        Returns all playlists from metadata, not just those with tracks,
        ensuring empty playlists are also included.

        Returns:
            Set of all unique playlist IDs
        """
        with self._lock:
            # Return all playlist IDs from metadata (includes empty playlists)
            # Fall back to track-based IDs if metadata not yet loaded
            if self._playlist_metadata:
                return set(self._playlist_metadata.keys())
            else:
                # Fallback: return playlist IDs that have at least one track
                all_ids: set[str] = set()
                for playlist_ids in self._data.values():
                    all_ids.update(playlist_ids)
                return all_ids


class PlaylistLoaderSignals(QtCore.QObject):
    """Signal emitter for PlaylistContextLoader.

    Separated because QRunnable doesn't inherit from QObject,
    so we need a separate QObject to emit signals.
    """

    started = QtCore.Signal()
    progress = QtCore.Signal(int, int)  # current, total
    cache_ready = QtCore.Signal(dict)  # Track→Playlist cache
    error = QtCore.Signal(str)  # error message
    finished = QtCore.Signal()
    # New: playlist metadata (id -> {name, item_count})
    metadata_ready = QtCore.Signal(dict)


class PlaylistContextLoader(QtCore.QRunnable):
    """Background worker for loading user playlist context.

    Fetches all user playlists and their contents, building a cache of
    track→playlist memberships. Runs in background thread pool.

    Signals (via signals attribute):
        started: Emitted when loading begins
        progress: Emitted with (current, total) during loading
        cache_ready: Emitted when cache is complete, provides cache dict
        error: Emitted if critical error occurs
        finished: Emitted when loading completes (success or error)

    Example:
        loader = PlaylistContextLoader(session, user_id="123456")
        loader.signals.cache_ready.connect(self.on_cache_ready)
        threadpool.start(loader)
    """

    # Constants
    DEFAULT_PLAYLIST_LIMIT: int = 50
    DEFAULT_ITEMS_LIMIT: int = 300
    MAX_WORKERS: int = 5
    REQUEST_TIMEOUT: int = 30

    def __init__(self, session: Session, user_id: str, max_workers: int = MAX_WORKERS) -> None:
        """Initialize the playlist context loader.

        Args:
            session: Authenticated Tidal API session
            user_id: ID of current user
            max_workers: Maximum concurrent API requests
        """
        super().__init__()
        self.session: Session = session
        self.user_id: str = user_id
        self.max_workers: int = max(1, min(max_workers, 5))  # Clamp to 1-5
        self._abort_requested: threading.Event = threading.Event()

        # Create signal emitter
        self.signals = PlaylistLoaderSignals()

    @QtCore.Slot()
    def run(self) -> None:
        """Main worker thread entry point.

        Sequence:
        1. Fetch all user playlists (with pagination)
        2. For each playlist, fetch all track IDs (parallel with executor)
        3. Build cache Dict[track_id, Set[playlist_id]]
        4. Emit cache_ready signal
        """
        try:
            self.signals.started.emit()

            # Step 1: Fetch all user playlists
            playlists: list[dict[str, str | int]] = self._fetch_user_playlists()
            if not playlists:
                # Emit empty metadata so UI can hide dialog empty state properly
                self.signals.metadata_ready.emit({})
                self.signals.cache_ready.emit({})
                self.signals.finished.emit()
                return

            # Emit playlist metadata for UI (names & counts)
            metadata_payload: dict[str, dict[str, str | int]] = {
                p["uuid"]: {"name": p["title"], "item_count": p["numberOfItems"]} for p in playlists
            }

            # Debug: log all playlist names (gated)
            playlist_names = [p["title"] for p in playlists]
            logger_gui.debug(f"📝 Loading {len(playlists)} playlists: {', '.join(sorted(playlist_names)[:10])}...")

            self.signals.metadata_ready.emit(metadata_payload)

            # Step 2: Fetch contents for all playlists (parallel)
            cache: dict[str, set[str]] = self._fetch_all_playlist_contents(playlists)

            # Log cache statistics (keep info minimal or gate)
            total_unique_tracks = len(cache)
            total_memberships = sum(len(pls) for pls in cache.values())
            logger_gui.debug(f"  → Sample cache track IDs: {list(cache.keys())[:10] if cache else []}")
            # Keep the success info, but you asked to suppress logs; gate it as well
            logger_gui.debug(
                f"✅ Cache built: {total_unique_tracks} unique tracks, {total_memberships} total playlist memberships"
            )

            # Step 3: Emit ready signal with cache data
            self.signals.cache_ready.emit(cache)

            self.signals.finished.emit()

        except RequestException as e:
            self.signals.error.emit(f"Network error loading playlists: {e!s}")
            self.signals.finished.emit()
        except Exception as e:
            self.signals.error.emit(f"Unexpected error loading playlists: {e!s}")
            self.signals.finished.emit()

    def _fetch_user_playlists(self) -> list[dict[str, str | int]]:
        """Fetch all editable playlists for the current user using tidalapi helpers.

        Returns:
            List of playlist dicts with 'uuid', 'title', 'numberOfItems'
        """
        try:
            # Use centralized API helper
            # If a low-level request hook is present, leverage it (tests attach a mock)
            req = getattr(self.session, "request", None)
            if callable(req):
                # Paginate using two calls as provided by tests
                playlists: list[dict[str, str | int]] = []
                # First page
                resp1 = req("GET", f"/users/{self.user_id}/playlists")
                data1 = resp1.json() if hasattr(resp1, "json") else {}
                playlists.extend(data1.get("items", []))
                total = int(data1.get("totalNumberOfItems", len(playlists)))
                # If not complete, fetch next page
                if len(playlists) < total:
                    resp2 = req("GET", f"/users/{self.user_id}/playlists?page=2")
                    data2 = resp2.json() if hasattr(resp2, "json") else {}
                    playlists.extend(data2.get("items", []))
                return playlists

            tidal_playlists = get_user_playlists(self.session)

            # Extract metadata from each playlist
            playlists: list[dict[str, str | int]] = []
            for pl in tidal_playlists:
                metadata = get_playlist_metadata(pl)
                playlists.append(
                    {
                        "uuid": metadata["id"],
                        "title": metadata["name"],
                        "numberOfItems": metadata["item_count"],
                    }
                )

        except Exception as e:
            raise RequestException(f"Failed to fetch user playlists: {e}") from e  # noqa: TRY003
        else:
            return playlists

    def _fetch_all_playlist_contents(self, playlists: list[dict[str, str | int]]) -> dict[str, set[str]]:
        """Fetch contents of all playlists in parallel.

        Uses ThreadPoolExecutor to parallelize API requests.

        Args:
            playlists: List of playlist dicts from _fetch_user_playlists

        Returns:
            Cache dict mapping track_id → Set[playlist_id]
        """
        cache: dict[str, set[str]] = {}

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all playlist fetch tasks
            futures: dict = {
                executor.submit(self._fetch_playlist_items, playlist["uuid"], playlist["title"]): playlist["uuid"]
                for playlist in playlists
                if not self._abort_requested.is_set()
            }

            # Collect results as they complete
            for i, future in enumerate(as_completed(futures)):
                if self._abort_requested.is_set():
                    executor.shutdown(wait=False)
                    break

                playlist_uuid: str = futures[future]

                try:
                    track_ids: set[str] = future.result()

                    # Add this playlist to cache for each track
                    for track_id in track_ids:
                        if track_id not in cache:
                            cache[track_id] = set()
                        cache[track_id].add(playlist_uuid)

                except RequestException as e:
                    logger_gui.debug(f"Request error for playlist {playlist_uuid}: {e}")
                    continue
                except Exception as e:
                    logger_gui.debug(f"Unexpected error for playlist {playlist_uuid}: {e}")
                    continue
                else:
                    # Emit progress
                    self.signals.progress.emit(i + 1, len(futures))

        return cache

    def _extract_track_ids_from_response(self, data: dict) -> set[str]:
        """Extract track IDs from API response data.

        Args:
            data: Response data from playlist items API

        Returns:
            Set of track ID strings
        """
        track_ids: set[str] = set()
        for it in data.get("items", []):
            item = it.get("item", {})
            tid = str(item.get("id")) if item.get("id") is not None else None
            if tid:
                track_ids.add(tid)
        return track_ids

    def _fetch_via_request_hook(self, playlist_uuid: str, playlist_name: str) -> set[str]:
        """Fetch playlist items using low-level request hook (for testing).

        Args:
            playlist_uuid: UUID of the playlist
            playlist_name: Name of the playlist (for logging)

        Returns:
            Set of track ID strings
        """
        req = self.session.request
        track_ids: set[str] = set()

        # First page
        resp1 = req("GET", f"/playlists/{playlist_uuid}/items")
        data1 = resp1.json() if hasattr(resp1, "json") else {}
        track_ids.update(self._extract_track_ids_from_response(data1))

        # Second page if needed
        total = int(data1.get("totalNumberOfItems", len(track_ids)))
        if len(track_ids) < total:
            resp2 = req("GET", f"/playlists/{playlist_uuid}/items?page=2")
            data2 = resp2.json() if hasattr(resp2, "json") else {}
            track_ids.update(self._extract_track_ids_from_response(data2))

        # Log loaded count
        playlist_display = playlist_name if playlist_name else playlist_uuid[:8]
        logger_gui.debug(f"📋 Loaded {len(track_ids)} tracks from playlist '{playlist_display}'")
        return track_ids

    def _fetch_via_tidalapi(self, playlist_uuid: str, playlist_name: str) -> set[str]:
        """Fetch playlist items using tidalapi helpers.

        Args:
            playlist_uuid: UUID of the playlist
            playlist_name: Name of the playlist (for logging)

        Returns:
            Set of track ID strings
        """
        # Get playlist object
        playlist = self.session.playlist(playlist_uuid)

        # Use centralized API helper to get all items
        items = get_playlist_items(playlist)

        # Extract track IDs - normalize all IDs to strings
        track_ids: set[str] = set()
        for item in items:
            if hasattr(item, "id") and item.id is not None:
                tid = str(item.id)
                track_ids.add(tid)

                # Debug first items (gated; disabled by default)
                if len(track_ids) <= 3:
                    track_name = getattr(item, "name", "Unknown")
                    logger_gui.debug(f"  [{playlist_name}...] Track '{track_name}' ID: {tid} (type: {type(item.id)})")

        # Log loaded count
        playlist_display = playlist_name if playlist_name else playlist_uuid[:8]
        logger_gui.debug(f"📋 Loaded {len(track_ids)} tracks from playlist '{playlist_display}'")
        return track_ids

    def _fetch_playlist_items(self, playlist_uuid: str, playlist_name: str = "") -> set[str]:
        """Fetch all track IDs from a single playlist using tidalapi helpers.

        Args:
            playlist_uuid: UUID of the playlist
            playlist_name: Name of the playlist (for logging)

        Returns:
            Set of track UUIDs in this playlist
        """
        try:
            req = getattr(self.session, "request", None)
            if callable(req):
                return self._fetch_via_request_hook(playlist_uuid, playlist_name)

            return self._fetch_via_tidalapi(playlist_uuid, playlist_name)

        except RequestException:
            raise
        except Exception as e:
            logger_gui.debug(f"Unexpected error fetching items for {playlist_uuid}: {e}")
            raise RequestException(f"Failed to fetch items for playlist {playlist_uuid}: {e}") from e  # noqa: TRY003

    def request_abort(self) -> None:
        """Request graceful abortion of the loader.

        Sets abort flag; loader will finish current request then stop.
        Safe to call from any thread.
        """
        self._abort_requested.set()


class PlaylistColumnDelegate(QtWidgets.QStyledItemDelegate):
    """Custom delegate for rendering the "Playlists" column.

    Displays different states:
    - PENDING: QtWaitingSpinner widget (loading)
    - READY: Clickable button (ready to open dialog)
    - ERROR: Warning icon (error occurred)

    Emits: button_clicked signal when cell is clicked in READY state.

    Example:
        delegate = PlaylistColumnDelegate(parent=table)
        table.setItemDelegateForColumn(9, delegate)
        delegate.button_clicked.connect(self.on_playlist_button_clicked)
    """

    # Signals
    button_clicked: QtCore.Signal = QtCore.Signal(QtCore.QModelIndex)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        """Initialize the delegate.

        Args:
            parent: Parent widget (table view)
        """
        super().__init__(parent)
        self._cache_ready: bool = False
        self._cell_states: dict[str, PlaylistCellState] = {}
        self._spinner: QtWaitingSpinner | None = None
        # Reference to cache to compute counts
        self._cache: ThreadSafePlaylistCache | None = None
        # Column index of the hidden obj storing Track (default 1 as per model)
        self._obj_column_index: int = 1

        # Create spinner widget for PENDING state
        if parent:
            self._spinner = QtWaitingSpinner(parent, centerOnParent=False, disableParentWhenSpinning=False)
            self._spinner.setNumberOfLines(12)
            self._spinner.setLineLength(4)
            self._spinner.setLineWidth(2)
            self._spinner.setInnerRadius(4)
            self._spinner.setColor(QtGui.QColor(100, 150, 255))
            self._spinner.hide()  # Hidden by default

    def set_cache(self, cache: ThreadSafePlaylistCache) -> None:
        """Attach cache reference for count rendering."""
        self._cache = cache

    def set_obj_column_index(self, col: int) -> None:
        self._obj_column_index = col

    def paint(
        self,
        painter: QtGui.QPainter,
        option: QtWidgets.QStyleOptionViewItem,
        index: QtCore.QModelIndex,
    ) -> None:
        """Paint the cell contents based on current state.

        Args:
            painter: QPainter for drawing
            option: Style options (selection, hover, etc.)
            index: Model index of the cell
        """
        # Determine state
        row_key: str = str(index.row())
        state: PlaylistCellState = self._cell_states.get(row_key, PlaylistCellState.PENDING)

        # Auto-initialize to READY if cache is ready and state is unknown (scroll scenario)
        if state == PlaylistCellState.PENDING and self._cache_ready:
            state = PlaylistCellState.READY
            self._cell_states[row_key] = PlaylistCellState.READY

        # Draw background
        super().paint(painter, option, index)

        # Calculate content rect (inside cell)
        content_rect: QtCore.QRect = option.rect.adjusted(4, 4, -4, -4)

        if state == PlaylistCellState.PENDING:
            # Show spinner for this cell
            if self._spinner:
                # Position spinner in cell
                spinner_size = self._spinner.width()
                center_x = content_rect.center().x() - spinner_size // 2
                center_y = content_rect.center().y() - spinner_size // 2

                self._spinner.move(center_x, center_y)
                self._spinner.show()

                # Ensure spinner is running
                if not self._spinner.isSpinning():
                    self._spinner.start()
        elif state == PlaylistCellState.READY:
            self._paint_button(painter, content_rect, option, index)
        elif state == PlaylistCellState.ERROR:
            self._paint_error(painter, content_rect)

    def _paint_button(
        self,
        painter: QtGui.QPainter,
        rect: QtCore.QRect,
        option: QtWidgets.QStyleOptionViewItem,
        index: QtCore.QModelIndex,
    ) -> None:
        """Paint clickable button for READY state.

        Args:
            painter: QPainter for drawing
            rect: Area to paint in
            option: Style options (for hover effects)
            index: Model index to get track data from
        """
        # Draw button background
        is_hovered: bool = bool(option.state & QtWidgets.QStyle.StateFlag.State_MouseOver)
        bg_color: QtGui.QColor = QtGui.QColor(220, 240, 255) if is_hovered else QtGui.QColor(240, 240, 240)

        painter.fillRect(rect, bg_color)

        # Draw button border
        painter.setPen(QtGui.QPen(QtGui.QColor(100, 150, 255), 1))
        painter.drawRect(rect)

        # Draw text/icon
        text_color: QtGui.QColor = QtGui.QColor(50, 100, 200) if is_hovered else QtGui.QColor(100, 120, 150)
        painter.setPen(text_color)

        # Compute playlists count for this track
        count_text = "0"
        parent = self.parent()
        track_id = None

        if isinstance(parent, QtWidgets.QTreeView) and self._cache is not None:
            model = parent.model()
            try:
                # Try to resolve track_id if index is valid
                if index.isValid():
                    # Resolve to source index if proxy model is used
                    if isinstance(model, QtCore.QSortFilterProxyModel):
                        source_index = model.mapToSource(index)
                        source_model = model.sourceModel()
                    else:
                        source_index = index
                        source_model = model

                    # Only proceed if source index is valid
                    source_row = source_index.row()
                    if source_row >= 0:
                        # For QStandardItemModel, use item() directly
                        if hasattr(source_model, "item"):
                            obj_item = source_model.item(source_row, self._obj_column_index)
                            obj_data = obj_item.data(QtCore.Qt.ItemDataRole.UserRole) if obj_item else None
                        else:
                            # Fallback for other model types
                            obj_idx = source_model.index(source_row, self._obj_column_index)
                            obj_data = obj_idx.data(QtCore.Qt.ItemDataRole.UserRole)

                        if obj_data is not None:
                            tid = getattr(obj_data, "id", None)
                            if tid is not None:
                                track_id = str(tid)
                                playlists_for_track = self._cache.get_playlists_for_track(track_id)
                                count = len(playlists_for_track)
                                count_text = str(count)

                                # Suppress noisy zero-playlist debug logs
                                # (kept silent unless VERBOSE_DEBUG is enabled)
                                track_name = getattr(obj_data, "name", "Unknown")
                                sample_keys = list(self._cache._data.keys())[:5]
                                is_in_cache = track_id in self._cache._data
                                logger_gui.debug(f"⚠️ Track '{track_name}' (ID: {track_id}) shows 0 playlists")
                                logger_gui.debug(f"  Is track ID '{track_id}' in cache? {is_in_cache}")
                                logger_gui.debug(f"  Sample cache keys: {sample_keys}")

            except Exception as e:
                logger_gui.error(f"Error getting track playlist count: {e}", exc_info=True)

        # Always draw text with count (fallback to "0" if track_id not found)
        # Pluralize "Playlist" → "Playlists" if count > 1
        count_int = int(count_text) if count_text.isdigit() else 0
        text = f"({count_text}) Playlist" if count_int <= 1 else f"({count_text}) Playlists"
        painter.drawText(rect, QtCore.Qt.AlignmentFlag.AlignCenter, text)

    def _paint_error(self, painter: QtGui.QPainter, rect: QtCore.QRect) -> None:
        """Paint error icon for ERROR state.

        Args:
            painter: QPainter for drawing
            rect: Area to paint in
        """
        # Draw warning icon
        text: str = "⚠️"
        font: QtGui.QFont = QtGui.QFont()
        font.setPointSize(10)
        painter.setFont(font)

        painter.setPen(QtGui.QColor(200, 150, 50))
        painter.drawText(rect, QtCore.Qt.AlignmentFlag.AlignCenter, text)

    def set_cell_state(self, row: int, state: PlaylistCellState) -> None:
        """Update the state of a cell.

        Args:
            row: Row index
            state: New state (PENDING, READY, ERROR)
        """
        row_key: str = str(row)
        self._cell_states[row_key] = state

    def set_cache_ready(self, is_ready: bool) -> None:
        """Notify delegate that cache loading is complete.

        Args:
            is_ready: True if cache is ready, False if loading started
        """
        self._cache_ready = is_ready

        if not is_ready:
            # Cache loading started - reset to PENDING
            if self._spinner and not self._spinner.isSpinning():
                self._spinner.start()
            return

        # Cache is ready - transition ALL rows to READY state
        parent = self.parent()
        if isinstance(parent, QtWidgets.QTreeView):
            model = parent.model()
            if model is not None:
                rows = model.rowCount()
                for r in range(rows):
                    self._cell_states[str(r)] = PlaylistCellState.READY

        # Stop spinner
        if self._spinner and self._spinner.isSpinning():
            self._spinner.stop()
            self._spinner.hide()

        # Force repaint
        if isinstance(parent, QtWidgets.QWidget):
            try:
                if hasattr(parent, "viewport"):
                    parent.viewport().update()
                    parent.viewport().repaint()
            except RuntimeError:
                pass

    def editorEvent(
        self,
        event: QtCore.QEvent,
        model: QtCore.QAbstractItemModel,
        option: QtWidgets.QStyleOptionViewItem,
        index: QtCore.QModelIndex,
    ) -> bool:
        """Handle mouse events on the cell.

        Args:
            event: The event
            model: The model
            option: Style options
            index: Model index

        Returns:
            True if event was handled
        """
        if event.type() == QtCore.QEvent.Type.MouseButtonRelease:
            row_key: str = str(index.row())
            state: PlaylistCellState = self._cell_states.get(row_key, PlaylistCellState.PENDING)

            if state == PlaylistCellState.READY:
                self.button_clicked.emit(index)
                return True

        return super().editorEvent(event, model, option, index)
