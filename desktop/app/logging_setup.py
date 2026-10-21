"""Application logging and crash safety for the desktop client.

The packaged build runs with ``console=False``, so tracebacks must be written to
a rotating file before the first window exists.  This module deliberately keeps
the log path and the user-facing text in one place so both development and
PyInstaller builds behave the same way.
"""

from __future__ import annotations

import logging
import os
import sys
import tempfile
import threading
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QMetaObject, QObject, Qt, QUrl, Slot
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QApplication, QMessageBox

_LOGGER_NAME = "resivo"
_LOG_FILENAME = "app.log"
_MAX_BYTES = 1_000_000
_BACKUP_COUNT = 3
_configured = False
_active_log_path: Path | None = None
_reporter: "_ExceptionReporter | None" = None


def app_data_dir() -> Path:
    """Return the per-user application data directory."""
    override = os.environ.get("RESIVO_DATA_DIR")
    if override:
        return Path(override)
    base = os.environ.get("APPDATA")
    if base:
        return Path(base) / "RESIVO"
    return Path.home() / ".resivo"


def log_dir() -> Path:
    return app_data_dir() / "logs"


def _fallback_log_dir() -> Path:
    """Writable fallback when the roaming profile is unavailable/locked."""
    return Path(tempfile.gettempdir()) / "RESIVO" / "logs"


def log_path() -> Path:
    return _active_log_path or (log_dir() / _LOG_FILENAME)


def setup_logging() -> Path:
    """Configure the rotating app log without ever preventing startup.

    A locked or unwritable ``%APPDATA%`` is realistic on managed Windows
    machines.  The client still starts and falls back to the temporary folder;
    an unhandled ``OSError`` here used to make a ``console=False`` build look
    like it never launched at all.
    """
    global _configured, _active_log_path
    if _configured:
        return log_path()

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)-8s [%(threadName)s] %(name)s: %(message)s"
    )

    primary_dir = log_dir()
    candidates = [primary_dir]
    fallback_dir = _fallback_log_dir()
    if fallback_dir != primary_dir:
        candidates.append(fallback_dir)

    handler = None
    chosen_path = primary_dir / _LOG_FILENAME
    primary_error: OSError | None = None
    for directory in candidates:
        candidate = directory / _LOG_FILENAME
        try:
            directory.mkdir(parents=True, exist_ok=True)
            handler = RotatingFileHandler(
                candidate,
                maxBytes=_MAX_BYTES,
                backupCount=_BACKUP_COUNT,
                encoding="utf-8",
            )
        except OSError as exc:
            if not candidates or directory == primary_dir:
                primary_error = exc
            continue
        chosen_path = candidate
        break

    if handler is None:
        # Last resort: keep the process alive even if no file can be opened.
        root.addHandler(logging.NullHandler())
        _active_log_path = primary_dir / _LOG_FILENAME
        _configured = True
        return _active_log_path

    handler.setFormatter(formatter)
    root.addHandler(handler)
    _active_log_path = chosen_path

    # Keep third-party request logs out of the file: they can contain URLs and
    # occasional request metadata, but the app never needs them for diagnosis.
    for name in ("httpx", "httpcore", "urllib3", "gotrue", "postgrest"):
        logging.getLogger(name).setLevel(logging.WARNING)

    _configured = True
    logger = logging.getLogger(_LOGGER_NAME)
    if chosen_path != primary_dir / _LOG_FILENAME and primary_error is not None:
        logger.warning(
            "Could not write the app log to %s (%s); using %s",
            primary_dir / _LOG_FILENAME,
            primary_error,
            chosen_path,
        )
    logger.info("Logging started: %s", chosen_path)
    return chosen_path


def _notify_user(message: str) -> None:
    """Show a non-fatal, non-modal error dialog on the GUI thread."""
    global _reporter
    if _reporter is None:
        return
    _reporter.request(message)


