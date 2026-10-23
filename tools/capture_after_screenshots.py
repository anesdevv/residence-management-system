"""Capture offscreen screenshots of the redesigned Add/Edit Room dialog."""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtWidgets import QApplication

from desktop.app.ui.pages.rooms import RoomSetupDialog

def main():
    app = QApplication.instance() or QApplication([])

    out_dir = Path("docs/screenshots/ui-fix/after")
    out_dir.mkdir(parents=True, exist_ok=True)

    blocks = [
        {"name": "A", "gender": "male"},
        {"name": "B", "gender": "female"},
    ]

    # 1. Add Room Dialog
    dlg_add = RoomSetupDialog(blocks=blocks)
    dlg_add.show()
    app.processEvents()
    dlg_add.grab().save(str(out_dir / "add_room_dialog.png"))
    dlg_add.close()

    # 2. Edit Room Dialog
    room = {
        "id": "r101",
        "block": "A",
        "floor": 2,
        "number": "204",
        "capacity": 3,
        "gender": "male",
    }
    dlg_edit = RoomSetupDialog(room=room, current_occupancy=2, blocks=blocks)
    dlg_edit.show()
    app.processEvents()
    dlg_edit.grab().save(str(out_dir / "edit_room_dialog.png"))
    dlg_edit.close()

    print("Screenshots captured successfully.")

if __name__ == "__main__":
    main()
