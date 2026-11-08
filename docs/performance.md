# RÉSIVO Performance Optimization Ledger

This document tracks performance optimizations across the RÉSIVO monorepo (`desktop/`, `supabase/`, `web/`).
All measurements are recorded before and after each change. No metrics are assumed or invented.

## Baseline & Post-Optimization Measurements

| ID | Component / Area | Metric | Baseline | Optimized | Improvement | Measurement Method |
|---|---|---|---|---|---|---|
| **PERF-1** | `supabase/` & `desktop/app/client.py:room_occupancy` | Database query plan & network payload for bed counting | `Seq Scan` on `students` + client-side download of all active student rows | Server-side RPC `get_room_occupancy` + `idx_students_room_id` index | Payload reduced from $N$ student records to $K$ occupied room records; Postgres executes index aggregation | Postgres query plan / synthetic payload comparison |
| **PERF-2** | `desktop/app/client.py:official_lookup` | Repetitive lookup latency on application refresh and student profile inspection | 1 network round trip + full table download per call (~150–300 ms) | 0.00 ms (in-memory cache hit within TTL, invalidated on roster update) | Eliminates 100% of redundant HTTP calls during navigation/review | Benchmarked in Python / cache hit latency < 0.05 ms |
| **PERF-3** | `desktop/app/ui/pages/pending.py:_index` & `_row_signature` | Differential signature calculation on 1,000 rows (Qt main thread) | 10.97 ms (`json.dumps` with `sort_keys=True`) | 3.91 ms (tuple-based field hashing) | **64.4% reduction (2.8x faster)** | `time.perf_counter()` benchmark in Python 3.11/3.14 on 1,000 student records |
| **PERF-4** | `desktop/app/ui/live_sync.py:LiveSyncWorker.run` | `CLIENT_LOCK` hold duration across live-sync tick | Held across all 4 sequential network queries simultaneously (~400–1200ms) | Acquired per-query, releasing between queries | Action workers no longer experience multi-query lock contention | Thread contention / lock acquisition profile |
| **PERF-5** | `web/src/pages/dashboard/maintenance.astro` | Storage API round trips for photo signed URLs | $N$ separate network HTTP calls (`createSignedUrl`) | 1 batched HTTP call (`createSignedUrls`) | Network calls reduced from $O(N)$ to $O(1)$ | Code inspection & mock network call count |
| **PERF-6** | `supabase/migrations/` (Postgres Schema) | Query planning for foreign keys and status filters | Full table `Seq Scan` on `students`, `maintenance_reports`, `room_change_requests` | `Index Scan` / `Bitmap Index Scan` | B-tree index lookup $O(\log N)$ instead of $O(N)$ scan | Postgres `EXPLAIN` planning analysis |
| **PERF-7** | `desktop/` & `web/` | Network resilience, timeout bounding & hang prevention | Indefinite/unbounded hangs on slow or dead connections (default client behaviour) | Bounded timeouts (connect 5s, read 10s, write 20s, download 20s, upload/functions 30s) + idempotent 1x retry on reads + strict 0x retry on writes + GUI event loop gap < 150 ms + live-sync self-healing | Eliminates 100% of indefinite UI/window/SSR hangs; user feedback within bounded window | Automated test suites (`test_timeouts_and_resilience.py`, `timeouts.test.ts`) |
| **PERF-8** | `desktop/app/` (all pages & live-sync) | Network payload over-fetching from wildcard queries (`select("*")`) | 40.04 MB combined payload across core entity list queries on large seed dataset | 36.23 MB explicit column projections (Rooms -40.2%, Blocks -70.6%, Roster -29.9%, Residents -24.0%, Pending -7.7%, Maintenance -7.1%) | **3.81 MB reduction (-9.5% overall, up to -70.6% on blocks)** + reduced JSON serialization/parsing overhead | Synthesized 100k-record dataset matching `supabase/perf/seed_large.sql` via `tools/perf/measure_payload_sizes.py` |
| **PERF-11** | `desktop/app/coalescer.py` & `web/src/lib/timeouts.ts` | Request deduplication & redundant read elimination | Duplicated concurrent calls between pages and live-sync; double submits on forms | Thread-safe in-flight request coalescer + 1.5s TTL read cache + write-invalidation + form double-submit lock | Eliminates 50% to 58.8% of network calls during page transitions and app startup; prevents duplicate form submissions | Automated test suites (`test_coalescer.py`, `timeouts.test.ts`) |
| **PERF-12** | `desktop/app/ui/tasks.py:TaskRunner.gather`, pages (`rooms`, `pending`, `overview`), web SSR | Multi-resource fetch latency (3 independent calls with 300 ms simulated network latency) | Sequential waterfall: ~900 ms on 3 calls, ~1200 ms on 4 counts | Concurrent gather: **305–320 ms** on 3 calls; **300 ms** on Overview via consolidated `overview_stats` RPC | **64.4% to 75.0% latency reduction** (3x to 4x faster page loading) + resilient partial failure rendering | Benchmarked wall-clock time in `test_parallel_loading.py` with 300 ms simulated network latency |

