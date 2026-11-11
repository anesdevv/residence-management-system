"""Regression tests ensuring every lazy desktop module is bundled in frozen builds."""

from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QThreadPool
from PySide6.QtWidgets import QApplication, QWidget

from desktop.app.ui import main_window as main_mod
from desktop.app.ui.main_window import MainWindow
from tools.check_deps import expected_desktop_modules

ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = ROOT / "desktop" / "resivo.spec"

_qapp = QApplication.instance()
if _qapp is None:
    _qapp = QApplication([])


def _spec_hiddenimports(tmp_path: Path) -> set[str]:
    pytest.importorskip("PyInstaller")
    captured: dict[str, object] = {}

    class _StubAnalysis:
        def __init__(self, *args, **kwargs):
            captured["hiddenimports"] = list(kwargs.get("hiddenimports") or [])
            self.scripts = []
            self.pure = []
            self.binaries = []
            self.zipfiles = []
            self.zipped_data = []
            self.datas = []

    ns = {
        "__file__": str(SPEC_PATH),
        "SPECPATH": str(ROOT / "desktop"),
        "DISTPATH": str(tmp_path / "dist"),
        "workpath": str(tmp_path / "build"),
        "Analysis": _StubAnalysis,
        "PYZ": lambda *a, **kw: object(),
        "EXE": lambda *a, **kw: object(),
        "COLLECT": lambda *a, **kw: object(),
    }
    exec(compile(SPEC_PATH.read_text(encoding="utf-8"), str(SPEC_PATH), "exec"), ns)
    return set(captured["hiddenimports"])  # type: ignore[arg-type]


def test_resivo_spec_bundles_all_desktop_and_lazy_page_modules(tmp_path: Path):
    hidden = _spec_hiddenimports(tmp_path)

    # Every lazy page referenced by MainWindow._LAZY_PAGE_MODULES must resolve
    # under desktop.app.ui (the package MainWindow runs under in main.py).
    lazy_targets = {
        f"desktop.app.ui{rel}" for rel in main_mod._LAZY_PAGE_MODULES.values()
    }
    missing_lazy = sorted(lazy_targets - hidden)
    assert not missing_lazy, f"Lazy page modules missing from resivo.spec hiddenimports: {missing_lazy}"

    # Every desktop.* source module must also be covered so transitive imports
    # (infocard, updates_ui, importers.official_list, stepper shim) never drop.
    expected = expected_desktop_modules(ROOT)
    missing_all = sorted(expected - hidden)
    assert not missing_all, f"Desktop modules missing from resivo.spec hiddenimports: {missing_all}"


def _make_mock_client():
    auth = SimpleNamespace(
        _in_memory_session=SimpleNamespace(
            user=SimpleNamespace(
                id="admin-1",
                email="admin@univ-tlemcen.dz",
                user_metadata={"full_name": "Residence Admin"},
            )
        ),
        get_user=lambda: SimpleNamespace(
            user=SimpleNamespace(
                id="admin-1",
                email="admin@univ-tlemcen.dz",
                user_metadata={"full_name": "Residence Admin"},
            )
        ),
        sign_out=lambda: None,
    )

    class _QueryStub:
        def select(self, *_a, **_kw):
            return self

        def eq(self, *_a, **_kw):
            return self

        def neq(self, *_a, **_kw):
            return self

        def in_(self, *_a, **_kw):
            return self

        def order(self, *_a, **_kw):
            return self

        def limit(self, *_a, **_kw):
            return self

        def single(self):
            return self

        def maybe_single(self):
            return self

        def execute(self):
            return SimpleNamespace(count=0, data=[])

    return SimpleNamespace(
        auth=auth,
        table=lambda _n: _QueryStub(),
        rpc=lambda *_a, **_kw: SimpleNamespace(execute=lambda: SimpleNamespace(data={})),
        functions=SimpleNamespace(invoke=lambda *_a, **_kw: b"[]"),
    )


def test_main_window_navigates_to_all_real_lazy_pages(monkeypatch):
    from desktop.app.ui.pages import settings as settings_mod

    monkeypatch.setattr(main_mod.LiveSyncWorker, "start", lambda self: None)
    monkeypatch.setattr(settings_mod.McpHealthWorker, "start", lambda self: None)
    monkeypatch.setattr(main_mod.UpdateService, "check", lambda self, *a, **kw: False)

    mw = MainWindow(_make_mock_client(), role="admin")
    try:
        for row in range(len(mw._nav_slot_keys)):
            mw.nav.setCurrentRow(row)
            _qapp.processEvents()
            assert isinstance(mw.stack.currentWidget(), QWidget)

        mw.on_settings_clicked()
        _qapp.processEvents()
        assert isinstance(mw.stack.currentWidget(), QWidget)

        for slot in (
            "pending",
            "residents",
            "rooms",
            "maintenance",
            "room_changes",
            "official_list",
            "staff_accounts",
            "settings",
        ):
            assert slot in mw._built_pages, f"Real page {slot!r} was not built"
    finally:
        mw._shutdown_confirmed = True
        mw._shutdown_workers()
        mw.close()
        QThreadPool.globalInstance().waitForDone(5000)
        _qapp.processEvents()
