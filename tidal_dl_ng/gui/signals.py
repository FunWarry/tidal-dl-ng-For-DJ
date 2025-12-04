"""Signals mixin for MainWindow.

Handles all Qt signal definitions and connections.
"""

from PySide6 import QtCore, QtWidgets
from tidalapi import Album, Artist, Track, Video

from tidal_dl_ng.helper.gui import get_results_media_item


class SignalsMixin:
    """Mixin containing Qt signal definitions and signal connection methods."""

    def _init_signals(self) -> None:
        """Connect signals to their respective slots."""
        self.pb_download.clicked.connect(lambda: self.thread_it(self.on_download_results))
        self.pb_download_list.clicked.connect(lambda: self.thread_it(self.playlist_manager.on_download_list_media))
        self.l_search.returnPressed.connect(
            lambda: self.search_manager.search_populate_results(self.l_search.text(), self.cb_search_type.currentData())
        )
        self.pb_search.clicked.connect(
            lambda: self.search_manager.search_populate_results(self.l_search.text(), self.cb_search_type.currentData())
        )
        self.cb_quality_audio.currentIndexChanged.connect(self.on_quality_set_audio)
        self.cb_quality_video.currentIndexChanged.connect(self.on_quality_set_video)
        self.s_spinner_start[QtWidgets.QWidget].connect(self.on_spinner_start)
        self.s_spinner_stop.connect(self.on_spinner_stop)
        self.s_item_advance.connect(self.on_progress_item)
        self.s_item_name.connect(self.on_progress_item_name)
        self.s_list_name.connect(self.on_progress_list_name)
        self.s_list_advance.connect(self.on_progress_list)
        self.s_pb_reset.connect(self.on_progress_reset)
        self.s_statusbar_message.connect(self.on_statusbar_message)
        self.s_tr_results_add_top_level_item.connect(self.on_tr_results_add_top_level_item)
        self.s_settings_save.connect(self.on_settings_save)
        self.s_pb_reload_status.connect(self.button_reload_status)
        self.s_update_check.connect(lambda: self.thread_it(self.on_update_check))
        self.s_update_show.connect(self.on_version)

        # Menubar
        self.a_exit.triggered.connect(self.close)
        self.a_version.triggered.connect(self.on_version)
        self.a_preferences.triggered.connect(self.on_preferences)
        self.a_logout.triggered.connect(self.on_logout)
        self.a_updates_check.triggered.connect(lambda: self.on_update_check(False))

        # Results
        self.tr_results.expanded.connect(self.on_tr_results_expanded)
        self.tr_results.clicked.connect(self.on_result_item_clicked)
        self.tr_results.doubleClicked.connect(lambda: self.thread_it(self.on_download_results))

        # Managers
        self.queue_manager.connect_signals()
        self.playlist_manager.connect_signals()
        self.info_tab_widget.s_search_in_app.connect(self.on_search_in_app)
        self.info_tab_widget.s_search_in_browser.connect(self.on_search_in_browser)

    def on_result_item_clicked(self, index: QtCore.QModelIndex) -> None:
        """Handle the event when a result item is clicked."""
        media: Track | Video | Album | Artist = get_results_media_item(
            index, self.proxy_tr_results, self.model_tr_results
        )

        self.info_tab_widget.update_on_selection(media)
        self.thread_it(self.cover_manager.load_cover, media)

    def on_quality_set_audio(self, index: int) -> None:
        """Set the audio quality for downloads."""
        from tidalapi import Quality

        quality_data = self.cb_quality_audio.itemData(index)
        self.settings.data.quality_audio = Quality(quality_data)
        self.settings.save()
        if self.tidal:
            self.tidal.settings_apply()

    def on_quality_set_video(self, index: int) -> None:
        """Set the video quality for downloads."""
        from tidal_dl_ng.constants import QualityVideo

        self.settings.data.quality_video = QualityVideo(self.cb_quality_video.itemData(index))
        self.settings.save()
        if self.tidal:
            self.tidal.settings_apply()
