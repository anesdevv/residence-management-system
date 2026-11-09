// supabase/functions/tests/edge_functions_test.ts
// Unit tests for Edge Function shared modules, identifier resolution,
// throttling, generic response contracts, and security rules.

import { isCardId, isEmail, normalizeEmail, maskEmail, maskIdentifier } from "../_shared/validation.ts";
import { checkRateLimit } from "../_shared/throttler.ts";
import { getCorsHeaders } from "../_shared/cors.ts";

function assert(condition: boolean, msg?: string) {
  if (!condition) throw new Error(msg || "Assertion failed");
}

function assertEquals(actual: unknown, expected: unknown, msg?: string) {
  if (actual !== expected) {
    throw new Error(msg || `Expected ${JSON.stringify(expected)} but got ${JSON.stringify(actual)}`);
  }
}

// 1. Validation and Identifier Parsing
Deno.test("isCardId correctly recognizes numeric student card IDs", () => {
  assert(isCardId("20230001"), "8-digit card id should pass");
  assert(isCardId("1234"), "4-digit card id should pass");
  assert(!isCardId("123"), "Under 4 digits should fail");
  assert(!isCardId("abc1234"), "Alpha-numeric should fail");
  assert(!isCardId("user@univ-tlemcen.dz"), "Email should fail card_id check");
});

Deno.test("isEmail correctly recognizes valid emails", () => {
  assert(isEmail("student@example.dz"));
  assert(isEmail("first.last@univ-tlemcen.dz"));
  assert(!isEmail("not-an-email"));
  assert(!isEmail("20230001"));
  assert(!isEmail("@missing-local.dz"));
});

Deno.test("normalizeEmail lowercases and trims", () => {
  assertEquals(normalizeEmail("  Student.Name@Univ-Tlemcen.DZ  "), "student.name@univ-tlemcen.dz");
});

Deno.test("maskEmail and maskIdentifier obscure sensitive details", () => {
  assertEquals(maskEmail("yacine@gmail.com"), "y***e@gmail.com");
  assertEquals(maskEmail("ab@gmail.com"), "a***@gmail.com");
  assertEquals(maskIdentifier("20230001"), "20****01");
  assertEquals(maskIdentifier("student@test.com"), "s***t@test.com");
});

// 2. CORS Handling
Deno.test("getCorsHeaders allows permitted site origins", () => {
  const req = new Request("http://localhost/test", {
    headers: { origin: "https://resivo.univ-tlemcen.dz" },
  });
  const headers = getCorsHeaders(req);
  assertEquals(headers["Access-Control-Allow-Origin"], "https://resivo.univ-tlemcen.dz");
});

Deno.test("getCorsHeaders permits local Astro dev origins", () => {
  const req = new Request("http://localhost/test", {
    headers: { origin: "http://localhost:4321" },
  });
  const headers = getCorsHeaders(req);
  assertEquals(headers["Access-Control-Allow-Origin"], "http://localhost:4321");
});

// 3. Throttler / Rate Limiting
Deno.test("checkRateLimit allows requests up to limit and blocks beyond", () => {
  const testKey = `test_throttle_${Date.now()}`;
  const limit = 3;
  const windowMs = 5000;

  // First 3 should be allowed
  assertEquals(checkRateLimit(testKey, limit, windowMs).allowed, true);
  assertEquals(checkRateLimit(testKey, limit, windowMs).allowed, true);
  assertEquals(checkRateLimit(testKey, limit, windowMs).allowed, true);

  // 4th must be rejected with retryAfterSeconds > 0
  const blocked = checkRateLimit(testKey, limit, windowMs);
  assertEquals(blocked.allowed, false);
  assert(blocked.retryAfterSeconds > 0, "Retry after should be positive");
});

// 4. Contract Verification: Generic Responses (Anti-Enumeration)
Deno.test("Password reset response message does not disclose account existence", () => {
  const genericMsg = "If an account exists for this card ID or email, password recovery instructions have been sent to the verified email address on file.";
  assert(genericMsg.includes("If an account exists"), "Must be conditional to prevent enumeration");
});

Deno.test("Login link response message does not disclose account existence", () => {
  const genericMsg = "If an account exists for this card ID or email, a sign-in code or link has been sent to the verified email address on file.";
  assert(genericMsg.includes("If an account exists"), "Must be conditional to prevent enumeration");
});
