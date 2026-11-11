"""Tests for updater version parsing and comparison."""

from __future__ import annotations

import pytest

from desktop.updater.versioning import (
    compare_versions,
    format_version,
    is_newer,
    parse_tag,
    parse_version,
)


@pytest.mark.parametrize(
    "text,expected",
    [
        ("1.2.3", (1, 2, 3)),
        ("v1.2.3", (1, 2, 3)),
        ("V1.2.3", (1, 2, 3)),
        (" 1.2.3 ", (1, 2, 3)),
        ("01.02.03", (1, 2, 3)),
        ("10.0.0", (10, 0, 0)),
    ],
)
def test_parse_version_valid(text, expected):
    assert parse_version(text) == expected


@pytest.mark.parametrize(
    "text",
    ["", "   ", "v1", "1", "1.2", "1.2.x", "1.2.3.4", "1.2.-3", "a.b.c", "1,2,3", None, 123],
)
def test_parse_version_invalid(text):
    assert parse_version(text) is None


@pytest.mark.parametrize("text", ["1.2.3", "1.2", "", None])
def test_parse_tag_requires_v_prefix(text):
    assert parse_tag(text) is None


@pytest.mark.parametrize("tag", ["v1.2.3", "V1.2.3", " v2.0.1 "])
def test_parse_tag_valid(tag):
    assert parse_tag(tag) is not None


def test_parse_tag_delegates_to_parse_version():
    assert parse_tag("v1.10.0") == (1, 10, 0)


def test_format_version():
    assert format_version((1, 2, 3)) == "1.2.3"
    assert format_version([1, 10, 0]) == "1.10.0"
    assert format_version("v1.2.3") == "1.2.3"
    with pytest.raises(ValueError):
        format_version((1, 2))


def test_compare_versions_numeric_not_lexicographic():
    assert compare_versions("1.10.0", "1.9.0") == 1
    assert compare_versions((1, 10, 0), (1, 9, 0)) == 1
    assert compare_versions("1.2.3", "v1.2.3") == 0
    assert compare_versions("1.0.0", "1.0.1") == -1


def test_compare_versions_invalid_raises():
    with pytest.raises(ValueError):
        compare_versions("nope", "1.0.0")


def test_is_newer():
    assert is_newer("1.10.0", "1.9.0") is True
    assert is_newer("1.2.3", "1.2.3") is False
    assert is_newer("1.2.2", "1.2.3") is False
    assert is_newer("garbage", "1.0.0") is False
    assert is_newer("1.0.1", None) is True
    assert is_newer(None, "1.0.0") is False
