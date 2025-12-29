"""Main window for TIDAL Downloader Next Generation.

This module combines all GUI functionality through mixins to create
the main application window.
"""

from collections.abc import Callable

from PySide6 import QtCore, QtGui, QtWidgets
from tidalapi import Quality

from tidal_dl_ng.cache import TrackExtrasCache
from tidal_dl_ng.config import HandlingApp, Settings, Tidal
from tidal_dl_ng.constants import QualityVideo
from tidal_dl_ng.download import Download
from tidal_dl_ng.gui.context_menus import ContextMenusMixin
from tidal_dl_ng.gui.covers import CoverManager
from tidal_dl_ng.gui.downloads import DownloadsMixin
from tidal_dl_ng.gui.history import HistoryMixin
from tidal_dl_ng.gui.initialization import InitializationMixin
from tidal_dl_ng.gui.playlist import GuiPlaylistManager
from tidal_dl_ng.gui.playlist_membership_mixin import PlaylistMembershipMixin
from tidal_dl_ng.gui.progress import ProgressMixin
from tidal_dl_ng.gui.queue import GuiQueueManager
from tidal_dl_ng.gui.search import GuiSearchManager
from tidal_dl_ng.gui.signals import SignalsMixin
from tidal_dl_ng.gui.tidal_session import TidalSessionMixin
from tidal_dl_ng.gui.track_extras import TrackExtrasMixin
from tidal_dl_ng.gui.trees_results import TreesResultsMixin
from tidal_dl_ng.gui.ui_helpers import UIHelpersMixin
from tidal_dl_ng.gui.updates import UpdatesMixin
from tidal_dl_ng.helper.gui import HumanProxyModel
from tidal_dl_ng.helper.hover_manager import HoverManager
from tidal_dl_ng.history import HistoryService
from tidal_dl_ng.logger import XStream, logger_gui
from tidal_dl_ng.ui.info_tab_widget import InfoTabWidget
from tidal_dl_ng.ui.main import Ui_MainWindow
from tidal_dl_ng.worker import Worker


