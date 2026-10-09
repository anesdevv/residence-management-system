# Backend & Data Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the Supabase backend for the residence management system: schema, enums, RLS, secure RPC functions, storage bucket, the staff-account Edge Function, seed data, and backend tests.

**Architecture:** Supabase (Postgres + Auth + Storage + REST) is the entire backend. Clients read through the REST API under RLS; sensitive multi-step writes go through `security definer` Postgres functions so business rules live in one place. Staff/admin auth users are created by a service-role Edge Function; students self-register and are materialized by a trigger on `auth.users`.

**Tech Stack:** PostgreSQL (Supabase), Supabase CLI (`npx supabase`), Deno Edge Functions, Python 3.14 + `supabase` (supabase-py v2) + `pytest` for backend tests.

## Global Constraints

- Monorepo root is this repository. Subfolders: `web/`, `desktop/`, `supabase/`, `scripts/`, `tests/`, `docs/`.
- UI/UX text language is English (not relevant to this plan except copy in messages).
- Only the **anon key** may live in client apps; the **service role key** is used only by server-side code (Edge Function) and the local seed script — never committed.
- Supabase free tier; **no Docker** on the dev machine — target a hosted project, apply migrations with `npx supabase db push` (after `npx supabase link`) or the Supabase MCP `apply_migration`.
- All fixed value sets are Postgres enums with exactly these values:
  - `gender`: `male`, `female`
  - `study_level`: `L1`, `L2`, `L3`, `M1`, `M2`, `Doctorat`
  - `user_role`: `student`, `staff`, `admin`
  - `student_status`: `pending`, `active`, `rejected`
  - `report_status`: `pending`, `in_progress`, `resolved`
  - `request_status`: `pending`, `approved`, `rejected`
  - `maintenance_category`: `plumbing`, `electrical`, `furniture`, `internet`, `other`
- Table and column names are exactly as specified in the design spec `docs/superpowers/specs/2026-10-09-residence-management-system-design.md`.
- PowerShell is the shell; use `;` to chain and `.\.venv\Scripts\Activate.ps1` for the venv.

---

## File Structure

- `README.md` — project overview + local setup + how to run migrations/seed/tests.
- `.gitignore` — venv, env files, node/astro build output, supabase temp.
- `.env.example` — template of required env vars (URL, anon key, service role key).
- `docs/erd.md` — entity relationship description (text ERD).
- `supabase/migrations/<ts>_init_enums.sql` — enums.
- `supabase/migrations/<ts>_core_tables.sql` — `profiles`, `staff`, `rooms`, `students`, `set_updated_at()` trigger.
- `supabase/migrations/<ts>_request_tables.sql` — `maintenance_reports`, `room_change_requests`, `official_residents`.
- `supabase/migrations/<ts>_auth_and_helpers.sql` — `handle_new_user()` trigger + `auth_role()`/`is_staff()` helpers.
- `supabase/migrations/<ts>_rpc_functions.sql` — `approve_student`, `reject_student`, `approve_room_change`, `reject_room_change`, `update_my_contact`, `import_official_residents`.
- `supabase/migrations/<ts>_rls_policies.sql` — enable RLS + policies for every table.
- `supabase/migrations/<ts>_storage.sql` — `maintenance-photos` bucket + storage policies.
- `supabase/functions/admin-users/index.ts` — service-role Edge Function to create/list staff.
- `supabase/functions/admin-users/deno.json` — import config for the function.
- `scripts/seed.py` — creates admin/staff/student users and sample rows (uses service role).
- `tests/requirements.txt` — pytest + supabase-py.
- `tests/conftest.py` — fixtures: service client, anon client, staff client, student client.
- `tests/test_rls.py` — RLS behavior tests.
- `tests/test_rpc.py` — RPC behavior tests.

---

## Task 1: Monorepo scaffold, config, and Supabase init

**Files:**
- Create: `README.md`
- Create: `.gitignore`
- Create: `.env.example`
- Create: `supabase/config.toml` (via `npx supabase init`)

**Interfaces:**
- Consumes: nothing.
- Produces: repo skeleton and a linked Supabase project so later tasks can `npx supabase db push`.

- [ ] **Step 1: Create the folder skeleton**

Run (from repo root):
```powershell
New-Item -ItemType Directory -Force -Path web, desktop, scripts, tests, docs | Out-Null
```

- [ ] **Step 2: Write `.gitignore`**

```gitignore
# Python
.venv/
__pycache__/
*.pyc
.pytest_cache/

# Env / secrets
.env
.env.*
!.env.example

# Node / Astro
node_modules/
dist/
.astro/

# Supabase local
supabase/.branches/
supabase/.temp/
supabase/.env

# OS / editors
.DS_Store
Thumbs.db
.vscode/
.idea/
```

