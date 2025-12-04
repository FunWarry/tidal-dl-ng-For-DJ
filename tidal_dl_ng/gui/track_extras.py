"""Track extras mixin for MainWindow.

Handles track extras caching and retrieval.
"""

import contextlib
from collections.abc import Callable

from PySide6 import QtCore

from tidal_dl_ng.helper.tidal import extract_contributor_names, fetch_raw_track_and_album, parse_track_and_album_extras
from tidal_dl_ng.worker import Worker


class TrackExtrasMixin:
    """Mixin containing track extras management methods."""

    def get_track_extras(self, track_id: str, callback: Callable[[str, dict | None], None]) -> dict | None:
        """Return cached extras for a track or start async fetch."""
        cached = self.track_extras_cache.get(track_id)
        if cached is not None:
            return cached

        if track_id in self._pending_extras_workers:
            return None

        if callback:
            self._track_extras_callbacks[track_id] = callback

        def worker() -> None:
            extras = None
            try:
                track_json, album_json = fetch_raw_track_and_album(self.tidal.session, track_id)
                extras = parse_track_and_album_extras(track_json, album_json)
                extras = self._decorate_extras(extras)
                self.track_extras_cache.set(track_id, extras)
            except Exception:
                extras = None
            finally:
                self._pending_extras_workers.pop(track_id, None)
                self.s_track_extras_ready.emit(track_id, extras)
                self.s_invoke_callback.emit(track_id, extras)

        worker_obj = Worker(worker)
        self._pending_extras_workers[track_id] = worker_obj
        self.threadpool.start(worker_obj)
        return None

    @QtCore.Slot(str, object)
    def _on_invoke_callback(self, track_id: str, extras: dict | None) -> None:
        """Invoke the stored callback for a track in the main thread."""
        callback = self._track_extras_callbacks.pop(track_id, None)
        if callback:
            with contextlib.suppress(Exception):
                callback(track_id, extras)

    def _decorate_extras(self, extras: dict | None) -> dict:
        """Add formatted string fields to extras dict."""
        if not extras:
            return {}
        result = dict(extras)
        result["genres_text"] = ", ".join(result.get("genres", []))
        for role, key in [
            ("producer", "producers_text"),
            ("composer", "composers_text"),
            ("lyricist", "lyricists_text"),
        ]:
            result[key] = extract_contributor_names(result.get("contributors_by_role"), role)
        return result

    def preload_covers_for_playlist(self, items: list) -> None:
        """Preload cover pixmaps for a list of tracks in background."""
        if self.cover_manager:
            self.cover_manager.preload_covers_for_playlist(items)
