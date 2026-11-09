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

## Windows EXE checks (`dist\RESIVO\RESIVO.exe`)

Build with `desktop\.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean desktop\resivo.spec`.

- [ ] On a clean Windows profile, double-click `dist\RESIVO\RESIVO.exe`; the login window opens (no console flash, no missing-DLL dialog).
- [ ] `%APPDATA%\RESIVO\logs\app.log` is created; on any unhandled exception, the error dialog shows that path and **Open log folder** opens it.
- [ ] Log in as the seeded admin. The footer shows **Administrator**, **Staff accounts** is present, and Settings shows **Advanced settings / Developer mode** enabled.
- [ ] Log in as staff. **Staff accounts** is absent and Developer mode is disabled with the admin-only note.
- [ ] Approve a pending room-change request: the button disables immediately, the window stays responsive, and the request moves to **Approved** with the reassigned room after the worker finishes.
- [ ] Reject a pending room-change request with a reason: the window stays responsive, the request appears in **Rejected**, and its card shows the reason, decider and date.
- [ ] Switch to **Rejected**, type a search, wait at least two 2-second LiveSync ticks: the view, search, row and selection remain.
- [ ] Have another admin delete that request; within a few LiveSync ticks it disappears from this client (no ghost row).
- [ ] Kill the network (disable Wi-Fi) during approve/reject: an inline error appears, controls re-enable, the app does not crash, and the log contains the failure.
- [ ] Open `dist\RESIVO\_internal` and confirm there is no `mcp\.env` and no service-role key; only the public Supabase URL/anon key are packaged.
- [ ] For a deployment `.env`, place it next to `RESIVO.exe`; it takes precedence over the bundled copy.
- [ ] Resize to the 980x640 minimum and confirm Settings, Staff accounts and the rejection card remain readable (scrollbars appear where needed).

## Verification Checklist for Shipped Windows EXE

Execute each step directly in `dist\RESIVO\RESIVO.exe` to verify full operational readiness:

