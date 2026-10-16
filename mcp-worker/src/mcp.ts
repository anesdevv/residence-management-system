/**
 * The 6 read-only admin tools + the stateless MCP handler.
 *
 * Ports `mcp/server.py` verbatim where the plan's parity table (§3) says so:
 * tool names, descriptions and server name/instructions are copied
 * character-for-character from the Python source; every handler mirrors
 * `call_admin_rpc` (audit → validate → rpc → empty-message / compact
 * truncated JSON).
 */
import { McpServer } from "@modelcontextprotocol/server";
import { createMcpHandler } from "agents/mcp/server";
import { z } from "zod";

import type { AuditTrail, RpcCall } from "./audit";
import { friendlyError } from "./errors";
import {
  ROOM_CHANGE_STATUSES,
  TICKET_STATUSES,
  capLimit,
  emptyMessage,
  toCompactJson,
  truncateRecords,
  validateStatus,
} from "./formatting";

/** Copied verbatim from `mcp/server.py` (FastMCP(...) call). */
export const SERVER_NAME = "Residence Tlemcen Admin";
export const SERVER_VERSION = "1.0.0";
export const SERVER_INSTRUCTIONS =
  "Read-only administrator tools for the Residence Tlemcen university " +
  "residence (maintenance tickets, room change requests, pending " +
  "registrations, student lookup, rooms and an overall summary). " +
  "All data comes from the live Supabase project. The tools never " +
  "modify anything.";

export interface ToolDeps {
  /** Admin rpc from `createSupabaseAdmin(...).rpc` / `createSupabaseAdmin`. */
  rpc: RpcCall;
  /**
   * Two-phase audit trail from `createAuditLogger`. Reads open a row via
   * `begin` (best-effort, result ignored); the write flow (Task 5) completes
   * it via `complete`.
   */
  audit: AuditTrail;
}

interface EmptyHint {
  entity: string;
  status?: string | null;
  block?: string | null;
}

