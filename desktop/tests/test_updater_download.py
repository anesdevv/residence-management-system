"""Tests for installer download/verification and checksum helpers."""

from __future__ import annotations

import hashlib
from pathlib import Path
import urllib.request

import pytest

from desktop.updater import config
from desktop.updater.downloader import (
    DownloadCancelled,
    UpdateError,
    clean_updates_dir,
    download_installer,
    fetch_checksums,
)
from desktop.updater.http import HttpResponse, SafeRedirectHandler, validate_download_url
from desktop.updater.release import ReleaseError, ReleaseInfo
from desktop.updater.verify import (
    constant_time_equal,
    has_pe_header,
    parse_checksums,
    sha256_file,
    verify_checksum,
)

INSTALLER_NAME = "Setup-RESIVO-1.2.0.exe"
INSTALLER_URL = (
    "https://github.com/anesdevv/residence-management-system/releases/download/"
    f"v1.2.0/{INSTALLER_NAME}"
)
CHECKSUM_URL = (
    "https://github.com/anesdevv/residence-management-system/releases/download/"
    "v1.2.0/SHA256SUMS.txt"
)


def pe_body(size: int = config.CHUNK_SIZE * 3 + 17) -> bytes:
    return b"MZ" + b"\x00" * (size - 2)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def make_release(
    data: bytes,
    *,
    checksum_text: str | None = None,
    installer_size: int | None = None,
    installer_name: str = INSTALLER_NAME,
    installer_url: str = INSTALLER_URL,
    checksum_url: str = CHECKSUM_URL,
) -> ReleaseInfo:
    text = checksum_text if checksum_text is not None else f"{sha(data)}  {installer_name}\n"
    return ReleaseInfo(
        version=(1, 2, 0),
        version_str="1.2.0",
        tag="v1.2.0",
        name="RESIVO 1.2.0",
        notes="",
        published_at=None,
        published_dt=None,
        installer_name=installer_name,
        installer_url=installer_url,
        installer_size=len(data) if installer_size is None else installer_size,
        checksum_url=checksum_url,
        checksum_size=len(text.encode("utf-8")),
        html_url="",
    )


class RoutedHttp:
    def __init__(
        self,
        installer_body: bytes,
        checksum_text: str,
        *,
        checksum_headers=None,
        installer_headers=None,
        omit_installer_length: bool = False,
    ):
        self.installer_body = installer_body
        self.checksum_body = checksum_text.encode("utf-8")
        self.checksum_headers = dict(checksum_headers or {})
        self.installer_headers = dict(installer_headers or {})
        if not omit_installer_length and "Content-Length" not in self.installer_headers:
            self.installer_headers["Content-Length"] = str(len(installer_body))
        self.urls: list[str] = []

    def __call__(self, url, *, headers=None, timeout=None):
        self.urls.append(url)
        if url == CHECKSUM_URL:
            return HttpResponse(200, self.checksum_headers, self.checksum_body)
        return HttpResponse(200, self.installer_headers, self.installer_body)


def leftovers(directory: Path) -> list[str]:
    return sorted(path.name for path in directory.iterdir())


def test_successful_download_verifies_and_replaces(tmp_path):
    data = pe_body()
    fake = RoutedHttp(data, f"{sha(data)}  {INSTALLER_NAME}\n")
    events: list[tuple[int, int]] = []

    result = download_installer(
        make_release(data),
        dest_dir=tmp_path,
        progress=lambda done, total: events.append((done, total)),
        http=fake,
    )

    assert result == tmp_path / INSTALLER_NAME
    assert result.read_bytes() == data
    assert leftovers(tmp_path) == [INSTALLER_NAME]
    total = len(data)
    assert events[0] == (0, total)
    assert events[-1] == (total, total)
    assert all(a[0] <= b[0] for a, b in zip(events, events[1:]))
    assert fake.urls[0] == CHECKSUM_URL
    assert fake.urls[1] == INSTALLER_URL


def test_checksum_mismatch_deletes_temp(tmp_path):
    data = pe_body(2048)
    fake = RoutedHttp(data, f"{'0' * 64}  {INSTALLER_NAME}\n")
    with pytest.raises(UpdateError) as excinfo:
        download_installer(make_release(data), dest_dir=tmp_path, http=fake)
    assert excinfo.value.code == "checksum_mismatch"
    assert leftovers(tmp_path) == []


def test_content_length_mismatch(tmp_path):
    data = pe_body(2048)
    fake = RoutedHttp(
        data,
        f"{sha(data)}  {INSTALLER_NAME}\n",
        installer_headers={"Content-Length": str(len(data) + 1)},
    )
    with pytest.raises(UpdateError) as excinfo:
        download_installer(make_release(data), dest_dir=tmp_path, http=fake)
    assert excinfo.value.code == "size_mismatch"
    assert leftovers(tmp_path) == []


