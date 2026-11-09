# RÉSIVO — Brevo SMTP & Authentication Email Setup Guide

This guide details how authentication emails work in RÉSIVO across local development (Mailpit) and cloud production (Brevo SMTP relay), along with step-by-step instructions for the Supabase Cloud dashboard.

---

## 1. Architecture Overview

RÉSIVO uses Supabase Auth's native SMTP relay integration. All authentication emails:
* **Email Verification (Signup)**
* **Password Reset (Recovery)**
* **Magic Link / One-Time Code Sign-In**
* **Email Change Verification**
* **Identity Re-authentication**

are dispatched directly by Supabase Auth using branded, email-client-safe templates.

The configuration is **provider-neutral**:
* `SMTP_HOST`: The SMTP server host (default: `smtp-relay.brevo.com`).
* `SMTP_PORT`: `587` (STARTTLS) or `465` (SSL).
* `SMTP_USER`: The SMTP login identifier.
* `SMTP_PASS`: The SMTP relay key / password.
* `SMTP_FROM`: The verified sender email address.
* `SMTP_FROM_NAME`: `"RÉSIVO - Cité Universitaire Tlemcen"`.

Any standard SMTP provider (Brevo, AWS SES, Resend, Postmark, SendGrid) can be swapped in without modifying any application code.

---

## 2. Brevo (Sendinblue) Configuration

