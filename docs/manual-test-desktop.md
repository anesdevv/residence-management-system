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
- [ ] **Windows notifications & System tray (C8)**: Look in the Windows taskbar notification area (system tray) and confirm the RÉSIVO tray icon is present. Right-click it and verify the context menu provides "Open RÉSIVO" and "Quit". Go to **Settings** -> **Notifications**, click **Send test notification**, and confirm a Windows toast / tray balloon appears with title "RÉSIVO Notifications". In Settings, toggle individual category notifications (applications, room changes, urgent maintenance, resolved maintenance), test quiet hours time range, and test privacy masking ("Mask student names"). Confirm clicking an alert toast brings RÉSIVO to the foreground and deep-links directly to the corresponding page.