- [ ] **Step 3: Write `.env.example`**

```dotenv
SUPABASE_URL=https://YOUR-PROJECT-ref.supabase.co
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
```

- [ ] **Step 4: Write `README.md`**

```markdown
# University Residence Management System (Tlemcen)

Backend: Supabase (Postgres + Auth + Storage).
Websites/clients: `web/` (Astro, students), `desktop/` (PySide6, staff).

## Backend setup
1. `npx supabase login`
2. `npx supabase link --project-ref <your-ref>`
3. `npx supabase db push`          # apply migrations
4. Copy `.env.example` to `.env` and fill in real keys (never commit `.env`).
5. Seed: `python scripts/seed.py`  # needs SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY
6. Tests: `pip install -r tests/requirements.txt` then `python -m pytest tests -v`
```

- [ ] **Step 5: Initialize the Supabase project folder**

Run:
```powershell
npx --yes supabase init
```
Expected: creates `supabase/config.toml` and `supabase/.gitignore`.

- [ ] **Step 6: Link to the hosted project**

Run (interactive; needs your project ref and DB password):
```powershell
npx supabase link --project-ref YOUR-PROJECT-ref
```
Expected: "Finished supabase link."

- [ ] **Step 7: Commit**

```powershell
git add .gitignore .env.example README.md supabase/
git commit -m "chore: scaffold monorepo and init supabase project"
```

---

## Task 2: Enums migration

**Files:**
- Create: `supabase/migrations/<ts>_init_enums.sql` (created via `npx supabase migration new init_enums`)

**Interfaces:**
- Consumes: linked project from Task 1.
- Produces: enum types `gender`, `study_level`, `user_role`, `student_status`, `report_status`, `request_status`, `maintenance_category`.

- [ ] **Step 1: Create the migration file**

Run:
```powershell
npx supabase migration new init_enums
```
Expected: prints the new empty file path under `supabase/migrations/`.

- [ ] **Step 2: Write the enum definitions** into the created file:

```sql
create type gender as enum ('male', 'female');
create type study_level as enum ('L1', 'L2', 'L3', 'M1', 'M2', 'Doctorat');
create type user_role as enum ('student', 'staff', 'admin');
create type student_status as enum ('pending', 'active', 'rejected');
create type report_status as enum ('pending', 'in_progress', 'resolved');
create type request_status as enum ('pending', 'approved', 'rejected');
create type maintenance_category as enum ('plumbing', 'electrical', 'furniture', 'internet', 'other');
```

- [ ] **Step 3: Apply the migration**

Run:
```powershell
npx supabase db push
```
Expected: lists `<ts>_init_enums.sql` as applied with no errors.

- [ ] **Step 4: Verify the types exist**

Using the Supabase SQL editor (or MCP `execute_sql`), run:
```sql
select typname from pg_type where typname in
 ('gender','study_level','user_role','student_status','report_status','request_status','maintenance_category')
order by typname;
```
Expected: 7 rows.

- [ ] **Step 5: Commit**

```powershell
git add supabase/migrations
git commit -m "feat(db): add enum types"
```

---

## Task 3: Core tables + updated_at trigger

**Files:**
- Create: `supabase/migrations/<ts>_core_tables.sql`

**Interfaces:**
- Consumes: enums from Task 2.
- Produces: tables `profiles`, `staff`, `rooms`, `students`, and function `set_updated_at()`.

- [ ] **Step 1: Create the migration**

```powershell
npx supabase migration new core_tables
```

- [ ] **Step 2: Write the schema** into the file:

```sql
create or replace function set_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end; $$;

create table profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  role user_role not null default 'student',
  created_at timestamptz not null default now()
);

create table staff (
  id uuid primary key references profiles(id) on delete cascade,
  full_name text not null,
  position text,
  created_at timestamptz not null default now()
);

create table rooms (
  id uuid primary key default gen_random_uuid(),
  block text not null,
  floor int not null default 0,
  number text not null,
  capacity int not null default 1 check (capacity > 0),
  gender gender not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (block, number)
);

create table students (
  id uuid primary key references profiles(id) on delete cascade,
  card_id text not null unique,
  first_name text not null,
  last_name text not null,
  birth_date date not null,
  gender gender not null,
  phone text not null,
  email text,
  university text not null,
  faculty text not null,
  study_level study_level not null,
  wilaya text not null,
  status student_status not null default 'pending',
  rejection_reason text,
  room_id uuid references rooms(id) on delete set null,
  reviewed_by uuid references staff(id) on delete set null,
  reviewed_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create trigger rooms_set_updated_at before update on rooms
  for each row execute function set_updated_at();
create trigger students_set_updated_at before update on students
  for each row execute function set_updated_at();
```

