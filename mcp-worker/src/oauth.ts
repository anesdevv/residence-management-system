/**
 * Public (non-API) routes for the Worker: `/health` and the OAuth consent page.
 *
 * Wiring follows the installed `@cloudflare/workers-oauth-provider` 1.2.3 docs
 * (`docs/consent-page.md`, `docs/authorization-server.md`): `parseAuthRequest()`
 * validates client, redirect URI, response type, resource and PKCE from the
 * URL, our page asks for the admin token, and a POST calls
 * `completeAuthorization()` and redirects to its `redirectTo`.
 *
 * Deliberate deviation from the docs' `beginConsent()/approveConsent()` flow:
 * those helpers bind the form to the browser with an `__Host-` cookie that is
 * always `Secure`, and non-browser clients on plain `http://localhost`
 * (wrangler dev, the fixed Python verify script) never send it back — Python's
 * `http.cookiejar` has no localhost exception for `Secure` cookies. Plan D6
 * only requires the pasted `access_token` + `completeAuthorization`, so both
 * GET and POST re-validate the URL with `parseAuthRequest()`; the token gate is
 * the authorization factor (CSRF cannot forge it). The token is never echoed,
 * logged, or stored anywhere.
 */
import {
  AuthorizationError,
  CimdFetchError,
  authorizationErrorRedirect,
  type AuthRequest,
  type ConsentDescription,
  type OAuthHelpers,
} from "@cloudflare/workers-oauth-provider";

import { tokenEquals } from "./formatting";

declare global {
  interface Env {
    /**
     * OAuth helpers injected by `OAuthProvider` before the default handler runs
     * (installed 1.2.3: consent-page.md, "Showing it, approving, declining").
     */
    OAUTH_PROVIDER: OAuthHelpers;
  }
}

/** Non-secret grant identity for anyone who passed the consent token gate. */
export const CONSENT_USER_ID = "residence-admin";

// ---------------------------------------------------------------------------
// HTML rendering (small, self-contained, no CDNs, dark-friendly)
// ---------------------------------------------------------------------------

