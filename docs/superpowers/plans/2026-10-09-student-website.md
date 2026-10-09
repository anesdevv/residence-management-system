# Student Website Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Astro student website: public landing page, registration, card-ID login, and a logged-in dashboard with account status, room info, maintenance reports, room-change requests, and profile editing.

**Architecture:** Astro SSR (`output: 'server'`) deployed to Vercel, styled with Tailwind. Authentication uses `@supabase/ssr` (cookie-based sessions). Pages are server-rendered and read/write Supabase under RLS; sensitive writes call the RPC functions from the backend plan. This plan depends on the backend plan being fully applied and seeded.

**Tech Stack:** Astro 5, `@astrojs/vercel`, Tailwind CSS, `@supabase/ssr` + `@supabase/supabase-js`, TypeScript, Vitest.

## Global Constraints

- The v1 anon key is the only Supabase secret in this app; it is read from env, never hardcoded.
- Student login identifier is **card ID**; it is mapped to the synthetic email `<card_id>@students.residence.local` for Supabase Auth.
- **Disable "Confirm email" in the Supabase project Auth settings** so students can log in immediately after registering (the synthetic email cannot receive mail). Staff accounts are unaffected (created with `email_confirm: true`).
- UI text is English.
- All pages that fetch per-user data set `export const prerender = false`.
- Env vars required: `PUBLIC_SUPABASE_URL`, `PUBLIC_SUPABASE_ANON_KEY`.
- RPC names/params are exactly: `approve_student`, `reject_student`, `approve_room_change`, `reject_room_change`, `update_my_contact(p_phone text, p_email text)`, `import_official_residents`.
- `maintenance-photos` is a **private** bucket; display images via short-lived signed URLs.

---

## File Structure

- `web/package.json`, `web/astro.config.mjs`, `web/tsconfig.json` — project config.
- `web/.env` (gitignored) / `web/.env.example` — env vars.
- `web/src/styles/global.css` — Tailwind import + base styles.
- `web/src/layouts/Layout.astro` — HTML shell, nav, logout.
- `web/src/lib/supabase.ts` — server + browser Supabase clients.
- `web/src/lib/validation.ts` — pure validators (unit-tested).
- `web/src/middleware.ts` — session refresh + route protection.
- `web/src/env.d.ts` — Astro locals typing.
- `web/src/pages/index.astro` — landing.
- `web/src/pages/register.astro` — registration form.
- `web/src/pages/login.astro` — login form.
- `web/src/pages/logout.ts` — sign-out endpoint.
- `web/src/pages/dashboard/index.astro` — status + room.
- `web/src/pages/dashboard/maintenance.astro` — reports list + create.
- `web/src/pages/dashboard/room-change.astro` — requests list + create.
- `web/src/pages/dashboard/profile.astro` — view + edit contact.
- `web/src/pages/api/register.ts`, `login.ts`, `maintenance.ts`, `room-change.ts`, `profile.ts` — form handlers.
- `web/src/lib/validation.test.ts` — Vitest unit tests.

---

## Task 1: Scaffold the Astro app

**Files:**
- Create: `web/` (via Astro CLI), `web/astro.config.mjs`, `web/.env.example`, `web/.gitignore`.

**Interfaces:**
- Consumes: nothing.
- Produces: a runnable Astro SSR project with Tailwind and the Supabase client installed.

- [ ] **Step 1: Create the Astro project**

Run from repo root:
```powershell
npm create astro@latest web -- --template minimal --no-install --no-git --typescript strict
```
Expected: `web/` created.

- [ ] **Step 2: Add the Vercel adapter and Tailwind**

```powershell
npm --prefix web install
npx --prefix web astro add vercel --yes
npx --prefix web astro add tailwind --yes
```

- [ ] **Step 3: Install Supabase libraries**

```powershell
npm --prefix web install @supabase/supabase-js @supabase/ssr
```

- [ ] **Step 4: Set server output in `web/astro.config.mjs`**

```js
// @ts-check
import { defineConfig } from 'astro/config';
import vercel from '@astrojs/vercel';
import tailwind from '@astrojs/tailwind';

export default defineConfig({
  output: 'server',
  adapter: vercel(),
  integrations: [tailwind()],
});
```

- [ ] **Step 5: Write `web/.env.example`**

```dotenv
PUBLIC_SUPABASE_URL=https://YOUR-PROJECT-ref.supabase.co
PUBLIC_SUPABASE_ANON_KEY=your-anon-key
```

- [ ] **Step 6: Run the dev server**

```powershell
Copy-Item web/.env.example web/.env
# then edit web/.env with real values
npm --prefix web run dev
```
Expected: dev server starts on `http://localhost:4321` with the default page.

- [ ] **Step 7: Commit**

```powershell
git add web/
git commit -m "chore(web): scaffold astro app with tailwind and supabase"
```

---

## Task 2: Supabase clients, middleware, and typed locals

**Files:**
- Create: `web/src/lib/supabase.ts`
- Create: `web/src/middleware.ts`
- Create: `web/src/env.d.ts`

