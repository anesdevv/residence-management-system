import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Search for .env in desktop/, root, or frozen bundle directories
_candidates = [
    Path(__file__).resolve().parent.parent / ".env",
    Path(__file__).resolve().parent.parent.parent / ".env",
]
if getattr(sys, "frozen", False):
    _exe_dir = Path(sys.executable).parent
    _candidates.extend([_exe_dir / ".env"])
    _meipass = getattr(sys, "_MEIPASS", None)
    if _meipass:
        _candidates.append(Path(_meipass) / ".env")

for env_path in _candidates:
    if env_path.exists():
        load_dotenv(env_path)
        break

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


