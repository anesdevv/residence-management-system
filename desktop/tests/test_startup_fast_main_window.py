"""Phase 3 tests: fast MainWindow startup, lazy pages, cached icons, title, live state."""

from __future__ import annotations

import os
import time
from types import SimpleNamespace
from unittest.mock import MagicMock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QThreadPool
from PySide6.QtWidgets import QApplication, QWidget

from desktop import i18n
from desktop.app.ui import icons as icons_mod
from desktop.app.ui import main_window as main_mod
from desktop.app.ui import theme as theme_mod
from desktop.app.ui.login_window import LoginWindow
from desktop.app.ui.main_window import MainWindow
from desktop.i18n import t

_qapp = QApplication.instance()
if _qapp is None:
    _qapp = QApplication([])


@pytest.fixture
def qapp():
    return _qapp


@pytest.fixture(autouse=True)
def _cleanup(qapp):
    yield
    QThreadPool.globalInstance().waitForDone(5000)
    qapp.processEvents()


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
        set_session=lambda acc, ref: SimpleNamespace(
            session=SimpleNamespace(
                access_token=acc,
                refresh_token=ref,
                expires_at=1900000000,
                user=SimpleNamespace(
                    id="admin-1",
                    email="admin@univ-tlemcen.dz",
                    user_metadata={"full_name": "Residence Admin"},
                ),
            )
        ),
        sign_out=lambda: None,
    )
    return SimpleNamespace(
        auth=auth,
        table=lambda _n: SimpleNamespace(
            select=lambda *_a, **_kw: SimpleNamespace(
                eq=lambda *_a, **_kw: SimpleNamespace(
                    neq=lambda *_a, **_kw: SimpleNamespace(execute=lambda: SimpleNamespace(count=0, data=[])),
                    single=lambda: SimpleNamespace(execute=lambda: SimpleNamespace(data={"role": "admin"})),
                    execute=lambda: SimpleNamespace(count=0, data=[]),
                ),
                neq=lambda *_a, **_kw: SimpleNamespace(execute=lambda: SimpleNamespace(count=0, data=[])),
                order=lambda *_a, **_kw: SimpleNamespace(execute=lambda: SimpleNamespace(data=[])),
                execute=lambda: SimpleNamespace(count=0, data=[]),
            )
        ),
        rpc=lambda *_a, **_kw: SimpleNamespace(execute=lambda: SimpleNamespace(data={})),
        functions=SimpleNamespace(invoke=lambda *_a, **_kw: b"[]"),
    )


def test_secondary_pages_are_lazy_and_hydrate_from_cached_live_sync(qapp, monkeypatch):
    builds: dict[str, int] = {}
    received_live: dict[str, list] = {}
    reloads: list[str] = []

    def _make_stub(name: str):
        class _StubPage(QWidget):
            def __init__(self, client, **kwargs):
                super().__init__()
                self.kwargs = kwargs
                builds[name] = builds.get(name, 0) + 1

            def apply_live_data(self, *args):
                received_live.setdefault(name, []).append(args)

            def reload(self):
                reloads.append(name)

            def reload_residence(self):
                pass

            def set_role(self, _role):
                pass

            def set_residence_name(self, _name):
                pass

        return _StubPage

    for page_cls_name in (
        "OverviewPage",
        "PendingPage",
        "ResidentsPage",
        "RoomsPage",
        "MaintenancePage",
        "RoomChangesPage",
        "OfficialListPage",
        "StaffAccountsPage",
        "SettingsPage",
    ):
        monkeypatch.setattr(main_mod, page_cls_name, _make_stub(page_cls_name))

    monkeypatch.setattr(main_mod.LiveSyncWorker, "start", lambda self: None)

    mw = MainWindow(_make_mock_client(), role="admin")
    try:
        # Only OverviewPage should be constructed upfront
        assert builds == {"OverviewPage": 1}
        assert "Overview" in mw.pages
        assert "Pending accounts" in mw.pages
        assert "Staff accounts" in mw.pages
        assert "Settings" in mw.pages

        # Live sync tick arrives before visiting secondary pages -> cached, no page build triggered
        mw.on_live_sync_tick({
            "pending_students": [{"id": "s1"}],
            "reports": [{"id": "m1"}],
            "open_reports_count": 1,
            "pending_requests": [{"id": "r1"}],
            "active_residents_count": 10,
        })
        assert builds == {"OverviewPage": 1}
        assert len(received_live["OverviewPage"]) == 1

        # Clicking Pending nav row constructs ONLY PendingPage and hydrates cached live data immediately
        mw.nav.setCurrentRow(1)
        qapp.processEvents()
        assert builds == {"OverviewPage": 1, "PendingPage": 1}
        assert received_live["PendingPage"] == [([{"id": "s1"}],)]
        assert "PendingPage" not in reloads

        # Clicking Residents nav row constructs ONLY ResidentsPage and triggers async reload
        mw.nav.setCurrentRow(2)
        qapp.processEvents()
        assert builds == {"OverviewPage": 1, "PendingPage": 1, "ResidentsPage": 1}
        assert "ResidentsPage" in reloads

        # Closing without visiting Settings must NOT instantiate SettingsPage
        assert "SettingsPage" not in builds
    finally:
        mw._shutdown_confirmed = True
        mw._shutdown_workers()
        mw.close()
        qapp.processEvents()
        assert "SettingsPage" not in builds


