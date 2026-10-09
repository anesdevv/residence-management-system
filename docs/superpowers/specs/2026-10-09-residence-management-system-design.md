# University Residence Management System — Design

**Date:** 2026-10-09
**Status:** Approved (design), pending implementation plan
**Project folder:** `C:\Users\Admin\Documents\OpenCode\my school project THE MAIN`

## 1. Overview

A system for managing a university student residence in Tlemcen, Algeria. It has two
clients that share one backend:

- A **website (Astro)** used by **students** to register, check their account status,
  see their room, and submit maintenance and room-change requests.
- A **desktop app (Python / PySide6)** used by **residence staff** to review pending
  registrations against the official residents list, approve or reject accounts, manage
  rooms and residents, and handle maintenance and room-change requests.

The goal is a polished, complete class project published to GitHub. It should look and
behave like a real system while running entirely on free tiers.

## 2. Context & Constraints

- **Purpose:** primarily a graded class project pushed to GitHub. Not a mandatory
  production deployment, but built as if it could go live: realistic data model,
  real authentication, sensible (not enterprise) security.
- **Budget:** free tiers only (Supabase free tier, Vercel/Cloudflare free tier).
- **Language:** all UI text in **English**.
- **Local development:** Supabase local stack via the Supabase CLI.

## 3. Architecture

- **Backend = Supabase only.** Postgres database, Auth, Storage (maintenance photos),
  and the auto-generated REST API (PostgREST). No self-hosted server is maintained.
- **Website (students):** Astro + Tailwind CSS. Uses the Supabase JS client. Static
  pages for public/marketing/registration; server-rendered where needed for dashboards.
  Default deploy target: **Vercel** (swappable to Cloudflare Pages because the backend is
  Supabase).
- **Desktop (staff):** Python 3 + **PySide6**, talking to Supabase over HTTPS via
  `supabase-py`. Staff authenticate inside the app.
- **Approach:** Hybrid data access — both clients read through the Supabase REST API
  protected by Row-Level Security (RLS), and sensitive multi-step writes go through
  **Postgres functions** (security definer) so business rules live in one place and are
  atomic.

### 3.1 Monorepo layout

```
residence-manager/
  web/            # Astro student website
  desktop/        # PySide6 staff app
  supabase/       # SQL migrations, RLS policies, functions, storage config, seed data
  docs/           # spec, ER diagram, setup guide
  README.md
```

## 4. Data Model

All tables use a `uuid` primary key. Postgres enums are used for the fixed sets below.
Common audit columns (`created_at`, `updated_at`) are present where noted.

| Table | Key fields |
|---|---|
| `profiles` | `id` (= Supabase auth user id), `role` (`student` / `staff` / `admin`), `created_at` |
| `staff` | `id` → `profiles`, `full_name`, `position` |
| `students` | `id` → `profiles`, `card_id` (unique), `first_name`, `last_name`, `birth_date`, `gender`, `phone`, `email` (nullable), `university`, `faculty`, `study_level`, `wilaya`, `status` (`pending` / `active` / `rejected`), `rejection_reason` (nullable), `room_id` (nullable) → `rooms`, `reviewed_by` (nullable) → `staff`, `reviewed_at` (nullable), timestamps |
| `rooms` | `block`, `floor`, `number`, `capacity`, `gender` (`male` / `female`) — occupancy is computed as the count of assigned students |
| `maintenance_reports` | `student_id` → `students`, `category`, `description`, `photo_path` (nullable, Storage), `status` (`pending` / `in_progress` / `resolved`), `staff_note` (nullable), `handled_by` (nullable) → `staff`, timestamps |
| `room_change_requests` | `student_id` → `students`, `current_room_id` → `rooms`, `preferred_room_id` (nullable) → `rooms`, `reason`, `status` (`pending` / `approved` / `rejected`), `decision_note` (nullable), `decided_by` (nullable) → `staff`, `decided_at` (nullable) |
| `official_residents` | `card_id` (unique), `first_name`, `last_name`, `birth_date` (nullable), `gender` (nullable), `university` (nullable), `faculty` (nullable), imported by admin for comparison |

**Enums:** `gender`, `study_level` (`L1`, `L2`, `L3`, `M1`, `M2`, `Doctorat`), `student_status`, `report_status`, `request_status`, `role`, `maintenance_category` (`plumbing`, `electrical`, `furniture`, `internet`, `other`).

**Storage:** one private bucket `maintenance-photos`. Students upload photos for their own
reports; staff can read all.

**Sensitive multi-step writes — Postgres functions (security definer):**

- `approve_student(student_id, room_id)` — sets `status = active`, assigns `room_id`,
  records `reviewed_by` / `reviewed_at`; validates room capacity and gender match.
- `reject_student(student_id, reason)` — sets `status = rejected`, stores `rejection_reason`.
- `approve_room_change(request_id, new_room_id)` — reassigns the student's room atomically,
  marks request `approved`.