**Interfaces:**
- Consumes: env vars from Task 1.
- Produces:
  - `createSupabaseServerClient(context)` → Supabase client bound to request cookies.
  - `createSupabaseBrowserClient()` → browser client.
  - `Astro.locals.user` typed as `User | null`.
  - Middleware that refreshes the session and redirects unauthenticated `/dashboard/*` visits to `/login`.

- [ ] **Step 1: Write `web/src/lib/supabase.ts`**

```ts
import { createServerClient, createBrowserClient, parseCookieHeader, serializeCookieHeader } from '@supabase/ssr';
import type { AstroCookies } from 'astro';

const URL = import.meta.env.PUBLIC_SUPABASE_URL;
const ANON = import.meta.env.PUBLIC_SUPABASE_ANON_KEY;

export function createSupabaseServerClient(
  request: Request,
  cookies: AstroCookies,
) {
  return createServerClient(URL, ANON, {
    cookies: {
      getAll() {
        return parseCookieHeader(request.headers.get('Cookie') ?? '');
      },
      setAll(cookiesToSet) {
        cookiesToSet.forEach(({ name, value, options }) =>
          cookies.set(name, value, { ...options, path: '/' }),
        );
      },
    },
  });
}

export function createSupabaseBrowserClient() {
  return createBrowserClient(URL, ANON);
}

export function cardIdToEmail(cardId: string) {
  return `${cardId.trim()}@students.residence.local`;
}
```

- [ ] **Step 2: Write `web/src/middleware.ts`**

```ts
import { defineMiddleware } from 'astro:middleware';
import { createSupabaseServerClient } from './lib/supabase';

export const onRequest = defineMiddleware(async (context, next) => {
  const supabase = createSupabaseServerClient(context.request, context.cookies);
  const { data } = await supabase.auth.getUser();
  context.locals.user = data.user ?? null;

  if (context.url.pathname.startsWith('/dashboard') && !data.user) {
    return context.redirect('/login');
  }
  return next();
});
```

- [ ] **Step 3: Write `web/src/env.d.ts`**

```ts
/// <reference types="astro/client" />
import type { User } from '@supabase/supabase-js';

declare global {
  namespace App {
    interface Locals {
      user: User | null;
    }
  }
}

declare namespace App {
  interface Locals {
    user: User | null;
  }
}
```

- [ ] **Step 4: Verify it compiles**

```powershell
npm --prefix web run astro -- --help
npx --prefix web astro check
```
Expected: `astro check` reports 0 errors.

- [ ] **Step 5: Commit**

```powershell
git add web/src/lib/supabase.ts web/src/middleware.ts web/src/env.d.ts
git commit -m "feat(web): add supabase ssr clients, middleware, and locals typing"
```

---

## Task 3: Layout, navigation, and landing page

**Files:**
- Create: `web/src/layouts/Layout.astro`
- Modify: `web/src/pages/index.astro`

**Interfaces:**
- Consumes: `Astro.locals.user`.
- Produces: shared layout used by all pages; public landing page.

- [ ] **Step 1: Write `web/src/layouts/Layout.astro`**

```astro
---
import '../styles/global.css';
interface Props { title?: string; }
const { title = 'Residence Tlemcen' } = Astro.props;
const user = Astro.locals.user;
---
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{title}</title>
  </head>
  <body class="min-h-screen bg-slate-50 text-slate-900">
    <header class="border-b bg-white">
      <nav class="mx-auto flex max-w-4xl items-center justify-between px-4 py-3">
        <a href="/" class="font-semibold">Residence Tlemcen</a>
        <div class="flex items-center gap-4 text-sm">
          {user ? (
            <>
              <a href="/dashboard" class="hover:underline">Dashboard</a>
              <a href="/logout" class="hover:underline">Log out</a>
            </>
          ) : (
            <>
              <a href="/login" class="hover:underline">Log in</a>
              <a href="/register" class="rounded bg-slate-900 px-3 py-1.5 text-white">Register</a>
            </>
          )}
        </div>
      </nav>
    </header>
    <main class="mx-auto max-w-4xl px-4 py-8">
      <slot />
    </main>
  </body>
</html>
```

- [ ] **Step 2: Replace `web/src/pages/index.astro`**

```astro
---
import Layout from '../layouts/Layout.astro';
---
<Layout title="Residence Tlemcen">
  <h1 class="text-3xl font-bold">University Residence — Tlemcen</h1>
  <p class="mt-3 text-slate-600">
    Register, track your accommodation status, and submit maintenance or
    room-change requests — all in one place.
  </p>
  <div class="mt-6 flex gap-3">
    <a href="/register" class="rounded bg-slate-900 px-4 py-2 text-white">Register as a resident</a>
    <a href="/login" class="rounded border px-4 py-2">Log in</a>
  </div>
</Layout>
```

- [ ] **Step 3: Verify in the browser**

```powershell
npm --prefix web run dev
```
Expected: visiting `/` shows the heading and the two buttons.

- [ ] **Step 4: Commit**

