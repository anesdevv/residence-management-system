# Website Manual Test Checklist

## 1. Baseline Web Portal Verification
Prereqs: Supabase local running (`npx supabase status`); `web/.env` set; `npm --prefix web run dev`.

- [ ] `/` shows the landing page with Register and Sign in navigation.
- [ ] Log out → dashboard redirects to `/login`.
- [ ] Unauthenticated visit to `/dashboard` → redirected to `/login`.
- [ ] Submit a maintenance report with a photo → appears as `pending`; photo renders via signed URL.
- [ ] Submit a room-change request → appears as `pending`; preferred rooms match gender.
- [ ] Edit phone on `/dashboard/profile` → success banner; phone persists; email is verified read-only.

---

## 2. Real Verified Email & Auth Flows (Local Mailpit Testing)

Supabase local includes an in-memory mail catcher (Mailpit) running at **`http://localhost:54324`**. All verification emails, OTP codes, recovery messages, and magic links are caught here without needing a Brevo account or external SMTP credentials.

### Scenario A: New Student Registration & Email Verification
1. Navigate to `http://localhost:4321/register`.
2. Fill in enrollment and personal data:
   - Student card ID: `202338077777` (at least 4 digits, not yet registered)
   - Real email: `newstudent@univ-tlemcen.dz`
   - Confirm email: `newstudent@univ-tlemcen.dz`
   - Password: `Password123!` (at least 8 chars, strength meter updates to Good/Strong)
3. Submit registration dossier.
4. **Expected**: Redirected to `http://localhost:4321/verify-email`. The page displays:
   - Account activation header
   - Masked target address (e.g., `n***t@univ-tlemcen.dz`)
   - 6-slot numeric OTP code input
   - "Resend code" button with countdown
5. Open Mailpit at `http://localhost:54324`. A branded RÉSIVO email titled *"Confirm your RÉSIVO account"* should be present.
6. Copy the 6-digit verification code from the email (e.g., `123456`).
7. Enter or paste the digits into `/verify-email`.
8. Click **Verify and continue**.
9. **Expected**: Redirected to `http://localhost:4321/login?verified=1` with banner *"Email verified! Your email address has been confirmed."*
10. Check database: `students.email` is now populated with `newstudent@univ-tlemcen.dz`, and `auth.users.email_confirmed_at` is set.

### Scenario B: Verification Link Click (Secondary Flow)
1. Register another student with email `student.link@univ-tlemcen.dz`.
2. Open Mailpit at `http://localhost:54324`.
3. In the email, click the blue button **"Verify your email"** (pointing to `http://localhost:4321/auth/confirm?token_hash=...&type=email`).
4. **Expected**: The browser validates the hash server-side and redirects to `/dashboard` or `/login?verified=1`.

### Scenario C: Unverified Email Login Attempt
1. Register a student with email `unconfirmed@univ-tlemcen.dz` but do **not** verify the code.
2. Go to `/login` and attempt to sign in with `unconfirmed@univ-tlemcen.dz` and the correct password.
3. **Expected**: Redirected back to `/verify-email?unverified=1` with banner *"Your university housing dossier has been submitted, but your email address has not been verified yet."*

### Scenario D: Wrong & Expired OTP Codes
1. On `/verify-email`, enter an invalid code (e.g. `000000`).
2. Submit.
3. **Expected**: Error banner *"Invalid verification code. Please check your digits and try again."* Input slots remain accessible.

### Scenario E: "Resend Code" Cooldown & Session Cap
1. On `/verify-email`, click **Resend code**.
2. **Expected**:
   - Fresh email received in Mailpit.
   - Button immediately disables, changing label to *"Resend in 60s"*.
   - Countdown decrements every second: `59s`, `58s`, ... `0s`.
   - Once counter hits `0s`, button re-enables with label *"Resend code"*.
   - Rapidly requesting codes reaches the 5 sends/hour session cap with banner *"Hourly send limit reached (5/5). Try again in ... minutes."*

