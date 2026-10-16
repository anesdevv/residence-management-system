/**
 * The 14 admin tools (6 reads ported from `mcp/server.py` + 8 writes) and the
 * stateless MCP handler.
 *
 * Read tool names, descriptions and the server name are copied
 * character-for-character from the Python source; every read handler mirrors
 * `call_admin_rpc` (audit → validate → rpc → empty-message / compact
 * truncated JSON). The write tools are worker-only: `runWrite` reads the
 * writes off-switch, opens a required audit attempt row (`begin`), executes
 * the rpc, then fills the outcome (`complete`) — "no audit row, no write".
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

/** The 14-tool instructions (deliberately diverges from the read-only Python text). */
export const SERVER_INSTRUCTIONS =
  "Administrator tools for the Residence Tlemcen university residence. " +
  "You can read data freely; when the administrator has enabled changes " +
  "you can also approve or reject registrations and room-change requests, " +
  "manage rooms, and update maintenance tickets. Before any change, show " +
  "the user exactly what will change and get their explicit confirmation. " +
  "All data comes from the live Supabase project; every call is logged.";

/** Returned when the desktop off-switch (`mcp_settings.writes_enabled`) is off. */
export const WRITING_DISABLED_MESSAGE =
  "Writing is currently disabled. Turn it on in the desktop app: Settings → Allow ChatGPT to change data.";

/** Returned when the audit attempt row could not be recorded (fail closed). */
export const AUDIT_REQUIRED_MESSAGE =
  "Could not record this action in the audit log, so nothing was changed. Try again.";

/** Returned when the writes gate could not be read (fail closed). */
const GATE_READ_ERROR_MESSAGE =
  "Writing could not be verified right now, so nothing was changed. Try again.";