/** Escape every string that can come from the OAuth client. */
function escapeHtml(value: string): string {
  return value.replace(/[&<>"']/g, (char) => `&#${char.charCodeAt(0)};`);
}

const PAGE_CSS = `
:root { color-scheme: light dark; }
body {
  margin: 0; min-height: 100vh; display: flex; align-items: center; justify-content: center;
  font-family: ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif;
  background: #0b1220; color: #e6edf7; padding: 24px; box-sizing: border-box;
}
.card {
  width: min(100%, 440px); background: #111a2e; border: 1px solid #23304d;
  border-radius: 14px; padding: 24px; box-shadow: 0 10px 30px rgba(0, 0, 0, 0.35);
}
h1 { font-size: 1.15rem; margin: 0 0 2px; }
.sub { color: #8fa3c8; font-size: 0.85rem; margin: 0 0 16px; }
p { line-height: 1.45; margin: 10px 0 0; }
.meta { color: #9fb2d4; font-size: 0.88rem; }
label { display: block; font-size: 0.8rem; color: #9fb2d4; margin: 18px 0 6px; }
input {
  width: 100%; box-sizing: border-box; padding: 10px 12px; border-radius: 8px;
  border: 1px solid #2c3c5e; background: #0b1220; color: inherit; font-size: 1rem;
}
.actions { display: flex; gap: 10px; margin-top: 16px; }
button {
  flex: 1; padding: 10px 12px; border-radius: 8px; border: 1px solid transparent;
  font-size: 0.95rem; cursor: pointer;
}
button.approve { background: #2563eb; color: #ffffff; }
button.deny { background: transparent; border-color: #2c3c5e; color: #c3d0e8; }
.scope {
  display: inline-block; margin: 2px 4px 2px 0; padding: 2px 8px; border-radius: 999px;
  background: #1b2a4a; color: #cdd9f1; font-size: 0.78rem;
}
.error {
  padding: 9px 11px; border-radius: 8px; background: #3a1420; border: 1px solid #7f1d3a;
  color: #fecdd3; font-size: 0.85rem;
}
.warn {
  padding: 9px 11px; border-radius: 8px; background: #3a2b0f; border: 1px solid #8a6d1f;
  color: #fde68a; font-size: 0.85rem;
}
@media (prefers-color-scheme: light) {
  body { background: #f1f5fb; color: #0f172a; }
  .card { background: #ffffff; border-color: #dbe4f0; box-shadow: 0 10px 30px rgba(15, 23, 42, 0.08); }
  .sub, label { color: #5b6b88; }
  .meta { color: #475569; }
  input { background: #f8fafc; border-color: #cbd5e1; }
  button.deny { border-color: #cbd5e1; color: #334155; }
  .scope { background: #e8eef9; color: #334155; }
  .warn { background: #fef9c3; border-color: #eab308; color: #854d0e; }
  .error { background: #fee2e2; border-color: #ef4444; color: #991b1b; }
}
`;

function htmlResponse(body: string, status = 200): Response {
  return new Response(body, {
    status,
    headers: {
      "content-type": "text/html; charset=utf-8",
      "cache-control": "no-store",
      "x-content-type-options": "nosniff",
    },
  });
}

function errorPage(message: string, status: number): Response {
  const page = `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>RÉSIVO MCP</title>
<style>${PAGE_CSS}</style>
</head>
<body>
<main class="card">
<h1>RÉSIVO Admin</h1>
<p class="sub">Administrator MCP server for the university residence</p>
<p class="error" role="alert">${escapeHtml(message)}</p>
</main>
</body>
</html>`;
  return htmlResponse(page, status);
}

/**
 * The consent page. The token input is empty on every render — the pasted
 * value is never echoed back, never stored, and never placed in the HTML.
 */
function consentPage(details: ConsentDescription, action: string, error?: string): string {
  const clientName = escapeHtml(details.clientName);
  const publishedBy = details.clientDomain
    ? `<p class="meta">Published by <strong>${escapeHtml(details.clientDomain)}</strong>.</p>`
    : `<p class="meta">This app registered itself; its name is not verified.</p>`;
  const redirectLine = `<p class="meta">Tokens will be sent to <strong>${escapeHtml(details.redirectHost)}</strong>.</p>`;
  const loopbackWarning = details.redirectIsLoopback
    ? `<p class="warn">This sends access to an app on <strong>this computer</strong>. Continue only if you just started signing in from it.</p>`
    : "";
  const scopes =
    details.scope.length > 0
      ? `<p class="meta">Scopes: ${details.scope
          .map((scope) => `<span class="scope">${escapeHtml(scope)}</span>`)
          .join(" ")}</p>`
      : `<p class="meta">No scopes requested.</p>`;
  const errorBanner = error ? `<p class="error" role="alert">${escapeHtml(error)}</p>` : "";
  return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Sign in — RÉSIVO MCP</title>
<style>${PAGE_CSS}</style>
</head>
<body>
<main class="card">
<h1>RÉSIVO Admin</h1>
<p class="sub">Administrator MCP server for the university residence</p>
<p><strong>${clientName}</strong> wants to connect to the residence admin tools.</p>
${publishedBy}
${redirectLine}
${loopbackWarning}
${scopes}
${errorBanner}
<form method="post" action="${escapeHtml(action)}">
<label for="access_token">Access token</label>
<input id="access_token" name="access_token" type="password" autocomplete="off" autofocus required>
<div class="actions">
<button class="approve" type="submit" name="decision" value="approve">Allow</button>
<button class="deny" type="submit" name="decision" value="deny">Deny</button>
</div>
</form>
</main>
</body>
</html>`;
}

// ---------------------------------------------------------------------------
// /authorize handlers
// ---------------------------------------------------------------------------

/**
 * The form posts back to the URL it was rendered from (path + query). Both
 * clients in the wild do this; it is what lets the POST re-validate the exact
 * authorization request with `parseAuthRequest()` without any server state.
 */
function actionFor(request: Request): string {
  const url = new URL(request.url);
  return `${url.pathname}${url.search}`;
}

type ParsedAuthorize =
  | { ok: true; authRequest: AuthRequest; details: ConsentDescription }
  | { ok: false; response: Response };

/**
 * Validate the authorization request from the URL and describe it for the
 * consent page, mapping the library's error taxonomy to responses
 * (installed docs: consent-page.md, "Errors: redirect or render?").
 */
async function parseAuthorizeRequest(request: Request, env: Env): Promise<ParsedAuthorize> {
  try {
    const authRequest = await env.OAUTH_PROVIDER.parseAuthRequest(request);
    const details = await env.OAUTH_PROVIDER.describeConsent(authRequest);
    return { ok: true, authRequest, details };
  } catch (error) {
    if (error instanceof AuthorizationError && error.redirectTo) {
      // Client + exact redirect URI were validated: a redirect is safe.
      return { ok: false, response: Response.redirect(error.redirectTo, 302) };
    }
    if (error instanceof AuthorizationError) {
      return { ok: false, response: errorPage(`Request error: ${error.description}`, 400) };
    }
    if (error instanceof CimdFetchError) {
      return { ok: false, response: errorPage("This app could not be verified.", 400) };
    }
    throw error;
  }
}

async function handleAuthorizeGet(request: Request, env: Env): Promise<Response> {
  const parsed = await parseAuthorizeRequest(request, env);
  if (!parsed.ok) return parsed.response;
  return htmlResponse(consentPage(parsed.details, actionFor(request)));
}

async function handleAuthorizePost(request: Request, env: Env): Promise<Response> {
  const form = await request.formData();
  const parsed = await parseAuthorizeRequest(request, env);

  // "Deny" needs no token: always safe to send the client access_denied.
  if (form.get("decision") === "deny") {
    if (!parsed.ok) return parsed.response;
    return Response.redirect(
      authorizationErrorRedirect(parsed.authRequest, "access_denied", "The administrator declined this request."),
      302,
    );
  }

  if (!parsed.ok) return parsed.response;

  const provided = form.get("access_token");
  const expected = env.MCP_AUTH_TOKEN;
  const authorized =
    typeof provided === "string" &&
    typeof expected === "string" &&
    expected !== "" &&
    tokenEquals(provided, expected);

  if (!authorized) {
    // Fail closed: wrong token or MCP_AUTH_TOKEN not configured. Re-render
    // with a short error; the submitted value is never echoed back.
    return htmlResponse(
      consentPage(parsed.details, actionFor(request), "Wrong access token. Check the token and try again."),
      401,
    );
  }

  try {
    const { redirectTo } = await env.OAUTH_PROVIDER.completeAuthorization({
      request: parsed.authRequest,
      userId: CONSENT_USER_ID,
      metadata: {},
      scope: parsed.authRequest.scope,
      props: { role: "admin" },
    });
    return Response.redirect(redirectTo, 302);
  } catch (error) {
    if (error instanceof AuthorizationError) {
      return errorPage(`Authorization failed: ${error.description}`, 400);
    }
    throw error;
  }
}

// ---------------------------------------------------------------------------
// Default handler (/health, /authorize, everything else)
// ---------------------------------------------------------------------------

export function createDefaultHandler(): ExportedHandler<Env> {
  return {
    async fetch(request: Request, env: Env): Promise<Response> {
      const { pathname } = new URL(request.url);

      if (pathname === "/health") {
        // Public liveness probe: never gated, never rate limited.
        if (request.method !== "GET" && request.method !== "HEAD") {
          return Response.json({ error: "method not allowed" }, { status: 405, headers: { Allow: "GET, HEAD" } });
        }
        return Response.json({ status: "ok" }, { headers: { "cache-control": "no-store" } });
      }

      if (pathname === "/authorize") {
        return request.method === "POST" ? handleAuthorizePost(request, env) : handleAuthorizeGet(request, env);
      }

      return Response.json({ error: "not found" }, { status: 404 });
    },
  };
}