- [ ] **Approve student application**: On the **Pending** page, select a pending student application and click **Approve**. Confirm the room allocation dialog opens, select a room, and approve. Verify the window stays responsive ("Not Responding" never appears), controls disable with a busy state, the student transitions to active with the room assigned, and the row disappears from Pending into Residents.
- [ ] **Reject student application with reason**: On the **Pending** page, select a pending application, click **Reject**, enter a non-empty rejection reason, and submit. Verify non-empty reason is enforced, the action completes asynchronously without UI freeze, and the student's status becomes rejected.
- [ ] **Approve room change request**: On the **Room changes** page, select a pending request, click **Approve**, choose an available target room, and confirm. Verify the request moves to the **Approved** tab and room occupancy updates accordingly.
- [ ] **Reject room change and find under Rejected with reason visible**: On the **Room changes** page, select a pending request, click **Reject**, enter the rejection motive (e.g. "Requested block is at full capacity"), and confirm. Verify the page automatically switches to the **Rejected** view, the request remains visible in the list, and selecting it displays the **Rejection reason (desk inquiry reference)** card with reason, decider name, decision timestamp, student name, card ID, current room, requested room, and original motive.
- [ ] **Change maintenance status**: On the **Maintenance** page, select a report and update its status (e.g. click **In Progress** or **Resolve**). Verify button text updates to "Working...", controls disable during network write, and the status pill reflects the update without GUI freeze.
- [ ] **Import a roster**: On the **Official list** page, as admin, click **Import roster** (or drag-and-drop a valid CSV/Excel file). Verify the import runs off the GUI thread, controls disable during parsing/RPC execution, and imported resident rows populate the table.
- [ ] **Open Staff accounts as admin**: Log into the EXE using an account with `role: 'admin'`. Verify the **Staff accounts** navigation item is present in the sidebar, clicking it loads the staff directory, and the user role pill in the sidebar footer displays **Administrator**.
- [ ] **Create a staff account and log in with it**: On the **Staff accounts** page, enter full name, position, email, and password, then click **Create staff account**. Confirm the new account appears in the list. Sign out, and log in with the newly created staff credentials. Confirm login succeeds and **Staff accounts** is absent for this non-admin user.
- [ ] **Delete a staff account**: Log back in as admin, select the newly created staff account, and click **Delete staff account**. Confirm the deletion prompt; verify the row is removed from the table asynchronously.
- [ ] **Confirm admin cannot delete own account**: On the **Staff accounts** page as admin, select your own account row. Confirm the **Delete** button is disabled, the tooltip states *"You cannot delete your own staff account."*, and the inline self-delete warning banner is displayed. Confirm even attempting deletion programmatically or via shortcut is blocked.
- [ ] **Open Settings from sidebar footer (C1)**: Click **Settings** in the sidebar footer. Confirm Settings opens with Console preferences (General, Notifications, Developers), and About RÉSIVO credits. Confirm Settings appears only once (in the sidebar footer, not in the upper nav list), and clicking other nav items returns cleanly.
- [ ] **Maintenance page filter order (C2)**: On the **Maintenance** page, verify the segmented filter order from left to right is strictly: **All** - **Pending** - **In progress** - **Resolved**. Confirm "Pending" is selected by default on load, "All" displays tickets of every status, and search and live-sync refreshes preserve the active filter and search text.
- [ ] **Room changes filter order (C3)**: On the **Room changes** page, verify the segmented filter order from left to right is strictly: **All** - **Pending** - **Approved** - **Rejected**. Confirm "Pending" is selected by default on load, "All" displays requests across all statuses, and rejected requests still display their desk inquiry card.
- [ ] **Pending accounts/applications filter order (C3)**: On the **Pending** page, verify the segmented filter order from left to right is strictly: **All** - **Pending** - **Approved** - **Rejected**. Confirm "Pending" is selected by default on load, and "All" displays all application statuses.
- [ ] **EXE icon & Windows application metadata (C4)**: In Windows Explorer, verify `dist\RESIVO\RESIVO.exe` shows the high-resolution RÉSIVO mark icon. In Windows Task Manager (Details and Processes tab), verify the process displays the icon and application name "RÉSIVO" with company "Direction des Œuvres Universitaires - Cité Universitaire Tlemcen" rather than a generic white icon or raw filename. In the Windows taskbar, verify the running application is pinned/grouped under AppUserModelID `dz.dou.resivo.desktop`.
- [ ] **Login window show/hide password toggle (C5)**: On the login window, verify the password field contains an eye icon on the right edge. Type a password and click the eye button (or press Tab to focus it and press Space/Enter). Verify the input toggles between masked bullets and plain text, the icon swaps between eye and eye-off, and the tooltip switches between "Show password" and "Hide password". Confirm pressing Enter in the password field still logs in. Confirm when reopening the login window after sign-out, the field resets to masked.
- [ ] **Add/Edit Dormitory Room dialog & NumberStepper (C6)**: On the **Rooms** page, click **Add room**. Confirm the dialog layout is cleanly aligned: labels have a consistent column width (~160px), inputs are 40px high with a 16px row gap. Confirm "Floor Level" and "Bed Capacity" use the custom `NumberStepper` with styled 32x32 ghost minus (`-`) and plus (`+`) buttons, tabular numbers, and mouse wheel protection unless focused. Confirm the "+ Block" button displays a single plus icon followed by text "Add block" (not "+ + Block"). Confirm comboboxes render SVG chevrons. In the toolbar, confirm Add room (primary teal), Edit (secondary), and Delete (danger) have equal 36px height, and Edit/Delete remain disabled with explanatory tooltips when no room is selected.
- [ ] **Close confirmation dialog (C7)**: Attempt to close the main window via the top-right X button, Alt+F4, or tray menu "Quit". Confirm a confirmation dialog appears with Cancel (focused by default) and "Close app". Check "Don't ask me again" and click "Close app"; restart the app and confirm it closes immediately without prompt. Go to **Settings** -> **General preferences** and re-enable "Confirm before closing the app". Trigger a long-running action or busy state and attempt to close; confirm the dialog warns that an action is currently in progress with "Close anyway" (danger button).
- [ ] **Windows notifications & System tray (C8 & C10)**: Look in the Windows taskbar notification area (system tray) and confirm the RÉSIVO tray icon is present. Right-click it and verify the context menu provides "Open RÉSIVO", "Minimize to tray", and "Quit". Verify clicking "Minimize to tray" or pressing `Ctrl+M` hides the window from the taskbar into the system tray. Click or double-click the tray icon to restore the window to the foreground. In **Settings → General**, verify "Minimize to system tray" is checked by default, and that clicking the window titlebar minimize (`_`) button hides to the system tray. When attempting to close the app (`X`), confirm the confirmation dialog provides a "Minimize to tray" button that keeps live sync and desktop notifications running. Go to **Settings** -> **Notifications**, click **Send test notification**, and confirm a Windows toast / tray balloon appears with title "RÉSIVO Notifications". In Settings, toggle individual category notifications (applications, room changes, urgent maintenance, resolved maintenance), test quiet hours time range, and test privacy masking ("Mask student names"). Confirm clicking an alert toast brings RÉSIVO to the foreground and deep-links directly to the corresponding page.
- [ ] **Language Selection & Hot-Switching (i18n)**:
  - On the **Login Window**, verify the discreet language toggle (`Français | English`) in the form footer. Click it and verify the entire login window (hero title, value line, inputs, placeholders, buttons, and error messages) retranslates instantly in-memory without application restart.
  - Sign in and navigate to **Settings → General**. Find the **Language** setting (`QComboBox` with "English" and "Français"). Select **Français**.
  - Confirm an inline info banner appears: *"Langue modifiée. Redémarrez RÉSIVO pour appliquer les modifications."* with action buttons *"Redémarrer maintenant"* and *"Plus tard"*.
  - Click **"Redémarrer maintenant"**. Verify RÉSIVO cleanly releases its instance lock, exits, and restarts in French with all navigation items, tables, dialogs, status pills, and notifications displayed in formal French.
  - Verify that running with `$env:RESIVO_PSEUDO_LOCALE = "1"` renders accented characters (`[!! ... !!]`) with ~40% expanded text and zero layout clipping at the minimum 980x640 window dimensions.



