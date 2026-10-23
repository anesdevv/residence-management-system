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
- [ ] **Open Settings from sidebar footer**: Click **Settings** in the sidebar footer. Confirm Settings opens with Console preferences, Developer mode (admin only), and About RÉSIVO credits. Confirm Settings appears only once (in the sidebar footer, not in the upper nav list), and clicking other nav items returns cleanly.