- [ ] **Step 3: Apply**

```powershell
npx supabase db push
```
Expected: applied with no errors.

- [ ] **Step 4: Verify tables**

```sql
select table_name from information_schema.tables
where table_schema = 'public' and table_name in ('profiles','staff','rooms','students')
order by table_name;
```
Expected: 4 rows.

- [ ] **Step 5: Commit**

```powershell
git add supabase/migrations
git commit -m "feat(db): add core tables and updated_at trigger"
```

---

## Task 4: Request tables + official residents

**Files:**
- Create: `supabase/migrations/<ts>_request_tables.sql`

**Interfaces:**
- Consumes: enums (Task 2), `rooms`/`students` (Task 3), `set_updated_at()` (Task 3).
- Produces: tables `maintenance_reports`, `room_change_requests`, `official_residents`.

- [ ] **Step 1: Create the migration**

```powershell
npx supabase migration new request_tables
```

- [ ] **Step 2: Write the schema**:

```sql
create table maintenance_reports (
  id uuid primary key default gen_random_uuid(),
  student_id uuid not null references students(id) on delete cascade,
  category maintenance_category not null,
  description text not null,
  photo_path text,
  status report_status not null default 'pending',
  staff_note text,
  handled_by uuid references staff(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table room_change_requests (
  id uuid primary key default gen_random_uuid(),
  student_id uuid not null references students(id) on delete cascade,
  current_room_id uuid references rooms(id) on delete set null,
  preferred_room_id uuid references rooms(id) on delete set null,
  reason text not null,
  status request_status not null default 'pending',
  decision_note text,
  decided_by uuid references staff(id) on delete set null,
  decided_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table official_residents (
  id uuid primary key default gen_random_uuid(),
  card_id text not null unique,
  first_name text not null,
  last_name text not null,
  birth_date date,
  gender gender,
  university text,
  faculty text,
  created_at timestamptz not null default now()
);

create trigger maintenance_reports_set_updated_at before update on maintenance_reports
  for each row execute function set_updated_at();
create trigger room_change_requests_set_updated_at before update on room_change_requests
  for each row execute function set_updated_at();
```

- [ ] **Step 3: Apply**

```powershell
npx supabase db push
```
Expected: applied with no errors.

- [ ] **Step 4: Verify**

```sql
select table_name from information_schema.tables
where table_schema='public' and table_name in ('maintenance_reports','room_change_requests','official_residents')
order by table_name;
```
Expected: 3 rows.

- [ ] **Step 5: Commit**

```powershell
git add supabase/migrations
git commit -m "feat(db): add request and official residents tables"
```

---

## Task 5: Auth trigger and role helpers

**Files:**
- Create: `supabase/migrations/<ts>_auth_and_helpers.sql`

**Interfaces:**
- Consumes: `profiles`, `students`, `staff` (Tasks 3–4).
- Produces:
  - `handle_new_user()` trigger on `auth.users` (creates `profiles` row; creates `students` row when `card_id` is present in signup metadata).
  - `auth_role()` → `user_role` of the current user.
  - `is_staff()` → boolean (role is `staff` or `admin`).

- [ ] **Step 1: Create the migration**

```powershell
npx supabase migration new auth_and_helpers
```

- [ ] **Step 2: Write the functions and trigger**:

```sql
-- Role of the currently authenticated user (null if none/no profile).
create or replace function auth_role() returns user_role
language sql stable security definer set search_path = public as $$
  select role from profiles where id = auth.uid();
$$;

-- True when the caller is staff or admin.
create or replace function is_staff() returns boolean
language sql stable security definer set search_path = public as $$
  select coalesce(
    (select role in ('staff','admin') from profiles where id = auth.uid()),
    false);
$$;

-- Materialize a profile for every new auth user.
-- Students self-register with a card_id in metadata; role is ALWAYS 'student'
-- here -- privilege escalation is impossible because metadata.role is ignored.
create or replace function handle_new_user() returns trigger
language plpgsql security definer set search_path = public as $$
begin
  insert into profiles (id, role) values (new.id, 'student');

  if new.raw_user_meta_data ? 'card_id' then
    insert into students (
      id, card_id, first_name, last_name, birth_date, gender, phone, email,
      university, faculty, study_level, wilaya
    ) values (
      new.id,
      new.raw_user_meta_data->>'card_id',
      new.raw_user_meta_data->>'first_name',
      new.raw_user_meta_data->>'last_name',
      (new.raw_user_meta_data->>'birth_date')::date,
      (new.raw_user_meta_data->>'gender')::gender,
      new.raw_user_meta_data->>'phone',
      nullif(new.raw_user_meta_data->>'email', ''),
      new.raw_user_meta_data->>'university',
      new.raw_user_meta_data->>'faculty',
      (new.raw_user_meta_data->>'study_level')::study_level,
      new.raw_user_meta_data->>'wilaya'
    );
  end if;

  return new;
end; $$;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function handle_new_user();
```

