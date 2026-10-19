"""Capture high-resolution screenshots of the RÉSIVO desktop console in offscreen mode.

Saves captured frames to docs/screenshots/desktop/.
"""

import os
import sys

# Ensure offscreen mode for Qt
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QApplication

# Add project root and desktop to path
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT_DIR)
sys.path.insert(0, os.path.join(ROOT_DIR, "desktop"))

from desktop.app.ui import theme
from desktop.app.ui.login_window import LoginWindow
from desktop.app.ui.main_window import MainWindow


class MockAuth:
    def get_session(self):
        class Session:
            class User:
                email = "admin@resivo.dz"
                user_metadata = {"full_name": "Dr. Amine Mansouri"}
            user = User()
        return Session()


class MockQuery:
    def __init__(self, name):
        self._name = name

    def select(self, *args, **kwargs):
        return self

    def order(self, *args, **kwargs):
        return self

    def eq(self, *args, **kwargs):
        return self

    def execute(self):
        class Response:
            data = []
        resp = Response()
        if self._name == "rooms":
            resp.data = [
                {"id": "r1", "block": "A", "floor": 0, "number": "02", "capacity": 3, "gender": "male"},
                {"id": "r2", "block": "A", "floor": 1, "number": "101", "capacity": 2, "gender": "male"},
                {"id": "r3", "block": "A", "floor": 1, "number": "102", "capacity": 2, "gender": "male"},
                {"id": "r4", "block": "B", "floor": 1, "number": "101", "capacity": 2, "gender": "female"},
                {"id": "r5", "block": "C", "floor": 1, "number": "5", "capacity": 2, "gender": "male"},
            ]
        return resp


class MockClient:
    auth = MockAuth()

    def table(self, name):
        return MockQuery(name)


def capture():
    os.makedirs("docs/screenshots/desktop", exist_ok=True)

    app = QApplication.instance() or QApplication(sys.argv)
    theme.load_fonts()

    # 1. Login Window
    print("Capturing Login Window...")
    login = LoginWindow()
    login.resize(1024, 640)
    login.show()
    app.processEvents()
    login.grab().save("docs/screenshots/desktop/login-split-1024.png")

    login.resize(420, 560)
    app.processEvents()
    login.grab().save("docs/screenshots/desktop/login-compact-420.png")
    login.close()
    app.processEvents()

    # 2. Main Window with mock client
    print("Capturing Main Window...")
    # Monkeypatch workers to avoid live network
    from desktop.app.ui.live_sync import LiveSyncWorker
    LiveSyncWorker.start = lambda self: None
    from desktop.app.ui.pages.settings import McpHealthWorker
    McpHealthWorker.start = lambda self: None
    from desktop.app import client as desktop_client
    desktop_client.room_occupancy = lambda c: {"r1": 1, "r2": 1, "r3": 0, "r4": 0, "r5": 0}
    from desktop.app.ui.pages import rooms as rooms_page_mod
    rooms_page_mod.room_occupancy = lambda c: {"r1": 1, "r2": 1, "r3": 0, "r4": 0, "r5": 0}

    client = MockClient()
    main = MainWindow(client)
    main.resize(1280, 800)
    main.show()
    app.processEvents()

    # Disconnect fade animation for crisp instant captures
    try:
        main.stack.currentChanged.disconnect(main._animate_stack_page)
    except Exception:
        pass
    for i in range(main.stack.count()):
        w = main.stack.widget(i)
        if w:
            w.setGraphicsEffect(None)

    page_names = [
        ("overview", 0),
        ("pending", 1),
        ("residents", 2),
        ("rooms", 3),
        ("maintenance", 4),
        ("room_changes", 5),
        ("official_list", 6),
        ("staff_accounts", 7),
        ("settings", 8),
    ]

    for name, idx in page_names:
        if idx < main.stack.count():
            main.nav.setCurrentRow(idx)
            app.processEvents()
            filename = f"docs/screenshots/desktop/{idx:02d}-{name}-1280.png"
            main.grab().save(filename)
            print(f"Saved {filename}")

    # Capture minimized sidebar state
    main.nav.setCurrentRow(0)
    main.toggle_sidebar()
    app.processEvents()
    minimized_filename = "docs/screenshots/desktop/00-overview-sidebar-minimized-1280.png"
    main.grab().save(minimized_filename)
    print(f"Saved {minimized_filename}")

    main.close()
    app.processEvents()
    print("All desktop screenshots captured successfully!")


if __name__ == "__main__":
    capture()
