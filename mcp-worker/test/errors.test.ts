/**
 * Unit tests for `src/errors.ts` — the TypeScript port of
 * `mcp/server.py::friendly_error` (parity table §3).
 */
import { describe, expect, it } from "vitest";

import { friendlyError } from "../src/errors";

const PERMISSION_DENIED =
  "Permission denied: this tool requires an administrator account (profiles.role = 'admin').";
const AUTH_FAILED =
  "The server could not authenticate with Supabase. Check ADMIN_EMAIL / ADMIN_PASSWORD in mcp/.env.";

describe("friendlyError", () => {
  it("maps 'admin only' errors to the permission message", () => {
    expect(friendlyError(new Error("admin only"))).toBe(PERMISSION_DENIED);
    expect(friendlyError(new Error("ERROR: admin only"))).toBe(PERMISSION_DENIED);
    expect(friendlyError(new Error("permission denied for function mcp_summary"))).toBe(
      PERMISSION_DENIED,
    );
  });

  it("is case-insensitive for marker matching", () => {
    expect(friendlyError(new Error("ADMIN ONLY"))).toBe(PERMISSION_DENIED);
    expect(friendlyError(new Error("Permission Denied"))).toBe(PERMISSION_DENIED);
  });

  it("maps 'invalid status' / 'query required' errors to Invalid request", () => {
    expect(friendlyError(new Error("invalid status 'bogus': expected one of pending"))).toBe(
      "Invalid request: invalid status 'bogus': expected one of pending",
    );
    expect(friendlyError(new Error("query required"))).toBe("Invalid request: query required");
  });

  it("gives Invalid request priority over auth markers", () => {
    expect(friendlyError(new Error("invalid status 'bogus': auth token suggested"))).toBe(
      "Invalid request: invalid status 'bogus': auth token suggested",
    );
    expect(friendlyError(new Error("query required: invalid jwt"))).toBe(
      "Invalid request: query required: invalid jwt",
    );
  });

  it("maps auth-ish markers to the Supabase authentication message", () => {
    for (const message of [
      "JWT expired",
      "invalid JWT",
      "token has expired",
      "session not found",
      "refresh token not found",
      "Unauthorized",
      "auth error",
      "Invalid Authentication",
    ]) {
      expect(friendlyError(new Error(message))).toBe(AUTH_FAILED);
    }
  });

  it("does not treat 'invalid claim' as an auth marker (Python parity)", () => {
    expect(friendlyError(new Error("invalid claim: missing sub claim"))).toBe(
      "Error talking to Supabase: invalid claim: missing sub claim",
    );
  });

  it("gives the permission message priority over auth markers", () => {
    expect(friendlyError(new Error("admin only: invalid jwt token"))).toBe(PERMISSION_DENIED);
  });

  it("maps the write-domain markers to clean sentences", () => {
    expect(friendlyError(new Error("reason required"))).toBe("A rejection reason is required.");
    expect(friendlyError(new Error("gender mismatch"))).toBe(
      "That room's gender does not match the student's.",
    );
    expect(friendlyError(new Error("room full"))).toBe("That room has no free places.");
    expect(friendlyError(new Error("student not found"))).toBe(
      "Student not found (the id may be stale — re-check with list_pending_registrations or search_students).",
    );
    expect(friendlyError(new Error("room not found"))).toBe(
      "Room not found (the id may be stale — re-check with list_rooms).",
    );
    expect(friendlyError(new Error("pending request not found"))).toBe(
      "No pending room-change request with that id (it may already be decided — re-check with list_room_change_requests).",
    );
    expect(friendlyError(new Error("ticket not found"))).toBe(
      "Maintenance ticket not found (re-check with list_maintenance_tickets).",
    );
  });

  it("passes the room-guard and duplicate messages through as-is", () => {
    for (const message of [
      "Cannot delete room B-101: 2 active resident(s) are still assigned.",
      "Cannot set capacity below the 2 active resident(s) already assigned.",
      "Cannot change the gender of an occupied room.",
      "Room ZZT-999 already exists.",
    ]) {
      expect(friendlyError(new Error(message))).toBe(message);
    }
  });

  it("is case-insensitive for write markers and keeps the read mappings first", () => {
    expect(friendlyError(new Error("REASON REQUIRED"))).toBe("A rejection reason is required.");
    expect(friendlyError(new Error("ERROR: GENDER MISMATCH"))).toBe(
      "That room's gender does not match the student's.",
    );
    // Read mappings and auth detection still win when both families match.
    expect(friendlyError(new Error("admin only: room not found"))).toBe(PERMISSION_DENIED);
    expect(friendlyError(new Error("invalid status 'x': ticket not found"))).toBe(
      "Invalid request: invalid status 'x': ticket not found",
    );
    expect(friendlyError(new Error("token expired: student not found"))).toBe(AUTH_FAILED);
    // First write marker wins when a message contains several.
    expect(friendlyError(new Error("reason required: room not found"))).toBe(
      "A rejection reason is required.",
    );
  });

  it("falls back to the generic Supabase error with the original message", () => {
    expect(friendlyError(new Error("connection reset by peer"))).toBe(
      "Error talking to Supabase: connection reset by peer",
    );
  });

  it("collapses whitespace before matching and returning", () => {
    expect(friendlyError(new Error("boom\n\n  something\telse"))).toBe(
      "Error talking to Supabase: boom something else",
    );
  });

  it("truncates the collapsed message part to 300 characters", () => {
    expect(friendlyError(new Error("y".repeat(1000)))).toBe(
      `Error talking to Supabase: ${"y".repeat(300)}`,
    );
  });

  it("checks markers only on the collapsed, 300-char-truncated message", () => {
    // "admin only" beyond 300 chars is cut before the marker check (Python parity).
    const long = "x".repeat(300) + "admin only";
    expect(friendlyError(new Error(long))).toBe(`Error talking to Supabase: ${"x".repeat(300)}`);
  });

  it("handles non-Error inputs", () => {
    expect(friendlyError("admin only")).toBe(PERMISSION_DENIED);
    expect(friendlyError("plain failure")).toBe("Error talking to Supabase: plain failure");
  });

  it("handles an empty message", () => {
    expect(friendlyError(new Error(""))).toBe("Error talking to Supabase: ");
  });
});
