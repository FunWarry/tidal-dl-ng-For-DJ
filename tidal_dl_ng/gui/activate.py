"""GUI activation and entry point for TIDAL Downloader Next Generation."""

import sys

from tidal_dl_ng import __version__
from tidal_dl_ng.config import Tidal

try:
    import qdarktheme
    from PySide6 import QtCore, QtGui, QtWidgets
except ImportError as e:
    print(e)
    print("Qt dependencies missing. Cannot start GUI. Please read the 'README.md' carefully.")
    sys.exit(1)


def gui_activate(tidal: Tidal | None = None):
    """Activate the GUI application.

    Args:
        tidal (Tidal | None): Optional pre-existing Tidal session.
    """
    from tidal_dl_ng.gui.main_window import MainWindow

    # Set dark theme and create QT app
    qdarktheme.enable_hi_dpi()
    app = QtWidgets.QApplication(sys.argv)

    # Fix for Windows: Tooltips have bright font color
    # https://github.com/5yutan5/PyQtDarkTheme/issues/239
    qdarktheme.setup_theme(additional_qss="QToolTip { border: 0px; }")

    # Create icon object and apply it to app window
    icon: QtGui.QIcon = QtGui.QIcon()

    icon.addFile("tidal_dl_ng/ui/icon16.png", QtCore.QSize(16, 16))
    icon.addFile("tidal_dl_ng/ui/icon32.png", QtCore.QSize(32, 32))
    icon.addFile("tidal_dl_ng/ui/icon48.png", QtCore.QSize(48, 48))
    icon.addFile("tidal_dl_ng/ui/icon64.png", QtCore.QSize(64, 64))
    icon.addFile("tidal_dl_ng/ui/icon256.png", QtCore.QSize(256, 256))
    icon.addFile("tidal_dl_ng/ui/icon512.png", QtCore.QSize(512, 512))
    app.setWindowIcon(icon)

    # This bit gets the taskbar icon working properly in Windows
    if sys.platform.startswith("win"):
        import ctypes

        # Make sure Pyinstaller icons are still grouped
        if not sys.argv[0].endswith(".exe"):
            # Arbitrary string
            my_app_id: str = "exislow.tidal.dl-ng." + __version__
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(my_app_id)

    window = MainWindow(tidal=tidal)

    window.show()

    exit_code = app.exec()
    sys.exit(exit_code)


if __name__ == "__main__":
    gui_activate()
