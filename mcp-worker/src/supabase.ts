/**
 * Supabase admin session for the MCP worker.
 *
 * Ports `mcp/server.py::SupabaseAdminSession` to REST:
 *  - password grant login: `POST {url}/auth/v1/token?grant_type=password`
 *    (apikey = anon key), access token cached in module scope;
 *  - `rpc(fn, params)`: `POST {url}/rest/v1/rpc/{fn}` with apikey + Bearer
 *    admin token;
 *  - renew early at 45 minutes; retry once on auth errors (re-login) and
 *    once on transient 5xx/network errors (500 ms delay).
 *
 * Secrets are never logged; the anon key and admin JWT only travel in request
 * headers.
 */

/** Access tokens last 1h; re-login comfortably early (Python parity). */
export const RELOGIN_AFTER_SECONDS = 45 * 60;

/** One retry only, after this pause (Python parity: time.sleep(0.5)). */
export const TRANSIENT_RETRY_DELAY_MS = 500;

export interface SupabaseAdminConfig {
  url: string;
  anonKey: string;
  email: string;
  password: string;
  /** Injectable for tests; defaults to the global fetch. */
  fetch?: typeof fetch;
  /** Injectable clock in milliseconds; defaults to Date.now. */
  now?: () => number;
  /** Injectable delay; defaults to setTimeout. */
  sleep?: (ms: number) => Promise<void>;
}

export interface RpcOptions {
  signal?: AbortSignal;
}

export interface SupabaseAdmin {
  /** Call a SQL function as the admin; resolves with the parsed JSON body. */
  rpc(
    functionName: string,
    params?: Record<string, unknown>,
    options?: RpcOptions,
  ): Promise<unknown>;
}

/** Auth markers, ported verbatim from `_looks_like_auth_error`. */
const AUTH_MARKERS = [
  "jwt expired",
  "jwt is expired",
  "invalid jwt",
  "token has expired",
  "invalid claim",
  "session not found",
  "refresh token",
  "401",
] as const;

/**
 * Transient markers, ported from `_looks_like_transient_error` plus "network"
 * (JS fetch rejects with `TypeError: fetch failed` — there is no httpx
 * ConnectError equivalent to match on).
 */
const TRANSIENT_MARKERS = [
  "json could not be generated",
  "timeout",
  "timed out",
  "connection",
  "temporarily",
  "upstream",
  "bad gateway",
  "service unavailable",
  "502",
  "503",
  "504",
  "network",
] as const;

class SupabaseHttpError extends Error {
  readonly status: number | null;

  constructor(message: string, status: number | null) {
    super(message);
    this.name = "SupabaseHttpError";
    this.status = status;
  }
}

function errorMessageFromBody(body: unknown, status: number, statusText: string): string {
  if (body !== null && typeof body === "object") {
    const record = body as Record<string, unknown>;
    for (const key of ["message", "error_description", "error", "msg"]) {
      const value = record[key];
      if (typeof value === "string" && value !== "") return value;
    }
  }
  if (typeof body === "string" && body.trim() !== "") return body.trim();
  return `${status} ${statusText}`.trim();
}

