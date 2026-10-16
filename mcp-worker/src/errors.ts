/**
 * Friendly, safe error text: no traceback, no secrets.
 *
 * TypeScript port of `mcp/server.py::friendly_error` (parity table §3):
 * collapse whitespace, truncate the message to 300 chars, then map
 * well-known markers to stable user-facing strings.
 */

const AUTH_MARKERS = ["jwt", "token", "session", "auth"] as const;

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
  return `Error talking to Supabase: ${message}`;
}
