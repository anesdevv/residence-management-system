/**
 * Worker entry (Task 5): rate-limited `/mcp` in front of the OAuth provider.
 *
 * Single-Worker `OAuthProvider` shape from the installed
 * `@cloudflare/workers-oauth-provider` 1.2.3 (README "One Worker: OAuthProvider";
 * docs/authorization-server.md, docs/mcp-discovery.md):
 *  - `apiRoute: "/mcp"` with the Task-3 stateless MCP handler as `apiHandler`;
 *  - `authorizeEndpoint: "/authorize"` (our consent page in `src/oauth.ts`);
 *  - `tokenEndpoint: "/oauth/token"` (provider-owned token + revocation);
 *  - `clientRegistrationEndpoint: "/oauth/register"` (RFC 7591 DCR — required
 *    by `scripts/verify_remote.py`, still useful for non-CIMD clients);
 *  - `clientIdMetadataDocumentEnabled: true` (CIMD; the docs require the
 *    `global_fetch_strictly_public` compatibility flag, set in wrangler.jsonc);
 *  - `resourceMetadata.resource` = `${PUBLIC_URL}/mcp` and
 *    `requiredScopes: ["mcp:read"]` (advertised in the 401 challenge).
 *
 * The provider is built lazily on the first request because `PUBLIC_URL` is a
 * plain var: the deployed origin (Task 7) replaces the dev default without a
 * code change. `PUBLIC_URL` is stable per Worker version, so this is one
 * construction per isolate.
 *
 * The top-level fetch rate-limits every `/mcp` request (pre-auth, key =
 * `CF-Connecting-IP`) per plan D8, then delegates everything to the provider.
 */
import { OAuthProvider } from "@cloudflare/workers-oauth-provider";

import type { RpcCall } from "./audit";
import { createAuditLogger } from "./audit";
import { createMcpHttpHandler, type ToolDeps } from "./mcp";
import { createDefaultHandler } from "./oauth";
import { getSupabaseAdmin } from "./supabase";

/** Dev default; Task 7 points this at the deployed workers.dev origin. */
const DEFAULT_PUBLIC_URL = "http://localhost:8788";

/** The one protected route (plan D1/D5). */
const MCP_ROUTE = "/mcp";

/** Scopes this authorization server can grant (plan D5: admin). */
const SUPPORTED_SCOPES = ["mcp:read", "offline_access"] as const;

function publicBaseUrl(env: Env): string {
  const raw = (env.PUBLIC_URL ?? "").trim();
  return (raw === "" ? DEFAULT_PUBLIC_URL : raw).replace(/\/+$/, "");
}

/** The route `/mcp` and its descendants (same path-boundary rule the provider uses). */
function isMcpPath(pathname: string): boolean {
  return pathname === MCP_ROUTE || pathname.startsWith(`${MCP_ROUTE}/`);
}

/**
 * Tool dependencies for the MCP handler: the Supabase admin session (itself
 * cached per isolate) plus an audit logger that swallows every failure.
 */
function createToolDeps(env: Env): ToolDeps {
  const admin = getSupabaseAdmin({
    url: env.SUPABASE_URL,
    anonKey: env.SUPABASE_ANON_KEY,
    email: env.ADMIN_EMAIL,
    password: env.ADMIN_PASSWORD,
  });
  const rpc: RpcCall = (functionName, params, options) => admin.rpc(functionName, params, options);
  return { rpc, audit: createAuditLogger(rpc) };
}

// ---------------------------------------------------------------------------
// Per-isolate lazy singletons
// ---------------------------------------------------------------------------

let mcpHandler: ReturnType<typeof createMcpHttpHandler> | null = null;

/** The stateless MCP handler, built once per isolate. */
function getMcpHandler(env: Env) {
  if (mcpHandler === null) {
    mcpHandler = createMcpHttpHandler(createToolDeps(env));
  }
  return mcpHandler;
}

let cachedProvider: { resource: string; provider: OAuthProvider<Env> } | null = null;

/** The OAuth provider, built per isolate for the configured PUBLIC_URL. */
function getOAuthProvider(env: Env): OAuthProvider<Env> {
  const resource = `${publicBaseUrl(env)}${MCP_ROUTE}`;
  if (cachedProvider === null || cachedProvider.resource !== resource) {
    cachedProvider = {
      resource,
      provider: new OAuthProvider<Env>({
        apiRoute: MCP_ROUTE,
        apiHandler: {
          fetch(request: Request, requestEnv: Env, ctx: ExecutionContext): Promise<Response> {
            // Authenticated requests reach here with ctx.props / ctx.auth set;
            // the stateless MCP handler receives the same context.
            return getMcpHandler(requestEnv)(request, requestEnv, ctx);
          },
        },
        defaultHandler: createDefaultHandler(),
        authorizeEndpoint: "/authorize",
        tokenEndpoint: "/oauth/token",
        clientRegistrationEndpoint: "/oauth/register",
        clientIdMetadataDocumentEnabled: true,
        scopesSupported: [...SUPPORTED_SCOPES],
        resourceMetadata: {
          resource,
          resource_name: "RÉSIVO Admin",
        },
        requiredScopes: ["mcp:read"],
      }),
    };
  }
  return cachedProvider.provider;
}

// ---------------------------------------------------------------------------
// Entry point
// ---------------------------------------------------------------------------

export default {
  async fetch(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
    // D8: 60 req/min per client IP on /mcp, before auth. The binding is
    // optional so the code path survives if the free plan rejects it (D4).
    if (isMcpPath(new URL(request.url).pathname)) {
      const limiter = env.RATE_LIMITER;
      if (limiter) {
        const key = request.headers.get("CF-Connecting-IP") ?? "unknown";
        const { success } = await limiter.limit({ key });
        if (!success) {
          return Response.json({ error: "rate limit exceeded" }, { status: 429 });
        }
      }
    }
    return getOAuthProvider(env).fetch(request, env, ctx);
  },
} satisfies ExportedHandler<Env>;