## Slow Network, Offline & Flapping Connection Checklist (Rebuilt EXE)

Execute directly with `dist\RESIVO\RESIVO.exe`:

- [ ] **Wi-Fi disconnect during student application approval**:
  1. On the **Pending** page, select a pending student application and click **Approve**.
  2. Select an available room in the allocation dialog.
  3. Immediately upon clicking **Confirm approval** (while the button shows "Approving application..." / "Working..."), disconnect Wi-Fi (or unplug Ethernet).
  4. Confirm the window remains fully interactive and responsive (never shows "Not Responding").
  5. Confirm that after the write timeout (20s), an error banner appears stating: *"The result is unknown. Refresh to check before trying again."*
  6. Confirm buttons re-enable and no crash occurs.
  7. Reconnect Wi-Fi. Click **Refresh** (or wait for the next LiveSync tick) to confirm the true backend state.
- [ ] **Wi-Fi disconnect during student rejection**:
  1. Select a pending application, click **Reject**, enter a rejection reason.
  2. Disconnect Wi-Fi right after clicking confirm.
  3. Verify error banner appears, GUI never freezes, and the rejection can be safely retried once connection is restored.
- [ ] **Live-sync connection loss and automatic recovery**:
  1. Observe the live sync status in the bottom-left sidebar / status bar (green dot, *"Connected"*).
  2. Disconnect Wi-Fi. Within 2-5 seconds (next tick), verify the indicator turns amber (*"Reconnecting..."*).
  3. Keep Wi-Fi disconnected for 15 seconds. Confirm no error dialog pops up to interrupt the operator, and CPU usage stays near 0%.
  4. Reconnect Wi-Fi. Within 2-5 seconds, verify the indicator automatically transitions back to green (*"Connected"*).
  5. Verify that previously received notifications and badges are NOT duplicated or re-fired after reconnection.
- [ ] **Closing the app during a slow / stalled network operation**:
  1. Start an operation on a slow connection (or with Wi-Fi disabled).
  2. Attempt to close the app via the window close button (`X`).
  3. Confirm the app prompts with the close confirmation dialog warning that background operations are in progress.
  4. Confirm clicking **Close anyway** safely stops workers within the bounded shutdown timeout (under 10s) and terminates without a hang or crash dialog.
- [ ] **Network Throttling Tool (Optional - Clumsy / NetLimiter / Chrome DevTools MCP)**:
  1. Configure throttling to **150 ms latency, 1.6 Mbps download, 750 kbps upload** (simulated 3G/Slow 4G).
  2. Navigate across Pending, Residents, Rooms, Maintenance, Room changes, and Official list pages.
  3. Verify table contents populate cleanly, search filtering remains instantaneous (debounced locally), and photos display loading spinners followed by smooth off-thread thumbnail decoding.


## Windows Autostart & Single-Instance Checklist (Rebuilt EXE)

