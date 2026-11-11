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
| **Phase 3** | Lazy/idle-sliced secondary pages, live-sync pre-build caching, parallel prefetch, atomic Login->Main swap, single app QSS, cached SVG icons, neutral `Connecting...`, fixed title `Staff Console — RÉSIVO` | `MainWindow` shown `<= 1.0 s` (ex-net), first data `<= 1.5 s`, max heartbeat `<= 150 ms` |
| **Phase 4** | BEFORE vs AFTER benchmarks, full `pytest` verification, PyInstaller EXE checklist | All targets met, zero regressions |
