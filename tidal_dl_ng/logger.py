import logging
import sys

import coloredlogs
from PySide6 import QtCore


class XStream(QtCore.QObject):
    _stdout = None
    _stderr = None
    messageWritten = QtCore.Signal(str)

    def flush(self):
        pass

    def fileno(self):
        return -1

    def write(self, msg):
        if not self.signalsBlocked():
            self.messageWritten.emit(msg)

    @staticmethod
    def stdout():
        if not XStream._stdout:
            XStream._stdout = XStream()
            sys.stdout = XStream._stdout
        return XStream._stdout

    @staticmethod
    def stderr():
        if not XStream._stderr:
            XStream._stderr = XStream()
            sys.stderr = XStream._stderr
        return XStream._stderr


class QtHandler(logging.Handler):
    def __init__(self):
        logging.Handler.__init__(self)

    def emit(self, record):
        record = self.format(record)

        if record:
            # originally: XStream.stdout().write("{}\n".format(record))
            XStream.stdout().write("%s\n" % record)


# --- Verbosity control -------------------------------------------------------
# If False: DEBUG and WARNING messages are suppressed (INFO/ERROR/CRITICAL shown).
# If True: DEBUG and WARNING messages are shown.
_VERBOSE_DEBUG = False


class DebugWarningFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        # Always allow INFO (and above except WARNING handled below)
        # Suppress DEBUG and WARNING when _VERBOSE_DEBUG is False
        if not _VERBOSE_DEBUG and record.levelno in (logging.DEBUG, logging.WARNING):
            return False
        return True


def enable_debug_and_warnings(enabled: bool = True):
    """Enable/disable showing DEBUG and WARNING log records globally.

    INFO/ERROR/CRITICAL are unaffected and always shown.
    """
    global _VERBOSE_DEBUG
    _VERBOSE_DEBUG = bool(enabled)


logger_gui = logging.getLogger(__name__)
handler_qt: QtHandler = QtHandler()
# log_fmt: str = "[%(asctime)s] %(levelname)s: %(message)s"
log_fmt: str = "> %(message)s"
# formatter = logging.Formatter(log_fmt)
# Configure custom level styles to make INFO messages green
level_styles = coloredlogs.DEFAULT_LEVEL_STYLES.copy()
level_styles["info"] = {"color": "green"}
formatter = coloredlogs.ColoredFormatter(fmt=log_fmt, level_styles=level_styles)
handler_qt.setFormatter(formatter)
# Apply filter to control DEBUG/WARNING visibility
handler_qt.addFilter(DebugWarningFilter())
logger_gui.addHandler(handler_qt)
logger_gui.setLevel(logging.DEBUG)

logger_cli = logging.getLogger(__name__)
handler_stream: logging.StreamHandler = logging.StreamHandler()
formatter = coloredlogs.ColoredFormatter(fmt=log_fmt, level_styles=level_styles)
handler_stream.setFormatter(formatter)
# Apply filter to control DEBUG/WARNING visibility
handler_stream.addFilter(DebugWarningFilter())
logger_cli.addHandler(handler_stream)
logger_cli.setLevel(logging.DEBUG)