```powershell
git add web/src/layouts web/src/pages/index.astro
git commit -m "feat(web): add layout and landing page"
```

---

## Task 4: Registration

**Files:**
- Create: `web/src/lib/validation.ts`
- Create: `web/src/pages/register.astro`
- Create: `web/src/pages/api/register.ts`

**Interfaces:**
- Consumes: `createSupabaseServerClient`, `cardIdToEmail`.
- Produces:
  - `validateRegistration(data) → string[]` (list of errors; empty = valid).
  - `POST /api/register` creates an auth user via `signUp` with metadata; the backend trigger fills `profiles` + `students` (status `pending`).

- [ ] **Step 1: Write `web/src/lib/validation.ts`**

```ts
export interface RegistrationInput {
  card_id: string;
  first_name: string;
  last_name: string;
  birth_date: string;
  gender: string;
  phone: string;
  email: string;
  university: string;
  faculty: string;
  study_level: string;
  wilaya: string;
  password: string;
}

const STUDY_LEVELS = ['L1', 'L2', 'L3', 'M1', 'M2', 'Doctorat'];

export function validateRegistration(d: RegistrationInput): string[] {
  const errors: string[] = [];
  if (!/^\d{4,}$/.test(d.card_id.trim())) errors.push('Student card ID must be at least 4 digits.');
  if (!d.first_name.trim()) errors.push('First name is required.');
  if (!d.last_name.trim()) errors.push('Last name is required.');
  if (!/^\d{4}-\d{2}-\d{2}$/.test(d.birth_date)) errors.push('Birth date must be YYYY-MM-DD.');
  if (!['male', 'female'].includes(d.gender)) errors.push('Gender must be male or female.');
  if (!/^[0-9+\s]{6,}$/.test(d.phone)) errors.push('Phone number is invalid.');
  if (d.email.trim() && !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(d.email.trim())) errors.push('Email is invalid.');
  if (!d.university.trim()) errors.push('University is required.');
  if (!d.faculty.trim()) errors.push('Faculty is required.');
  if (!STUDY_LEVELS.includes(d.study_level)) errors.push('Study level is invalid.');
  if (!d.wilaya.trim()) errors.push('Wilaya is required.');
  if (d.password.length < 8) errors.push('Password must be at least 8 characters.');
  return errors;
}
```

- [ ] **Step 2: Write `web/src/pages/api/register.ts`**

```ts
export const prerender = false;
import type { APIRoute } from 'astro';
import { createSupabaseServerClient, cardIdToEmail } from '../../lib/supabase';
import { validateRegistration } from '../../lib/validation';

export const POST: APIRoute = async (context) => {
  const form = await context.request.formData();
  const data = {
    card_id: String(form.get('card_id') ?? ''),
    first_name: String(form.get('first_name') ?? ''),
    last_name: String(form.get('last_name') ?? ''),
    birth_date: String(form.get('birth_date') ?? ''),
    gender: String(form.get('gender') ?? ''),
    phone: String(form.get('phone') ?? ''),
    email: String(form.get('email') ?? ''),
    university: String(form.get('university') ?? ''),
    faculty: String(form.get('faculty') ?? ''),
    study_level: String(form.get('study_level') ?? ''),
    wilaya: String(form.get('wilaya') ?? ''),
    password: String(form.get('password') ?? ''),
  };

  const errors = validateRegistration(data);
  if (errors.length) {
    return context.redirect(`/register?error=${encodeURIComponent(errors[0])}`);
  }

  const supabase = createSupabaseServerClient(context.request, context.cookies);
  const { error } = await supabase.auth.signUp({
    email: cardIdToEmail(data.card_id),
    password: data.password,
    options: {
      data: {
        card_id: data.card_id.trim(),
        first_name: data.first_name.trim(),
        last_name: data.last_name.trim(),
        birth_date: data.birth_date,
        gender: data.gender,
        phone: data.phone.trim(),
        email: data.email.trim(),
        university: data.university.trim(),
        faculty: data.faculty.trim(),
        study_level: data.study_level,
        wilaya: data.wilaya.trim(),
      },
    },
  });

  if (error) {
    return context.redirect(`/register?error=${encodeURIComponent(error.message)}`);
  }
  return context.redirect('/login?registered=1');
};
```

- [ ] **Step 3: Write `web/src/pages/register.astro`**

