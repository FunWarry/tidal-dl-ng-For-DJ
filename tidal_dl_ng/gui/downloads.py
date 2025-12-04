"""Downloads mixin for MainWindow.

Handles download queue and download operations.
"""

import time

from PySide6 import QtCore, QtWidgets
from tidalapi import Album, Artist, Mix, Playlist, Quality, Track, UserPlaylist, Video

from tidal_dl_ng.config import HandlingApp
from tidal_dl_ng.constants import QualityVideo, QueueDownloadStatus
from tidal_dl_ng.download import Download
from tidal_dl_ng.helper.gui import (
    get_queue_download_media,
    get_queue_download_quality_audio,
    get_queue_download_quality_video,
    get_results_media_item,
    set_queue_download_media,
)
from tidal_dl_ng.helper.path import get_format_template
from tidal_dl_ng.helper.tidal import items_results_all
from tidal_dl_ng.logger import logger_gui
from tidal_dl_ng.model.gui_data import QueueDownloadItem, StatusbarMessage


class DownloadsMixin:
    """Mixin containing download-related methods."""

    def on_download_results(self) -> None:
        """Download the selected results in the results tree."""
        items = self.tr_results.selectionModel().selectedRows()

        if len(items) == 0:
            logger_gui.error("Please select a row first.")
        else:
            for item in items:
                media = get_results_media_item(item, self.proxy_tr_results, self.model_tr_results)
                queue_dl_item: QueueDownloadItem = self.search_manager.media_to_queue_download_model(media)

                if queue_dl_item:
                    self.queue_download_media(queue_dl_item)

    def queue_download_media(self, queue_dl_item: QueueDownloadItem) -> None:
        """Add a media item to the download queue."""
        child: QtWidgets.QTreeWidgetItem = QtWidgets.QTreeWidgetItem()

        child.setText(0, queue_dl_item.status)
        set_queue_download_media(child, queue_dl_item.obj)
        child.setText(2, queue_dl_item.name)
        child.setText(3, queue_dl_item.type_media)
        child.setText(4, queue_dl_item.quality_audio)
        child.setText(5, queue_dl_item.quality_video)
        self.tr_queue_download.addTopLevelItem(child)

    def watcher_queue_download(self) -> None:
        """Monitor the download queue and process items as they become available."""
        handling_app: HandlingApp = HandlingApp()

        while not handling_app.event_abort.is_set():
            items = self.tr_queue_download.findItems(
                QueueDownloadStatus.Waiting, QtCore.Qt.MatchFlag.MatchExactly, column=0
            )

            if len(items) > 0:
                item: QtWidgets.QTreeWidgetItem = items[0]
                media = get_queue_download_media(item)
                quality_audio: Quality = get_queue_download_quality_audio(item)
                quality_video: QualityVideo = get_queue_download_quality_video(item)

                try:
                    self.s_queue_download_item_downloading.emit(item)
                    result = self.on_queue_download(media, quality_audio=quality_audio, quality_video=quality_video)

                    if result == QueueDownloadStatus.Finished:
                        self.s_queue_download_item_finished.emit(item)
                    elif result == QueueDownloadStatus.Skipped:
                        self.s_queue_download_item_skipped.emit(item)
                except Exception as e:
                    logger_gui.error(e)
                    self.s_queue_download_item_failed.emit(item)
            else:
                time.sleep(2)

    def on_queue_download_item_downloading(self, item: QtWidgets.QTreeWidgetItem) -> None:
        """Update the status of a queue download item to 'Downloading'."""
        self.queue_download_item_status(item, QueueDownloadStatus.Downloading)

    def on_queue_download_item_finished(self, item: QtWidgets.QTreeWidgetItem) -> None:
        """Update the status of a queue download item to 'Finished'."""
        self.queue_download_item_status(item, QueueDownloadStatus.Finished)

    def on_queue_download_item_failed(self, item: QtWidgets.QTreeWidgetItem) -> None:
        """Update the status of a queue download item to 'Failed'."""
        self.queue_download_item_status(item, QueueDownloadStatus.Failed)

    def on_queue_download_item_skipped(self, item: QtWidgets.QTreeWidgetItem) -> None:
        """Update the status of a queue download item to 'Skipped'."""
        self.queue_download_item_status(item, QueueDownloadStatus.Skipped)

    def queue_download_item_status(self, item: QtWidgets.QTreeWidgetItem, status: str) -> None:
        """Set the status text of a queue download item."""
        item.setText(0, status)

    def on_queue_download(
        self,
        media: Track | Album | Playlist | Video | Mix | Artist,
        quality_audio: Quality | None = None,
        quality_video: QualityVideo | None = None,
    ) -> QueueDownloadStatus:
        """Download the specified media item(s) and return the result status."""
        result: QueueDownloadStatus

        items_media: list = items_results_all(self.tidal.session, media) if isinstance(media, Artist) else [media]

        download_delay: bool = bool(isinstance(media, Track | Video) and self.settings.data.download_delay)

        for item_media in items_media:
            result = self.download(
                item_media,
                self.dl,
                delay_track=download_delay,
                quality_audio=quality_audio,
                quality_video=quality_video,
            )

        return result

    def download(
        self,
        media: Track | Album | Playlist | Video | Mix | Artist,
        dl: Download,
        delay_track: bool = False,
        quality_audio: Quality | None = None,
        quality_video: QualityVideo | None = None,
    ) -> QueueDownloadStatus:
        """Download a media item and return the result status."""
        result_dl: bool
        path_file: str
        result: QueueDownloadStatus
        self.s_pb_reset.emit()
        self.s_statusbar_message.emit(StatusbarMessage(message="Download started..."))

        file_template = get_format_template(media, self.settings)

        # Determine source information
        source_type = "manual"
        source_id = None
        source_name = None

        if isinstance(media, Album):
            source_type = "album"
            source_id = str(media.id)
            source_name = media.name
        elif isinstance(media, Playlist | UserPlaylist):
            source_type = "playlist"
            source_id = str(media.id) if hasattr(media, "id") else None
            source_name = media.name if hasattr(media, "name") else None
        elif isinstance(media, Mix):
            source_type = "mix"
            source_id = str(media.id)
            source_name = media.title
        elif isinstance(media, Track):
            if hasattr(media, "album") and media.album:
                source_type = "album"
                source_id = str(media.album.id)
                source_name = media.album.name
            else:
                source_type = "track"
                source_id = str(media.id)
                source_name = media.name

        if isinstance(media, Track | Video):
            result_dl, path_file = dl.item(
                media=media,
                file_template=file_template,
                download_delay=delay_track,
                quality_audio=quality_audio,
                quality_video=quality_video,
                source_type=source_type,
                source_id=source_id,
                source_name=source_name,
            )
        elif isinstance(media, Album | Playlist | Mix):
            dl.items(
                media=media,
                file_template=file_template,
                video_download=self.settings.data.video_download,
                download_delay=self.settings.data.download_delay,
                quality_audio=quality_audio,
                quality_video=quality_video,
                source_type=source_type,
                source_id=source_id,
                source_name=source_name,
            )

            result_dl = True
            path_file = "dummy"

        self.s_statusbar_message.emit(StatusbarMessage(message="Download finished.", timeout=2000))

        if result_dl and path_file:
            result = QueueDownloadStatus.Finished
        elif not result_dl and path_file:
            result = QueueDownloadStatus.Skipped
        else:
            result = QueueDownloadStatus.Failed

        return result
