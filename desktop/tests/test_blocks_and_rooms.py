from unittest.mock import MagicMock, patch
import pytest
from PySide6.QtWidgets import QApplication

from desktop.app.ui.pages.rooms import (
    BlockSetupDialog,
    ManageBlocksDialog,
    RoomSetupDialog,
    RoomsPage,
)


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_block_setup_dialog_validation_and_creation(qapp):
    mock_client = MagicMock()
    existing = ["A", "B"]

    dlg = BlockSetupDialog(client=mock_client, existing_names=existing)
    dlg.name_edit.setText("")
    with patch("PySide6.QtWidgets.QMessageBox.warning") as mock_warn:
        dlg.on_save()
        mock_warn.assert_called_once()
        assert dlg.result_data is None

    # Test duplicate name
    dlg.name_edit.setText("a")
    with patch("PySide6.QtWidgets.QMessageBox.warning") as mock_warn:
        dlg.on_save()
        mock_warn.assert_called_once()
        assert dlg.result_data is None

    # Test valid block creation (Female)
    dlg.name_edit.setText("D")
    dlg.gender_combo.setCurrentText("Female")
    dlg.on_save()

    assert dlg.result_data == {"name": "D", "gender": "female"}
    mock_client.table.assert_called_with("blocks")
    mock_client.table().insert.assert_called_with({"name": "D", "gender": "female"})


def test_room_setup_dialog_automatic_gender_inheritance(qapp):
    blocks = [
        {"name": "A", "gender": "male"},
        {"name": "B", "gender": "female"},
        {"name": "NORTH", "gender": "female"},
    ]
    mock_client = MagicMock()

    dlg = RoomSetupDialog(client=mock_client, blocks=blocks)

    # Gender combo must be disabled (read-only) because it inherits from block
    assert not dlg.gender_combo.isEnabled()

    # Default to first block A (Male)
    dlg.block_combo.setCurrentIndex(0)
    assert dlg.gender_combo.currentText() == "Male"
    assert "Block A" in dlg.gender_note.text()

    # Switch to block B (Female)
    dlg.block_combo.setCurrentIndex(1)
    assert dlg.gender_combo.currentText() == "Female"
    assert "Block B" in dlg.gender_note.text()
    assert dlg.block_edit.text() == "B"

    # Fill room number and verify saved result has female gender automatically
    dlg.num_edit.setText("205")
    dlg.floor_spin.setValue(2)
    dlg.cap_spin.setValue(3)
    dlg.on_save()

    assert dlg.result_data == {
        "block": "B",
        "floor": 2,
        "number": "205",
        "capacity": 3,
        "gender": "female",
    }


def test_room_setup_dialog_occupied_room_locks_block_and_gender(qapp):
    blocks = [
        {"name": "A", "gender": "male"},
        {"name": "B", "gender": "female"},
    ]
    room = {"id": "r1", "block": "B", "floor": 1, "number": "104", "capacity": 2, "gender": "female"}

    # Room with 1 active occupant
    dlg = RoomSetupDialog(room=room, current_occupancy=1, blocks=blocks)

    assert not dlg.block_combo.isEnabled()
    assert not dlg.new_block_btn.isEnabled()
    assert not dlg.gender_combo.isEnabled()
    assert dlg.gender_combo.currentText() == "Female"


def test_manage_blocks_dialog_table_and_actions(qapp):
    blocks = [
        {"id": "b1", "name": "A", "gender": "male"},
        {"id": "b2", "name": "B", "gender": "female"},
        {"id": "b3", "name": "EMPTY", "gender": "female"},
    ]
    rooms = [
        {"id": "r1", "block": "A", "capacity": 2},
        {"id": "r2", "block": "B", "capacity": 3},
    ]
    occupancy = {"r1": 1, "r2": 2}
    mock_client = MagicMock()
    mock_client.table.return_value.select.return_value.order.return_value.execute.return_value.data = blocks

    dlg = ManageBlocksDialog(client=mock_client, rooms=rooms, occupancy=occupancy)
    assert dlg.table.rowCount() == 3

    # Check Block A (row 0)
    assert "Block A" in dlg.table.item(0, 0).text()
    assert dlg.table.item(0, 2).text() == "1"  # 1 room
    assert dlg.table.item(0, 3).text() == "2"  # 2 beds
    assert dlg.table.item(0, 4).text() == "1"  # 1 occupied

    # Block A has rooms: delete button must be disabled
    del_holder_a = dlg.table.cellWidget(0, 5)
    del_btn_a = del_holder_a.findChild(type(dlg.add_block_btn))
    assert del_btn_a is not None
    assert not del_btn_a.isEnabled()

    # Block EMPTY (row 2) has 0 rooms: delete button must be enabled
    del_holder_empty = dlg.table.cellWidget(2, 5)
    del_btn_empty = del_holder_empty.findChild(type(dlg.add_block_btn))
    assert del_btn_empty is not None
    assert del_btn_empty.isEnabled()


def test_rooms_page_has_blocks_management_button(qapp):
    mock_client = MagicMock()
    mock_client.table.return_value.select.return_value.order.return_value.order.return_value.execute.return_value.data = []
    with patch("desktop.app.ui.pages.rooms.room_occupancy", return_value={}):
        page = RoomsPage(mock_client)

    assert hasattr(page, "blocks_btn")
    assert page.blocks_btn.text() == "Residential blocks"
