# Staff Desktop App Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the PySide6 staff desktop console: staff login, overview counts, pending-account review with official-list comparison, approve/reject, residents list, room management, maintenance handling, room-change handling, official-list import, and staff-account management.

**Architecture:** A single PySide6 application using a `QMainWindow` with a left navigation list and a `QStackedWidget` of page widgets. All data access goes through the `supabase` Python client (anon key + staff login session). Sensitive writes call the RPC functions; staff creation calls the `admin-users` Edge Function. Uses the same Supabase backend as the website.

**Tech Stack:** Python 3.14, PySide6, `supabase` (supabase-py v2), `python-dotenv`, `openpyxl` (Excel import), `pytest`.

## Global Constraints

- Only the **anon key** is used; the service role key is never present in the desktop app.
- Staff authenticate with **email + password**; the client session's JWT is sent with every request and enforces RLS.
- UI text is English.
- Env vars required (in `desktop/.env`): `SUPABASE_URL`, `SUPABASE_ANON_KEY`.
- Windows shell (PowerShell); venv at `desktop/.venv`, activate with `desktop\.venv\Scripts\Activate.ps1`.
- RPCs: `approve_student(p_student, p_room)`, `reject_student(p_student, p_reason)`, `approve_room_change(p_request, p_room)`, `reject_room_change(p_request, p_reason)`, `import_official_residents(p_rows jsonb)`.
- Edge Function: `admin-users` with `{action:"create_staff"|"list_staff"}`.
- Storage bucket `maintenance-photos` is private; view photos via signed URLs.
- This plan depends on the backend plan being applied and seeded.

---

## File Structure

- `desktop/requirements.txt` — dependencies.
- `desktop/.env.example` — env template.
- `desktop/main.py` — entry point.
- `desktop/app/config.py` — env loading.
- `desktop/app/client.py` — Supabase client factory + sign-in + small query helpers.
- `desktop/app/ui/login_window.py` — staff login.
- `desktop/app/ui/main_window.py` — nav shell + page stack.
- `desktop/app/ui/pages/overview.py` — counts dashboard.
- `desktop/app/ui/pages/pending.py` — pending accounts + official comparison + approve/reject.
- `desktop/app/ui/pages/residents.py` — active residents list.
- `desktop/app/ui/pages/rooms.py` — room CRUD + occupancy.
- `desktop/app/ui/pages/maintenance.py` — maintenance handling.
- `desktop/app/ui/pages/room_changes.py` — room-change handling.
- `desktop/app/ui/pages/official_list.py` — import + browse official residents.
- `desktop/app/ui/pages/staff_accounts.py` — create/list staff (admin only).
- `desktop/app/importers/official_list.py` — read Excel/CSV → list of dict rows.
- `desktop/tests/test_importer.py` — importer unit tests.
- `desktop/tests/test_client.py` — integration smoke test (skipped without env).

---

## Task 1: Scaffold the desktop app

**Files:**
- Create: `desktop/requirements.txt`, `desktop/.env.example`, `desktop/main.py`, `desktop/app/__init__.py`, `desktop/app/ui/__init__.py`, `desktop/app/ui/pages/__init__.py`.

**Interfaces:**
- Consumes: nothing.
- Produces: a venv, dependencies installed, and `python main.py` opening an empty window.

- [ ] **Step 1: Write `desktop/requirements.txt`**

```text
PySide6==6.8.0.2
supabase==2.9.0
python-dotenv==1.0.1
openpyxl==3.1.5
pytest==8.3.3
```

- [ ] **Step 2: Write `desktop/.env.example`**

```dotenv
SUPABASE_URL=https://YOUR-PROJECT-ref.supabase.co
SUPABASE_ANON_KEY=your-anon-key
```

- [ ] **Step 3: Create the venv and install**

```powershell
python -m venv desktop/.venv
desktop\.venv\Scripts\Activate.ps1
pip install -r desktop/requirements.txt
```

- [ ] **Step 4: Write package markers and `desktop/main.py`**

`desktop/app/__init__.py`:
```python
```
`desktop/app/ui/__init__.py`:
```python
```
`desktop/app/ui/pages/__init__.py`:
```python
```

`desktop/main.py`:
```python
import sys
from PySide6.QtWidgets import QApplication, QLabel

def main() -> int:
    app = QApplication(sys.argv)
    label = QLabel("Residence Staff Console")
    label.resize(320, 120)
    label.show()
    return app.exec()

if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Run the smoke test**

```powershell
desktop\.venv\Scripts\Activate.ps1
python desktop/main.py
```
Expected: a small window titled "Residence Staff Console" appears; close it.

- [ ] **Step 6: Commit**

```powershell
git add desktop/
git commit -m "chore(desktop): scaffold pyside6 app with dependencies"
```

---

## Task 2: Config and Supabase client

**Files:**
- Create: `desktop/app/config.py`
- Create: `desktop/app/client.py`

**Interfaces:**
- Consumes: env from `desktop/.env`.
- Produces:
  - `make_client() -> Client`
  - `sign_in(client, email, password) -> AuthResponse`
  - `current_role(client) -> str | None`
  - `room_occupancy(client) -> dict[str, int]` (room id → count of active students)
  - `official_lookup(client) -> dict[str, dict]` (card_id → official row)

- [ ] **Step 1: Write `desktop/app/config.py`**

```python
import os
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_ANON_KEY = os.environ["SUPABASE_ANON_KEY"]
```

- [ ] **Step 2: Write `desktop/app/client.py`**

```python
from supabase import create_client, Client
from .config import SUPABASE_URL, SUPABASE_ANON_KEY