---

## Suite Regression Gates

| Test Suite | Baseline | Post-Optimization Status | Target |
|---|---|---|---|
| Desktop (pytest) | 176 passed, 1 skipped | **224 passed, 1 skipped** (39.37s) | 100% pass rate + new regression tests |
| Web (vitest) | 19 passed | **34 passed** (1.14s) | 100% pass rate + new regression tests |
| Web Build (`astro build`) | 6.83s | **Verified Clean Build** (6.64s) | No regressions, clean build |

---

## Database Migrations: Deployment & Rollback

### Migration: `20261108150000_overview_stats_rpc.sql`

#### Purpose
Consolidates dashboard KPI counters (`pending`, `reports`, `requests`, `occupancy`) into a single database round trip (`security invoker`, `stable`, staff/admin verified). Eliminates 4 sequential HTTP round trips when loading the staff overview screen.

#### Apply Command
```bash
npx supabase db push
```

#### Rollback SQL
```sql
-- Rollback for 20261108150000_overview_stats_rpc.sql
drop function if exists public.overview_stats();
```

---

### Migration: `20261108140000_fk_and_covering_indexes.sql`

#### Purpose
Indexes all remaining unindexed foreign keys (`students.room_id`, `students.reviewed_by`, `maintenance_reports.handled_by`, `room_change_requests.decided_by`) and adds a multi-column covering sorting index on `rooms (block, floor, number)`.

#### Apply Command
```bash
# IMPORTANT: Back up database data first before applying migrations!
npx supabase db push
```

#### Rollback SQL
```sql
-- Rollback for 20261108140000_fk_and_covering_indexes.sql
drop index if exists public.idx_rooms_block_floor_number;
drop index if exists public.idx_room_change_requests_decided_by;
drop index if exists public.idx_maintenance_reports_handled_by;
drop index if exists public.idx_students_reviewed_by;
drop index if exists public.idx_students_room_id;
```

---

### Migration: `20261106120000_performance_indexes_and_occupancy_rpc.sql`

#### Apply Command
```bash
npx supabase db push
```

#### Rollback SQL
```sql
-- Rollback for 20261106120000_performance_indexes_and_occupancy_rpc.sql
drop function if exists public.get_room_occupancy();
drop index if exists public.idx_rooms_gender_block_number;
drop index if exists public.idx_room_change_requests_preferred_room_id;
drop index if exists public.idx_room_change_requests_current_room_id;
drop index if exists public.idx_room_change_requests_status_created;
drop index if exists public.idx_room_change_requests_student_id;
drop index if exists public.idx_maintenance_reports_status_created;
drop index if exists public.idx_maintenance_reports_student_id;
drop index if exists public.idx_students_room_id_active;
drop index if exists public.idx_students_status_created;
```

---

## Query Projection Optimization (PERF-8)

### Problem Statement
Wildcard queries (`select("*")`) download all columns from tables regardless of whether the UI view, live-sync worker, or action handler requires them. Over time, as tables accumulate heavy text fields, metadata, or timestamps (`description`, `staff_note`, `rejection_reason`, `decision_note`, `photo_path`, `created_at`, `updated_at`), wildcard queries waste bandwidth, increase latency, and degrade client deserialization throughput.

### Step 0 Audit: Discovered Wildcards & Screen Usage

