"""Single source of truth for the RÉSIVO desktop version.

Every other place that needs the version (Settings, PyInstaller version-info,
Inno Setup define, installer file name, ``--selftest``) reads it from here.
Never hard-code the version anywhere else.
"""

from __future__ import annotations

__version__ = "0.1.2"

# The version as an integer tuple, for the Windows version resource.
VERSION_INFO = tuple(int(part) for part in __version__.split("."))

__all__ = ["__version__", "VERSION_INFO"]
