"""GUI module for TIDAL Downloader Next Generation.

This module provides the main window and all GUI-related functionality
organized into manageable components.
"""

try:
    from PySide6 import QtCore, QtGui, QtWidgets
except ImportError:  # pragma: no cover - GUI deps optional in some environments
    QtCore = QtGui = QtWidgets = None

from tidal_dl_ng.gui.main_window import MainWindow

__all__ = [
    "MainWindow",
    "QtCore",
    "QtGui",
    "QtWidgets",
]
