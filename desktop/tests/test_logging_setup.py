import logging
import sys
import threading

from desktop.app import logging_setup


def _detach_file_handlers():
    root = logging.getLogger()
    removed = []
    for handler in list(root.handlers):
        if isinstance(handler, logging.FileHandler):
            root.removeHandler(handler)
            handler.close()
            removed.append(handler)
    return removed


def test_setup_logging_creates_rotating_log(tmp_path, monkeypatch):
    monkeypatch.setenv("RESIVO_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(logging_setup, "_configured", False)
    _detach_file_handlers()

    path = logging_setup.setup_logging()
    logging.getLogger("resivo").info("rotation test")
    for handler in logging.getLogger().handlers:
        handler.flush()

    assert path == tmp_path / "logs" / "app.log"
    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert "rotation test" in text
    file_handler = next(
        h for h in logging.getLogger().handlers if isinstance(h, logging.FileHandler)
    )
    assert file_handler.maxBytes == 1_000_000
    assert file_handler.backupCount == 3


def test_setup_logging_falls_back_when_appdata_is_not_writable(tmp_path, monkeypatch):
    blocked_parent = tmp_path / "blocked"
    blocked_parent.write_text("not a directory", encoding="utf-8")
    monkeypatch.setattr(logging_setup, "log_dir", lambda: blocked_parent / "logs")
    monkeypatch.setattr(
        logging_setup, "_fallback_log_dir", lambda: tmp_path / "fallback" / "logs"
    )
    monkeypatch.setattr(logging_setup, "_configured", False)
    monkeypatch.setattr(logging_setup, "_active_log_path", None)
    _detach_file_handlers()

    try:
        path = logging_setup.setup_logging()
        logging.getLogger("resivo").warning("fallback write")
        for handler in logging.getLogger().handlers:
            handler.flush()

        assert path == tmp_path / "fallback" / "logs" / "app.log"
        assert path.exists()
        assert "fallback write" in path.read_text(encoding="utf-8")
    finally:
        _detach_file_handlers()


def test_exception_hooks_log_and_notify(tmp_path, monkeypatch):
    monkeypatch.setenv("RESIVO_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(logging_setup, "_configured", False)
    _detach_file_handlers()
    logging_setup.setup_logging()

    notifications = []
    old_sys_hook = sys.excepthook
    old_thread_hook = threading.excepthook
    try:
        logging_setup.install_exception_hooks(notify=notifications.append)
        try:
            raise ValueError("slot failure")
        except ValueError:
            sys.excepthook(*sys.exc_info())

        assert notifications == [
            "Something went wrong. The error was saved to the log file."
        ]
        for handler in logging.getLogger().handlers:
            handler.flush()
        text = (tmp_path / "logs" / "app.log").read_text(encoding="utf-8")
        assert "ValueError: slot failure" in text
        assert "Unhandled exception (main thread)" in text
    finally:
        sys.excepthook = old_sys_hook
        threading.excepthook = old_thread_hook
