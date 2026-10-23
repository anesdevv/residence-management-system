# RÉSIVO Desktop App — Fix & Audit Progress

## 1. Audit Results (Baseline Verification)

| Audit Item | Status | Key Evidence / Primary Locations | Notes & Findings |
|---|---|---|---|
| **Rotating log file (`%APPDATA%/RESIVO/logs/app.log`)** | **DONE** | `desktop/app/logging_setup.py:33-127`, `desktop/main.py:42` | `RotatingFileHandler` with 1MB limit, 3 backups. Fallback to `%TEMP%/RESIVO/logs` if APPDATA unwritable. HTTP transports silenced to WARNING. |
| **Global exception hooks** | **DONE** | `desktop/app/logging_setup.py:202-294`, `desktop/main.py:43-44` | Catches unhandled exceptions via `sys.excepthook`, `threading.excepthook`, `qInstallMessageHandler`, and `SafeApplication.notify()`. Prevents crash in `--noconsole` builds. |
| **Friendly error dialog with "Open log folder" button** | **DONE** | `desktop/app/logging_setup.py:138-201`, `desktop/app/ui/diagnostics.py:112-132` | `_ExceptionReporter` safely invokes non-modal error dialog via `QueuedConnection`. "Open log folder" button opens explorer via `QDesktopServices.openUrl()`. |
| **Reusable background worker helper** | **DONE** | `desktop/app/ui/tasks.py:63-210` (`_Task`, `TaskRunner`) | `QRunnable` / `QThreadPool` pattern. Signals (`succeeded`, `failed`, `finished`) delivered to GUI thread. Key-based deduplication (`_by_key`) prevents double-execution. |
| **Off-thread action handlers with busy state & double-click protection** | **DONE** | `pending.py:1202-1300`, `room_changes.py:1234-1439`, `maintenance.py:1115-1186`, `rooms.py:1246-1366`, `staff_accounts.py:458-557`, `official_list.py:475-534` | All core mutating actions run on worker pool via `self.tasks.run()`. Controls disabled during action (`_working = True`), button text changes to `"Working..."` / busy banner displayed, double clicks blocked. |
| **Safeguards preserved** | **DONE** | `pending.py:1098, 1271`, `room_changes.py:1347`, `staff_accounts.py:288, 473`, `rooms.py:1341` | Pending apps cannot be deleted; rejection requires non-empty reason; admin cannot delete self (UI + RPC); occupied rooms cannot be deleted; minimum window 980x640 preserved. |
| **LiveSyncWorker & Action Worker Concurrency** | **DONE** | `client.py:12` (`CLIENT_LOCK`), `live_sync.py:43-85`, `tasks.py:85-89`, `residents.py:104-220`, `main_window.py:944-971` | LiveSyncWorker and TaskRunner synchronize with `CLIENT_LOCK`. `room_occupancy` and `official_lookup` synchronized under `CLIENT_LOCK`. `ResidentsPage` loading and roster lookup moved off GUI thread via `TaskRunner`. Stale selections handled after refresh (`pending.py`, `maintenance.py`, `room_changes.py`, `rooms.py`). Shutdown timeout fallback prevents indefinite hang. |
| **RoomChangesPage: 4-view filter & search** | **DONE** | `desktop/app/ui/pages/room_changes.py:93-99, 361-367, 663-694` | 4 views (Pending / Approved / Rejected / All) via `SegmentedControl`. Search matches student name, card ID, request reason, and decision note. |
| **RoomChangesPage: Rejected persistence & desk inquiry card** | **DONE** | `room_changes.py:507-548, 672-675, 1122-1172, 1370-1378` | Table uses `setRowHidden` (never removes rows). Rejected requests show "Rejection reason (desk inquiry reference)" card with reason, decided by, date/time, student, rooms, and motive. Post-rejection selects record in Rejected tab with feedback message. |
| **Backend `reject_room_change` RPC** | **DONE** | `supabase/migrations/20261010102834_rpc_functions.sql:54-65`, `20261009224944_request_tables.sql:14-26` | Schema contains `reason`, `status`, `decision_note`, `decided_by`, `decided_at`. RPC records `decision_note = p_reason`, `decided_by = auth.uid()`, `decided_at = now()`. |
| **Staff accounts page in EXE & anti-downgrade** | **DONE** | `client.py:232-287`, `login_window.py:277-331`, `main_window.py:471, 702-794` | Direct lookup on `public.profiles.role` (case-insensitive, normalized, cached by session). Non-admin cannot see page. If role check fails, displays `InlineBanner` with "Retry" button. Never silently downgrades to non-admin. |
| **PyInstaller spec & BUILD documentation** | **DONE** | `desktop/resivo.spec`, `desktop/BUILD.md`, `desktop/app/config.py:11-30, 52-75` | Spec bundles assets, brand icon, root `.env`, and all hidden imports (`supabase`, `postgrest`, `gotrue`, `realtime`, `openpyxl`, `PySide6.*`, `app.*`). Config prioritizes `.env` next to EXE, then `_MEIPASS`. Config error screen cleanly exits before GUI startup. |
| **"About & Diagnostics" dialog** | **DONE** | `desktop/app/ui/diagnostics.py:60-133`, `desktop/app/ui/main_window.py:604-615` | Shows version, Supabase host without keys, connection status, user email, verified role, log path, and "Open log folder" button. Accessible from sidebar footer in expanded and collapsed modes. |
| **Automated Test Suite** | **DONE** | `desktop/tests/` (130 items: 129 passed, 1 skipped live test) | Comprehensive unit and integration tests across logging, task runner deduplication, async actions, role resolution, status views, and sign-out. |

