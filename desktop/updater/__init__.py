"""In-app updater for the RÉSIVO desktop console.

Public interface lives in :mod:`desktop.updater.service`; the rest of the
package is pure logic that can be tested without Qt or the network.
"""

from __future__ import annotations

from .config import updates_dir
from .state import UpdateState
from .versioning import compare_versions, is_newer, parse_version

__all__ = [
    "UpdateState",
    "compare_versions",
    "is_newer",
    "parse_version",
    "updates_dir",
]