Execute directly with `dist\RESIVO\RESIVO.exe` (and `python desktop/main.py` for source check):

- [ ] **Default state in Settings**:
  1. Open `dist\RESIVO\RESIVO.exe`, log in, and go to **Settings → General**.
  2. Confirm "Start RÉSIVO when Windows starts" switch is **OFF** by default.
  3. Confirm the "Start minimized to the taskbar" sub-option is disabled while the main switch is OFF.
- [ ] **Enable autostart & restart check**:
  1. Turn the "Start RÉSIVO when Windows starts" switch **ON**.
  2. Sign out of Windows or restart the PC.
  3. Confirm RÉSIVO opens by itself at the login window upon Windows sign-in (credentials never stored).
- [ ] **Task Manager Startup apps listing**:
  1. Open Windows Task Manager (`Ctrl+Shift+Esc`) and go to the **Startup apps** tab.
  2. Confirm "RÉSIVO" is listed with the brand icon and the correct publisher/application name.
- [ ] **Disable via Task Manager**:
  1. In Task Manager > Startup apps, right-click "RÉSIVO" and click **Disable**.
  2. Open RÉSIVO Settings → General.
  3. Confirm the switch displays **OFF** and displays the warning note: *"Turned off in Windows Startup settings. Re-enable it there, or turn this switch off and on again."*
  4. Toggle the switch ON in RÉSIVO: verify the disabled flag is cleared and the note disappears.
- [ ] **Turn switch OFF**:
  1. Turn the autostart switch **OFF** in Settings.
  2. Restart the PC or sign out: verify the app does not launch on Windows startup.
- [ ] **Start minimized to taskbar**:
  1. Turn the autostart switch **ON** and check "Start minimized to the taskbar".
  2. Restart the PC or launch with `--autostart`: verify the app starts minimized to the taskbar.
  3. Log in: verify the main console window also opens minimized to the taskbar.
- [ ] **Startup without network (offline/Wi-Fi off)**:
  1. Launch with Wi-Fi disabled.
  2. Confirm the login window opens cleanly without crashing or freezing.
  3. Attempt login: verify the friendly connection banner appears with Retry, and re-enabling Wi-Fi allows immediate successful sign-in.
- [ ] **Single-instance guard**:
  1. Launch `dist\RESIVO\RESIVO.exe`.
  2. Launch a second copy of `dist\RESIVO\RESIVO.exe`.
  3. Confirm only ONE window opens and the second launch brings the existing window to the foreground.
  4. Launch `dist\RESIVO\RESIVO.exe --autostart` while already running: confirm it exits immediately and silently without opening a second copy.
- [ ] **Moved EXE path repair**:
  1. Enable autostart in Settings.
  2. Close RÉSIVO, move `dist\RESIVO` to another directory (e.g. `dist\RESIVO_Moved`).
  3. Launch `RESIVO.exe` from the new folder.
  4. Check the Run key in Registry Editor (`regedit`): verify `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` now points to the new path.
- [ ] **Run from source check (`python desktop/main.py`)**:
  1. Run the app from source code with `python desktop/main.py`.
  2. Open **Settings → General**.
  3. Confirm the "Start RÉSIVO when Windows starts" switch is disabled with the helper text: *"Available in the installed app (EXE) only."*


---

## 5. Session Persistence ("Stay signed in until Windows restarts") Checklist

Execute with the rebuilt standalone executable (`dist\RESIVO\RESIVO.exe`):

- [ ] **1. Normal App Restart (Close with X / Alt+F4)**:
  1. On Login window, check **"Stay signed in until this PC restarts"** and sign in.
  2. Verify main window opens and `%LOCALAPPDATA%\RESIVO\session\session.bin` exists.
  3. Close the application via window close button (**X** or `Alt+F4`).
  4. Reopen `RESIVO.exe`.
  5. **Pass criteria**: Bypasses the login window directly into `MainWindow` within ~400ms without prompting for credentials.

- [ ] **2. Process Termination in Task Manager**:
  1. With session stored, open Windows Task Manager (`Ctrl+Shift+Esc`).
  2. End process `RESIVO.exe`.
  3. Reopen `RESIVO.exe`.
  4. **Pass criteria**: Still signed in; opens directly into `MainWindow`.

