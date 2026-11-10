"""Phase 2 tests: Desktop single-gender residence settings, startup prompts, UI removal, and warning badges."""

from __future__ import annotations

import os
import time
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QThreadPool
from PySide6.QtWidgets import QApplication, QDialog, QWidget

from desktop.app.client import invalidate_residence_settings_cache
from desktop.app.ui.infocard import RoomInfoCardDialog, StudentInfoCardDialog
from desktop.app.ui.main_window import MainWindow
from desktop.app.ui.pages import pending as pending_mod
from desktop.app.ui.pages import settings as settings_mod
from desktop.app.ui.pages.pending import PendingPage, RoomAllocationDialog
from desktop.app.ui.pages.residents import ResidentsPage
from desktop.app.ui.pages.room_changes import RoomChangesPage
from desktop.app.ui.pages.rooms import BlockSetupDialog, RoomSetupDialog, RoomsPage
from desktop.app.ui.pages.settings import SettingsPage
from desktop.app.ui.residence_dialogs import ResidenceGenderChangeDialog, ResidenceSetupDialog

_qapp = QApplication.instance()
if _qapp is None:
    _qapp = QApplication([])


@pytest.fixture
def qapp():
    return _qapp


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    invalidate_residence_settings_cache()
    monkeypatch.setattr("desktop.app.ui.pages.settings.McpHealthWorker.start", lambda self: None)
    monkeypatch.setattr("desktop.app.ui.main_window.LiveSyncWorker.start", lambda self: None)
    yield
    QThreadPool.globalInstance().waitForDone(5000)
    _qapp.processEvents()
    invalidate_residence_settings_cache()


def wait_until(qapp, predicate, timeout=4.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        qapp.processEvents()
        if predicate():
            return True
        time.sleep(0.01)
    qapp.processEvents()
    return bool(predicate())


class _FakeRpcChain:
    def __init__(self, client, fn_name: str, params: dict):
        self.client = client
        self.fn_name = fn_name
        self.params = dict(params or {})

    def execute(self):
        self.client.rpc_calls.append((self.fn_name, dict(self.params)))
        if self.fn_name == "get_residence_public":
            return SimpleNamespace(
                data={
                    "residence_name": self.client.residence_name,
                    "residence_gender": self.client.residence_gender,
                }
            )
        if self.fn_name == "get_residence_settings_admin":
            return SimpleNamespace(
                data={
                    "residence_name": self.client.residence_name,
                    "residence_gender": self.client.residence_gender,
                    "last_changed_at": self.client.last_changed_at,
                    "last_changed_by_name": self.client.last_changed_by_name,
                }
            )
        if self.fn_name == "get_residence_gender_change_impact":
            if self.client.impact_delay:
                time.sleep(self.client.impact_delay)
            return SimpleNamespace(data=dict(self.client.impact))
        if self.fn_name == "set_residence_gender":
            if self.client.set_delay:
                time.sleep(self.client.set_delay)
            if self.client.set_error:
                raise self.client.set_error
            if self.client.impact.get("needs_confirmation") and self.params.get("p_confirmation") != "CHANGE":
                raise RuntimeError("Confirmation required: type CHANGE")
            self.client.residence_gender = self.params["p_gender"]
            self.client.last_changed_at = "2026-11-10T22:00:00Z"
            self.client.last_changed_by_name = "Residence Director"
            return SimpleNamespace(
                data={
                    "residence_name": self.client.residence_name,
                    "residence_gender": self.client.residence_gender,
                }
            )
        if self.fn_name == "set_residence_name":
            self.client.residence_name = str(self.params["p_name"]).strip()
            return SimpleNamespace(
                data={
                    "residence_name": self.client.residence_name,
                    "residence_gender": self.client.residence_gender,
                }
            )
        if self.fn_name == "mcp_get_settings":
            return SimpleNamespace(data={"writes_enabled": True})
        return SimpleNamespace(data=None)


class _FakeTableChain:
    def __init__(self, client, name: str):
        self.client = client
        self.name = name

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, *_args, **_kwargs):
        return self

    def order(self, *_args, **_kwargs):
        return self

    def single(self):
        return self

    def execute(self):
        return SimpleNamespace(data=[])


