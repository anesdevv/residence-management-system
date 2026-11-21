# RÉSIVO — Inspector & Profile Data Quality Verification SQL

This document provides **100% read-only** SQL queries for administrators and developers to run in the **Supabase Cloud SQL Editor**.

> [!NOTE]
> None of the queries below modify, insert, update, or delete any data. They simply report on data completeness and relation integrity for records displayed in the **Maintenance (Ticket Inspector)**, **Room Changes (Transfer Inspector)**, and **Student Profile Dialog**.

---

## 1. Open Maintenance Tickets & Resident Data Completeness

Runs an audit of all active maintenance tickets (`pending` and `in_progress`), joining the resident's profile and assigned room.

```sql
SELECT
    t.id AS ticket_id,
    t.category,
    t.status AS ticket_status,
    t.created_at AS ticket_submitted_at,
    t.updated_at AS ticket_updated_at,
    t.photo_path IS NOT NULL AS has_photo,
    t.staff_note IS NOT NULL AS has_staff_note,
    s.id AS student_id,
    s.card_id,
    s.first_name || ' ' || s.last_name AS resident_name,
    s.status AS student_status,
    -- Contact & Academic Fields
    COALESCE(s.phone, 'MISSING') AS phone,
    COALESCE(s.email, 'MISSING') AS email,
    COALESCE(s.university, 'MISSING') AS university,
    COALESCE(s.faculty, 'MISSING') AS faculty,
    COALESCE(s.study_level, 'MISSING') AS study_level,
    COALESCE(s.wilaya, 'MISSING') AS wilaya,
    -- Room Allocation
    CASE
        WHEN r.id IS NOT NULL THEN 'Block ' || r.block || ' · Floor ' || r.floor || ' · Room ' || r.number
        ELSE 'NO_ROOM_ASSIGNED'
    END AS assigned_room,
    -- Admissions Roster Cross-Check
    CASE
        WHEN o.card_id IS NOT NULL THEN 'MATCHED'
        ELSE 'NOT_IN_ROSTER'
    END AS roster_match_status
FROM public.maintenance_reports t
LEFT JOIN public.students s ON s.id = t.student_id
LEFT JOIN public.rooms r ON r.id = s.room_id
LEFT JOIN public.official_residents o ON o.card_id = s.card_id
WHERE t.status IN ('pending', 'in_progress')
ORDER BY t.created_at DESC;
```

---

## 2. Room Change Requests & Relation Completeness

Audits all room change requests (pending, approved, rejected) to verify current room, requested room, decider profile, and reason notes.

```sql
SELECT
    rcr.id AS request_id,
    rcr.status AS request_status,
    rcr.created_at AS submitted_at,
    rcr.decided_at,
    s.card_id,
    s.first_name || ' ' || s.last_name AS student_name,
    -- Current Room
    CASE
        WHEN cur_r.id IS NOT NULL THEN 'Block ' || cur_r.block || ' · Floor ' || cur_r.floor || ' · Room ' || cur_r.number
        ELSE 'NO_CURRENT_ROOM'
    END AS current_room,
    -- Preferred Room
    CASE
        WHEN pref_r.id IS NOT NULL THEN 'Block ' || pref_r.block || ' · Floor ' || pref_r.floor || ' · Room ' || pref_r.number
        ELSE 'NO_PREFERENCE'
    END AS preferred_room,
    -- Reason & Decision
    rcr.reason AS student_reason,
    COALESCE(rcr.decision_note, 'NONE') AS decision_note,
    dec_staff.full_name AS decided_by_staff
FROM public.room_change_requests rcr
LEFT JOIN public.students s ON s.id = rcr.student_id
LEFT JOIN public.rooms cur_r ON cur_r.id = rcr.current_room_id
LEFT JOIN public.rooms pref_r ON pref_r.id = rcr.preferred_room_id
LEFT JOIN public.staff dec_staff ON dec_staff.id = rcr.decided_by
ORDER BY rcr.created_at DESC;
```

---

## 3. Active Residents Missing Room Allocations or Optional Information

Lists any resident with `status = 'active'` that does not have a `room_id`, helping staff identify records that trigger the amber warning badge `"Active but no room assigned: check the allocation"`.

```sql
SELECT
    s.id AS student_id,
    s.card_id,
    s.first_name || ' ' || s.last_name AS full_name,
    s.status,
    s.created_at AS registered_at,
    CASE WHEN s.phone IS NULL OR trim(s.phone) = '' THEN 'YES' ELSE 'NO' END AS missing_phone,
    CASE WHEN s.email IS NULL OR trim(s.email) = '' THEN 'YES' ELSE 'NO' END AS missing_email,
    CASE WHEN s.university IS NULL OR trim(s.university) = '' THEN 'YES' ELSE 'NO' END AS missing_university,
    CASE WHEN s.faculty IS NULL OR trim(s.faculty) = '' THEN 'YES' ELSE 'NO' END AS missing_faculty,
    CASE WHEN s.room_id IS NULL THEN 'NO_ROOM (Triggers Amber Warning)' ELSE 'ALLOCATED' END AS room_status,
    CASE WHEN o.card_id IS NULL THEN 'SELF_REGISTERED (No Roster Entry)' ELSE 'ROSTER_VERIFIED' END AS admissions_verification
FROM public.students s
LEFT JOIN public.official_residents o ON o.card_id = s.card_id
WHERE s.status = 'active' AND (s.room_id IS NULL OR o.card_id IS NULL)
ORDER BY s.created_at DESC;
```

---

## 4. How the Desktop App Handles These States

| Data State in DB | Old Desktop UI Appearance | New Desktop UI Appearance |
|---|---|---|
| Optional field is `NULL` (phone, email, univ, etc.) | Bare dash `—` | Muted italic `"Not provided"` (FR: `"Non renseigné"`) |
| Student has `room_id = NULL` | Bare dash `—` | `"No room assigned yet"` (FR: `"Aucune chambre attribuée"`) |
| Active resident with `room_id = NULL` | Unexplained empty room | Amber warning pill + warning banner: `"Active but no room assigned: check the allocation"` |
| Pending student with no roster match | Generic error / dash | Red audit banner: `"Not found on the admissions roster. Self-registered record. Audit the physical dossier before authorising a room allocation."` |
| Active student with no roster match | Red mismatch error banner | Quiet neutral info banner: `"Approved without a roster match"` (exception approval) |
| Ticket or request timestamps | Raw ISO `2026-11-12 22:28:37.75375+00:00` | Localized timestamp `'12 Nov 2026, 22:28'` |
| Pending ticket resolution date | Bare dash `—` | `"Not resolved yet"` (FR: `"Pas encore résolu"`) |