def make_client() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_ANON_KEY)


def sign_in(client: Client, email: str, password: str):
    return client.auth.sign_in_with_password({"email": email, "password": password})


def current_role(client: Client) -> str | None:
    user = client.auth.get_user().user
    if not user:
        return None
    resp = client.table("profiles").select("role").eq("id", user.id).single().execute()
    return (resp.data or {}).get("role")


def room_occupancy(client: Client) -> dict[str, int]:
    resp = client.table("students").select("room_id").eq("status", "active").execute()
    counts: dict[str, int] = {}
    for row in resp.data or []:
        rid = row["room_id"]
        if rid:
            counts[rid] = counts.get(rid, 0) + 1
    return counts


def official_lookup(client: Client) -> dict[str, dict]:
    resp = client.table("official_residents").select("*").execute()
    return {r["card_id"]: r for r in (resp.data or [])}
```

- [ ] **Step 3: Verify imports load**

```powershell
desktop\.venv\Scripts\Activate.ps1
Copy-Item desktop/.env.example desktop/.env
# edit desktop/.env with real values
python -c "from app.client import make_client; print('ok')" --  # run from desktop/
```
Run the command from the `desktop` directory:
```powershell
python -c "from app.client import make_client; print('ok')"
```
Expected: prints `ok`.

- [ ] **Step 4: Commit**

```powershell
git add desktop/app/config.py desktop/app/client.py desktop/.env.example
git commit -m "feat(desktop): add config and supabase client helpers"
```

---

## Task 3: Login window

**Files:**
- Create: `desktop/app/ui/login_window.py`
- Modify: `desktop/main.py`

**Interfaces:**
- Consumes: `make_client`, `sign_in`.
- Produces: `LoginWindow(QWidget)` that on success constructs and shows `MainWindow` (Task 4), then closes itself.

- [ ] **Step 1: Write `desktop/app/ui/login_window.py`**

```python
from PySide6.QtWidgets import (
    QWidget, QFormLayout, QLineEdit, QPushButton, QLabel, QVBoxLayout, QMessageBox,
)
from ..client import make_client, sign_in


class LoginWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Staff Login — Residence Tlemcen")
        self.client = make_client()

        self.email = QLineEdit()
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.Password)

        form = QFormLayout()
        form.addRow("Email", self.email)
        form.addRow("Password", self.password)

        self.button = QPushButton("Log in")
        self.button.clicked.connect(self.attempt)

        self.status = QLabel("")
        self.status.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.button)
        layout.addWidget(self.status)
        self.resize(380, 200)

    def attempt(self):
        try:
            sign_in(self.client, self.email.text().strip(), self.password.text())
        except Exception as exc:  # noqa: BLE001
            self.status.setText(f"Login failed: {exc}")
            return
        from .main_window import MainWindow
        self.window = MainWindow(self.client)
        self.window.show()
        self.close()
```

- [ ] **Step 2: Update `desktop/main.py`**

```python
import sys
from PySide6.QtWidgets import QApplication
from app.ui.login_window import LoginWindow


def main() -> int:
    app = QApplication(sys.argv)
    window = LoginWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 3: Verify login works**

Run `python desktop/main.py` (from repo root with venv active); log in with the seeded staff (`staff@residence.test` / `Staff1234!`). It will attempt to open `MainWindow` (created next task); until then it raises an import error — proceed to Task 4 before testing, or temporarily expect an error dialog.

- [ ] **Step 4: Commit**

```powershell
git add desktop/app/ui/login_window.py desktop/main.py
git commit -m "feat(desktop): add staff login window"
```

---

## Task 4: Main window shell, navigation, and overview

**Files:**
- Create: `desktop/app/ui/main_window.py`
- Create: `desktop/app/ui/pages/overview.py`

**Interfaces:**
- Consumes: `make_client`, `current_role`.
- Produces:
  - `MainWindow(QMainWindow)` with a nav list and `QStackedWidget`; pages are added in later tasks. It only adds `OverviewPage` now, plus placeholder sections that later tasks replace.
  - `OverviewPage(QWidget)` showing counts of pending accounts, open reports, pending requests, and total occupancy.

- [ ] **Step 1: Write `desktop/app/ui/pages/overview.py`**

```python
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton
from ...client import room_occupancy


class OverviewPage(QWidget):
    def __init__(self, client):
        super().__init__()
        self.client = client
        self.labels: dict[str, QLabel] = {}

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<h2>Overview</h2>", textFormat=1))
        for key, title in [
            ("pending", "Pending accounts"),
            ("reports", "Open maintenance reports"),
            ("requests", "Pending room-change requests"),
            ("occupancy", "Total residents (active)"),
        ]:
            row = QLabel(f"{title}: —")
            self.labels[key] = row
            layout.addWidget(row)

        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self.reload)
        layout.addWidget(refresh)
        layout.addStretch(1)

    def _count(self, table, **filters) -> int:
        q = self.client.table(table).select("id", count="exact")
        for col, val in filters.items():
            q = q.eq(col, val)
        return q.execute().count or 0

    def reload(self):
        pending = self._count("students", status="pending")
        reports = self._count("maintenance_reports", status="pending")
        requests = self._count("room_change_requests", status="pending")
        occupancy = sum(room_occupancy(self.client).values())
        self.labels["pending"].setText(f"Pending accounts: {pending}")
        self.labels["reports"].setText(f"Open maintenance reports: {reports}")
        self.labels["requests"].setText(f"Pending room-change requests: {requests}")
        self.labels["occupancy"].setText(f"Total residents (active): {occupancy}")
```