class _FakeResidenceClient:
    def __init__(
        self,
        *,
        role: str = "admin",
        residence_name: str = "Cité Universitaire · Tlemcen",
        residence_gender: str | None = None,
        impact: dict | None = None,
    ):
        self.role = role
        self.residence_name = residence_name
        self.residence_gender = residence_gender
        self.last_changed_at = None
        self.last_changed_by_name = None
        self.impact = dict(
            impact
            or {
                "current_gender": residence_gender,
                "new_gender": "male",
                "students_total": 0,
                "students_pending": 0,
                "students_active": 0,
                "students_rejected": 0,
                "students_with_room": 0,
                "students_of_other_gender": 0,
                "rooms_total": 0,
                "rooms_of_other_gender": 0,
                "open_room_change_requests": 0,
                "needs_confirmation": False,
            }
        )
        self.impact_delay = 0.0
        self.set_delay = 0.0
        self.set_error = None
        self.rpc_calls: list[tuple[str, dict]] = []
        user = SimpleNamespace(
            id="u-1",
            email="director@residence.test",
            user_metadata={"full_name": "Residence Director", "role": role},
        )
        self.auth = SimpleNamespace(
            get_session=lambda: SimpleNamespace(user=user, access_token="tok"),
            sign_out=lambda: None,
        )

    def rpc(self, fn_name: str, params: dict | None = None):
        return _FakeRpcChain(self, fn_name, params or {})

    def table(self, name: str):
        return _FakeTableChain(self, name)


def test_typed_confirmation_dialog_contract(qapp):
    impact = {
        "current_gender": "female",
        "new_gender": "male",
        "students_total": 120,
        "students_pending": 14,
        "students_active": 100,
        "students_rejected": 6,
        "students_with_room": 98,
        "students_of_other_gender": 12,
        "rooms_total": 60,
        "rooms_of_other_gender": 60,
        "open_room_change_requests": 2,
        "needs_confirmation": True,
    }
    dlg = ResidenceGenderChangeDialog(None, impact, "male")
    body = dlg.body_label.text()

    assert dlg.windowTitle() == "Change the residence type?"
    assert "120 students" in body
    assert "14 pending" in body
    assert "100 active" in body
    assert "6 rejected" in body
    assert "98 assigned rooms" in body
    assert "12 students are registered as female" in body
    assert "Existing students and rooms will NOT be changed" in body
    assert dlg.cancel_btn.isDefault()
    assert not dlg.confirm_btn.isDefault()
    assert not dlg.confirm_btn.isEnabled()

    for bad in ("", "change", "Change", "CHANGE ", " CHANGE", "YES"):
        dlg.confirm_edit.setText(bad)
        assert not dlg.confirm_btn.isEnabled(), f"{bad!r} must keep button disabled"

    dlg.confirm_edit.setText("CHANGE")
    assert dlg.confirm_btn.isEnabled()

    # Cancel resets confirmed=False and leaves DB untouched
    dlg.cancel_btn.click()
    assert not dlg.confirmed


def test_settings_residence_visibility_by_role(qapp, monkeypatch):
    client = _FakeResidenceClient(role="staff", residence_gender="male")
    monkeypatch.setattr("desktop.app.ui.pages.settings.current_role", lambda _c: "staff")
    staff_page = SettingsPage(client)
    assert staff_page.residence_card.isHidden()

    monkeypatch.setattr("desktop.app.ui.pages.settings.current_role", lambda _c: "admin")
    client_admin = _FakeResidenceClient(role="admin", residence_gender="male")
    admin_page = SettingsPage(client_admin)
    assert not admin_page.residence_card.isHidden()
    assert admin_page.residence_type_combo.currentData() == "male"


