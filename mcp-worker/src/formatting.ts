/**
 * Pure helpers for the Residence Tlemcen admin MCP worker.
 *
 * TypeScript port of `mcp/formatting.py` (the parity source of truth):
 * everything here is dependency-free, network-free and deterministic so it
 * can be unit-tested with plain vitest.
 */

/** Free text longer than this is truncated in tool results (spec: 500 chars). */
export const MAX_FREE_TEXT = 500;

/** Free-text fields present in the jsonb rows returned by the mcp_* SQL functions. */
export const FREE_TEXT_FIELDS = [
  "description",
  "staff_note",
  "reason",
  "decision_note",
  "rejection_reason",
] as const;

export const DEFAULT_LIMIT = 20;
export const MAX_LIMIT = 100;

export const TICKET_STATUSES = ["pending", "in_progress", "resolved"] as const;
export const ROOM_CHANGE_STATUSES = ["pending", "approved", "rejected"] as const;

const EMPTY_LABELS: Record<string, string> = {
  tickets: "maintenance tickets",
  room_changes: "room change requests",
  registrations: "pending registrations",
  students: "students matching your search",
  rooms: "rooms",
};

/**
 * Truncate free text to at most `limit` characters (adding "..." when cut).
 *
 * `null`/`undefined` pass through unchanged. Mirrors
 * `formatting.truncate_text`: the kept prefix is right-stripped before the
 * ellipsis is appended.
 */
export function truncateText(value: unknown, limit: number = MAX_FREE_TEXT): string | null {
  if (value === null || value === undefined) return null;
  const text = String(value);
  if (text.length <= limit) return text;
  return text.slice(0, Math.max(limit - 3, 0)).replace(/\s+$/, "") + "...";
}

/**
 * Recursively truncate the given free-text fields in dicts/lists of dicts.
 *
 * Mirrors `formatting.truncate_records`: strings under `fields` are truncated,
 * nested objects/arrays are recursed into, everything else is returned as-is
 * (a new structure — the input is never mutated).
 */
export function truncateRecords(
  records: unknown,
  fields: readonly string[] = FREE_TEXT_FIELDS,
  limit: number = MAX_FREE_TEXT,
): unknown {
  if (Array.isArray(records)) {
    return records.map((item) => truncateRecords(item, fields, limit));
  }
  if (records !== null && typeof records === "object") {
    const out: Record<string, unknown> = {};
    for (const [key, value] of Object.entries(records)) {
      if (fields.includes(key) && typeof value === "string") {
        out[key] = truncateText(value, limit);
      } else if (value !== null && typeof value === "object") {
        out[key] = truncateRecords(value, fields, limit);
      } else {
        out[key] = value;
      }
    }
    return out;
  }
  return records;
}

/**
 * Coerce a user-supplied limit into `[1, maximum]`; `null`/`undefined` become
 * the default. Throws `Error("limit must be a number")` for non-numeric input
 * (booleans included), mirroring `formatting.cap_limit`.
 */
export function capLimit(
  limit: unknown,
  defaultLimit: number = DEFAULT_LIMIT,
  maximum: number = MAX_LIMIT,
): number {
  if (limit === null || limit === undefined) return defaultLimit;
  let value: number;
  if (typeof limit === "number") {
    value = limit;
  } else if (typeof limit === "string") {
    // Python's int("...") equivalent: optional sign + digits only.
    const trimmed = limit.trim();
    if (!/^[+-]?\d+$/.test(trimmed)) throw new Error("limit must be a number");
    value = Number(trimmed);
  } else {
    // Booleans, arrays, objects, functions, ... are all rejected by Python too.
    throw new Error("limit must be a number");
  }
  if (!Number.isFinite(value)) throw new Error("limit must be a number");
  return Math.max(1, Math.min(Math.trunc(value), maximum));
}

/** Python-style repr for error messages (close enough for status values). */
function pyRepr(value: unknown): string {
  if (typeof value === "string") {
    return `'${value.replace(/\\/g, "\\\\").replace(/'/g, "\\'")}'`;
  }
  if (value === null || value === undefined) return "None";
  if (typeof value === "boolean") return value ? "True" : "False";
  return String(value);
}

/**
 * Normalize and validate a status filter; `null`/`undefined` pass through.
 *
 * Accepts e.g. 'Pending', 'in progress', 'in-progress' for 'in_progress'.
 * Throws `Error` listing the allowed values for anything else, mirroring
 * `formatting.validate_status`.
 */