```astro
---
import Layout from '../layouts/Layout.astro';
export const prerender = false;
const error = Astro.url.searchParams.get('error');
const levels = ['L1', 'L2', 'L3', 'M1', 'M2', 'Doctorat'];
---
<Layout title="Register — Residence Tlemcen">
  <h1 class="text-2xl font-bold">Resident registration</h1>
  {error && <p class="mt-3 rounded bg-red-50 p-3 text-red-700">{error}</p>}
  <form method="POST" action="/api/register" class="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2">
    <label class="flex flex-col gap-1">Student card ID
      <input name="card_id" required class="rounded border p-2" /></label>
    <label class="flex flex-col gap-1">First name
      <input name="first_name" required class="rounded border p-2" /></label>
    <label class="flex flex-col gap-1">Last name
      <input name="last_name" required class="rounded border p-2" /></label>
    <label class="flex flex-col gap-1">Birth date
      <input type="date" name="birth_date" required class="rounded border p-2" /></label>
    <label class="flex flex-col gap-1">Gender
      <select name="gender" required class="rounded border p-2">
        <option value="male">Male</option>
        <option value="female">Female</option>
      </select></label>
    <label class="flex flex-col gap-1">Phone
      <input name="phone" required class="rounded border p-2" /></label>
    <label class="flex flex-col gap-1">Email (optional)
      <input type="email" name="email" class="rounded border p-2" /></label>
    <label class="flex flex-col gap-1">University
      <input name="university" required class="rounded border p-2" /></label>
    <label class="flex flex-col gap-1">Faculty
      <input name="faculty" required class="rounded border p-2" /></label>
    <label class="flex flex-col gap-1">Study level
      <select name="study_level" required class="rounded border p-2">
        {levels.map((l) => <option value={l}>{l}</option>)}
      </select></label>
    <label class="flex flex-col gap-1">Wilaya
      <input name="wilaya" required class="rounded border p-2" /></label>
    <label class="flex flex-col gap-1">Password
      <input type="password" name="password" required minlength="8" class="rounded border p-2" /></label>
    <div class="sm:col-span-2">
      <button type="submit" class="rounded bg-slate-900 px-4 py-2 text-white">Submit registration</button>
    </div>
  </form>
</Layout>
```

- [ ] **Step 4: Manually verify registration**

Start dev server, submit the form with a new card ID, then check the DB:
```sql
select s.card_id, s.status, p.role
from students s join profiles p on p.id = s.id
where s.card_id = '20239999';
```
Expected: one row, `status = pending`, `role = student`.

- [ ] **Step 5: Commit**

```powershell
git add web/src/lib/validation.ts web/src/pages/register.astro web/src/pages/api/register.ts
git commit -m "feat(web): add registration form, validation, and api"
```

---

## Task 5: Login and logout

**Files:**
- Create: `web/src/pages/login.astro`
- Create: `web/src/pages/api/login.ts`
- Create: `web/src/pages/logout.ts`

**Interfaces:**
- Consumes: `createSupabaseServerClient`, `cardIdToEmail`.
- Produces: card-ID login that creates a cookie session and redirects to `/dashboard`; logout clears the session.

- [ ] **Step 1: Write `web/src/pages/api/login.ts`**

```ts
export const prerender = false;
import type { APIRoute } from 'astro';
import { createSupabaseServerClient, cardIdToEmail } from '../../lib/supabase';

export const POST: APIRoute = async (context) => {
  const form = await context.request.formData();
  const cardId = String(form.get('card_id') ?? '').trim();
  const password = String(form.get('password') ?? '');

  const supabase = createSupabaseServerClient(context.request, context.cookies);
  const { error } = await supabase.auth.signInWithPassword({
    email: cardIdToEmail(cardId),
    password,
  });

  if (error) {
    return context.redirect(`/login?error=${encodeURIComponent('Invalid card ID or password.')}`);
  }
  return context.redirect('/dashboard');
};
```

- [ ] **Step 2: Write `web/src/pages/login.astro`**

```astro
---
import Layout from '../layouts/Layout.astro';
export const prerender = false;
const error = Astro.url.searchParams.get('error');
const registered = Astro.url.searchParams.get('registered');
---
<Layout title="Log in — Residence Tlemcen">
  <h1 class="text-2xl font-bold">Log in</h1>
  {registered && <p class="mt-3 rounded bg-green-50 p-3 text-green-700">Registration received. You can log in once your account is reviewed.</p>}
  {error && <p class="mt-3 rounded bg-red-50 p-3 text-red-700">{error}</p>}
  <form method="POST" action="/api/login" class="mt-6 max-w-sm space-y-4">
    <label class="flex flex-col gap-1">Student card ID
      <input name="card_id" required class="rounded border p-2" /></label>
    <label class="flex flex-col gap-1">Password
      <input type="password" name="password" required class="rounded border p-2" /></label>
    <button type="submit" class="rounded bg-slate-900 px-4 py-2 text-white">Log in</button>
  </form>
</Layout>
```

- [ ] **Step 3: Write `web/src/pages/logout.ts`**

```ts
export const prerender = false;
import type { APIRoute } from 'astro';
import { createSupabaseServerClient } from '../lib/supabase';

export const GET: APIRoute = async (context) => {
  const supabase = createSupabaseServerClient(context.request, context.cookies);
  await supabase.auth.signOut();
  return context.redirect('/');
};
```

- [ ] **Step 4: Manually verify**

Log in with the seeded student (`20230001` / `Student1234!`) → redirected to `/dashboard`. Visit `/logout` → session cleared, redirected to `/`.

- [ ] **Step 5: Commit**

```powershell
git add web/src/pages/login.astro web/src/pages/api/login.ts web/src/pages/logout.ts
git commit -m "feat(web): add card-id login and logout"
```

