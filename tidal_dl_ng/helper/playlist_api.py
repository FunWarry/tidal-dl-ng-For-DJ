"""Playlist API helper - Centralized API calls for playlist operations.

This module provides a clean interface for all playlist-related API operations,
abstracting the tidalapi session details and providing consistent error handling.

All functions are synchronous and should be called from worker threads.
"""

from requests.exceptions import RequestException
from tidalapi import Session, Track, UserPlaylist

from tidal_dl_ng.logger import logger_gui


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
        raise ValueError("User not authenticated")  # noqa: TRY003

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
        # Force refresh to get latest items
        playlist._items = None

        # Replace single-call fetching by robust pagination to retrieve ALL items
        # Some tidalapi backends return only the first N items (e.g., 100) by default.
        # We iterate with an offset/limit until exhaustion.
        all_items: list[Track] = []
        offset: int = 0
        limit: int = 100  # Use API-supported page size to avoid 400 errors

        while True:
            try:
                batch = playlist.items(offset=offset, limit=limit)
            except TypeError:
                batch = playlist.items(offset, limit)

            if not batch:
                break

            # Filter to only include Track objects
            tracks_batch = [item for item in batch if isinstance(item, Track)]
            all_items.extend(tracks_batch)

            # Progress
            offset += len(batch)

            # Safety: stop if no progress to avoid infinite loop
            if len(batch) < limit:
                break

    except RequestException as e:
        logger_gui.error(f"Failed to fetch playlist items for {playlist.id}: {e}")
        raise
    else:
        # Silenced diagnostics: previously logged first few tracks for ID normalization
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
    try:
        playlist = session.playlist(playlist_id)
        if not playlist:
            raise ValueError(f"Playlist {playlist_id} not found")  # noqa: TRY003

        # Normalize ID as int where supported
        try:
            norm_id = int(track_id)
        except (TypeError, ValueError):
            norm_id = track_id

        playlist.add([norm_id])
        # Silenced info log
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
    try:
        playlist = session.playlist(playlist_id)
        if not playlist:
            raise ValueError(f"Playlist {playlist_id} not found")  # noqa: TRY003

        # Always use index-based removal with robust pagination
        # Force refresh and paginate to get all items
        playlist._items = None
        items_all = []
        offset = 0
        limit = 100
        while True:
            try:
                batch = playlist.items(offset=offset, limit=limit)
            except TypeError:
                batch = playlist.items(offset, limit)
            if not batch:
                break
            items_all.extend(batch)
            offset += len(batch)
            if len(batch) < limit:
                break

        # Find the track index
        track_index = None
        for i, item in enumerate(items_all):
            item_id = getattr(item, "id", None)
            if str(item_id) == str(track_id):
                track_index = i
                break

        if track_index is None:
            # Silenced warning: skip quietly if not found
            return

        # Remove by index
        playlist.remove_by_index(track_index)
        # Silenced info log
    except RequestException as e:
        logger_gui.error(f"Failed to remove track {track_id} from playlist {playlist_id}: {e}")
        raise


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