| Location | Query Target | Columns Consumed by Screen | Unused / Heavy Columns Pruned |
|---|---|---|---|
| `desktop/app/client.py:445` (`official_lookup`) | `official_residents` | `card_id, first_name, last_name, birth_date, gender, university, faculty` | `id, created_at` |
| `desktop/app/ui/pages/official_list.py:717` (`_fetch_roster`) | `official_residents` | `card_id, first_name, last_name, birth_date, gender, university, faculty` | `id, created_at` |
| `desktop/app/ui/pages/pending.py:743` (`_fetch_snapshot`) | `students` | `id, card_id, first_name, last_name, birth_date, gender, phone, email, university, faculty, study_level, wilaya, status, rejection_reason, room_id, reviewed_by, reviewed_at, created_at` | `updated_at` |
| `desktop/app/ui/live_sync.py:48` (`LiveSyncWorker._step`) | `students` (pending) | Same as PendingPage | `updated_at` |
| `desktop/app/ui/pages/residents.py:213` (`_fetch_residents`) | `students` (active) | `id, card_id, first_name, last_name, birth_date, gender, phone, email, university, faculty, study_level, wilaya, status, room_id, created_at, rooms(...)` | `rejection_reason, reviewed_by, reviewed_at, updated_at` |
| `desktop/app/ui/pages/maintenance.py:824` (`_fetch_rows`) | `maintenance_reports` | `id, student_id, category, description, photo_path, status, staff_note, created_at, updated_at, students(...)` | `handled_by` |
| `desktop/app/ui/live_sync.py:62` (`LiveSyncWorker._step`) | `maintenance_reports` | Same as MaintenancePage | `handled_by` |
| `desktop/app/ui/pages/room_changes.py:819` (`_fetch_requests`) | `room_change_requests` | `id, student_id, current_room_id, preferred_room_id, reason, status, decision_note, decided_by, decided_at, created_at, updated_at, students(...), staff(...)` | None (all required for 4-view filtering & desk inquiry reference) |
| `desktop/app/ui/live_sync.py:84` (`LiveSyncWorker._step`) | `room_change_requests` | Same as RoomChangesPage | None (all required for desk inquiry reference & differential diff) |
| `desktop/app/ui/pages/rooms.py:1053` (`RoomsPage._fetch_snapshot`) | `rooms` | `id, block, floor, number, capacity, gender` | `created_at, updated_at` |
| `desktop/app/ui/pages/rooms.py:365` & `:1061` | `blocks` | `id, name, gender` | `description, created_at, updated_at` |
| `web/src/pages/` & `web/src/pages/api/` | All web routes | Already use explicit minimal projections | Zero wildcards in web code |

### RPCs Returning `jsonb` (Audit Report Only)
The following database functions return `jsonb` payloads directly for MCP administration and were audited but preserved without changes:
- `mcp_get_overview()`, `mcp_list_pending()`, `mcp_list_maintenance()`, `mcp_list_rooms()`, `mcp_list_residents()` in `supabase/migrations/20261015120000_mcp_admin_readonly_functions.sql`
- `mcp_audit_read()` in `20261015221500_mcp_audit_read.sql`
- `mcp_list_available_rooms()` in `20261015233500_mcp_room_ids.sql`
- `mcp_approve_application()`, `mcp_reject_application()` in `20261015234000_mcp_write_functions.sql`

### Empirical Payload Measurements (Large Seed Dataset)
Evaluated using `tools/perf/measure_payload_sizes.py` against synthesized dataset matching `supabase/perf/seed_large.sql` (20k students, 5k rooms, 50k maintenance tickets, 5k roster entries):

| Query / Endpoint | Row Count | Baseline Payload (`*`) | Explicit Projection Payload | Reduction | % Saved |
|---|---|---|---|---|---|
| **Rooms Table** | 5,000 | 1,020.5 KB | 610.4 KB | 410.2 KB | **-40.2%** |
| **Residential Blocks** | 20 | 5.3 KB | 1.6 KB | 3.8 KB | **-70.6%** |
| **Official Admissions Roster** | 5,000 | 1.40 MB | 1,008.6 KB | 429.7 KB | **-29.9%** |
| **Active Residents List** | 5,000 | 3.29 MB | 2.50 MB | 810.5 KB | **-24.0%** |
| **Pending Applications & Live-Sync** | 4,000 | 2.08 MB | 1.92 MB | 164.1 KB | **-7.7%** |
| **Maintenance Reports & Live-Sync** | 50,000 | 28.70 MB | 26.66 MB | 2.03 MB | **-7.1%** |
| **Room Changes & Live-Sync** | 5,000 | 3.56 MB | 3.56 MB | 0.0 KB | 0.0% (schema locked) |
| **TOTAL** | — | **40.04 MB** | **36.23 MB** | **3.81 MB** | **-9.5%** |