class _ExceptionReporter(QObject):
    """Queues exception notifications onto the Qt GUI thread.

    ``sys.excepthook`` already runs on the GUI thread for slot errors, but
    ``threading.excepthook`` and Qt events can arrive from a worker.  Using a
    queued Qt invocation avoids touching widgets off-thread.
    """

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._pending: str | None = None
        self._dialog: QMessageBox | None = None

    def request(self, message: str) -> None:
        self._pending = message
        try:
            QMetaObject.invokeMethod(
                self, "_show_pending", Qt.ConnectionType.QueuedConnection
            )
        except Exception:  # pragma: no cover - Qt unavailable during shutdown
            logging.getLogger(_LOGGER_NAME).exception(
                "Could not queue the error dialog"
            )

    @Slot()
    def _show_pending(self) -> None:
        message = self._pending or (
            "Something went wrong. The error was saved to the log file."
        )
        self._pending = None
        app = QApplication.instance()
        if app is None:
            return
        # Avoid a pile of dialogs if the event loop is failing repeatedly.
        if self._dialog is not None and self._dialog.isVisible():
            return

        box = QMessageBox()
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("RÉSIVO")
        box.setText(message)
        box.setInformativeText(f"Log file: {log_path()}")
        box.setStandardButtons(QMessageBox.StandardButton.Close)
        open_button = box.addButton(
            "Open log folder", QMessageBox.ButtonRole.ActionRole
        )
        open_button.clicked.connect(self._open_log_folder)
        box.setModal(False)
        box.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        box.finished.connect(self._dialog_closed)
        self._dialog = box
        box.open()

    @Slot()
    def _dialog_closed(self) -> None:
        self._dialog = None

    @Slot()
    def _open_log_folder(self) -> None:
        folder = log_path().parent
        folder.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))


def _handle_exception(
    exc_type: type[BaseException],
    exc: BaseException,
    tb,
    *,
    context: str,
    notify: Callable[[str], None] | None = None,
) -> None:
    logging.getLogger(_LOGGER_NAME).critical(
        "Unhandled exception (%s)", context, exc_info=(exc_type, exc, tb)
    )
    message = "Something went wrong. The error was saved to the log file."
    if notify is not None:
        notify(message)
    else:
        _notify_user(message)


def install_exception_hooks(
    *, notify: Callable[[str], None] | None = None
) -> None:
    """Install sys/threading/Qt exception handlers.

    ``notify`` is injectable for tests.  In normal use the module-level dialog
    reporter is created here, after the QApplication exists.
    """
    global _reporter
    if notify is None and QApplication.instance() is not None and _reporter is None:
        _reporter = _ExceptionReporter()

    def _sys_hook(exc_type, exc, tb):
        _handle_exception(exc_type, exc, tb, context="main thread", notify=notify)

    def _thread_hook(args):
        _handle_exception(
            args.exc_type,
            args.exc_value,
            args.exc_traceback,
            context=f"thread {getattr(args.thread, 'name', 'unknown')}",
            notify=notify,
        )

    sys.excepthook = _sys_hook
    threading.excepthook = _thread_hook

    try:
        from PySide6.QtCore import qInstallMessageHandler

        qInstallMessageHandler(_qt_message_handler)
    except Exception:  # pragma: no cover - Qt should always be present
        logging.getLogger(_LOGGER_NAME).exception("Could not install Qt log handler")


def _qt_message_handler(mode, context, message) -> None:
    """Persist Qt warnings without turning them into modal dialogs."""
    logger = logging.getLogger("resivo.qt")
    level = logging.INFO
    try:
        from PySide6.QtCore import QtMsgType

        if mode in (
            QtMsgType.QtWarningMsg,
            QtMsgType.QtCriticalMsg,
        ):
            level = logging.WARNING
        elif mode == QtMsgType.QtFatalMsg:
            level = logging.CRITICAL
    except Exception:  # pragma: no cover
        pass
    logger.log(level, "%s", message)


class SafeApplication(QApplication):
    """Catch Python exceptions escaping Qt event delivery.

    Without this, PySide6 may terminate a ``--noconsole`` process after an
    exception in a slot, losing all evidence.  Returning ``False`` drops only
    the failing event and lets the window continue.
    """

    def notify(self, receiver, event) -> bool:  # noqa: N802 - Qt API
        try:
            return super().notify(receiver, event)
        except BaseException:
            exc_type, exc, tb = sys.exc_info()
            _handle_exception(
                exc_type,
                exc,
                tb,
                context="Qt event",
            )
            return False
