/**
 * Friendly, safe error text: no traceback, no secrets.
 *
 * TypeScript port of `mcp/server.py::friendly_error` (parity table §3):
 * collapse whitespace, truncate the message to 300 chars, then map
 * well-known markers to stable user-facing strings. The read mappings stay
 * first; the write-domain mappings (plan Task 5) follow, then the
 * already-user-ready guard/duplicate messages pass through as-is.
 */

const AUTH_MARKERS = ["jwt", "token", "session", "auth"] as const;

/**
 * Write-domain SQL markers → clean sentences, first match wins (plan Task 5).
 * Matched (case-insensitively) after every existing read mapping.
 */
const WRITE_MAPPINGS: ReadonlyArray<readonly [marker: string, text: string]> = [
  ["reason required", "A rejection reason is required."],
  ["gender mismatch", "That room's gender does not match the student's."],
  ["room full", "That room has no free places."],
  [
    "student not found",
    "Student not found (the id may be stale — re-check with list_pending_registrations or search_students).",
  ],
  ["room not found", "Room not found (the id may be stale — re-check with list_rooms)."],
  [
    "pending request not found",
    "No pending room-change request with that id (it may already be decided — re-check with list_room_change_requests).",
  ],
  [
    "ticket not found",
    "Maintenance ticket not found (re-check with list_maintenance_tickets).",
  ],
];

/** Guard/duplicate messages that are already user-ready: returned as-is. */
const WRITE_PASSTHROUGH = [
  "cannot delete room",
  "cannot set capacity",
  "cannot change the gender",
  "already exists",
] as const;

export function friendlyError(error: unknown): string {
  const raw = error instanceof Error ? error.message : String(error);
  const message = raw
    .split(/\s+/)
    .filter((part) => part.length > 0)
    .join(" ")
    .slice(0, 300);
  const lowered = message.toLowerCase();
  if (lowered.includes("admin only") || lowered.includes("permission denied")) {
    return (
      "Permission denied: this tool requires an administrator account " +
      "(profiles.role = 'admin')."
    );
  }
  if (lowered.includes("invalid status") || lowered.includes("query required")) {
    return `Invalid request: ${message}`;
  }
  if (AUTH_MARKERS.some((marker) => lowered.includes(marker))) {
    return (
      "The server could not authenticate with Supabase. " +
      "Check ADMIN_EMAIL / ADMIN_PASSWORD in mcp/.env."
    );
  }
  for (const [marker, text] of WRITE_MAPPINGS) {
    if (lowered.includes(marker)) return text;
  }
  if (WRITE_PASSTHROUGH.some((marker) => lowered.includes(marker))) {
    return message;
  }
  return `Error talking to Supabase: ${message}`;
}
