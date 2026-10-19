import os
import pytest
from app.client import make_client, sign_in, current_role


@pytest.mark.skipif(
    not os.environ.get("RUN_LIVE_TESTS"),
    reason="Requires live test Supabase environment (set RUN_LIVE_TESTS=1)",
)
def test_staff_sign_in_and_role():
    client = make_client()
    sign_in(client, "staff@residence.test", "Staff1234!")
    assert current_role(client) == "staff"


def test_current_role_handles_exception_safely():
    class BrokenClient:
        @property
        def auth(self):
            raise RuntimeError("Network offline")

    assert current_role(BrokenClient()) is None