---

## Task 6: Dashboard home (status + room)

**Files:**
- Create: `web/src/pages/dashboard/index.astro`

**Interfaces:**
- Consumes: cookie session from Task 5; `students` and `rooms` tables.
- Produces: page showing status badge, rejection reason when rejected, and room details when active.

- [ ] **Step 1: Write `web/src/pages/dashboard/index.astro`**

```astro
---
import Layout from '../../layouts/Layout.astro';
import { createSupabaseServerClient } from '../../lib/supabase';
export const prerender = false;

const supabase = createSupabaseServerClient(Astro.request, Astro.cookies);
const { data: student } = await supabase
  .from('students')
  .select('first_name, last_name, card_id, status, rejection_reason, room_id, rooms(block, floor, number)')
  .eq('id', Astro.locals.user!.id)
  .single();

const statusColor =
  student?.status === 'active' ? 'bg-green-100 text-green-800'
  : student?.status === 'rejected' ? 'bg-red-100 text-red-800'
  : 'bg-amber-100 text-amber-800';
---
<Layout title="Dashboard — Residence Tlemcen">
  <h1 class="text-2xl font-bold">Welcome, {student?.first_name} {student?.last_name}</h1>

  <div class="mt-4 rounded border bg-white p-4">
    <span class="text-sm text-slate-500">Account status</span>
    <div class="mt-1">
      <span class={`rounded px-2 py-1 text-sm font-medium ${statusColor}`}>{student?.status}</span>
    </div>
    {student?.status === 'rejected' && (
      <p class="mt-2 text-sm text-red-700">Reason: {student.rejection_reason}</p>
    )}
    {student?.status === 'pending' && (
      <p class="mt-2 text-sm text-slate-600">Your registration is awaiting staff review.</p>
    )}
    {student?.status === 'active' && student.rooms && (
      <p class="mt-2 text-sm text-slate-600">
        Room: Block {student.rooms.block}, Floor {student.rooms.floor}, No. {student.rooms.number}
      </p>
    )}
  </div>

  <div class="mt-6 flex gap-3 text-sm">
    <a href="/dashboard/maintenance" class="rounded border px-3 py-2">Maintenance reports</a>
    <a href="/dashboard/room-change" class="rounded border px-3 py-2">Room-change requests</a>
    <a href="/dashboard/profile" class="rounded border px-3 py-2">Profile</a>
  </div>
</Layout>
```

- [ ] **Step 2: Manually verify**

Log in as the seeded student; the page shows their name and `pending` (or `active` if the staff test already approved them). Re-run seed to reset to `pending` if needed.

- [ ] **Step 3: Commit**

```powershell
git add web/src/pages/dashboard/index.astro
git commit -m "feat(web): add dashboard home with status and room"
```

---

## Task 7: Maintenance reports

**Files:**
- Create: `web/src/pages/dashboard/maintenance.astro`
- Create: `web/src/pages/api/maintenance.ts`

**Interfaces:**
- Consumes: `maintenance_reports` table; `maintenance-photos` bucket.
- Produces: list of the student's reports (with signed photo URL) and a create form that uploads a photo then inserts the row.

- [ ] **Step 1: Write `web/src/pages/api/maintenance.ts`**

```ts
export const prerender = false;
import type { APIRoute } from 'astro';
import { createSupabaseServerClient } from '../../lib/supabase';

const CATEGORIES = ['plumbing', 'electrical', 'furniture', 'internet', 'other'];

export const POST: APIRoute = async (context) => {
  const user = context.locals.user!;
  const form = await context.request.formData();
  const category = String(form.get('category') ?? '');
  const description = String(form.get('description') ?? '').trim();
  const photo = form.get('photo');

  if (!CATEGORIES.includes(category) || description.length < 5) {
    return context.redirect('/dashboard/maintenance?error=Invalid+report');
  }

  const supabase = createSupabaseServerClient(context.request, context.cookies);
  let photo_path: string | null = null;

  if (photo instanceof File && photo.size > 0) {
    const ext = photo.name.split('.').pop()?.toLowerCase() || 'jpg';
    const path = `${user.id}/${crypto.randomUUID()}.${ext}`;
    const { error: upErr } = await supabase.storage
      .from('maintenance-photos')
      .upload(path, photo, { contentType: photo.type });
    if (upErr) {
      return context.redirect(`/dashboard/maintenance?error=${encodeURIComponent(upErr.message)}`);
    }
    photo_path = path;
  }

  const { error } = await supabase.from('maintenance_reports').insert({
    student_id: user.id, category, description, photo_path,
  });
  if (error) {
    return context.redirect(`/dashboard/maintenance?error=${encodeURIComponent(error.message)}`);
  }
  return context.redirect('/dashboard/maintenance?created=1');
};
```

- [ ] **Step 2: Write `web/src/pages/dashboard/maintenance.astro`**

