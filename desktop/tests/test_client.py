import os
import pytest
from app.client import make_client, sign_in, current_role


pytestmark = pytest.mark.skipif(
    not os.environ.get("SUPABASE_URL"), reason="SUPABASE_URL not set"
)


def test_staff_sign_in_and_role():
    client = make_client()
    sign_in(client, "staff@residence.test", "Staff1234!")
    assert current_role(client) == "staff"