- [ ] **Step 3: Apply**

```powershell
npx supabase db push
```
Expected: applied with no errors.

- [ ] **Step 4: Verify the trigger exists**

```sql
select tgname from pg_trigger where tgname = 'on_auth_user_created';
```
Expected: 1 row.

- [ ] **Step 5: Commit**

```powershell
git add supabase/migrations
git commit -m "feat(db): add auth trigger and role helper functions"
```

---

## Task 6: Staff-account Edge Function

**Files:**
- Create: `supabase/functions/admin-users/deno.json`
- Create: `supabase/functions/admin-users/index.ts`

**Interfaces:**
- Consumes: `profiles`, `staff` tables; `is_staff`/role model.
- Produces: Edge Function `admin-users` with actions:
  - `POST { "action": "create_staff", "email", "password", "full_name", "position" }` → creates an auth user (email confirmed) and a `staff` row.
  - `POST { "action": "list_staff" }` → returns staff with emails.
  - Only callers whose `profiles.role = 'admin'` may call it.

- [ ] **Step 1: Write `deno.json`**

```json
{
  "imports": {
    "@supabase/supabase-js": "https://esm.sh/@supabase/supabase-js@2"
  }
}
```

- [ ] **Step 2: Write `index.ts`**

```ts
import { createClient } from "@supabase/supabase-js";

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: CORS });

  const url = Deno.env.get("SUPABASE_URL")!;
  const serviceKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
  const anonKey = Deno.env.get("SUPABASE_ANON_KEY")!;
  const authHeader = req.headers.get("Authorization") ?? "";

  // Identify the caller using their JWT.
  const caller = createClient(url, anonKey, {
    global: { headers: { Authorization: authHeader } },
  });
  const { data: userData } = await caller.auth.getUser();
  if (!userData?.user) {
    return new Response(JSON.stringify({ error: "unauthorized" }), {
      status: 401, headers: { ...CORS, "Content-Type": "application/json" },
    });
  }

  // Only admins may proceed.
  const admin = createClient(url, serviceKey);
  const { data: profile } = await admin
    .from("profiles").select("role").eq("id", userData.user.id).single();
  if (profile?.role !== "admin") {
    return new Response(JSON.stringify({ error: "forbidden" }), {
      status: 403, headers: { ...CORS, "Content-Type": "application/json" },
    });
  }

  const body = await req.json();

  if (body.action === "create_staff") {
    const { email, password, full_name, position } = body;
    if (!email || !password || !full_name) {
      return new Response(JSON.stringify({ error: "email, password, full_name required" }), {
        status: 400, headers: { ...CORS, "Content-Type": "application/json" },
      });
    }
    const { data: created, error } = await admin.auth.admin.createUser({
      email, password, email_confirm: true,
    });
    if (error) {
      return new Response(JSON.stringify({ error: error.message }), {
        status: 400, headers: { ...CORS, "Content-Type": "application/json" },
      });
    }
    await admin.from("profiles").update({ role: "staff" }).eq("id", created.user.id);
    await admin.from("staff").insert({
      id: created.user.id, full_name, position: position ?? null,
    });
    return new Response(JSON.stringify({ id: created.user.id }), {
      status: 201, headers: { ...CORS, "Content-Type": "application/json" },
    });
  }

  if (body.action === "list_staff") {
    const { data } = await admin.from("staff").select("id, full_name, position");
    return new Response(JSON.stringify(data ?? []), {
      headers: { ...CORS, "Content-Type": "application/json" },
    });
  }

  return new Response(JSON.stringify({ error: "unknown action" }), {
    status: 400, headers: { ...CORS, "Content-Type": "application/json" },
  });
});
```

- [ ] **Step 3: Deploy the function**

```powershell
npx supabase functions deploy admin-users
```
Expected: "Deployed Function admin-users".

- [ ] **Step 4: Commit**

```powershell
git add supabase/functions
git commit -m "feat(functions): add admin-users staff management function"
```

---

## Task 7: Secure RPC functions

**Files:**
- Create: `supabase/migrations/<ts>_rpc_functions.sql`