def test_actual_size_mismatch(tmp_path):
    data = pe_body(2048)
    fake = RoutedHttp(
        data,
        f"{sha(data)}  {INSTALLER_NAME}\n",
        omit_installer_length=True,
    )
    with pytest.raises(UpdateError) as excinfo:
        download_installer(
            make_release(data, installer_size=len(data) + 10),
            dest_dir=tmp_path,
            http=fake,
        )
    assert excinfo.value.code == "size_mismatch"
    assert leftovers(tmp_path) == []


def test_declared_oversize_rejected_before_download(tmp_path):
    fake = RoutedHttp(b"", "")
    with pytest.raises(UpdateError) as excinfo:
        download_installer(
            make_release(b"MZ", installer_size=config.MAX_DOWNLOAD_BYTES + 1),
            dest_dir=tmp_path,
            http=fake,
        )
    assert excinfo.value.code == "oversize"
    assert fake.urls == []
    assert leftovers(tmp_path) == []


def test_oversize_stream_rejected(tmp_path):
    data = pe_body(config.CHUNK_SIZE * 2)
    fake = RoutedHttp(
        data,
        f"{sha(data)}  {INSTALLER_NAME}\n",
        omit_installer_length=True,
    )
    with pytest.raises(UpdateError) as excinfo:
        download_installer(
            make_release(data, installer_size=config.CHUNK_SIZE),
            dest_dir=tmp_path,
            http=fake,
        )
    assert excinfo.value.code == "oversize"
    assert leftovers(tmp_path) == []


def test_cancel_mid_download_removes_part_file(tmp_path):
    data = pe_body(config.CHUNK_SIZE * 3)
    fake = RoutedHttp(data, f"{sha(data)}  {INSTALLER_NAME}\n")
    cancelled = {"value": False}
    events: list[tuple[int, int]] = []

    def progress(done, total):
        events.append((done, total))
        if done > 0:
            cancelled["value"] = True

    with pytest.raises(DownloadCancelled):
        download_installer(
            make_release(data),
            dest_dir=tmp_path,
            progress=progress,
            cancel=lambda: cancelled["value"],
            http=fake,
        )
    assert events[0][0] == 0
    assert leftovers(tmp_path) == []


def test_bad_pe_header_fails(tmp_path):
    data = b"XX" + b"\x00" * 2048
    fake = RoutedHttp(data, f"{sha(data)}  {INSTALLER_NAME}\n")
    with pytest.raises(UpdateError) as excinfo:
        download_installer(make_release(data), dest_dir=tmp_path, http=fake)
    assert excinfo.value.code == "bad_pe"
    assert leftovers(tmp_path) == []


def test_missing_checksum_entry(tmp_path):
    data = pe_body(1024)
    fake = RoutedHttp(data, f"{sha(data)}  Setup-RESIVO-9.9.9.exe\n")
    with pytest.raises(UpdateError) as excinfo:
        download_installer(make_release(data), dest_dir=tmp_path, http=fake)
    assert excinfo.value.code == "missing_checksum"
    assert leftovers(tmp_path) == []


def test_non_https_installer_url_rejected(tmp_path):
    data = pe_body(1024)
    fake = RoutedHttp(data, f"{sha(data)}  {INSTALLER_NAME}\n")
    with pytest.raises(UpdateError) as excinfo:
        download_installer(
            make_release(data, installer_url=f"http://github.com/{INSTALLER_NAME}"),
            dest_dir=tmp_path,
            http=fake,
        )
    assert excinfo.value.code == "bad_host"
    assert fake.urls == []


def test_non_allowlisted_host_rejected(tmp_path):
    data = pe_body(1024)
    fake = RoutedHttp(data, f"{sha(data)}  {INSTALLER_NAME}\n")
    with pytest.raises(UpdateError) as excinfo:
        download_installer(
            make_release(data, installer_url=f"https://evil.example/{INSTALLER_NAME}"),
            dest_dir=tmp_path,
            http=fake,
        )
    assert excinfo.value.code == "bad_host"
    assert fake.urls == []


def test_wrong_installer_name_rejected(tmp_path):
    data = pe_body(1024)
    fake = RoutedHttp(data, f"{sha(data)}  Other.exe\n")
    with pytest.raises(UpdateError) as excinfo:
        download_installer(
            make_release(data, installer_name="Other.exe"),
            dest_dir=tmp_path,
            http=fake,
        )
    assert excinfo.value.code == "bad_asset_name"
    assert fake.urls == []