async function readBody(response: Response): Promise<unknown> {
  const text = await response.text();
  if (text.trim() === "") return null;
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

function classify(error: unknown): "auth" | "transient" | "other" {
  const message = error instanceof Error ? error.message : String(error);
  const lowered = message.toLowerCase();
  const status = error instanceof SupabaseHttpError ? error.status : null;
  if (status === 401 || AUTH_MARKERS.some((marker) => lowered.includes(marker))) {
    return "auth";
  }
  if (
    (status !== null && status >= 500) ||
    TRANSIENT_MARKERS.some((marker) => lowered.includes(marker))
  ) {
    return "transient";
  }
  return "other";
}

function defaultSleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export function createSupabaseAdmin(config: SupabaseAdminConfig): SupabaseAdmin {
  const baseUrl = config.url.replace(/\/+$/, "");
  const doFetch = config.fetch ?? fetch;
  const now = config.now ?? (() => Date.now());
  const sleep = config.sleep ?? defaultSleep;
  const renewAfterMs = RELOGIN_AFTER_SECONDS * 1000;

  let accessToken: string | null = null;
  let signedInAtMs = 0;
  let loginInFlight: Promise<void> | null = null;

  function tokenIsFresh(): boolean {
    return accessToken !== null && now() - signedInAtMs <= renewAfterMs;
  }

  async function login(): Promise<void> {
    let response: Response;
    try {
      response = await doFetch(`${baseUrl}/auth/v1/token?grant_type=password`, {
        method: "POST",
        headers: { apikey: config.anonKey, "content-type": "application/json" },
        body: JSON.stringify({ email: config.email, password: config.password }),
      });
    } catch (error) {
      throw new SupabaseHttpError(
        `network error: ${error instanceof Error ? error.message : String(error)}`,
        null,
      );
    }
    const body = await readBody(response);
    if (!response.ok) {
      throw new SupabaseHttpError(errorMessageFromBody(body, response.status, response.statusText), response.status);
    }
    const token = body !== null && typeof body === "object"
      ? (body as Record<string, unknown>).access_token
      : null;
    if (typeof token !== "string" || token === "") {
      throw new SupabaseHttpError("login response did not include an access_token", response.status);
    }
    accessToken = token;
    signedInAtMs = now();
  }

  /** Ensure a token exists; `force` re-logs in (auth-error retry path). */
  async function ensureToken(force: boolean): Promise<void> {
    if (!force && tokenIsFresh()) return;
    if (loginInFlight === null) {
      loginInFlight = login().finally(() => {
        loginInFlight = null;
      });
    }
    await loginInFlight;
  }

  async function rpcOnce(
    functionName: string,
    params: Record<string, unknown>,
    options: RpcOptions,
  ): Promise<unknown> {
    let response: Response;
    try {
      response = await doFetch(`${baseUrl}/rest/v1/rpc/${functionName}`, {
        method: "POST",
        headers: {
          apikey: config.anonKey,
          Authorization: `Bearer ${accessToken}`,
          "content-type": "application/json",
        },
        body: JSON.stringify(params),
        signal: options.signal,
      });
    } catch (error) {
      throw new SupabaseHttpError(
        `network error: ${error instanceof Error ? error.message : String(error)}`,
        null,
      );
    }
    const body = await readBody(response);
    if (!response.ok) {
      throw new SupabaseHttpError(
        errorMessageFromBody(body, response.status, response.statusText),
        response.status,
      );
    }
    return body;
  }

  async function rpc(
    functionName: string,
    params: Record<string, unknown> = {},
    options: RpcOptions = {},
  ): Promise<unknown> {
    await ensureToken(false);
    try {
      return await rpcOnce(functionName, params, options);
    } catch (error) {
      const kind = classify(error);
      if (kind === "auth") {
        await ensureToken(true);
        return await rpcOnce(functionName, params, options);
      }
      if (kind === "transient") {
        // A request aborted by its caller (e.g. the audit timeout) must not
        // burn the retry: the signal is already dead.
        if (options.signal?.aborted) throw error;
        await sleep(TRANSIENT_RETRY_DELAY_MS);
        return await rpcOnce(functionName, params, options);
      }
      throw error;
    }
  }

  return { rpc };
}

// ---------------------------------------------------------------------------
// Module-scope session cache (one login per isolate, like Python's SESSION)
// ---------------------------------------------------------------------------

let cachedAdmin: SupabaseAdmin | null = null;
let cachedAdminKey = "";

/** Return the isolate-wide admin session for this project/admin account. */
export function getSupabaseAdmin(config: SupabaseAdminConfig): SupabaseAdmin {
  const key = `${config.url}|${config.email}`;
  if (cachedAdmin === null || cachedAdminKey !== key) {
    cachedAdmin = createSupabaseAdmin(config);
    cachedAdminKey = key;
  }
  return cachedAdmin;
}