def test_main_window_title_and_connecting_live_state_i18n(qapp, monkeypatch):
    for page_cls_name in (
        "OverviewPage",
        "PendingPage",
        "ResidentsPage",
        "RoomsPage",
        "MaintenancePage",
        "RoomChangesPage",
        "OfficialListPage",
        "StaffAccountsPage",
        "SettingsPage",
    ):
        monkeypatch.setattr(main_mod, page_cls_name, lambda client, **_kw: QWidget())
    monkeypatch.setattr(main_mod.LiveSyncWorker, "start", lambda self: None)

    # English
    i18n.init("en")
    mw_en = MainWindow(_make_mock_client(), role="staff")
    try:
        assert mw_en.windowTitle() == "Staff Console"
        assert "RÉSIVO" not in mw_en.windowTitle()
        assert mw_en.live_label.text() == "Connecting..."
        assert mw_en.live_dot.property("state") == "connecting"
        assert "Staff accounts" not in mw_en.pages

        # Tick flips Connecting... -> Live sync connected
        mw_en.on_live_sync_tick({
            "pending_students": [],
            "reports": [],
            "open_reports_count": 0,
            "pending_requests": [],
            "active_residents_count": 0,
        })
        assert mw_en.live_label.text() == t("live_sync.connected")
        assert mw_en.live_dot.property("state") == "connected"
    finally:
        mw_en._shutdown_confirmed = True
        mw_en._shutdown_workers()
        mw_en.close()

    # French
    i18n.init("fr")
    mw_fr = MainWindow(_make_mock_client(), role="staff")
    try:
        assert mw_fr.windowTitle() == "Console du personnel"
        assert "RÉSIVO" not in mw_fr.windowTitle()
        assert mw_fr.live_label.text() == "Connexion en cours…"
        assert mw_fr.live_dot.property("state") == "connecting"
    finally:
        mw_fr._shutdown_confirmed = True
        mw_fr._shutdown_workers()
        mw_fr.close()
        i18n.init("en")


def test_svg_icon_cache_and_app_stylesheet_are_reused(qapp):
    icons_mod.clear_icon_cache()
    pm1 = icons_mod.get_pixmap("refresh", 18, "#0F766E")
    pm2 = icons_mod.get_pixmap("refresh", 18, "#0F766E")
    assert not pm1.isNull()
    assert pm1.cacheKey() == pm2.cacheKey()
    assert len(icons_mod._PIXMAP_CACHE) == 1

    ic1 = icons_mod.get_icon("refresh", 18, "#0F766E")
    ic2 = icons_mod.get_icon("refresh", 18, "#0F766E")
    assert not ic1.isNull()
    assert ic1.cacheKey() == ic2.cacheKey()
    assert len(icons_mod._ICON_CACHE) == 1

    theme_mod.apply_app_stylesheet()
    assert qapp.styleSheet() == theme_mod.DESKTOP_STYLESHEET


