/**
 * Unit tests for `src/formatting.ts` — the TypeScript port of `mcp/formatting.py`.
 *
 * The expected values below are ported from the Python test suite
 * (`mcp/tests/test_formatting.py`), which was taken from the actual Python
 * code (the parity source of truth). Pure and deterministic: no network, no
 * file I/O, no real clock (the rate limiter takes an injected `now`).
 */
import { describe, expect, it, vi } from "vitest";

import {
  DEFAULT_LIMIT,
  FREE_TEXT_FIELDS,
  MAX_FREE_TEXT,
  MAX_LIMIT,
  ROOM_CHANGE_STATUSES,
  RateLimiter,
  TICKET_STATUSES,
  capLimit,
  emptyMessage,
  toCompactJson,
  tokenEquals,
  truncateRecords,
  truncateText,
  validateStatus,
} from "../src/formatting";

// ---------------------------------------------------------------------------
// Constants: the contract the rest of the server relies on
// ---------------------------------------------------------------------------

describe("constants", () => {
  it("match the contract", () => {
    expect(MAX_FREE_TEXT).toBe(500);
    expect(DEFAULT_LIMIT).toBe(20);
    expect(MAX_LIMIT).toBe(100);
    expect(new Set(FREE_TEXT_FIELDS)).toEqual(
      new Set(["description", "staff_note", "reason", "decision_note", "rejection_reason"]),
    );
    expect(TICKET_STATUSES).toEqual(["pending", "in_progress", "resolved"]);
    expect(ROOM_CHANGE_STATUSES).toEqual(["pending", "approved", "rejected"]);
  });
});

// ---------------------------------------------------------------------------
// truncateText
// ---------------------------------------------------------------------------

describe("truncateText", () => {
  it("leaves short text unchanged", () => {
    expect(truncateText("short note")).toBe("short note");
    expect(truncateText("")).toBe("");
  });

  it("passes null/undefined through", () => {
    expect(truncateText(null)).toBeNull();
    expect(truncateText(undefined)).toBeNull();
  });

  it("stringifies non-string values", () => {
    expect(truncateText(42)).toBe("42");
  });

  it("keeps text of exactly 500 chars unchanged", () => {
    const text = "a".repeat(MAX_FREE_TEXT);
    const result = truncateText(text);
    expect(result).toBe(text);
    expect(result!.length).toBe(MAX_FREE_TEXT);
    expect(result!.endsWith("...")).toBe(false);
  });

  it("truncates 501 chars to exactly 500 ending with an ellipsis", () => {
    // Code: text.slice(0, limit - 3).replace(/\s+$/, "") + "..." -> 497 + 3 = 500.
    const text = "a".repeat(MAX_FREE_TEXT + 1);
    const result = truncateText(text);
    expect(result).toBe("a".repeat(MAX_FREE_TEXT - 3) + "...");
    expect(result!.length).toBe(MAX_FREE_TEXT);
    expect(result!.endsWith("...")).toBe(true);
  });

  it("truncates long text to 500 total", () => {
    const result = truncateText("word ".repeat(1000));
    expect(result!.length).toBe(MAX_FREE_TEXT);
    expect(result!.endsWith("...")).toBe(true);
  });

  it("counts unicode in characters, not bytes", () => {
    const result = truncateText("é".repeat(600));
    expect(result!.length).toBe(MAX_FREE_TEXT);
    expect([...result!].filter((ch) => ch === "é").length).toBe(MAX_FREE_TEXT - 3);
    expect(result!.endsWith("...")).toBe(true);
  });

  it("strips trailing whitespace at the cut point", () => {
    // limit=10 -> keep text.slice(0, 7) ("abcdef ") then rstrip -> "abcdef...".
    const result = truncateText("abcdef   ghijkl", 10);
    expect(result).toBe("abcdef...");
    expect(result!.length).toBeLessThanOrEqual(10);
  });

  it("honors a custom limit", () => {
    const result = truncateText("x".repeat(50), 10);
    expect(result).toBe("x".repeat(7) + "...");
    expect(result!.length).toBe(10);
  });

  it("produces only the ellipsis marker when limit is 3", () => {
    expect(truncateText("abcdef", 3)).toBe("...");
  });
});

// ---------------------------------------------------------------------------
// truncateRecords
// ---------------------------------------------------------------------------

