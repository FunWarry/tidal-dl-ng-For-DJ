"""Initialization mixin for MainWindow.

Handles all initialization-related methods for the GUI components.
"""

from collections.abc import Iterable
from typing import Any

from ansi2html import Ansi2HTMLConverter
from PySide6 import QtCore, QtGui, QtWidgets
from rich.progress import Progress

from tidal_dl_ng.config import HandlingApp
from tidal_dl_ng.download import Download
from tidal_dl_ng.helper.gui import FilterHeader, HumanProxyModel
from tidal_dl_ng.helper.path import resource_path
from tidal_dl_ng.logger import logger_gui
from tidal_dl_ng.model.gui_data import ProgressBars
from tidal_dl_ng.ui.spinner import QtWaitingSpinner


class InitializationMixin:
    """Mixin containing initialization methods for MainWindow."""

    def _init_gui(self) -> None:
        """Initialize GUI-specific variables and state."""
        self.setGeometry(
            self.settings.data.window_x,
            self.settings.data.window_y,
            self.settings.data.window_w,
            self.settings.data.window_h,
        )
        self.spinners: dict[QtWidgets.QWidget, QtWaitingSpinner] = {}
        self.converter_ansi_html: Ansi2HTMLConverter = Ansi2HTMLConverter()

    def _init_threads(self):
        """Initialize thread pool and start background workers."""
        self.threadpool = QtCore.QThreadPool()
        self.thread_it(self.queue_manager.watcher_queue_download)

    def _init_dl(self):
        """Initialize Download object and related progress bars."""
        data_pb: ProgressBars = ProgressBars(
            item=self.s_item_advance,
            list_item=self.s_list_advance,
            item_name=self.s_item_name,
            list_name=self.s_list_name,
        )
        progress: Progress = Progress()
        handling_app: HandlingApp = HandlingApp()
        self.dl = Download(
            tidal_obj=self.tidal,
            skip_existing=self.tidal.settings.data.skip_existing,
            path_base=self.settings.data.download_base_path,
            fn_logger=logger_gui,
            progress_gui=data_pb,
            progress=progress,
            event_abort=handling_app.event_abort,
            event_run=handling_app.event_run,
        )

    def _init_progressbar(self):
        """Initialize and add progress bars to the status bar."""
        self.pb_list = QtWidgets.QProgressBar()
        self.pb_item = QtWidgets.QProgressBar()
        pbs = [self.pb_list, self.pb_item]

        for pb in pbs:
            pb.setRange(0, 100)
            self.statusbar.addPermanentWidget(pb)

    def _init_info(self):
        """Set default album cover image in the GUI."""
        path_image: str = resource_path("tidal_dl_ng/ui/default_album_image.png")
        self.l_pm_cover.setPixmap(QtGui.QPixmap(path_image))

    def _init_tree_results(self, tree: QtWidgets.QTreeView, model: QtGui.QStandardItemModel) -> None:
        """Initialize the results tree view and its model."""
        header: FilterHeader = FilterHeader(tree)
        self.proxy_tr_results: HumanProxyModel = HumanProxyModel(self)

        tree.setHeader(header)
        tree.setModel(model)
        self.proxy_tr_results.setSourceModel(model)
        tree.setModel(self.proxy_tr_results)
        header.set_filter_boxes(model.columnCount())
        header.filter_activated.connect(self.handle_filter_activated)

        tree.sortByColumn(0, QtCore.Qt.SortOrder.AscendingOrder)
        tree.setColumnHidden(1, True)
        normal_width = max(150, (self.width() * 0.13))
        narrow_width = max(90, (self.width() * 0.06))
        skinny_width = max(60, (self.width() * 0.03))
        tree.setColumnWidth(2, normal_width)
        tree.setColumnWidth(3, normal_width)
        tree.setColumnWidth(4, normal_width)
        tree.setColumnWidth(5, skinny_width)
        tree.setColumnWidth(6, narrow_width)
        tree.setColumnWidth(7, narrow_width)
        tree.setColumnWidth(8, skinny_width)
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)

        tree.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        tree.customContextMenuRequested.connect(self.menu_context_tree_results)

        from tidal_dl_ng.helper.hover_manager import HoverManager

        self.hover_manager = HoverManager(
            tree_view=tree,
            proxy_model=self.proxy_tr_results,
            source_model=model,
            debounce_delay_ms=50,
            parent=self,
        )
        self.hover_manager.s_hover_confirmed.connect(self.on_track_hover_confirmed)
        self.hover_manager.s_hover_left.connect(self.on_track_hover_left)

    def _init_tree_results_model(self, model: QtGui.QStandardItemModel) -> None:
        """Initialize the model for the results tree view."""
        labels_column: list[str] = [
            "#",
            "obj",
            "Artist",
            "Title",
            "Album",
            "Duration",
            "Quality",
            "Date",
            "Downloaded?",
            "Playlists",
        ]
        model.setColumnCount(len(labels_column))
        model.setRowCount(0)
        model.setHorizontalHeaderLabels(labels_column)

    def _init_tree_queue(self, tree: QtWidgets.QTableWidget) -> None:
        """Initialize the download queue table widget."""
        tree.setColumnHidden(1, True)
        tree.setColumnWidth(2, 200)

        header = tree.header()
        if hasattr(header, "setSectionResizeMode"):
            header.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
        tree.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        tree.customContextMenuRequested.connect(self.menu_context_queue_download)

    def _init_tree_lists(self, tree: QtWidgets.QTreeWidget) -> None:
        """Initialize the user lists tree widget."""
        tree.setColumnWidth(0, 200)
        tree.setColumnHidden(1, True)
        tree.setColumnWidth(2, 300)
        tree.expandAll()

        tree.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        tree.customContextMenuRequested.connect(self.playlist_manager.menu_context_tree_lists)

    def _init_menu_actions(self) -> None:
        """Initialize custom menu actions."""
        menubar = self.menuBar()
        tools_menu = None

        for action in menubar.actions():
            if action.text() == "Tools":
                tools_menu = action.menu()
                break

        if not tools_menu:
            tools_menu = menubar.addMenu("Tools")

        self.a_view_history = QtGui.QAction("View Download History...", self)
        self.a_view_history.triggered.connect(self.on_view_history)
        tools_menu.addAction(self.a_view_history)

        tools_menu.addSeparator()

        self.a_toggle_duplicate_prevention = QtGui.QAction("Prevent Duplicate Downloads", self)
        self.a_toggle_duplicate_prevention.setCheckable(True)
        is_preventing = self.history_service.get_settings().get("preventDuplicates", True)
        self.a_toggle_duplicate_prevention.setChecked(is_preventing)
        self.a_toggle_duplicate_prevention.triggered.connect(self.on_toggle_duplicate_prevention)
        tools_menu.addAction(self.a_toggle_duplicate_prevention)

    def _populate_quality(self, ui_target: QtWidgets.QComboBox, options: Iterable[Any]) -> None:
        """Populate a combo box with quality options."""
        for item in options:
            ui_target.addItem(item.name, item)

    def _populate_search_types(self, ui_target: QtWidgets.QComboBox, options: Iterable[Any]) -> None:
        """Populate a combo box with search type options."""
        for item in options:
            if item:
                ui_target.addItem(item.__name__, item)
        self.cb_search_type.setCurrentIndex(2)
