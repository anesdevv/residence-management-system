import os
from datetime import date
import pytest

from supabase import create_client

URL = os.environ["SUPABASE_URL"]
ANON = os.environ["SUPABASE_ANON_KEY"]


def _client():
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