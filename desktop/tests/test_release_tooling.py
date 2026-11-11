"""Release tooling contract: installer + make_release.ps1 + release convention."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ISS_PATH = ROOT / "desktop" / "installer" / "resivo.iss"
PS1_PATH = ROOT / "tools" / "release" / "make_release.ps1"
RELEASING_DOC = ROOT / "docs" / "releasing.md"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_installer_keeps_its_identity_and_update_contract():
    text = _read(ISS_PATH)

    # Fixed AppId (upgrades must replace, never install side by side).
    assert "D37E84B1-6A22-4F15-B61E-7D49B892F1A0" in text
    assert "PrivilegesRequired=lowest" in text
    assert "DefaultDirName={localappdata}\\Programs\\RESIVO" in text

    # Version comes from the builder, never from the .iss file.
    assert "#ifndef MyAppVersion" in text
    assert "#error" in text
    assert "make_release.ps1" in text
    assert '#define MyAppVersion "' not in text

    # Single-instance mutex must match desktop/main.py.
    assert "AppMutex=RESIVO.Desktop.SingleInstance" in text
    assert "CloseApplications=yes" in text
    assert "RestartApplications=no" in text
    assert "UsePreviousAppDir=yes" in text

    # Silent update relaunch.
    assert "IsUpdateInstall" in text
    assert "function IsUpdateInstall: Boolean;" in text
    assert "WizardSilent" in text
    assert "{param:UPDATE|0}" in text
    assert '"--updated"' in text
    assert "runhidden" in text

    # The documented silent command line used by the updater.
    assert "/UPDATE=1" in text
    assert "/VERYSILENT" in text
    assert "/FORCECLOSEAPPLICATIONS" in text
    assert "/SP-" in text


def test_make_release_reads_version_and_builds_both_artifacts():
    text = _read(PS1_PATH)

    assert "desktop\\version.py" in text
    assert "__version__" in text
    assert ".venv\\Scripts\\python.exe" in text
    assert "PyInstaller" in text
    assert "desktop\\resivo.spec" in text
    assert "ISCC" in text
    assert "/DMyAppVersion=" in text
    assert "desktop\\installer\\resivo.iss" in text
    assert "Setup-RESIVO-" in text
    assert "SHA256SUMS.txt" in text
    assert "Get-FileHash" in text
    assert ".ToUpperInvariant()" in text


def test_make_release_writes_two_space_checksum_format():
    text = _read(PS1_PATH)
    # sha256sum format: <UPPERCASE_SHA256><two spaces><file name>
    assert "$hash  Setup-RESIVO-$version.exe" in text


def test_make_release_prints_but_never_runs_publishing():
    text = _read(PS1_PATH)
    assert "gh release create" in text
    assert "--notes-file" in text
    assert "--title" in text

    printed = [
        line
        for line in text.splitlines()
        if "gh release create" in line and ("Write-Host" in line or "Write-Output" in line)
    ]
    assert printed, "the printed gh command is missing"

    # No line may invoke gh directly (optionally through the call operator).
    for line in text.splitlines():
        assert not re.match(r"^\s*(&\s*)?gh\s+release\s+create\b", line), (
            f"gh release create must only be printed, not executed: {line.strip()}"
        )


def test_make_release_has_no_publishing_commands():
    text = _read(PS1_PATH)
    for forbidden in ("git tag", "git push", "Invoke-RestMethod", "Invoke-WebRequest", "--clobber"):
        assert forbidden not in text, f"make_release.ps1 must not publish ({forbidden})"


def test_releasing_doc_matches_the_convention():
    assert RELEASING_DOC.is_file(), "docs/releasing.md is missing"
    text = _read(RELEASING_DOC)

    assert "desktop\\version.py" in text or "desktop/version.py" in text
    assert "make_release.ps1" in text
    assert "Setup-RESIVO-" in text
    assert "SHA256SUMS.txt" in text
    assert "releases/latest" in text
    assert "pre-release" in text.lower()
    assert "vMAJOR.MINOR.PATCH" in text