**Interfaces:**
- Consumes: all tables; `auth_role()`, `is_staff()`.
- Produces (all `security definer`, callable via `supabase.rpc(...)`):
  - `approve_student(p_student uuid, p_room uuid) returns students`
  - `reject_student(p_student uuid, p_reason text) returns students`
  - `approve_room_change(p_request uuid, p_room uuid) returns room_change_requests`
  - `reject_room_change(p_request uuid, p_reason text) returns room_change_requests`
  - `update_my_contact(p_phone text, p_email text) returns students`
  - `import_official_residents(p_rows jsonb) returns int`

- [ ] **Step 1: Create the migration**

```powershell
npx supabase migration new rpc_functions
```

- [ ] **Step 2: Write the functions**:

```sql
create or replace function approve_student(p_student uuid, p_room uuid)
returns students language plpgsql security definer set search_path = public as $$
declare s students; r rooms; occ int;
begin
  if not is_staff() then raise exception 'not authorized'; end if;
  select * into s from students where id = p_student for update;
  if s is null then raise exception 'student not found'; end if;
  select * into r from rooms where id = p_room;
  if r is null then raise exception 'room not found'; end if;
  if r.gender <> s.gender then raise exception 'gender mismatch'; end if;
  select count(*) into occ from students
    where room_id = p_room and status = 'active' and id <> p_student;
  if occ >= r.capacity then raise exception 'room full'; end if;
  update students set status = 'active', room_id = p_room, rejection_reason = null,
    reviewed_by = auth.uid(), reviewed_at = now()
  where id = p_student returning * into s;
  return s;
end; $$;

create or replace function reject_student(p_student uuid, p_reason text)
returns students language plpgsql security definer set search_path = public as $$
declare s students;
begin
  if not is_staff() then raise exception 'not authorized'; end if;
  if p_reason is null or length(trim(p_reason)) = 0 then raise exception 'reason required'; end if;
  update students set status = 'rejected', rejection_reason = p_reason, room_id = null,
    reviewed_by = auth.uid(), reviewed_at = now()
  where id = p_student returning * into s;
  if s is null then raise exception 'student not found'; end if;
  return s;
end; $$;

create or replace function approve_room_change(p_request uuid, p_room uuid)
returns room_change_requests language plpgsql security definer set search_path = public as $$
declare req room_change_requests; s students; r rooms; occ int;
begin
  if not is_staff() then raise exception 'not authorized'; end if;
  select * into req from room_change_requests where id = p_request and status = 'pending' for update;
  if req is null then raise exception 'pending request not found'; end if;
  select * into s from students where id = req.student_id;
  select * into r from rooms where id = p_room;
  if r is null then raise exception 'room not found'; end if;
  if r.gender <> s.gender then raise exception 'gender mismatch'; end if;
  select count(*) into occ from students
    where room_id = p_room and status = 'active' and id <> s.id;
  if occ >= r.capacity then raise exception 'room full'; end if;
  update students set room_id = p_room where id = s.id;
  update room_change_requests set status = 'approved', decided_by = auth.uid(),
    decided_at = now(), decision_note = null
  where id = p_request returning * into req;
  return req;
end; $$;

create or replace function reject_room_change(p_request uuid, p_reason text)
returns room_change_requests language plpgsql security definer set search_path = public as $$
declare req room_change_requests;
begin
  if not is_staff() then raise exception 'not authorized'; end if;
  if p_reason is null or length(trim(p_reason)) = 0 then raise exception 'reason required'; end if;
  update room_change_requests set status = 'rejected', decision_note = p_reason,
    decided_by = auth.uid(), decided_at = now()
  where id = p_request and status = 'pending' returning * into req;
  if req is null then raise exception 'pending request not found'; end if;
  return req;
end; $$;

create or replace function update_my_contact(p_phone text, p_email text)
returns students language plpgsql security definer set search_path = public as $$
declare s students;
begin
  update students set phone = p_phone, email = nullif(p_email, '')
  where id = auth.uid() returning * into s;
  if s is null then raise exception 'student not found'; end if;
  return s;
end; $$;

create or replace function import_official_residents(p_rows jsonb)
returns int language plpgsql security definer set search_path = public as $$
declare n int;
begin
  if coalesce(auth_role()::text, '') <> 'admin' then raise exception 'admin only'; end if;
  insert into official_residents (card_id, first_name, last_name, birth_date, gender, university, faculty)
  select x->>'card_id', x->>'first_name', x->>'last_name',
         nullif(x->>'birth_date','')::date,
         nullif(x->>'gender','')::gender,
         x->>'university', x->>'faculty'
  from jsonb_array_elements(p_rows) as x
  on conflict (card_id) do update set
    first_name = excluded.first_name, last_name = excluded.last_name,
    birth_date = excluded.birth_date, gender = excluded.gender,
    university = excluded.university, faculty = excluded.faculty;
  get diagnostics n = row_count;
  return n;
end; $$;

grant execute on function
  approve_student(uuid, uuid),
  reject_student(uuid, text),
  approve_room_change(uuid, uuid),
  reject_room_change(uuid, text),
  update_my_contact(text, text),
  import_official_residents(jsonb)
to authenticated;
```