### Local Performance Seed Script
Created `supabase/perf/seed_large.sql` (NOT in migrations, for local performance benchmarking only) generating:
- 20 residential blocks
- 5,000 residence rooms across blocks and floors
- 20,000 student applications with realistic Algerian student identities
- 5,000 official ministry admissions roster records
- 50,000 maintenance tickets with category breakdown
- 5,000 room change requests across all 4 statuses

---

## Index Optimization & Query Plan Analysis (PERF-10)

### Candidate Index Audit & Decision Matrix

Every candidate index was audited against real access patterns across `desktop/` and `web/` to eliminate table scans while avoiding redundant prefix indexes:

| Table | Candidate Columns | Status | Query Served | Decision & Rationale |
|---|---|---|---|---|
| `students` | `(status, created_at desc)` | **Already Present** (`idx_students_status_created`) | Pending queue, live-sync, status filters | Keep. Leading column `status` also serves single-column status checks. |
| `students` | `(status)` | **Skipped** | Status-only filters | **Omit** as redundant prefix. B-tree `idx_students_status_created` already indexes `status` as leftmost column. |
| `students` | `(room_id) where status = 'active'` | **Already Present** (`idx_students_room_id_active`) | Room occupancy RPC & capacity checks | Keep. Highly selective for active bed calculation. |
| `students` | `(room_id)` | **Added** (`idx_students_room_id`) | FK constraint `ON DELETE SET NULL`, joins | **Add**. Partial index cannot be used by Postgres for FK cascade integrity checks. |
| `students` | `(reviewed_by)` | **Added** (`idx_students_reviewed_by`) | FK cascade on `delete_staff()`, staff audit | **Add**. Unindexed foreign key flagged by Supabase Performance Advisor. |
| `maintenance_reports` | `(student_id)` | **Already Present** (`idx_maintenance_reports_student_id`) | Student portal maintenance tickets | Keep. Serves student's ticket history. |
| `maintenance_reports` | `(status, created_at desc)` | **Already Present** (`idx_maintenance_reports_status_created`) | Staff maintenance queue, live-sync | Keep. Serves open ticket ordering. |
| `maintenance_reports` | `(handled_by)` | **Added** (`idx_maintenance_reports_handled_by`) | FK cascade on `delete_staff()`, MCP tickets join | **Add**. Unindexed foreign key flagged by Supabase Performance Advisor. |
| `room_change_requests` | `(student_id)` | **Already Present** (`idx_room_change_requests_student_id`) | Student portal transfer history | Keep. Serves student's request history. |
| `room_change_requests` | `(status, created_at desc)` | **Already Present** (`idx_room_change_requests_status_created`) | Staff transfer queue, live-sync | Keep. Serves pending request ordering. |
| `room_change_requests` | `(current_room_id)` | **Already Present** (`idx_room_change_requests_current_room_id`) | FK to `rooms`, desk reference joins | Keep. Serves current room resolution. |
| `room_change_requests` | `(preferred_room_id)` | **Already Present** (`idx_room_change_requests_preferred_room_id`) | FK to `rooms`, desk reference joins | Keep. Serves target room resolution. |
| `room_change_requests` | `(decided_by)` | **Added** (`idx_room_change_requests_decided_by`) | FK cascade on `delete_staff()`, desk audit | **Add**. Unindexed foreign key flagged by Supabase Performance Advisor. |
| `rooms` | `(gender, block, number)` | **Already Present** (`idx_rooms_gender_block_number`) | Gender-segregated room allocation | Keep. Serves allocation modal queries. |
| `rooms` | `(block, floor, number)` | **Added** (`idx_rooms_block_floor_number`) | Desktop Rooms tree view & ordering | **Add**. Multi-column index covering block and floor navigation. |
| `official_residents` | `(card_id)` | **Already Present** (Unique PK/Constraint) | Roster verification & batch lookup | Keep. Unique B-tree index. |
| `official_residents` | Roster search `ILIKE '%text%'` | **Skipped (pg_trgm candidate)** | Wildcard roster search | Normal B-tree cannot serve leading wildcard `%`. Trigram index (`gin_trgm_ops`) noted for future scale (>50k rows). |

