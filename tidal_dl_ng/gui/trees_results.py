"""Trees and results mixin for MainWindow.

Handles tree view population and results display.
"""

import contextlib
import math
from collections.abc import Callable, Sequence

from PySide6 import QtCore, QtGui, QtWidgets
from tidalapi import Album, Artist, Mix, Playlist, Track, UserPlaylist, Video
from tidalapi.playlist import Folder

from tidal_dl_ng.constants import FAVORITES, TidalLists
from tidal_dl_ng.helper.gui import (
    HumanProxyModel,
    get_results_media_item,
    get_user_list_media_item,
    set_user_list_media,
)
from tidal_dl_ng.helper.tidal import favorite_function_factory, items_results_all, user_media_lists
from tidal_dl_ng.model.gui_data import ResultItem


class TreesResultsMixin:
    """Mixin containing tree view and results management methods."""

    def handle_filter_activated(self) -> None:
        """Handle activation of filter headers in the results tree."""
        header = self.tr_results.header()
        filters: list[tuple[int, str]] = []
        for i in range(header.count()):
            text: str = header.filter_text(i)
            if text:
                filters.append((i, text))

        proxy_model: HumanProxyModel = self.tr_results.model()
        proxy_model.filters = filters

    def populate_tree_results(self, results: list[ResultItem], parent: QtGui.QStandardItem | None = None) -> None:
        """Populate the results tree with ResultItem objects."""
        if not parent:
            self.model_tr_results.removeRows(0, self.model_tr_results.rowCount())

        count_digits: int = int(math.log10(len(results) if results else 1)) + 1

        for item in results:
            child: tuple = self.populate_tree_result_child(item=item, index_count_digits=count_digits)

            if parent:
                parent.appendRow(child)
            else:
                self.s_tr_results_add_top_level_item.emit(child)

    def populate_tree_result_child(self, item: ResultItem, index_count_digits: int) -> Sequence[QtGui.QStandardItem]:
        """Create a row of QStandardItems for a ResultItem."""
        duration: str = ""

        if item.duration_sec > -1:
            m, s = divmod(item.duration_sec, 60)
            duration: str = f"{m:02d}:{s:02d}"

        index: str = str(item.position + 1).zfill(index_count_digits)

        child_index: QtGui.QStandardItem = QtGui.QStandardItem(index)
        child_obj: QtGui.QStandardItem = QtGui.QStandardItem()
        child_obj.setData(item.obj, QtCore.Qt.ItemDataRole.UserRole)

        child_artist: QtGui.QStandardItem = QtGui.QStandardItem(item.artist)
        child_title: QtGui.QStandardItem = QtGui.QStandardItem(item.title)
        child_album: QtGui.QStandardItem = QtGui.QStandardItem(item.album)
        child_duration: QtGui.QStandardItem = QtGui.QStandardItem(duration)
        child_quality: QtGui.QStandardItem = QtGui.QStandardItem(item.quality)
        child_date: QtGui.QStandardItem = QtGui.QStandardItem(
            item.date_user_added if item.date_user_added != "" else item.date_release
        )

        child_downloaded: QtGui.QStandardItem = QtGui.QStandardItem()
        child_playlists: QtGui.QStandardItem = QtGui.QStandardItem()

        if isinstance(item.obj, Track):
            track_id = str(item.obj.id)
            if self.history_service.is_downloaded(track_id):
                child_downloaded.setText("✅")
                child_downloaded.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            # Store track_id in playlists column for lookup
            child_playlists.setData(track_id, QtCore.Qt.ItemDataRole.UserRole)

        if isinstance(item.obj, Mix | Playlist | Album | Artist):
            child_dummy: QtGui.QStandardItem = QtGui.QStandardItem()
            child_dummy.setEnabled(False)
            child_index.appendRow(child_dummy)

        return (
            child_index,
            child_obj,
            child_artist,
            child_title,
            child_album,
            child_duration,
            child_quality,
            child_date,
            child_downloaded,
            child_playlists,
        )

    def on_tr_results_add_top_level_item(self, item_child: Sequence[QtGui.QStandardItem]):
        """Add a top-level item to the results tree model."""
        self.model_tr_results.appendRow(item_child)

    def on_tr_results_expanded(self, index: QtCore.QModelIndex) -> None:
        """Handle the event when a result item group is expanded."""
        self.thread_it(self.tr_results_expanded, index)

    def tr_results_expanded(self, index: QtCore.QModelIndex) -> None:
        """Load and display the children of an expanded result item."""
        item: QtGui.QStandardItem = self.model_tr_results.itemFromIndex(self.proxy_tr_results.mapToSource(index))
        load_children: bool = not item.child(0, 0).isEnabled()

        if load_children:
            item.removeRow(0)
            media_list = get_results_media_item(index, self.proxy_tr_results, self.model_tr_results)

            self.s_spinner_start.emit(self.tr_results)

            try:
                self.list_items_show_result(media_list=media_list, parent=item)
            finally:
                self.s_spinner_stop.emit()

    def list_items_show_result(
        self,
        media_list: Album | Playlist | Mix | Artist | None = None,
        point: QtCore.QPoint | None = None,
        parent: QtGui.QStandardItem | None = None,
        favorite_function: Callable | None = None,
    ) -> None:
        """Populate the results tree with the items of a media list."""
        if point:
            item = self.tr_lists_user.itemAt(point)
            media_list = get_user_list_media_item(item)

        if favorite_function or isinstance(media_list, str):
            if isinstance(media_list, str):
                favorite_function = favorite_function_factory(self.tidal, media_list)
            media_items: list[Track | Video | Album] = favorite_function()
        else:
            media_items: list[Track | Video | Album] = items_results_all(self.tidal.session, media_list)

        result: list[ResultItem] = self.search_manager.search_result_to_model(media_items)
        self.populate_tree_results(result, parent=parent)

    def tidal_user_lists(self) -> None:
        """Fetch and emit user playlists, mixes, and favorites from Tidal."""
        self.s_spinner_start.emit(self.tr_lists_user)
        self.s_pb_reload_status.emit(False)

        user_all: dict[str, list] = user_media_lists(self.tidal.session)
        self.s_populate_tree_lists.emit(user_all)

    def on_populate_tree_lists(self, user_lists: dict[str, list]) -> None:
        """Populate the user lists tree with playlists, mixes, and favorites."""
        twi_playlists: QtWidgets.QTreeWidgetItem = self.tr_lists_user.findItems(
            TidalLists.Playlists, QtCore.Qt.MatchExactly, 0
        )[0]
        twi_mixes: QtWidgets.QTreeWidgetItem = self.tr_lists_user.findItems(
            TidalLists.Mixes, QtCore.Qt.MatchExactly, 0
        )[0]
        twi_favorites: QtWidgets.QTreeWidgetItem = self.tr_lists_user.findItems(
            TidalLists.Favorites, QtCore.Qt.MatchExactly, 0
        )[0]

        for twi in [twi_playlists, twi_mixes]:
            for i in reversed(range(twi.childCount())):
                twi.removeChild(twi.child(i))

        for item in user_lists.get("playlists", []):
            if isinstance(item, Folder):
                twi_child = QtWidgets.QTreeWidgetItem(twi_playlists)
                name: str = f"📁 {item.name}"
                info: str = f"({item.total_number_of_items} items)" if item.total_number_of_items else ""
                twi_child.setText(0, name)
                set_user_list_media(twi_child, item)
                twi_child.setText(2, info)

                dummy_child = QtWidgets.QTreeWidgetItem(twi_child)
                dummy_child.setDisabled(True)
            elif isinstance(item, UserPlaylist | Playlist):
                twi_child = QtWidgets.QTreeWidgetItem(twi_playlists)
                name: str = item.name if getattr(item, "name", None) is not None else ""
                description: str = f" {item.description}" if item.description else ""
                info: str = f"({item.num_tracks + item.num_videos} Tracks){description}"
                twi_child.setText(0, name)
                set_user_list_media(twi_child, item)
                twi_child.setText(2, info)

        for item in user_lists.get("mixes", []):
            if isinstance(item, Mix):
                twi_child = QtWidgets.QTreeWidgetItem(twi_mixes)
                name: str = item.title
                info: str = item.sub_title
                twi_child.setText(0, name)
                set_user_list_media(twi_child, item)
                twi_child.setText(2, info)

        for i in reversed(range(twi_favorites.childCount())):
            twi_favorites.removeChild(twi_favorites.child(i))

        for key, favorite in FAVORITES.items():
            twi_child = QtWidgets.QTreeWidgetItem(twi_favorites)
            name: str = favorite["name"]
            info: str = ""

            twi_child.setText(0, name)
            set_user_list_media(twi_child, key)
            twi_child.setText(2, info)

        self.s_spinner_stop.emit()
        self.s_pb_reload_status.emit(True)

    def on_track_hover_confirmed(self, media: Track | Video | Album | Mix | Playlist | Artist) -> None:
        """Handle confirmed hover event over a track (after debounce delay)."""
        if not media:
            return

        self.info_tab_widget.update_on_hover(media)

        if self.cover_manager:
            self.cover_manager.load_cover(media, use_cache_check=True)

    def on_track_hover_left(self) -> None:
        """Handle hover leaving the track list."""
        with contextlib.suppress(Exception):
            self.info_tab_widget.revert_to_selection()

        if self.info_tab_widget.current_media_selected and self.cover_manager:
            self.cover_manager.load_cover(self.info_tab_widget.current_media_selected, use_cache_check=True)
