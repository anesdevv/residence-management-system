"""TLS certificate bundle, proxy detection, and clock-skew error helpers."""

from __future__ import annotations

import inspect
import logging
import os
import ssl
import sys
import urllib.request
from pathlib import Path
from typing import Any

import certifi

_log = logging.getLogger("resivo.tls")


def ca_bundle_path() -> Path | None:
    """Return the path to the bundled CA certificate file (``cacert.pem``).

    Frozen builds check next to the executable and inside ``_MEIPASS`` first,
    then fall back to ``certifi.where()``.
    """
    candidates: list[Path] = []
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        candidates.append(exe_dir / "certifi" / "cacert.pem")
        candidates.append(exe_dir / "cacert.pem")
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            mp = Path(meipass)
            candidates.append(mp / "certifi" / "cacert.pem")
            candidates.append(mp / "cacert.pem")

    try:
        where = Path(certifi.where())
        candidates.append(where)
    except Exception:  # pragma: no cover - defensive fallback
        pass

    for candidate in candidates:
        try:
            if candidate.is_file():
                return candidate
        except OSError:
            continue
    return None


def configure_tls_environment() -> Path | None:
    """Point standard TLS env vars at the bundled ``certifi`` CA bundle."""
    bundle = ca_bundle_path()
    if bundle is None:
        _log.warning("Could not locate certifi CA bundle; using OS certificate store.")
        return None

    bundle_str = str(bundle)
    os.environ.setdefault("SSL_CERT_FILE", bundle_str)
    os.environ.setdefault("REQUESTS_CA_BUNDLE", bundle_str)
    os.environ.setdefault("WEBSOCKETS_CA_CERTS", bundle_str)
    return bundle


def create_ssl_context() -> ssl.SSLContext:
    """Create a verified TLS ``SSLContext`` backed by the bundled CA file."""
    bundle = ca_bundle_path()
    if bundle is not None:
        return ssl.create_default_context(cafile=str(bundle))
    return ssl.create_default_context()


def urlopen_with_tls(url_or_req: Any, *, timeout: float) -> Any:
    """Call ``urllib.request.urlopen`` with the bundled CA context when supported.

    Preserves compatibility with unit tests that monkeypatch ``urlopen`` with a
    two-argument lambda ``(req, timeout=...)`` without a ``context`` parameter.
    """
    urlopen_fn = urllib.request.urlopen
    try:
        params = inspect.signature(urlopen_fn).parameters
        accepts_context = "context" in params or any(
            p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values()
        )
    except (TypeError, ValueError):
        accepts_context = False

    if accepts_context:
        return urlopen_fn(url_or_req, timeout=timeout, context=create_ssl_context())
    return urlopen_fn(url_or_req, timeout=timeout)


def system_proxy_summary() -> dict[str, str]:
    """Return configured HTTP/HTTPS system proxies without credential details."""
    try:
        raw = urllib.request.getproxies() or {}
    except Exception:
        return {}
    clean: dict[str, str] = {}
    for k, v in raw.items():
        if not v:
            continue
        text = str(v)
        # Strip embedded user:pass@ from proxy URLs if present before logging/UI.
        if "@" in text and "://" in text:
            scheme, rest = text.split("://", 1)
            text = f"{scheme}://{rest.split('@', 1)[1]}"
        clean[str(k)] = text
    return clean


def classify_tls_error(exc: BaseException | None) -> tuple[bool, bool]:
    """Inspect exception chain and return ``(is_tls_error, is_clock_skew_likely)``."""
    seen: set[int] = set()
    curr: BaseException | None = exc
    while curr is not None and id(curr) not in seen:
        seen.add(id(curr))
        msg = str(curr).lower()
        is_ssl = isinstance(curr, ssl.SSLError) or (
            "certificate" in msg
            or "ssl" in msg
            or "tls" in msg
        )
        if is_ssl and (
            "certificate verify failed" in msg
            or "not yet valid" in msg
            or "has expired" in msg
            or "self signed" in msg
            or "self-signed" in msg
            or "unable to get local issuer certificate" in msg
            or isinstance(curr, ssl.SSLCertVerificationError)
        ):
            clock_likely = (
                "not yet valid" in msg
                or "has expired" in msg
                or "certificate has expired" in msg
            )
            return True, clock_likely
        curr = (
            getattr(curr, "__cause__", None)
            or getattr(curr, "__context__", None)
            or (
                getattr(curr, "reason", None)
                if isinstance(getattr(curr, "reason", None), BaseException)
                else None
            )
        )
    return False, False