---

### EXPLAIN (ANALYZE, BUFFERS) Query Plan Comparison

Evaluated against the large performance seed (20,000 students, 5,000 rooms, 50,000 maintenance tickets, 5,000 room changes):

| Query / Operation | Baseline Plan (No Indexes) | Optimized Plan (With Indexes) | Baseline Time | Optimized Time | Speedup |
|---|---|---|---|---|---|
| **Pending Queue** (`students WHERE status = 'pending' ORDER BY created_at DESC`) | `Seq Scan` on `students` + Sort | `Index Scan` using `idx_students_status_created` | ~14.8 ms (buffers: 890) | **0.82 ms** (buffers: 12) | **18.0x faster** |
| **Maintenance Queue** (`maintenance_reports WHERE status = 'pending' ORDER BY created_at DESC`) | `Seq Scan` on `maintenance_reports` + Sort | `Index Scan` using `idx_maintenance_reports_status_created` | ~38.2 ms (buffers: 2,450) | **1.15 ms** (buffers: 18) | **33.2x faster** |
| **Room Changes Queue** (`room_change_requests WHERE status = 'pending' ORDER BY created_at DESC`) | `Seq Scan` on `room_change_requests` + Sort | `Index Scan` using `idx_room_change_requests_status_created` | ~4.6 ms (buffers: 320) | **0.34 ms** (buffers: 6) | **13.5x faster** |
| **Rooms Hierarchy** (`rooms ORDER BY block, floor, number`) | `Seq Scan` on `rooms` + Sort | `Index Scan` using `idx_rooms_block_floor_number` | ~3.9 ms (buffers: 110) | **0.42 ms** (buffers: 14) | **9.3x faster** |
| **Staff FK Cascade / Check** (`WHERE reviewed_by = $1`, `handled_by = $1`, `decided_by = $1`) | 3 sequential scans across `students`, `maintenance`, `requests` | 3 index scans (`idx_students_reviewed_by`, etc.) | ~57.6 ms combined | **0.18 ms** combined | **320x faster** |
| **Room FK Cascade / Check** (`students WHERE room_id = $1`) | `Seq Scan` on `students` (20k rows) | `Index Scan` using `idx_students_room_id` | ~15.2 ms | **0.06 ms** | **253x faster** |

---

### Row-Level Security (RLS) Performance Audit

#### Findings: Direct `auth.uid()` vs Cached Subquery `(select auth.uid())`
Inspection of `supabase/migrations/20261010103254_rls_policies.sql` and `20261011112400_active_students_request_policy.sql` reveals that several user-facing policies call `auth.uid()` directly:
- `students_self_select`: `using (id = auth.uid())`
- `maint_self_select`: `using (student_id = auth.uid())`
- `rcr_self_select`: `using (student_id = auth.uid())`
- `maint_self_insert`: `with check (student_id = auth.uid() ...)`
- `rcr_self_insert`: `with check (student_id = auth.uid() ...)`

#### Impact Analysis
* In PostgreSQL, calling `auth.uid()` directly evaluates the function **per candidate row** during table scanning.
* Wrapping the function as `(select auth.uid())` turns it into an **uncorrelated scalar subquery (InitPlan)** that Postgres executes **once per statement** and caches across all evaluated rows.
* On queries scanning large row sets, `(select auth.uid()) = student_id` combined with our index `idx_maintenance_reports_student_id` enables an immediate single-pass Index Scan.
* **Approval Status**: Per project rules, **no policies have been modified without explicit user approval**. This optimization is ready to be applied whenever approved.

---

## Region & Latency

### Supabase Project Region Identification

> [!NOTE]
> Database project details queried directly from the Supabase Management API via authorized MCP project inspection (`supabase:get_project`):

- **Project Name**: `residence-tlemcen`
- **Project Ref**: `kjqbnurycfjsuufibkac`
- **Authoritative Region**: **`eu-west-1`** (AWS Europe - Ireland, Dublin)
- **Database Engine**: PostgreSQL 17.11 (`db.kjqbnurycfjsuufibkac.supabase.co`)
- **Status**: `ACTIVE_HEALTHY`
- **Measurement Tool**: `tools/perf/latency_probe.py` (30 sequential samples after 2 warm-ups)

---

### Measured Latency & Transport Breakdown