```astro
---
import Layout from '../../layouts/Layout.astro';
import { createSupabaseServerClient } from '../../lib/supabase';
export const prerender = false;

const supabase = createSupabaseServerClient(Astro.request, Astro.cookies);
const { data: reports } = await supabase
  .from('maintenance_reports')
  .select('id, category, description, status, staff_note, photo_path, created_at')
  .eq('student_id', Astro.locals.user!.id)
  .order('created_at', { ascending: false });

const withUrls = await Promise.all((reports ?? []).map(async (r) => {
  if (!r.photo_path) return { ...r, url: null };
  const { data } = await supabase.storage.from('maintenance-photos').createSignedUrl(r.photo_path, 300);
  return { ...r, url: data?.signedUrl ?? null };
}));

const error = Astro.url.searchParams.get('error');
const categories = ['plumbing', 'electrical', 'furniture', 'internet', 'other'];
---
<Layout title="Maintenance — Residence Tlemcen">
  <h1 class="text-2xl font-bold">Maintenance reports</h1>
  {error && <p class="mt-3 rounded bg-red-50 p-3 text-red-700">{error}</p>}

  <form method="POST" action="/api/maintenance" enctype="multipart/form-data" class="mt-6 space-y-4 rounded border bg-white p-4">
    <label class="flex flex-col gap-1">Category
      <select name="category" required class="rounded border p-2">
        {categories.map((c) => <option value={c}>{c}</option>)}
      </select></label>
    <label class="flex flex-col gap-1">Description
      <textarea name="description" required rows="3" class="rounded border p-2"></textarea></label>
    <label class="flex flex-col gap-1">Photo (optional)
      <input type="file" name="photo" accept="image/*" /></label>
    <button type="submit" class="rounded bg-slate-900 px-4 py-2 text-white">Submit report</button>
  </form>

  <h2 class="mt-8 text-lg font-semibold">Your reports</h2>
  <ul class="mt-3 space-y-3">
    {withUrls.map((r) => (
      <li class="rounded border bg-white p-4">
        <div class="flex items-center justify-between">
          <span class="font-medium capitalize">{r.category}</span>
          <span class="text-sm text-slate-500">{r.status}</span>
        </div>
        <p class="mt-2 text-slate-700">{r.description}</p>
        {r.staff_note && <p class="mt-2 text-sm text-slate-600">Staff note: {r.staff_note}</p>}
        {r.url && <img src={r.url} alt="report photo" class="mt-3 max-h-48 rounded" />}
      </li>
    ))}
  </ul>
</Layout>
```

- [ ] **Step 3: Manually verify**

Submit a report (with a photo); it appears in the list with `pending`. Confirm the object exists under `maintenance-photos/<user-id>/`.

- [ ] **Step 4: Commit**

```powershell
git add web/src/pages/dashboard/maintenance.astro web/src/pages/api/maintenance.ts
git commit -m "feat(web): add maintenance reports list and creation"
```

---

## Task 8: Room-change requests

**Files:**
- Create: `web/src/pages/dashboard/room-change.astro`
- Create: `web/src/pages/api/room-change.ts`

**Interfaces:**
- Consumes: `room_change_requests` table; `rooms` table.
- Produces: list of the student's requests and a create form (reason + optional preferred room of matching gender).

- [ ] **Step 1: Write `web/src/pages/api/room-change.ts`**

```ts
export const prerender = false;
import type { APIRoute } from 'astro';
import { createSupabaseServerClient } from '../../lib/supabase';

export const POST: APIRoute = async (context) => {
  const user = context.locals.user!;
  const form = await context.request.formData();
  const reason = String(form.get('reason') ?? '').trim();
  const preferred = String(form.get('preferred_room_id') ?? '').trim();

  if (reason.length < 5) {
    return context.redirect('/dashboard/room-change?error=Please+describe+your+reason');
  }

  const supabase = createSupabaseServerClient(context.request, context.cookies);
  const { data: student } = await supabase
    .from('students').select('room_id').eq('id', user.id).single();

  const { error } = await supabase.from('room_change_requests').insert({
    student_id: user.id,
    current_room_id: student?.room_id ?? null,
    preferred_room_id: preferred || null,
    reason,
  });
  if (error) {
    return context.redirect(`/dashboard/room-change?error=${encodeURIComponent(error.message)}`);
  }
  return context.redirect('/dashboard/room-change?created=1');
};
```

- [ ] **Step 2: Write `web/src/pages/dashboard/room-change.astro`**

