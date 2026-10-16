"""Unit tests for ``mcp/formatting.py`` (Step 5 of the MCP admin server task).

Pure and deterministic: no network, no file I/O, no real clock (the rate
limiter takes an injected ``now``). The expected values below are taken from
the actual code, not from the handoff summary.

Run from the repo root:
    & "mcp\\.venv\\Scripts\\python.exe" -m pytest "mcp\\tests" -q
"""

from __future__ import annotations

import json
import pathlib
import sys

# Make ``import formatting`` work without installing the mcp package.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402

import formatting  # noqa: E402
from formatting import (  # noqa: E402
    RateLimiter,
    cap_limit,
    empty_message,
    to_compact_json,
    token_is_valid,
    truncate_records,
    truncate_text,
    validate_status,
)


# ---------------------------------------------------------------------------
# Constants: the contract the rest of the server relies on
# ---------------------------------------------------------------------------


def test_constants_match_the_contract():
    assert formatting.MAX_FREE_TEXT == 500
    assert formatting.DEFAULT_LIMIT == 20
    assert formatting.MAX_LIMIT == 100
    assert set(formatting.FREE_TEXT_FIELDS) == {
        "description",
        "staff_note",
        "reason",
        "decision_note",
        "rejection_reason",
    }
    assert formatting.TICKET_STATUSES == ("pending", "in_progress", "resolved")
    assert formatting.ROOM_CHANGE_STATUSES == ("pending", "approved", "rejected")


# ---------------------------------------------------------------------------
# truncate_text
# ---------------------------------------------------------------------------


class TestTruncateText:
    def test_short_text_is_unchanged(self):
        assert truncate_text("short note") == "short note"
        assert truncate_text("") == ""

    def test_none_passes_through(self):
        assert truncate_text(None) is None

    def test_non_string_values_are_stringified(self):
        assert truncate_text(42) == "42"

    def test_exactly_at_limit_is_unchanged(self):
        text = "a" * formatting.MAX_FREE_TEXT
        result = truncate_text(text)
        assert result == text
        assert len(result) == formatting.MAX_FREE_TEXT
        assert not result.endswith("...")

    def test_one_over_limit_gives_exactly_limit_chars_ending_with_ellipsis(self):
        # Code: text[: limit - 3].rstrip() + "..."  ->  497 chars + "..." = 500.
        text = "a" * (formatting.MAX_FREE_TEXT + 1)
        result = truncate_text(text)
        assert result == "a" * (formatting.MAX_FREE_TEXT - 3) + "..."
        assert len(result) == formatting.MAX_FREE_TEXT
        assert result.endswith("...")

    def test_long_text_is_truncated_to_500_total(self):
        result = truncate_text("word " * 1000)
        assert len(result) == formatting.MAX_FREE_TEXT
        assert result.endswith("...")

    def test_unicode_is_counted_in_characters_not_bytes(self):
        result = truncate_text("é" * 600)
        assert len(result) == formatting.MAX_FREE_TEXT
        assert result.count("é") == formatting.MAX_FREE_TEXT - 3
        assert result.endswith("...")

    def test_trailing_whitespace_at_the_cut_point_is_stripped(self):
        # limit=10 -> keep text[:7] ("abcdef ") then rstrip -> "abcdef...".
        result = truncate_text("abcdef   ghijkl", limit=10)
        assert result == "abcdef..."
        assert len(result) <= 10

    def test_custom_limit(self):
        result = truncate_text("x" * 50, limit=10)
        assert result == "x" * 7 + "..."
        assert len(result) == 10

    def test_limit_three_produces_only_the_ellipsis_marker(self):
        assert truncate_text("abcdef", limit=3) == "..."

    def test_limit_below_three_exceeds_the_limit(self):
        # NOTE: possible bug -- the docstring promises "the result never
        # exceeds ``limit``", but the "..." marker is 3 characters, so with
        # limit < 3 the result is longer than the limit.  Observed behavior is
        # asserted as-is.  Unreachable with the default limit=500.
        result = truncate_text("abcdef", limit=2)
        assert result == "..."
        assert len(result) == 3  # contradicts the docstring, hence the note


# ---------------------------------------------------------------------------
# truncate_records
# ---------------------------------------------------------------------------