export function validateStatus(
  value: unknown,
  allowed: readonly string[] = TICKET_STATUSES,
  label = "status",
): string | null {
  if (value === null || value === undefined) return null;
  const normalized = String(value)
    .trim()
    .toLowerCase()
    .replace(/-/g, "_")
    .replace(/ /g, "_");
  if (!allowed.includes(normalized)) {
    throw new Error(`invalid ${label} ${pyRepr(value)}: expected one of ${allowed.join(", ")}`);
  }
  return normalized;
}

/**
 * Friendly message used when a query returns no rows.
 * Ports `formatting.empty_message` verbatim.
 */
export function emptyMessage(
  entity: string,
  status?: string | null,
  block?: string | null,
): string {
  if (entity === "students") return "No students matched your search.";
  if (entity === "registrations") return "No pending registrations found.";
  if (entity === "rooms") {
    if (block) return `No rooms found in block ${block}.`;
    return "No rooms found.";
  }
  const label = EMPTY_LABELS[entity];
  if (label === undefined) throw new Error(`unknown entity: ${entity}`);
  if (status) return `No ${status.replace(/_/g, "-")} ${label} found.`;
  return `No ${label} found.`;
}

/**
 * Compact, non-ASCII-preserving JSON string, ready for a tool result.
 * Mirrors `formatting.to_compact_json` (`json.dumps` with `ensure_ascii=False`
 * and `(",", ":")` separators — `JSON.stringify` emits exactly that).
 */
export function toCompactJson(payload: unknown): string {
  const result = JSON.stringify(payload);
  return result === undefined ? "null" : result;
}

/**
 * Constant-time token comparison.
 *
 * Length mismatch returns false immediately (lengths are not secret); equal
 * lengths are compared with the workerd extension
 * `crypto.subtle.timingSafeEqual` when available, with a bitwise-XOR
 * accumulate fallback for runtimes that lack it (e.g. Node under vitest —
 * same constant-work algorithm for equal-length inputs).
 */
export function tokenEquals(
  provided: string | null | undefined,
  expected: string | null | undefined,
): boolean {
  if (!provided || !expected) return false;
  const encoder = new TextEncoder();
  const a = encoder.encode(provided);
  const b = encoder.encode(expected);
  if (a.byteLength !== b.byteLength) return false;
  // workerd declares `crypto` as a bare global (not a `globalThis` property).
  const subtle = (globalThis as unknown as { crypto: { subtle: SubtleCrypto } }).crypto.subtle as
    SubtleCrypto & {
      timingSafeEqual?: (x: ArrayBuffer | ArrayBufferView, y: ArrayBuffer | ArrayBufferView) => boolean;
    };
  if (typeof subtle.timingSafeEqual === "function") {
    return subtle.timingSafeEqual(a, b);
  }
  let diff = 0;
  for (let i = 0; i < a.length; i++) {
    diff |= a[i]! ^ b[i]!;
  }
  return diff === 0;
}

/**
 * Sliding-window rate limiter, keyed by client (e.g. IP address).
 *
 * Pure and deterministic when `now` is passed in tests. Ports
 * `formatting.RateLimiter`: blocked requests are not recorded, and a hit
 * expires once `now - window >= hit` (cutoff inclusive).
 */
export class RateLimiter {
  readonly limit: number;
  readonly windowSeconds: number;
  private readonly hits = new Map<string, number[]>();

  constructor(limit = 60, windowSeconds = 60.0) {
    if (limit <= 0 || windowSeconds <= 0) {
      throw new Error("limit and window_seconds must be positive");
    }
    this.limit = Math.trunc(limit);
    this.windowSeconds = Number(windowSeconds);
  }

  /** Record one hit for `key`; return false while over the limit. */
  allow(key: string, now?: number): boolean {
    const moment = now ?? performance.now() / 1000;
    const hits = this.hits.get(key) ?? [];
    const cutoff = moment - this.windowSeconds;
    while (hits.length > 0 && hits[0]! <= cutoff) {
      hits.shift();
    }
    if (hits.length >= this.limit) {
      this.hits.set(key, hits);
      return false;
    }
    hits.push(moment);
    this.hits.set(key, hits);
    return true;
  }
}
