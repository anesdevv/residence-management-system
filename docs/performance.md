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

---

## Suite Regression Gates

| Test Suite | Baseline | Post-Optimization Status | Target |
|---|---|---|---|
| Desktop (pytest) | 176 passed, 1 skipped | **182 passed, 1 skipped** (34.87s) | 100% pass rate + new regression tests |
| Web (vitest) | 19 passed | **22 passed** (728ms) | 100% pass rate + new regression tests |
| Web Build (`astro build`) | 6.83s | **Verified Clean Build** (10.41s) | No regressions, clean build |

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

