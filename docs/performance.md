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

---

## Suite Regression Gates

| Test Suite | Baseline | Post-Optimization Status | Target |
|---|---|---|---|
| Desktop (pytest) | 176 passed, 1 skipped | **205 passed, 1 skipped** (43.00s) | 100% pass rate + new regression tests |
| Web (vitest) | 19 passed | **31 passed** (1.89s) | 100% pass rate + new regression tests |
| Web Build (`astro build`) | 6.83s | **Verified Clean Build** (14.78s) | No regressions, clean build |

---

## Database Migrations: Deployment & Rollback

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

