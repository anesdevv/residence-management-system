
# TestSprite AI Testing Report(MCP)

---

## 1️⃣ Document Metadata
- **Project Name:** RESIVO — Student Resident Web Portal (directory: my school project THE MAIN)
- **Date:** 2026-10-18
- **Prepared by:** TestSprite AI Team
- **Test Type:** Frontend (login flow included)
- **Environment:** Astro 7 SSR dev server at http://localhost:4321, live Supabase backend (PostgreSQL 15 + Auth)
- **Test Account:** Seeded student `20230001@students.residence.local` (Yacine Benali — Active Resident, Block A / Room 101)
- **Scope:** 15 of 30 planned test cases executed (dev-server mode limits execution to the 15 highest-priority cases)

---

## 2️⃣ Requirement Validation Summary

### Requirement: Student Login
- **Description:** Students sign in with a synthetic email derived from their university card ID and a portal password (Supabase Auth email+password via `/api/login`).

#### Test TC001 Log in with a valid student account
- **Test Code:** [TC001_Log_in_with_a_valid_student_account.py](./TC001_Log_in_with_a_valid_student_account.py)
- **Test Error:** 
- **Test Visualization and Result:** https://www.testsprite.com/dashboard/mcp/tests/cfca8640-c0f1-5482-a1b4-f435c0d5c924/test/51fa9bfb-9648-4f51-957b-6f7f7f8d18f8
- **Status:** ✅ Passed
- **Severity:** LOW
- **Analysis / Findings:** Valid card-ID-derived email and password authenticate successfully, the session cookie is set, and the browser lands on the authenticated dashboard. Confirms the `cardIdToEmail` convention (`20230001@students.residence.local`) works end-to-end against live Supabase Auth.

---

### Requirement: Student Registration
- **Description:** Prospective students register at `/register` with their university card ID and profile details; the server derives a synthetic email, signs the user up in Supabase, and detects duplicate card IDs.

#### Test TC003 Register a new student account
- **Test Code:** [TC003_Register_a_new_student_account.py](./TC003_Register_a_new_student_account.py)
- **Test Error:** 
- **Test Visualization and Result:** https://www.testsprite.com/dashboard/mcp/tests/cfca8640-c0f1-5482-a1b4-f435c0d5c924/test/48e19f93-f652-415e-855b-1bda724905c6
- **Status:** ✅ Passed
- **Severity:** LOW
- **Analysis / Findings:** Registration with a unique card ID and valid details creates a real Supabase Auth user, shows the success confirmation, and redirects to `/login?registered=1`. Server-side `validateRegistration()` and the signup metadata flow work as designed.

---

#### Test TC004 Public visitor can register and reach the authenticated dashboard
- **Test Code:** [TC004_Public_visitor_can_register_and_reach_the_authenticated_dashboard.py](./TC004_Public_visitor_can_register_and_reach_the_authenticated_dashboard.py)
- **Test Error:** 
- **Test Visualization and Result:** https://www.testsprite.com/dashboard/mcp/tests/cfca8640-c0f1-5482-a1b4-f435c0d5c924/test/3626ead8-0293-44d9-8a4a-e47e0a3d56cb
- **Status:** ✅ Passed
- **Severity:** LOW
- **Analysis / Findings:** Full happy-path journey verified — landing page → registration → sign-in with the newly created synthetic email → authenticated dashboard. The complete first-run student onboarding flow is functional.

---

### Requirement: Route Protection Middleware
- **Description:** Astro middleware redirects unauthenticated visitors away from `/dashboard/*` and returns 401 for protected `/api/*` routes.

#### Test TC002 Unauthenticated visitor is redirected away from the dashboard
- **Test Code:** [TC002_Unauthenticated_visitor_is_redirected_away_from_the_dashboard.py](./TC002_Unauthenticated_visitor_is_redirected_away_from_the_dashboard.py)
- **Test Error:** 
- **Test Visualization and Result:** https://www.testsprite.com/dashboard/mcp/tests/cfca8640-c0f1-5482-a1b4-f435c0d5c924/test/8cdd2736-2c1d-49e5-b522-8292004e71e2
- **Status:** ✅ Passed
- **Severity:** LOW
- **Analysis / Findings:** Visiting `/dashboard` without a session redirects to `/login`. The middleware guard works correctly.

---

