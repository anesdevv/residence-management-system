"""Tests for the update checker (fake HTTP, no real network)."""

from __future__ import annotations

import json
import logging
import time
import urllib.error

import pytest

from desktop.updater import config
from desktop.updater.checker import (
    CheckResult,
    ETagCache,
    check_for_update,
    default_cache_path,
)
from desktop.updater.http import HttpResponse

REPO_URL = "https://github.com/anesdevv/residence-management-system/releases/download"


def make_asset(name, *, size=1024):
    return {
        "name": name,
        "size": size,
        "state": "uploaded",
        "browser_download_url": f"{REPO_URL}/v1.2.0/{name}",
    }


def make_payload(version="1.2.0"):
    tag = f"v{version}"
    return {
        "tag_name": tag,
        "name": f"RESIVO {version}",
        "body": "notes",
        "draft": False,
        "prerelease": False,
        "published_at": "2026-01-02T03:04:05Z",
        "html_url": "https://github.com/anesdevv/residence-management-system/releases/tag/"
        + tag,
        "assets": [
            make_asset(f"Setup-RESIVO-{version}.exe"),
            make_asset(config.CHECKSUM_ASSET_NAME, size=120),
        ],
    }


def json_response(payload, *, status=200, headers=None):
    body = payload if isinstance(payload, bytes) else json.dumps(payload).encode("utf-8")
    return HttpResponse(status, dict(headers or {}), body)


class FakeHttp:
    def __init__(self, response=None, exc=None):
        self.response = response
        self.exc = exc
        self.calls = []

    def __call__(self, url, *, headers=None, timeout=None):
        self.calls.append(
            {"url": url, "headers": dict(headers or {}), "timeout": timeout}
        )
        if self.exc is not None:
            raise self.exc
        return self.response


def test_available_release_and_cache_saved(tmp_path):
    fake = FakeHttp(json_response(make_payload("1.2.0"), headers={"ETag": 'W/"abc"'}))
    cache_path = tmp_path / "check_cache.json"
    result = check_for_update("1.0.0", cache_path, http=fake)

    assert isinstance(result, CheckResult)
    assert result.kind == "available"
    assert result.release is not None
    assert result.release.version_str == "1.2.0"
    assert result.etag == 'W/"abc"'
    assert result.checked_at > 0

    call = fake.calls[0]
    assert call["url"] == config.GITHUB_API_URL
    assert call["timeout"] == config.API_TIMEOUT_S
    assert call["headers"]["Accept"] == config.ACCEPT_HEADER
    assert call["headers"]["User-Agent"] == config.USER_AGENT
    assert call["headers"]["X-GitHub-Api-Version"] == config.API_VERSION_HEADER
    assert "If-None-Match" not in call["headers"]

    cached = ETagCache(cache_path).load()
    assert cached["etag"] == 'W/"abc"'
    assert cached["payload"]["tag_name"] == "v1.2.0"


def test_up_to_date_logs_event(tmp_path, caplog):
    fake = FakeHttp(json_response(make_payload("1.0.0")))
    with caplog.at_level(logging.INFO, logger="resivo.updater"):
        result = check_for_update("1.0.0", tmp_path / "cache.json", http=fake)
    assert result.kind == "up_to_date"
    assert result.release is None
    assert any("update check: up to date" in rec.message for rec in caplog.records)


def test_available_logs_event(tmp_path, caplog):
    fake = FakeHttp(json_response(make_payload("1.2.0")))
    with caplog.at_level(logging.INFO, logger="resivo.updater"):
        result = check_for_update("1.0.0", tmp_path / "cache.json", http=fake)
    assert result.kind == "available"
    assert any("update available v1.2.0" in rec.message for rec in caplog.records)


def test_304_uses_cached_payload(tmp_path):
    cache_path = tmp_path / "cache.json"
    ETagCache(cache_path).save('"etag-1"', make_payload("1.2.0"))
    fake = FakeHttp(HttpResponse(304, {}, b""))

    result = check_for_update("1.0.0", cache_path, http=fake)

    assert result.kind == "available"
    assert result.release is not None
    assert result.etag == '"etag-1"'
    assert fake.calls[0]["headers"]["If-None-Match"] == '"etag-1"'


