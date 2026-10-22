import os
import sys
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

APP_VERSION = "0.0.1"


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
if _env_path is not None:
    load_dotenv(_env_path)
elif not getattr(sys, "frozen", False):
    # Development convenience: also honour a .env in the current directory.
    load_dotenv()

# Production project credentials as fallback for packaged installers
_FALLBACK_URL = "https://kjqbnurycfjsuufibkac.supabase.co"
_FALLBACK_KEY = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImtqcWJudXJ5Y2Zqc3V1Zmlia2FjIiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTE1NzM1NjcsImV4cCI6MjEwNzE0OTU2N30."
    "6KBkUy6fcD3jGRVmfNUvDZtnK9siQFOJ8KBDvDL0JGM"
)

SUPABASE_URL = os.environ.get("SUPABASE_URL", "") or _FALLBACK_URL
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", "") or _FALLBACK_KEY


def config_error() -> str | None:
    """Return a safe, user-facing configuration error, or ``None`` if valid.

    Values are never included in the message (no URL, no key material).
    """
    url = (SUPABASE_URL or "").strip()
    key = (SUPABASE_ANON_KEY or "").strip()
    if not url:
        return (
            "Supabase URL is missing. Add SUPABASE_URL to the .env file next to "
            "RESIVO.exe (or use the bundled configuration)."
        )
    if not key:
        return (
            "Supabase anon key is missing. Add SUPABASE_ANON_KEY to the .env file "
            "next to RESIVO.exe (or use the bundled configuration)."
        )
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return (
            "SUPABASE_URL is not a valid http(s) URL. Fix the .env file next to "
            "RESIVO.exe and start the app again."
        )
    return None