#### Test TC008 Unauthenticated visitor is redirected away from profile requests
- **Test Code:** [TC008_Unauthenticated_visitor_is_redirected_away_from_the_profile_requests.py](./TC008_Unauthenticated_visitor_is_redirected_away_from_the_profile_requests.py)
- **Test Error:** 
- **Test Visualization and Result:** https://www.testsprite.com/dashboard/mcp/tests/cfca8640-c0f1-5482-a1b4-f435c0d5c924/test/c84491f1-05af-4643-997f-e766857eb9f2
- **Status:** ✅ Passed
- **Severity:** LOW
- **Analysis / Findings:** `/dashboard/profile` without a session is redirected to `/login`. Sub-route protection under `/dashboard/` is confirmed, not just the index route.

---

### Requirement: Session Logout
- **Description:** Authenticated users can end their session via `/logout` and return to the public site.

#### Test TC005 Authenticated user can log out and return to the public homepage
- **Test Code:** [TC005_Authenticated_user_can_log_out_and_return_to_the_public_homepage.py](./TC005_Authenticated_user_can_log_out_and_return_to_the_public_homepage.py)
- **Test Error:** 
- **Test Visualization and Result:** https://www.testsprite.com/dashboard/mcp/tests/cfca8640-c0f1-5482-a1b4-f435c0d5c924/test/ee828405-94ce-44d8-9ba3-b00a6103285c
- **Status:** ✅ Passed
- **Severity:** LOW
- **Analysis / Findings:** Sign-in → logout completes cleanly: `supabase.auth.signOut()` invalidates the session and the visitor lands back on the public landing page in an unauthenticated state.

---

### Requirement: Student Dashboard Status Overview
- **Description:** The `/dashboard` page renders the student's application status (Pending / Active Resident / Rejected with reason) and assigned housing details, and is documented to include a digital residency pass.

#### Test TC006 Render approved resident dashboard details
- **Test Code:** [TC006_Render_approved_resident_dashboard_details.py](./TC006_Render_approved_resident_dashboard_details.py)
- **Test Error:** TEST FAILURE

The dashboard displays the assigned room, but residency pass details are not visible.

Observations:
- The dashboard shows Block A — Room 101, Floor 1.
- Searching the dashboard for "pass" found no matches.
- **Test Visualization and Result:** https://www.testsprite.com/dashboard/mcp/tests/cfca8640-c0f1-5482-a1b4-f435c0d5c924/test/5e77583b-fdbe-473f-a13d-8a8a95331b37
- **Status:** ❌ Failed
- **Severity:** MEDIUM
- **Analysis / Findings:** This is a **genuine product gap, not a test artifact**. README.md and PRODUCT.md advertise a "Digital Resident Pass" (block, room, floor, and official residency pass), but code inspection confirms `web/src/pages/dashboard/index.astro` contains no residency-pass section — the dashboard renders only the "Officially Assigned Quarters" summary (block/room/floor). Either implement the residency pass card (with QR/verification element as specified) or correct the documentation. Note TC009 passed because its assertions only required the assigned-room details.

---

#### Test TC007 Render pending student dashboard status
- **Test Code:** [TC007_Render_pending_student_dashboard_status.py](./TC007_Render_pending_student_dashboard_status.py)
- **Test Error:** TEST FAILURE

The dashboard opened, but the account is shown as an active resident rather than a pending applicant.

Observations:
- The dashboard displays "Active Resident."
- It shows "Officially Assigned Quarters" and "Block A — Room 101."
- Protected dashboard content is visible, but pending application messaging is not shown.
- **Test Visualization and Result:** https://www.testsprite.com/dashboard/mcp/tests/cfca8640-c0f1-5482-a1b4-f435c0d5c924/test/c32f438a-e456-4826-8e41-ebdbd66a10a7
- **Status:** ❌ Failed
- **Severity:** LOW
- **Analysis / Findings:** **Test-data limitation, not an app defect.** The only seeded account (`20230001`) is an approved resident with an assigned room, so the dashboard correctly rendered "Active Resident." No pending-state account exists in the database to exercise this path. The dashboard's conditional rendering logic itself was not disproven — it was simply never reached. Fix: seed a pending-state student (see Key Gaps).

---

#### Test TC009 Authenticated resident can view dashboard status and residency pass details
- **Test Code:** [TC009_Authenticated_resident_can_view_dashboard_status_and_residency_pass_details.py](./TC009_Authenticated_resident_can_view_dashboard_status_and_residency_pass_details.py)
- **Test Error:** 
- **Test Visualization and Result:** https://www.testsprite.com/dashboard/mcp/tests/cfca8640-c0f1-5482-a1b4-f435c0d5c924/test/17dbe390-b7ef-46fe-a9c9-49ad98125691
- **Status:** ✅ Passed
- **Severity:** LOW
- **Analysis / Findings:** The authenticated dashboard correctly shows the active resident status and the assigned room details (Block A / Room 101 / Floor 1) for the approved account. Passed with room-detail assertions; see TC006 for the unresolved residency-pass gap.

