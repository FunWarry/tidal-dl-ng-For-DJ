"""Context menus mixin for MainWindow.

Handles context menu creation and actions.
"""

import time
import urllib.parse

from PySide6 import QtCore, QtGui, QtWidgets
from tidalapi import Album, Artist, Mix, Playlist, Track, UserPlaylist, Video

from tidal_dl_ng.constants import QueueDownloadStatus
from tidal_dl_ng.helper.gui import get_results_media_item, get_user_list_media_item
from tidal_dl_ng.helper.tidal import items_results_all, name_builder_artist
from tidal_dl_ng.logger import logger_gui
from tidal_dl_ng.model.gui_data import StatusbarMessage


class ContextMenusMixin:
    """Mixin containing context menu methods."""

    def menu_context_tree_results(self, point: QtCore.QPoint) -> None:
        """Show context menu for results tree."""
        index = self.tr_results.indexAt(point)

        if not index.isValid():
            return

        media = get_results_media_item(index, self.proxy_tr_results, self.model_tr_results)

        menu = QtWidgets.QMenu()

        if isinstance(media, Track | Video) and hasattr(media, "album") and media.album:
            menu.addAction("Download Full Album", lambda: self.thread_download_album_from_track(point))

        if isinstance(media, Track):
            track_id = str(media.id)
            is_downloaded = self.history_service.is_downloaded(track_id)

            if is_downloaded:
                menu.addAction(
                    "✖️ Mark as Not Downloaded", lambda: self.on_mark_track_as_not_downloaded(track_id, index)
                )
            else:
                menu.addAction("✅ Mark as Downloaded", lambda: self.on_mark_track_as_downloaded(media, index))

        menu.addAction("Copy Share URL", lambda: self.on_copy_url_share(self.tr_results, point))

        menu.exec(self.tr_results.mapToGlobal(point))

    def menu_context_queue_download(self, point: QtCore.QPoint) -> None:
        """Show context menu for download queue."""
        item = self.tr_queue_download.itemAt(point)

        if not item:
            return

        menu = QtWidgets.QMenu()

        status = item.text(0)
        if status == QueueDownloadStatus.Waiting:
            menu.addAction("🗑️ Remove from Queue", lambda: self.on_queue_download_remove_item(item))

        if menu.isEmpty():
            return

        menu.exec(self.tr_queue_download.mapToGlobal(point))

    def on_queue_download_remove_item(self, item: QtWidgets.QTreeWidgetItem) -> None:
        """Remove a specific item from the download queue."""
        index = self.tr_queue_download.indexOfTopLevelItem(item)
        if index >= 0:
            self.tr_queue_download.takeTopLevelItem(index)
            logger_gui.info("Removed item from download queue")

    def on_copy_url_share(
        self, tree_target: QtWidgets.QTreeWidget | QtWidgets.QTreeView, point: QtCore.QPoint = None
    ) -> None:
        """Copy the share URL of a media item to the clipboard."""
        if isinstance(tree_target, QtWidgets.QTreeWidget):
            item: QtWidgets.QTreeWidgetItem = tree_target.itemAt(point)
            media = get_user_list_media_item(item)
        else:
            index: QtCore.QModelIndex = tree_target.indexAt(point)
            media = get_results_media_item(index, self.proxy_tr_results, self.model_tr_results)

        clipboard = QtWidgets.QApplication.clipboard()
        url_share = media.share_url if hasattr(media, "share_url") else "No share URL available."

        clipboard.clear()
        clipboard.setText(url_share)

    def thread_download_list_media(self, point: QtCore.QPoint) -> None:
        """Start download of a list media item in a thread."""
        self.thread_it(self.playlist_manager.on_download_list_media, point)

    def thread_download_album_from_track(self, point: QtCore.QPoint) -> None:
        """Starts the download of the full album from a selected track in a new thread."""
        self.thread_it(self.on_download_album_from_track, point)

    def on_download_album_from_track(self, point: QtCore.QPoint) -> None:
        """Adds the album associated with a selected track to the download queue."""
        index: QtCore.QModelIndex = self.tr_results.indexAt(point)
        media_track: Track = get_results_media_item(index, self.proxy_tr_results, self.model_tr_results)

        if isinstance(media_track, Track) and media_track.album and media_track.album.id:
            try:
                full_album_object = self.tidal.session.album(media_track.album.id)

                queue_dl_item = self.search_manager.media_to_queue_download_model(full_album_object)

                if queue_dl_item:
                    self.queue_download_media(queue_dl_item)
                else:
                    logger_gui.warning(f"Failed to create a queue item for album ID: {full_album_object.id}")
            except Exception as e:
                logger_gui.error(f"Could not fetch the full album from TIDAL. Error: {e}")
        else:
            logger_gui.warning("Could not retrieve album information from the selected track.")

    def on_download_all_albums_from_playlist(self, point: QtCore.QPoint) -> None:
        """Download all unique albums from tracks in a playlist."""
        try:
            item = self.tr_lists_user.itemAt(point)
            media_list = get_user_list_media_item(item)

            if not isinstance(media_list, Playlist | UserPlaylist | Mix):
                logger_gui.error("Please select a playlist or mix.")
                return

            logger_gui.info(f"Fetching all tracks from: {media_list.name}")
            media_items = items_results_all(self.tidal.session, media_list)

            album_ids = self._extract_album_ids_from_tracks(media_items)

            if not album_ids:
                logger_gui.warning("No albums found in this playlist.")
                return

            logger_gui.info(f"Found {len(album_ids)} unique albums. Loading with rate limiting...")

            albums_dict = self._load_albums_with_rate_limiting(album_ids)

            if not albums_dict:
                logger_gui.error("Failed to load any albums from playlist.")
                return

            self._queue_loaded_albums(albums_dict)

            message = f"Added {len(albums_dict)} albums to download queue"
            self.s_statusbar_message.emit(StatusbarMessage(message=message, timeout=3000))
            logger_gui.info(message)

        except Exception as e:
            error_msg = f"Error downloading albums from playlist: {e!s}"
            logger_gui.error(error_msg)
            self.s_statusbar_message.emit(StatusbarMessage(message=error_msg, timeout=3000))

    def _extract_album_ids_from_tracks(self, media_items: list) -> dict[int, Album]:
        """Extract unique album IDs from a list of media items."""
        album_ids = {}

        for media_item in media_items:
            if not isinstance(media_item, Track | Video):
                continue

            if not hasattr(media_item, "album") or not media_item.album:
                continue

            try:
                album_id = media_item.album.id
                if album_id:
                    album_ids[album_id] = media_item.album
            except Exception as e:
                logger_gui.debug(f"Skipping track with unavailable album: {e!s}")
                continue

        return album_ids

    def _load_albums_with_rate_limiting(self, album_ids: dict[int, Album]) -> dict[int, Album]:
        """Load full album objects with rate limiting to prevent API throttling."""
        albums_dict = {}
        batch_size = self.settings.data.api_rate_limit_batch_size
        delay_sec = self.settings.data.api_rate_limit_delay_sec

        for idx, album_id in enumerate(album_ids.keys(), start=1):
            try:
                if idx > 1 and (idx - 1) % batch_size == 0:
                    logger_gui.info(f"⏰ RATE LIMITING: Processed {idx - 1} albums, pausing for {delay_sec} seconds...")
                    time.sleep(delay_sec)

                if not self.tidal.session.check_login():
                    logger_gui.error("Session expired. Please restart the application and login again.")
                    return albums_dict

                album = self.tidal.session.album(album_id)
                albums_dict[album.id] = album
                logger_gui.debug(f"Loaded album {idx}/{len(album_ids)}: {name_builder_artist(album)} - {album.name}")

            except Exception as e:
                if not self._handle_album_load_error(e, album_id):
                    return albums_dict
                continue

        logger_gui.info(f"Successfully loaded {len(albums_dict)} albums.")
        return albums_dict

    def _handle_album_load_error(self, error: Exception, album_id: int) -> bool:
        """Handle errors that occur when loading an album."""
        if self.tidal.is_authentication_error(error):
            error_msg = str(error)
            logger_gui.error(f"Authentication error: {error_msg}")
            logger_gui.error("Your session has expired. Please restart the application and login again.")
            self.s_statusbar_message.emit(
                StatusbarMessage(message="Session expired - please restart and login", timeout=5000)
            )
            return False

        logger_gui.warning(f"Failed to load album {album_id}: {error!s}")
        logger_gui.info(
            "Note: Some albums may be unavailable due to region restrictions or removal from TIDAL. This is normal."
        )
        return True

    def _queue_loaded_albums(self, albums_dict: dict[int, Album]) -> None:
        """Prepare and add loaded albums to the download queue."""
        logger_gui.info(f"Preparing queue items for {len(albums_dict)} albums...")

        queue_items = []
        for album in albums_dict.values():
            queue_dl_item = self.queue_manager.media_to_queue_download_model(album)
            if queue_dl_item:
                queue_items.append((queue_dl_item, album))
                logger_gui.debug(f"Prepared: {name_builder_artist(album)} - {album.name}")

        logger_gui.info(f"Adding {len(queue_items)} albums to queue...")
        for queue_dl_item, album in queue_items:
            self.queue_manager.queue_download_media(queue_dl_item)
            logger_gui.info(f"Added: {name_builder_artist(album)} - {album.name}")

    def on_search_in_app(self, search_term: str, search_type: str):
        """Perform a search within the application, selecting the correct category."""
        self.l_search.setText(search_term)

        search_type_map = {
            "artist": Artist,
            "album": Album,
            "track": Track,
            "video": Video,
            "playlist": Playlist,
        }
        search_category = search_type_map.get(search_type.lower(), self.cb_search_type.currentData())

        for i in range(self.cb_search_type.count()):
            if self.cb_search_type.itemData(i) == search_category:
                self.cb_search_type.setCurrentIndex(i)
                break

        self.search_manager.search_populate_results(search_term, search_category)

    def on_search_in_browser(self, search_term: str, search_type: str):
        """Open a search in the default web browser."""
        safe_term = urllib.parse.quote(search_term)
        search_path_map = {
            "artist": "artists",
            "album": "albums",
            "track": "tracks",
            "video": "videos",
            "playlist": "playlists",
        }
        search_path = search_path_map.get(search_type.lower())

        if search_path:
            url = QtCore.QUrl(f"https://listen.tidal.com/search/{search_path}?q={safe_term}")
        else:
            url = QtCore.QUrl(f"https://listen.tidal.com/search?q={safe_term}")

        QtGui.QDesktopServices.openUrl(url)
