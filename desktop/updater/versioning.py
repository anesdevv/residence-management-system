"""Version parsing and comparison helpers (pure, no I/O).

Release convention: tags look like ``v1.2.3``.  A version is always exactly
three numeric components, so ``1.2``, ``1.2.3.4``, ``v1`` and ``1.2.x`` are
invalid.  A single leading ``v``/``V`` is tolerated by :func:`parse_version`
because it is convenient when a version string is reused as a tag; the release
parser uses :func:`parse_tag`, which *requires* the leading ``v``.
"""

from __future__ import annotations

import re
from typing import Sequence

__all__ = [
    "compare_versions",
    "format_version",
    "is_newer",
    "parse_tag",
    "parse_version",
]

_VERSION_RE = re.compile(r"^[vV]?(\d+)\.(\d+)\.(\d+)$")

VersionTuple = tuple[int, int, int]


def parse_version(text: str) -> VersionTuple | None:
    """Parse ``1.2.3`` (optionally prefixed with ``v``/``V``).

    Returns ``None`` for empty input, wrong component counts, non-numeric
    components, or anything that is not a string.
    """
    if not isinstance(text, str):
        return None
    value = text.strip()
    if not value:
        return None
    match = _VERSION_RE.fullmatch(value)
    if match is None:
        return None
    try:
        major, minor, patch = (int(part) for part in match.groups())
    except (ValueError, OverflowError):
        # Extremely long numeric components exceed CPython's int conversion
        # limit; treat those as invalid instead of crashing.
        return None
    return (major, minor, patch)


def parse_tag(tag: str) -> VersionTuple | None:
    """Parse a release tag such as ``v1.2.3``; the leading ``v`` is required."""
    if not isinstance(tag, str):
        return None
    value = tag.strip()
    if len(value) < 2 or value[0] not in "vV":
        return None
    return parse_version(value[1:])


def format_version(value: VersionTuple | Sequence[int] | str) -> str:
    """Format a version tuple (or version string) as ``major.minor.patch``."""
    if isinstance(value, str):
        parsed = parse_version(value)
        return ".".join(str(part) for part in parsed) if parsed else value.strip()
    parts = tuple(value)
    if len(parts) != 3:
        raise ValueError("version must have exactly three components")
    try:
        return ".".join(str(int(part)) for part in parts)
    except (TypeError, ValueError) as exc:
        raise ValueError("version components must be numeric") from exc


def _coerce(value: VersionTuple | Sequence[int] | str | None) -> VersionTuple | None:
    if value is None:
        return None
    if isinstance(value, str):
        return parse_version(value)
    try:
        parts = tuple(int(part) for part in value)
    except (TypeError, ValueError):
        return None
    return parts if len(parts) == 3 else None


def compare_versions(
    a: VersionTuple | Sequence[int] | str,
    b: VersionTuple | Sequence[int] | str,
) -> int:
    """Return ``-1``, ``0`` or ``1`` comparing ``a`` to ``b`` numerically."""
    left = _coerce(a)
    right = _coerce(b)
    if left is None or right is None:
        raise ValueError("invalid version")
    return (left > right) - (left < right)


def is_newer(
    candidate: VersionTuple | Sequence[int] | str | None,
    current: VersionTuple | Sequence[int] | str | None,
) -> bool:
    """True when ``candidate`` is strictly newer than ``current``.

    An unparseable candidate is never newer; an unparseable current version is
    treated as older (so a valid candidate is offered).
    """
    candidate_tuple = _coerce(candidate)
    if candidate_tuple is None:
        return False
    current_tuple = _coerce(current)
    if current_tuple is None:
        return True
    return candidate_tuple > current_tuple