- `reject_room_change(request_id, reason)` — marks request `rejected` with `decision_note`.
- `update_my_contact(phone, email)` — lets a student safely update only contact fields.
- `import_official_residents(rows)` — bulk import/replace of the official list (admin only).

## 5. Backend Rules (Auth, RLS, security)

**Authentication**

- **Students:** Supabase Auth using a hidden synthetic email
  (`<card_id>@students.residence.local`) plus a password. The login form accepts
  **card ID + password**; the client maps it to the synthetic email.
  A DB trigger on new auth users creates the `profiles` row (`role = student`) and the
  `students` row with `status = pending`.
- **Staff / admin:** the admin creates accounts (real email + password) through a secured
  server-side call. `role` is set server-side only; clients can never self-assign roles.

**Keys**

- Website and desktop both use the public **anon key**; all access is governed by RLS.
- The **service role key is never shipped** in either client. It is used only for
  privileged admin operations within Supabase (e.g., Edge Function / migration context).

**RLS policies**

- Students: read their own `profiles` / `students` row, their own reports and requests;
  insert maintenance reports and room-change requests; update only via the safe RPC.
- Staff / admin: read all rows; perform approvals/rejections via the Postgres functions.
- `official_residents`: readable by staff and admin (needed to compare pending
  accounts); writable (import/replace) by admin only.

## 6. Website (Student) — Features

- **Public:** landing page (about the residence, Tlemcen); registration form with fields:
  student card ID, first name, last name, birth date, gender, phone, email (optional),
  university, faculty, study level, wilaya, password.
- **Login:** card ID + password.
- **Dashboard:**
  - Account status: `pending` / `active` / `rejected` (+ `rejection_reason` when rejected).
  - Room details when active.
  - **Maintenance reports:** create (category + description + photo), list, see status.
  - **Room-change requests:** create (reason + optional preferred room), list, see status.
  - Profile: view; edit phone/email.

## 7. Desktop (Staff) — Features

Left-nav sections:

1. **Overview** — counts: pending accounts, open reports, pending requests, occupancy.
2. **Pending accounts** — list; selecting a student shows submitted data **side-by-side
   with the official-list match** plus a match / no-match hint; **Approve** (room picker)
   or **Reject** (reason).
3. **Residents** — all active students; search/filter; detail view.
4. **Rooms** — create/edit rooms (block, floor, number, capacity, gender); view occupancy.
5. **Maintenance** — list/filter reports; view photo; set status + note.
6. **Room-change requests** — approve (pick new room) / reject (reason).
7. **Official list** — import Excel/CSV; browse imported entries.
8. **Staff accounts** (admin only) — create staff, manage roles.

## 8. Core Flows

1. **Registration → decision:** student registers → `pending` → staff compare against the
   official list → **Approve** (room assigned, `active`, student now sees their room) or
   **Reject** (reason shown to the student).
2. **Maintenance:** student submits → `pending` → staff set `in_progress` → `resolved`
   (with staff note).
3. **Room change:** student requests → staff **Approve** (room reassigned atomically) or
   **Reject** (reason).

## 9. Non-Goals (Out of Scope)

- Multi-residence / multi-tenant support.
- Email or SMS notifications (status is shown in-app only).
- Payments, billing, or cafeteria management.
- Native mobile apps.
- Bilingual UI / RTL (English only).
- A packaged `.exe` (the desktop app runs via `python main.py`; packaging is optional).

## 10. Testing & Verification

- Develop against **Supabase local** (`supabase start`).
- `supabase/seed.sql` seeds rooms, an admin, staff, and sample students plus an official list.
- Light automated tests:
  - `pytest` for the Python Supabase client wrapper.
  - `vitest` for web form validation logic.
- A written **end-to-end manual checklist** (register → approve → assign room →
  maintenance → room change) executed before each milestone is called done.

## 11. Build Order (Phases)

- **P0** Repo scaffold + Supabase project + README + docs/ERD.
- **P1** Data layer: tables, enums, RLS, functions, storage bucket, auth triggers, seed.
- **P2** Website: registration, login, dashboard, maintenance + room-change forms.
- **P3** Desktop: login, overview, pending accounts (compare + approve/reject), residents, rooms.
- **P4** Desktop: maintenance handling, room-change handling, official-list import, staff accounts.
- **P5** Polish: validation, sample data, screenshots, grading-ready docs.

## 12. Decisions Log

| Decision | Choice |
|---|---|
| Purpose | Class project, published to GitHub |
| Backend | Supabase (Postgres + Auth + Storage + REST) |
| Client data access | Hybrid: RLS for reads, Postgres functions for sensitive writes |
| Repo | Single monorepo |
| Web host | Vercel (swappable to Cloudflare Pages) |
| Student auth | Card ID + password (hidden synthetic email) |
| Staff accounts | Admin-created; roles student / staff / admin |
| Room model | Rooms with capacity, gender-separated; assign on approval |
| Requests | Full workflow for maintenance and room-change requests |
| Notifications | In-app only |
| UI language | English |
| Desktop toolkit | PySide6 (Qt) |
| Official residents list | Imported (Excel/CSV) for in-app comparison |
