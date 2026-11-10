# RÉSIVO Single-Gender Residence Architecture

In Algerian higher-education housing (*Cités Universitaires* under the *Direction des Œuvres Universitaires — DOU*), each residence operates exclusively as either a male residence or a female residence. RÉSIVO models this at the residence level via a singleton configuration table rather than per-block or per-room gender rules.

---

## 1. Database Architecture

Migration: [`supabase/migrations/20261110224500_single_gender_residence.sql`](../supabase/migrations/20261110224500_single_gender_residence.sql)

### Tables
- **`public.residence_settings`** *(singleton `id = 1`)*
  - `residence_name text` (defaults to `'Cité Universitaire · Tlemcen'`)
  - `residence_gender gender` (`'male' | 'female' | NULL` until configured)
  - `updated_at`, `updated_by`
  - **RLS**: Readable by `authenticated`; direct `INSERT`/`UPDATE`/`DELETE` revoked. Mutations run exclusively through admin-gated `SECURITY DEFINER` RPCs.
- **`public.residence_settings_audit`**
  - Records every change to `residence_gender` (`changed_at`, `changed_by`, `old_gender`, `new_gender`, `impact jsonb`).
  - **RLS**: Read-only for administrators (`auth_role() = 'admin'`).

### Functions & Triggers
- **`get_residence_public()`** *(callable by `anon` and `authenticated`)*: Returns only `{residence_name, residence_gender}` so pre-login web registration displays the configured residence type with zero PII exposure.
- **`get_residence_gender_change_impact(p_new_gender text)`** *(admin-only)*: Returns exact counts before any change:
  - `current_gender`, `new_gender`
  - `students_total`, `students_pending`, `students_active`, `students_rejected`
  - `students_with_room` (currently assigned to a room)
  - `students_of_other_gender` (students whose stored `gender` differs from `p_new_gender`)
  - `rooms_total`, `rooms_of_other_gender`
  - `open_room_change_requests`
  - `needs_confirmation` (`true` whenever `students_total > 0` or `students_with_room > 0`)
- **`set_residence_gender(p_gender text, p_confirmation text default null)`** *(admin-only)*:
  - Validates `'male'` or `'female'`.
  - When `needs_confirmation` is `true`, requires exact case-sensitive `p_confirmation = 'CHANGE'`; otherwise raises an error including the live counts.
  - Updates `residence_settings` and writes a row to `residence_settings_audit`.
- **`set_residence_name(p_name text)`** & **`get_residence_settings_admin()`** *(admin-only)*: Edit residence display name and read settings plus latest audit actor/timestamp.
- **Triggers**:
  - `trg_students_set_residence_gender` (`BEFORE INSERT ON public.students`) and updated `handle_new_user()`: Automatically assign `students.gender = residence_settings.residence_gender`. While `residence_gender IS NULL`, registration fails with `"Registration is not open yet"`.
  - `rooms_a_set_residence_gender` (`BEFORE INSERT ON public.rooms`) and `trg_blocks_set_residence_gender` (`BEFORE INSERT ON public.blocks`): Populate legacy `gender` on insert when configured without ever rewriting existing rows on `UPDATE`.
- **Allocation RPCs**: `approve_student` and `approve_room_change` preserve `FOR UPDATE` row locks and bed capacity checks (`occ >= r.capacity`) while dropping the `r.gender <> s.gender` rejection.

---

## 2. Understanding Impact Counts & Historical Data

Why changing `residence_gender` **never** deletes, moves, or overwrites existing records:

1. **Zero destructive side effects**: Switching `residence_gender` is an administrative configuration change for future registrations and staff warnings. Existing `students`, `rooms`, `blocks`, `room_change_requests`, and `maintenance_reports` keep their stored values and room assignments intact.
2. **Legacy column compatibility**: Existing columns `students.gender`, `rooms.gender`, `blocks.gender` (now nullable), and `official_residents.gender` are preserved so reports, exports, and existing code paths never break.
3. **What the typed `CHANGE` counts tell the administrator**:
   - `students_total`, `students_pending`, `students_active`, `students_rejected`: Full student footprint currently in the database.
   - `students_with_room`: Residents currently occupying beds whose housing assignments remain untouched.
   - `students_of_other_gender` / `rooms_of_other_gender`: Historical rows whose stored gender differs from the newly chosen type.

---

## 3. Reviewing Flagged Students (Amber Warning Badge)

After switching a mixed or legacy residence to a single type (or importing an official admissions list containing a different gender marker):

- In **Pending applications (`PendingPage`)** and the **Resident detail card (`StudentInfoCardDialog`)**, any student whose stored `gender` or matched official roster `gender` differs from `residence_gender` displays an amber **"Gender differs from this residence"** (*"Le genre diffère de cette résidence"*) pill badge.
- The badge is **informational only** and never disables room allocation or approval — intake officers review the physical dossier and decide case by case.

---

## 4. Provisioning a New Customer Residence Deployment

Each RÉSIVO deployment (one Supabase project + web portal + desktop console build) serves **one residence**:

1. Apply database migrations (`supabase db push`) against the target Supabase project. `residence_settings` initializes with `id = 1` and `residence_gender = NULL`.
2. Deploy `web/`. Student registration stays safely closed (`"Registration is not open yet"`) until an administrator sets the type.
3. Launch the desktop console and sign in as an `admin`.
4. The first-time setup prompt immediately asks to choose **Male residence** or **Female residence**.
5. Optionally open **Settings → Residence** to set the campus/residence display name, then import the official admissions roster and add blocks/rooms.