- [ ] **Step 2: Write `desktop/app/ui/main_window.py`** (pages for later tasks are added with the same pattern; only Overview exists now)

```python
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QListWidget, QStackedWidget,
)
from ..client import current_role
from .pages.overview import OverviewPage


class MainWindow(QMainWindow):
    def __init__(self, client):
        super().__init__()
        self.client = client
        self.role = current_role(client)
        self.setWindowTitle("Residence Staff Console — Tlemcen")
        self.resize(1000, 680)

        self.nav = QListWidget()
        self.nav.setFixedWidth(200)
        self.stack = QStackedWidget()

        self.pages: dict[str, QWidget] = {}
        self._add_page("Overview", OverviewPage(client))

        # Later tasks append more pages via self._add_page(...).

        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex)

        container = QWidget()
        layout = QHBoxLayout(container)
        layout.addWidget(self.nav)
        layout.addWidget(self.stack, 1)
        self.setCentralWidget(container)

        self.nav.setCurrentRow(0)

    def _add_page(self, title: str, widget: QWidget):
        self.pages[title] = widget
        self.nav.addItem(title)
        self.stack.addWidget(widget)
```

- [ ] **Step 3: Verify**

Run the app, log in as staff, confirm the Overview shows counts (Seed values: 1 pending account, 0 open reports, 0 pending requests, up to 1 resident).

- [ ] **Step 4: Commit**

```powershell
git add desktop/app/ui/main_window.py desktop/app/ui/pages/overview.py
git commit -m "feat(desktop): add main window shell and overview page"
```

---

## Task 5: Pending accounts (compare + approve/reject)

**Files:**
- Create: `desktop/app/ui/pages/pending.py`
- Modify: `desktop/app/ui/main_window.py` (add the page)

**Interfaces:**
- Consumes: `official_lookup`, `room_occupancy`, RPCs `approve_student`, `reject_student`.
- Produces: `PendingPage(QWidget)` with a table of pending students, a detail panel showing the official-list match status, and Approve (room picker) / Reject (reason) actions.

- [ ] **Step 1: Write `desktop/app/ui/pages/pending.py`**

```python
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QInputDialog, QMessageBox, QTextEdit,
)
from ...client import room_occupancy, official_lookup


class PendingPage(QWidget):
    def __init__(self, client):
        super().__init__()
        self.client = client
        self.rows: list[dict] = []

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Card ID", "Name", "Gender", "Official list", "Requested"])
        self.table.itemSelectionChanged.connect(self.show_detail)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)

        self.detail = QTextEdit()
        self.detail.setReadOnly(True)

        self.approve = QPushButton("Approve")
        self.approve.clicked.connect(self.on_approve)
        self.reject = QPushButton("Reject")
        self.reject.clicked.connect(self.on_reject)

        actions = QHBoxLayout()
        actions.addWidget(self.approve)
        actions.addWidget(self.reject)
        actions.addStretch(1)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<h2>Pending accounts</h2>", textFormat=1))
        layout.addWidget(self.table)
        layout.addWidget(self.detail)
        layout.addLayout(actions)

        self.reload()

    def reload(self):
        resp = self.client.table("students").select("*").eq("status", "pending").execute()
        self.rows = resp.data or []
        self.official = official_lookup(self.client)
        self.table.setRowCount(len(self.rows))
        for i, s in enumerate(self.rows):
            match = "match" if s["card_id"] in self.official else "no match"
            self.table.setItem(i, 0, QTableWidgetItem(s["card_id"]))
            self.table.setItem(i, 1, QTableWidgetItem(f"{s['first_name']} {s['last_name']}"))
            self.table.setItem(i, 2, QTableWidgetItem(s["gender"]))
            self.table.setItem(i, 3, QTableWidgetItem(match))
            self.table.setItem(i, 4, QTableWidgetItem(s["created_at"]))

    def selected(self) -> dict | None:
        r = self.table.currentRow()
        return self.rows[r] if 0 <= r < len(self.rows) else None

    def show_detail(self):
        s = self.selected()
        if not s:
            return
        o = self.official.get(s["card_id"])
        official = (
            f"MATCH with official record:\n  {o['first_name']} {o['last_name']}, "
            f"{o.get('birth_date') or '—'}, {o.get('gender') or '—'}"
            if o else "NO MATCH in official list."
        )
        self.detail.setPlainText(
            f"Card ID: {s['card_id']}\n"
            f"Name: {s['first_name']} {s['last_name']}\n"
            f"Birth date: {s['birth_date']}\n"
            f"Gender: {s['gender']}\n"
            f"Phone: {s['phone']}\n"
            f"Email: {s['email'] or '—'}\n"
            f"University: {s['university']} / {s['faculty']}\n"
            f"Study level: {s['study_level']} | Wilaya: {s['wilaya']}\n\n"
            f"{official}"
        )

    def on_approve(self):
        s = self.selected()
        if not s:
            return
        rooms = self.client.table("rooms").select("id, block, number, capacity, gender") \
            .eq("gender", s["gender"]).execute().data or []
        occ = room_occupancy(self.client)
        options = []
        for r in rooms:
            free = r["capacity"] - occ.get(r["id"], 0)
            options.append(f"Block {r['block']} — {r['number']} ({free} free) | id={r['id']}")
        if not options:
            QMessageBox.warning(self, "No rooms", "No rooms available for this gender.")
            return
        choice, ok = QInputDialog.getItem(self, "Assign room", "Room:", options, 0, False)
        if not ok:
            return
        room_id = choice.split("id=")[1].strip()
        try:
            self.client.rpc("approve_student", {"p_student": s["id"], "p_room": room_id}).execute()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Error", str(exc))
            return
        QMessageBox.information(self, "Approved", f"{s['first_name']} {s['last_name']} approved.")
        self.reload()

    def on_reject(self):
        s = self.selected()
        if not s:
            return
        reason, ok = QInputDialog.getMultiLineText(self, "Reject", "Reason for rejection:")
        if not ok or not reason.strip():
            return
        try:
            self.client.rpc("reject_student", {"p_student": s["id"], "p_reason": reason.strip()}).execute()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Error", str(exc))
            return
        self.reload()
```

