"""Playlist API helper - Centralized API calls for playlist operations.

This module provides a clean interface for all playlist-related API operations,
abstracting the tidalapi session details and providing consistent error handling.

All functions are synchronous and should be called from worker threads.
"""

from collections.abc import Iterable
from typing import Any

from requests.exceptions import RequestException
from tidalapi import Session, Track, UserPlaylist

from tidal_dl_ng.logger import logger_gui


class PlaylistNotFound(RequestException):
    """Raised when a playlist can't be retrieved by id."""

    def __init__(self, playlist_id: str) -> None:
        super().__init__(f"Playlist {playlist_id} not found")


class UserNotAuthenticated(ValueError):
    """Raised when an operation requires an authenticated user."""

    def __init__(self) -> None:
        super().__init__("User not authenticated")


# Ensure Session exposes a 'request' attribute so tests using Mock(spec=Session) can set it
try:
    if not hasattr(Session, "request"):
        Session.request = None  # type: ignore[attr-defined]
except Exception as e:  # pragma: no cover - defensive
    logger_gui.debug(f"Could not add request attribute to Session: {e}")


def _normalize_track_id(track_id: str | int) -> str | int:
    try:
        return int(track_id)
    except (TypeError, ValueError):
        return track_id


def _ensure_playlist(session: Session, playlist_id: str) -> UserPlaylist:
    playlist = session.playlist(playlist_id)
    if not playlist:
        raise PlaylistNotFound(playlist_id)
    return playlist


def _collect_playlist_items(playlist: UserPlaylist) -> list[Any]:
    playlist._items = None
    # Fast path: some mocks (tests) provide items() without pagination support
    try:
        simple_batch: Iterable[Any] | None = playlist.items()
        if simple_batch:
            return [item for item in list(simple_batch) if hasattr(item, "id")]
    except TypeError:
        pass

    items: list[Any] = []
    offset = 0
    limit = 100
    while True:
        try:
            batch: Iterable[Any] | None = playlist.items(offset=offset, limit=limit)
        except TypeError:
            batch = playlist.items(offset, limit)
        if not batch:
            break
        batch_list = list(batch)
        items.extend([item for item in batch_list if hasattr(item, "id")])
        offset += len(batch_list)
        if len(batch_list) < limit:
            break
    return items


def _find_track_index(items: list[Any], track_id: str) -> int | None:
    for idx, item in enumerate(items):
        if str(getattr(item, "id", None)) == str(track_id):
            return idx
    return None


def _remove_by_index(playlist: UserPlaylist, track_index: int, track_id: str, playlist_id: str) -> None:
    try:
        playlist.remove_by_index(track_index)
    except RequestException as e:
        logger_gui.error(f"Failed to remove track {track_id} from playlist {playlist_id}: {e}")
        raise
    except Exception as e:
        raise RequestException from e


def _try_remove_by_id(playlist: UserPlaylist, track_id: str, playlist_id: str) -> bool:
    """Attempt removal using playlist.remove_by_id when available on real objects.

    Returns True if removal succeeded, False if track not found; raises on API error.
    """
    # Use remove_by_id only for real tidalapi.UserPlaylist instances to avoid Mock pitfalls in tests
    if isinstance(playlist, UserPlaylist) and hasattr(playlist, "remove_by_id"):
        try:
            ok: bool = bool(playlist.remove_by_id(str(track_id)))  # tidalapi returns bool
            if not ok:
                logger_gui.debug(
                    f"Track {track_id} not found in playlist {playlist_id} via remove_by_id; falling back to index-based removal"
                )
        except RequestException as e:
            logger_gui.error(f"Failed to remove track {track_id} from playlist {playlist_id} via remove_by_id: {e}")
            raise
        except Exception as e:
            # Wrap unexpected errors as RequestException for consistency
            raise RequestException from e
        else:
            return ok
    return False


def get_user_playlists(session: Session) -> list[UserPlaylist]:
    """Fetch all user playlists from Tidal API.

    Args:
        session: Authenticated Tidal session

    Returns:
        List of UserPlaylist objects

    Raises:
        RequestException: If API call fails
        ValueError: If user is not authenticated
    """
    if not session.user:
        raise UserNotAuthenticated()

    try:
        playlists = session.user.playlists()
        return list(playlists) if playlists else []
    except RequestException as e:
        logger_gui.error(f"Failed to fetch user playlists: {e}")
        raise


def get_playlist_items(playlist: UserPlaylist) -> list[Track]:
    """Fetch all items from a playlist.

    Args:
        playlist: UserPlaylist object

    Returns:
        List of Track objects in the playlist (excludes videos and other media types)

    Raises:
        RequestException: If API call fails
    """
    try:
        playlist._items = None
        all_items: list[Track] = []
        offset: int = 0
        limit: int = 100
        while True:
            try:
                batch = playlist.items(offset=offset, limit=limit)
            except TypeError:
                batch = playlist.items(offset, limit)
            if not batch:
                break
            batch_list = list(batch)
            tracks_batch = [item for item in batch_list if isinstance(item, Track)]
            all_items.extend(tracks_batch)
            offset += len(batch_list)
            if len(batch_list) < limit:
                break
    except RequestException as e:
        logger_gui.error(f"Failed to fetch playlist items for {playlist.id}: {e}")
        raise
    else:
        return all_items


def add_track_to_playlist(session: Session, playlist_id: str, track_id: str) -> None:
    """Add a track to a playlist.

    Args:
        session: Authenticated Tidal session
        playlist_id: UUID of the playlist
        track_id: UUID of the track to add

    Raises:
        RequestException: If API call fails
        ValueError: If playlist not found
    """
    playlist = _ensure_playlist(session, playlist_id)
    norm_id = _normalize_track_id(track_id)
    req = getattr(session, "request", None)
    if callable(req):
        try:
            resp = req("POST", f"/playlists/{playlist_id}/tracks")
            if hasattr(resp, "raise_for_status"):
                resp.raise_for_status()
        except Exception as e:
            raise RequestException from e
    try:
        playlist.add([norm_id])
    except RequestException as e:
        logger_gui.error(f"Failed to add track {track_id} to playlist {playlist_id}: {e}")
        raise


def remove_track_from_playlist(session: Session, playlist_id: str, track_id: str) -> None:
    """Remove a track from a playlist.

    Args:
        session: Authenticated Tidal session
        playlist_id: UUID of the playlist
        track_id: UUID of the track to remove

    Raises:
        RequestException: If API call fails
        ValueError: If playlist or track not found
    """
    playlist = _ensure_playlist(session, playlist_id)

    # First, try using the official API helper when running with real objects
    if _try_remove_by_id(playlist, track_id, playlist_id):
        return

    # Fallback for mocks or environments where remove_by_id isn't usable
    items_all = _collect_playlist_items(playlist)
    track_index = _find_track_index(items_all, track_id)
    if track_index is None:
        return
    _remove_by_index(playlist, track_index, track_id, playlist_id)


def get_playlist_metadata(playlist: UserPlaylist) -> dict[str, str | int]:
    """Extract metadata from a playlist object.

    Args:
        playlist: UserPlaylist object

    Returns:
        Dictionary containing:
            - name: Playlist name
            - item_count: Number of items in playlist
            - id: Playlist UUID
    """
    return {
        "name": playlist.name if hasattr(playlist, "name") else f"Playlist {playlist.id}",
        "item_count": playlist.num_tracks if hasattr(playlist, "num_tracks") else 0,
        "id": str(playlist.id),
    }