### Step 1: Create Account & Account Activation
1. Sign up for a free account at [brevo.com](https://www.brevo.com).
2. Brevo free tier includes **300 emails/day** with zero cost.
3. If this is a new account, Brevo might require brief verification of your account details before enabling SMTP relay sending.

### Step 2: Add and Verify Sender Email
1. In the Brevo dashboard, navigate to **Senders, Domains & Dedicated IPs** > **Senders**.
2. Click **Add a sender**.
3. Enter:
   * **Sender Name**: `RÉSIVO - Cité Universitaire Tlemcen`
   * **Sender Email**: The email address you want students to see (e.g. `resivo.dou.tlemcen@gmail.com` or `no-reply@resivo.univ-tlemcen.dz`).
4. Brevo will send a verification link to that email address. Click the link to complete verification.
   > **Note on Deliverability**: If using a free webmail address (such as `@gmail.com`) as sender, outbound emails may be flagged as spam by recipient inboxes. Students should be advised to check their Spam/Junk folder. For maximum deliverability, add a domain you own under **Domains** and configure the Brevo DKIM and SPF DNS TXT records.

### Step 3: Generate SMTP Key
1. In Brevo, click on your account name (top right) and select **SMTP & API**.
2. Open the **SMTP** tab.
3. Note your credentials:
   * **SMTP Server**: `smtp-relay.brevo.com`
   * **Port**: `587`
   * **Login**: Your SMTP login email (e.g. `c22d04001@smtp-brevo.com`). *Note: This is often distinct from your Brevo account email.*
4. Click **Generate a new SMTP key**, provide a name (e.g. `resivo-supabase`), and copy the generated key (`xsmtpsib-...`).
   > **SECURITY**: Never commit this key to version control or include it in client-side code.

---

## 3. Supabase Cloud Project Configuration

Follow these steps in the [Supabase Cloud Dashboard](https://supabase.com/dashboard/project/_):

### A. Configure Custom SMTP Settings
1. Go to **Authentication** > **Emails** > **SMTP Settings**.
2. Toggle **Enable Custom SMTP** to **ON**.
3. Enter the credentials:
   * **Sender email**: Your verified Brevo sender email (e.g. `resivo.dou.tlemcen@gmail.com`).
   * **Sender name**: `RÉSIVO - Cité Universitaire Tlemcen`
   * **Host**: `smtp-relay.brevo.com`
   * **Port number**: `587`
   * **Username**: Your Brevo SMTP Login (e.g. `c22d04001@smtp-brevo.com`)
   * **Password**: Your Brevo SMTP Key (`xsmtpsib-...`)
4. Click **Save**.

### B. Configure URLs & Redirects
1. Go to **Authentication** > **URL Configuration**.
2. Set **Site URL**:
   * Production: `https://resivo.univ-tlemcen.dz` (or your live domain)
   * Local testing: `http://localhost:4321`
3. In **Redirect URLs**, add:
   * `http://localhost:4321/**`
   * `http://127.0.0.1:4321/**`
   * `https://resivo.univ-tlemcen.dz/**`
   * Specifically ensure:
     * `http://localhost:4321/auth/confirm`
     * `http://localhost:4321/reset-password`
     * `http://localhost:4321/dashboard`
     * `http://localhost:4321/account/add-email`
4. Click **Save**.

### C. Enable Email Confirmations & Password Policy
1. Go to **Authentication** > **Providers** > **Email**.
2. Ensure **Confirm email** is enabled (**ON**).
3. Ensure **Secure email change** is set to require confirmation of the new email address only (or double confirmation disabled, so legacy accounts without access to `@students.residence.local` inboxes can transition cleanly).
4. In **Password requirements**, ensure minimum length is set to `8`.

### D. Email Templates
Copy the HTML from `supabase/templates/` into each corresponding template in **Authentication** > **Email Templates**:
* **Confirm signup**: Content from [`supabase/templates/confirmation.html`](file:///c:/Users/Admin/Documents/OpenCode/my%20school%20project%20THE%20MAIN/supabase/templates/confirmation.html)
  * Subject: `Confirm your email address`
* **Reset password**: Content from [`supabase/templates/recovery.html`](file:///c:/Users/Admin/Documents/OpenCode/my%20school%20project%20THE%20MAIN/supabase/templates/recovery.html)
  * Subject: `Reset your password`
* **Magic link**: Content from [`supabase/templates/magic_link.html`](file:///c:/Users/Admin/Documents/OpenCode/my%20school%20project%20THE%20MAIN/supabase/templates/magic_link.html)
  * Subject: `Your one-time sign-in code`
* **Change email address**: Content from [`supabase/templates/email_change.html`](file:///c:/Users/Admin/Documents/OpenCode/my%20school%20project%20THE%20MAIN/supabase/templates/email_change.html)
  * Subject: `Confirm your new email address`

### E. Rate Limits
1. Go to **Authentication** > **Rate Limits**.
2. Increase the email sending limit from default 2–4 emails/hour to at least **30 emails/hour** (or as appropriate for your expected onboarding volume).

---

## 4. Local Development with Mailpit

In local development with Supabase CLI:
1. `supabase/config.toml` has `[auth.email.smtp] enabled = false`.
2. Supabase CLI runs a local Mailpit / Inbucket email catcher on:
   ```
   http://localhost:54324
   ```
3. Whenever an email is sent (signup confirmation, OTP, password recovery, magic link), it is intercepted by Mailpit.
4. Open `http://localhost:54324` in your browser to inspect the full HTML email, verify formatting, and copy the 6-digit OTP code or click the confirmation link.
5. No Brevo daily email quota is consumed while testing locally.

---

## 5. Daily Limits & Error Handling

* **Brevo Free Plan**: **300 emails per 24 hours**.
* If the daily limit is exhausted, Brevo rejects outbound SMTP requests with code `421` / `550`.
* The client UI and Edge Functions catch rate limit exceptions and present a clean notification:
  > *"The email delivery service is currently busy or has reached its daily limit. Please try again tomorrow or contact the residence administration."*
* Resend buttons enforce a client-side 60-second cooldown and a maximum of 5 sends per hour per session.

---

## 6. Switching SMTP Providers

To switch from Brevo to another provider (e.g. AWS SES, Resend, Postmark):
1. In Supabase Cloud Dashboard, open **Authentication** > **Emails** > **SMTP Settings**.
2. Update **Host**, **Port**, **Username**, **Password**, and **Sender Email** to match the new provider.
3. No code modifications or database migrations are required.