---

#### Test TC010 Render rejected applicant dashboard reason
- **Test Code:** [TC010_Render_rejected_applicant_dashboard_reason.py](./TC010_Render_rejected_applicant_dashboard_reason.py)
- **Test Error:** TEST FAILURE

The dashboard opened successfully, but it shows the account as an active resident instead of a rejected applicant. No rejection reason is visible.

Observations:
- The dashboard displays "Active Resident."
- The assigned quarters are shown as Block A — Room 101.
- No rejection status or reason details appear on the dashboard.
- **Test Visualization and Result:** https://www.testsprite.com/dashboard/mcp/tests/cfca8640-c0f1-5482-a1b4-f435c0d5c924/test/4f273779-b4ce-4f29-bc07-2c6a33e69dd8
- **Status:** ❌ Failed
- **Severity:** LOW
- **Analysis / Findings:** **Test-data limitation, not an app defect.** Same root cause as TC007/TC011/TC014: the single seeded account is approved, so no rejection state could be rendered. The mandatory rejection-reason display (a documented desk-inquiry feature) remains **untested**. Fix: seed a rejected-state student with a rejection reason.

---

#### Test TC011 Pending student sees review status and restricted-action guidance on the dashboard
- **Test Code:** [TC011_Pending_student_sees_review_status_and_restricted_action_guidance_on_the_dashboard.py](./TC011_Pending_student_sees_review_status_and_restricted_action_guidance_on_the_dashboard.py)
- **Test Error:** TEST FAILURE

The dashboard does not show a pending application or explain that requests are restricted until approval. It identifies the account as an active resident and shows assigned quarters and resident service shortcuts.

Observations:
- The dashboard displayed "Active Resident."
- It showed assigned quarters: "Block A — Room 101."
- No pending-review status or restricted-action guidance was visible.
- **Test Visualization and Result:** https://www.testsprite.com/dashboard/mcp/tests/cfca8640-c0f1-5482-a1b4-f435c0d5c924/test/bc89d6b4-34ed-4a73-8660-ae8256280bc3
- **Status:** ❌ Failed
- **Severity:** LOW
- **Analysis / Findings:** **Test-data limitation, not an app defect.** The approved account correctly saw approved-state content. The pending-review messaging and "wait for approval" guidance could not be exercised without a pending-state account.

---

#### Test TC014 Rejected student sees rejection status and reason on the dashboard
- **Test Code:** [TC014_Rejected_student_sees_rejection_status_and_reason_on_the_dashboard.py](./TC014_Rejected_student_sees_rejection_status_and_reason_on_the_dashboard.py)
- **Test Error:** TEST FAILURE

The dashboard opened, but it did not show a rejected application status or the required rejection reason.

Observations:
- The dashboard labels the account "Active Resident."
- It shows assigned quarters: Block A — Room 101.
- No rejection reason is displayed.
- **Test Visualization and Result:** https://www.testsprite.com/dashboard/mcp/tests/cfca8640-c0f1-5482-a1b4-f435c0d5c924/test/714f2eb0-563c-4154-83cb-f74a9fb9e753
- **Status:** ❌ Failed
- **Severity:** LOW
- **Analysis / Findings:** **Test-data limitation, not an app defect.** Duplicate coverage of TC010 with the same single-account root cause. The rejection-status branch of the dashboard remains unverified.

---

### Requirement: Maintenance Ticket Submission
- **Description:** Approved residents file maintenance faults with category, description, and optional photo via `/dashboard/maintenance` and `/api/maintenance`.

#### Test TC012 View maintenance form as an approved resident
- **Test Code:** [TC012_View_maintenance_form_as_an_approved_resident.py](./TC012_View_maintenance_form_as_an_approved_resident.py)
- **Test Error:** 
- **Test Visualization and Result:** https://www.testsprite.com/dashboard/mcp/tests/cfca8640-c0f1-5482-a1b4-f435c0d5c924/test/12975428-a3e1-45e1-9b8c-23ecf99d66cb
- **Status:** ✅ Passed
- **Severity:** LOW
- **Analysis / Findings:** The approved resident reaches the maintenance page and the reporting form renders ready for input. Route access for eligible accounts is correct.

