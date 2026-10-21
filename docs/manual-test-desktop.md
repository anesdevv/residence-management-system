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
- [ ] `%APPDATA%\RESIVO\logs\app.log` is created; **About & Diagnostics** shows that path and **Open log folder** opens it.
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
