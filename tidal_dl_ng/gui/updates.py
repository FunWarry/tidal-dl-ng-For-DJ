"""Updates mixin for MainWindow.

Handles application update checking.
"""

from tidal_dl_ng import update_available
from tidal_dl_ng.dialog import DialogVersion
from tidal_dl_ng.model.meta import ReleaseLatest


class UpdatesMixin:
    """Mixin containing update checking methods."""

    def on_update_check(self, on_startup: bool = True) -> None:
        """Check for application updates and emit update signals."""
        is_available, info = update_available()

        if (on_startup and is_available) or not on_startup:
            self.s_update_show.emit(True, is_available, info)

    def on_version(
        self, update_check: bool = False, update_available: bool = False, update_info: ReleaseLatest | None = None
    ) -> None:
        """Show the version information dialog."""
        DialogVersion(self, update_check, update_available, update_info)
