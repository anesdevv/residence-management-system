# Website Manual Test Checklist

## 1. Baseline Web Portal Verification
Prereqs: Supabase local running (`npx supabase status`); `web/.env` set; `npm --prefix web run dev`.

- [ ] `/` shows the landing page with Register and Sign in navigation.
- [ ] Log out → dashboard redirects to `/login`.
- [ ] Unauthenticated visit to `/dashboard` → redirected to `/login`.
- [ ] Submit a maintenance report with a photo → appears as `pending`; photo renders via signed URL.
- [ ] Submit a room-change request → appears as `pending`; preferred rooms match gender.
- [ ] Edit phone and/or contact email on `/dashboard/profile` → success banner; values persist; **Contact email** shows no "Verified" badge.

---

## 2. Simple Contact-Email & Zero-Email Auth Flows

Prerequisites: `supabase start` (or linked dev DB with migrations applied) and `npm --prefix web run dev`. Zero emails are ever sent by Supabase Auth or any Edge Function.

### Scenario A: Registration Email Validation (Mismatch & Duplicate Case-Insensitive)
1. Navigate to `http://localhost:4321/register`.
2. Fill in valid personal details, enter `student@univ-tlemcen.dz` in **Email**, and enter `other@univ-tlemcen.dz` in **Confirm email**.
3. Verify pasting into **Confirm email** works (not blocked), then submit.
4. **Expected**: Submission is blocked client-side with *"The emails do not match"* (no network request sent).
5. Try registering with an email already belonging to a seed student in different letter case (e.g. `Karim.Benali@UNIV-TLEMCEN.DZ`) and matching confirm field.
6. **Expected**: Friendly error banner (`email_in_use`), account is NOT created.

### Scenario B: Valid Registration (Zero Emails Sent)
1. Fill in valid registration fields for an unregistered enrolled student card ID (`202338077777`) and a unique email (`NewStudent@Univ-Tlemcen.dz` / matching confirm email).
2. Observe inline hint: *"Use an email address you can still access in the future. It is only used as contact information."*
3. Submit registration dossier.
4. **Expected**:
   - Redirected immediately to `http://localhost:4321/login?registered=1` with banner *"Account created. Wait for the housing office to review it."*
   - No verification screen, no code input, no resend button.
   - `public.students.email` stores `newstudent@univ-tlemcen.dz` (trimmed & lowercased) and `status = 'pending'`.
   - Zero emails sent anywhere (confirm in Supabase Auth logs).

### Scenario C: Student & Staff Login Without Verification or Email Recovery
1. Visit `/login`.
2. **Expected**:
   - No **"Forgot password?"** link and no **"Email me a sign-in link"** option.
   - Plain-text notice displayed: *"Forgot your password? Please contact the housing office."*
3. Sign in with Student Card ID + password (`202338012345`).
4. **Expected**: Signed in directly to `/dashboard` (students with `students.email` present are never redirected to `/account/add-email`).
5. Verify a staff account (email + password) can still authenticate normally and is never redirected to `/account/add-email`.

### Scenario D: Legacy Student Without Email Redirect Gate
1. Sign in as legacy seed student without an email (e.g., Card ID `202138099888` with `students.email IS NULL`).
2. **Expected**:
   - Redirected automatically to `/account/add-email`.
   - Direct navigation to `/dashboard` redirects back to `/account/add-email` until a contact email is saved.
3. Submit Email + Confirm email (`tariq.meghazi@univ-tlemcen.dz`).
4. **Expected**: Saved directly via `update_my_contact` (no code sent), and user is redirected to `/dashboard`. Subsequent visits to `/dashboard` work directly.

### Scenario E: Profile Contact Email & Phone Editing
1. Sign in as resident (`202338012345`) and visit `/dashboard/profile`.
2. **Expected**:
   - Email field is labeled **Contact email** (no "Verified" badge).
   - Updating phone and/or Contact email (with Confirm email field matching) saves cleanly via `update_my_contact`.
   - Entering a duplicate email used by another student returns the friendly `email_in_use` error.

---

## 3. Bilingual Web Portal Verification (English & Français)

### Scenario K: Language Switcher & Cookie Persistence
1. Navigate to the landing page at `http://localhost:4321/`.
2. Locate the language toggle in the header (`FR | EN`).
3. Click **FR**.
4. **Expected**:
   - The URL updates to `http://localhost:4321/fr`.
   - `<html lang="fr">` is present in the DOM.
   - All landing sections (hero headline, value propositions, intake process steps, campus services, institutional footer) render in formal French.
   - Cookie `resivo_locale=fr` is set with a 1-year max-age.
5. Click **"Espace Résident"** or **"Se connecter"**.
6. **Expected**:
   - Routes to `/fr/login`.
   - All input labels, placeholders, password toggle tooltips, and help links appear in French.
7. Close the browser tab and open `http://localhost:4321/`.
8. **Expected**: Middleware detects `resivo_locale=fr` and serves the French portal.

### Scenario L: Localized Student Dashboard
1. Sign in to `/fr/login` with resident credentials.
2. **Expected**:
   - Navigates to `/fr/dashboard`.
   - Greeting, status summary pills, digital resident pass labels, and recent activity list are in French.
   - Tab navigation shows: *"Vue d'ensemble"*, *"Demandes de réparation"*, *"Changement de chambre"*, *"Mon profil"*.
3. Click **"Demandes de réparation"** (`/fr/dashboard/maintenance`).
4. **Expected**: Maintenance status pills (*En attente*, *En cours*, *Résolue*), category badges (*Plomberie*, *Électricité*, *Menuiserie*, *Autres*), and ticket creation form appear in French.
5. In the header, click **EN**.
6. **Expected**: Switches immediately to `/dashboard/maintenance` in English, preserving state and query parameters.

---

### Scenario M: Single-Gender Registration Header & Closed State
1. With `residence_settings.residence_gender = NULL`, open `http://localhost:4321/register` (and `/fr/register`).
2. **Expected**:
   - Displays a warning banner: *"Registration is not open yet"* (*"Les inscriptions ne sont pas encore ouvertes"*).
   - Form fields and submit button are disabled, and direct `POST /api/register` rejects registration.
3. Have an administrator set `residence_gender = 'female'` (or `'male'`), then reload `/register` and `/fr/register`.
4. **Expected**:
   - Header shows the configured `residence_name` and *"Registration for the female residence"* (or male).
   - No `<select name="gender">` field appears anywhere in the registration form.
   - Submitting valid registration succeeds and assigns `students.gender` from `residence_settings` automatically via Postgres trigger.

### Scenario N: Room Change Portal Without Gender Filtering
1. Sign in as an active resident with an assigned room and open `/dashboard/room-change`.
2. **Expected**:
   - Preferred room dropdown lists all dormitory rooms (no block-gender restriction or hint text).
   - Submitting a valid room change request succeeds across blocks.

