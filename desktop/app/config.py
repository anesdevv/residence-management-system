import os
import sys
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

APP_VERSION = "0.1.1"


def _env_candidates() -> list[Path]:
    """Config file search order.

    Frozen builds prefer a ``.env`` next to ``RESIVO.exe`` (so support can fix
    the deployment without rebuilding), then the file bundled as ``_MEIPASS``.
    Development keeps the historical desktop/ then repository-root order.
    """
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        candidates = [exe_dir / ".env"]
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidates.append(Path(meipass) / ".env")
        return candidates

    desktop_dir = Path(__file__).resolve().parent.parent
    return [
        desktop_dir / ".env",
        desktop_dir.parent / ".env",
    ]


_env_path = next((path for path in _env_candidates() if path.is_file()), None)
_ENV_SOURCE = "fallback"
if _env_path is not None:
    load_dotenv(_env_path, encoding="utf-8")
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        _ENV_SOURCE = "exe_dir" if _env_path.parent == exe_dir else "bundled"
    else:
        desktop_dir = Path(__file__).resolve().parent.parent
        _ENV_SOURCE = "desktop_env" if _env_path.parent == desktop_dir else "repo_env"
elif not getattr(sys, "frozen", False):
    # Development convenience: also honour a .env in the current directory.
    if load_dotenv(encoding="utf-8"):
        _ENV_SOURCE = "cwd_env"

# Production project credentials as fallback for packaged installers
_FALLBACK_URL = "https://kjqbnurycfjsuufibkac.supabase.co"
_FALLBACK_KEY = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImtqcWJudXJ5Y2Zqc3V1Zmlia2FjIiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTE1NzM1NjcsImV4cCI6MjEwNzE0OTU2N30."
    "6KBkUy6fcD3jGRVmfNUvDZtnK9siQFOJ8KBDvDL0JGM"
)

SUPABASE_URL = os.environ.get("SUPABASE_URL", "") or _FALLBACK_URL
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", "") or _FALLBACK_KEY

# ---------------------------------------------------------------------------
# Session persistence constants (Staff Stay Signed In)
# ---------------------------------------------------------------------------
SESSION_MAX_AGE_HOURS: int = 168  # 7 days
SESSION_MAX_AGE_SECONDS: int = SESSION_MAX_AGE_HOURS * 3600
SESSION_ENTROPY: bytes = b"RESIVO_STAFF_SESSION_ENTROPY_V1"

from .timeouts import (
    CONNECT_TIMEOUT_S,
    READ_TIMEOUT_S,
    WRITE_TIMEOUT_S,
    STORAGE_DOWNLOAD_TIMEOUT_S,
    STORAGE_UPLOAD_TIMEOUT_S,
    EDGE_FUNCTION_TIMEOUT_S,
)


def config_source() -> str:
    """Return a safe description of where config was loaded from (no secrets)."""
    return _ENV_SOURCE


def config_error_code() -> str | None:
    """Return ``'missing_url'``, ``'missing_key'``, ``'invalid_url'``, or ``None``."""
    url = (SUPABASE_URL or "").strip()
    key = (SUPABASE_ANON_KEY or "").strip()
    if not url:
        return "missing_url"
    if not key:
        return "missing_key"
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return "invalid_url"
    return None


def config_error() -> str | None:
    """Return a safe, user-facing configuration error, or ``None`` if valid.

    Values are never included in the message (no URL, no key material).
    """
    code = config_error_code()
    if code == "missing_url":
        return (
            "Supabase URL is missing. Add SUPABASE_URL to the .env file next to "
            "RESIVO.exe (or use the bundled configuration)."
        )
    if code == "missing_key":
        return (
            "Supabase anon key is missing. Add SUPABASE_ANON_KEY to the .env file "
            "next to RESIVO.exe (or use the bundled configuration)."
        )
    if code == "invalid_url":
        return (
            "SUPABASE_URL is not a valid http(s) URL. Fix the .env file next to "
            "RESIVO.exe and start the app again."
        )
    return None