class TestTruncateRecords:
    def test_truncates_nested_free_text_fields_and_preserves_structure(self):
        long = "L" * (formatting.MAX_FREE_TEXT + 100)
        expected = "L" * (formatting.MAX_FREE_TEXT - 3) + "..."
        data = {
            "id": 7,
            "description": long,
            "staff_note": "short",
            "university": long,  # not a free-text field: untouched
            "inner": {"reason": long, "count": 3},
            "items": [
                {"decision_note": long, "label": "x"},
                {"rejection_reason": long},
            ],
            "empty": None,
        }

        out = truncate_records(data)

        assert out["id"] == 7
        assert out["description"] == expected
        assert out["staff_note"] == "short"
        assert out["university"] == long
        assert out["inner"] == {"reason": expected, "count": 3}
        assert out["items"][0] == {"decision_note": expected, "label": "x"}
        assert out["items"][1] == {"rejection_reason": expected}
        assert out["empty"] is None
        assert len(expected) == formatting.MAX_FREE_TEXT
        assert expected.endswith("...")

    def test_every_declared_free_text_field_is_truncated(self):
        long = "Z" * (formatting.MAX_FREE_TEXT + 1)
        out = truncate_records({field: long for field in formatting.FREE_TEXT_FIELDS})
        assert set(out) == set(formatting.FREE_TEXT_FIELDS)
        for field in formatting.FREE_TEXT_FIELDS:
            assert out[field] == "Z" * (formatting.MAX_FREE_TEXT - 3) + "..."

    def test_non_free_text_fields_stay_untouched_even_when_long(self):
        long = "N" * (formatting.MAX_FREE_TEXT * 2)
        assert truncate_records({"university": long, "phone": long}) == {
            "university": long,
            "phone": long,
        }

    def test_original_input_is_not_mutated(self):
        long = "M" * (formatting.MAX_FREE_TEXT * 2)
        data = {"description": long, "inner": {"reason": long}}
        truncate_records(data)
        assert data["description"] == long
        assert data["inner"]["reason"] == long

    def test_custom_fields_and_limit(self):
        data = {"notes": "abcdefghij", "description": "abcdefghij"}
        out = truncate_records(data, fields=("notes",), limit=7)
        assert out == {"notes": "abcd...", "description": "abcdefghij"}

    def test_non_string_field_values_are_untouched(self):
        out = truncate_records(
            {"description": None, "reason": 123, "staff_note": ["inline"]}
        )
        assert out == {"description": None, "reason": 123, "staff_note": ["inline"]}

    def test_scalars_and_empty_containers_pass_through(self):
        assert truncate_records("plain") == "plain"
        assert truncate_records(5) == 5
        assert truncate_records(None) is None
        assert truncate_records([]) == []
        assert truncate_records({}) == {}

    def test_truncates_inside_nested_lists_of_lists(self):
        long = "Q" * (formatting.MAX_FREE_TEXT + 5)
        out = truncate_records([[{"description": long}]])
        assert out == [[{"description": "Q" * (formatting.MAX_FREE_TEXT - 3) + "..."}]]


# ---------------------------------------------------------------------------
# cap_limit
# ---------------------------------------------------------------------------


class TestCapLimit:
    def test_none_returns_the_default(self):
        assert cap_limit(None) == formatting.DEFAULT_LIMIT == 20
        assert cap_limit(None, default=7) == 7

    @pytest.mark.parametrize("value", [1, 20, 50, formatting.MAX_LIMIT])
    def test_valid_values_pass_through(self, value):
        assert cap_limit(value) == value

    def test_values_above_the_maximum_are_capped(self):
        assert cap_limit(formatting.MAX_LIMIT + 1) == formatting.MAX_LIMIT
        assert cap_limit(10_000) == formatting.MAX_LIMIT

    def test_custom_maximum_is_respected(self):
        assert cap_limit(50, maximum=10) == 10

    def test_zero_and_negative_are_floored_to_one(self):
        assert cap_limit(0) == 1
        assert cap_limit(-5) == 1
        assert cap_limit(-0.5) == 1

    def test_numeric_strings_are_accepted_and_then_capped(self):
        assert cap_limit("30") == 30
        assert cap_limit("999") == formatting.MAX_LIMIT
        assert cap_limit("0") == 1

    def test_floats_truncate_toward_zero(self):
        assert cap_limit(2.9) == 2
        assert cap_limit(100.99) == formatting.MAX_LIMIT
        assert cap_limit(0.9) == 1

    @pytest.mark.parametrize(
        "bad",
        ["abc", "", "10.5", True, False, [], {}, object()],
        ids=["letters", "empty-string", "float-string", "true", "false", "list", "dict", "object"],
    )
    def test_invalid_input_raises_value_error(self, bad):
        with pytest.raises(ValueError, match="limit must be a number"):
            cap_limit(bad)

    def test_value_error_message_is_exact(self):
        with pytest.raises(ValueError) as excinfo:
            cap_limit("abc")
        assert str(excinfo.value) == "limit must be a number"
        assert excinfo.value.__cause__ is None  # raised with `from None`

    def test_nan_raises_value_error(self):
        with pytest.raises(ValueError, match="limit must be a number"):
            cap_limit(float("nan"))

    def test_infinity_raises_overflow_error(self):
        # NOTE: possible bug -- float("inf") is numeric, so it passes the
        # isinstance guard, but int(float("inf")) raises OverflowError, which
        # the except (TypeError, ValueError) clause does not catch.  Only
        # reachable through direct Python calls (MCP tool params are ints).
        with pytest.raises(OverflowError):
            cap_limit(float("inf"))