---

#### Test TC013 Submit a maintenance ticket
- **Test Code:** [TC013_Submit_a_maintenance_ticket.py](./TC013_Submit_a_maintenance_ticket.py)
- **Test Error:** 
- **Test Visualization and Result:** https://www.testsprite.com/dashboard/mcp/tests/cfca8640-c0f1-5482-a1b4-f435c0d5c924/test/82fafa2a-8c35-427d-92b3-2522e355d7f4
- **Status:** ✅ Passed
- **Severity:** LOW
- **Analysis / Findings:** A ticket with category and description submits successfully, confirmation is shown, and the new ticket appears in the student's request list (persisted to the live Supabase `maintenance_reports` table). The end-to-end submission path works.

---

### Requirement: Profile Contact Management
- **Description:** Authenticated students view and update contact details (phone, email) via `/dashboard/profile` and `/api/profile`.

#### Test TC015 Update profile contact details
- **Test Code:** [TC015_Update_profile_contact_details.py](./TC015_Update_profile_contact_details.py)
- **Test Error:** 
- **Test Visualization and Result:** https://www.testsprite.com/dashboard/mcp/tests/cfca8640-c0f1-5482-a1b4-f435c0d5c924/test/452cc3dc-e348-4b61-83aa-2079dfc4c3d9
- **Status:** ✅ Passed
- **Severity:** LOW
- **Analysis / Findings:** Updating phone and email saves successfully, confirmation is displayed, and the refreshed values render on the profile page. Contact persistence through `/api/profile` works.

---

## 3️⃣ Coverage & Matching Metrics

- **66.67% of tests passed** (10 of 15 executed)

| Requirement | Total Tests | ✅ Passed | ❌ Failed |
|--------------------|-------------|-----------|------------|
| Student Login | 1 | 1 | 0 |
| Student Registration | 2 | 2 | 0 |
| Route Protection Middleware | 2 | 2 | 0 |
| Session Logout | 1 | 1 | 0 |
| Student Dashboard Status Overview | 6 | 1 | 5 |
| Maintenance Ticket Submission | 2 | 2 | 0 |
| Profile Contact Management | 1 | 1 | 0 |
| **Total** | **15** | **10** | **5** |

**Adjusted view:** Of the 5 failures, 4 (TC007, TC010, TC011, TC014) are attributable to a single-state test account rather than application defects. Measured against executed-against-available-data, the effective pass rate is 10/11 (90.9%), with 1 genuine product gap (TC006).

---

## 4️⃣ Key Gaps / Risks

> 66.67% of executed tests passed fully (10/15). Four failures share one root cause — a single seeded account in one state — and one failure is a genuine product gap.

1. **Digital Resident Pass is documented but not implemented (TC006 — MEDIUM).** README.md and PRODUCT.md advertise a "Digital Resident Pass" showing block, room, floor, and an official pass. The dashboard (`web/src/pages/dashboard/index.astro`) has no pass section — verified by code inspection, not only by the browser test. Implement the pass card or amend the documentation before submission/demo.

2. **Single-state seed data blocks status-variant coverage.** `scripts/seed.py` seeds exactly one student (approved, room-assigned). The Pending and Rejected dashboard states — including the mandatory rejection-reason display that README.md highlights for desk inquiries — are **completely untested**. Add seeded students in each state (pending applicant; rejected applicant with a documented reason), then re-run TC007, TC010, TC011, TC014.

3. **Half the test plan was not executed.** Only the 15 highest-priority cases ran because the Vercel adapter forbids `astro preview`, forcing dev-server mode. The 15 unexecuted cases cover valuable negative paths: duplicate registration (TC024), invalid login credentials (TC025), registration validation errors (TC028), restricted-student request locks (TC026, TC029), room-transfer submission (TC021), and profile validation (TC027). For a full run: temporarily switch `astro.config` to the `node` adapter (or run the dev server with TestSprite's production tunnel), then execute the plan again.

4. **Tests mutate live production data.** Registration and maintenance tests created real Supabase Auth users and real tickets in your live project. Consider a dedicated test project or a cleanup script (delete users with card IDs ≥ 2099XXXX and their profiles) before demoing.

5. **Re-running requires re-provisioning.** TestSprite deletes `testsprite_tests/tmp/config.json` after a successful run (credential hygiene). To run again, re-invoke the `testsprite_generate_code_and_execute` MCP step first — it rewrites the config — rather than calling the CLI directly.

---
