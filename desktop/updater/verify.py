"""Checksum and installer-file verification helpers."""

from __future__ import annotations

import hashlib
import hmac
import os
import re

__all__ = [
    "constant_time_equal",
    "has_pe_header",
    "parse_checksums",
    "sha256_file",
    "verify_checksum",
]

_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_READ_SIZE = 1024 * 1024


def sha256_file(path) -> str:
    """Return the lowercase hex SHA-256 of ``path`` (streamed, no full read)."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            chunk = handle.read(_READ_SIZE)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def parse_checksums(text: str) -> dict[str, str]:
    """Parse ``sha256sum``-style output into ``{lowercase name: lowercase hash}``.

    Accepts ``<hash>  <file>``, ``<hash> *<file>`` and whitespace-separated
    lines.  Blank lines, comments and malformed entries are ignored.
    """
    result: dict[str, str] = {}
    if not isinstance(text, str):
        return result
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        parts = stripped.split(None, 1)
        if len(parts) != 2:
            continue
        digest, name = parts[0].strip().lower(), parts[1].strip()
        if not _HEX64.fullmatch(digest):
            continue
        if name.startswith("*"):
            name = name[1:].strip()
        if not name:
            continue
        result[name.lower()] = digest
    return result


def has_pe_header(path) -> bool:
    """True when the file starts with ``MZ`` and is at least 64 bytes long."""
    try:
        if os.path.getsize(path) < 64:
            return False
        with open(path, "rb") as handle:
            header = handle.read(2)
    except OSError:
        return False
    return header == b"MZ"


def constant_time_equal(a: str, b: str) -> bool:
    """Timing-safe comparison of two strings (typically hex digests)."""
    try:
        return hmac.compare_digest(str(a).lower(), str(b).lower())
    except (TypeError, ValueError):
        return False


def verify_checksum(path, expected_hex: str) -> bool:
    """True when the file's SHA-256 matches ``expected_hex``."""
    expected = (expected_hex or "").strip().lower()
    if not _HEX64.fullmatch(expected):
        return False
    try:
        actual = sha256_file(path)
    except OSError:
        return False
    return constant_time_equal(actual, expected)