---

## 2. Root Cause Diagnoses

### P1: UI "Not Responding" and Crashes on Action Submissions
- **Root Cause**:
  1. Synchronous HTTP network queries (`client.table().select()`, `client.rpc()`, `client.auth.get_user()`) executed directly on the Qt main GUI thread within button click handlers (`on_approve`, `on_reject`, `on_delete`, etc.). Any network latency or packet drop stalled the single-threaded Qt event loop, causing Windows to mark the process as "Not Responding".
  2. No in-flight debounce or double-click protection allowed rapid consecutive clicks to fire duplicate RPCs while the first was still processing.
  3. Ad-hoc threads lacked synchronization with `LiveSyncWorker` (which polls every 2 seconds), corrupting shared client state and triggering table index out-of-range crashes when rebuilding models with active selections.
  4. Exceptions inside slots under PyInstaller `--noconsole` had no global exception handler, causing silent process termination.

### P2: Rejected Room Change Requests Disappearing from the List
- **Root Cause**:
  1. `RoomChangesPage.reload()` originally executed `.eq("status", "pending")` directly against `room_change_requests`. The moment an admin called `reject_room_change` and the status transitioned to `'rejected'`, subsequent reloads or LiveSync ticks excluded the record, causing it to disappear instantly.
  2. The page lacked a multi-view filtering segmented control (unlike `PendingPage`).
  3. The detail pane lacked an audit/desk inquiry view to inspect rejection notes, decider details, and timestamps for student desk inquiries.

### P3: Staff Accounts Inaccessible in EXE & Role Verification Issues
- **Root Cause**:
  1. Packaging configuration: PyInstaller previously omitted necessary hidden imports (`supabase`, `gotrue`, `postgrest`, `realtime`, `storage3`, `websockets`, `app.ui.pages.*`) and failed to bundle `.env` fallback assets, causing module import or network client initialization failures in frozen mode.
  2. Role resolution failure mode: In earlier iterations, any exception in role lookup silently defaulted the user role to non-admin (`staff`), hiding the "Staff accounts" navigation item without notifying the operator.
  3. "Developer mode / Advanced settings": Never existed as a separate standalone settings page; the MCP token and write switches in `SettingsPage` were colloquially referred to as "developer mode" in commit comments (`e2a7498`).

---

## 3. SQL Query to Verify Admin Account in `public.profiles`

Run this read-only SQL query in the Supabase SQL editor to verify whether an account has the `'admin'` role:

```sql
SELECT 
    u.id AS user_id,
    u.email,
    p.role AS profile_role,
    s.full_name,
    s.position,
    (p.role = 'admin') AS is_admin,
    u.created_at AS user_created_at
FROM auth.users u
LEFT JOIN public.profiles p ON p.id = u.id
LEFT JOIN public.staff s ON s.id = u.id
WHERE u.email = 'YOUR_ADMIN_EMAIL_HERE';
```

Or to inspect all active administrators:

```sql
SELECT 
    u.id AS user_id,
    u.email,
    p.role,
    s.full_name,
    s.position,
    p.created_at AS profile_created_at
FROM public.profiles p
JOIN auth.users u ON u.id = p.id
LEFT JOIN public.staff s ON s.id = u.id
WHERE p.role = 'admin';
```

---

## 4. Work Progress and Remaining Items

