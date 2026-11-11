"""Tests for GitHub release payload parsing."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from desktop.updater import config
from desktop.updater.release import (
    ReleaseError,
    ReleaseInfo,
    parse_published_at,
    parse_release,
)

CURRENT = "1.0.0"
REPO_URL = "https://github.com/anesdevv/residence-management-system/releases/download"


def make_asset(name, *, size=1024, url=None, state="uploaded"):
    return {
        "name": name,
        "size": size,
        "state": state,
        "browser_download_url": (
            f"{REPO_URL}/v1.2.0/{name}" if url is None else url
        ),
    }


def make_payload(
    version="1.2.0",
    *,
    installer_name=None,
    installer_size=1024,
    checksum_size=120,
    include_installer=True,
    include_checksum=True,
    installer_url=None,
    checksum_url=None,
    **overrides,
):
    tag = f"v{version}"
    installer_name = installer_name or f"Setup-RESIVO-{version}.exe"
    assets = []
    if include_installer:
        assets.append(
            make_asset(installer_name, size=installer_size, url=installer_url)
        )
    if include_checksum:
        assets.append(
            make_asset(
                config.CHECKSUM_ASSET_NAME,
                size=checksum_size,
                url=checksum_url,
            )
        )
    payload = {
        "tag_name": tag,
        "name": f"RESIVO {version}",
        "body": "Release notes",
        "draft": False,
        "prerelease": False,
        "published_at": "2026-01-02T03:04:05Z",
        "html_url": f"https://github.com/anesdevv/residence-management-system/releases/tag/{tag}",
        "assets": assets,
    }
    payload.update(overrides)
    return payload


def test_parses_newer_release():
    info = parse_release(make_payload(), CURRENT)
    assert isinstance(info, ReleaseInfo)
    assert info.version == (1, 2, 0)
    assert info.version_str == "1.2.0"
    assert info.tag == "v1.2.0"
    assert info.installer_name == "Setup-RESIVO-1.2.0.exe"
    assert info.installer_size == 1024
    assert info.notes == "Release notes"
    assert info.published_dt == datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
    assert info.published_dt.tzinfo is not None


def test_1_10_0_is_offered_against_1_9_0():
    info = parse_release(make_payload("1.10.0"), "1.9.0")
    assert info is not None
    assert info.version == (1, 10, 0)


@pytest.mark.parametrize("version", ["1.0.0", "0.9.9"])
def test_equal_or_older_release_ignored(version):
    assert parse_release(make_payload(version), CURRENT) is None


@pytest.mark.parametrize("flag", ["draft", "prerelease"])
def test_draft_and_prerelease_ignored(flag):
    payload = make_payload()
    payload[flag] = True
    assert parse_release(payload, CURRENT) is None


@pytest.mark.parametrize("tag", ["", "v1", "1.2.3", "1.2.x", "v1.2", "v1.2.3.4"])
def test_bad_tags_ignored(tag):
    payload = make_payload()
    payload["tag_name"] = tag
    assert parse_release(payload, CURRENT) is None


def test_missing_tag_ignored():
    payload = make_payload()
    payload.pop("tag_name")
    assert parse_release(payload, CURRENT) is None


def test_missing_installer_asset():
    payload = make_payload(include_installer=False)
    with pytest.raises(ReleaseError) as excinfo:
        parse_release(payload, CURRENT)
    assert excinfo.value.code == "missing_assets"


def test_missing_checksum_asset():
    payload = make_payload(include_checksum=False)
    with pytest.raises(ReleaseError) as excinfo:
        parse_release(payload, CURRENT)
    assert excinfo.value.code == "missing_assets"


@pytest.mark.parametrize(
    "name",
    ["Setup-RESIVO.exe", "RESIVO-Setup-1.2.0.exe", "Setup-RESIVO-1.2.0.msi"],
)
def test_wrong_installer_asset_name(name):
    payload = make_payload(installer_name=name)
    with pytest.raises(ReleaseError) as excinfo:
        parse_release(payload, CURRENT)
    assert excinfo.value.code == "bad_asset_name"


def test_installer_name_version_must_match_tag():
    payload = make_payload(installer_name="Setup-RESIVO-1.2.1.exe")
    with pytest.raises(ReleaseError) as excinfo:
        parse_release(payload, CURRENT)
    assert excinfo.value.code == "bad_asset_name"


def test_installer_not_uploaded_is_missing():
    payload = make_payload()
    payload["assets"][0]["state"] = "new"
    with pytest.raises(ReleaseError) as excinfo:
        parse_release(payload, CURRENT)
    assert excinfo.value.code == "missing_assets"


def test_installer_size_limit():
    payload = make_payload(installer_size=config.MAX_DOWNLOAD_BYTES + 1)
    with pytest.raises(ReleaseError) as excinfo:
        parse_release(payload, CURRENT)
    assert excinfo.value.code == "size_limit"


def test_checksum_size_limit():
    payload = make_payload(checksum_size=config.MAX_CHECKSUM_BYTES + 1)
    with pytest.raises(ReleaseError) as excinfo:
        parse_release(payload, CURRENT)
    assert excinfo.value.code == "size_limit"


@pytest.mark.parametrize(
    "url",
    ["http://github.com/a/Setup.exe", "https://evil.example/Setup.exe", ""],
)
def test_installer_url_must_be_allowlisted_https(url):
    payload = make_payload(installer_url=url)
    with pytest.raises(ReleaseError) as excinfo:
        parse_release(payload, CURRENT)
    assert excinfo.value.code == "bad_host"


@pytest.mark.parametrize(
    "payload",
    [
        None,
        [],
        "nope",
        {"tag_name": 12, "assets": []},
        {"tag_name": "v1.2.0", "assets": "nope"},
        {"tag_name": "v1.2.0", "assets": [42]},
        {"tag_name": "v1.2.0", "assets": [{"name": 3}]},
    ],
)
def test_malformed_payload_raises_code_not_typeerror(payload):
    with pytest.raises(ReleaseError) as excinfo:
        parse_release(payload, CURRENT)
    assert excinfo.value.code == "malformed"


def test_malformed_asset_size():
    payload = make_payload()
    payload["assets"][0]["size"] = "1024"
    with pytest.raises(ReleaseError) as excinfo:
        parse_release(payload, CURRENT)
    assert excinfo.value.code == "malformed"


def test_malformed_draft_flag():
    payload = make_payload()
    payload["draft"] = "false"
    with pytest.raises(ReleaseError) as excinfo:
        parse_release(payload, CURRENT)
    assert excinfo.value.code == "malformed"


def test_malformed_assets_none_is_treated_as_empty():
    payload = make_payload()
    payload["assets"] = None
    with pytest.raises(ReleaseError) as excinfo:
        parse_release(payload, CURRENT)
    assert excinfo.value.code == "missing_assets"


@pytest.mark.parametrize(
    "text,expected",
    [
        ("2026-01-02T03:04:05Z", datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)),
        (
            "2026-01-02T05:04:05+02:00",
            datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc),
        ),
        ("2026-01-02T03:04:05", datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)),
    ],
)
def test_parse_published_at_iso(text, expected):
    assert parse_published_at(text) == expected


@pytest.mark.parametrize("text", [None, "", "   ", "not-a-date", 12345])
def test_parse_published_at_invalid(text):
    assert parse_published_at(text) is None