# ---------------------------------------------------------------------------
# validate_status
# ---------------------------------------------------------------------------


class TestValidateStatus:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("pending", "pending"),
            ("Pending", "pending"),
            ("PENDING", "pending"),
            ("in_progress", "in_progress"),
            ("In Progress", "in_progress"),
            ("in-progress", "in_progress"),
            ("IN-PROGRESS", "in_progress"),
            (" In-Progress ", "in_progress"),
            ("resolved", "resolved"),
            ("Resolved", "resolved"),
        ],
    )
    def test_normalizes_case_spaces_and_hyphens(self, value, expected):
        assert validate_status(value) == expected

    def test_none_passes_through(self):
        assert validate_status(None) is None

    def test_room_change_statuses_normalize_with_the_allowed_override(self):
        assert validate_status("Pending", formatting.ROOM_CHANGE_STATUSES) == "pending"
        assert validate_status("Approved", formatting.ROOM_CHANGE_STATUSES) == "approved"
        assert validate_status("rejected", formatting.ROOM_CHANGE_STATUSES) == "rejected"

    def test_ticket_status_is_rejected_for_room_changes(self):
        with pytest.raises(ValueError):
            validate_status("in_progress", formatting.ROOM_CHANGE_STATUSES)

    def test_invalid_value_error_message_is_exact(self):
        with pytest.raises(ValueError) as excinfo:
            validate_status("bogus")
        assert str(excinfo.value) == (
            "invalid status 'bogus': expected one of pending, in_progress, resolved"
        )

    def test_custom_label_appears_in_the_error(self):
        with pytest.raises(ValueError) as excinfo:
            validate_status("bogus", formatting.ROOM_CHANGE_STATUSES, label="room change status")
        assert str(excinfo.value) == (
            "invalid room change status 'bogus': "
            "expected one of pending, approved, rejected"
        )

    def test_non_string_invalid_values_raise(self):
        with pytest.raises(ValueError):
            validate_status(5)


# ---------------------------------------------------------------------------
# empty_message
# ---------------------------------------------------------------------------


class TestEmptyMessage:
    def test_students(self):
        assert empty_message("students") == "No students matched your search."

    def test_registrations(self):
        assert empty_message("registrations") == "No pending registrations found."

    def test_rooms_without_block(self):
        assert empty_message("rooms") == "No rooms found."
        assert empty_message("rooms", block="") == "No rooms found."

    def test_rooms_with_block(self):
        assert empty_message("rooms", block="B") == "No rooms found in block B."

    def test_tickets_without_status(self):
        assert empty_message("tickets") == "No maintenance tickets found."

    def test_tickets_with_pending_status(self):
        assert empty_message("tickets", status="pending") == "No pending maintenance tickets found."

    def test_tickets_with_in_progress_status_uses_a_hyphen(self):
        assert (
            empty_message("tickets", status="in_progress")
            == "No in-progress maintenance tickets found."
        )

    def test_room_changes_without_status(self):
        assert empty_message("room_changes") == "No room change requests found."

    def test_room_changes_with_status(self):
        assert (
            empty_message("room_changes", status="pending")
            == "No pending room change requests found."
        )

    def test_status_and_block_are_ignored_for_students_and_registrations(self):
        assert empty_message("students", status="pending") == "No students matched your search."
        assert empty_message("registrations", block="A") == "No pending registrations found."

    def test_unknown_entity_raises_key_error(self):
        with pytest.raises(KeyError):
            empty_message("bogus")


# ---------------------------------------------------------------------------
# token_is_valid
# ---------------------------------------------------------------------------


