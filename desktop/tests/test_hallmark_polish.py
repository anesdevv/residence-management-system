"""Tests verifying Nutlope Hallmark accessibility, state, motion, and visual-craft rules."""

from __future__ import annotations

import os
from PySide6.QtCore import QAbstractAnimation, QEvent, QPointF, Qt
from PySide6.QtGui import QEnterEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from desktop.app.ui import theme
from desktop.app.ui.components import (
    Button,
    IconButton,
    LiveDot,
    Skeleton,
    Toast,
    show_toast,
)
from desktop.app.ui.infocard import RoomInfoCardDialog
from desktop.app.ui.pages.maintenance import MaintenancePage
from desktop.app.ui.pages.official_list import ClearAllRosterDialog, OfficialListPage
from desktop.app.ui.pages.overview import OverviewPage
from desktop.app.ui.pages.pending import PendingPage
from desktop.app.ui.pages.residents import ResidentsPage
from desktop.app.ui.pages.room_changes import RoomChangesPage
from desktop.app.ui.pages.rooms import RoomSetupDialog, RoomsPage
from desktop.app.ui.pages.staff_accounts import StaffAccountsPage
from desktop.app.ui.residence_dialogs import (
    ResidenceGenderChangeDialog,
    ResidenceSetupDialog,
)
from desktop.app.ui.stepper import NumberStepper


def _hex_to_rgb(hex_color: str) -> tuple[float, float, float]:
    value = hex_color.lstrip("#")
    if len(value) == 8:
        value = value[:6]
    return tuple(int(value[i : i + 2], 16) / 255.0 for i in (0, 2, 4))


def _contrast_ratio(c1: str, c2: str) -> float:
    def lum(rgb: tuple[float, float, float]) -> float:
        def ch(c: float) -> float:
            return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

        r, g, b = (ch(x) for x in rgb)
        return 0.2126 * r + 0.7152 * g + 0.0722 * b

    l1, l2 = lum(_hex_to_rgb(c1)), lum(_hex_to_rgb(c2))
    return (max(l1, l2) + 0.05) / (min(l1, l2) + 0.05)


class _DummyQuery:
    def __init__(self, data=None):
        self._data = data if data is not None else []
        self.count = len(self._data)

    def select(self, *_a, **_kw):
        return self

    def eq(self, *_a, **_kw):
        return self

    def neq(self, *_a, **_kw):
        return self

    def order(self, *_a, **_kw):
        return self

    def limit(self, *_a, **_kw):
        return self

    def execute(self):
        return self

    @property
    def data(self):
        return self._data


class _DummyAuth:
    def get_user(self):
        class _Resp:
            class _User:
                id = "uid-1"

            user = _User()

        return _Resp()


class _DummyFunctions:
    def invoke(self, *_a, **_kw):
        return {"data": []}


class _DummyClient:
    def __init__(self):
        self.auth = _DummyAuth()
        self.functions = _DummyFunctions()

    def table(self, _name: str):
        return _DummyQuery([])

    def rpc(self, _name: str, _params=None):
        return _DummyQuery([])


def test_qss_hallmark_stamp_and_no_forbidden_constructs():
    qss = theme.DESKTOP_STYLESHEET
    assert qss.lstrip().startswith("/* hallmark: checked")
    assert "scope: app-screens" in qss[:240]
    assert "@import" not in qss
    assert ":nth-child" not in qss
    assert "calc(" not in qss
    assert "border-input" in theme.TOKENS


