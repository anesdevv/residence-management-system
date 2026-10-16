/**
 * Unit tests for `src/supabase.ts` — password-grant login cache + rpc with
 * the retry policy ported from `mcp/server.py::SupabaseAdminSession`:
 * re-login once on auth errors, retry once on transient 5xx/network errors.
 *
 * `fetch`, the clock and `sleep` are injected — no real network, no real
 * waiting, no secrets.
 */
import { describe, expect, it, vi } from "vitest";

import {
  RELOGIN_AFTER_SECONDS,
  TRANSIENT_RETRY_DELAY_MS,
  createSupabaseAdmin,
  getSupabaseAdmin,
} from "../src/supabase";

interface FakeCall {
  url: string;
  init: RequestInit;
  headers: Record<string, string>;
  body: unknown;
}

type Handler = (call: FakeCall) => Response | Promise<Response>;

/** Build a fetch that answers each call from the next handler in the list. */
function queueFetch(handlers: Handler[]) {
  const calls: FakeCall[] = [];
  const fetchImpl = (async (input: RequestInfo | URL, init?: RequestInit) => {
    const headers = (init?.headers ?? {}) as Record<string, string>;
    const bodyText = typeof init?.body === "string" ? init.body : "";
    const call: FakeCall = {
      url: String(input),
      init: init ?? {},
      headers,
      body: bodyText === "" ? undefined : JSON.parse(bodyText),
    };
    calls.push(call);
    const handler = handlers.shift();
    if (!handler) throw new Error(`unexpected fetch call #${calls.length}: ${call.url}`);
    return handler(call);
  }) as typeof fetch;
  return { fetchImpl, calls };
}

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "content-type": "application/json" },
  });
}

const CONFIG = {
  url: "https://project.supabase.co",
  anonKey: "anon-key",
  email: "admin@example.com",
  password: "not-a-real-password",
};

const LOGIN_URL = "https://project.supabase.co/auth/v1/token?grant_type=password";
const summaryResponse = () => jsonResponse([{ total: 3 }]);