- [ ] **Step 3: Apply**

```powershell
npx supabase db push
```
Expected: applied with no errors.

- [ ] **Step 4: Verify functions exist**

```sql
select proname from pg_proc where proname in
 ('approve_student','reject_student','approve_room_change','reject_room_change','update_my_contact','import_official_residents')
order by proname;
```
Expected: 6 rows.

- [ ] **Step 5: Commit**

```powershell
git add supabase/migrations
git commit -m "feat(db): add secure rpc functions"
```

---

## Task 8: Row Level Security policies

**Files:**
- Create: `supabase/migrations/<ts>_rls_policies.sql`

**Interfaces:**
- Consumes: all tables; `is_staff()`, `auth_role()`.
- Produces: RLS enabled + policies on every public table.

- [ ] **Step 1: Create the migration**

```powershell
npx supabase migration new rls_policies
```

- [ ] **Step 2: Write the policies**:

```sql
alter table profiles enable row level security;
alter table staff enable row level security;
alter table rooms enable row level security;
alter table students enable row level security;
alter table maintenance_reports enable row level security;
alter table room_change_requests enable row level security;
alter table official_residents enable row level security;

-- profiles: self read, staff read all
create policy profiles_self_select on profiles for select using (id = auth.uid());
create policy profiles_staff_select on profiles for select using (is_staff());

-- staff: staff read all; self read
create policy staff_self_select on staff for select using (id = auth.uid());
create policy staff_staff_select on staff for select using (is_staff());

-- rooms: any authenticated user may read; staff manage
create policy rooms_auth_select on rooms for select using (auth.role() = 'authenticated');
create policy rooms_staff_write on rooms for all using (is_staff()) with check (is_staff());

-- students: self read, staff read/update all
create policy students_self_select on students for select using (id = auth.uid());
create policy students_staff_select on students for select using (is_staff());
create policy students_staff_update on students for update using (is_staff()) with check (is_staff());

-- maintenance_reports: student owns, staff manage
create policy maint_self_select on maintenance_reports for select using (student_id = auth.uid());
create policy maint_self_insert on maintenance_reports for insert
  with check (student_id = auth.uid() and status = 'pending');
create policy maint_staff_all on maintenance_reports for all using (is_staff()) with check (is_staff());

-- room_change_requests: student owns, staff manage
create policy rcr_self_select on room_change_requests for select using (student_id = auth.uid());
create policy rcr_self_insert on room_change_requests for insert
  with check (student_id = auth.uid() and status = 'pending');
create policy rcr_staff_all on room_change_requests for all using (is_staff()) with check (is_staff());

-- official_residents: staff (incl. admin) read; admin write
create policy official_staff_select on official_residents for select using (is_staff());
create policy official_admin_write on official_residents for all
  using (auth_role() = 'admin') with check (auth_role() = 'admin');
```

- [ ] **Step 3: Apply**

```powershell
npx supabase db push
```
Expected: applied with no errors.

- [ ] **Step 4: Verify RLS is enabled everywhere**

```sql
select relname from pg_class
where relnamespace = 'public'::regnamespace and relkind='r' and relrowsecurity = false;
```
Expected: 0 rows (every table has RLS on).

- [ ] **Step 5: Commit**

```powershell
git add supabase/migrations
git commit -m "feat(db): enable rls with policies"
```

---

## Task 9: Storage bucket for maintenance photos

**Files:**
- Create: `supabase/migrations/<ts>_storage.sql`

**Interfaces:**
- Consumes: `is_staff()`.
- Produces: private bucket `maintenance-photos` with policies: students read/write inside their own `<student_id>/` folder, staff read all.

- [ ] **Step 1: Create the migration**

```powershell
npx supabase migration new storage
```

- [ ] **Step 2: Write the bucket + policies**:

```sql
insert into storage.buckets (id, name, public)
values ('maintenance-photos', 'maintenance-photos', false)
on conflict (id) do nothing;

create policy maint_photos_self_read on storage.objects for select
  using (bucket_id = 'maintenance-photos'
         and (storage.foldername(name))[1] = auth.uid()::text);

create policy maint_photos_self_insert on storage.objects for insert
  with check (bucket_id = 'maintenance-photos'
              and (storage.foldername(name))[1] = auth.uid()::text);

create policy maint_photos_staff_read on storage.objects for select
  using (bucket_id = 'maintenance-photos' and is_staff());
```

- [ ] **Step 3: Apply**

```powershell
npx supabase db push
```
Expected: applied with no errors.