| Step | Item | Status | Files | Notes |
|---|---|---|---|---|
| Step A | Audit & Baseline Verification | **DONE** | All files in `desktop/`, `supabase/` | 129 passed, 1 skipped. Code compiles cleanly. Detailed audit logged above. |
| Step B.1 | Observability | **DONE** | `desktop/app/logging_setup.py`, `desktop/main.py` | Verified rotating logs, exception hooks, error dialog with Explorer button. |
| Step B.2 | P1: Off-Thread Actions & Concurrency Hardening | **DONE** | `desktop/app/ui/pages/residents.py`, `desktop/app/client.py`, `desktop/app/ui/main_window.py`, `desktop/app/ui/pages/staff_accounts.py` | Core pages verified; `room_occupancy` & `official_lookup` wrapped in `CLIENT_LOCK`; `ResidentsPage` async reload & roster lookup implemented; shutdown escape hatch added; 3 new async tests added. |
| Step B.3 | P2: Rejected Room Changes Visibility & Desk Reference | **DONE** | `desktop/app/ui/pages/room_changes.py` | 4 views, search, rejection persistence, desk inquiry card, and post-reject navigation verified. |
| Step B.4 | P3: Admin Features & EXE Packaging | **DONE** | `desktop/resivo.spec`, `desktop/BUILD.md`, `desktop/app/config.py`, `desktop/app/ui/diagnostics.py` | Anti-downgrade retry banner, frozen config search order, diagnostics dialog verified. |
| Step B.5 | Manual Test Checklist Documentation | **DONE** | `docs/manual-test-desktop.md` | All 10 explicit manual test points and EXE instructions enumerated in the checklist. |

---

## 5. 3 Tasks Execution Progress (Roster, Maintenance Stages & Categories)

| Task | Title | Status | Files Changed | Description / Details |
|---|---|---|---|---|
| **T1** | **Modify and Delete Official Roster Entries** | **DONE** | `supabase/migrations/20261022133000_official_roster_management.sql`, `desktop/app/ui/pages/official_list.py`, `desktop/app/ui/main_window.py`, `desktop/tests/test_official_roster_actions.py` | Added idempotent migration with `add_official_resident`, `update_official_resident`, `delete_official_residents`, and `clear_official_residents` RPCs (security definer, admin check). Added search preservation, multi-row selection, Add, Edit, Delete selected, and Clear all (typed DELETE confirmation) actions to OfficialListPage with background TaskRunner execution. Gated write actions for admins with staff tooltips. Connected roster update notifications to PendingPage badge refresh. Added 7 unit tests (146 passed in pytest). |
| **T2** | **Remove "Under Review" Stage Everywhere** | **DONE** | `desktop/app/ui/pages/maintenance.py`, `desktop/tests/test_async_actions_maintenance_rooms.py`, `web/src/lib/maintenance.ts`, `web/src/lib/maintenance.test.ts`, `web/src/components/StatusPill.astro`, `web/src/components/Stepper.astro`, `web/src/pages/dashboard/maintenance.astro`, `web/src/pages/styleguide.astro`, `docs/PRD.md`, `README.md` | Removed "Under Review" stage across desktop MaintenancePage (segmented control buttons, stepper, overview counters, status pill) and web student portal (maintenance stepper, filters, badges, and styleguide). Normalized any legacy `under_review` tickets to `pending` in both desktop and web so existing tickets display and behave as Pending without data loss. Verified DB enum `report_status` is already strictly `('pending', 'in_progress', 'resolved')` (no schema migration needed). Added 2 new desktop unit tests and 4 web unit tests. Full suites passing: pytest 148 passed (1 skipped), vitest 14 passed. |
---

## 6. 8 Changes Execution Progress (RÉSIVO Desktop App)

| Change | Title | Status | Files Changed | Description / Details |
|---|---|---|---|---|
| **C1** | **Settings replaces About & Diagnostics** | **DONE** | `desktop/app/ui/diagnostics.py` (deleted), `desktop/resivo.spec`, `desktop/app/ui/main_window.py`, `desktop/tests/test_role_and_diagnostics.py`, `desktop/tests/test_role_cache_identity.py`, `desktop/BUILD.md`, `docs/manual-test-desktop.md` | Deleted `DiagnosticsDialog` and `desktop/app/ui/diagnostics.py`. Removed Settings from upper navigation list and moved it to the exact sidebar footer location previously occupied by About & Diagnostics. Ensured Settings appears only once. Added `clear_selection()` to `_SidebarNav`, added active checked state styling, connected settings button click to switch `QStackedWidget` to `SettingsPage`. Updated specs, tests, and documentation. Full pytest suite passes (142 passed, 1 skipped). |
| **C2** | **Maintenance page: add "All" filter** | **TODO** | | |
| **C3** | **Room changes & Pending pages: "All" becomes FIRST** | **TODO** | | |
| **C4** | **Fix the EXE icon & Windows metadata** | **TODO** | | |
| **C5** | **Login window: password show/hide button** | **TODO** | | |
| **C6** | **Fix Add/Edit Room dialog & broken spin-box arrows** | **TODO** | | |
| **C7** | **Confirm before closing the app** | **TODO** | | |
| **C8** | **Windows notifications & settings** | **TODO** | | |