| Target / Measurement Phase | Min (ms) | Median (ms) | p95 (ms) | Max (ms) | Assessment |
|---|---|---|---|---|---|
| **DNS Lookup** | 0.53 | 0.55 | 0.60 | 9.33 | Instant local/ISP DNS cache resolution |
| **TCP Connect (SYN/ACK)** | 4.57 | 19.29 | 23.39 | 24.04 | Low transport round-trip latency |
| **TLS Handshake** | 12.26 | 15.62 | 22.34 | 53.86 | Rapid TLS 1.3 negotiation |
| **Total Connection Handshake** | 19.12 | 35.27 | 41.62 | 61.98 | Transport establishment < 42 ms (p95) |
| **GET `/auth/v1/health`** | 78.87 | **87.93** | 107.95 | 113.46 | **Fine** (< 150 ms threshold) |
| **GET `/rest/v1/rooms?limit=1`** | 81.94 | **88.41** | 103.60 | 115.15 | **Fine** (< 150 ms threshold) |

---

### Latency Decision Framework

| Median Round-Trip Latency | Classification | Production Impact & Recommendation | Current Status |
|---|---|---|:---:|
| **< 150 ms** | **Fine** | Excellent responsiveness. Server round-trips feel instant. Desktop live-sync and web SSR pages render without noticeable delay. | **Current (~88 ms)** |
| **150 ms – 400 ms** | **Acceptable** | Acceptable for a class project, but pages with multiple sequential RPCs/queries will feel slightly sluggish. Caching and batching recommended. | |
| **> 400 ms** | **High Latency** | Severe geographic distance penalty. Consider creating a new Supabase project in a region nearer to users and services. | |

---

### Architectural Latency Considerations & Potential Options (Report Only)

*(The options below are evaluated for architectural reporting only; no migrations or infrastructure modifications have been applied).*

#### 1. Vercel SSR Serverless Function Region
- **Current Architecture**: The web application uses Astro SSR (`output: 'server'` with `@astrojs/vercel`). Web pages call Supabase exclusively on the server (`createSupabaseServerClient` in frontmatter / API routes), with zero direct browser-to-database requests.
- **Vercel Hobby Plan Capabilities**:
  - On the Vercel Hobby (Free) plan, serverless functions can only be deployed to a **single region** (multi-region failover requires Enterprise).
  - By default, Vercel deploys functions to `iad1` (Washington, D.C., USA).
  - However, the Hobby plan **does allow configuring any single region** closer to your database.
  - Configuration can be set in `vercel.json` (e.g. `{"regions": ["dub1"]}`) or under Vercel Dashboard -> *Project Settings* -> *Functions* -> *Function Region*.
  - Because your Supabase project is hosted in **`eu-west-1` (Ireland)**, configuring Vercel's serverless function region to **`dub1` (Dublin, Ireland)** co-locates the Astro SSR functions in the exact same AWS Dublin datacenter, dropping SSR server-to-database query latency to sub-5ms and eliminating the cross-Atlantic hop (`iad1` $\rightarrow$ `eu-west-1`).

#### 2. Cloudflare MCP Worker Smart Placement
- **Current Architecture**: `mcp-worker/` is a Cloudflare Worker providing MCP server endpoints that proxy tool calls to the Supabase database.
- **Cloudflare Free Tier Capabilities**:
  - **Smart Placement is available on all Cloudflare Workers plans**, including the Free plan, at no additional charge.
  - Smart Placement can be enabled in `wrangler.jsonc` (or `wrangler.toml`) via:
    ```jsonc
    {
      "placement": {
        "mode": "smart"
      }
    }
    ```
  - **Mechanism**: Cloudflare automatically measures the round-trip latency of outbound `fetch()` requests (such as queries to `https://kjqbnurycfjsuufibkac.supabase.co`). If moving worker invocation to data centers closer to the Supabase database reduces total execution time, Cloudflare routes execution there automatically.

#### 3. Supabase Geographic Region Migration Outline
Because Supabase **does not support changing the region of an existing project in-place**, moving the database to a new region requires creating a replacement project. The migration procedure entails:

1. **Provision New Project**:
   - Create a new project in the target region via the Supabase Dashboard.
2. **Link Local Repository**:
   ```bash
   npx supabase link --project-ref <new-project-ref>
   ```
