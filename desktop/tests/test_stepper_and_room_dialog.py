"""Unit tests for C6: NumberStepper, RoomSetupDialog UI & RoomsPage toolbar."""

import pytest
from unittest.mock import MagicMock, patch

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QApplication, QDialogButtonBox, QMessageBox

from desktop.app.ui.components import NumberStepper
from desktop.app.ui.pages.rooms import RoomSetupDialog, RoomsPage
from desktop.ui.components.stepper import NumberStepper as ShimNumberStepper


@pytest.fixture
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_stepper_shim_import():
    assert NumberStepper is ShimNumberStepper


def test_stepper_api_and_range(qapp):
    stepper = NumberStepper()
    stepper.setRange(1, 5)
    assert stepper.minimum() == 1
    assert stepper.maximum() == 5

    stepper.setValue(1)
    assert stepper.value() == 1
    # Boundary: at min, minus button is disabled
    assert not stepper.minus_btn.isEnabled()
    assert stepper.plus_btn.isEnabled()

    # Step up to 2
    stepper.stepUp()
    assert stepper.value() == 2
    assert stepper.minus_btn.isEnabled()
    assert stepper.plus_btn.isEnabled()

    # Set to max
    stepper.setValue(5)
    assert stepper.value() == 5
    assert stepper.minus_btn.isEnabled()
    assert not stepper.plus_btn.isEnabled()

    # Step down
    stepper.stepDown()
    assert stepper.value() == 4
    assert stepper.plus_btn.isEnabled()


def test_stepper_signals_and_autorepeat(qapp):
    stepper = NumberStepper()
    stepper.setRange(0, 10)
    stepper.setValue(0)

    received = []
    stepper.valueChanged.connect(lambda val: received.append(val))

    stepper.plus_btn.click()
    assert stepper.value() == 1
    assert received == [1]

    # Check auto-repeat configuration
    assert stepper.plus_btn.autoRepeat()
    assert stepper.minus_btn.autoRepeat()
    assert stepper.plus_btn.autoRepeatDelay() == 300
    assert stepper.minus_btn.autoRepeatDelay() == 300

    # Height specification
    assert stepper.height() == 40 or stepper.sizeHint().height() == 40 or stepper.minimumHeight() == 40


def test_stepper_disabled_state(qapp):
    stepper = NumberStepper()
    stepper.setRange(0, 10)
    stepper.setValue(5)
    assert stepper.minus_btn.isEnabled()
    assert stepper.plus_btn.isEnabled()

    stepper.setEnabled(False)
    assert not stepper.isEnabled()
    assert not stepper.minus_btn.isEnabled()
    assert not stepper.plus_btn.isEnabled()


def test_stepper_wheel_only_on_focus(qapp):
    stepper = NumberStepper()
    stepper.show()
    qapp.processEvents()
    stepper.setRange(0, 10)
    stepper.setValue(5)

    # Wheel event without focus should be ignored
    stepper.clearFocus()
    stepper._spin.clearFocus()
    qapp.processEvents()
    event_unfocused = QWheelEvent(
        QPoint(10, 10),
        QPoint(10, 10),
        QPoint(0, 120),
        QPoint(0, 120),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )
    stepper._spin.wheelEvent(event_unfocused)
    assert stepper.value() == 5

    # Wheel event with focus modifies value
    stepper._spin.setFocus()
    qapp.processEvents()
    event_focused = QWheelEvent(
        QPoint(10, 10),
        QPoint(10, 10),
        QPoint(0, 120),
        QPoint(0, 120),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )
    stepper._spin.wheelEvent(event_focused)
    assert stepper.value() > 5
    stepper.close()


def test_room_setup_dialog_titles_and_components(qapp):
    blocks = [{"name": "A", "gender": "male"}]

    # 1. Add mode
    dlg_add = RoomSetupDialog(blocks=blocks)
    assert dlg_add.windowTitle() == "Add Dormitory Room"
    assert isinstance(dlg_add.floor_spin, NumberStepper)
    assert isinstance(dlg_add.cap_spin, NumberStepper)
    assert dlg_add.new_block_btn.text() == "Add block"
    assert dlg_add.new_block_btn.height() == 40
    assert dlg_add.block_combo.height() == 40
    assert dlg_add.save_btn.text() == "Create room"
    assert dlg_add.save_btn.isDefault()
    assert isinstance(dlg_add.button_box, QDialogButtonBox)

    # 2. Edit mode
    room = {"id": "r1", "block": "A", "floor": 2, "number": "201", "capacity": 3, "gender": "male"}
    dlg_edit = RoomSetupDialog(room=room, current_occupancy=1, blocks=blocks)
    assert dlg_edit.windowTitle() == "Edit Dormitory Room"
    assert dlg_edit.save_btn.text() == "Save changes"
    assert dlg_edit.floor_spin.value() == 2
    assert dlg_edit.cap_spin.value() == 3
    assert dlg_edit.cap_spin.minimum() == 1  # current occupancy minimum


def test_room_setup_dialog_validation_and_inline_error(qapp):
    blocks = [{"name": "A", "gender": "male"}]
    dlg = RoomSetupDialog(blocks=blocks)
    dlg.show()
    qapp.processEvents()

    # Initially empty room number: save button is disabled
    assert not dlg.num_edit.text().strip()
    assert not dlg.save_btn.isEnabled()

    # Inline error appears when user types or attempts save
    dlg.num_edit.setText("   ")
    qapp.processEvents()
    assert not dlg.save_btn.isEnabled()
    assert not dlg.num_error_label.isHidden()
    assert "required" in dlg.num_error_label.text().lower()

    # Provide valid room number: save button enabled and error hidden
    dlg.num_edit.setText("105")
    qapp.processEvents()
    assert dlg.save_btn.isEnabled()
    assert dlg.num_error_label.isHidden()

    # Check double-submission prevention
    dlg.on_save()
    assert dlg.result_data["number"] == "105"
    assert not dlg.save_btn.isEnabled()
    dlg.close()


def test_rooms_page_toolbar_and_selection(qapp):
    mock_client = MagicMock()
    mock_client.table.return_value.select.return_value.order.return_value.order.return_value.execute.return_value.data = [
        {"id": "r1", "block": "A", "floor": 1, "number": "101", "capacity": 2, "gender": "male"},
        {"id": "r2", "block": "A", "floor": 1, "number": "102", "capacity": 2, "gender": "male"},
    ]
    with patch("desktop.app.ui.pages.rooms.room_occupancy", return_value={}):
        page = RoomsPage(mock_client)

    # Add, Edit, Delete are all in toolbar and have equal height (36px)
    assert page.add_btn.height() == 36
    assert page.edit_btn.height() == 36
    assert page.delete_btn.height() == 36

    # Initially when rows are loaded without selection:
    # Edit and Delete buttons must be disabled with tooltip
    page.table.clearSelection()
    page.table.setCurrentItem(None)
    page._update_action_buttons()

    assert not page.edit_btn.isEnabled()
    assert not page.delete_btn.isEnabled()
    assert "Select a room" in page.edit_btn.toolTip()
    assert "Select a room" in page.delete_btn.toolTip()

    # Selecting a row enables Edit and Delete
    page.table.selectRow(0)
    assert page.edit_btn.isEnabled()
    assert page.delete_btn.isEnabled()
    assert "Edit the selected room" in page.edit_btn.toolTip()
    assert "Delete the selected room" in page.delete_btn.toolTip()

    # Clearing selection disables them again
    page.table.clearSelection()
    assert not page.edit_btn.isEnabled()
    assert not page.delete_btn.isEnabled()