describe("truncateRecords", () => {
  it("truncates nested free-text fields and preserves structure", () => {
    const long = "L".repeat(MAX_FREE_TEXT + 100);
    const expected = "L".repeat(MAX_FREE_TEXT - 3) + "...";
    const data = {
      id: 7,
      description: long,
      staff_note: "short",
      university: long, // not a free-text field: untouched
      inner: { reason: long, count: 3 },
      items: [{ decision_note: long, label: "x" }, { rejection_reason: long }],
      empty: null,
    };

    const out = truncateRecords(data) as typeof data;

    expect(out.id).toBe(7);
    expect(out.description).toBe(expected);
    expect(out.staff_note).toBe("short");
    expect(out.university).toBe(long);
    expect(out.inner).toEqual({ reason: expected, count: 3 });
    expect(out.items[0]).toEqual({ decision_note: expected, label: "x" });
    expect(out.items[1]).toEqual({ rejection_reason: expected });
    expect(out.empty).toBeNull();
    expect(expected.length).toBe(MAX_FREE_TEXT);
  });

  it("truncates every declared free-text field", () => {
    const long = "Z".repeat(MAX_FREE_TEXT + 1);
    const input: Record<string, unknown> = {};
    for (const field of FREE_TEXT_FIELDS) input[field] = long;
    const out = truncateRecords(input) as Record<string, string>;
    expect(new Set(Object.keys(out))).toEqual(new Set(FREE_TEXT_FIELDS));
    for (const field of FREE_TEXT_FIELDS) {
      expect(out[field]).toBe("Z".repeat(MAX_FREE_TEXT - 3) + "...");
    }
  });

  it("leaves non-free-text fields untouched even when long", () => {
    const long = "N".repeat(MAX_FREE_TEXT * 2);
    expect(truncateRecords({ university: long, phone: long })).toEqual({
      university: long,
      phone: long,
    });
  });

  it("does not mutate the input", () => {
    const long = "M".repeat(MAX_FREE_TEXT * 2);
    const data = { description: long, inner: { reason: long } };
    truncateRecords(data);
    expect(data.description).toBe(long);
    expect(data.inner.reason).toBe(long);
  });

  it("supports custom fields and limit", () => {
    const data = { notes: "abcdefghij", description: "abcdefghij" };
    expect(truncateRecords(data, ["notes"], 7)).toEqual({
      notes: "abcd...",
      description: "abcdefghij",
    });
  });

  it("leaves non-string field values untouched", () => {
    expect(
      truncateRecords({ description: null, reason: 123, staff_note: ["inline"] }),
    ).toEqual({ description: null, reason: 123, staff_note: ["inline"] });
  });

  it("passes scalars and empty containers through", () => {
    expect(truncateRecords("plain")).toBe("plain");
    expect(truncateRecords(5)).toBe(5);
    expect(truncateRecords(null)).toBeNull();
    expect(truncateRecords([])).toEqual([]);
    expect(truncateRecords({})).toEqual({});
  });

  it("truncates inside nested lists of lists", () => {
    const long = "Q".repeat(MAX_FREE_TEXT + 5);
    expect(truncateRecords([[{ description: long }]])).toEqual([
      [{ description: "Q".repeat(MAX_FREE_TEXT - 3) + "..." }],
    ]);
  });
});

// ---------------------------------------------------------------------------
// capLimit
// ---------------------------------------------------------------------------

describe("capLimit", () => {
  it("returns the default for null/undefined", () => {
    expect(capLimit(null)).toBe(DEFAULT_LIMIT);
    expect(capLimit(undefined)).toBe(DEFAULT_LIMIT);
    expect(capLimit(null, 7)).toBe(7);
  });

  it("passes valid values through", () => {
    for (const value of [1, 20, 50, MAX_LIMIT]) {
      expect(capLimit(value)).toBe(value);
    }
  });

  it("caps values above the maximum", () => {
    expect(capLimit(MAX_LIMIT + 1)).toBe(MAX_LIMIT);
    expect(capLimit(10_000)).toBe(MAX_LIMIT);
  });

  it("respects a custom maximum", () => {
    expect(capLimit(50, DEFAULT_LIMIT, 10)).toBe(10);
  });

  it("floors zero and negatives to one", () => {
    expect(capLimit(0)).toBe(1);
    expect(capLimit(-5)).toBe(1);
    expect(capLimit(-0.5)).toBe(1);
  });

  it("accepts numeric strings and then caps them", () => {
    expect(capLimit("30")).toBe(30);
    expect(capLimit("999")).toBe(MAX_LIMIT);
    expect(capLimit("0")).toBe(1);
  });

  it("truncates floats toward zero", () => {
    expect(capLimit(2.9)).toBe(2);
    expect(capLimit(100.99)).toBe(MAX_LIMIT);
    expect(capLimit(0.9)).toBe(1);
  });

  it.each([
    ["letters", "abc"],
    ["empty-string", ""],
    ["float-string", "10.5"],
    ["true", true],
    ["false", false],
    ["list", []],
    ["dict", {}],
    ["object", { }],
    ["nan", Number.NaN],
    ["infinity", Number.POSITIVE_INFINITY],
    ["function", () => 1],
  ])("rejects invalid input: %s", (_label, bad) => {
    expect(() => capLimit(bad)).toThrow("limit must be a number");
  });

  it("uses an exact ValueError-equivalent message", () => {
    expect(() => capLimit("abc")).toThrowError(
      expect.objectContaining({ message: "limit must be a number" }) as Error,
    );
  });
});