### Scenario F: Sign in with Card ID vs Email (Dual Identifier Support)
1. Sign in with Card ID:
   - Identifier: `202338012345`
   - Password: `Password123!`
   - **Expected**: Successful sign-in to dashboard.
2. Sign out.
3. Sign in with Email:
   - Identifier: `karim.benali@univ-tlemcen.dz`
   - Password: `Password123!`
   - **Expected**: Successful sign-in to dashboard.
4. Try invalid credentials:
   - Identifier: `nonexistent@univ-tlemcen.dz` (or card ID `999999999999`)
   - Password: `WrongPassword!`
   - **Expected**: Generic message *"Invalid card ID/email or password."* (No account enumeration).

### Scenario G: Password Recovery Flow (Card ID & Email)
1. Go to `/login` and click **"Forgot password?"**.
2. Enter Card ID `202338012345` (or email `karim.benali@univ-tlemcen.dz`).
3. Click **Send recovery code**.
4. **Expected**: Transition to recovery OTP step with generic notification *"If an account exists for that identifier, instructions and a 6-digit recovery code have been dispatched to the email on file."*
5. Open Mailpit (`http://localhost:54324`).
6. Notice the email titled *"Reset your RÉSIVO portal password"*.
7. Copy the 6-digit recovery code and enter it on the recovery screen.
8. Click **Verify code & continue**.
9. **Expected**: Redirected to `/reset-password`.
10. Enter a new password (e.g., `NewStrongPassword123!`), view the strength meter update to Strong, and submit.
11. **Expected**: Redirected to `/login?reset=1` with banner *"Your password has been updated. Please sign in with your new password."*
12. Sign in with the new password.

### Scenario H: Magic Link / Passwordless One-Time Code
1. On `/login`, expand **"Email me a sign-in code or link"**.
2. Enter `202338012345` or `karim.benali@univ-tlemcen.dz`.
3. Submit.
4. **Expected**: Generic notice *"If an account matches that identifier, we sent a one-time sign-in code and magic link..."*.
5. Open Mailpit, open the sign-in email, and click the magic link button.
6. **Expected**: Authenticated directly into `/dashboard`.

### Scenario I: Student Profile & Changing Email
1. Sign in as resident `karim.benali@univ-tlemcen.dz`.
2. Go to `/dashboard/profile`.
3. Observe:
   - Mobile phone number is editable.
   - Contact email is read-only with a green **Verified** status badge.
   - Link **"Change email →"** is present.
4. Click **"Change email →"** (routes to `/account/add-email`).
5. Enter a new email (e.g., `karim.new@univ-tlemcen.dz`) and confirm.
6. Submit.
7. Open Mailpit, grab confirmation OTP, and enter it.
8. **Expected**: Redirected back to `/dashboard/profile?updated=1`. The contact email is now `karim.new@univ-tlemcen.dz` with the Verified badge.

### Scenario J: Legacy Student Account Migration Flow
1. In `/login`, enter legacy student credentials:
   - Card ID: `202138099888`
   - Password: `Password123!`
2. Submit.
3. **Expected**: `student-login` detects the synthetic `@students.residence.local` email and middleware automatically redirects the student to **`/account/add-email`**.
4. Attempt to navigate directly to `/dashboard` or `/dashboard/maintenance`.
5. **Expected**: Automatically intercepted and redirected back to `/account/add-email`.
6. Fill in a real email:
   - Email: `tariq.meghazi@univ-tlemcen.dz`
   - Confirm email: `tariq.meghazi@univ-tlemcen.dz`
7. Click **Send verification code**.
8. In Mailpit, find the verification email sent exclusively to `tariq.meghazi@univ-tlemcen.dz` (zero email sent to `@students.residence.local`).
9. Enter the 6-digit code and submit.
10. **Expected**: Real email is confirmed and mirrored into `students.email`. User is now permitted into `/dashboard`!