```astro
---
import Layout from '../../layouts/Layout.astro';
import { createSupabaseServerClient } from '../../lib/supabase';
export const prerender = false;

const supabase = createSupabaseServerClient(Astro.request, Astro.cookies);
const uid = Astro.locals.user!.id;

const { data: student } = await supabase.from('students').select('gender').eq('id', uid).single();
const { data: rooms } = await supabase
  .from('rooms').select('id, block, floor, number, gender').eq('gender', student?.gender ?? 'male')
  .order('block').order('number');

const { data: requests } = await supabase
  .from('room_change_requests')
  .select('id, reason, status, decision_note, preferred_room_id, created_at')
  .eq('student_id', uid).order('created_at', { ascending: false });

const error = Astro.url.searchParams.get('error');
---
<Layout title="Room change — Residence Tlemcen">
  <h1 class="text-2xl font-bold">Room-change requests</h1>
  {error && <p class="mt-3 rounded bg-red-50 p-3 text-red-700">{error}</p>}

  <form method="POST" action="/api/room-change" class="mt-6 space-y-4 rounded border bg-white p-4">
    <label class="flex flex-col gap-1">Reason
      <textarea name="reason" required rows="3" class="rounded border p-2"></textarea></label>
    <label class="flex flex-col gap-1">Preferred room (optional)
      <select name="preferred_room_id" class="rounded border p-2">
        <option value="">No preference</option>
        {(rooms ?? []).map((r) => <option value={r.id}>Block {r.block} — {r.number}</option>)}
      </select></label>
    <button type="submit" class="rounded bg-slate-900 px-4 py-2 text-white">Submit request</button>
  </form>

  <h2 class="mt-8 text-lg font-semibold">Your requests</h2>
  <ul class="mt-3 space-y-3">
    {(requests ?? []).map((r) => (
      <li class="rounded border bg-white p-4">
        <div class="flex items-center justify-between">
          <span class="font-medium">Request</span>
          <span class="text-sm text-slate-500">{r.status}</span>
        </div>
        <p class="mt-2 text-slate-700">{r.reason}</p>
        {r.decision_note && <p class="mt-2 text-sm text-slate-600">Staff note: {r.decision_note}</p>}
      </li>
    ))}
  </ul>
</Layout>
```

- [ ] **Step 3: Manually verify**

Submit a request; it appears as `pending`. The preferred-room list only shows rooms of the student's gender.

- [ ] **Step 4: Commit**

```powershell
git add web/src/pages/dashboard/room-change.astro web/src/pages/api/room-change.ts
git commit -m "feat(web): add room-change requests list and creation"
```

---

## Task 9: Profile (view + edit contact)

**Files:**
- Create: `web/src/pages/dashboard/profile.astro`
- Create: `web/src/pages/api/profile.ts`

**Interfaces:**
- Consumes: `students` table; RPC `update_my_contact(p_phone text, p_email text)`.
- Produces: read-only profile fields plus editable phone/email.

- [ ] **Step 1: Write `web/src/pages/api/profile.ts`**

```ts
export const prerender = false;
import type { APIRoute } from 'astro';
import { createSupabaseServerClient } from '../../lib/supabase';

export const POST: APIRoute = async (context) => {
  const form = await context.request.formData();
  const phone = String(form.get('phone') ?? '').trim();
  const email = String(form.get('email') ?? '').trim();

  if (!/^[0-9+\s]{6,}$/.test(phone)) {
    return context.redirect('/dashboard/profile?error=Invalid+phone');
  }
  if (email && !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) {
    return context.redirect('/dashboard/profile?error=Invalid+email');
  }

  const supabase = createSupabaseServerClient(context.request, context.cookies);
  const { error } = await supabase.rpc('update_my_contact', { p_phone: phone, p_email: email });
  if (error) {
    return context.redirect(`/dashboard/profile?error=${encodeURIComponent(error.message)}`);
  }
  return context.redirect('/dashboard/profile?updated=1');
};
```

- [ ] **Step 2: Write `web/src/pages/dashboard/profile.astro`**

```astro
---
import Layout from '../../layouts/Layout.astro';
import { createSupabaseServerClient } from '../../lib/supabase';
export const prerender = false;

const supabase = createSupabaseServerClient(Astro.request, Astro.cookies);
const { data: s } = await supabase
  .from('students')
  .select('card_id, first_name, last_name, birth_date, gender, phone, email, university, faculty, study_level, wilaya')
  .eq('id', Astro.locals.user!.id).single();

const error = Astro.url.searchParams.get('error');
const updated = Astro.url.searchParams.get('updated');
---
<Layout title="Profile — Residence Tlemcen">
  <h1 class="text-2xl font-bold">Profile</h1>
  {updated && <p class="mt-3 rounded bg-green-50 p-3 text-green-700">Contact details updated.</p>}
  {error && <p class="mt-3 rounded bg-red-50 p-3 text-red-700">{error}</p>}

  <dl class="mt-6 grid grid-cols-2 gap-3 rounded border bg-white p-4 text-sm">
    <div><dt class="text-slate-500">Card ID</dt><dd>{s?.card_id}</dd></div>
    <div><dt class="text-slate-500">Name</dt><dd>{s?.first_name} {s?.last_name}</dd></div>
    <div><dt class="text-slate-500">Birth date</dt><dd>{s?.birth_date}</dd></div>
    <div><dt class="text-slate-500">Gender</dt><dd>{s?.gender}</dd></div>
    <div><dt class="text-slate-500">University</dt><dd>{s?.university}</dd></div>
    <div><dt class="text-slate-500">Faculty</dt><dd>{s?.faculty}</dd></div>
    <div><dt class="text-slate-500">Study level</dt><dd>{s?.study_level}</dd></div>
    <div><dt class="text-slate-500">Wilaya</dt><dd>{s?.wilaya}</dd></div>
  </dl>

  <form method="POST" action="/api/profile" class="mt-6 max-w-sm space-y-4 rounded border bg-white p-4">
    <p class="text-sm text-slate-500">You can edit your phone and email.</p>
    <label class="flex flex-col gap-1">Phone
      <input name="phone" value={s?.phone ?? ''} required class="rounded border p-2" /></label>
    <label class="flex flex-col gap-1">Email (optional)
      <input type="email" name="email" value={s?.email ?? ''} class="rounded border p-2" /></label>
    <button type="submit" class="rounded bg-slate-900 px-4 py-2 text-white">Save</button>
  </form>
</Layout>
```