def test_wcag_contrast_ratios_and_focus_rings():
    t = theme.TOKENS
    text_pairs = [
        (t["text-primary"], t["surface"]),
        (t["text-secondary"], t["surface"]),
        (t["text-muted"], t["surface"]),
        (t["text-muted"], t["canvas"]),
        (t["text-muted"], t["surface-subtle"]),
        (t["text-on-dark"], t["navy-900"]),
        (t["text-on-dark-muted"], t["navy-900"]),
        (t["surface"], t["navy-800"]),
        (t["surface"], t["teal-600"]),
        (t["surface"], t["status-danger-ink"]),
        (t["status-ok-ink"], t["status-ok-bg"]),
        (t["status-pending-ink"], t["status-pending-bg"]),
        (t["status-review-ink"], t["status-review-bg"]),
        (t["status-progress-ink"], t["status-progress-bg"]),
        (t["status-danger-ink"], t["status-danger-bg"]),
        (t["status-neutral-ink"], t["status-neutral-bg"]),
    ]
    for fg, bg in text_pairs:
        assert _contrast_ratio(str(fg), str(bg)) >= 4.5, f"Low text contrast: {fg} on {bg}"

    # Interactive control edges >= 3:1 (WCAG 1.4.11)
    assert _contrast_ratio(str(t["border-input"]), str(t["surface"])) >= 3.0
    assert _contrast_ratio(str(t["border-input"]), str(t["canvas"])) >= 3.0
    assert _contrast_ratio(str(t["border-input"]), str(t["surface-subtle"])) >= 3.0

    # Every button variant's outer focus ring must contrast >= 3:1 against page surface & canvas
    for name, spec in theme._BUTTON_SPECS.items():
        ring_hex = str(t[str(spec["ring"])])
        assert _contrast_ratio(ring_hex, str(t["surface"])) >= 3.0, f"{name} focus ring vs surface"
        assert _contrast_ratio(ring_hex, str(t["canvas"])) >= 3.0, f"{name} focus ring vs canvas"


def test_button_and_input_focus_zero_geometry_shift_and_disabled_cursor(qapp):
    host = QWidget()
    layout = QVBoxLayout(host)
    btn_lg = Button.primary("Primary Action")
    btn_sm = Button("Compact", variant="secondary", size="sm")
    icon_btn = IconButton("refresh", "Reload")
    line_edit = QLineEdit("hello")
    combo = QComboBox()
    combo.addItems(["One", "Two"])
    stepper = NumberStepper()
    checkbox = QCheckBox("Stay signed in until this PC restarts")

    for w in (btn_lg, btn_sm, icon_btn, line_edit, combo, stepper, checkbox):
        layout.addWidget(w)

    host.resize(360, 460)
    host.show()
    qapp.processEvents()

    for w in (btn_lg, btn_sm, icon_btn, line_edit, combo, stepper, checkbox):
        before = w.size()
        w.setFocus()
        qapp.processEvents()
        after = w.size()
        assert before == after, f"Focus changed size for {w!r}: {before} -> {after}"

    # QCheckBox focus ring must stay on the indicator only, never wrap the text label
    checkbox.setFocus()
    qapp.processEvents()
    cb_img = checkbox.grab().toImage()
    text_teal = [
        (x, y)
        for x in range(40, cb_img.width())
        for y in range(cb_img.height())
        if cb_img.pixelColor(x, y).green() > 100 and cb_img.pixelColor(x, y).red() < 50
    ]
    assert text_teal == [], f"Unexpected focus border around checkbox text: {text_teal[:5]}"

    # Cursor reflects disabled affordance
    assert btn_lg.cursor().shape() == Qt.CursorShape.PointingHandCursor
    btn_lg.setEnabled(False)
    qapp.processEvents()
    assert btn_lg.cursor().shape() == Qt.CursorShape.ForbiddenCursor
    btn_lg.setEnabled(True)
    qapp.processEvents()
    assert btn_lg.cursor().shape() == Qt.CursorShape.PointingHandCursor

    assert icon_btn.cursor().shape() == Qt.CursorShape.PointingHandCursor
    icon_btn.setEnabled(False)
    qapp.processEvents()
    assert icon_btn.cursor().shape() == Qt.CursorShape.ForbiddenCursor
    host.close()


def test_reduced_motion_honored(qapp, monkeypatch):
    monkeypatch.setenv("RESIVO_REDUCED_MOTION", "1")
    assert theme.prefers_reduced_motion() is True
    assert theme.effective_duration(200) == 0

    host = QWidget()
    host.resize(500, 400)
    dot = LiveDot(host)
    skel = Skeleton(rows=3, parent=host)
    dot.set_state("connected")
    host.show()
    qapp.processEvents()

    assert dot._animation.state() == QAbstractAnimation.State.Stopped
    assert dot._effect.opacity() == 1.0
    assert skel._animation.state() == QAbstractAnimation.State.Stopped

    toast = show_toast(host, "Saved", kind="success")
    qapp.processEvents()
    assert toast is not None
    expected_x = max(0, host.width() - toast.width() - theme.S("space-6"))
    assert toast.x() == expected_x
    toast.dismiss()
    host.close()