- [ ] **Step 2: Register the page in `main_window.py`**

Add the import and page registration:
```python
from .pages.pending import PendingPage
```
and, right after the Overview registration:
```python
        self._add_page("Pending accounts", PendingPage(client))
```

- [ ] **Step 3: Verify**

Log in as staff; the seeded pending student appears with `match` (card `20230001`). Approve into a male room → the student becomes active and disappears from the list (overview pending count drops).

- [ ] **Step 4: Commit**

```powershell
git add desktop/app/ui/pages/pending.py desktop/app/ui/main_window.py
git commit -m "feat(desktop): add pending accounts with official comparison and approve/reject"
```

---

## Task 6: Residents page

**Files:**
- Create: `desktop/app/ui/pages/residents.py`
- Modify: `desktop/app/ui/main_window.py`

**Interfaces:**
- Consumes: `students` + `rooms`.
- Produces: `ResidentsPage(QWidget)` listing active students with their room and a search box.

- [ ] **Step 1: Write `desktop/app/ui/pages/residents.py`**

```python
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLineEdit, QTableWidget, QTableWidgetItem, QLabel,
)


class ResidentsPage(QWidget):
    def __init__(self, client):
        super().__init__()
        self.client = client
        self.rows: list[dict] = []

        self.search = QLineEdit()
        self.search.setPlaceholderText("Search by name or card ID…")
        self.search.textChanged.connect(self.render)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Card ID", "Name", "Gender", "Room", "Status"])

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<h2>Residents</h2>", textFormat=1))
        layout.addWidget(self.search)
        layout.addWidget(self.table)

        self.reload()

    def reload(self):
        resp = self.client.table("students") \
            .select("card_id, first_name, last_name, gender, status, rooms(block, number)") \
            .eq("status", "active").execute()
        self.rows = resp.data or []
        self.render()

    def render(self):
        needle = self.search.text().lower().strip()
        filtered = [
            r for r in self.rows
            if needle in f"{r['first_name']} {r['last_name']} {r['card_id']}".lower()
        ]
        self.table.setRowCount(len(filtered))
        for i, r in enumerate(filtered):
            room = r.get("rooms") or {}
            self.table.setItem(i, 0, QTableWidgetItem(r["card_id"]))
            self.table.setItem(i, 1, QTableWidgetItem(f"{r['first_name']} {r['last_name']}"))
            self.table.setItem(i, 2, QTableWidgetItem(r["gender"]))
            self.table.setItem(i, 3, QTableWidgetItem(f"{room.get('block','—')} / {room.get('number','—')}"))
            self.table.setItem(i, 4, QTableWidgetItem(r["status"]))
```

- [ ] **Step 2: Register in `main_window.py`**

```python
from .pages.residents import ResidentsPage
```
```python
        self._add_page("Residents", ResidentsPage(client))
```

- [ ] **Step 3: Verify** — the approved student appears; searching by their name filters the table.

- [ ] **Step 4: Commit**

```powershell
git add desktop/app/ui/pages/residents.py desktop/app/ui/main_window.py
git commit -m "feat(desktop): add residents page"
```

---

## Task 7: Rooms page

**Files:**
- Create: `desktop/app/ui/pages/rooms.py`
- Modify: `desktop/app/ui/main_window.py`

**Interfaces:**
- Consumes: `rooms`, `room_occupancy`.
- Produces: `RoomsPage(QWidget)` with a table (block, floor, number, capacity, gender, occupied) and Add/Edit/Delete.

- [ ] **Step 1: Write `desktop/app/ui/pages/rooms.py`**

