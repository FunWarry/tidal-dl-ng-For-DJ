# Compilation mode, support OS-specific options
# nuitka-project-if: {OS} in ("Darwin"):
#    nuitka-project: --macos-create-app-bundle
#    nuitka-project: --macos-app-icon=tidal_dl_ng/ui/icon.icns
#    nuitka-project: --macos-signed-app-name=com.exislow.TidalDlNg
#    nuitka-project: --macos-app-mode=gui
# nuitka-project-if: {OS} in ("Linux", "FreeBSD"):
#    nuitka-project: --linux-icon=tidal_dl_ng/ui/icon512.png
# nuitka-project-if: {OS} in ("Windows"):
#    nuitka-project: --windows-icon-from-ico=tidal_dl_ng/ui/icon.ico
#    nuitka-project: --file-description="TIDAL media downloader next generation."

# Debugging options, controlled via environment variable at compile time.
# nuitka-project-if: {OS} == "Windows" and os.getenv("DEBUG_COMPILATION", "no") == "yes":
#    nuitka-project: --windows-console-mode=hide
# nuitka-project-else:
#    nuitka-project: --windows-console-mode=disable
# nuitka-project-if: os.getenv("DEBUG_COMPILATION", "no") == "yes":
#    nuitka-project: --debug
#    nuitka-project: --debugger
#    nuitka-project: --experimental=allow-c-warnings
#    nuitka-project: --no-debug-immortal-assumptions
#    nuitka-project: --run
# nuitka-project-else:
#    nuitka-project: --assume-yes-for-downloads
# nuitka-project-if: os.getenv("DEPLOYMENT", "no") == "yes":
#    nuitka-project: --deployment

# The PySide6 plugin covers qt-plugins
# nuitka-project: --standalone
# nuitka-project: --output-dir=dist
# nuitka-project: --enable-plugin=pyside6
# nuitka-project: --include-qt-plugins=qml
# nuitka-project: --noinclude-dlls=libQt6Charts*
# nuitka-project: --noinclude-dlls=libQt6Quick3D*
# nuitka-project: --noinclude-dlls=libQt6Sensors*
# nuitka-project: --noinclude-dlls=libQt6Test*
# nuitka-project: --noinclude-dlls=libQt6WebEngine*
# nuitka-project: --include-data-files={MAIN_DIRECTORY}/ui/icon*=tidal_dl_ng/ui/
# nuitka-project: --include-data-files={MAIN_DIRECTORY}/ui/default_album_image.png=tidal_dl_ng/ui/default_album_image.png
# nuitka-project: --include-data-files=./pyproject.toml=pyproject.toml
# nuitka-project: --force-stderr-spec="{TEMP}/tidal-dl-ng.err.log"
# nuitka-project: --force-stdout-spec="{TEMP}/tidal-dl-ng.out.log"
# nuitka-project: --company-name=exislow

"""Backward-compatible GUI entry point.

The legacy :mod:`tidal_dl_ng.gui` module now delegates to the modular
implementation located under :mod:`tidal_dl_ng.gui.*`.
"""

from tidal_dl_ng.gui.activate import gui_activate
from tidal_dl_ng.gui.main_window import MainWindow

__all__ = ["MainWindow", "gui_activate"]


if __name__ == "__main__":
    gui_activate()