- [ ] **3. Explicit Sign Out**:
  1. From `MainWindow`, click **Sign out** (via sidebar footer or **Settings → Security & Sign-in**).
  2. Verify app transitions back to the Login window.
  3. Inspect `%LOCALAPPDATA%\RESIVO\session\`.
  4. **Pass criteria**: `session.bin` is securely deleted; next launch requires full credentials.

- [ ] **4. Windows PC Restart**:
  1. Sign in with "Stay signed in until this PC restarts" checked.
  2. Restart Windows (`Start → Power → Restart`).
  3. After reboot, launch `RESIVO.exe`.
  4. **Pass criteria**: Login window opens displaying an info banner: *"You were signed out because Windows restarted."* Stored session file is cleaned up.

- [ ] **5. Windows Shut Down and Start (Fast Startup Active)**:
  1. Sign in with session persistence enabled.
  2. Shut down Windows (`Start → Power → Shut down`).
  3. Turn on PC and log in to Windows.
  4. Launch `RESIVO.exe`.
  5. **Pass criteria**: Boot epoch detection catches system restart despite Fast Startup hibernation; displays restart notice and prompts for login.

- [ ] **6. Windows User Sign-out / Account Switch**:
  1. Sign in with session persistence enabled.
  2. Sign out of Windows (`Ctrl+Alt+Del → Sign out`).
  3. Log back into Windows with the same Windows user account.
  4. Launch `RESIVO.exe`.
  5. **Pass criteria**: Windows logon session LUID mismatch detected; shows restart notice and prompts for login.

- [ ] **7. Lock Screen / Sleep and Wake**:
  1. Sign in with session persistence enabled.
  2. Lock Windows (`Win + L`) or put the PC to Sleep.
  3. Unlock / wake the PC.
  4. Open or restore `RESIVO.exe`.
  5. **Pass criteria**: Still signed in; live sync resumes without interruption.

- [ ] **8. Box Unchecked (Ephemeral Session)**:
  1. Uncheck "Stay signed in until this PC restarts" and sign in.
  2. Check `%LOCALAPPDATA%\RESIVO\session\`: verify no `session.bin` file exists.
  3. Close and reopen `RESIVO.exe`.
  4. **Pass criteria**: Login window is displayed immediately with blank fields.

- [ ] **9. Role Verification on Restore**:
  1. Sign in with an `admin` account (box checked), close and reopen: confirm **Staff accounts** navigation item is visible.
  2. Sign in with a `staff` account (box checked), close and reopen: confirm **Staff accounts** navigation item is hidden.

- [ ] **10. Wi-Fi Off / Offline at Launch with Stored Session**:
  1. Sign in with session persistence enabled, then close RÉSIVO.
  2. Turn off Wi-Fi or disconnect Ethernet cable.
  3. Launch `RESIVO.exe`.
  4. **Pass criteria**: Opens `MainWindow` with amber connection warning banner; `session.bin` is NOT deleted. Reconnect Wi-Fi and click "Retry": connects smoothly without re-login.

- [ ] **11. Remote Password Invalidation / Expiry**:
  1. Change staff password on another machine or invalidate user session in Supabase Dashboard.
  2. Launch `RESIVO.exe` with stored session.
  3. **Pass criteria**: Auth refresh fails; `session.bin` is wiped; app returns to Login window with warning banner: *"Your session has expired. Please sign in again."*

- [ ] **12. Single Instance Protection**:
  1. Launch `RESIVO.exe`.
  2. Attempt to launch `RESIVO.exe` a second time.
  3. **Pass criteria**: Single window enforced; second launch brings existing window to front.

- [ ] **13. Autostart Interaction**:
  1. Enable both "Start RÉSIVO when Windows starts" and "Stay signed in until this PC restarts".
  2. Restart PC: upon Windows sign-in, RÉSIVO autostarts directly at the Login window (reboot detected).
  3. Sign in, close RÉSIVO, and reopen manually: enters `MainWindow` directly.

- [ ] **14. Settings Page Security Switch & Actions**:
  1. Open **Settings → Security & Sign-in**.
  2. Verify "Stay signed in until this PC restarts" checkbox reflects the saved setting.
  3. Toggle switch **OFF**: verify `session.bin` is deleted immediately from disk.
  4. Toggle switch **ON**: verify active session is persisted to `session.bin` immediately.
  5. Verify account information line correctly shows `Signed in as <email> (<role>)`.
  6. Click "Sign out" button in the security card: verify full sign-out flow executes and lands on Login window.