```python
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QInputDialog, QMessageBox,
)
from ...client import room_occupancy


class RoomsPage(QWidget):
    def __init__(self, client):
        super().__init__()
        self.client = client
        self.rows: list[dict] = []

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Block", "Floor", "Number", "Capacity", "Gender", "Occupied"])
        self.table.setSelectionBehavior(QTableWidget.SelectRows)

        add = QPushButton("Add room")
        add.clicked.connect(self.on_add)
        edit = QPushButton("Edit room")
        edit.clicked.connect(self.on_edit)
        delete = QPushButton("Delete room")
        delete.clicked.connect(self.on_delete)
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self.reload)

        actions = QHBoxLayout()
        for b in (add, edit, delete, refresh):
            actions.addWidget(b)
        actions.addStretch(1)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<h2>Rooms</h2>", textFormat=1))
        layout.addWidget(self.table)
        layout.addLayout(actions)

        self.reload()

    def reload(self):
        self.rows = self.client.table("rooms").select("*").order("block").order("number").execute().data or []
        occ = room_occupancy(self.client)
        self.table.setRowCount(len(self.rows))
        for i, r in enumerate(self.rows):
            self.table.setItem(i, 0, QTableWidgetItem(r["block"]))
            self.table.setItem(i, 1, QTableWidgetItem(str(r["floor"])))
            self.table.setItem(i, 2, QTableWidgetItem(r["number"]))
            self.table.setItem(i, 3, QTableWidgetItem(str(r["capacity"])))
            self.table.setItem(i, 4, QTableWidgetItem(r["gender"]))
            self.table.setItem(i, 5, QTableWidgetItem(str(occ.get(r["id"], 0))))

    def _prompt(self, block="", floor="0", number="", capacity="1", gender="male"):
        block, ok = QInputDialog.getText(self, "Room", "Block:", text=block)
        if not ok:
            return None
        floor_s, ok = QInputDialog.getText(self, "Room", "Floor:", text=floor)
        if not ok:
            return None
        number, ok = QInputDialog.getText(self, "Room", "Number:", text=number)
        if not ok:
            return None
        cap_s, ok = QInputDialog.getText(self, "Room", "Capacity:", text=capacity)
        if not ok:
            return None
        gender_idx = 0 if gender == "male" else 1
        gender, ok = QInputDialog.getItem(self, "Room", "Gender:", ["male", "female"], gender_idx, False)
        if not ok:
            return None
        return {
            "block": block.strip(), "floor": int(floor_s or 0), "number": number.strip(),
            "capacity": int(cap_s or 1), "gender": gender,
        }

    def on_add(self):
        data = self._prompt()
        if not data:
            return
        try:
            self.client.table("rooms").insert(data).execute()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Error", str(exc))
        self.reload()

    def on_edit(self):
        r = self.table.currentRow()
        if r < 0:
            return
        room = self.rows[r]
        data = self._prompt(room["block"], str(room["floor"]), room["number"], str(room["capacity"]), room["gender"])
        if not data:
            return
        try:
            self.client.table("rooms").update(data).eq("id", room["id"]).execute()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Error", str(exc))
        self.reload()

    def on_delete(self):
        r = self.table.currentRow()
        if r < 0:
            return
        room = self.rows[r]
        confirm = QMessageBox.question(self, "Delete", f"Delete room {room['block']}-{room['number']}?")
        if confirm != QMessageBox.Yes:
            return
        try:
            self.client.table("rooms").delete().eq("id", room["id"]).execute()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Error", str(exc))
        self.reload()
```

- [ ] **Step 2: Register in `main_window.py`**

```python
from .pages.rooms import RoomsPage
```
```python
        self._add_page("Rooms", RoomsPage(client))
```

- [ ] **Step 3: Verify** — add a room, edit it, delete it; occupancy column reflects active residents.

- [ ] **Step 4: Commit**

```powershell
git add desktop/app/ui/pages/rooms.py desktop/app/ui/main_window.py
git commit -m "feat(desktop): add rooms management page"
```

---

## Task 8: Maintenance page

**Files:**
- Create: `desktop/app/ui/pages/maintenance.py`
- Modify: `desktop/app/ui/main_window.py`

**Interfaces:**
- Consumes: `maintenance_reports` (+ students), Storage signed URLs.
- Produces: `MaintenancePage(QWidget)` listing reports; selecting a row shows the description/photo; buttons to set status (`in_progress` / `resolved`) with a staff note.

- [ ] **Step 1: Write `desktop/app/ui/pages/maintenance.py`**

```python
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QTextEdit, QInputDialog, QMessageBox,
)
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt


class MaintenancePage(QWidget):
    def __init__(self, client):
        super().__init__()
        self.client = client
        self.rows: list[dict] = []

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Category", "Student", "Status", "Created"])
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.itemSelectionChanged.connect(self.show_detail)

        self.detail = QTextEdit()
        self.detail.setReadOnly(True)
        self.photo = QLabel()
        self.photo.setAlignment(Qt.AlignCenter)
        self.photo.setMinimumHeight(200)

        in_progress = QPushButton("Mark in progress")
        in_progress.clicked.connect(lambda: self.set_status("in_progress"))
        resolved = QPushButton("Mark resolved")
        resolved.clicked.connect(lambda: self.set_status("resolved"))
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self.reload)

        actions = QHBoxLayout()
        for b in (in_progress, resolved, refresh):
            actions.addWidget(b)
        actions.addStretch(1)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<h2>Maintenance reports</h2>", textFormat=1))
        layout.addWidget(self.table)
        layout.addWidget(self.detail)
        layout.addWidget(self.photo)
        layout.addLayout(actions)

        self.reload()

    def reload(self):
        self.rows = self.client.table("maintenance_reports") \
            .select("*, students(first_name, last_name, card_id)") \
            .order("created_at", desc=True).execute().data or []
        self.table.setRowCount(len(self.rows))
        for i, r in enumerate(self.rows):
            st = r.get("students") or {}
            self.table.setItem(i, 0, QTableWidgetItem(r["category"]))
            self.table.setItem(i, 1, QTableWidgetItem(f"{st.get('first_name','')} {st.get('last_name','')}"))
            self.table.setItem(i, 2, QTableWidgetItem(r["status"]))
            self.table.setItem(i, 3, QTableWidgetItem(r["created_at"]))

    def selected(self) -> dict | None:
        r = self.table.currentRow()
        return self.rows[r] if 0 <= r < len(self.rows) else None

    def show_detail(self):
        r = self.selected()
        if not r:
            return
        self.detail.setPlainText(f"{r['description']}\n\nStaff note: {r.get('staff_note') or '—'}")
        self.photo.clear()
        if r.get("photo_path"):
            signed = self.client.storage.from_("maintenance-photos").create_signed_url(r["photo_path"], 300)
            url = (signed or {}).get("signedURL") or (signed or {}).get("signedUrl")
            if url:
                import urllib.request
                data = urllib.request.urlopen(url).read()
                pix = QPixmap()
                pix.loadFromData(data)
                self.photo.setPixmap(pix.scaledToWidth(400, Qt.SmoothTransformation))

    def set_status(self, status: str):
        r = self.selected()
        if not r:
            return
        note, ok = QInputDialog.getMultiLineText(self, "Staff note", "Note (optional):")
        if not ok:
            return
        try:
            self.client.table("maintenance_reports") \
                .update({"status": status, "staff_note": note or None}) \
                .eq("id", r["id"]).execute()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Error", str(exc))
        self.reload()
```