def test_304_cached_up_to_date(tmp_path):
    cache_path = tmp_path / "cache.json"
    ETagCache(cache_path).save('"etag-1"', make_payload("1.0.0"))
    result = check_for_update("1.0.0", cache_path, http=FakeHttp(HttpResponse(304, {}, b"")))
    assert result.kind == "up_to_date"


def test_304_without_cache_is_error(tmp_path):
    result = check_for_update(
        "1.0.0", tmp_path / "cache.json", http=FakeHttp(HttpResponse(304, {}, b""))
    )
    assert result.kind == "error"
    assert result.code == "no_cached_payload"


def test_404_means_no_releases(tmp_path, caplog):
    with caplog.at_level(logging.INFO, logger="resivo.updater"):
        result = check_for_update(
            "1.0.0", tmp_path / "cache.json", http=FakeHttp(HttpResponse(404, {}, b"{}"))
        )
    assert result.kind == "no_releases"
    assert result.release is None
    assert any("update check: no releases" in rec.message for rec in caplog.records)


def test_403_rate_limit_uses_reset_epoch(tmp_path, caplog):
    reset = int(time.time()) + 120
    fake = FakeHttp(
        HttpResponse(403, {"X-RateLimit-Reset": str(reset)}, b"{}")
    )
    with caplog.at_level(logging.WARNING, logger="resivo.updater"):
        result = check_for_update("1.0.0", tmp_path / "cache.json", http=fake)
    assert result.kind == "rate_limited"
    assert result.retry_at == pytest.approx(reset)
    assert result.message
    assert any("update check: rate limited" in rec.message for rec in caplog.records)


def test_429_rate_limit_uses_retry_after(tmp_path):
    before = time.time()
    fake = FakeHttp(HttpResponse(429, {"Retry-After": "42"}, b"{}"))
    result = check_for_update("1.0.0", tmp_path / "cache.json", http=fake)
    assert result.kind == "rate_limited"
    assert result.retry_at is not None
    assert before + 40 <= result.retry_at <= before + 45


@pytest.mark.parametrize(
    "exc", [TimeoutError("timed out"), urllib.error.URLError("no route"), OSError("boom")]
)
def test_network_failures_are_offline(tmp_path, exc, caplog):
    with caplog.at_level(logging.WARNING, logger="resivo.updater"):
        result = check_for_update(
            "1.0.0", tmp_path / "cache.json", http=FakeHttp(exc=exc)
        )
    assert result.kind == "offline"
    assert result.release is None
    assert any("update check: offline" in rec.message for rec in caplog.records)


def test_malformed_json_is_error(tmp_path):
    result = check_for_update(
        "1.0.0", tmp_path / "cache.json", http=FakeHttp(json_response(b"{"))
    )
    assert result.kind == "error"
    assert result.code == "invalid_response"
    assert "traceback" not in result.message.lower()


def test_missing_assets_is_error(tmp_path, caplog):
    payload = make_payload("1.2.0")
    payload["assets"] = payload["assets"][:1]
    with caplog.at_level(logging.WARNING, logger="resivo.updater"):
        result = check_for_update(
            "1.0.0", tmp_path / "cache.json", http=FakeHttp(json_response(payload))
        )
    assert result.kind == "error"
    assert result.code == "missing_assets"
    assert result.message
    assert any("update failed: missing_assets" in rec.message for rec in caplog.records)


def test_unexpected_status_is_error(tmp_path):
    result = check_for_update(
        "1.0.0", tmp_path / "cache.json", http=FakeHttp(HttpResponse(500, {}, b""))
    )
    assert result.kind == "error"
    assert result.code == "http_500"


def test_default_cache_path_uses_updates_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("RESIVO_UPDATES_DIR", str(tmp_path / "updates"))
    assert default_cache_path() == tmp_path / "updates" / "check_cache.json"


def test_etag_cache_tolerates_corrupt_file(tmp_path):
    path = tmp_path / "cache.json"
    path.write_text("not json", encoding="utf-8")
    cache = ETagCache(path)
    assert cache.load() == {}

    path.write_text(json.dumps({"etag": 5, "payload": []}), encoding="utf-8")
    assert cache.load() == {}

    cache.save('"e"', {"tag_name": "v1.2.0"})
    assert cache.load()["etag"] == '"e"'
    cache.clear()
    assert not path.exists()
    cache.clear()  # idempotent