- [ ] **Step 4: Verify the bucket**

```sql
select id, public from storage.buckets where id = 'maintenance-photos';
```
Expected: 1 row with `public = false`.

- [ ] **Step 5: Commit**

```powershell
git add supabase/migrations
git commit -m "feat(db): add maintenance photos storage bucket and policies"
```

---

## Task 10: Seed script

**Files:**
- Create: `scripts/seed.py`

**Interfaces:**
- Consumes: all tables + `admin-users` function logic (staff created directly here via service role).
- Produces: an admin (`admin@residence.test` / `Admin1234!`), a staff user (`staff@residence.test` / `Staff1234!`), a sample student (`card_id` `20230001` / `Student1234!` with synthetic email `20230001@students.residence.local`), 3 rooms, and 3 official residents.
- Idempotent: safe to run more than once.

- [ ] **Step 1: Write `scripts/seed.py`**

```python
import os
from datetime import date
from supabase import create_client

URL = os.environ["SUPABASE_URL"]
SERVICE = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
sb = create_client(URL, SERVICE)


def ensure_user(email, password, role, meta=None):
    users = sb.auth.admin.list_users()
    existing = next((u for u in users if u.email == email), None)
    if existing:
        uid = existing.id
    else:
        uid = sb.auth.admin.create_user({
            "email": email, "password": password, "email_confirm": True,
            "user_metadata": meta or {},
        }).user.id
    sb.table("profiles").upsert({"id": uid, "role": role}).execute()
    return uid


def main():
    admin_id = ensure_user("admin@residence.test", "Admin1234!", "admin")
    sb.table("staff").upsert({
        "id": admin_id, "full_name": "Residence Admin", "position": "Administrator",
    }).execute()

    staff_id = ensure_user("staff@residence.test", "Staff1234!", "staff")
    sb.table("staff").upsert({
        "id": staff_id, "full_name": "Amina Staff", "position": "Front desk",
    }).execute()

    rooms = [
        {"block": "A", "floor": 1, "number": "101", "capacity": 2, "gender": "male"},
        {"block": "A", "floor": 1, "number": "102", "capacity": 2, "gender": "male"},
        {"block": "B", "floor": 1, "number": "101", "capacity": 2, "gender": "female"},
    ]
    for r in rooms:
        sb.table("rooms").upsert(r, on_conflict="block,number").execute()

    # Sample student: created via admin API (metadata fills students via trigger).
    ensure_user(
        "20230001@students.residence.local", "Student1234!", "student",
        meta={
            "card_id": "20230001", "first_name": "Yacine", "last_name": "Benali",
            "birth_date": "2003-05-14", "gender": "male", "phone": "0550000001",
            "email": "", "university": "Abou Bekr Belkaid",
            "faculty": "Sciences", "study_level": "L2", "wilaya": "Tlemcen",
        },
    )

    sb.table("official_residents").upsert([
        {"card_id": "20230001", "first_name": "Yacine", "last_name": "Benali",
         "birth_date": "2003-05-14", "gender": "male",
         "university": "Abou Bekr Belkaid", "faculty": "Sciences"},
        {"card_id": "20230002", "first_name": "Nadia", "last_name": "Cherif",
         "birth_date": "2002-11-02", "gender": "female",
         "university": "Abou Bekr Belkaid", "faculty": "Medicine"},
        {"card_id": "20230003", "first_name": "Omar", "last_name": "Tazi",
         "birth_date": "2001-01-20", "gender": "male",
         "university": "Abou Bekr Belkaid", "faculty": "Law"},
    ], on_conflict="card_id").execute()

    print("Seed complete.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the seed**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install supabase
$env:SUPABASE_URL="https://YOUR-PROJECT-ref.supabase.co"
$env:SUPABASE_SERVICE_ROLE_KEY="your-service-role-key"
python scripts/seed.py
```
Expected: prints `Seed complete.`

- [ ] **Step 3: Verify seeded rows**

```sql
select (select count(*) from staff) as staff,
       (select count(*) from rooms) as rooms,
       (select count(*) from students) as students,
       (select count(*) from official_residents) as official;
```
Expected: `staff` ≥ 2, `rooms` = 3, `students` = 1, `official` = 3.

- [ ] **Step 4: Commit**

```powershell
git add scripts/seed.py
git commit -m "chore(seed): add idempotent seed script"
```

---

## Task 11: Backend tests (pytest)

**Files:**
- Create: `tests/requirements.txt`
- Create: `tests/conftest.py`
- Create: `tests/test_rls.py`
- Create: `tests/test_rpc.py`

**Interfaces:**
- Consumes: seeded users from Task 10 and RPC functions from Task 7.
- Produces: passing pytest suite verifying RLS isolation and RPC authorization.