- [ ] **Step 3: Manually verify**

Change phone → success banner; reload shows the new value. Confirm other fields are read-only.

- [ ] **Step 4: Commit**

```powershell
git add web/src/pages/dashboard/profile.astro web/src/pages/api/profile.ts
git commit -m "feat(web): add profile view and contact editing"
```

---

## Task 10: Validation unit tests

**Files:**
- Create: `web/vitest.config.ts`
- Create: `web/src/lib/validation.test.ts`
- Modify: `web/package.json` (add `test` script)

**Interfaces:**
- Consumes: `validateRegistration` from Task 4.
- Produces: Vitest unit tests for registration validation.

- [ ] **Step 1: Install Vitest**

```powershell
npm --prefix web install -D vitest
```

- [ ] **Step 2: Write `web/vitest.config.ts`**

```ts
import { defineConfig } from 'vitest/config';
export default defineConfig({ test: { environment: 'node' } });
```

- [ ] **Step 3: Write `web/src/lib/validation.test.ts`**

```ts
import { describe, it, expect } from 'vitest';
import { validateRegistration, type RegistrationInput } from './validation';

const base: RegistrationInput = {
  card_id: '20230001', first_name: 'Yacine', last_name: 'Benali',
  birth_date: '2003-05-14', gender: 'male', phone: '0550000001', email: '',
  university: 'Abou Bekr Belkaid', faculty: 'Sciences', study_level: 'L2',
  wilaya: 'Tlemcen', password: 'Student1234!',
};

describe('validateRegistration', () => {
  it('accepts a valid input', () => {
    expect(validateRegistration(base)).toEqual([]);
  });
  it('rejects a short password', () => {
    expect(validateRegistration({ ...base, password: 'short' })).toContain('Password must be at least 8 characters.');
  });
  it('rejects a bad card id', () => {
    expect(validateRegistration({ ...base, card_id: 'abc' })).toContain('Student card ID must be at least 4 digits.');
  });
  it('rejects a bad email when provided', () => {
    expect(validateRegistration({ ...base, email: 'nope' })).toContain('Email is invalid.');
  });
});
```

- [ ] **Step 4: Add the test script to `web/package.json`**

Ensure the `scripts` block contains:
```json
"test": "vitest run"
```

- [ ] **Step 5: Run the tests**

```powershell
npm --prefix web test
```
Expected: 4 tests pass.

- [ ] **Step 6: Commit**

```powershell
git add web/vitest.config.ts web/src/lib/validation.test.ts web/package.json
git commit -m "test(web): add registration validation unit tests"
```

---

## Task 11: Manual end-to-end checklist

**Files:**
- Create: `docs/manual-test-web.md`

**Interfaces:**
- Consumes: the running website + backend.
- Produces: a repeatable checklist used to verify the site before each milestone.

- [ ] **Step 1: Write `docs/manual-test-web.md`**

```markdown
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
```

- [ ] **Step 2: Run through the checklist once and confirm every item passes.**

- [ ] **Step 3: Commit**

```powershell
git add docs/manual-test-web.md
git commit -m "docs: add website manual test checklist"
```

---

## Self-Review

**Spec coverage:**
- Landing page — Task 3. ✅
- Registration fields (card ID, names, birth date, gender, phone, optional email, university, faculty, study level, wilaya, password) — Task 4. ✅
- Card-ID + password login — Task 5. ✅
- Dashboard status / rejection reason / room details — Task 6. ✅
- Maintenance reports (category + description + photo, see status + staff note) — Task 7. ✅
- Room-change requests (reason + optional preferred room, see status + decision note) — Task 8. ✅
- Profile view + edit phone/email via RPC — Task 9. ✅
- In-app only notifications (status shown in pages, no email) — Tasks 6–8. ✅
- English UI — all pages. ✅
- Tests: Vitest for validation (Task 10) + manual E2E (Task 11). ✅

**Placeholder scan:** no `TBD`/`TODO`; every code step contains full code.

**Type consistency:** `cardIdToEmail`, `createSupabaseServerClient(request, cookies)`, and `validateRegistration` signatures match between their definitions and all call sites; RPC `update_my_contact(p_phone, p_email)` matches the backend plan.

**Dependencies:** requires the backend plan applied + seeded, and "Confirm email" disabled in Supabase Auth settings (Global Constraints).