def test_settings_no_data_confirm_and_cancel(qapp, monkeypatch):
    client = _FakeResidenceClient(role="admin", residence_gender=None)
    monkeypatch.setattr("desktop.app.ui.pages.settings.current_role", lambda _c: "admin")
    page = SettingsPage(client)

    # Cancel keeps type unset and makes no set_residence_gender call
    with patch.object(settings_mod.ConfirmDialog, "ask", return_value=False) as mock_ask:
        idx_female = page.residence_type_combo.findData("female")
        page.residence_type_combo.setCurrentIndex(idx_female)
        assert wait_until(qapp, lambda: mock_ask.call_count == 1)

    assert page.residence_type_combo.currentData() is None
    assert not any(name == "set_residence_gender" for name, _ in client.rpc_calls)

    # Confirm without typed CHANGE when needs_confirmation is False
    with patch.object(settings_mod.ConfirmDialog, "ask", return_value=True):
        page.residence_type_combo.setCurrentIndex(idx_female)
        assert wait_until(
            qapp,
            lambda: client.residence_gender == "female"
            and not page._residence_saving
            and page.residence_type_combo.currentData() == "female"
            and "Residence Director" in page.residence_audit_label.text(),
        )

    set_calls = [p for name, p in client.rpc_calls if name == "set_residence_gender"]
    assert set_calls == [{"p_gender": "female", "p_confirmation": None}]
    assert page.residence_type_combo.currentData() == "female"
    assert "Residence Director" in page.residence_audit_label.text()


def test_settings_with_data_cancel_and_confirm_and_error_revert(qapp, monkeypatch):
    impact = {
        "current_gender": "female",
        "new_gender": "male",
        "students_total": 10,
        "students_pending": 2,
        "students_active": 8,
        "students_rejected": 0,
        "students_with_room": 8,
        "students_of_other_gender": 10,
        "rooms_total": 5,
        "rooms_of_other_gender": 5,
        "open_room_change_requests": 0,
        "needs_confirmation": True,
    }
    client = _FakeResidenceClient(role="admin", residence_gender="female", impact=impact)
    monkeypatch.setattr("desktop.app.ui.pages.settings.current_role", lambda _c: "admin")
    page = SettingsPage(client)
    assert page.residence_type_combo.currentData() == "female"

    # Cancel in typed dialog leaves female intact
    class _CancelledTypedDlg:
        confirmed = False

        def __init__(self, *args, **kwargs):
            pass

        def exec(self):
            return QDialog.DialogCode.Rejected

    with patch.object(settings_mod, "ResidenceGenderChangeDialog", _CancelledTypedDlg):
        idx_male = page.residence_type_combo.findData("male")
        page.residence_type_combo.setCurrentIndex(idx_male)
        assert wait_until(qapp, lambda: not page._residence_saving and any(n == "get_residence_gender_change_impact" for n, _ in client.rpc_calls))

    assert client.residence_gender == "female"
    assert page.residence_type_combo.currentData() == "female"

    # Server failure shows error banner and reverts selector
    class _AcceptedTypedDlg:
        confirmed = True

        def __init__(self, *args, **kwargs):
            pass

        def exec(self):
            return QDialog.DialogCode.Accepted

    client.set_error = RuntimeError("database unavailable")
    with patch.object(settings_mod, "ResidenceGenderChangeDialog", _AcceptedTypedDlg):
        page.residence_type_combo.setCurrentIndex(idx_male)
        assert wait_until(qapp, lambda: not page._residence_saving and not page.residence_banner.isHidden())

    assert client.residence_gender == "female"
    assert page.residence_type_combo.currentData() == "female"
    assert "database unavailable" in page.residence_banner._message.text()

    # Successful switch with 'CHANGE'
    client.set_error = None
    with patch.object(settings_mod, "ResidenceGenderChangeDialog", _AcceptedTypedDlg):
        page.residence_type_combo.setCurrentIndex(idx_male)
        assert wait_until(qapp, lambda: client.residence_gender == "male" and not page._residence_saving)

    set_calls = [p for name, p in client.rpc_calls if name == "set_residence_gender"]
    assert set_calls[-1] == {"p_gender": "male", "p_confirmation": "CHANGE"}


