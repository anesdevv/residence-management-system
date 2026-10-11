import os
from pathlib import Path
import pytest
from supabase import create_client

# Locate .env from root or desktop/.env
for env_path in [
    Path(__file__).resolve().parent.parent / ".env",
    Path(__file__).resolve().parent.parent / "desktop" / ".env",
]:
    if env_path.exists():
        try:
            from dotenv import load_dotenv
            load_dotenv(env_path)
        except ImportError:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        k, v = k.strip(), v.strip()
                        if k and k not in os.environ:
                            os.environ[k] = v.strip("'\"")

URL = os.environ.get("SUPABASE_URL", "")
ANON = os.environ.get("SUPABASE_ANON_KEY", "")


def _client():
    if not URL or not ANON:
        pytest.skip("SUPABASE_URL and SUPABASE_ANON_KEY required for integration tests")
    return create_client(URL, ANON)


@pytest.fixture
def anon_client():
    return _client()


@pytest.fixture
def staff_client():
    c = _client()
    c.auth.sign_in_with_password({"email": "staff@residence.test", "password": "Staff1234!"})
    return c


@pytest.fixture
def student_client():
    c = _client()
    c.auth.sign_in_with_password({
        "email": "20230001@students.residence.local", "password": "Student1234!",
    })
    return c