class TestTokenIsValid:
    def test_valid_token(self):
        assert token_is_valid("Bearer abc123", "abc123") is True

    @pytest.mark.parametrize("scheme", ["Bearer", "bearer", "BEARER", "BeArEr"])
    def test_scheme_is_case_insensitive(self, scheme):
        assert token_is_valid(f"{scheme} abc123", "abc123") is True

    def test_extra_whitespace_around_the_token_is_ignored(self):
        assert token_is_valid("Bearer   abc123  ", "abc123") is True

    def test_wrong_token_is_rejected(self):
        assert token_is_valid("Bearer abc123", "different") is False

    def test_token_comparison_is_case_sensitive(self):
        assert token_is_valid("Bearer ABC123", "abc123") is False

    @pytest.mark.parametrize("header", [None, "", "Bearer", "Bearer   "])
    def test_missing_or_empty_header_is_rejected(self, header):
        assert token_is_valid(header, "abc123") is False

    @pytest.mark.parametrize("scheme", ["Token", "Basic", "api-key"])
    def test_wrong_scheme_is_rejected(self, scheme):
        assert token_is_valid(f"{scheme} abc123", "abc123") is False

    @pytest.mark.parametrize("expected", ["", None])
    def test_missing_expected_token_is_rejected(self, expected):
        assert token_is_valid("Bearer abc123", expected) is False

    def test_short_expected_token_is_accepted_when_equal(self):
        # This helper only compares; the >= 32-char minimum is enforced by
        # server.load_config, not here.
        assert token_is_valid("Bearer short", "short") is True


# ---------------------------------------------------------------------------
# to_compact_json
# ---------------------------------------------------------------------------


class TestToCompactJson:
    def test_produces_compact_json(self):
        assert to_compact_json({"a": 1, "b": [1, 2], "c": None}) == '{"a":1,"b":[1,2],"c":null}'

    def test_keeps_non_ascii_characters_literal(self):
        assert to_compact_json({"city": "Tlemcené"}) == '{"city":"Tlemcené"}'

    def test_round_trips_losslessly(self):
        payload = {"description": "café ☕" * 10, "n": [1, "x", True]}
        assert json.loads(to_compact_json(payload)) == payload

    def test_output_has_no_separator_whitespace(self):
        assert " " not in to_compact_json({"a": 1, "b": 2})


# ---------------------------------------------------------------------------
# RateLimiter
# ---------------------------------------------------------------------------


class TestRateLimiter:
    def test_allows_up_to_the_limit_and_blocks_the_next(self):
        limiter = RateLimiter(limit=3, window_seconds=60.0)
        assert [limiter.allow("ip", now=100.0) for _ in range(3)] == [True, True, True]
        assert limiter.allow("ip", now=100.0) is False

    def test_blocked_requests_do_not_extend_the_window(self):
        limiter = RateLimiter(limit=1, window_seconds=10.0)
        assert limiter.allow("ip", now=0.0) is True
        # Blocked attempts at 0/5/9.9 must not be recorded as extra hits.
        assert limiter.allow("ip", now=0.0) is False
        assert limiter.allow("ip", now=5.0) is False
        assert limiter.allow("ip", now=9.9) is False
        # A hit at t expires when now - window >= t (cutoff is inclusive).
        assert limiter.allow("ip", now=10.0) is True

    def test_sliding_window_frees_slots_one_by_one(self):
        limiter = RateLimiter(limit=2, window_seconds=10.0)
        assert limiter.allow("ip", now=0.0) is True
        assert limiter.allow("ip", now=5.0) is True
        assert limiter.allow("ip", now=5.0) is False
        assert limiter.allow("ip", now=10.0) is True  # the t=0 hit expired
        assert limiter.allow("ip", now=10.0) is False  # the t=5 hit still counts
        assert limiter.allow("ip", now=15.0) is True  # the t=5 hit expired

    def test_keys_are_isolated(self):
        limiter = RateLimiter(limit=1, window_seconds=60.0)
        assert limiter.allow("a", now=0.0) is True
        assert limiter.allow("a", now=0.0) is False
        assert limiter.allow("b", now=0.0) is True
        assert limiter.allow("b", now=0.0) is False

    def test_default_clock_is_used_when_now_is_omitted(self):
        limiter = RateLimiter(limit=2, window_seconds=60.0)
        assert limiter.allow("ip") is True
        assert limiter.allow("ip") is True
        assert limiter.allow("ip") is False

    def test_defaults_match_the_documented_60_per_minute(self):
        limiter = RateLimiter()
        assert limiter.limit == 60
        assert limiter.window_seconds == 60.0
        assert all(limiter.allow("ip", now=0.0) for _ in range(60))
        assert limiter.allow("ip", now=0.0) is False

    def test_non_positive_limit_or_window_are_rejected(self):
        with pytest.raises(ValueError):
            RateLimiter(limit=0)
        with pytest.raises(ValueError):
            RateLimiter(limit=-1)
        with pytest.raises(ValueError):
            RateLimiter(window_seconds=0)
        with pytest.raises(ValueError):
            RateLimiter(limit=1, window_seconds=-0.1)