@pytest.mark.parametrize(
    "url",
    [
        f"https://github.com/{INSTALLER_NAME}",
        "https://github.com:443/asset.exe",
        "https://release-assets.githubusercontent.com/asset.exe",
    ],
)
def test_validate_download_url_allows_trusted(url):
    validate_download_url(url)


@pytest.mark.parametrize(
    "url",
    [
        f"http://github.com/{INSTALLER_NAME}",
        "ftp://github.com/asset.exe",
        "https://evil.example/asset.exe",
        "https://user:pass@github.com/asset.exe",
        "",
        None,
    ],
)
def test_validate_download_url_rejects(url):
    with pytest.raises(ReleaseError) as excinfo:
        validate_download_url(url)
    assert excinfo.value.code == "bad_host"


def test_safe_redirect_handler_blocks_untrusted_host():
    request = urllib.request.Request("https://github.com/start")
    handler = SafeRedirectHandler()
    with pytest.raises(ReleaseError) as excinfo:
        handler.redirect_request(
            request, None, 302, "Found", {}, "https://evil.example/payload.exe"
        )
    assert excinfo.value.code == "bad_host"


def test_safe_redirect_handler_blocks_http_downgrade():
    request = urllib.request.Request("https://github.com/start")
    handler = SafeRedirectHandler()
    with pytest.raises(ReleaseError) as excinfo:
        handler.redirect_request(
            request, None, 302, "Found", {}, "http://github.com/payload.exe"
        )
    assert excinfo.value.code == "bad_host"


def test_safe_redirect_handler_allows_trusted_target():
    request = urllib.request.Request("https://github.com/start")
    handler = SafeRedirectHandler()
    redirected = handler.redirect_request(
        request,
        None,
        302,
        "Found",
        {},
        "https://objects.githubusercontent.com/payload.exe",
    )
    assert redirected is not None


def test_fetch_checksums_parses_common_formats(tmp_path):
    digest_a = "a" * 64
    digest_b = "b" * 64
    body = (
        "# generated\n"
        "\n"
        f"{digest_a}  Setup-RESIVO-1.2.0.exe\n"
        f"{digest_b} *SHA256SUMS.txt\n"
        "not a checksum line\n"
    )
    fake = RoutedHttp(pe_body(), body)
    result = fetch_checksums(CHECKSUM_URL, http=fake)
    assert result["setup-resivo-1.2.0.exe"] == digest_a
    assert result["sha256sums.txt"] == digest_b


def test_fetch_checksums_rejects_oversize_body():
    fake = RoutedHttp(b"MZ", "")
    fake.checksum_body = b"x" * (config.MAX_CHECKSUM_BYTES + 1)
    with pytest.raises(UpdateError) as excinfo:
        fetch_checksums(CHECKSUM_URL, http=fake)
    assert excinfo.value.code == "oversize"


def test_clean_updates_dir_removes_parts_and_stale_installers(tmp_path):
    cache = tmp_path / "check_cache.json"
    cache.write_text("{}", encoding="utf-8")
    part = tmp_path / ".abc.part"
    part.write_bytes(b"x")
    old = tmp_path / "Setup-RESIVO-1.0.0.exe"
    old.write_bytes(b"x")
    keep = tmp_path / INSTALLER_NAME
    keep.write_bytes(b"x")
    other = tmp_path / "notes.txt"
    other.write_text("keep me", encoding="utf-8")

    removed = clean_updates_dir(tmp_path, keep=keep)

    assert removed == 2
    assert not part.exists()
    assert not old.exists()
    assert keep.exists()
    assert cache.exists()
    assert other.exists()


def test_verify_helpers(tmp_path):
    target = tmp_path / "file.bin"
    data = b"hello world"
    target.write_bytes(data)

    assert sha256_file(target) == hashlib.sha256(data).hexdigest()
    assert verify_checksum(target, hashlib.sha256(data).hexdigest()) is True
    assert verify_checksum(target, "0" * 64) is False
    assert verify_checksum(target, "not-a-hash") is False

    assert constant_time_equal("ABC", "abc") is True
    assert constant_time_equal("abc", "abd") is False

    assert parse_checksums("bad line") == {}
    assert parse_checksums("") == {}


def test_has_pe_header(tmp_path):
    good = tmp_path / "good.exe"
    good.write_bytes(b"MZ" + b"\x00" * 100)
    assert has_pe_header(good) is True

    short = tmp_path / "short.exe"
    short.write_bytes(b"MZ")
    assert has_pe_header(short) is False

    wrong = tmp_path / "wrong.exe"
    wrong.write_bytes(b"ZZ" + b"\x00" * 100)
    assert has_pe_header(wrong) is False

    assert has_pe_header(tmp_path / "missing.exe") is False
