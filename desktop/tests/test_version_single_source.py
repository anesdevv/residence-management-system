"""desktop/version.py must be the single source of truth for the app version."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SEMVER_RE = re.compile(r"\b\d+\.\d+\.\d+\b")

# Files that used to duplicate the version and must never hard-code it again.
VERSION_FREE_FILES = (
    "desktop/app/config.py",
    "desktop/installer/resivo.iss",
    "desktop/version_info.txt",
    "desktop/resivo.spec",
)


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_version_module_defines_the_semver():
    from desktop import version

    assert re.fullmatch(r"\d+\.\d+\.\d+", version.__version__)
    assert version.VERSION_INFO == tuple(
        int(part) for part in version.__version__.split(".")
    )


def test_config_reexports_the_version_module_value():
    from desktop import version
    from desktop.app import config

    assert config.APP_VERSION == version.__version__


def test_no_hard_coded_semver_outside_version_py():
    offenders = {}
    for relative_path in VERSION_FREE_FILES:
        matches = SEMVER_RE.findall(_read(relative_path))
        if matches:
            offenders[relative_path] = matches
    assert not offenders, f"Hard-coded version(s) found outside desktop/version.py: {offenders}"


def test_no_literal_version_assignments():
    config_text = _read("desktop/app/config.py")
    assert not re.search(r"^[ \t]*APP_VERSION[ \t]*=[ \t]*['\"]", config_text, re.MULTILINE)

    iss_text = _read("desktop/installer/resivo.iss")
    assert "#ifndef MyAppVersion" in iss_text
    assert not re.search(
        r"^[ \t]*#define[ \t]+MyAppVersion[ \t]+['\"]", iss_text, re.MULTILINE
    )
    assert "make_release.ps1" in iss_text


def test_version_info_is_a_placeholder_template():
    text = _read("desktop/version_info.txt")
    for placeholder in ("@MAJOR@", "@MINOR@", "@PATCH@", "@BUILD@"):
        assert placeholder in text, f"Missing {placeholder} in version_info.txt"
    assert not SEMVER_RE.search(text)
    # Existing metadata assertions keep working on the template.
    assert "RÉSIVO" in text
    assert "CompanyName" in text
    assert "ProductName" in text
    assert "FileDescription" in text


def test_spec_renders_the_template_from_version_py():
    spec_text = _read("desktop/resivo.spec")
    assert "version_info.txt" in spec_text
    assert '"version.py"' in spec_text
    assert "__version__" in spec_text
    for placeholder in ("@MAJOR@", "@MINOR@", "@PATCH@", "@BUILD@"):
        assert placeholder in spec_text
    assert "version=str(" in spec_text
    # Hidden imports cover the whole updater package.
    for module in (
        "desktop.updater",
        "desktop.updater.config",
        "desktop.updater.versioning",
        "desktop.updater.release",
        "desktop.updater.checker",
        "desktop.updater.downloader",
        "desktop.updater.verify",
        "desktop.updater.installer",
        "desktop.updater.state",
        "desktop.updater.prefs",
        "desktop.updater.service",
        "desktop.updater.http",
        "desktop.version",
    ):
        assert f'"{module}"' in spec_text, f"{module} missing from spec hiddenimports"
