"""Tests for installer command construction and detached launch."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess

import pytest

from desktop.updater import config
from desktop.updater.downloader import UpdateError
from desktop.updater import installer as installer_module
from desktop.updater.installer import build_installer_command, launch_installer

EXPECTED_FLAGS = [
    "/VERYSILENT",
    "/SUPPRESSMSGBOXES",
    "/NORESTART",
    "/CLOSEAPPLICATIONS",
    "/FORCECLOSEAPPLICATIONS",
    "/SP-",
    "/UPDATE=1",
]


def make_exe(directory: Path, name: str = "Setup-RESIVO-1.2.0.exe") -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_bytes(b"MZ" + b"\x00" * 128)
    return path


def test_build_installer_command_is_exact(tmp_path):
    path = make_exe(tmp_path)
    command = build_installer_command(path)
    assert command == [str(path), *EXPECTED_FLAGS]


def test_flags_match_config():
    assert list(config.INSTALLER_SILENT_FLAGS) == EXPECTED_FLAGS


def test_launch_installer_detached(tmp_path, monkeypatch):
    monkeypatch.setenv("RESIVO_UPDATES_DIR", str(tmp_path / "updates"))
    exe = make_exe(tmp_path / "updates")
    captured = {}

    class FakeProcess:
        pass

    def fake_popen(**kwargs):
        captured.update(kwargs)
        return FakeProcess()

    monkeypatch.setattr(installer_module, "Popen", fake_popen)
    process = launch_installer(exe)

    assert isinstance(process, FakeProcess)
    assert captured["args"] == [str(exe), *EXPECTED_FLAGS]
    assert captured["cwd"] == str(exe.parent)
    assert captured["close_fds"] is True
    assert captured["shell"] is False
    if os.name == "nt":
        flags = captured["creationflags"]
        assert flags & subprocess.DETACHED_PROCESS
        assert flags & subprocess.CREATE_NEW_PROCESS_GROUP


def test_launch_installer_accepts_explicit_allowed_dir(tmp_path, monkeypatch):
    allowed = tmp_path / "allowed"
    exe = make_exe(allowed)
    captured = {}

    def fake_popen(**kwargs):
        captured.update(kwargs)

        class FakeProcess:
            pass

        return FakeProcess()

    monkeypatch.setattr(installer_module, "Popen", fake_popen)
    launch_installer(exe, allowed_dir=allowed)
    assert captured["args"][0] == str(exe)


def test_launch_refuses_path_outside_updates_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("RESIVO_UPDATES_DIR", str(tmp_path / "updates"))
    outside = make_exe(tmp_path / "elsewhere")

    def fail_popen(**kwargs):  # pragma: no cover - must not be called
        raise AssertionError("Popen must not be called")

    monkeypatch.setattr(installer_module, "Popen", fail_popen)
    with pytest.raises(UpdateError) as excinfo:
        launch_installer(outside)
    assert excinfo.value.code == "bad_installer_path"


def test_launch_refuses_non_exe(tmp_path, monkeypatch):
    monkeypatch.setenv("RESIVO_UPDATES_DIR", str(tmp_path / "updates"))
    updates = tmp_path / "updates"
    updates.mkdir(parents=True)
    text_file = updates / "installer.txt"
    text_file.write_text("not an installer", encoding="utf-8")

    def fail_popen(**kwargs):  # pragma: no cover - must not be called
        raise AssertionError("Popen must not be called")

    monkeypatch.setattr(installer_module, "Popen", fail_popen)
    with pytest.raises(UpdateError) as excinfo:
        launch_installer(text_file)
    assert excinfo.value.code == "bad_installer_path"


def test_launch_refuses_missing_file(tmp_path, monkeypatch):
    monkeypatch.setenv("RESIVO_UPDATES_DIR", str(tmp_path / "updates"))
    missing = tmp_path / "updates" / "Setup-RESIVO-9.9.9.exe"

    def fail_popen(**kwargs):  # pragma: no cover - must not be called
        raise AssertionError("Popen must not be called")

    monkeypatch.setattr(installer_module, "Popen", fail_popen)
    with pytest.raises(UpdateError) as excinfo:
        launch_installer(missing)
    assert excinfo.value.code == "bad_installer_path"
