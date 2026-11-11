"""Installer command construction and detached launch."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess

from . import config
from .downloader import UpdateError

__all__ = ["build_installer_command", "launch_installer"]

# Module-level alias so tests can substitute a fake process without touching
# the real subprocess module.
Popen = subprocess.Popen


def _absolute(path) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def build_installer_command(path) -> list[str]:
    """Return the silent installer command line for ``path``."""
    return [str(_absolute(path)), *config.INSTALLER_SILENT_FLAGS]


def launch_installer(
    path,
    *,
    allowed_dir: str | os.PathLike[str] | None = None,
) -> subprocess.Popen:
    """Launch the installer fully detached and return the ``Popen`` handle.

    The executable must exist, end in ``.exe`` and live inside the updates
    directory (or ``allowed_dir`` when supplied).  Raises
    :class:`UpdateError` with ``bad_installer_path`` otherwise.
    """
    base = Path(allowed_dir) if allowed_dir is not None else config.updates_dir()
    try:
        resolved = Path(path).resolve()
        base_resolved = base.resolve()
        inside = resolved.is_relative_to(base_resolved)
    except (OSError, ValueError):
        raise UpdateError("bad_installer_path") from None

    if resolved.suffix.lower() != ".exe" or not resolved.is_file() or not inside:
        raise UpdateError("bad_installer_path")

    command = build_installer_command(resolved)
    kwargs: dict = {
        "args": command,
        "cwd": str(resolved.parent),
        "close_fds": True,
        "shell": False,
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
    }
    if os.name == "nt":
        kwargs["creationflags"] = (
            subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
        )
    return Popen(**kwargs)