describe("createSupabaseAdmin.rpc", () => {
  it("logs in with the password grant and calls the SQL function as the admin", async () => {
    const { fetchImpl, calls } = queueFetch([
      () => jsonResponse({ access_token: "token-1", token_type: "bearer" }),
      () => summaryResponse(),
    ]);
    const admin = createSupabaseAdmin({ ...CONFIG, fetch: fetchImpl });

    await expect(admin.rpc("mcp_summary", {})).resolves.toEqual([{ total: 3 }]);

    expect(calls).toHaveLength(2);
    expect(calls[0]!.url).toBe(LOGIN_URL);
    expect(calls[0]!.init.method).toBe("POST");
    expect(calls[0]!.headers.apikey).toBe("anon-key");
    expect(calls[0]!.headers.Authorization).toBeUndefined();
    expect(calls[0]!.body).toEqual({ email: CONFIG.email, password: CONFIG.password });

    expect(calls[1]!.url).toBe("https://project.supabase.co/rest/v1/rpc/mcp_summary");
    expect(calls[1]!.init.method).toBe("POST");
    expect(calls[1]!.headers.apikey).toBe("anon-key");
    expect(calls[1]!.headers.Authorization).toBe("Bearer token-1");
    expect(calls[1]!.headers["content-type"]).toBe("application/json");
    expect(calls[1]!.body).toEqual({});
  });

  it("reuses the cached token across calls (single login)", async () => {
    const { fetchImpl, calls } = queueFetch([
      () => jsonResponse({ access_token: "token-1" }),
      () => summaryResponse(),
      () => jsonResponse([{ total: 4 }]),
    ]);
    const admin = createSupabaseAdmin({ ...CONFIG, fetch: fetchImpl });

    await admin.rpc("mcp_summary", {});
    await admin.rpc("mcp_summary", {});

    const loginCalls = calls.filter((call) => call.url === LOGIN_URL);
    expect(loginCalls).toHaveLength(1);
    expect(calls).toHaveLength(3);
  });

  it(`renews the token after ${RELOGIN_AFTER_SECONDS / 60} minutes, not before`, async () => {
    let clock = 0;
    const { fetchImpl, calls } = queueFetch([
      () => jsonResponse({ access_token: "token-1" }),
      () => summaryResponse(),
      // still cached at exactly the renewal boundary
      () => jsonResponse([{ total: 2 }]),
      // renewed after it passes
      () => jsonResponse({ access_token: "token-2" }),
      () => jsonResponse([{ total: 5 }]),
    ]);
    const admin = createSupabaseAdmin({ ...CONFIG, fetch: fetchImpl, now: () => clock });

    await admin.rpc("mcp_summary", {});

    clock = RELOGIN_AFTER_SECONDS * 1000; // exactly 45 min: still fresh
    await admin.rpc("mcp_summary", {});
    expect(calls.filter((call) => call.url === LOGIN_URL)).toHaveLength(1);

    clock = RELOGIN_AFTER_SECONDS * 1000 + 1; // one ms past: re-login
    await admin.rpc("mcp_summary", {});
    expect(calls.filter((call) => call.url === LOGIN_URL)).toHaveLength(2);
    expect(calls.at(-1)!.headers.Authorization).toBe("Bearer token-2");
  });

  it("re-logs in once and retries on a 401 JWT error", async () => {
    const { fetchImpl, calls } = queueFetch([
      () => jsonResponse({ access_token: "token-1" }),
      () => jsonResponse({ message: "JWT expired" }, 401),
      () => jsonResponse({ access_token: "token-2" }),
      () => summaryResponse(),
    ]);
    const admin = createSupabaseAdmin({ ...CONFIG, fetch: fetchImpl });

    await expect(admin.rpc("mcp_summary", {})).resolves.toEqual([{ total: 3 }]);

    expect(calls.map((call) => call.url)).toEqual([
      LOGIN_URL,
      "https://project.supabase.co/rest/v1/rpc/mcp_summary",
      LOGIN_URL,
      "https://project.supabase.co/rest/v1/rpc/mcp_summary",
    ]);
    expect(calls[1]!.headers.Authorization).toBe("Bearer token-1");
    expect(calls[3]!.headers.Authorization).toBe("Bearer token-2");
  });

  it("retries once after 500 ms on a transient 5xx error", async () => {
    const sleep = vi.fn(async () => {});
    const { fetchImpl, calls } = queueFetch([
      () => jsonResponse({ access_token: "token-1" }),
      () => jsonResponse({ message: "upstream connect error" }, 503),
      () => summaryResponse(),
    ]);
    const admin = createSupabaseAdmin({ ...CONFIG, fetch: fetchImpl, sleep });

    await expect(admin.rpc("mcp_summary", {})).resolves.toEqual([{ total: 3 }]);
    expect(sleep).toHaveBeenCalledExactlyOnceWith(TRANSIENT_RETRY_DELAY_MS);
    expect(calls).toHaveLength(3);
  });

  it("retries once after 500 ms on a network failure", async () => {
    const sleep = vi.fn(async () => {});
    const { fetchImpl, calls } = queueFetch([
      () => jsonResponse({ access_token: "token-1" }),
      () => {
        throw new TypeError("fetch failed");
      },
      () => summaryResponse(),
    ]);
    const admin = createSupabaseAdmin({ ...CONFIG, fetch: fetchImpl, sleep });

    await expect(admin.rpc("mcp_summary", {})).resolves.toEqual([{ total: 3 }]);
    expect(sleep).toHaveBeenCalledExactlyOnceWith(TRANSIENT_RETRY_DELAY_MS);
    expect(calls).toHaveLength(3);
  });

  it("does not retry non-auth non-transient errors and surfaces the SQL message", async () => {
    const sleep = vi.fn(async () => {});
    const { fetchImpl, calls } = queueFetch([
      () => jsonResponse({ access_token: "token-1" }),
      () => jsonResponse({ message: "admin only" }, 403),
    ]);
    const admin = createSupabaseAdmin({ ...CONFIG, fetch: fetchImpl, sleep });

    await expect(admin.rpc("mcp_summary", {})).rejects.toThrow("admin only");
    expect(sleep).not.toHaveBeenCalled();
    expect(calls).toHaveLength(2);
  });

  it("surfaces the GoTrue error_description when login fails", async () => {
    const { fetchImpl } = queueFetch([
      () =>
        jsonResponse({ error: "invalid_grant", error_description: "Invalid login credentials" }, 400),
    ]);
    const admin = createSupabaseAdmin({ ...CONFIG, fetch: fetchImpl });

    await expect(admin.rpc("mcp_summary", {})).rejects.toThrow("Invalid login credentials");
  });

  it("fails clearly when the login response has no access_token", async () => {
    const { fetchImpl } = queueFetch([() => jsonResponse({ token_type: "bearer" })]);
    const admin = createSupabaseAdmin({ ...CONFIG, fetch: fetchImpl });

    await expect(admin.rpc("mcp_summary", {})).rejects.toThrow("access_token");
  });

  it("returns null for an empty 200 body", async () => {
    const { fetchImpl } = queueFetch([
      () => jsonResponse({ access_token: "token-1" }),
      () => new Response("", { status: 200 }),
    ]);
    const admin = createSupabaseAdmin({ ...CONFIG, fetch: fetchImpl });

    await expect(admin.rpc("mcp_log_audit", { p_tool: "get_summary", p_args: {} })).resolves.toBe(
      null,
    );
  });

  it("forwards the abort signal to fetch", async () => {
    const controller = new AbortController();
    const { fetchImpl, calls } = queueFetch([
      () => jsonResponse({ access_token: "token-1" }),
      () => summaryResponse(),
    ]);
    const admin = createSupabaseAdmin({ ...CONFIG, fetch: fetchImpl });

    await admin.rpc("mcp_summary", {}, { signal: controller.signal });
    expect(calls[1]!.init.signal).toBe(controller.signal);
  });

  it("does not retry an aborted (timed-out) request", async () => {
    const controller = new AbortController();
    controller.abort();
    const sleep = vi.fn(async () => {});
    const { fetchImpl, calls } = queueFetch([
      () => jsonResponse({ access_token: "token-1" }),
      () => jsonResponse({ message: "timed out" }, 504),
    ]);
    const admin = createSupabaseAdmin({ ...CONFIG, fetch: fetchImpl, sleep });

    await expect(
      admin.rpc("mcp_log_audit", { p_tool: "get_summary", p_args: {} }, { signal: controller.signal }),
    ).rejects.toThrow();
    expect(sleep).not.toHaveBeenCalled();
    expect(calls).toHaveLength(2);
  });

  it("shares one login between concurrent rpc calls (single-flight)", async () => {
    const { fetchImpl, calls } = queueFetch([
      () => jsonResponse({ access_token: "token-1" }),
      () => summaryResponse(),
      () => jsonResponse([{ total: 9 }]),
    ]);
    const admin = createSupabaseAdmin({ ...CONFIG, fetch: fetchImpl });

    const [a, b] = await Promise.all([admin.rpc("mcp_summary", {}), admin.rpc("mcp_summary", {})]);
    expect(a).toEqual([{ total: 3 }]);
    expect(b).toEqual([{ total: 9 }]);
    expect(calls.filter((call) => call.url === LOGIN_URL)).toHaveLength(1);
  });
});

describe("getSupabaseAdmin", () => {
  it("returns the same module-scope session for the same project/admin", () => {
    const first = getSupabaseAdmin({ ...CONFIG, fetch: vi.fn() as unknown as typeof fetch });
    const second = getSupabaseAdmin({ ...CONFIG, fetch: vi.fn() as unknown as typeof fetch });
    expect(second).toBe(first);

    const other = getSupabaseAdmin({
      ...CONFIG,
      url: "https://other.supabase.co",
      fetch: vi.fn() as unknown as typeof fetch,
    });
    expect(other).not.toBe(first);
  });
});
