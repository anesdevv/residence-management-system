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