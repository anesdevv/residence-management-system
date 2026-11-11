// supabase/functions/tests/edge_functions_test.ts
// Unit tests for Edge Function shared modules, Card ID validation,
// throttling, CORS, and student-login contracts.

import { isCardId } from "../_shared/validation.ts";
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

Deno.test("isCardId recognizes numeric student card IDs and rejects emails", () => {
  assert(isCardId("20230001"), "8-digit card id should pass");
  assert(isCardId("1234"), "4-digit card id should pass");
  assert(!isCardId("123"), "Under 4 digits should fail");
  assert(!isCardId("abc1234"), "Alpha-numeric should fail");
  assert(!isCardId("user@univ-tlemcen.dz"), "Email must not be accepted as a card_id");
});

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

Deno.test("checkRateLimit allows requests up to limit and blocks beyond", () => {
  const testKey = `test_throttle_${Date.now()}`;
  const limit = 3;
  const windowMs = 5000;

  assertEquals(checkRateLimit(testKey, limit, windowMs).allowed, true);
  assertEquals(checkRateLimit(testKey, limit, windowMs).allowed, true);
  assertEquals(checkRateLimit(testKey, limit, windowMs).allowed, true);

  const blocked = checkRateLimit(testKey, limit, windowMs);
  assertEquals(blocked.allowed, false);
  assert(blocked.retryAfterSeconds > 0, "Retry after should be positive");
});
