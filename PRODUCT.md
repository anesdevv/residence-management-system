# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

1. **Student Residents (Web Portal)**: Enrolled university students in Tlemcen applying for university dormitory accommodation, monitoring application status, viewing assigned rooms, reporting maintenance faults with photos, and requesting room transfers.
2. **Residence Administration & Housing Staff (Desktop Application)**: Dormitory department officers, intake clerks, facility triage staff, and housing directors managing room allocation, capacity, maintenance resolution, student verification against the official university roster, and staff accounts.

## Product Purpose

A complete, dual-surface student accommodation & facility management system for Cité Universitaire (Residence Tlemcen). It digitizes student housing applications, eliminates manual paperwork, accelerates maintenance triage, provides real-time department situational awareness, and ensures fair room occupancy management.

## Positioning

Tailored specifically for higher-education university residences with gender-segregated blocks, official university enrollment verification, fast live-mode staff desktop operations, and end-to-end multi-layer student request authorization.

## Operating Context

- **Student Side**: Accessible on mobile phones, tablets, and laptops via web browsers. High-clarity, low-friction forms, responsive layouts, clear status badges, and strict guidance on room policies.
- **Department Side**: Runs continuously on staff office workstations (PySide6 desktop). High scanability, instant real-time live synchronization, rapid triage keyboard/mouse navigation, and offline resilience with clean error feedback.

## Capabilities and Constraints

- **Web (Student Portal)**:
  - Account registration with student card ID verification
  - Authentication and profile contact management (phone, email)
  - Real-time application status tracking (Pending review, Active resident, Rejected with reason)
  - Maintenance ticketing with category selection, description, photo upload, and staff resolution notes
  - Room transfer requests with preferred room choice matching student gender
  - Strict multi-layer locking: Pending and rejected students cannot file requests until approved and assigned to a room
- **Desktop (Staff Console)**:
  - Live Mode 2-second background synchronization with notification badge counters and live toast alerts
  - Key performance indicator overview dashboard
  - Pending applications review with automatic cross-referencing against official university CSV/Excel rosters
  - Room assignment modal with capacity and occupancy enforcement
  - Room directory and resident directory with instant filtering
  - Maintenance triage workflow (pending -> in-progress -> resolved) with signed photo inspector
  - Room change request adjudication with room reassignment
  - CSV/Excel official resident list bulk import
  - Administrator staff user management

## Brand Commitments

- **Institution Name**: *Cité Universitaire — Residence Tlemcen* (Direction des Œuvres Universitaires / University Dormitory Department).
- **Tone**: Trustworthy, institutional, clear, organized, accessible, and respectful of students.
- **Palette Foundation**: Deep institutional navy/slate (`#0f172a`, `#1e293b`), crisp clean whites, subtle cool grays (`#f8fafc`, `#f1f5f9`), with clear functional semantic indicators (Emerald `#10b981` for active/resolved, Amber `#f59e0b` for pending review, Rose `#ef4444` for rejected/urgent, Blue `#2563eb` for primary department actions).

## Evidence on Hand

- PostgreSQL Supabase database schema with RLS and RPCs (`students`, `rooms`, `official_residents`, `maintenance_reports`, `room_change_requests`, `staff_roles`).
- Existing test suites passing 10/10 pytest and 8/8 vitest tests.
- Official resident file importer supporting CSV/Excel normalized schemas.

## Product Principles

1. **Clarity Over Mystery**: Students and department staff always know their exact status and next steps without ambiguity.
2. **Speed & Scanability**: Administrative staff process hundreds of requests daily; dense, organized layouts and instant visual cues outrank decorative fluff.
3. **Institutional Integrity**: Multi-layer authorization ensures non-active students cannot file invalid requests, protecting database and administrative sanity.
4. **Cohesive Design Language**: Both web and desktop share identical naming conventions, status indicators, and institutional branding aesthetics.
