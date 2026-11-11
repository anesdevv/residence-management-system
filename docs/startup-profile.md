# RÉSIVO Desktop — Startup & Window-Transition Profile

Generated from live Windows Qt (`windows` QPA) instrumentation via [`desktop/app/startup_debug.py`](file:///c:/Users/Admin/Documents/OpenCode/my%20school%20project%20THE%20MAIN/desktop/app/startup_debug.py) (`RESIVO_DEBUG_STARTUP=1` / `RESIVO_DEBUG_WINDOWS=1`).

## 1. Test Environment & Methodology

- **OS / Qt backend**: Windows, PySide6 / Qt 6 (`windows` QPA platform plugin — real native HWND creation and focus behavior, not offscreen).
- **Flows measured**:
  1. **Real network baseline (`get_residence_public` anonymous RPC)** to configured Supabase host: `284.2 ms` – `317.7 ms` warm RTT (`1068.4 ms` cold TLS handshake observed).
  2. **`zero_net_cpu_qt` (`0 ms` simulated RPC delay)**: isolates pure Python import, Qt widget construction, layout, DPAPI session write (`WindowsBackend`), and painting overhead on the GUI thread.
  3. **`simulated_120ms_net` (`120 ms` simulated per-RPC latency)**: models realistic authenticated REST/RPC round trips without network jitter.
- **Role tested**: `admin` (exercises all 9 navigation pages and Settings admin controls).
- **Whitelisted windows** (`DEFAULT_WINDOW_WHITELIST`): `LoginWindow`, `MainWindow`.

---

## 2. BEFORE Baseline — Startup Timelines

### 2A. Pure CPU / Qt Cost (`0 ms` simulated RPC latency)

- **Max 50 ms GUI heartbeat gap**: **`3943.5 ms`** (target: `<= 150 ms`)
- **`first_paint`**: **`3645.0 ms`**
- **Post-show event loop responsiveness (`post_show_event_loop_tick`)**: **`3941.8 ms`**
- **First data received (`first_data_received`)**: **`3942.9 ms`**

| Marker | Elapsed (ms) | Step Delta (ms) | What happened on the GUI thread |
|---|---:|---:|---|
| `sign_in_click` | 0.2 | 0.2 | User clicked Sign In |
| `auth_start` | 0.8 | 0.6 | Pre-validation |
| `auth_end` | 1.4 | 0.6 | Synchronous `sign_in()` |
| `role_check_start` | 1.8 | 0.5 | Synchronous role check started |
| `role_check_end` | 2.3 | 0.5 | Synchronous `resolve_role()` |
| `session_save_end` | 15.2 | 12.9 | Synchronous DPAPI encrypt + atomic write + `fsync` |
| `main_window_init_start` | 500.7 | **485.5** | Lazy `from .main_window import MainWindow` importing all 9 page modules on GUI thread |
| `page:OverviewPage` | 1350.9 | **850.2** | `MainWindow` shell + tray/banners + `OverviewPage` construction |
| `page:PendingPage` | 1572.3 | 221.4 | Eager page construction + synchronous load |
| `page:ResidentsPage` | 1733.1 | 160.8 | Eager page construction |
| `page:RoomsPage` | 1871.4 | 138.3 | Eager page construction + synchronous load |
| `page:MaintenancePage` | 2038.7 | 167.4 | Eager page construction + synchronous load |
| `page:RoomChangesPage` | 2238.6 | 199.9 | Eager page construction + synchronous load |
| `page:OfficialListPage` | 2402.6 | 164.0 | Eager page construction + synchronous load |
| `page:StaffAccountsPage` | 2854.2 | **451.6** | Eager page construction + `current_uid` + load |
| `page:SettingsPage` | 3306.7 | **452.5** | Eager page construction + residence load + `McpHealthWorker` |
| `workers_started` | 3482.4 | 175.8 | `LiveSyncWorker` started |
| `main_window_init_end` | 3483.1 | 0.6 | `MainWindow.__init__` finished |
| `main_window_shown` | 3634.8 | 151.7 | `MainWindow.show()` + initial layout polish |
| `first_paint` | **3645.0** | 10.2 | First `QEvent.Type.Paint` on `MainWindow` |
| `post_show_event_loop_tick` | 3941.8 | 296.7 | First queued `QTimer.singleShot(0)` after `show()` |
| `first_data_received` | 3942.9 | 1.1 | First `LiveSyncWorker` snapshot applied |

### 2B. With Simulated Network Latency (`120 ms` per RPC)

- **Max 50 ms GUI heartbeat gap**: **`7366.2 ms`**
- **`main_window_shown`**: **`6298.8 ms`**
- **`first_paint`**: **`6309.7 ms`**
- **`post_show_event_loop_tick`**: **`7331.6 ms`**
- **`first_data_received`**: **`7365.6 ms`**

| Marker | Elapsed (ms) | Step Delta (ms) |
|---|---:|---:|
| `sign_in_click` | 0.2 | 0.2 |
| `auth_start` | 1.2 | 1.0 |
| `auth_end` | 124.7 | 123.5 |
| `role_check_start` | 125.4 | 0.7 |
| `role_check_end` | 353.4 | 228.0 |
| `session_save_end` | 384.8 | 31.4 |
| `main_window_init_start` | 1101.3 | 716.5 |
| `page:OverviewPage` | 2639.2 | 1537.9 |
| `page:PendingPage` | 3074.3 | 435.1 |
| `page:ResidentsPage` | 3279.5 | 205.2 |
| `page:RoomsPage` | 3769.2 | 489.7 |
| `page:MaintenancePage` | 4065.8 | 296.6 |
| `page:RoomChangesPage` | 4486.3 | 420.5 |
| `page:OfficialListPage` | 4722.2 | 235.9 |
| `page:StaffAccountsPage` | 5310.9 | 588.6 |
| `page:SettingsPage` | 6046.4 | 735.5 |
| `workers_started` | 6159.1 | 112.7 |
| `main_window_init_end` | 6159.7 | 0.6 |
| `main_window_shown` | 6298.8 | 139.1 |
| `first_paint` | 6309.7 | 10.9 |
| `post_show_event_loop_tick` | 7331.6 | 1021.9 |
| `first_data_received` | 7365.6 | 34.0 |

*(Notice: With `120 ms` simulated delay, `OverviewPage` + `MainWindow` added ~688 ms of extra network blocking — e.g. `fetch_residence_public` and `OverviewPage` synchronous calls if any, `MainWindow` profile fetch — and the 8 secondary pages spent `~3.4 s` executing blocking queries inside `__init__()`.)*

---

## 3. BEFORE Baseline — Unexpected Top-Level Ghost Windows

Across **160** total top-level `Show` / `ShowToParent` / `WinIdChange` events recorded during `LoginWindow` -> `MainWindow` startup, **152 events** were unexpected ghost windows (only **8** belonged to `LoginWindow` and `MainWindow`).

Because `SafeApplication` sets `app.setApplicationDisplayName("RÉSIVO")` and these orphan widgets had `windowTitle == ""` and `parent == None`, Windows created tiny top-level tool/window HWNDs titled `"RÉSIVO"` over the top-left corner, flashing empty frames and stealing OS focus from `LoginWindow` (turning its title bar grey).

### Grouped Summary by Origin

| Component | Exact Line(s) | Events Fired | Count | Class / Title / Sample Size / Flags | Mechanism |
|---|---|---|---:|---|---|
| `InlineBanner` | `components.py:921, 925, 928` | `WinIdChange`, `Show`, `ShowToParent` | **116** | `QLabel`, `title=''` (OS displays `'RÉSIVO'`), `(640, 480)` -> `(119, 19)` / `(197, 19)`, `parent=None`, `flags=0x800f001` | `self._title` & `self._message` are created as `QLabel(...)` with `parent=None`, placed in an unattached `column = QVBoxLayout()`, and `.setVisible(True)` is called BEFORE `root.addLayout(column, 1)` parents them into `InlineBanner`. Reparenting immediately destroys the orphan top-level HWND (`29x WinIdChange` on line 928). Fires across **17** banner instances (`MainWindow` x2, `OverviewPage`, `PendingPage` x2, `ResidentsPage`, `RoomsPage`, `MaintenancePage`, `RoomChangesPage` x2, `OfficialListPage` x2, `StaffAccountsPage` x2, `SettingsPage` x3). |
| `PageHeader` | `components.py:598, 601` | `WinIdChange`, `Show`, `ShowToParent` | **36** | `QLabel`, `title=''` (OS displays `'RÉSIVO'`), `(640, 480)` / `(424, 19)`, `parent=None`, `flags=0x800f001` | `self._subtitle = QLabel(...)` has `parent=None`, is placed in unattached `column = QVBoxLayout()`, and `.setVisible(bool(subtitle))` is called on line 598 BEFORE `root.addLayout(column, 1)` on line 601 parents it into `PageHeader`. Fires **1** popup + reparent (`4` events) on every single one of the **9** pages (`9 x 4 = 36`). |

**Representative Stack Trace (`InlineBanner`):**
```text
File "desktop/app/ui/login_window.py", line 408, in attempt -> self._verify_role()
File "desktop/app/ui/login_window.py", line 500, in _verify_role -> self.window = MainWindow(self.client, role=role)
File "desktop/app/ui/main_window.py", line 512, in __init__ -> root_layout.addWidget(self._build_content(), 1)
File "desktop/app/ui/main_window.py", line 792, in _build_content -> self.role_banner = InlineBanner(...)
File "desktop/app/ui/components.py", line 921, in __init__ -> self._title.setVisible(bool(title))
```

**Representative Stack Trace (`PageHeader`):**
```text
File "desktop/app/ui/main_window.py", line 540, in __init__ -> self.overview_page = OverviewPage(client)
File "desktop/app/ui/pages/overview.py", line 193, in __init__ -> layout.addWidget(PageHeader(...))
File "desktop/app/ui/components.py", line 598, in __init__ -> self._subtitle.setVisible(bool(subtitle))
```

A static audit across `desktop/app/` (`rg -n "setVisible\(|\\.show\(|setCellWidget\(|QWidget\(\)" desktop/app/`) confirmed these two components were the exact source of the 152 startup flashes. Other `setVisible()` calls in pages happen either after `layout.addWidget(...)` or with `False`, though several pages/helpers still construct child widgets without passing `parent=self` before adding them to layouts (which Phase 2 will also harden defensively).

---

## 4. Root Causes Identified (All Observed in Source + Runtime)

1. **Synchronous GUI-thread Sign In (`desktop/app/ui/login_window.py`)**:
   - `attempt()` sets the button text to `t("login.signing_in")` and immediately calls `sign_in()`, `_verify_role()`, `resolve_role()`, `save_current_session()`, lazy imports (`+485 ms`–`+716 ms`), and `MainWindow(...)` synchronously without yielding to the Qt event loop.
   - As a result, `"Signing in..."` is never painted, controls stay active/unpainted, the OS shows the busy wheel, and the GUI thread stalls for `3.9 s`–`7.4 s`.
2. **Orphan `setVisible(True)` in `PageHeader` & `InlineBanner` (`desktop/app/ui/components.py`)**:
   - Parentless `QLabel` instances inside an unparented `QVBoxLayout()` are made visible prior to `root.addLayout(column, 1)`, creating 26 distinct flashing native `"RÉSIVO"` top-level ghost windows (`152` events) during `MainWindow` construction and stealing focus from `LoginWindow`.
3. **Eager 9-Page Construction + Blocking `__init__()` RPCs (`desktop/app/ui/main_window.py` & `pages/*.py`)**:
   - `MainWindow.__init__()` instantiates all 9 pages upfront.
   - Six secondary pages (`PendingPage`, `RoomsPage`, `MaintenancePage`, `RoomChangesPage`, `OfficialListPage`, `StaffAccountsPage`) plus `SettingsPage._load_residence_sync()` run blocking synchronous Supabase requests inside `__init__()` on the GUI thread (`~1.96 s` CPU at 0 ms, `~3.30 s` at 120 ms).
4. **Window Title Duplication (`desktop/app/ui/main_window.py` + `desktop/main.py`)**:
   - `SafeApplication` sets `app.setApplicationDisplayName("RÉSIVO")`, while `MainWindow.__init__()` calls `self.setWindowTitle("RÉSIVO — Staff Console")`. Qt automatically appends `applicationDisplayName`, producing `"RÉSIVO — Staff Console — RÉSIVO"`. (`MAIN_WINDOW_TITLE_PROPERTY='RÉSIVO — Staff Console'`).
5. **Misleading Initial Live-Sync Text (`desktop/app/ui/main_window.py`)**:
   - `MainWindow` initializes `_set_live_state("reconnecting")`, displaying `"Live sync reconnecting"` even before the first live-sync tick arrives. Should start in a neutral connecting state (`Connecting...` / `Connexion…`) until the first snapshot arrives or an error occurs.
6. **Styling & Icon Rendering Overhead (`desktop/app/ui/theme.py`, `desktop/app/ui/icons.py`)**:
   - `DESKTOP_STYLESHEET` is applied on individual windows rather than once at `QApplication` level, and `icons.get_pixmap()` re-parses SVG XML via `QSvgRenderer` without a pixmap/icon cache.

---

## 5. Planned Fix Phases & Target Metrics

| Phase | Scope | Target Metric |
|---|---|---|
| **Step 0** | Instrumentation (`RESIVO_DEBUG_STARTUP=1` / `RESIVO_DEBUG_WINDOWS=1`) & BEFORE profile | Documented baseline (`152` ghost events, `3.9 s`–`7.4 s` stall) |
| **Phase 1** | Async off-thread Sign In, immediate <=100 ms busy state + spinner, cancelable idle background warm-up | Busy feedback `<= 100 ms`, GUI heartbeat `<= 150 ms` during auth |
| **Phase 2** | Parent-first construction in `PageHeader`, `InlineBanner`, shared components, pages; offscreen regression guard | **0** unexpected ghost window events |
| **Phase 3** | Lazy secondary pages, PEP 562 lazy module imports, live-sync cache, atomic Login->Main swap, cached app QSS & SVG icons, guarded `_set_tnum`, neutral `Connecting...`, fixed title `Staff Console` | `MainWindow` shown `<= 1.0 s` (ex-net), first data `<= 1.5 s` |
| **Phase 4** | BEFORE vs AFTER benchmarks, full `pytest` verification, PyInstaller EXE checklist | Complete — all startup goals verified |

---

## 6. AFTER Fixes — Measured Results (Windows `windows` QPA)

### 6A. Before vs After Comparison Summary (`LoginWindow` -> `MainWindow`)

| Metric | BEFORE (`0 ms`) | AFTER (`0 ms`) | BEFORE (`120 ms`) | AFTER (`120 ms`) | Target / Improvement |
|---|---:|---:|---:|---:|---|
| Instant busy UI (`busy_ui_event_loop_tick`) | *Never painted* (`~3941 ms`) | **`5.7 ms`** | *Never painted* (`~7331 ms`) | **`5.7 ms`** | **`<= 100 ms`** (`busy_ui_set` `3.5 ms`) |
| Auth + role + DPAPI save on GUI thread | Synchronous freeze | **Off-thread** (`QRunnable`) | Synchronous freeze (`384.8 ms`) | **Off-thread** (`331.4 ms`) | Non-blocking GUI loop during network |
| `MainWindow` shown after credentials accepted (`main_window_shown - role_check_end`) | `3632.5 ms` | **`474.5 ms`** | `5945.4 ms` | **`307.4 ms`** | **`<= 1.0 s`** (**7.7x – 19.3x faster**) |
| Total `sign_in_click` -> `main_window_shown` | `3634.8 ms` | **`516.8 ms`** | `6298.8 ms` | **`626.0 ms`** | **7.0x – 10.1x faster** |
| First `MainWindow` paint (`first_paint`) | `3645.0 ms` | **`526.2 ms`** | `6309.7 ms` | **`635.0 ms`** | **6.9x – 9.9x faster** |
| First live data (`first_data_received`) | `3942.9 ms` | **`696.1 ms`** | `7365.6 ms` | **`1108.5 ms`** | **`<= 1.5 s`** (**5.7x – 6.6x faster**) |
| `Max 50 ms GUI heartbeat gap` (entire flow)* | `3943.5 ms` | **`594.4 ms`** | `7366.2 ms` | **`366.8 ms`** | **6.6x – 20.1x smaller** |
| Unexpected top-level ghost events | **`152`** | **`0`** | **`152`** | **`0`** | **0 ghost windows** |
| Secondary pages built at startup | `8 / 8` (eager + blocking RPCs) | **`0 / 8`** (lazy on first open) | `8 / 8` | **`0 / 8`** | Zero unvisited-page startup cost |
| `MainWindow` title property (`applicationDisplayName="RÉSIVO"`) | `'RÉSIVO — Staff Console'` (renders twice) | **`'Staff Console'`** | `'RÉSIVO — Staff Console'` | **`'Staff Console'`** | Renders cleanly as `'Staff Console — RÉSIVO'` |
| Initial live-sync indicator (before first tick) | `'Live sync reconnecting'` | **`'Connecting...'`** | `'Live sync reconnecting'` | **`'Connecting...'`** | Neutral state (`live_sync.connecting`) |

> \* **Note on GUI heartbeat gap**: Auth (`sign_in`), role check (`resolve_role`), and DPAPI session persistence run completely off the GUI thread with zero event-loop stall (`busy_ui_event_loop_tick = 5.7 ms`). The remaining single `366.8 ms`–`594.4 ms` gap occurs solely during `MainWindow` shell + `OverviewPage` Qt widget construction and `MainWindow.show()` (which must execute on the GUI thread and completes well inside the `1.0 s` window-appearance budget), compared to the multi-second (`3.9 s`–`7.4 s`) freeze before.

### 6B. Detailed AFTER Timeline — `zero_net_cpu_qt` (`0 ms` simulated RPC latency)

- **`Max 50 ms GUI heartbeat gap`**: **`594.4 ms`**
- **`TOTAL_WINDOW_EVENTS`**: **`6`** (`3x LoginWindow`, `3x MainWindow`) | **`UNEXPECTED_GHOST_EVENTS`**: **`0`**

| Marker | Elapsed (ms) | Step Delta (ms) | What happened |
|---|---:|---:|---|
| `sign_in_click` | 0.4 | 0.4 | User clicked Sign In |
| `busy_ui_set` | 3.5 | 3.1 | Controls disabled + indeterminate busy bar shown |
| `busy_ui_event_loop_tick` | 5.7 | 2.2 | Event loop painted busy state back to OS |
| `auth_start` | 18.9 | 13.3 | Off-thread `_LoginWorker` started `sign_in()` |
| `auth_end` | 19.7 | 0.7 | Off-thread `sign_in()` returned |
| `role_check_start` | 41.6 | 22.0 | Off-thread `resolve_role()` started |
| `role_check_end` | 42.3 | 0.7 | Role resolved off GUI thread |
| `session_save_end` | 52.8 | 10.5 | DPAPI session persisted off GUI thread |
| `main_window_init_start` | 53.9 | 1.1 | Transition handed back to GUI thread |
| `main_window_ctor_start` | 56.0 | 2.1 | `MainWindow.__init__()` started |
| `page:OverviewPage` | 242.0 | 186.0 | Shell + `OverviewPage` built (8 secondary pages deferred) |
| `workers_started` | 408.2 | 166.2 | `LiveSyncWorker` started |
| `main_window_init_end` | 408.8 | 0.6 | `MainWindow.__init__()` finished |
| `main_window_shown` | 516.8 | 108.0 | `MainWindow` shown, raised & activated atomically before closing `LoginWindow` |
| `first_paint` | **526.2** | 9.5 | First `QEvent.Type.Paint` on `MainWindow` |
| `post_show_event_loop_tick` | 695.2 | 169.0 | Post-show event loop tick + deferred tray setup |
| `first_data_received` | **696.1** | 0.9 | First `LiveSyncWorker` snapshot applied |

### 6C. Detailed AFTER Timeline — `simulated_120ms_net` (`120 ms` simulated per-RPC latency)

- **`Max 50 ms GUI heartbeat gap`**: **`366.8 ms`**
- **`TOTAL_WINDOW_EVENTS`**: **`6`** (`3x LoginWindow`, `3x MainWindow`) | **`UNEXPECTED_GHOST_EVENTS`**: **`0`**

| Marker | Elapsed (ms) | Step Delta (ms) |
|---|---:|---:|
| `sign_in_click` | 0.2 | 0.2 |
| `busy_ui_set` | 3.5 | 3.3 |
| `busy_ui_event_loop_tick` | 5.7 | 2.2 |
| `auth_start` | 14.5 | 8.8 |
| `auth_end` | 135.9 | 121.4 |
| `role_check_start` | 136.7 | 0.8 |
| `role_check_end` | 318.6 | 181.9 |
| `session_save_end` | 331.4 | 12.8 |
| `main_window_init_start` | 350.3 | 18.9 |
| `main_window_ctor_start` | 352.7 | 2.4 |
| `page:OverviewPage` | 501.5 | 148.8 |
| `workers_started` | 561.8 | 60.3 |
| `main_window_init_end` | 562.3 | 0.5 |
| `main_window_shown` | **626.0** | 63.7 |
| `first_paint` | **635.0** | 9.1 |
| `post_show_event_loop_tick` | 689.2 | 54.2 |
| `first_data_received` | **1108.5** | 419.3 |

### 6D. Session Restore (`launch_application` with DPAPI `WindowsBackend`, `120 ms` simulated delay)

- **`TOTAL_WINDOW_EVENTS`**: **`3`** (`MainWindow` only; restore finishes in `320.0 ms`, inside the `400 ms` restoring-UI grace window so zero transient `LoginWindow` opens) | **`UNEXPECTED_GHOST_EVENTS`**: **`0`**
- **`main_window_shown`**: `1314.0 ms` (`994.0 ms` after `restore_role_end`), **`first_paint`**: `1319.7 ms`, **`first_data_received`**: `1701.3 ms`.

---

## 7. Manual Windows EXE Build & Verification Checklist

The PyInstaller spec (`desktop/resivo.spec`, verified syntax-valid against `PyInstaller 6.22.3`) includes `app.startup_debug` in `hiddenimports`. After pulling these changes on a Windows build machine (steps from `desktop/BUILD.md`):

1. **Rebuild the clean `onedir` bundle**:
   ```powershell
   Remove-Item -Recurse -Force build\resivo, dist\RESIVO -ErrorAction SilentlyContinue
   desktop\.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean desktop\resivo.spec
   desktop\.venv\Scripts\python.exe tools\check_deps.py dist\RESIVO
   dist\RESIVO\RESIVO.exe --selftest
   ```
2. **Verify interactive Sign In with startup diagnostics enabled**:
   ```powershell
   $env:RESIVO_DEBUG_STARTUP = "1"
   $env:RESIVO_DEBUG_WINDOWS = "1"
   dist\RESIVO\RESIVO.exe
   ```
   Confirm in the UI & `%APPDATA%\RESIVO\logs\app.log`:
   - Clicking **Sign In** disables controls and shows the busy progress bar + `"Opening console..."` / `"Ouverture de la console…"` immediately (`<= 100 ms`).
   - Zero small empty `"RÉSIVO"` frames flash over the top-left of the login window, and the login title bar stays active until the main window swaps in.
   - Main window title displays `"Staff Console — RÉSIVO"` (never `"RÉSIVO"` twice) and the initial live-sync badge displays `"Connecting..."` / `"Connexion en cours…"` before settling on `"Live sync connected"`.
   - Switching to secondary navigation tabs (`Pending`, `Residents`, `Rooms`, `Maintenance`, `Transfers`, `Official List`, `Staff Accounts`, `Settings`) constructs each page cleanly on first click with zero `[GHOST]` entries in `app.log`.
3. **Clear debug variables** afterward (`Remove-Item Env:RESIVO_DEBUG_STARTUP, Env:RESIVO_DEBUG_WINDOWS -ErrorAction SilentlyContinue`) so normal launches remain zero-overhead.