def test_atomic_swap_shows_main_window_before_closing_login(qapp, monkeypatch):
    events: list[str] = []

    class _TrackedMainWindow:
        def __init__(self, client, role=None):
            events.append("main_init")

        def show(self):
            events.append("main_show")

        def raise_(self):
            events.append("main_raise")

        def activateWindow(self):
            events.append("main_activate")

    monkeypatch.setattr(main_mod, "MainWindow", _TrackedMainWindow)

    login = LoginWindow(client=_make_mock_client())
    orig_close = login.close
    monkeypatch.setattr(login, "close", lambda: (events.append("login_close"), orig_close())[1])
    login.show()
    qapp.processEvents()

    login._open_main_window("admin")
    assert events == ["main_init", "main_show", "main_raise", "main_activate", "login_close"]


def test_defer_initial_load_skips_blocking_queries_on_secondary_pages(qapp, monkeypatch):
    from desktop.app.ui.pages.maintenance import MaintenancePage
    from desktop.app.ui.pages.official_list import OfficialListPage
    from desktop.app.ui.pages.pending import PendingPage
    from desktop.app.ui.pages.residents import ResidentsPage
    from desktop.app.ui.pages.room_changes import RoomChangesPage
    from desktop.app.ui.pages.rooms import RoomsPage
    from desktop.app.ui.pages import settings as settings_mod
    from desktop.app.ui.pages.settings import SettingsPage

    monkeypatch.setattr(settings_mod.McpHealthWorker, "start", lambda self: None)

    class _ForbidClient:
        auth = SimpleNamespace(get_user=lambda: (_ for _ in ()).throw(AssertionError("sync get_user")))
        functions = SimpleNamespace(invoke=lambda *_a, **_kw: (_ for _ in ()).throw(AssertionError("sync invoke")))

        def table(self, *_a, **_kw):
            raise AssertionError("sync table query during deferred __init__")

        def rpc(self, *_a, **_kw):
            raise AssertionError("sync rpc during deferred __init__")

    client = _ForbidClient()
    pages = [
        PendingPage(client, defer_initial_load=True),
        ResidentsPage(client, defer_initial_load=True),
        RoomsPage(client, defer_initial_load=True),
        MaintenancePage(client, defer_initial_load=True),
        RoomChangesPage(client, defer_initial_load=True),
        OfficialListPage(client, defer_initial_load=True, role="staff"),
        SettingsPage(client, defer_initial_load=True, role="staff"),
    ]
    for p in pages:
        p.close()
    qapp.processEvents()


def test_autostart_and_restarted_restore_launch_cleanly(qapp, monkeypatch, tmp_path):
    from desktop.auth.session_store import FakeBackend, SessionManager, SessionStore
    from desktop.main import launch_application

    for page_cls_name in (
        "OverviewPage",
        "PendingPage",
        "ResidentsPage",
        "RoomsPage",
        "MaintenancePage",
        "RoomChangesPage",
        "OfficialListPage",
        "StaffAccountsPage",
        "SettingsPage",
    ):
        monkeypatch.setattr(main_mod, page_cls_name, lambda client, **_kw: QWidget())
    monkeypatch.setattr(main_mod.LiveSyncWorker, "start", lambda self: None)
    monkeypatch.setattr("desktop.platform.autostart.get_start_minimized_setting", lambda: True)

    store = SessionStore(backend=FakeBackend(), storage_dir=tmp_path)
    sm = SessionManager(store=store)
    store.save(
        {
            "access_token": "acc_tok",
            "refresh_token": "ref_tok",
            "expires_at": 1900000000,
            "user_id": "admin-1",
        },
        remember=True,
    )
    client = _make_mock_client()

    deadline = None
    launch_application(
        app=qapp,
        client=client,
        session_manager_instance=sm,
        is_autostart=True,
        exec_loop=False,
    )
    end = time.monotonic() + 4.0
    while time.monotonic() < end:
        qapp.processEvents()
        if isinstance(getattr(qapp, "_main_window", None), MainWindow):
            break
        time.sleep(0.01)

    mw = getattr(qapp, "_main_window", None)
    assert isinstance(mw, MainWindow)
    assert mw.isMinimized()
    assert mw.windowTitle() == "Staff Console"
    assert mw.live_label.text() == t("live_sync.connecting")
    mw._shutdown_confirmed = True
    mw._shutdown_workers()
    mw.close()
    qapp._main_window = None