# TODO: Make more use of Exceptions
class MainWindow(
    QtWidgets.QMainWindow,
    Ui_MainWindow,
    InitializationMixin,
    TidalSessionMixin,
    SignalsMixin,
    ProgressMixin,
    UIHelpersMixin,
    TrackExtrasMixin,
    UpdatesMixin,
    DownloadsMixin,
    TreesResultsMixin,
    ContextMenusMixin,
    HistoryMixin,
    PlaylistMembershipMixin,
):
    """Main application window for TIDAL Downloader Next Generation.

    Handles GUI setup, user interactions, and download logic through
    a combination of mixins for better code organization.
    """

    # Type hints for class attributes
    settings: Settings
    tidal: Tidal
    dl: Download
    history_service: HistoryService
    threadpool: QtCore.QThreadPool
    tray: QtWidgets.QSystemTrayIcon
    spinners: dict
    cover_url_current: str = ""
    shutdown: bool = False
    model_tr_results: QtGui.QStandardItemModel = QtGui.QStandardItemModel()
    proxy_tr_results: HumanProxyModel
    info_tab_widget: InfoTabWidget
    hover_manager: HoverManager
    queue_manager: GuiQueueManager
    playlist_manager: GuiPlaylistManager
    search_manager: GuiSearchManager
    cover_manager: CoverManager
    track_extras_cache: TrackExtrasCache
    _pending_extras_workers: dict[str, Worker]
    _track_extras_callbacks: dict[str, Callable]

    # Qt Signals
    s_spinner_start: QtCore.Signal = QtCore.Signal(QtWidgets.QWidget)
    s_spinner_stop: QtCore.Signal = QtCore.Signal()
    s_track_extras_ready: QtCore.Signal = QtCore.Signal(str, object)
    s_invoke_callback: QtCore.Signal = QtCore.Signal(str, object)
    pb_item: QtWidgets.QProgressBar
    s_item_advance: QtCore.Signal = QtCore.Signal(float)
    s_item_name: QtCore.Signal = QtCore.Signal(str)
    s_list_name: QtCore.Signal = QtCore.Signal(str)
    pb_list: QtWidgets.QProgressBar
    s_list_advance: QtCore.Signal = QtCore.Signal(float)
    s_pb_reset: QtCore.Signal = QtCore.Signal()
    s_populate_tree_lists: QtCore.Signal = QtCore.Signal(dict)
    s_populate_folder_children: QtCore.Signal = QtCore.Signal(object, list, list)
    s_statusbar_message: QtCore.Signal = QtCore.Signal(object)
    s_tr_results_add_top_level_item: QtCore.Signal = QtCore.Signal(object)
    s_settings_save: QtCore.Signal = QtCore.Signal()
    s_pb_reload_status: QtCore.Signal = QtCore.Signal(bool)
    s_update_check: QtCore.Signal = QtCore.Signal(bool)
    s_update_show: QtCore.Signal = QtCore.Signal(bool, bool, object)
    s_queue_download_item_downloading: QtCore.Signal = QtCore.Signal(object)
    s_queue_download_item_finished: QtCore.Signal = QtCore.Signal(object)
    s_queue_download_item_failed: QtCore.Signal = QtCore.Signal(object)
    s_queue_download_item_skipped: QtCore.Signal = QtCore.Signal(object)

    def __init__(self, tidal: Tidal | None = None) -> None:
        """Initialize the main window and all components.

        Args:
            tidal (Tidal | None): Optional Tidal session object.
        """
        super().__init__()
        self.setupUi(self)
        self.setWindowTitle("TIDAL Downloader Next Generation!")

        # Initialize settings first
        self.settings = Settings()

        # Initialize managers that depend on settings
        self.queue_manager = GuiQueueManager(self)
        self.playlist_manager = GuiPlaylistManager(self)
        self.search_manager = GuiSearchManager(self)
        self.info_tab_widget = InfoTabWidget(self, self.tabWidget)

        # Logging redirect
        XStream.stdout().messageWritten.connect(self._log_output)

        self.history_service = HistoryService()

        # Core components
        self._init_threads()
        self._init_gui()
        self.track_extras_cache = TrackExtrasCache()
        self._pending_extras_workers: dict[str, Worker] = {}
        self._track_extras_callbacks: dict[str, Callable] = {}

        # Managers that have dependencies
        self.cover_manager = CoverManager(self, self.threadpool, self.info_tab_widget)

        # Initialize the rest of the UI
        self.info_tab_widget.set_track_extras_provider(self.get_track_extras)
        self._init_tree_results_model(self.model_tr_results)
        self._init_tree_results(self.tr_results, self.model_tr_results)
        self.playlist_manager.init_ui()
        self.queue_manager.init_ui()
        self._init_tree_lists(self.tr_lists_user)
        self._init_tree_queue(self.tr_queue_download)
        self._init_info()
        self._init_progressbar()
        self._populate_quality(self.cb_quality_audio, Quality)
        self._populate_quality(self.cb_quality_video, QualityVideo)

        from tidalapi.session import SearchTypes

        self._populate_search_types(self.cb_search_type, SearchTypes)

        self.apply_settings(self.settings)
        self._init_menu_actions()
        self._init_signals()

        # Connect signal for invoking track extras callbacks
        self.s_invoke_callback.connect(self._on_invoke_callback)

        # Connect playlist manager signals
        self.s_populate_tree_lists.connect(self.on_populate_tree_lists)

        self.init_tidal(tidal)

        logger_gui.info("All setup.")

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        """Handle the close event of the main window.

        Args:
            event (QtGui.QCloseEvent): The close event.
        """
        logger_gui.warning("⚠️ CLOSE EVENT TRIGGERED!")
        import traceback

        logger_gui.debug("Close event traceback:")
        for line in traceback.format_stack():
            logger_gui.debug(line.strip())
        # Save the main window size and position
        self.settings.data.window_x = self.x()
        self.settings.data.window_y = self.y()
        self.settings.data.window_w = self.width()
        self.settings.data.window_h = self.height()
        self.settings.save()

        self.shutdown = True

        handling_app: HandlingApp = HandlingApp()
        handling_app.event_abort.set()

        event.accept()

    def apply_settings(self, settings: Settings) -> None:
        """Apply user settings to the GUI.

        Args:
            settings (Settings): The settings object.
        """
        quality_audio = getattr(getattr(settings, "data", None), "quality_audio", 1)
        quality_video = getattr(getattr(settings, "data", None), "quality_video", 0)
        elements = [
            {"element": self.cb_quality_audio, "setting": quality_audio, "default_id": 1},
            {"element": self.cb_quality_video, "setting": quality_video, "default_id": 0},
        ]

        for item in elements:
            idx = item["element"].findData(item["setting"])

            if idx > -1:
                item["element"].setCurrentIndex(idx)
            else:
                item["element"].setCurrentIndex(item["default_id"])

    def thread_it(self, fn: Callable, *args, **kwargs) -> None:
        """Run a function in a separate thread.

        Args:
            fn (Callable): The function to run.
            *args: Positional arguments for the function.
            **kwargs: Keyword arguments for the function.
        """
        worker = Worker(fn, *args, **kwargs)
        self.threadpool.start(worker)