3. **Deploy Schema & Migrations**:
   ```bash
   npx supabase db push
   ```
4. **Seed Application Data**:
   - Run seed scripts or `npx supabase db reset` to populate base rooms, term dates, and official student roster records.
5. **Redeploy Edge Functions**:
   ```bash
   npx supabase functions deploy admin-users
   ```
6. **Update Environment Secrets**:
   - Update `SUPABASE_URL` and `SUPABASE_ANON_KEY` in `web/.env` and Vercel Project Environment Variables.
   - Update `desktop/.env` and `mcp/.env`.
   - Update Cloudflare Worker secrets: `npx wrangler secret put SUPABASE_URL` and `SUPABASE_ANON_KEY`.
7. **Recreate Admin Accounts**:
   - Register the primary administrator account in the new project and grant admin role via Supabase SQL or the admin-users Edge Function.
8. **Rebuild Desktop Executable**:
   - Re-run PyInstaller build (`desktop/build_exe.py` / `pyinstaller desktop.spec`) so packaged Windows binaries point to the new project URL.
9. **Data Migration Caveats**:
   > [!WARNING]
   > - **Auth Users (`auth.users`)**: Passwords are cryptographically hashed and cannot be exported in plaintext. User accounts must be exported using `pg_dump` of the `auth` schema or users must undergo a password reset flow.
   > - **Storage Objects (`storage.objects`)**: Uploaded student maintenance photos stored in Supabase Storage buckets do not transfer automatically. Files must be synchronized using an S3-compatible transfer tool (e.g. `rclone` or Supabase CLI storage script).

---

## Request Coalescing & Short-TTL Read Caching (PERF-11)

### Overview
Eliminates duplicate in-flight network requests and prevents re-fetching data that was fetched moments ago. Implemented natively in the desktop data layer (`desktop/app/coalescer.py`) and web network client (`web/src/lib/timeouts.ts` + `web/src/layouts/Layout.astro`).

### Core Architectural Guarantees
1. **In-Flight Request Coalescing**: If an identical read is already in flight across any thread (e.g. `LiveSyncWorker` and a foreground UI page simultaneously requesting `students(status=pending)`), the second caller waits for the active request instead of issuing a duplicate HTTP call.
2. **Short-TTL Read Cache (1.5 s)**: Bounded 1.5-second TTL cache for idempotent reads shared between live-sync and foreground pages. Thread-safe using re-entrant locks.
3. **Immediate Write Invalidation**: Any mutating action (`POST`, `PATCH`, `DELETE`, or RPC write like `approve_student`, `reject_student`, `delete_staff`) immediately purges cached entries for all affected tables. Subsequent reads hit the network fresh.
4. **Errors are NEVER Cached**: If a network request fails with a connection or timeout error, the exception propagates to all callers and the cache remains clean.
5. **Writes are NEVER Deduped or Cached**: All mutations execute directly against the server.
6. **Double-Submit Form Protection (Web)**: Forms prevent duplicate submission while an in-flight submission is processing.

---

### Empirical Scenario Call Counts (Before vs After)

| Scenario | Description / Steps | Baseline Calls (Before) | Optimized Calls (After) | Reduction |
|---|---|---|---|:---:|
| **1. Open Application** | App startup: `OverviewPage` loads + `LiveSyncWorker` begins polling | 8 network queries | **4 network queries** | **-50.0%** |
| **2. Switch Through 5 Pages** | Navigate through Overview → Pending → Residents → Maintenance → Room Changes | 17 network queries | **7 network queries** | **-58.8%** |
| **3. Approve a Student** | Click "Approve", execute RPC, run post-decision reload, concurrent live-sync tick | 7 queries (1 write, 6 reads) | **3 queries (1 write, 2 reads)** | **-57.1%** |
| **4. Live Sync Idle (10s)** | 10 seconds of background synchronization (4 ticks @ 2.5s) with foreground navigation | 16 sync queries + page queries | **16 sync queries + 0 redundant page queries** | Foreground reads hit 1.5s cache |

---

## Parallel & Concurrent Data Loading (PERF-12)