def test_settings_update_residence_name(qapp, monkeypatch):
    client = _FakeResidenceClient(role="admin", residence_gender="male")
    monkeypatch.setattr("desktop.app.ui.pages.settings.current_role", lambda _c: "admin")
    page = SettingsPage(client)
    changed_events = []
    page.residence_settings_changed.connect(lambda: changed_events.append(True))

    page.residence_name_edit.setText("Cité Universitaire Benboulaid")
    page.residence_name_save_btn.click()

    assert wait_until(qapp, lambda: len(changed_events) == 1)
    assert client.residence_name == "Cité Universitaire Benboulaid"


def _stub_main_window_pages(monkeypatch):
    for p in (
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
        monkeypatch.setattr(f"desktop.app.ui.main_window.{p}", lambda _c: QWidget())


def test_first_time_admin_dialog_and_staff_banner(qapp, monkeypatch):
    _stub_main_window_pages(monkeypatch)

    # 1. Admin gets one-time setup dialog when residence_gender is None
    admin_client = _FakeResidenceClient(role="admin", residence_gender=None)
    monkeypatch.setattr("desktop.app.ui.main_window.current_role", lambda _c: "admin")
    opened = []

    class _FakeSetupDlg:
        saved_gender = "female"

        def __init__(self, parent=None, client=None):
            opened.append(client)

        def exec(self):
            admin_client.residence_gender = "female"
            return QDialog.DialogCode.Accepted

    monkeypatch.setattr("desktop.app.ui.main_window.ResidenceSetupDialog", _FakeSetupDlg)
    mw_admin = MainWindow(admin_client, role="admin")
    mw_admin._check_residence_setup()
    assert wait_until(qapp, lambda: len(opened) == 1)
    mw_admin.close()

    # 2. Non-admin staff sees banner with no modal prompt (delivered via LiveSyncWorker signal or check)
    invalidate_residence_settings_cache()
    staff_client = _FakeResidenceClient(role="staff", residence_gender=None)
    monkeypatch.setattr("desktop.app.ui.main_window.current_role", lambda _c: "staff")
    staff_opened = []
    monkeypatch.setattr(
        "desktop.app.ui.main_window.ResidenceSetupDialog",
        lambda *_a, **_kw: staff_opened.append(True),
    )
    mw_staff = MainWindow(staff_client, role="staff")
    mw_staff.sync_worker.residence_loaded.emit(
        {"residence_name": "Cité Universitaire · Tlemcen", "residence_gender": None, "loaded": True}
    )
    assert wait_until(qapp, lambda: not mw_staff.residence_unset_banner.isHidden())
    assert staff_opened == []
    assert "The residence type has not been set. Ask an administrator." in mw_staff.residence_unset_banner._message.text()
    assert mw_staff.residence_settings_btn.isHidden()
    mw_staff.close()


def test_setup_dialog_saves_off_thread(qapp):
    client = _FakeResidenceClient(role="admin", residence_gender=None)
    dlg = ResidenceSetupDialog(client=client)
    assert not dlg.save_btn.isEnabled()

    dlg.female_radio.setChecked(True)
    assert dlg.save_btn.isEnabled()
    dlg.on_save()

    assert wait_until(qapp, lambda: dlg.saved_gender == "female")
    assert client.residence_gender == "female"


def test_rooms_and_residents_dropped_gender_controls_and_allocation_open(qapp):
    # RoomsPage & ResidentsPage have no gender_filter
    mock_client = MagicMock()
    mock_client.table.return_value.select.return_value.order.return_value.order.return_value.execute.return_value.data = [
        {"id": "r1", "block": "A", "floor": 1, "number": "101", "capacity": 2}
    ]
    with patch("desktop.app.ui.pages.rooms.room_occupancy", return_value={}):
        rooms_page = RoomsPage(mock_client)
    assert not hasattr(rooms_page, "gender_filter")
    assert rooms_page.table.columnCount() == 6

    res_mock = MagicMock()
    res_mock.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value.data = []
    residents_page = ResidentsPage(res_mock)
    assert not hasattr(residents_page, "gender_filter")

    # RoomAllocationDialog allows student allocation without gender restriction (only full rooms disabled)
    student = {"id": "s1", "card_id": "2024001", "first_name": "Bilal", "last_name": "Khelifi", "gender": "male"}
    rooms = [
        {"id": "r1", "block": "B", "number": "101", "floor": 1, "capacity": 2, "gender": "female"},
        {"id": "r2", "block": "A", "number": "102", "floor": 1, "capacity": 1, "gender": "male"},
    ]
    alloc = RoomAllocationDialog(None, student, rooms, {"r1": 0, "r2": 1})
    buttons = [alloc.room_rows.itemAt(i).widget().findChildren(type(alloc.findChildren(QWidget)[0])) for i in range(2)]
    from PySide6.QtWidgets import QPushButton
    row0_btns = alloc.room_rows.itemAt(0).widget().findChildren(QPushButton)
    row1_btns = alloc.room_rows.itemAt(1).widget().findChildren(QPushButton)
    assert row0_btns[0].isEnabled(), "Different stored room gender must NOT block allocation"
    assert not row1_btns[0].isEnabled(), "Full room must remain disabled"

    # RoomChangesPage._load_rooms does not filter by .eq("gender", ...)
    rc_mock = MagicMock()
    rc_mock.table.return_value.select.return_value.order.return_value.order.return_value.execute.return_value.data = []
    rc_page = RoomChangesPage(rc_mock)
    rc_mock.reset_mock()
    with patch("desktop.app.ui.pages.room_changes.room_occupancy", return_value={}):
        rc_page._load_rooms()
    rc_mock.table("rooms").select().eq.assert_not_called()

    # RoomInfoCardDialog omits "Designated for ... students"
    ri = RoomInfoCardDialog(None, {"block": "A", "number": "101", "floor": 2, "capacity": 2, "occupants": []}, None)
    labels = " ".join(lbl.text() for lbl in ri.findChildren(type(ri.capacity_pill).__mro__[1]))
    assert "Designated for" not in labels


def test_warning_only_gender_badges_in_pending_and_infocard(qapp):
    client = MagicMock()
    students = [
        {
            "id": "s1",
            "card_id": "2024001",
            "first_name": "Karim",
            "last_name": "Benali",
            "gender": "male",
            "status": "pending",
            "created_at": "2026-10-10T10:00:00Z",
        },
        {
            "id": "s2",
            "card_id": "2024002",
            "first_name": "Amira",
            "last_name": "Saidi",
            "gender": "female",
            "status": "pending",
            "created_at": "2026-10-10T10:00:00Z",
        },
    ]
    client.table.return_value.select.return_value.order.return_value.execute.return_value.data = students
    roster = {
        "2024001": {"card_id": "2024001", "first_name": "Karim", "last_name": "Benali", "gender": "female"},
        "2024002": {"card_id": "2024002", "first_name": "Amira", "last_name": "Saidi", "gender": "male"},
    }
    with patch.object(pending_mod, "official_lookup", return_value=roster):
        page = PendingPage(client)
    page.set_residence_gender("male")

    # Row 0: student male, roster female in a male residence -> amber warning shown, approve still enabled
    page.table.selectRow(0)
    assert not page.gender_warning_badge.isHidden()
    assert page.gender_warning_badge.text() == "Gender differs from this residence"
    assert page.approve_btn.isEnabled()

    # Row 1: stored female in a male residence -> amber warning shown, approve still enabled
    page.table.selectRow(1)
    assert not page.gender_warning_badge.isHidden()
    assert page.approve_btn.isEnabled()

    # Matching case hides badge
    roster["2024001"]["gender"] = "male"
    page.table.selectRow(0)
    assert page.gender_warning_badge.isHidden()

    # Resident detail modal (StudentInfoCardDialog) shows warning when student differs from residence_gender
    dlg_mismatch = StudentInfoCardDialog(
        None,
        students[1],
        roster["2024002"],
        residence_gender="male",
    )
    assert not dlg_mismatch.gender_warning_badge.isHidden()
    assert dlg_mismatch.gender_warning_badge.text() == "Gender differs from this residence"

    dlg_match = StudentInfoCardDialog(
        None,
        students[0],
        {"card_id": "2024001", "gender": "male"},
        residence_gender="male",
    )
    assert dlg_match.gender_warning_badge.isHidden()