function errorText(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

/** Port of `call_admin_rpc`: rpc → empty message / compact truncated JSON. */
async function renderRpcResult(
  deps: ToolDeps,
  functionName: string,
  params: Record<string, unknown>,
  empty?: EmptyHint,
): Promise<string> {
  let data: unknown;
  try {
    data = await deps.rpc(functionName, params);
  } catch (error) {
    return friendlyError(error);
  }
  if (data === null || data === undefined || (Array.isArray(data) && data.length === 0)) {
    if (empty) return emptyMessage(empty.entity, empty.status ?? null, empty.block ?? null);
    return "No data returned.";
  }
  return toCompactJson(truncateRecords(data));
}

// ---------------------------------------------------------------------------
// Tool logic (audit → validate → rpc → render), mirroring each @mcp.tool()
// ---------------------------------------------------------------------------

async function runListMaintenanceTickets(
  deps: ToolDeps,
  status: string | undefined,
  limit: number | undefined,
): Promise<string> {
  await deps.audit.begin("list_maintenance_tickets", { status: status ?? null, limit: limit ?? 20 });
  let normalized: string | null;
  let capped: number;
  try {
    normalized = validateStatus(status, TICKET_STATUSES, "status");
    capped = capLimit(limit, 20);
  } catch (error) {
    return `Invalid request: ${errorText(error)}`;
  }
  return renderRpcResult(
    deps,
    "mcp_list_tickets",
    { p_status: normalized, p_limit: capped },
    { entity: "tickets", status: normalized },
  );
}

async function runListRoomChangeRequests(
  deps: ToolDeps,
  status: string | undefined,
  limit: number | undefined,
): Promise<string> {
  await deps.audit.begin("list_room_change_requests", { status: status ?? null, limit: limit ?? 20 });
  let normalized: string | null;
  let capped: number;
  try {
    normalized = validateStatus(status, ROOM_CHANGE_STATUSES, "status");
    capped = capLimit(limit, 20);
  } catch (error) {
    return `Invalid request: ${errorText(error)}`;
  }
  return renderRpcResult(
    deps,
    "mcp_list_room_changes",
    { p_status: normalized, p_limit: capped },
    { entity: "room_changes", status: normalized },
  );
}

async function runListPendingRegistrations(
  deps: ToolDeps,
  limit: number | undefined,
): Promise<string> {
  await deps.audit.begin("list_pending_registrations", { limit: limit ?? 20 });
  let capped: number;
  try {
    capped = capLimit(limit, 20);
  } catch (error) {
    return `Invalid request: ${errorText(error)}`;
  }
  return renderRpcResult(
    deps,
    "mcp_list_pending_registrations",
    { p_limit: capped },
    { entity: "registrations" },
  );
}

async function runSearchStudents(
  deps: ToolDeps,
  query: string,
  limit: number | undefined,
): Promise<string> {
  await deps.audit.begin("search_students", { query, limit: limit ?? 10 });
  if (!query || query.trim() === "") {
    return "Invalid request: query is required (a name, card ID or room label such as 'B-101').";
  }
  let capped: number;
  try {
    capped = capLimit(limit, 10);
  } catch (error) {
    return `Invalid request: ${errorText(error)}`;
  }
  return renderRpcResult(
    deps,
    "mcp_search_students",
    { p_query: query.trim(), p_limit: capped },
    { entity: "students" },
  );
}

async function runListRooms(
  deps: ToolDeps,
  block: string | undefined,
  onlyAvailable: boolean | undefined,
): Promise<string> {
  await deps.audit.begin("list_rooms", {
    block: block ?? null,
    only_available: onlyAvailable ?? false,
  });
  const blockFilter = block ? String(block).trim() : null;
  return renderRpcResult(
    deps,
    "mcp_list_rooms",
    { p_block: blockFilter, p_only_available: Boolean(onlyAvailable) },
    { entity: "rooms", block: blockFilter },
  );
}

async function runGetSummary(deps: ToolDeps): Promise<string> {
  await deps.audit.begin("get_summary", {});
  return renderRpcResult(deps, "mcp_summary", {});
}

// ---------------------------------------------------------------------------
// MCP registration
// ---------------------------------------------------------------------------

/**
 * Register the 6 tools on the given server. Kept separate from
 * `buildMcpServer` so tests can capture the registration calls.
 */
export function registerAdminTools(server: McpServer, deps: ToolDeps): void {
  const result = (text: string) => ({ content: [{ type: "text" as const, text }] });

  server.registerTool(
    "list_maintenance_tickets",
    {
      description:
        "List maintenance tickets with student and room details. Use for questions about open, pending, in-progress or resolved maintenance problems. Status can be pending, in_progress or resolved (omit for all).",
      inputSchema: z.object({
        status: z
          .string()
          .optional()
          .describe("Filter by status: pending, in_progress or resolved (omit for all)."),
        limit: z
          .number()
          .int()
          .optional()
          .describe("Maximum number of tickets to return (default 20, max 100)."),
      }),
    },
    async ({ status, limit }) => result(await runListMaintenanceTickets(deps, status, limit)),
  );

  server.registerTool(
    "list_room_change_requests",
    {
      description:
        "List room change requests with student, current room and preferred room. Status can be pending, approved or rejected (omit for all).",
      inputSchema: z.object({
        status: z
          .string()
          .optional()
          .describe("Filter by status: pending, approved or rejected (omit for all)."),
        limit: z
          .number()
          .int()
          .optional()
          .describe("Maximum number of requests to return (default 20, max 100)."),
      }),
    },
    async ({ status, limit }) => result(await runListRoomChangeRequests(deps, status, limit)),
  );

  server.registerTool(
    "list_pending_registrations",
    {
      description:
        "List students waiting for account approval, with their submitted data and whether they match the official residents list.",
      inputSchema: z.object({
        limit: z
          .number()
          .int()
          .optional()
          .describe("Maximum number of registrations to return (default 20, max 100)."),
      }),
    },
    async ({ limit }) => result(await runListPendingRegistrations(deps, limit)),
  );

  server.registerTool(
    "search_students",
    {
      description:
        "Find a student by name or card ID and return their details, room and status. Also accepts a room label like 'B-101' to see which student lives there.",
      inputSchema: z.object({
        query: z
          .string()
          .describe("A name, card ID or room label such as 'B-101' (required)."),
        limit: z
          .number()
          .int()
          .optional()
          .describe("Maximum number of students to return (default 10, max 100)."),
      }),
    },
    async ({ query, limit }) => result(await runSearchStudents(deps, query, limit)),
  );

  server.registerTool(
    "list_rooms",
    {
      description:
        "List rooms with capacity, occupancy and free places. Use only_available to find rooms with space.",
      inputSchema: z.object({
        block: z
          .string()
          .optional()
          .describe("Only return rooms in this block (e.g. 'B'); omit for all blocks."),
        only_available: z
          .boolean()
          .optional()
          .describe("Only return rooms that still have free places (default false)."),
      }),
    },
    async ({ block, only_available }) => result(await runListRooms(deps, block, only_available)),
  );

  server.registerTool(
    "get_summary",
    {
      description:
        "Overview: registrations, tickets, room changes and occupancy, in total and per block.",
      inputSchema: z.object({}),
    },
    async () => result(await runGetSummary(deps)),
  );
}

/** Build a fresh McpServer with the 6 admin tools (factory for the handler). */
export function buildMcpServer(deps: ToolDeps): McpServer {
  const server = new McpServer(
    { name: SERVER_NAME, version: SERVER_VERSION },
    { instructions: SERVER_INSTRUCTIONS },
  );
  registerAdminTools(server, deps);
  return server;
}

/**
 * The stateless MCP HTTP handler for `/mcp` (installed-docs shape:
 * `createMcpHandler(factory, { route })`, callable as `(request, env, ctx)`).
 * Create it once at module scope and reuse it.
 */
export function createMcpHttpHandler(deps: ToolDeps) {
  return createMcpHandler(() => buildMcpServer(deps), { route: "/mcp" });
}