- [ ] **Step 2: Register in `main_window.py`**

```python
from .pages.maintenance import MaintenancePage
```
```python
        self._add_page("Maintenance", MaintenancePage(client))
```

- [ ] **Step 3: Verify** — the report submitted from the website appears; mark it `in_progress` then `resolved`; the photo loads.

- [ ] **Step 4: Commit**

```powershell
git add desktop/app/ui/pages/maintenance.py desktop/app/ui/main_window.py
git commit -m "feat(desktop): add maintenance handling page"
```

---

## Task 9: Room-change requests page

**Files:**
- Create: `desktop/app/ui/pages/room_changes.py`
- Modify: `desktop/app/ui/main_window.py`

**Interfaces:**
- Consumes: `room_change_requests`, `room_occupancy`, RPCs `approve_room_change`, `reject_room_change`.
- Produces: `RoomChangesPage(QWidget)` listing requests with approve (room picker) / reject (reason).

- [ ] **Step 1: Write `desktop/app/ui/pages/room_changes.py`**

```python
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QInputDialog, QMessageBox,
)
from ...client import room_occupancy


class RoomChangesPage(QWidget):
    def __init__(self, client):
        super().__init__()
        self.client = client
        self.rows: list[dict] = []

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Student", "Status", "Reason"])
        self.table.setSelectionBehavior(QTableWidget.SelectRows)

        approve = QPushButton("Approve")
        approve.clicked.connect(self.on_approve)
        reject = QPushButton("Reject")
        reject.clicked.connect(self.on_reject)
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self.reload)

        actions = QHBoxLayout()
        for b in (approve, reject, refresh):
            actions.addWidget(b)
        actions.addStretch(1)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<h2>Room-change requests</h2>", textFormat=1))
        layout.addWidget(self.table)
        layout.addLayout(actions)

        self.reload()

    def reload(self):
        self.rows = self.client.table("room_change_requests") \
            .select("*, students(first_name, last_name, gender)") \
            .eq("status", "pending").order("created_at", desc=True).execute().data or []
        self.table.setRowCount(len(self.rows))
        for i, r in enumerate(self.rows):
            st = r.get("students") or {}
            self.table.setItem(i, 0, QTableWidgetItem(f"{st.get('first_name','')} {st.get('last_name','')}"))
            self.table.setItem(i, 1, QTableWidgetItem(r["status"]))
            self.table.setItem(i, 2, QTableWidgetItem(r["reason"]))

    def selected(self) -> dict | None:
        r = self.table.currentRow()
        return self.rows[r] if 0 <= r < len(self.rows) else None

    def on_approve(self):
        r = self.selected()
        if not r:
            return
        gender = (r.get("students") or {}).get("gender", "male")
        rooms = self.client.table("rooms").select("id, block, number, capacity, gender") \
            .eq("gender", gender).execute().data or []
        occ = room_occupancy(self.client)
        options = [
            f"Block {room['block']} — {room['number']} "
            f"({room['capacity'] - occ.get(room['id'], 0)} free) | id={room['id']}"
            for room in rooms
        ]
        if not options:
            QMessageBox.warning(self, "No rooms", "No rooms available for this gender.")
            return
        choice, ok = QInputDialog.getItem(self, "Assign room", "New room:", options, 0, False)
        if not ok:
            return
        room_id = choice.split("id=")[1].strip()
        try:
            self.client.rpc("approve_room_change", {"p_request": r["id"], "p_room": room_id}).execute()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Error", str(exc))
        self.reload()

    def on_reject(self):
        r = self.selected()
        if not r:
            return
        reason, ok = QInputDialog.getMultiLineText(self, "Reject", "Reason:")
        if not ok or not reason.strip():
            return
        try:
            self.client.rpc("reject_room_change", {"p_request": r["id"], "p_reason": reason.strip()}).execute()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Error", str(exc))
        self.reload()
```

- [ ] **Step 2: Register in `main_window.py`**

```python
from .pages.room_changes import RoomChangesPage
```
```python
        self._add_page("Room changes", RoomChangesPage(client))
```

- [ ] **Step 3: Verify** — the request submitted on the website appears; approving reassigns the student's room; rejecting stores a decision note.

- [ ] **Step 4: Commit**

```powershell
git add desktop/app/ui/pages/room_changes.py desktop/app/ui/main_window.py
git commit -m "feat(desktop): add room-change handling page"
```

---

## Task 10: Official-list import

**Files:**
- Create: `desktop/app/importers/__init__.py`, `desktop/app/importers/official_list.py`
- Create: `desktop/tests/test_importer.py`
- Create: `desktop/app/ui/pages/official_list.py`
- Modify: `desktop/app/ui/main_window.py`

**Interfaces:**
- Consumes: RPC `import_official_residents(p_rows jsonb)`.
- Produces:
  - `read_official_file(path) -> list[dict]` (Excel `.xlsx` or CSV; columns: `card_id, first_name, last_name, birth_date, gender, university, faculty`).
  - `OfficialListPage(QWidget)` with an Import button and a browse table.

- [ ] **Step 1: Write `desktop/app/importers/official_list.py`**

