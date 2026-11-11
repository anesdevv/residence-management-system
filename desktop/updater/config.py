"""Updater configuration — public, non-secret constants only.

The app talks to the public GitHub REST API without authentication and never
carries a token.  Everything in this module is safe to ship in the EXE.
"""

from __future__ import annotations

import os
from pathlib import Path
import re

from desktop.version import __version__

# ---------------------------------------------------------------------------
# Update source (found in Step 0 from ``git remote -v``)
# ---------------------------------------------------------------------------
GITHUB_OWNER = "anesdevv"
GITHUB_REPO = "residence-management-system"

GITHUB_API_URL = (
    f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"
)
GITHUB_RELEASES_PAGE = f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/releases"

# Hosts a release download may come from.  Verified against the live redirect
# chain: github.com -> release-assets.githubusercontent.com (objects.* is the
# legacy host used by older assets).
ALLOWED_DOWNLOAD_HOSTS = frozenset(
    {
        "github.com",
        "release-assets.githubusercontent.com",
        "objects.githubusercontent.com",
    }
)

# Release convention: Setup-RESIVO-<MAJOR>.<MINOR>.<PATCH>.exe
ASSET_NAME_PATTERN = re.compile(r"^Setup-RESIVO-(\d+\.\d+\.\d+)\.exe$")
CHECKSUM_ASSET_NAME = "SHA256SUMS.txt"

# ---------------------------------------------------------------------------
# Limits and timeouts
# ---------------------------------------------------------------------------
MAX_DOWNLOAD_BYTES = 300 * 1024 * 1024  # 300 MB hard ceiling
MAX_CHECKSUM_BYTES = 128 * 1024
API_TIMEOUT_S = 10.0
DOWNLOAD_TIMEOUT_S = 30.0
CHECK_INTERVAL_HOURS = 24

USER_AGENT = f"RESIVO-Updater/{__version__} (+{GITHUB_RELEASES_PAGE})"
ACCEPT_HEADER = "application/vnd.github+json"
API_VERSION_HEADER = "2022-11-28"

# ---------------------------------------------------------------------------
# Endpoint / progress tuning
# ---------------------------------------------------------------------------
CHUNK_SIZE = 64 * 1024
INSTALLER_SILENT_FLAGS = (
    "/VERYSILENT",
    "/SUPPRESSMSGBOXES",
    "/NORESTART",
    "/CLOSEAPPLICATIONS",
    "/FORCECLOSEAPPLICATIONS",
    "/SP-",
    "/UPDATE=1",
)


def updates_dir() -> Path:
    """Directory for downloaded installers and the ETag cache."""
    override = os.environ.get("RESIVO_UPDATES_DIR")
    if override:
        return Path(override)
    local = os.environ.get("LOCALAPPDATA")
    if local:
        return Path(local) / "RESIVO" / "updates"
    return Path.home() / "AppData" / "Local" / "RESIVO" / "updates"


def preference_key(name: str) -> str:
    """QSettings key helper (single namespace for updater preferences)."""
    return f"updates/{name}"
