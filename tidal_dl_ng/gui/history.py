"""History management mixin for MainWindow.

Handles download history and duplicate prevention.
"""

from PySide6 import QtCore
from tidalapi import Track

from tidal_dl_ng.dialog import DialogPreferences
from tidal_dl_ng.dialog_history import DialogHistory
from tidal_dl_ng.logger import logger_gui
from tidal_dl_ng.model.gui_data import StatusbarMessage


class HistoryMixin:
    """Mixin containing download history management methods."""

    def on_view_history(self) -> None:
        """Open the download history dialog."""
        DialogHistory(history_service=self.history_service, parent=self)

    def on_toggle_duplicate_prevention(self, enabled: bool) -> None:
        """Toggle duplicate download prevention on or off."""
        self.history_service.update_settings(preventDuplicates=enabled)
        status_msg = "enabled" if enabled else "disabled"
        logger_gui.info(f"Duplicate download prevention {status_msg}")
        self.s_statusbar_message.emit(StatusbarMessage(message=f"Duplicate prevention {status_msg}.", timeout=2500))

    def on_mark_track_as_downloaded(self, track: Track, index: QtCore.QModelIndex) -> None:
        """Mark a track as downloaded in history."""
        track_id = str(track.id)

        source_type = "manual"
        source_id = None
        source_name = None

        if hasattr(track, "album") and track.album:
            source_type = "album"
            source_id = str(track.album.id)
            source_name = track.album.name

        self.history_service.add_track_to_history(
            track_id=track_id, source_type=source_type, source_id=source_id, source_name=source_name
        )

        self._update_downloaded_column(index, True)
        logger_gui.info(f"Marked track as downloaded: {track.name}")

    def on_mark_track_as_not_downloaded(self, track_id: str, index: QtCore.QModelIndex) -> None:
        """Remove a track from download history."""
        success = self.history_service.remove_track_from_history(track_id)

        if success:
            self._update_downloaded_column(index, False)
            logger_gui.info(f"Unmarked track (ID: {track_id})")

    def _update_downloaded_column(self, index: QtCore.QModelIndex, is_downloaded: bool) -> None:
        """Update the Downloaded? column for a specific index."""
        source_index = self.proxy_tr_results.mapToSource(index)

        item = self.model_tr_results.itemFromIndex(source_index)
        if not item:
            return

        row = item.row()
        parent = item.parent()

        downloaded_item = self.model_tr_results.item(row, 8) if parent is None else parent.child(row, 8)

        if downloaded_item:
            if is_downloaded:
                downloaded_item.setText("✅")
                downloaded_item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            else:
                downloaded_item.setText("")

    def on_preferences(self) -> None:
        """Open the preferences dialog."""
        DialogPreferences(settings=self.settings, settings_save=self.s_settings_save, parent=self)

    def on_settings_save(self) -> None:
        """Save settings and re-apply them to the GUI."""
        self.settings.save()
        self.apply_settings(self.settings)
        self._init_dl()