// ---------------------------------------------------------------------------
// validateStatus
// ---------------------------------------------------------------------------

describe("validateStatus", () => {
  it.each([
    ["pending", "pending"],
    ["Pending", "pending"],
    ["PENDING", "pending"],
    ["in_progress", "in_progress"],
    ["In Progress", "in_progress"],
    ["in-progress", "in_progress"],
    ["IN-PROGRESS", "in_progress"],
    [" In-Progress ", "in_progress"],
    ["resolved", "resolved"],
    ["Resolved", "resolved"],
  ])("normalizes case, spaces and hyphens: %s", (value, expected) => {
    expect(validateStatus(value)).toBe(expected);
  });

  it("passes null/undefined through", () => {
    expect(validateStatus(null)).toBeNull();
    expect(validateStatus(undefined)).toBeNull();
  });

  it("normalizes room-change statuses with the allowed override", () => {
    expect(validateStatus("Pending", ROOM_CHANGE_STATUSES)).toBe("pending");
    expect(validateStatus("Approved", ROOM_CHANGE_STATUSES)).toBe("approved");
    expect(validateStatus("rejected", ROOM_CHANGE_STATUSES)).toBe("rejected");
  });

  it("rejects a ticket status for room changes", () => {
    expect(() => validateStatus("in_progress", ROOM_CHANGE_STATUSES)).toThrow();
  });

  it("produces the exact invalid-status message", () => {
    expect(() => validateStatus("bogus")).toThrowError(
      "invalid status 'bogus': expected one of pending, in_progress, resolved",
    );
  });

  it("includes a custom label in the error", () => {
    expect(() => validateStatus("bogus", ROOM_CHANGE_STATUSES, "room change status")).toThrowError(
      "invalid room change status 'bogus': expected one of pending, approved, rejected",
    );
  });

  it("rejects non-string invalid values", () => {
    expect(() => validateStatus(5)).toThrowError(
      "invalid status 5: expected one of pending, in_progress, resolved",
    );
  });
});

// ---------------------------------------------------------------------------
// emptyMessage
// ---------------------------------------------------------------------------

describe("emptyMessage", () => {
  it("students", () => {
    expect(emptyMessage("students")).toBe("No students matched your search.");
  });

  it("registrations", () => {
    expect(emptyMessage("registrations")).toBe("No pending registrations found.");
  });

  it("rooms without a block", () => {
    expect(emptyMessage("rooms")).toBe("No rooms found.");
    expect(emptyMessage("rooms", null, "")).toBe("No rooms found.");
  });

  it("rooms with a block", () => {
    expect(emptyMessage("rooms", null, "B")).toBe("No rooms found in block B.");
  });

  it("tickets without a status", () => {
    expect(emptyMessage("tickets")).toBe("No maintenance tickets found.");
  });

  it("tickets with pending status", () => {
    expect(emptyMessage("tickets", "pending")).toBe("No pending maintenance tickets found.");
  });

  it("tickets with in_progress status use a hyphen", () => {
    expect(emptyMessage("tickets", "in_progress")).toBe(
      "No in-progress maintenance tickets found.",
    );
  });

  it("room changes without a status", () => {
    expect(emptyMessage("room_changes")).toBe("No room change requests found.");
  });

  it("room changes with status", () => {
    expect(emptyMessage("room_changes", "pending")).toBe("No pending room change requests found.");
  });

  it("ignores status and block for students and registrations", () => {
    expect(emptyMessage("students", "pending")).toBe("No students matched your search.");
    expect(emptyMessage("registrations", null, "A")).toBe("No pending registrations found.");
  });

  it("throws for an unknown entity", () => {
    expect(() => emptyMessage("bogus")).toThrow("unknown entity: bogus");
  });
});

// ---------------------------------------------------------------------------
// toCompactJson
// ---------------------------------------------------------------------------

describe("toCompactJson", () => {
  it("produces compact JSON", () => {
    expect(toCompactJson({ a: 1, b: [1, 2], c: null })).toBe('{"a":1,"b":[1,2],"c":null}');
  });

  it("keeps non-ASCII characters literal", () => {
    expect(toCompactJson({ city: "Tlemcené" })).toBe('{"city":"Tlemcené"}');
  });

  it("round-trips losslessly", () => {
    const payload = { description: "café ☕".repeat(10), n: [1, "x", true] };
    expect(JSON.parse(toCompactJson(payload))).toEqual(payload);
  });

  it("has no separator whitespace", () => {
    expect(toCompactJson({ a: 1, b: 2 })).not.toContain(" ");
  });

  it("renders undefined like Python's None", () => {
    expect(toCompactJson(undefined)).toBe("null");
  });
});