```python
import csv
from openpyxl import load_workbook

COLUMNS = ["card_id", "first_name", "last_name", "birth_date", "gender", "university", "faculty"]


def read_official_file(path: str) -> list[dict]:
    if path.lower().endswith(".csv"):
        with open(path, newline="", encoding="utf-8-sig") as fh:
            rows = list(csv.DictReader(fh))
    else:
        wb = load_workbook(path, read_only=True, data_only=True)
        ws = wb.active
        header = [str(c.value).strip() if c.value is not None else "" for c in next(ws.iter_rows(min_row=1, max_row=1))]
        rows = []
        for row in ws.iter_rows(min_row=2, values_only=True):
            rows.append({header[i]: row[i] for i in range(min(len(header), len(row)))})

    cleaned: list[dict] = []
    for r in rows:
        card = str(r.get("card_id") or "").strip()
        if not card:
            continue
        cleaned.append({
            "card_id": card,
            "first_name": str(r.get("first_name") or "").strip(),
            "last_name": str(r.get("last_name") or "").strip(),
            "birth_date": str(r.get("birth_date") or "").strip() or None,
            "gender": (str(r.get("gender") or "").strip().lower() or None),
            "university": str(r.get("university") or "").strip() or None,
            "faculty": str(r.get("faculty") or "").strip() or None,
        })
    return cleaned
```

Add `desktop/app/importers/__init__.py` (empty).

- [ ] **Step 2: Write `desktop/tests/test_importer.py`**

```python
import csv
import os
from app.importers.official_list import read_official_file


def test_read_csv(tmp_path):
    path = tmp_path / "list.csv"
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["card_id", "first_name", "last_name", "birth_date", "gender", "university", "faculty"])
        w.writerow(["20230001", "Yacine", "Benali", "2003-05-14", "male", "UBB", "Sciences"])
        w.writerow(["", "Ignored", "Row", "", "", "", ""])
    rows = read_official_file(str(path))
    assert len(rows) == 1
    assert rows[0]["card_id"] == "20230001"
    assert rows[0]["gender"] == "male"
```

- [ ] **Step 3: Run the unit tests**

```powershell
desktop\.venv\Scripts\Activate.ps1
python -m pytest desktop/tests/test_importer.py -v
```
Expected: 1 test passes.

- [ ] **Step 4: Write `desktop/app/ui/pages/official_list.py`**

```python
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QFileDialog, QMessageBox,
)
from ...importers.official_list import read_official_file


class OfficialListPage(QWidget):
    def __init__(self, client):
        super().__init__()
        self.client = client

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            ["Card ID", "First", "Last", "Birth date", "Gender", "University", "Faculty"]
        )

        import_btn = QPushButton("Import Excel/CSV…")
        import_btn.clicked.connect(self.on_import)
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self.reload)

        actions = QHBoxLayout()
        actions.addWidget(import_btn)
        actions.addWidget(refresh)
        actions.addStretch(1)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<h2>Official residents list</h2>", textFormat=1))
        layout.addWidget(self.table)
        layout.addLayout(actions)

        self.reload()

    def reload(self):
        rows = self.client.table("official_residents").select("*").order("card_id").execute().data or []
        self.table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            for c, key in enumerate(["card_id", "first_name", "last_name", "birth_date", "gender", "university", "faculty"]):
                self.table.setItem(i, c, QTableWidgetItem(str(r.get(key) or "")))

    def on_import(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open official list", "", "Spreadsheets (*.xlsx *.csv)")
        if not path:
            return
        try:
            rows = read_official_file(path)
            self.client.rpc("import_official_residents", {"p_rows": rows}).execute()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Import error", str(exc))
            return
        QMessageBox.information(self, "Imported", f"Imported {len(rows)} rows.")
        self.reload()
```

- [ ] **Step 5: Register in `main_window.py`**

```python
from .pages.official_list import OfficialListPage
```
```python
        self._add_page("Official list", OfficialListPage(client))
```

- [ ] **Step 6: Verify** — import a CSV with a few rows; they appear in the table and in the DB.

- [ ] **Step 7: Commit**

```powershell
git add desktop/app/importers desktop/tests/test_importer.py desktop/app/ui/pages/official_list.py desktop/app/ui/main_window.py
git commit -m "feat(desktop): add official list import and browsing"
```

---

## Task 11: Staff accounts page (admin only)

**Files:**
- Create: `desktop/app/ui/pages/staff_accounts.py`
- Modify: `desktop/app/ui/main_window.py`

**Interfaces:**
- Consumes: Edge Function `admin-users` (`create_staff`, `list_staff`).
- Produces: `StaffAccountsPage(QWidget)` showing staff list and a Create form. Hidden when the logged-in role is not `admin`.

- [ ] **Step 1: Write `desktop/app/ui/pages/staff_accounts.py`**

