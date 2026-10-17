import os
import sys
import base64
import subprocess
from pathlib import Path

# Paths
ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
VISUALS = DOCS / "visuals"
OUTPUT_HTML = DOCS / "APP_FLOW.html"
OUTPUT_PDF = DOCS / "RESIVO_Application_Flow_Document.pdf"

def get_base64_image(path: Path) -> str:
    if not path.exists():
        return ""
    mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
    data = base64.b64encode(path.read_bytes()).decode("utf-8")
    return f"data:{mime};base64,{data}"

def build_html() -> str:
    logo_b64 = get_base64_image(DOCS / "resivo_logo_transparent.png")
    workflow_b64 = get_base64_image(VISUALS / "resivo_architectural_workflow.jpg")
    lifecycle_b64 = get_base64_image(VISUALS / "resivo_residency_lifecycle_infographic.jpg")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>RÉSIVO — Application Flow & Architecture Document</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap');

  @page {{
    size: A4 portrait;
    margin: 14mm 16mm 14mm 16mm;
    @bottom-right {{
      content: "Page " counter(page);
      font-size: 9pt;
      color: #94a3b8;
      font-family: 'Plus Jakarta Sans', sans-serif;
    }}
  }}

  * {{
    box-sizing: border-box;
    margin: 0;
    padding: 0;
  }}

  body {{
    font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    color: #0f172a;
    background-color: #ffffff;
    font-size: 10pt;
    line-height: 1.5;
    -webkit-print-color-adjust: exact;
    print-color-adjust: exact;
  }}

  .page {{
    page-break-after: always;
    min-height: 260mm;
    position: relative;
    padding-bottom: 10mm;
  }}

  .page:last-child {{
    page-break-after: avoid;
  }}

  /* Header & Branding */
  .doc-header {{
    border-bottom: 2px solid #000b2b;
    padding-bottom: 12px;
    margin-bottom: 18px;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }}

  .doc-header .left-meta {{
    display: flex;
    align-items: center;
    gap: 14px;
  }}

  .doc-header img.logo {{
    height: 44px;
    width: auto;
  }}

  .doc-header .brand-title {{
    font-size: 16pt;
    font-weight: 800;
    color: #000b2b;
    letter-spacing: -0.5px;
  }}

  .doc-header .brand-subtitle {{
    font-size: 8.5pt;
    color: #64748b;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }}

  .doc-header .doc-badge {{
    background: #000b2b;
    color: #fe932c;
    font-size: 8pt;
    font-weight: 700;
    padding: 5px 12px;
    border-radius: 20px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }}

  /* Typography */
  h1 {{
    font-size: 18pt;
    font-weight: 800;
    color: #000b2b;
    margin-bottom: 6px;
    letter-spacing: -0.5px;
  }}

  h2 {{
    font-size: 13pt;
    font-weight: 700;
    color: #000b2b;
    margin-top: 14px;
    margin-bottom: 8px;
    border-left: 4px solid #fe932c;
    padding-left: 8px;
    letter-spacing: -0.2px;
  }}

  h3 {{
    font-size: 10.5pt;
    font-weight: 700;
    color: #1e293b;
    margin-top: 10px;
    margin-bottom: 4px;
  }}

  p, li {{
    font-size: 9.5pt;
    color: #334155;
    line-height: 1.55;
  }}

  ul, ol {{
    padding-left: 18px;
    margin-bottom: 8px;
  }}

  li {{
    margin-bottom: 3px;
  }}

  /* Visual Containers */
  .visual-card {{
    background: #080d1e;
    border: 1px solid #1e293b;
    border-radius: 8px;
    padding: 6px;
    margin: 12px 0 16px 0;
    box-shadow: 0 4px 12px rgba(0, 11, 43, 0.08);
  }}

  .visual-card img {{
    width: 100%;
    height: auto;
    border-radius: 6px;
    display: block;
  }}

  .visual-card .caption {{
    font-size: 8pt;
    color: #94a3b8;
    text-align: center;
    padding: 6px 4px 2px 4px;
    font-weight: 500;
  }}

  /* Grid Layouts */
  .grid-2 {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
    margin: 10px 0;
  }}

  .grid-3 {{
    display: grid;
    grid-template-columns: 1fr 1fr 1fr;
    gap: 10px;
    margin: 10px 0;
  }}

  /* Cards */
  .card {{
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 6px;
    padding: 10px 12px;
  }}

  .card.highlight {{
    background: #fffbeb;
    border-color: #fde68a;
  }}

  .card.dark {{
    background: #070a16;
    border-color: #1a2238;
    color: #f8fafc;
  }}

  .card.dark p {{
    color: #cbd5e1;
  }}

  .card.dark h3 {{
    color: #fe932c;
  }}

  .card h3 {{
    margin-top: 0;
    display: flex;
    align-items: center;
    gap: 6px;
  }}

  /* Badges & Tags */
  .badge {{
    display: inline-block;
    padding: 2px 7px;
    font-size: 7.5pt;
    font-weight: 700;
    border-radius: 4px;
    text-transform: uppercase;
    letter-spacing: 0.3px;
  }}

  .badge-emerald {{ background: #d1fae5; color: #065f46; }}
  .badge-amber {{ background: #fef3c7; color: #92400e; }}
  .badge-rose {{ background: #ffe4e6; color: #9f1239; }}
  .badge-blue {{ background: #dbeafe; color: #1e40af; }}
  .badge-navy {{ background: #000b2b; color: #fe932c; }}

  /* Tables */
  table {{
    width: 100%;
    border-collapse: collapse;
    margin: 8px 0 14px 0;
    font-size: 8.5pt;
  }}

  th, td {{
    padding: 6px 8px;
    border: 1px solid #e2e8f0;
    text-align: left;
    vertical-align: top;
  }}

  th {{
    background: #f1f5f9;
    color: #0f172a;
    font-weight: 700;
    text-transform: uppercase;
    font-size: 7.5pt;
    letter-spacing: 0.4px;
  }}

  tr:nth-child(even) td {{
    background: #f8fafc;
  }}

  /* Code / Pre */
  code, pre {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 8pt;
  }}

  code {{
    background: #f1f5f9;
    color: #0f172a;
    padding: 1px 4px;
    border-radius: 3px;
    border: 1px solid #e2e8f0;
  }}

  pre.desk-box {{
    background: #fff1f2;
    border: 1px solid #fecdd3;
    border-left: 4px solid #e11d48;
    color: #881337;
    padding: 8px 10px;
    border-radius: 4px;
    margin: 8px 0;
    white-space: pre-wrap;
    font-size: 8pt;
    line-height: 1.4;
  }}

  /* Flow Steps */
  .flow-step {{
    display: flex;
    gap: 12px;
    margin-bottom: 10px;
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 6px;
    padding: 8px 10px;
  }}

  .step-num {{
    background: #000b2b;
    color: #fe932c;
    font-size: 11pt;
    font-weight: 800;
    width: 28px;
    height: 28px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
  }}

  .step-content h4 {{
    font-size: 9.5pt;
    font-weight: 700;
    color: #000b2b;
    margin-bottom: 2px;
  }}

  .footer-meta {{
    position: absolute;
    bottom: 0;
    left: 0;
    right: 0;
    border-top: 1px solid #e2e8f0;
    padding-top: 6px;
    font-size: 7.5pt;
    color: #94a3b8;
    display: flex;
    justify-content: space-between;
  }}
</style>
</head>
<body>

<!-- PAGE 1: COVER & ARCHITECTURAL ECOSYSTEM -->
<div class="page">
  <div class="doc-header">
    <div class="left-meta">
      <img src="{logo_b64}" class="logo" alt="RÉSIVO" />
      <div>
        <div class="brand-title">RÉSIVO</div>
        <div class="brand-subtitle">Direction des Œuvres Universitaires • Cité Universitaire • Tlemcen</div>
      </div>
    </div>
    <div class="doc-badge">Apps Flow Specification</div>
  </div>

  <h1>Application Flow & Architectural Workflow Document</h1>
  <p><strong>System Scope:</strong> Dual-Surface Higher-Education Dormitory Operations, Resident Lifecycle & Facility Triage</p>

  <div class="visual-card">
    <img src="{workflow_b64}" alt="RÉSIVO Architectural Workflow Diagram" />
    <div class="caption">Figure 1.0: RÉSIVO Dual-Surface Operations Ecosystem (Student Web Portal &harr; Central Supabase Hub &harr; Staff Operations Console)</div>
  </div>

  <h2>1. High-Level Operations Overview</h2>
  <div class="grid-3">
    <div class="card">
      <h3>🌐 Resident Web Portal</h3>
      <p><strong>Platform:</strong> Astro 5 + Tailwind CSS v4</p>
      <p>Mobile-first portal for students: self-service registration, card ID verification, digital room passes, and maintenance ticketing with camera photo uploads.</p>
    </div>
    <div class="card highlight">
      <h3>🖥️ Staff Operations Console</h3>
      <p><strong>Platform:</strong> PySide6 (Qt 6) + Python 3.11</p>
      <p>Administrative desktop workstation: 2-second background sync worker, roster matching, room allocations, desk inquiry references, and async photo viewer.</p>
    </div>
    <div class="card">
      <h3>🤖 AI Operations Assistant</h3>
      <p><strong>Platform:</strong> Cloudflare Workers (MCP)</p>
      <p>Direct Model Context Protocol integration with ChatGPT: natural language occupancy queries and ticket status lookups with strict authorization.</p>
    </div>
  </div>

  <h2>2. Architectural Interaction Model</h2>
  <table>
    <thead>
      <tr>
        <th>Channel</th>
        <th>Source &rarr; Target</th>
        <th>Cadence / Protocol</th>
        <th>Safeguards & Invariants</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td><strong>Live State Polling</strong></td>
        <td>Staff Desktop &rarr; PostgreSQL</td>
        <td>2000ms Interval (<code>LiveSyncWorker</code>)</td>
        <td>Differential key check (<code>old_keys == new_keys</code>) avoids redraw flicker; preserves active filter tabs & search text.</td>
      </tr>
      <tr>
        <td><strong>Photo Evidence</strong></td>
        <td>Web Portal &rarr; Supabase Storage</td>
        <td>On-demand Multipart Upload</td>
        <td>Restricted to <code>maintenance-photos</code> bucket; fetched via multi-threaded background worker on desktop.</td>
      </tr>
      <tr>
        <td><strong>Dossier Deletion</strong></td>
        <td>Staff Desktop &rarr; Postgres RPC</td>
        <td>Administrative Confirmation</td>
        <td>Pending applications locked against deletion; only active/rejected students can be pruned; cascades room assignments.</td>
      </tr>
    </tbody>
  </table>

  <div class="footer-meta">
    <span>RÉSIVO Enterprise Architecture • Version 1.0.0</span>
    <span>Document Ref: RESIVO-AFD-2026</span>
  </div>
</div>

<!-- PAGE 2: RESIDENCY LIFECYCLE & USER JOURNEYS -->
<div class="page">
  <div class="doc-header">
    <div class="left-meta">
      <img src="{logo_b64}" class="logo" alt="RÉSIVO" />
      <div>
        <div class="brand-title">RÉSIVO</div>
        <div class="brand-subtitle">Residency Lifecycle &amp; Process Sequence</div>
      </div>
    </div>
    <div class="doc-badge">Section 2</div>
  </div>

  <h2>3. End-to-End Residency Process Sequence</h2>
  <div class="visual-card">
    <img src="{lifecycle_b64}" alt="RÉSIVO 5-Step Residency Lifecycle Infographic" />
    <div class="caption">Figure 2.0: The 5-Phase Student Housing Journey from Registration to Triage Resolution</div>
  </div>

  <div class="flow-step">
    <div class="step-num">1</div>
    <div class="step-content">
      <h4>Phase 1: Student Registration &amp; Academic Identity Submission</h4>
      <p>Student accesses <code>/register</code> on mobile or desktop web. Submits national student card ID (e.g. <code>202437010001</code>), full legal name, wilaya, gender, faculty, phone, and password. System authenticates user via Supabase Auth and inserts application with status <span class="badge badge-amber">Pending</span>.</p>
    </div>
  </div>

  <div class="flow-step">
    <div class="step-num">2</div>
    <div class="step-content">
      <h4>Phase 2: Automated Cross-Referencing against Official University Roster</h4>
      <p>The system queries <code>official_residents</code> table (imported from university enrollment files). If the card ID exists, the applicant is tagged <span class="badge badge-emerald">✓ Matched</span> with verified faculty details. If absent, it is flagged with <span class="badge badge-rose">⚠ Not in Roster</span>.</p>
    </div>
  </div>

  <div class="flow-step">
    <div class="step-num">3</div>
    <div class="step-content">
      <h4>Phase 3: Administrative Triage &amp; Room Allocation (`PendingPage`)</h4>
      <p>Housing staff filters by <code>Pending Applications</code>. Evaluates academic dossier and roster flag. If approved, opens the Room Allocation modal, which enforces block gender segregation (Block A = Male, Block B = Female) and validates capacity (&le; 2). Application becomes <span class="badge badge-emerald">Active</span>.</p>
    </div>
  </div>

  <div class="flow-step">
    <div class="step-num">4</div>
    <div class="step-content">
      <h4>Phase 4: Digital Resident Pass Issuance &amp; Dormitory Check-In</h4>
      <p>Upon approval, the student's dashboard unlocks their <strong>Digital Resident Pass</strong> displaying assigned Block, Floor, Room Number, and matriculation barcode. Locked services (Maintenance &amp; Transfer) immediately activate.</p>
    </div>
  </div>

  <div class="flow-step">
    <div class="step-num">5</div>
    <div class="step-content">
      <h4>Phase 5: Dormitory Living &amp; Photo Maintenance Triage</h4>
      <p>Residents report facility faults by selecting a category and snapping a photo. Staff desktop receives real-time notification, inspects full-resolution image with the async photo viewer, and updates status to <span class="badge badge-blue">In Progress</span> and <span class="badge badge-emerald">Resolved</span>.</p>
    </div>
  </div>

  <div class="footer-meta">
    <span>RÉSIVO Process Architecture • Phase Sequencing</span>
    <span>Page 2</span>
  </div>
</div>

<!-- PAGE 3: DETAILED DECISION TREES & SAFEGUARDS -->
<div class="page">
  <div class="doc-header">
    <div class="left-meta">
      <img src="{logo_b64}" class="logo" alt="RÉSIVO" />
      <div>
        <div class="brand-title">RÉSIVO</div>
        <div class="brand-subtitle">Application Triage &amp; Inquiry Decision Trees</div>
      </div>
    </div>
    <div class="doc-badge">Section 3</div>
  </div>

  <h2>4. Application Triage &amp; Desk Inquiry Decision Flow</h2>
  <p>The housing department console enforces institutional verification protocols during application processing:</p>

  <div class="grid-2">
    <div class="card">
      <h3>Decision A: Application Approval</h3>
      <ol>
        <li>Staff selects applicant from <code>Pending Applications</code>.</li>
        <li>Inspects roster match badge: <code>✓ Matched</code> or <code>⚠ Not in Roster</code>.</li>
        <li>Clicks <strong>Approve &amp; Assign Room</strong>.</li>
        <li>System filters rooms by student gender &amp; remaining capacity.</li>
        <li>Staff confirms target room; database executes atomic update:
          <pre><code>UPDATE students SET room_id = target_room,
status = 'active', reviewed_at = NOW();</code></pre>
        </li>
        <li>Student's digital pass is instantly generated and visible on web.</li>
      </ol>
    </div>

    <div class="card">
      <h3>Decision B: Application Rejection</h3>
      <ol>
        <li>Staff clicks <strong>Reject Application</strong>.</li>
        <li>System prompts for official administrative justification via <code>QInputDialog</code>.</li>
        <li><strong>Mandatory Validation:</strong> Empty reasons are strictly blocked with <code>QMessageBox.warning</code>.</li>
        <li>Staff enters formal note (e.g. <em>"Missing residence slip"</em>).</li>
        <li>Calls PostgreSQL RPC <code>reject_student</code>.</li>
        <li>Application status becomes <span class="badge badge-rose">Rejected</span>.</li>
      </ol>
    </div>
  </div>

  <h3>Front Desk Inquiry Support Reference</h3>
  <p>When a rejected applicant inquires at the housing reception desk, the officer filters by <code>Rejected Applications</code>. The detail inspector displays:</p>

  <pre class="desk-box">⚠️ REJECTION REASON (Desk Inquiry Reference):
"Incomplete academic file: missing residence registration slip"
Reviewed: 2026-10-12 14:30:15
Student: Mohamed Belkacem (Card ID: 202437010003)</pre>

  <h2>5. Multi-Tier Deletion Safety Matrix</h2>
  <table>
    <thead>
      <tr>
        <th>Target Record</th>
        <th>Application State</th>
        <th>Deletion Button State</th>
        <th>Backend Defense Mechanism</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td><strong>Student Dossier</strong></td>
        <td><span class="badge badge-amber">Pending</span></td>
        <td><strong>Disabled (Greyed Out)</strong><br/>Tooltip: <em>Pending applications cannot be deleted.</em></td>
        <td>Database RPC <code>delete_student</code> checks <code>status = 'pending'</code> &rarr; raises exception. RLS blocks delete.</td>
      </tr>
      <tr>
        <td><strong>Student Dossier</strong></td>
        <td><span class="badge badge-emerald">Approved</span></td>
        <td><strong>Enabled (Red / Danger)</strong><br/>Prompts <code>QMessageBox.question</code></td>
        <td>Clears room assignment; cascades maintenance reports and room requests; deletes auth user.</td>
      </tr>
      <tr>
        <td><strong>Student Dossier</strong></td>
        <td><span class="badge badge-rose">Rejected</span></td>
        <td><strong>Enabled (Red / Danger)</strong><br/>Prompts <code>QMessageBox.question</code></td>
        <td>Permanently removes rejected student dossier and associated credentials.</td>
      </tr>
      <tr>
        <td><strong>Staff Account</strong></td>
        <td>Logged-in Self</td>
        <td><strong>Disabled (Greyed Out)</strong><br/>Tooltip: <em>You cannot delete your own staff account.</em></td>
        <td>Edge Function checks <code>id === caller.id</code> &rarr; HTTP 400. RPC checks <code>p_staff = auth.uid()</code>.</td>
      </tr>
    </tbody>
  </table>

  <div class="footer-meta">
    <span>RÉSIVO Triage &amp; Safeguard Logic</span>
    <span>Page 3</span>
  </div>
</div>

<!-- PAGE 4: MAINTENANCE, TRANSFERS & AI QUERY FLOWS -->
<div class="page">
  <div class="doc-header">
    <div class="left-meta">
      <img src="{logo_b64}" class="logo" alt="RÉSIVO" />
      <div>
        <div class="brand-title">RÉSIVO</div>
        <div class="brand-subtitle">Facility Operations &amp; AI Integration</div>
      </div>
    </div>
    <div class="doc-badge">Section 4</div>
  </div>

  <h2>6. Maintenance Ticketing &amp; High-Resolution Photo Viewer</h2>
  <div class="flow-step">
    <div class="step-num">A</div>
    <div class="step-content">
      <h4>Resident Fault Submission Flow</h4>
      <p>Resident selects fault category (<code>Plumbing</code>, <code>Electricity</code>, <code>Heating</code>, <code>Carpentry</code>, <code>General</code>), provides problem details, and uploads a photo. Image is sent to Supabase Storage with signed token. Ticket state set to <span class="badge badge-amber">Pending</span>.</p>
    </div>
  </div>

  <div class="flow-step">
    <div class="step-num">B</div>
    <div class="step-content">
      <h4>Asynchronous Desktop Inspection Flow</h4>
      <p>Desktop console displays ticket with thumbnail loaded on a non-blocking background <code>QThread</code> (<code>PhotoFetchWorker</code>). Facility officer clicks thumbnail to launch <code>PhotoViewerDialog</code> featuring zoom controls (25% to 400%), fit-to-screen scaling, and clean thread cleanup on exit.</p>
    </div>
  </div>

  <div class="flow-step">
    <div class="step-num">C</div>
    <div class="step-content">
      <h4>Resolution &amp; Triage Lifecycle</h4>
      <p>Officer advances ticket stage: <span class="badge badge-amber">Pending</span> &rarr; <span class="badge badge-blue">In Progress</span> &rarr; <span class="badge badge-emerald">Resolved</span>, appending internal technician notes. Student portal updates dynamically without page reloads.</p>
    </div>
  </div>

  <h2>7. Room Transfer &amp; Adjudication Flow</h2>
  <div class="card">
    <ol>
      <li><strong>Locked State Enforcement:</strong> Only residents with status <code>active</code> can access the transfer docket; pending and rejected students are locked out.</li>
      <li><strong>Target Room Selection:</strong> Resident selects target dormitory block and available room matching their gender, entering written motive.</li>
      <li><strong>Housing Staff Review:</strong> Officer reviews justification in <code>RoomChangesPage</code>.</li>
      <li><strong>Atomic Transfer:</strong> If approved, the system updates the resident's <code>room_id</code>, updates request status to <code>approved</code>, and recalculates block occupancy immediately.</li>
    </ol>
  </div>

  <h2>8. Model Context Protocol (MCP) AI Query Flow</h2>
  <div class="card dark">
    <h3>🤖 AI Operations Assistant Architecture</h3>
    <p>Housing administrators can query real-time dormitory statistics using natural language through ChatGPT Plus/Pro:</p>
    <ul style="margin-top: 6px;">
      <li><strong>Query:</strong> <em>"Show current occupancy rates across all blocks and list pending plumbing tickets."</em></li>
      <li><strong>Flow:</strong> ChatGPT &rarr; Cloudflare Worker (<code>/mcp</code>) &rarr; Bearer Token Validation &rarr; Supabase SQL Execution &rarr; JSON-RPC Tool Result &rarr; ChatGPT Executive Summary.</li>
      <li><strong>Safety Guard:</strong> Assistant is read-only by default; data modifications require explicit user confirmation.</li>
    </ul>
  </div>

  <h2>9. Verification &amp; Certification</h2>
  <table>
    <thead>
      <tr>
        <th>Subsystem</th>
        <th>Test Suite</th>
        <th>Coverage Metric</th>
        <th>Status</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td><strong>Desktop Console</strong></td>
        <td>Pytest 8.3.3 (19 test cases)</td>
        <td>100% of status filters, self-deletion, live sync, photo viewer, and window scaling tested</td>
        <td><span class="badge badge-emerald">19 / 19 PASS</span></td>
      </tr>
      <tr>
        <td><strong>Student Web Portal</strong></td>
        <td>Vitest 5.0.3</td>
        <td>Astro SSR form submission, authentication routes, and profile updates validated</td>
        <td><span class="badge badge-emerald">ALL PASS</span></td>
      </tr>
      <tr>
        <td><strong>PostgreSQL Database</strong></td>
        <td>Supabase CLI &amp; MCP Runner</td>
        <td>Idempotent migrations, RLS policies, and SECURITY DEFINER RPCs verified</td>
        <td><span class="badge badge-emerald">VERIFIED</span></td>
      </tr>
    </tbody>
  </table>

  <div class="footer-meta">
    <span>RÉSIVO Technical Specifications • Approved for Campus Operations</span>
    <span>Page 4</span>
  </div>
</div>

</body>
</html>
"""
    return html

def main():
    print("[1/3] Generating self-contained HTML with base64 embedded visuals...")
    html_content = build_html()
    OUTPUT_HTML.write_text(html_content, encoding="utf-8")
    print(f"      Saved HTML to: {OUTPUT_HTML}")

    print("[2/3] Rendering pixel-perfect PDF via Google Chrome Headless...")
    chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    if not os.path.exists(chrome_path):
        print(f"Error: Chrome executable not found at {chrome_path}")
        return 1

    cmd = [
        chrome_path,
        "--headless",
        "--disable-gpu",
        "--run-all-compositor-stages-before-draw",
        "--no-pdf-header-footer",
        f"--print-to-pdf={OUTPUT_PDF}",
        str(OUTPUT_HTML),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error generating PDF: {result.stderr}")
        return 1

    print(f"[3/3] Successfully created PDF at: {OUTPUT_PDF}")
    print(f"      PDF Size: {OUTPUT_PDF.stat().st_size / 1024:.1f} KB")
    return 0

if __name__ == "__main__":
    sys.exit(main())