def test_toast_hover_pause_error_close_and_stacking(qapp, monkeypatch):
    monkeypatch.setenv("RESIVO_REDUCED_MOTION", "1")
    host = QWidget()
    host.resize(640, 480)
    host.show()
    qapp.processEvents()

    t1 = show_toast(host, "First update", kind="info", duration_ms=5000)
    t2 = show_toast(host, "Operation failed", kind="error", duration_ms=5000)
    qapp.processEvents()

    assert isinstance(t1, Toast) and isinstance(t2, Toast)
    # Newer toast stacks above older toast with no overlap
    assert t2.y() + t2.height() <= t1.y()
    assert t2.close_btn is not None
    assert t1.close_btn is None

    # Hovering pauses auto-dismiss timer and leaving resumes it
    assert t2._dismiss_timer.isActive()
    t2.enterEvent(QEnterEvent(QPointF(5, 5), QPointF(5, 5), QPointF(5, 5)))
    assert not t2._dismiss_timer.isActive()
    t2.leaveEvent(QEvent(QEvent.Type.Leave))
    assert t2._dismiss_timer.isActive()

    t1.dismiss()
    t2.dismiss()
    host.close()


def test_app_screen_data_states_disabled_tooltips_and_flat_nesting(qapp):
    client = _DummyClient()

    pages = [
        OverviewPage(client),
        PendingPage(client, defer_initial_load=True),
        ResidentsPage(client, defer_initial_load=True),
        RoomsPage(client, defer_initial_load=True),
        MaintenancePage(client, defer_initial_load=True),
        RoomChangesPage(client, defer_initial_load=True),
        OfficialListPage(client, defer_initial_load=True, role="admin"),
        StaffAccountsPage(client, defer_initial_load=True),
    ]
    for page in pages:
        assert hasattr(page, "error_banner"), f"{type(page).__name__} missing error_banner"
        assert hasattr(page, "retry_btn"), f"{type(page).__name__} missing retry_btn"
        assert hasattr(page, "skeleton"), f"{type(page).__name__} missing skeleton"
        assert any(
            isinstance(child, QPushButton) and child is page.retry_btn
            for child in page.error_banner.findChildren(QPushButton)
        )

    # Disabled tooltips explain why actions are disabled
    m_page = pages[4]
    assert not m_page.copy_summary_btn.isEnabled()
    assert bool(m_page.copy_summary_btn.toolTip().strip())

    rc_page = pages[5]
    assert not rc_page.copy_summary_btn.isEnabled()
    assert bool(rc_page.copy_summary_btn.toolTip().strip())

    sa_page = pages[7]
    assert not sa_page.delete_btn.isEnabled()
    assert bool(sa_page.delete_btn.toolTip().strip())

    clr_dlg = ClearAllRosterDialog(total_count=5, matching_pending=1)
    assert not clr_dlg.delete_button.isEnabled()
    assert bool(clr_dlg.delete_button.toolTip().strip())
    clr_dlg.close()

    rm_dlg = RoomSetupDialog(blocks=[{"name": "A", "gender": "male"}])
    assert not rm_dlg.save_btn.isEnabled()
    assert bool(rm_dlg.save_btn.toolTip().strip())
    rm_dlg.close()

    res_dlg = ResidenceSetupDialog(None, client=client)
    assert not res_dlg.save_btn.isEnabled()
    assert bool(res_dlg.save_btn.toolTip().strip())
    res_dlg.close()

    chg_dlg = ResidenceGenderChangeDialog(
        None,
        impact={"total": 1, "pending": 0, "active": 1, "rejected": 0, "assigned": 1, "other_count": 0},
        new_gender="male",
    )
    assert not chg_dlg.confirm_btn.isEnabled()
    assert bool(chg_dlg.confirm_btn.toolTip().strip())
    chg_dlg.close()

    # RoomInfoCardDialog must not nest cardFrame inside cardFrame
    room_dlg = RoomInfoCardDialog(
        None,
        {
            "block": "A",
            "floor": 1,
            "number": "104",
            "capacity": 4,
            "occupants": [{"first_name": "Nadia", "last_name": "Haddad", "card_id": "2024001", "faculty": "CS"}],
        },
    )
    cards = [
        f for f in room_dlg.findChildren(QFrame) if f.property("cardFrame") is True
    ]
    for outer in cards:
        nested = [
            inner for inner in outer.findChildren(QFrame)
            if inner is not outer and inner.property("cardFrame") is True
        ]
        assert not nested, f"Found nested cardFrame inside {outer.objectName()!r}"
    room_dlg.close()

    for page in pages:
        page.close()
