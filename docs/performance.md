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
