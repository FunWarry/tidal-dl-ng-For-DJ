"""Progress bars mixin for MainWindow.

Handles progress bar updates and formatting.
"""

import math


class ProgressMixin:
    """Mixin containing progress bar management methods."""

    def on_progress_reset(self):
        """Reset progress bars to zero."""
        self.pb_list.setValue(0)
        self.pb_item.setValue(0)

    def on_progress_list(self, value: float) -> None:
        """Update the progress of the list progress bar."""
        self.pb_list.setValue(int(math.ceil(value)))

    def on_progress_item(self, value: float) -> None:
        """Update the progress of the item progress bar."""
        self.pb_item.setValue(int(math.ceil(value)))

    def on_progress_item_name(self, value: str) -> None:
        """Set the format of the item progress bar."""
        self.pb_item.setFormat(f"%p% {value}")

    def on_progress_list_name(self, value: str) -> None:
        """Set the format of the list progress bar."""
        self.pb_list.setFormat(f"%p% {value}")