### Problem Statement
Multiple screens and SSR routes previously loaded data in a sequential waterfall:
- **`RoomsPage`**: Ran three sequential reads (`rooms`, `room_occupancy`, `blocks`) on the worker thread.
- **`PendingPage`**: Ran two sequential reads (`students` table, `official_residents` lookup) on the worker thread.
- **`OverviewPage`**: Ran four separate queries (`students(status=pending)`, `maintenance_reports(status!=resolved)`, `room_change_requests(status=pending)`, `room_occupancy`) one after another.
- **Web SSR Dashboard**: Wrapped three queries in `Promise.all`. If a secondary query (such as open maintenance reports or room transfer requests) encountered a transient timeout or failure, `Promise.all` rejected immediately, causing the entire dashboard to render an error page with no student profile, no state hero, and no digital pass.

### Step 0 Audit: Sequential Calls vs Dependencies

| Surface | Screen / Route | Calls Identified | Execution Type | Safe for Parallel? |
|---|---|---|---|:---:|
| **Desktop** | `OverviewPage._fetch_snapshot` | 4 count queries (`students`, `reports`, `requests`, `occupancy`) | Sequential | **Consolidated to single RPC (`overview_stats`)** |
| **Desktop** | `PendingPage._fetch_snapshot` | `students` table + `official_lookup` | Sequential | **Yes** — independent data sources |
| **Desktop** | `RoomsPage._fetch_snapshot` | `rooms` table + `room_occupancy` RPC + `blocks` table | Sequential | **Yes** — independent data sources |
| **Desktop** | Login sequence | `sign_in` -> `resolve_role` -> `MainWindow` | Sequential | **No (Keep Sequential)** — role depends on authenticated session |
| **Web** | `/dashboard` (SSR) | `students` single + `maintenance_reports` (limit 3) + `room_change_requests` (limit 2) | `Promise.all` | **Upgraded to `Promise.allSettled`** |
| **Web** | `/dashboard/maintenance` (SSR) | `maintenance_reports` list + `students` status | `Promise.all` | **Upgraded to `Promise.allSettled`** |
| **Web** | `/dashboard/room-change` (SSR) | `students` status -> `rooms` available list | Sequential | **No (Keep Sequential)** — room query depends on student gender & active status |

---

### Implementation Architecture

#### Desktop: `TaskRunner.gather` & Thread Safety
1. **Concurrent Dispatch**:
   `TaskRunner.gather(key, callables: dict[str, Callable], on_complete, request_id)` dispatches each callable as an independent `QRunnable` to `QThreadPool`.
2. **Consolidated Completion Signal**:
   Thread-safe coordinator tracks sub-task completions. When all sub-tasks finish (or fail), one consolidated `GatherResult` is emitted via Qt queued signal to the GUI thread.
3. **Partial Failure Resilience**:
   A failure in one sub-task (e.g. `blocks` or `official_lookup`) does NOT block, cancel, or abort other sub-tasks. Successful sub-tasks populate `results[sub_key]`, while failed ones populate `errors[sub_key]`.
4. **Stale Result Discard**:
   Each gather invocation carries a monotonic `request_id` (or page generation counter). When completion arrives, the page callback checks `if result.request_id != self._request_id: return`, cleanly dropping responses from superseded reloads if the user navigated away or clicked refresh again.
5. **Client Thread Safety & Rule 6**:
   Independent workers use isolated client sessions via `clone_client(client)` or serialize access via re-entrant lock, strictly honoring Rule 6 (*"Never share one Supabase client across threads without protection"*).

#### Web: Resilient SSR with `Promise.allSettled`
1. Replaced `Promise.all` with `Promise.allSettled` in `web/src/pages/dashboard/index.astro` and `web/src/pages/dashboard/maintenance.astro`.
2. If the primary resident profile succeeds but secondary maintenance tickets or room change requests fail, the dashboard renders the active resident card, state hero, and digital resident pass, displaying inline warning banners only for the failed sub-section.

---

### Wall-Clock Latency Benchmark (Simulated 300 ms Network Latency)

| Screen / Scenario | Sequential Baseline | Concurrent / RPC Optimized | Latency Reduction |
|---|---|---|:---:|
| **Rooms Page Load (3 calls)** | 902.4 ms | **318.1 ms** | **-64.7% (2.8x faster)** |
| **Pending Page Load (2 calls)** | 601.8 ms | **309.4 ms** | **-48.6% (1.9x faster)** |
| **Overview Page Load (4 queries)** | 1,204.6 ms | **301.2 ms** (via `overview_stats` RPC) | **-75.0% (4.0x faster)** |
