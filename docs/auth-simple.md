# RÉSIVO Web Authentication & Contact Email (Zero-Email Design)

## Overview

The RÉSIVO web portal **never sends emails** and **never uses email codes, OTPs, magic links, or email-based password recovery**. Brevo, custom SMTP, and Supabase email templates/confirmations are completely disabled.

- **Email is contact information only**: `public.students.email` is required for every new student registration and is saved so the housing office can reach residents offline/externally if needed. It is never used to sign in, verify an account, or reset a password.
- **Validation & uniqueness**: Every student email is trimmed, lowercased, limited to 254 characters, validated for syntax, blocked from internal `@students.residence.local` addresses, and enforced case-insensitively unique (`idx_students_unique_lower_email`).
- **Pending safety preserved**: Newly registered students still start with `status = 'pending'` and remain blocked by RLS from submitting maintenance or room-change requests until approved by housing staff.

## How Flows Work

1. **Student Registration (`/register`)**:
   - Students enter Card ID, academic/personal profile fields, **Email**, **Confirm email**, and password (`>= 8` characters).
   - Client and server validate format, normalization, and matching confirmation (`The emails do not match` / `errors.email_mismatch`).
   - `/api/register` creates the auth account using the hidden synthetic auth address (`<card_id>@students.residence.local`) while passing the real normalized contact email in metadata.
   - `handle_new_user()` verifies `residence_settings.residence_gender`, checks official enrollment eligibility, rejects missing/invalid/duplicate emails (`email_required`, `email_invalid`, `email_in_use`), and writes `public.students.email`.
   - `/api/register` immediately signs out any session returned by `signUp` and redirects to `/login?registered=1` (`Account created. Wait for the housing office to review it.`). Zero emails are sent.

2. **Student & Staff Login (`/login`)**:
   - **Students** enter their **Card ID** and password. `/api/login` calls the `student-login` Edge Function (with local synthetic-email fallback if needed) to resolve `card_id` -> `auth.users.email` (supporting both legacy `<card_id>@students.residence.local` accounts and existing accounts created with a real auth email) and signs in with password.
   - **Staff** enter their staff email and password directly and sign in via `signInWithPassword` without calling `student-login`. Staff workflows in the desktop app are unaffected.
   - **Forgotten passwords**: `/login` displays plain text: *"Forgot your password? Please contact the housing office."* Housing office staff handle password resets administratively (`admin-users` / desktop tooling).

3. **Legacy Students Missing Email (`/account/add-email`)**:
   - After login, web middleware checks `student_has_email()` (or `students.email`).
   - Existing students whose `public.students.email` is `NULL` or empty are redirected to `/account/add-email` to submit Email + Confirm email, saved through `update_my_contact(p_phone, p_email)`, then sent to `/dashboard`.
   - Students who already have a contact email and all staff users are never redirected to `/account/add-email`.

4. **Profile Editing (`/dashboard/profile`)**:
   - Displays **Contact email** (never a "Verified" badge) alongside phone number.
   - Students can update their contact email (with Confirm email validation) and phone via `update_my_contact`.

---

## Cloud Deployment & Cleanup Checklist (Manual Steps)

Do **not** run migration or function deletion commands without first backing up your cloud database!

### 1. Back up the cloud database first
Take a snapshot/backup in the **Supabase Dashboard** (Database -> Backups) or export your schema/data before pushing any database changes.

### 2. Push the migration and updated Edge Function
Run from the repository root against your linked cloud project (`kjqbnurycfjsuufibkac`):

```bash
npx supabase db push
npx supabase functions deploy student-login --no-verify-jwt
```

(Rollback SQL is included in the comments of `supabase/migrations/20261111120000_simple_contact_email.sql`.)

### 3. Delete unused email-sending Edge Functions from cloud

```bash
npx supabase functions delete request-password-reset
npx supabase functions delete request-login-link
npx supabase functions delete link-real-email
```

### 4. Clean up Supabase Dashboard Auth Settings
In **Authentication -> Providers -> Email**:
- Turn **OFF** **Confirm email**.

In **Authentication -> SMTP Settings** (Project Settings / Auth):
- Disable **Custom SMTP** so no external provider is configured.

In **Authentication -> Email Templates**:
- Reset or remove custom HTML templates previously uploaded for confirmation, magic link, recovery, reauthentication, and email change.

In **Authentication -> URL Configuration**:
- Remove unused redirect URLs: `/auth/confirm`, `/reset-password`, `/account/add-email` (plus `/fr/...` variants if added).

### 5. Revoke Brevo Credentials & Clean Hosting Env Vars
1. Log in to **Brevo** and revoke/delete the old SMTP key previously used for RÉSIVO.
2. In your web hosting provider (Vercel / Cloudflare Pages / etc.), remove any `SMTP_*` or Brevo environment variables if present.
3. Redeploy the `web/` application so the new static/SSR bundle and routes are live.

---

## Manual Verification Summary Checklist

See [docs/manual-test-web.md](./manual-test-web.md) for the full test checklist. Key smoke checks:
- [ ] `/register` with mismatched Confirm email is blocked client-side before submission.
- [ ] `/register` with a duplicate email differing only by letter case shows the friendly `email_in_use` message.
- [ ] `/register` with valid inputs creates the pending student, redirects to `/login?registered=1`, and sends zero emails.
- [ ] `/login` signs in students with Card ID + password and has no forgot-password link or sign-in-link button.
- [ ] Legacy student without an email is redirected to `/account/add-email`, saves Email + Confirm email once, and reaches `/dashboard`.
- [ ] `/dashboard/profile` shows **Contact email** (editable with Confirm email) and no `"Verified"` badge.
- [ ] Staff account login still works normally.
- [ ] Supabase Auth logs confirm zero emails were dispatched during all steps above.