export interface ToolDeps {
  /** Admin rpc from `createSupabaseAdmin(...).rpc` / `createSupabaseAdmin`. */
  rpc: RpcCall;
  /**
   * Two-phase audit trail from `createAuditLogger`. Reads open a row via
   * `begin` (best-effort, result ignored); writes go through `runWrite`
   * (gate → `begin` → execute → `complete`).
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
// Write flow: gate → audit attempt → execute → audit outcome
// ---------------------------------------------------------------------------

/** Case-insensitive uuid format for every id argument (plan Ruling 3). */
const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** `Invalid request:` text for a non-uuid id argument, or null when it is a uuid. */
function uuidError(value: string, arg: string, source: string): string | null {
  if (UUID_PATTERN.test(value)) return null;
  return `Invalid request: ${arg} must be a uuid copied from ${source}.`;
}

/** Normalize a free-form gender to `male`/`female`, or null when invalid. */
function normalizeGender(value: string): string | null {
  const normalized = value.trim().toLowerCase();
  return normalized === "male" || normalized === "female" ? normalized : null;
}

/**
 * Read the writes off-switch: `mcp_get_settings` → `writes_enabled`.
 * A missing settings row counts as enabled (the seeded default); any read
 * error (or an unparseable body) returns `null` so the caller refuses the
 * write (fail closed).
 */
async function getWritesEnabled(deps: ToolDeps): Promise<boolean | null> {
  let body: unknown;
  try {
    body = await deps.rpc("mcp_get_settings", {});
  } catch {
    return null;
  }
  if (body === null || body === undefined) return true;
  if (typeof body !== "object" || Array.isArray(body)) return null;
  const value = (body as Record<string, unknown>).writes_enabled;
  if (value === undefined) return true;
  return value === true;
}

/** Read a field off an unknown row returned by a write rpc. */
function rowField(row: unknown, key: string): unknown {
  return row !== null && typeof row === "object"
    ? (row as Record<string, unknown>)[key]
    : undefined;
}

/** `block-number` label of a room row, `?-?` when the fields are absent. */
function roomLabel(row: unknown): string {
  return `${String(rowField(row, "block") ?? "?")}-${String(rowField(row, "number") ?? "?")}`;
}

/**
 * Shared write flow (plan Task 5): read the gate, open an audit attempt row
 * (required — "no audit row, no write"), run the rpc, then fill the audit
 * outcome (`ok` + a short detail) and render the changed row.
 */
async function runWrite(
  deps: ToolDeps,
  tool: string,
  args: Record<string, unknown>,
  execute: () => Promise<unknown>,
  describe: (row: unknown) => string,
): Promise<string> {
  const enabled = await getWritesEnabled(deps);
  if (enabled === null) {
    // Gate unreadable: refuse, fail closed; the attempt is logged best-effort.
    const id = await deps.audit.begin(tool, args);
    await deps.audit.complete(id, false, GATE_READ_ERROR_MESSAGE);
    return GATE_READ_ERROR_MESSAGE;
  }
  if (!enabled) {
    // Off-switch off: refuse; the attempt is logged best-effort.
    const id = await deps.audit.begin(tool, args);
    await deps.audit.complete(id, false, WRITING_DISABLED_MESSAGE);
    return WRITING_DISABLED_MESSAGE;
  }
  const id = await deps.audit.begin(tool, args);
  if (id === null) return AUDIT_REQUIRED_MESSAGE;
  let row: unknown;
  try {
    row = await execute();
  } catch (error) {
    const text = friendlyError(error);
    await deps.audit.complete(id, false, text);
    return text;
  }
  await deps.audit.complete(id, true, describe(row));
  if (row === null || row === undefined || (Array.isArray(row) && row.length === 0)) {
    return "No data returned.";
  }
  return toCompactJson(truncateRecords(row));
}

// ---------------------------------------------------------------------------
// Write handlers (validate values in-handler, then the shared write flow)
// ---------------------------------------------------------------------------

async function runApproveRegistration(
  deps: ToolDeps,
  studentId: string,
  roomId: string,
): Promise<string> {
  const invalidStudent = uuidError(studentId, "student_id", "list_pending_registrations");
  if (invalidStudent) return invalidStudent;
  const invalidRoom = uuidError(roomId, "room_id", "list_rooms");
  if (invalidRoom) return invalidRoom;
  return runWrite(
    deps,
    "approve_registration",
    { student_id: studentId, room_id: roomId },
    () => deps.rpc("approve_student", { p_student: studentId, p_room: roomId }),
    (row) => `Approved registration for card ${rowField(row, "card_id") ?? "?"}.`,
  );
}

async function runRejectRegistration(
  deps: ToolDeps,
  studentId: string,
  reason: string,
): Promise<string> {
  const invalidStudent = uuidError(studentId, "student_id", "list_pending_registrations");
  if (invalidStudent) return invalidStudent;
  if (reason.trim() === "") {
    return "Invalid request: a rejection reason is required (so the student knows why).";
  }
  return runWrite(
    deps,
    "reject_registration",
    { student_id: studentId, reason },
    () => deps.rpc("reject_student", { p_student: studentId, p_reason: reason }),
    (row) => `Rejected registration for card ${rowField(row, "card_id") ?? "?"}.`,
  );
}

async function runApproveRoomChange(
  deps: ToolDeps,
  requestId: string,
  roomId: string,
): Promise<string> {
  const invalidRequest = uuidError(requestId, "request_id", "list_room_change_requests");
  if (invalidRequest) return invalidRequest;
  const invalidRoom = uuidError(roomId, "room_id", "list_rooms");
  if (invalidRoom) return invalidRoom;
  return runWrite(
    deps,
    "approve_room_change",
    { request_id: requestId, room_id: roomId },
    () => deps.rpc("approve_room_change", { p_request: requestId, p_room: roomId }),
    (row) => `Approved room change request ${rowField(row, "id") ?? "?"}.`,
  );
}

async function runRejectRoomChange(
  deps: ToolDeps,
  requestId: string,
  reason: string,
): Promise<string> {
  const invalidRequest = uuidError(requestId, "request_id", "list_room_change_requests");
  if (invalidRequest) return invalidRequest;
  if (reason.trim() === "") {
    return "Invalid request: a rejection reason is required (so the student knows why).";
  }
  return runWrite(
    deps,
    "reject_room_change",
    { request_id: requestId, reason },
    () => deps.rpc("reject_room_change", { p_request: requestId, p_reason: reason }),
    (row) => `Rejected room change request ${rowField(row, "id") ?? "?"}.`,
  );
}

async function runCreateRoom(
  deps: ToolDeps,
  block: string,
  floor: number,
  number: string,
  capacity: number,
  gender: string,
): Promise<string> {
  if (floor < 0 || floor > 15) {
    return "Invalid request: floor must be between 0 and 15.";
  }
  if (capacity < 1 || capacity > 8) {
    return "Invalid request: capacity must be between 1 and 8.";
  }
  const normalizedGender = normalizeGender(gender);
  if (normalizedGender === null) {
    return "Invalid request: gender must be male or female.";
  }
  return runWrite(
    deps,
    "create_room",
    { block, floor, number, capacity, gender: normalizedGender },
    () =>
      deps.rpc("mcp_create_room", {
        p_block: block,
        p_floor: floor,
        p_number: number,
        p_capacity: capacity,
        p_gender: normalizedGender,
      }),
    (row) => `Created room ${roomLabel(row)}.`,
  );
}

async function runUpdateRoom(
  deps: ToolDeps,
  roomId: string,
  block: string | undefined,
  floor: number | undefined,
  number: string | undefined,
  capacity: number | undefined,
  gender: string | undefined,
): Promise<string> {
  const invalidRoom = uuidError(roomId, "room_id", "list_rooms");
  if (invalidRoom) return invalidRoom;
  if (floor !== undefined && (floor < 0 || floor > 15)) {
    return "Invalid request: floor must be between 0 and 15.";
  }
  if (capacity !== undefined && (capacity < 1 || capacity > 8)) {
    return "Invalid request: capacity must be between 1 and 8.";
  }
  let normalizedGender: string | null = null;
  if (gender !== undefined) {
    normalizedGender = normalizeGender(gender);
    if (normalizedGender === null) {
      return "Invalid request: gender must be male or female.";
    }
  }
  return runWrite(
    deps,
    "update_room",
    {
      room_id: roomId,
      block: block ?? null,
      floor: floor ?? null,
      number: number ?? null,
      capacity: capacity ?? null,
      gender: normalizedGender,
    },
    () =>
      deps.rpc("mcp_update_room", {
        p_room: roomId,
        p_block: block ?? null,
        p_floor: floor ?? null,
        p_number: number ?? null,
        p_capacity: capacity ?? null,
        p_gender: normalizedGender,
      }),
    (row) => `Updated room ${roomLabel(row)}.`,
  );
}

async function runDeleteRoom(deps: ToolDeps, roomId: string): Promise<string> {
  const invalidRoom = uuidError(roomId, "room_id", "list_rooms");
  if (invalidRoom) return invalidRoom;
  return runWrite(
    deps,
    "delete_room",
    { room_id: roomId },
    () => deps.rpc("mcp_delete_room", { p_room: roomId }),
    (row) => `Deleted room ${roomLabel(rowField(row, "room"))}.`,
  );
}

async function runUpdateTicket(
  deps: ToolDeps,
  ticketId: string,
  status: string,
  note: string | undefined,
): Promise<string> {
  const invalidTicket = uuidError(ticketId, "ticket_id", "list_maintenance_tickets");
  if (invalidTicket) return invalidTicket;
  const normalizedStatus = status
    .trim()
    .toLowerCase()
    .replace(/-/g, "_")
    .replace(/ /g, "_");
  if (normalizedStatus !== "in_progress" && normalizedStatus !== "resolved") {
    return "Invalid request: status must be in_progress or resolved.";
  }
  return runWrite(
    deps,
    "update_ticket",
    { ticket_id: ticketId, status: normalizedStatus, note: note ?? null },
    () =>
      deps.rpc("mcp_update_ticket", {
        p_ticket: ticketId,
        p_status: normalizedStatus,
        p_note: note ?? null,
      }),
    (row) => `Ticket ${rowField(row, "id") ?? "?"} marked ${rowField(row, "status") ?? "?"}.`,
  );
}

// ---------------------------------------------------------------------------
// MCP registration
// ---------------------------------------------------------------------------

/**
 * Register the 14 tools on the given server. Kept separate from
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
      annotations: { readOnlyHint: true, openWorldHint: true },
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
      annotations: { readOnlyHint: true, openWorldHint: true },
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
      annotations: { readOnlyHint: true, openWorldHint: true },
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
      annotations: { readOnlyHint: true, openWorldHint: true },
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
      annotations: { readOnlyHint: true, openWorldHint: true },
    },
    async ({ block, only_available }) => result(await runListRooms(deps, block, only_available)),
  );

  server.registerTool(
    "get_summary",
    {
      description:
        "Overview: registrations, tickets, room changes and occupancy, in total and per block.",
      inputSchema: z.object({}),
      annotations: { readOnlyHint: true, openWorldHint: true },
    },
    async () => result(await runGetSummary(deps)),
  );

  // -------------------------------------------------------------------------
  // Write tools (readOnlyHint false; destructiveHint only on the 3 destructive)
  // -------------------------------------------------------------------------

  server.registerTool(
    "approve_registration",
    {
      description:
        "Approve a pending registration and assign the student to a room. This changes data: show the user exactly what will change and get their explicit confirmation before calling. Get student_id from list_pending_registrations and room_id from list_rooms (gender must match, room needs a free place).",
      inputSchema: z.object({
        student_id: z
          .string()
          .describe("The student's uuid from list_pending_registrations (required)."),
        room_id: z.string().describe("The room's uuid from list_rooms (required)."),
      }),
      annotations: { readOnlyHint: false, openWorldHint: true },
    },
    async ({ student_id, room_id }) =>
      result(await runApproveRegistration(deps, student_id, room_id)),
  );

  server.registerTool(
    "reject_registration",
    {
      description:
        "Reject a pending registration with a reason (the student sees it). This changes data: show the user exactly what will change and get their explicit confirmation before calling. A reason is required. Get student_id from list_pending_registrations.",
      inputSchema: z.object({
        student_id: z
          .string()
          .describe("The student's uuid from list_pending_registrations (required)."),
        reason: z
          .string()
          .describe("Why the registration is rejected — the student sees this (required, non-blank)."),
      }),
      annotations: { readOnlyHint: false, openWorldHint: true, destructiveHint: true },
    },
    async ({ student_id, reason }) => result(await runRejectRegistration(deps, student_id, reason)),
  );

  server.registerTool(
    "approve_room_change",
    {
      description:
        "Approve a pending room change request; moves the student to the given room. This changes data: show the user exactly what will change and get their explicit confirmation before calling. Get request_id from list_room_change_requests and room_id from list_rooms (gender must match, room needs a free place).",
      inputSchema: z.object({
        request_id: z
          .string()
          .describe("The request's uuid from list_room_change_requests (required)."),
        room_id: z.string().describe("The room's uuid from list_rooms (required)."),
      }),
      annotations: { readOnlyHint: false, openWorldHint: true },
    },
    async ({ request_id, room_id }) =>
      result(await runApproveRoomChange(deps, request_id, room_id)),
  );

  server.registerTool(
    "reject_room_change",
    {
      description:
        "Reject a pending room change request with a reason (the student sees it). This changes data: show the user exactly what will change and get their explicit confirmation before calling. A reason is required. Get request_id from list_room_change_requests.",
      inputSchema: z.object({
        request_id: z
          .string()
          .describe("The request's uuid from list_room_change_requests (required)."),
        reason: z
          .string()
          .describe("Why the request is rejected — the student sees this (required, non-blank)."),
      }),
      annotations: { readOnlyHint: false, openWorldHint: true, destructiveHint: true },
    },
    async ({ request_id, reason }) => result(await runRejectRoomChange(deps, request_id, reason)),
  );

  server.registerTool(
    "create_room",
    {
      description:
        "Create a new room. This changes data: show the user exactly what will change and get their explicit confirmation before calling. Block is uppercased; floor 0–15; capacity 1–8; gender male or female; block+number must not already exist.",
      inputSchema: z.object({
        block: z.string().describe("Block name, e.g. 'B' (required; stored uppercased)."),
        floor: z.number().int().describe("Floor 0–15 (required)."),
        number: z.string().describe("Room number within the block (required)."),
        capacity: z.number().int().describe("Number of places, 1–8 (required)."),
        gender: z.string().describe("Room gender: male or female (required)."),
      }),
      annotations: { readOnlyHint: false, openWorldHint: true },
    },
    async ({ block, floor, number, capacity, gender }) =>
      result(await runCreateRoom(deps, block, floor, number, capacity, gender)),
  );

  server.registerTool(
    "update_room",
    {
      description:
        "Update a room; omitted fields stay unchanged. This changes data: show the user exactly what will change and get their explicit confirmation before calling. Floor 0–15; capacity 1–8; gender male or female; capacity cannot go below current occupancy; gender cannot change while residents are assigned. Get room_id from list_rooms.",
      inputSchema: z.object({
        room_id: z.string().describe("The room's uuid from list_rooms (required)."),
        block: z.string().optional().describe("New block name (omit to keep the current one)."),
        floor: z.number().int().optional().describe("New floor 0–15 (omit to keep the current one)."),
        number: z.string().optional().describe("New room number (omit to keep the current one)."),
        capacity: z
          .number()
          .int()
          .optional()
          .describe("New capacity 1–8 (omit to keep the current one)."),
        gender: z
          .string()
          .optional()
          .describe("New gender male or female (omit to keep the current one)."),
      }),
      annotations: { readOnlyHint: false, openWorldHint: true },
    },
    async ({ room_id, block, floor, number, capacity, gender }) =>
      result(await runUpdateRoom(deps, room_id, block, floor, number, capacity, gender)),
  );

  server.registerTool(
    "delete_room",
    {
      description:
        "Delete a room permanently. This changes data: show the user exactly what will change and get their explicit confirmation before calling. Refused while active residents are assigned. Get room_id from list_rooms.",
      inputSchema: z.object({
        room_id: z.string().describe("The room's uuid from list_rooms (required)."),
      }),
      annotations: { readOnlyHint: false, openWorldHint: true, destructiveHint: true },
    },
    async ({ room_id }) => result(await runDeleteRoom(deps, room_id)),
  );

  server.registerTool(
    "update_ticket",
    {
      description:
        "Update a maintenance ticket: mark it in_progress (technician dispatched) or resolved (closed), with an optional note. This changes data: show the user exactly what will change and get their explicit confirmation before calling. Get ticket_id from list_maintenance_tickets.",
      inputSchema: z.object({
        ticket_id: z
          .string()
          .describe("The ticket's uuid from list_maintenance_tickets (required)."),
        status: z.string().describe("New status: in_progress or resolved (required)."),
        note: z
          .string()
          .optional()
          .describe("Optional note for the ticket (omit or leave blank to keep the existing note)."),
      }),
      annotations: { readOnlyHint: false, openWorldHint: true },
    },
    async ({ ticket_id, status, note }) =>
      result(await runUpdateTicket(deps, ticket_id, status, note)),
  );
}

/** Build a fresh McpServer with the 14 admin tools (factory for the handler). */
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