// ---------------------------------------------------------------------------
// tokenEquals
// ---------------------------------------------------------------------------

describe("tokenEquals", () => {
  it("accepts an equal token", () => {
    expect(tokenEquals("abc123", "abc123")).toBe(true);
  });

  it("rejects a different token", () => {
    expect(tokenEquals("abc123", "different")).toBe(false);
  });

  it("is case-sensitive", () => {
    expect(tokenEquals("ABC123", "abc123")).toBe(false);
  });

  it("rejects missing/empty inputs", () => {
    expect(tokenEquals(null, "abc123")).toBe(false);
    expect(tokenEquals("abc123", null)).toBe(false);
    expect(tokenEquals("", "abc123")).toBe(false);
    expect(tokenEquals("abc123", "")).toBe(false);
    expect(tokenEquals(undefined, undefined)).toBe(false);
  });

  it("compares tokens of equal length correctly", () => {
    expect(tokenEquals("token-aaaa", "token-bbbb")).toBe(false);
    expect(tokenEquals("token-aaaa", "token-aaaa")).toBe(true);
  });

  it("accepts a short token when equal (minimum length is enforced by config)", () => {
    expect(tokenEquals("short", "short")).toBe(true);
  });

  it("delegates to crypto.subtle.timingSafeEqual when the runtime provides it", () => {
    const calls: unknown[] = [];
    vi.stubGlobal("crypto", {
      subtle: {
        timingSafeEqual: (a: unknown, b: unknown) => {
          calls.push([a, b]);
          return true;
        },
      },
    });
    try {
      expect(tokenEquals("abc123", "abc123")).toBe(true);
      expect(calls).toHaveLength(1);
    } finally {
      vi.unstubAllGlobals();
    }
  });
});

// ---------------------------------------------------------------------------
// RateLimiter
// ---------------------------------------------------------------------------

describe("RateLimiter", () => {
  it("allows up to the limit and blocks the next", () => {
    const limiter = new RateLimiter(3, 60);
    expect([1, 2, 3].map(() => limiter.allow("ip", 100))).toEqual([true, true, true]);
    expect(limiter.allow("ip", 100)).toBe(false);
  });

  it("does not let blocked requests extend the window", () => {
    const limiter = new RateLimiter(1, 10);
    expect(limiter.allow("ip", 0)).toBe(true);
    expect(limiter.allow("ip", 0)).toBe(false);
    expect(limiter.allow("ip", 5)).toBe(false);
    expect(limiter.allow("ip", 9.9)).toBe(false);
    // A hit at t expires when now - window >= t (cutoff is inclusive).
    expect(limiter.allow("ip", 10)).toBe(true);
  });

  it("frees sliding-window slots one by one", () => {
    const limiter = new RateLimiter(2, 10);
    expect(limiter.allow("ip", 0)).toBe(true);
    expect(limiter.allow("ip", 5)).toBe(true);
    expect(limiter.allow("ip", 5)).toBe(false);
    expect(limiter.allow("ip", 10)).toBe(true); // the t=0 hit expired
    expect(limiter.allow("ip", 10)).toBe(false); // the t=5 hit still counts
    expect(limiter.allow("ip", 15)).toBe(true); // the t=5 hit expired
  });

  it("isolates keys", () => {
    const limiter = new RateLimiter(1, 60);
    expect(limiter.allow("a", 0)).toBe(true);
    expect(limiter.allow("a", 0)).toBe(false);
    expect(limiter.allow("b", 0)).toBe(true);
    expect(limiter.allow("b", 0)).toBe(false);
  });

  it("uses the default clock when now is omitted", () => {
    const limiter = new RateLimiter(2, 60);
    expect(limiter.allow("ip")).toBe(true);
    expect(limiter.allow("ip")).toBe(true);
    expect(limiter.allow("ip")).toBe(false);
  });

  it("defaults match the documented 60 per minute", () => {
    const limiter = new RateLimiter();
    expect(limiter.limit).toBe(60);
    expect(limiter.windowSeconds).toBe(60);
    expect(Array.from({ length: 60 }, () => limiter.allow("ip", 0)).every(Boolean)).toBe(true);
    expect(limiter.allow("ip", 0)).toBe(false);
  });

  it("rejects a non-positive limit or window", () => {
    expect(() => new RateLimiter(0)).toThrow("limit and window_seconds must be positive");
    expect(() => new RateLimiter(-1)).toThrow();
    expect(() => new RateLimiter(60, 0)).toThrow();
    expect(() => new RateLimiter(1, -0.1)).toThrow();
  });
});