```python
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit,
    QPushButton, QLabel, QTableWidget, QTableWidgetItem, QMessageBox,
)


class StaffAccountsPage(QWidget):
    def __init__(self, client):
        super().__init__()
        self.client = client

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Name", "Position", "ID"])

        self.email = QLineEdit()
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.Password)
        self.full_name = QLineEdit()
        self.position = QLineEdit()

        form = QFormLayout()
        form.addRow("Email", self.email)
        form.addRow("Password", self.password)
        form.addRow("Full name", self.full_name)
        form.addRow("Position", self.position)

        create = QPushButton("Create staff account")
        create.clicked.connect(self.on_create)
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self.reload)

        actions = QHBoxLayout()
        actions.addWidget(create)
        actions.addWidget(refresh)
        actions.addStretch(1)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<h2>Staff accounts</h2>", textFormat=1))
        layout.addWidget(self.table)
        layout.addLayout(form)
        layout.addLayout(actions)

        self.reload()

    def reload(self):
        try:
            resp = self.client.functions.invoke("admin-users", invoke_options={"body": {"action": "list_staff"}})
            rows = resp or []
        except Exception as exc:  # noqa: BLE001
            rows = []
            QMessageBox.warning(self, "Error", str(exc))
        self.table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            self.table.setItem(i, 0, QTableWidgetItem(r.get("full_name", "")))
            self.table.setItem(i, 1, QTableWidgetItem(r.get("position") or ""))
            self.table.setItem(i, 2, QTableWidgetItem(r.get("id", "")))

    def on_create(self):
        body = {
            "action": "create_staff",
            "email": self.email.text().strip(),
            "password": self.password.text(),
            "full_name": self.full_name.text().strip(),
            "position": self.position.text().strip(),
        }
        if not (body["email"] and body["password"] and body["full_name"]):
            QMessageBox.warning(self, "Missing data", "Email, password and full name are required.")
            return
        try:
            self.client.functions.invoke("admin-users", invoke_options={"body": body})
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Error", str(exc))
            return
        QMessageBox.information(self, "Created", "Staff account created.")
        self.reload()
```

- [ ] **Step 2: Register in `main_window.py`** — only when the role is admin

```python
from .pages.staff_accounts import StaffAccountsPage
```
```python
        if self.role == "admin":
            self._add_page("Staff accounts", StaffAccountsPage(client))
```

- [ ] **Step 3: Verify** — log in as `admin@residence.test` / `Admin1234!`; create a new staff account; it appears in the list and can log in.

- [ ] **Step 4: Commit**

```powershell
git add desktop/app/ui/pages/staff_accounts.py desktop/app/ui/main_window.py
git commit -m "feat(desktop): add admin-only staff accounts page"
```

---

## Task 12: Client integration test + manual checklist

**Files:**
- Create: `desktop/tests/test_client.py`
- Create: `docs/manual-test-desktop.md`

**Interfaces:**
- Consumes: `make_client`, `sign_in`, `current_role`.
- Produces: an integration test (skipped when env or creds are absent) and a manual checklist.

- [ ] **Step 1: Write `desktop/tests/test_client.py`**

```python
import os
import pytest
from app.client import make_client, sign_in, current_role


pytestmark = pytest.mark.skipif(
    not os.environ.get("SUPABASE_URL"), reason="SUPABASE_URL not set"
)


def test_staff_sign_in_and_role():
    client = make_client()
    sign_in(client, "staff@residence.test", "Staff1234!")
    assert current_role(client) == "staff"
```

- [ ] **Step 2: Run the integration test**

```powershell
desktop\.venv\Scripts\Activate.ps1
$env:SUPABASE_URL="https://YOUR-PROJECT-ref.supabase.co"
$env:SUPABASE_ANON_KEY="your-anon-key"
python -m pytest desktop/tests -v
```
Expected: importer test passes; integration test passes (or is skipped if env is unset).

- [ ] **Step 3: Write `docs/manual-test-desktop.md`**

```markdown
# Desktop manual test checklist

Prereqs: backend applied + seeded; `desktop/.env` set; venv active; `python desktop/main.py`.

- [ ] Wrong credentials → login shows an error and stays open.
- [ ] Staff login → main window with Overview counts.
- [ ] Pending accounts: seeded student shows "match"; approve into a male room → status active.
- [ ] Pending accounts: reject → student gets a rejection reason (verify on the website).
- [ ] Residents: approved student listed with room; search filters.
- [ ] Rooms: add/edit/delete a room; occupancy column correct.
- [ ] Maintenance: submit a report on the website → appears here; mark in progress then resolved; photo loads.
- [ ] Room changes: submit on the website → appears here; approve reassigns the room; reject stores a note.
- [ ] Official list: import a CSV → rows appear.
- [ ] Staff accounts (admin): create a staff account → list updates; new account can log in.
- [ ] Non-admin login → "Staff accounts" page is absent.
```

- [ ] **Step 4: Run through the checklist once and confirm every item passes.**

- [ ] **Step 5: Commit**

```powershell
git add desktop/tests/test_client.py docs/manual-test-desktop.md
git commit -m "test(desktop): add integration test and manual checklist"
```

---

## Self-Review

**Spec coverage:**
- Staff login (email + password) — Task 3. ✅
- Overview counts (pending accounts, open reports, pending requests, occupancy) — Task 4. ✅
- Pending accounts with official-list comparison + approve (room picker) / reject (reason) — Task 5. ✅
- Residents list with search — Task 6. ✅
- Rooms CRUD + occupancy — Task 7. ✅
- Maintenance handling (list/filter via table, view photo, set status + note) — Task 8. ✅
- Room-change handling (approve/reject) — Task 9. ✅
- Official-list import (Excel/CSV) + browse — Task 10. ✅
- Staff accounts (admin only) via Edge Function — Task 11. ✅
- Tests: pytest importer + integration (Task 12); manual checklist. ✅
- English UI throughout. ✅

**Placeholder scan:** no `TBD`/`TODO`; every code step contains full code.

**Type consistency:** `make_client`, `sign_in`, `current_role`, `room_occupancy`, `official_lookup` are defined in Task 2 and used with the same signatures in later tasks. RPC names/params match the backend plan (`approve_student`, `reject_student`, `approve_room_change`, `reject_room_change`, `import_official_residents`). Edge Function `admin-users` actions match Task 6 of the backend plan.

**Dependencies:** requires the backend plan applied + seeded (admin and staff users exist). The `admin-users` Edge Function must be deployed for Task 11.