- [ ] **Step 1: Write `tests/requirements.txt`**

```text
supabase==2.9.0
pytest==8.3.3
```

- [ ] **Step 2: Write `tests/conftest.py`** (fixtures log in as seeded users; requires `SUPABASE_URL` and `SUPABASE_ANON_KEY` in the env)

```python
import os
from datetime import date
import pytest

from supabase import create_client

URL = os.environ["SUPABASE_URL"]
ANON = os.environ["SUPABASE_ANON_KEY"]


def _client():
    return create_client(URL, ANON)


@pytest.fixture
def anon_client():
    return _client()


@pytest.fixture
def staff_client():
    c = _client()
    c.auth.sign_in_with_password({"email": "staff@residence.test", "password": "Staff1234!"})
    return c


@pytest.fixture
def student_client():
    c = _client()
    c.auth.sign_in_with_password({
        "email": "20230001@students.residence.local", "password": "Student1234!",
    })
    return c
```

- [ ] **Step 3: Write `tests/test_rls.py`**

```python
def test_anon_cannot_read_students(anon_client):
    resp = anon_client.table("students").select("id").execute()
    assert resp.data == []


def test_student_reads_only_self(student_client):
    resp = student_client.table("students").select("id, card_id").execute()
    assert len(resp.data) == 1
    assert resp.data[0]["card_id"] == "20230001"


def test_staff_reads_all_students(staff_client):
    resp = staff_client.table("students").select("id").execute()
    assert len(resp.data) >= 1


def test_student_cannot_insert_official_residents(student_client):
    resp = student_client.table("official_residents").insert(
        {"card_id": "99999999", "first_name": "Hack", "last_name": "Attempt"}
    ).execute()
    assert resp.data == []
```

- [ ] **Step 4: Write `tests/test_rpc.py`**

```python
def test_student_cannot_approve_student(student_client):
    with pytest.raises(Exception):
        student_client.rpc("approve_student", {"p_student": None, "p_room": None}).execute()


def test_staff_approve_then_reject_flow(staff_client):
    # Find the seeded female room for the seeded male student's gender mismatch check.
    rooms = staff_client.table("rooms").select("id, gender").execute().data
    male_room = next(r["id"] for r in rooms if r["gender"] == "male")
    student = staff_client.table("students").select("id").eq("card_id", "20230001").single().execute().data

    approved = staff_client.rpc("approve_student", {
        "p_student": student["id"], "p_room": male_room,
    }).execute().data
    assert approved["status"] == "active"
    assert approved["room_id"] == male_room
```

Add `import pytest` at the top of `tests/test_rpc.py`.

- [ ] **Step 5: Run the tests**

```powershell
pip install -r tests/requirements.txt
$env:SUPABASE_URL="https://YOUR-PROJECT-ref.supabase.co"
$env:SUPABASE_ANON_KEY="your-anon-key"
python -m pytest tests -v
```
Expected: all tests pass.

- [ ] **Step 6: Commit**

```powershell
git add tests/
git commit -m "test(backend): add rls and rpc tests"
```

---

## Self-Review

**Spec coverage:**
- Tables `profiles`, `staff`, `students`, `rooms`, `maintenance_reports`, `room_change_requests`, `official_residents` — Tasks 3–4. ✅
- Enums, study levels, categories — Task 2. ✅
- Student self-registration via trigger with hidden synthetic email — Task 5 (trigger) + Task 10 (seed demonstrates it). ✅
- Admin-created staff accounts, server-side role assignment — Task 6. ✅
- Sensitive RPCs (approve/reject student, approve/reject room change, update contact, import official list) — Task 7. ✅
- RLS (students self-only, staff all, official list staff-read/admin-write) — Task 8. ✅
- Storage bucket + policies — Task 9. ✅
- Seed data & tests — Tasks 10–11. ✅

**Resolved spec inconsistency:** the spec said `official_residents` is "admin-only read/write," but staff must read it to compare pending accounts. Fixed to **staff/admin read, admin write** (Task 8). The spec file is updated to match.

**Placeholder scan:** no `TBD`/`TODO`; every code step contains full code.

**Type consistency:** `user_role` enum name is used consistently (the spec called the concept `role`; the type is named `user_role` to avoid the `ROLE` keyword, with column `profiles.role`). RPC names/params match between Tasks 7 and 11 (`approve_student`, `reject_student`, `approve_room_change`, `reject_room_change`, `update_my_contact`, `import_official_residents`).

**Deferred to other plans:** website (`web/`) and desktop (`desktop/`) clients, including the Python Supabase client wrapper that the spec's pytest note references; the backend plan's pytest covers the data contract directly.
