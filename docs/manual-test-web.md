# Website manual test checklist

Prereqs: backend applied + seeded; `web/.env` set; `npm --prefix web run dev`.

- [ ] `/` shows the landing page with Register and Log in.
- [ ] Register a new card ID → redirected to login with a success message.
- [ ] DB shows the new student with status `pending`.
- [ ] Log in with a wrong card ID/password → error shown.
- [ ] Log in with the seeded student → dashboard shows status.
- [ ] Submit a maintenance report with a photo → appears as `pending`; photo renders via signed URL.
- [ ] Submit a room-change request → appears as `pending`; preferred rooms match gender.
- [ ] Edit phone → success banner; value persists; other fields read-only.
- [ ] Log out → dashboard redirects to `/login`.
- [ ] Unauthenticated visit to `/dashboard` → redirected to `/login`.