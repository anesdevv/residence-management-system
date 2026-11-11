"""Tiny HTTP layer used by the updater (stdlib only, bundled TLS trust)."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import logging
import ssl
from typing import Iterator
import urllib.error
import urllib.parse
import urllib.request

from . import config
from .release import ReleaseError

__all__ = [
    "HttpResponse",
    "HttpResponseStream",
    "SafeRedirectHandler",
    "http_get",
    "open_stream",
    "urllib_get",
    "validate_download_url",
]

_log = logging.getLogger("resivo.updater")

try:  # pragma: no cover - import path differs between frozen and source runs
    from desktop.app.tls import create_ssl_context
except Exception:  # pragma: no cover
    try:
        from app.tls import create_ssl_context  # type: ignore[no-redef]
    except Exception:  # pragma: no cover
        create_ssl_context = None  # type: ignore[assignment]


@dataclass(frozen=True)
class HttpResponse:
    status: int
    headers: dict[str, str]
    body: bytes

    def header(self, name: str, default: str = "") -> str:
        """Case-insensitive header lookup."""
        wanted = name.lower()
        for key, value in self.headers.items():
            if str(key).lower() == wanted:
                return str(value)
        return default


def _ssl_context() -> ssl.SSLContext | None:
    if create_ssl_context is None:  # pragma: no cover - defensive
        return None
    try:
        return create_ssl_context()
    except Exception:  # pragma: no cover - certifi missing/corrupt
        try:
            return ssl.create_default_context()
        except Exception:
            return None


def _host_allowed(url: str, allowed_hosts: frozenset[str] | set[str]) -> bool:
    try:
        parts = urllib.parse.urlsplit(url)
    except ValueError:
        return False
    if parts.scheme.lower() != "https":
        return False
    if parts.username or parts.password:
        return False
    host = (parts.hostname or "").lower()
    return bool(host) and host in allowed_hosts


def validate_download_url(url: str) -> None:
    """Raise :class:`ReleaseError` unless ``url`` is an allowed HTTPS target."""
    if not isinstance(url, str) or not url:
        raise ReleaseError("bad_host", "missing download URL")
    if not _host_allowed(url, config.ALLOWED_DOWNLOAD_HOSTS):
        raise ReleaseError("bad_host", "download host is not allowed")


class SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Redirect handler that re-validates every redirect target."""

    def __init__(self, allowed_hosts=None) -> None:
        super().__init__()
        self._allowed = frozenset(allowed_hosts or config.ALLOWED_DOWNLOAD_HOSTS)

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not _host_allowed(newurl, self._allowed):
            raise ReleaseError("bad_host", "redirect target host is not allowed")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _build_opener() -> urllib.request.OpenerDirector:
    handlers: list[urllib.request.BaseHandler] = [SafeRedirectHandler()]
    context = _ssl_context()
    if context is not None:
        handlers.append(urllib.request.HTTPSHandler(context=context))
    return urllib.request.build_opener(*handlers)


def urllib_get(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    timeout: float = 10.0,
) -> HttpResponse:
    """Perform a GET and return the complete response.

    HTTP error statuses are returned as :class:`HttpResponse` values instead of
    raising, so callers can handle 304/403/404 explicitly.  Network failures
    propagate as :class:`OSError` subclasses.  Redirects are followed only to
    HTTPS hosts in :data:`config.ALLOWED_DOWNLOAD_HOSTS`.
    """
    request = urllib.request.Request(url, headers=dict(headers or {}), method="GET")
    opener = _build_opener()
    try:
        with opener.open(request, timeout=timeout) as response:
            raw = response.read()
            response_headers = dict(response.headers.items())
            status = getattr(response, "status", None) or response.getcode()
            return HttpResponse(int(status), response_headers, raw)
    except urllib.error.HTTPError as exc:
        try:
            raw = exc.read()
        except Exception:  # pragma: no cover - defensive
            raw = b""
        exc_headers = dict(exc.headers.items()) if exc.headers is not None else {}
        return HttpResponse(int(exc.code), exc_headers, raw)


http_get = urllib_get


class HttpResponseStream:
    """A response whose body is read on demand (never buffered whole)."""

    def __init__(self, status: int, headers: dict[str, str], raw) -> None:
        self.status = int(status)
        self.headers = dict(headers or {})
        self._raw = raw

    def header(self, name: str, default: str = "") -> str:
        wanted = name.lower()
        for key, value in self.headers.items():
            if str(key).lower() == wanted:
                return str(value)
        return default

    def read(self, size: int = -1) -> bytes:
        data = self._raw.read(size)
        return bytes(data or b"")

    def chunks(self, size: int) -> Iterator[bytes]:
        while True:
            chunk = self.read(size)
            if not chunk:
                return
            yield chunk


@contextmanager
def open_stream(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    timeout: float = 30.0,
):
    """Open ``url`` and yield an :class:`HttpResponseStream`.

    Redirect targets are validated by :class:`SafeRedirectHandler`; the TLS
    context comes from the bundled certifi bundle.  HTTP error statuses are
    yielded (not raised) so the caller can report them.
    """
    request = urllib.request.Request(url, headers=dict(headers or {}), method="GET")
    opener = _build_opener()
    try:
        response = opener.open(request, timeout=timeout)
    except urllib.error.HTTPError as exc:  # 4xx/5xx are still readable streams
        try:
            yield HttpResponseStream(
                int(exc.code),
                dict(exc.headers.items()) if exc.headers is not None else {},
                exc,
            )
        finally:
            try:
                exc.close()
            except Exception:  # pragma: no cover - defensive
                pass
        return

    try:
        status = int(getattr(response, "status", None) or response.getcode())
        yield HttpResponseStream(status, dict(response.headers.items()), response)
    finally:
        try:
            response.close()
        except Exception:  # pragma: no cover - defensive
            pass
