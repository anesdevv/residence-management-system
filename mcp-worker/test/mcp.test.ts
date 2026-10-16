/**
 * Parity tests for `src/mcp.ts` and `src/audit.ts`.
 *
 * The registration path is exercised for real: `registerAdminTools` is called
 * with a capture object, and the captured tool callbacks are invoked. This
 * proves the wiring (names, verbatim descriptions, schemas, audit → validate
 * → rpc → render order) without needing a transport.
 *
 * Expected strings are copied from `mcp/server.py`.
 */
import { McpServer } from "@modelcontextprotocol/server";
import { describe, expect, it, vi } from "vitest";

import { createAuditLogger } from "../src/audit";
import {
  AUDIT_REQUIRED_MESSAGE,
  SERVER_INSTRUCTIONS,
  SERVER_NAME,
  WRITING_DISABLED_MESSAGE,
  buildMcpServer,
  registerAdminTools,
  type ToolDeps,
} from "../src/mcp";

type HandlerResult = { content: Array<{ type: string; text: string }> };
type Handler = (args: Record<string, unknown>) => Promise<HandlerResult>;

interface ToolAnnotations {
  readOnlyHint?: boolean;
  destructiveHint?: boolean;
  openWorldHint?: boolean;
}

interface Registered {
  name: string;
  description: string;
  inputSchema: unknown;
  annotations: ToolAnnotations | undefined;
  handler: Handler;
}

function captureTools(deps: ToolDeps): Registered[] {
  const registered: Registered[] = [];
  const fake = {
    registerTool(
      name: string,
      config: { description: string; inputSchema: unknown; annotations?: ToolAnnotations },
      handler: Handler,
    ) {
      registered.push({
        name,
        description: config.description,
        inputSchema: config.inputSchema,
        annotations: config.annotations,
        handler,
      });
      return {};
    },
  } as unknown as McpServer;
  registerAdminTools(fake, deps);
  return registered;
}

function makeDeps() {
  const audit = {
    begin: vi.fn(
      async (_tool: string, _args: Record<string, unknown>): Promise<number | null> => 1,
    ),
    complete: vi.fn(
      async (_id: number | null, _ok: boolean, _detail: string): Promise<void> => {},
    ),
  };
  const rpc = vi.fn(
    async (_fn: string, _params?: Record<string, unknown>): Promise<unknown> => [],
  );
  const deps: ToolDeps = { audit, rpc };
  return { deps, audit, rpc };
}

// Descriptions copied verbatim from mcp/server.py (lines ~246-328).
const DESCRIPTIONS = {
  list_maintenance_tickets:
    "List maintenance tickets with student and room details. Use for questions about open, pending, in-progress or resolved maintenance problems. Status can be pending, in_progress or resolved (omit for all).",
  list_room_change_requests:
    "List room change requests with student, current room and preferred room. Status can be pending, approved or rejected (omit for all).",
  list_pending_registrations:
    "List students waiting for account approval, with their submitted data and whether they match the official residents list.",
  search_students:
    "Find a student by name or card ID and return their details, room and status. Also accepts a room label like 'B-101' to see which student lives there.",
  list_rooms:
    "List rooms with capacity, occupancy and free places. Use only_available to find rooms with space.",
  get_summary:
    "Overview: registrations, tickets, room changes and occupancy, in total and per block.",
} as const;

const TOOL_ORDER = Object.keys(DESCRIPTIONS) as Array<keyof typeof DESCRIPTIONS>;

/** The 8 write tools, in registration order (Global Constraints). */
const WRITE_TOOL_ORDER = [
  "approve_registration",
  "reject_registration",
  "approve_room_change",
  "reject_room_change",
  "create_room",
  "update_room",
  "delete_room",
  "update_ticket",
] as const;

const ALL_TOOL_ORDER = [...TOOL_ORDER, ...WRITE_TOOL_ORDER];

const CONFIRMATION_SENTENCE =
  "This changes data: show the user exactly what will change and get their explicit confirmation before calling.";

const UUID_STUDENT = "11111111-1111-4111-8111-111111111111";
const UUID_ROOM = "22222222-2222-4222-8222-222222222222";
const UUID_REQUEST = "33333333-3333-4333-8333-333333333333";
const UUID_TICKET = "44444444-4444-4444-8444-444444444444";

describe("tool registration", () => {
  it("registers exactly the 14 tools, in order, with the 6 Python read descriptions verbatim", () => {
    const { deps } = makeDeps();
    const tools = captureTools(deps);
    expect(tools.map((tool) => tool.name)).toEqual(ALL_TOOL_ORDER);
    for (const [name, description] of Object.entries(DESCRIPTIONS)) {
      expect(tools.find((tool) => tool.name === name)!.description).toBe(description);
    }
    for (const tool of tools) {
      expect(tool.description).toBeTruthy();
      expect(tool.inputSchema).toBeDefined();
    }
  });

  it("tells the model to confirm writes and where each id comes from", () => {
    const { deps } = makeDeps();
    const tools = captureTools(deps);
    const idSources: Record<string, string[]> = {
      approve_registration: ["list_pending_registrations", "list_rooms"],
      reject_registration: ["list_pending_registrations"],
      approve_room_change: ["list_room_change_requests", "list_rooms"],
      reject_room_change: ["list_room_change_requests"],
      create_room: [],
      update_room: ["list_rooms"],
      delete_room: ["list_rooms"],
      update_ticket: ["list_maintenance_tickets"],
    };
    for (const name of WRITE_TOOL_ORDER) {
      const description = tools.find((tool) => tool.name === name)!.description;
      expect(description).toContain(CONFIRMATION_SENTENCE);
      for (const source of idSources[name]!) {
        expect(description).toContain(source);
      }
    }
  });

  it("annotates the reads as read-only and the writes as open-world writes", () => {
    const { deps } = makeDeps();
    const tools = captureTools(deps);
    for (const name of TOOL_ORDER) {
      expect(tools.find((tool) => tool.name === name)!.annotations).toEqual({
        readOnlyHint: true,
        openWorldHint: true,
      });
    }
    const expectedWrites: Record<string, ToolAnnotations> = {
      approve_registration: { readOnlyHint: false, openWorldHint: true },
      reject_registration: { readOnlyHint: false, openWorldHint: true, destructiveHint: true },
      approve_room_change: { readOnlyHint: false, openWorldHint: true },
      reject_room_change: { readOnlyHint: false, openWorldHint: true, destructiveHint: true },
      create_room: { readOnlyHint: false, openWorldHint: true },
      update_room: { readOnlyHint: false, openWorldHint: true },
      delete_room: { readOnlyHint: false, openWorldHint: true, destructiveHint: true },
      update_ticket: { readOnlyHint: false, openWorldHint: true },
    };
    for (const name of WRITE_TOOL_ORDER) {
      expect(tools.find((tool) => tool.name === name)!.annotations).toEqual(expectedWrites[name]);
    }
  });

  it("marks exactly reject_registration, reject_room_change and delete_room as destructive", () => {
    const { deps } = makeDeps();
    const tools = captureTools(deps);
    expect(
      tools.filter((tool) => tool.annotations?.destructiveHint === true).map((tool) => tool.name),
    ).toEqual(["reject_registration", "reject_room_change", "delete_room"]);
  });

  it("uses the new 14-tool server instructions (reads stay char-for-char; this text diverges)", () => {
    expect(SERVER_NAME).toBe("RÉSIVO Admin");
    expect(SERVER_INSTRUCTIONS).toBe(
      "Administrator tools for RÉSIVO, the university residence management system. " +
        "You can read data freely; when the administrator has enabled changes " +
        "you can also approve or reject registrations and room-change requests, " +
        "manage rooms, and update maintenance tickets. Before any change, show " +
        "the user exactly what will change and get their explicit confirmation. " +
        "All data comes from the live Supabase project; every call is logged.",
    );
  });

  it("builds a real McpServer that accepts the schemas", () => {
    const { deps } = makeDeps();
    expect(buildMcpServer(deps)).toBeInstanceOf(McpServer);
  });
});

describe("list_maintenance_tickets", () => {
  it("audits first, rpc second, then returns compact truncated JSON", async () => {
    const { deps, audit, rpc } = makeDeps();
    rpc.mockResolvedValueOnce([{ id: 1, description: "L".repeat(501), room: "B-101" }]);
    const tool = captureTools(deps).find((t) => t.name === "list_maintenance_tickets")!;

    const result = await tool.handler({});

    expect(audit.begin).toHaveBeenCalledBefore(rpc);
    expect(audit.begin).toHaveBeenCalledExactlyOnceWith("list_maintenance_tickets", {
      status: null,
      limit: 20,
    });
    expect(rpc).toHaveBeenCalledExactlyOnceWith("mcp_list_tickets", {
      p_status: null,
      p_limit: 20,
    });
    const parsed = JSON.parse(result.content[0]!.text) as Array<Record<string, unknown>>;
    expect(parsed[0]!.description).toBe("L".repeat(497) + "...");
    expect(parsed[0]!.room).toBe("B-101");
    expect(result.content[0]!.type).toBe("text");
  });

  it("normalizes the status and passes it through", async () => {
    const { deps, rpc } = makeDeps();
    const tool = captureTools(deps).find((t) => t.name === "list_maintenance_tickets")!;

    await tool.handler({ status: " In Progress ", limit: 5 });

    expect(rpc).toHaveBeenCalledExactlyOnceWith("mcp_list_tickets", {
      p_status: "in_progress",
      p_limit: 5,
    });
  });

  it("caps the limit like the Python server", async () => {
    const { deps, rpc } = makeDeps();
    const tool = captureTools(deps).find((t) => t.name === "list_maintenance_tickets")!;

    await tool.handler({ limit: 1000 });
    expect(rpc).toHaveBeenLastCalledWith("mcp_list_tickets", { p_status: null, p_limit: 100 });

    await tool.handler({ limit: 0 });
    expect(rpc).toHaveBeenLastCalledWith("mcp_list_tickets", { p_status: null, p_limit: 1 });
  });

  it("returns the friendly empty message with the normalized status", async () => {
    const { deps } = makeDeps();
    const tool = captureTools(deps).find((t) => t.name === "list_maintenance_tickets")!;

    const result = await tool.handler({ status: "In Progress" });
    expect(result.content[0]!.text).toBe("No in-progress maintenance tickets found.");
  });

  it("returns 'Invalid request' for a bad status, after auditing, without calling rpc", async () => {
    const { deps, audit, rpc } = makeDeps();
    const tool = captureTools(deps).find((t) => t.name === "list_maintenance_tickets")!;

    const result = await tool.handler({ status: "bogus" });

    expect(result.content[0]!.text).toBe(
      "Invalid request: invalid status 'bogus': expected one of pending, in_progress, resolved",
    );
    expect(audit.begin).toHaveBeenCalledExactlyOnceWith("list_maintenance_tickets", {
      status: "bogus",
      limit: 20,
    });
    expect(rpc).not.toHaveBeenCalled();
  });

  it("maps SQL errors with friendlyError", async () => {
    const { deps, rpc } = makeDeps();
    const tool = captureTools(deps).find((t) => t.name === "list_maintenance_tickets")!;

    rpc.mockRejectedValueOnce(new Error("admin only"));
    expect((await tool.handler({})).content[0]!.text).toBe(
      "Permission denied: this tool requires an administrator account (profiles.role = 'admin').",
    );

    rpc.mockRejectedValueOnce(new Error("JWT expired"));
    expect((await tool.handler({})).content[0]!.text).toBe(
      "The server could not authenticate with Supabase. Check ADMIN_EMAIL / ADMIN_PASSWORD in mcp/.env.",
    );
  });
});

describe("list_room_change_requests", () => {
  it("uses the room-change statuses and the room-change empty message", async () => {
    const { deps, rpc } = makeDeps();
    const tool = captureTools(deps).find((t) => t.name === "list_room_change_requests")!;

    const result = await tool.handler({ status: "Approved" });
    expect(rpc).toHaveBeenCalledExactlyOnceWith("mcp_list_room_changes", {
      p_status: "approved",
      p_limit: 20,
    });
    expect(result.content[0]!.text).toBe("No approved room change requests found.");
  });

  it("rejects ticket-only statuses", async () => {
    const { deps } = makeDeps();
    const tool = captureTools(deps).find((t) => t.name === "list_room_change_requests")!;

    expect((await tool.handler({ status: "in_progress" })).content[0]!.text).toBe(
      "Invalid request: invalid status 'in_progress': expected one of pending, approved, rejected",
    );
  });
});

describe("list_pending_registrations", () => {
  it("defaults to limit 20 and returns the registrations empty message", async () => {
    const { deps, rpc } = makeDeps();
    const tool = captureTools(deps).find((t) => t.name === "list_pending_registrations")!;

    const result = await tool.handler({});
    expect(rpc).toHaveBeenCalledExactlyOnceWith("mcp_list_pending_registrations", { p_limit: 20 });
    expect(result.content[0]!.text).toBe("No pending registrations found.");
  });
});

describe("search_students", () => {
  it("rejects a blank query, after auditing, without calling rpc", async () => {
    const { deps, audit, rpc } = makeDeps();
    const tool = captureTools(deps).find((t) => t.name === "search_students")!;

    const result = await tool.handler({ query: "   " });
    expect(result.content[0]!.text).toBe(
      "Invalid request: query is required (a name, card ID or room label such as 'B-101').",
    );
    expect(audit.begin).toHaveBeenCalledExactlyOnceWith("search_students", {
      query: "   ",
      limit: 10,
    });
    expect(rpc).not.toHaveBeenCalled();
  });

  it("trims the query and defaults the limit to 10", async () => {
    const { deps, rpc } = makeDeps();
    const tool = captureTools(deps).find((t) => t.name === "search_students")!;

    await tool.handler({ query: "  B-101 " });
    expect(rpc).toHaveBeenCalledExactlyOnceWith("mcp_search_students", {
      p_query: "B-101",
      p_limit: 10,
    });
  });

  it("returns the students empty message", async () => {
    const { deps } = makeDeps();
    const tool = captureTools(deps).find((t) => t.name === "search_students")!;

    expect((await tool.handler({ query: "Ali" })).content[0]!.text).toBe(
      "No students matched your search.",
    );
  });
});

describe("list_rooms", () => {
  it("passes the block filter and only_available through", async () => {
    const { deps, rpc } = makeDeps();
    const tool = captureTools(deps).find((t) => t.name === "list_rooms")!;

    await tool.handler({ block: " B ", only_available: true });
    expect(rpc).toHaveBeenCalledExactlyOnceWith("mcp_list_rooms", {
      p_block: "B",
      p_only_available: true,
    });
  });

  it("treats a blank block as no filter", async () => {
    const { deps, rpc } = makeDeps();
    const tool = captureTools(deps).find((t) => t.name === "list_rooms")!;

    await tool.handler({ block: "" });
    expect(rpc).toHaveBeenCalledExactlyOnceWith("mcp_list_rooms", {
      p_block: null,
      p_only_available: false,
    });
  });

  it("returns the room empty messages (with and without block)", async () => {
    const { deps } = makeDeps();
    const tool = captureTools(deps).find((t) => t.name === "list_rooms")!;

    expect((await tool.handler({ block: "B" })).content[0]!.text).toBe(
      "No rooms found in block B.",
    );
    expect((await tool.handler({})).content[0]!.text).toBe("No rooms found.");
  });
});

describe("get_summary", () => {
  it("audits with empty args and returns compact JSON", async () => {
    const { deps, audit, rpc } = makeDeps();
    rpc.mockResolvedValueOnce({ residents: 120, blocks: { A: 40 } });
    const tool = captureTools(deps).find((t) => t.name === "get_summary")!;

    const result = await tool.handler({});
    expect(audit.begin).toHaveBeenCalledExactlyOnceWith("get_summary", {});
    expect(rpc).toHaveBeenCalledExactlyOnceWith("mcp_summary", {});
    expect(result.content[0]!.text).toBe('{"residents":120,"blocks":{"A":40}}');
  });

  it("returns 'No data returned.' for null", async () => {
    const { deps, rpc } = makeDeps();
    rpc.mockResolvedValueOnce(null);
    const tool = captureTools(deps).find((t) => t.name === "get_summary")!;

    expect((await tool.handler({})).content[0]!.text).toBe("No data returned.");
  });
});

// ---------------------------------------------------------------------------
// Write tools: gate → audit attempt → execute → audit outcome
// ---------------------------------------------------------------------------

interface WriteCase {
  tool: string;
  args: Record<string, unknown>;
  auditArgs: Record<string, unknown>;
  rpc: string;
  params: Record<string, unknown>;
  row: Record<string, unknown>;
  detail: string;
  error: { message: string; text: string };
}

const WRITE_CASES: WriteCase[] = [
  {
    tool: "approve_registration",
    args: { student_id: UUID_STUDENT, room_id: UUID_ROOM },
    auditArgs: { student_id: UUID_STUDENT, room_id: UUID_ROOM },
    rpc: "approve_student",
    params: { p_student: UUID_STUDENT, p_room: UUID_ROOM },
    row: { id: UUID_STUDENT, card_id: "20260001", status: "active" },
    detail: "Approved registration for card 20260001.",
    error: { message: "gender mismatch", text: "That room's gender does not match the student's." },
  },
  {
    tool: "reject_registration",
    args: { student_id: UUID_STUDENT, reason: "Missing documents" },
    auditArgs: { student_id: UUID_STUDENT, reason: "Missing documents" },
    rpc: "reject_student",
    params: { p_student: UUID_STUDENT, p_reason: "Missing documents" },
    row: { id: UUID_STUDENT, card_id: "20260001", status: "rejected" },
    detail: "Rejected registration for card 20260001.",
    error: {
      message: "student not found",
      text: "Student not found (the id may be stale — re-check with list_pending_registrations or search_students).",
    },
  },
  {
    tool: "approve_room_change",
    args: { request_id: UUID_REQUEST, room_id: UUID_ROOM },
    auditArgs: { request_id: UUID_REQUEST, room_id: UUID_ROOM },
    rpc: "approve_room_change",
    params: { p_request: UUID_REQUEST, p_room: UUID_ROOM },
    row: { id: UUID_REQUEST, status: "approved" },
    detail: `Approved room change request ${UUID_REQUEST}.`,
    error: {
      message: "pending request not found",
      text: "No pending room-change request with that id (it may already be decided — re-check with list_room_change_requests).",
    },
  },
  {
    tool: "reject_room_change",
    args: { request_id: UUID_REQUEST, reason: "Room unavailable" },
    auditArgs: { request_id: UUID_REQUEST, reason: "Room unavailable" },
    rpc: "reject_room_change",
    params: { p_request: UUID_REQUEST, p_reason: "Room unavailable" },
    row: { id: UUID_REQUEST, status: "rejected" },
    detail: `Rejected room change request ${UUID_REQUEST}.`,
    error: { message: "reason required", text: "A rejection reason is required." },
  },
  {
    tool: "create_room",
    args: { block: "ZZT", floor: 9, number: "MCP-1", capacity: 2, gender: "male" },
    auditArgs: { block: "ZZT", floor: 9, number: "MCP-1", capacity: 2, gender: "male" },
    rpc: "mcp_create_room",
    params: { p_block: "ZZT", p_floor: 9, p_number: "MCP-1", p_capacity: 2, p_gender: "male" },
    row: { id: UUID_ROOM, block: "ZZT", floor: 9, number: "MCP-1", capacity: 2, gender: "male" },
    detail: "Created room ZZT-MCP-1.",
    error: { message: "Room ZZT-MCP-1 already exists.", text: "Room ZZT-MCP-1 already exists." },
  },
  {
    tool: "update_room",
    args: { room_id: UUID_ROOM, capacity: 3 },
    auditArgs: {
      room_id: UUID_ROOM,
      block: null,
      floor: null,
      number: null,
      capacity: 3,
      gender: null,
    },
    rpc: "mcp_update_room",
    params: {
      p_room: UUID_ROOM,
      p_block: null,
      p_floor: null,
      p_number: null,
      p_capacity: 3,
      p_gender: null,
    },
    row: { id: UUID_ROOM, block: "B", floor: 1, number: "101", capacity: 3 },
    detail: "Updated room B-101.",
    error: {
      message: "Cannot set capacity below the 2 active resident(s) already assigned.",
      text: "Cannot set capacity below the 2 active resident(s) already assigned.",
    },
  },
  {
    tool: "delete_room",
    args: { room_id: UUID_ROOM },
    auditArgs: { room_id: UUID_ROOM },
    rpc: "mcp_delete_room",
    params: { p_room: UUID_ROOM },
    row: { deleted: true, room: { id: UUID_ROOM, block: "B", number: "101" } },
    detail: "Deleted room B-101.",
    error: {
      message: "Cannot delete room B-101: 2 active resident(s) are still assigned.",
      text: "Cannot delete room B-101: 2 active resident(s) are still assigned.",
    },
  },
  {
    tool: "update_ticket",
    args: { ticket_id: UUID_TICKET, status: "resolved", note: "Fixed the tap" },
    auditArgs: { ticket_id: UUID_TICKET, status: "resolved", note: "Fixed the tap" },
    rpc: "mcp_update_ticket",
    params: { p_ticket: UUID_TICKET, p_status: "resolved", p_note: "Fixed the tap" },
    row: { id: UUID_TICKET, status: "resolved" },
    detail: `Ticket ${UUID_TICKET} marked resolved.`,
    error: {
      message: "ticket not found",
      text: "Maintenance ticket not found (re-check with list_maintenance_tickets).",
    },
  },
];

describe("write tools", () => {
  describe.each(WRITE_CASES)("$tool", (testCase) => {
    it("gates, audits the attempt, executes and completes the outcome on success", async () => {
      const { deps, audit, rpc } = makeDeps();
      rpc.mockResolvedValueOnce({ writes_enabled: true }).mockResolvedValueOnce(testCase.row);
      const tool = captureTools(deps).find((t) => t.name === testCase.tool)!;

      const result = await tool.handler(testCase.args);

      expect(rpc).toHaveBeenNthCalledWith(1, "mcp_get_settings", {});
      expect(rpc).toHaveBeenNthCalledWith(2, testCase.rpc, testCase.params);
      // Gate read → audit attempt → write rpc → audit outcome.
      expect(rpc).toHaveBeenCalledBefore(audit.begin);
      expect(audit.begin.mock.invocationCallOrder[0]!).toBeLessThan(
        rpc.mock.invocationCallOrder[1]!,
      );
      expect(rpc.mock.invocationCallOrder[1]!).toBeLessThan(
        audit.complete.mock.invocationCallOrder[0]!,
      );
      expect(audit.begin).toHaveBeenCalledExactlyOnceWith(testCase.tool, testCase.auditArgs);
      expect(audit.complete).toHaveBeenCalledExactlyOnceWith(1, true, testCase.detail);
      expect(result.content[0]!.type).toBe("text");
      expect(JSON.parse(result.content[0]!.text)).toEqual(testCase.row);
    });

    it("refuses with the disabled message without executing when writes are off", async () => {
      const { deps, audit, rpc } = makeDeps();
      rpc.mockResolvedValueOnce({ writes_enabled: false });
      const tool = captureTools(deps).find((t) => t.name === testCase.tool)!;

      const result = await tool.handler(testCase.args);

      expect(result.content[0]!.text).toBe(WRITING_DISABLED_MESSAGE);
      expect(rpc).toHaveBeenCalledExactlyOnceWith("mcp_get_settings", {});
      expect(audit.begin).toHaveBeenCalledExactlyOnceWith(testCase.tool, testCase.auditArgs);
      expect(audit.complete).toHaveBeenCalledExactlyOnceWith(1, false, WRITING_DISABLED_MESSAGE);
    });

    it("refuses when the writes gate cannot be read (fail closed)", async () => {
      const { deps, audit, rpc } = makeDeps();
      rpc.mockRejectedValueOnce(new Error("network down"));
      const tool = captureTools(deps).find((t) => t.name === testCase.tool)!;

      const result = await tool.handler(testCase.args);

      expect(result.content[0]!.text).toBe(
        "Writing could not be verified right now, so nothing was changed. Try again.",
      );
      expect(rpc).toHaveBeenCalledExactlyOnceWith("mcp_get_settings", {});
      expect(audit.begin).toHaveBeenCalledExactlyOnceWith(testCase.tool, testCase.auditArgs);
      expect(audit.complete).toHaveBeenCalledExactlyOnceWith(
        1,
        false,
        "Writing could not be verified right now, so nothing was changed. Try again.",
      );
    });

    it("refuses when the audit attempt row cannot be recorded", async () => {
      const { deps, audit, rpc } = makeDeps();
      rpc.mockResolvedValueOnce({ writes_enabled: true });
      audit.begin.mockResolvedValueOnce(null);
      const tool = captureTools(deps).find((t) => t.name === testCase.tool)!;

      const result = await tool.handler(testCase.args);

      expect(result.content[0]!.text).toBe(AUDIT_REQUIRED_MESSAGE);
      expect(rpc).toHaveBeenCalledExactlyOnceWith("mcp_get_settings", {});
      expect(audit.complete).not.toHaveBeenCalled();
    });

    it("maps rpc failures to friendly text and completes the row with ok=false", async () => {
      const { deps, audit, rpc } = makeDeps();
      rpc
        .mockResolvedValueOnce({ writes_enabled: true })
        .mockRejectedValueOnce(new Error(testCase.error.message));
      const tool = captureTools(deps).find((t) => t.name === testCase.tool)!;

      const result = await tool.handler(testCase.args);

      expect(result.content[0]!.text).toBe(testCase.error.text);
      expect(rpc).toHaveBeenNthCalledWith(2, testCase.rpc, testCase.params);
      expect(audit.complete).toHaveBeenCalledExactlyOnceWith(1, false, testCase.error.text);
    });
  });

  it("treats a missing settings row (null or no key) as enabled", async () => {
    const { deps, rpc } = makeDeps();
    const tool = captureTools(deps).find((t) => t.name === "delete_room")!;
    const row = { deleted: true, room: { block: "B", number: "101" } };

    rpc.mockResolvedValueOnce({ updated_at: null }).mockResolvedValueOnce(row);
    expect((await tool.handler({ room_id: UUID_ROOM })).content[0]!.text).toContain('"deleted":true');

    rpc.mockResolvedValueOnce(null).mockResolvedValueOnce(row);
    expect((await tool.handler({ room_id: UUID_ROOM })).content[0]!.text).toContain('"deleted":true');
  });

  it("normalizes gender and ticket status before calling the rpc", async () => {
    const { deps, rpc } = makeDeps();
    const tools = captureTools(deps);

    rpc.mockResolvedValueOnce({ writes_enabled: true }).mockResolvedValueOnce({});
    await tools.find((t) => t.name === "create_room")!.handler({
      block: "ZZT",
      floor: 1,
      number: "1",
      capacity: 2,
      gender: " Female ",
    });
    expect(rpc).toHaveBeenNthCalledWith(2, "mcp_create_room", {
      p_block: "ZZT",
      p_floor: 1,
      p_number: "1",
      p_capacity: 2,
      p_gender: "female",
    });

    rpc.mockResolvedValueOnce({ writes_enabled: true }).mockResolvedValueOnce({});
    await tools.find((t) => t.name === "update_ticket")!.handler({
      ticket_id: UUID_TICKET,
      status: " In Progress ",
    });
    expect(rpc).toHaveBeenLastCalledWith("mcp_update_ticket", {
      p_ticket: UUID_TICKET,
      p_status: "in_progress",
      p_note: null,
    });
  });

  it("truncates long free-text fields in write results", async () => {
    const { deps, rpc } = makeDeps();
    rpc
      .mockResolvedValueOnce({ writes_enabled: true })
      .mockResolvedValueOnce({
        id: UUID_TICKET,
        status: "in_progress",
        staff_note: "S".repeat(600),
      });
    const tool = captureTools(deps).find((t) => t.name === "update_ticket")!;

    const result = await tool.handler({ ticket_id: UUID_TICKET, status: "in_progress" });

    const parsed = JSON.parse(result.content[0]!.text) as { staff_note: string };
    expect(parsed.staff_note).toBe("S".repeat(497) + "...");
  });

  it("returns 'No data returned.' when the write rpc returns null", async () => {
    const { deps, audit, rpc } = makeDeps();
    rpc.mockResolvedValueOnce({ writes_enabled: true }).mockResolvedValueOnce(null);
    const tool = captureTools(deps).find((t) => t.name === "delete_room")!;

    const result = await tool.handler({ room_id: UUID_ROOM });

    expect(result.content[0]!.text).toBe("No data returned.");
    expect(audit.complete).toHaveBeenCalledExactlyOnceWith(1, true, expect.any(String));
  });
});

const INVALID_REQUESTS: Array<{ tool: string; args: Record<string, unknown>; text: string }> = [
  {
    tool: "reject_registration",
    args: { student_id: UUID_STUDENT, reason: "   " },
    text: "Invalid request: a rejection reason is required (so the student knows why).",
  },
  {
    tool: "reject_room_change",
    args: { request_id: UUID_REQUEST, reason: "" },
    text: "Invalid request: a rejection reason is required (so the student knows why).",
  },
  {
    tool: "create_room",
    args: { block: "ZZT", floor: 16, number: "1", capacity: 2, gender: "male" },
    text: "Invalid request: floor must be between 0 and 15.",
  },
  {
    tool: "create_room",
    args: { block: "ZZT", floor: -1, number: "1", capacity: 2, gender: "male" },
    text: "Invalid request: floor must be between 0 and 15.",
  },
  {
    tool: "update_room",
    args: { room_id: UUID_ROOM, floor: 16 },
    text: "Invalid request: floor must be between 0 and 15.",
  },
  {
    tool: "create_room",
    args: { block: "ZZT", floor: 1, number: "1", capacity: 9, gender: "male" },
    text: "Invalid request: capacity must be between 1 and 8.",
  },
  {
    tool: "create_room",
    args: { block: "ZZT", floor: 1, number: "1", capacity: 0, gender: "male" },
    text: "Invalid request: capacity must be between 1 and 8.",
  },
  {
    tool: "update_room",
    args: { room_id: UUID_ROOM, capacity: 9 },
    text: "Invalid request: capacity must be between 1 and 8.",
  },
  {
    tool: "create_room",
    args: { block: "ZZT", floor: 1, number: "1", capacity: 2, gender: "x" },
    text: "Invalid request: gender must be male or female.",
  },
  {
    tool: "update_room",
    args: { room_id: UUID_ROOM, gender: "x" },
    text: "Invalid request: gender must be male or female.",
  },
  {
    tool: "update_ticket",
    args: { ticket_id: UUID_TICKET, status: "done" },
    text: "Invalid request: status must be in_progress or resolved.",
  },
  {
    tool: "approve_registration",
    args: { student_id: "not-a-uuid", room_id: UUID_ROOM },
    text: "Invalid request: student_id must be a uuid copied from list_pending_registrations.",
  },
  {
    tool: "approve_registration",
    args: { student_id: UUID_STUDENT, room_id: "not-a-uuid" },
    text: "Invalid request: room_id must be a uuid copied from list_rooms.",
  },
  {
    tool: "reject_registration",
    args: { student_id: "123", reason: "Missing documents" },
    text: "Invalid request: student_id must be a uuid copied from list_pending_registrations.",
  },
  {
    tool: "approve_room_change",
    args: { request_id: "abc", room_id: UUID_ROOM },
    text: "Invalid request: request_id must be a uuid copied from list_room_change_requests.",
  },
  {
    tool: "approve_room_change",
    args: { request_id: UUID_REQUEST, room_id: "abc" },
    text: "Invalid request: room_id must be a uuid copied from list_rooms.",
  },
  {
    tool: "reject_room_change",
    args: { request_id: "abc", reason: "Room unavailable" },
    text: "Invalid request: request_id must be a uuid copied from list_room_change_requests.",
  },
  {
    tool: "update_room",
    args: { room_id: "abc" },
    text: "Invalid request: room_id must be a uuid copied from list_rooms.",
  },
  {
    tool: "delete_room",
    args: { room_id: "abc" },
    text: "Invalid request: room_id must be a uuid copied from list_rooms.",
  },
  {
    tool: "update_ticket",
    args: { ticket_id: "abc", status: "resolved" },
    text: "Invalid request: ticket_id must be a uuid copied from list_maintenance_tickets.",
  },
];

describe("write validation", () => {
  it.each(INVALID_REQUESTS)("$tool rejects invalid args before any rpc", async ({
    tool: name,
    args,
    text,
  }) => {
    const { deps, audit, rpc } = makeDeps();
    const tool = captureTools(deps).find((t) => t.name === name)!;

    const result = await tool.handler(args);

    expect(result.content[0]!.text).toBe(text);
    expect(rpc).not.toHaveBeenCalled();
    expect(audit.begin).not.toHaveBeenCalled();
  });
});

describe("createAuditLogger", () => {
  describe("begin", () => {
    it("calls mcp_log_audit with p_tool/p_args and a timeout signal, returns the row id", async () => {
      const rpc = vi.fn(async (_fn: string, _params?: Record<string, unknown>, _opts?: unknown) => 7);
      const audit = createAuditLogger(rpc);

      await expect(audit.begin("get_summary", { answer: 42 })).resolves.toBe(7);

      expect(rpc).toHaveBeenCalledTimes(1);
      const [fn, params, options] = rpc.mock.calls[0]!;
      expect(fn).toBe("mcp_log_audit");
      expect(params).toEqual({ p_tool: "get_summary", p_args: { answer: 42 } });
      expect((options as { signal: unknown }).signal).toBeInstanceOf(AbortSignal);
    });

    it("accepts a numeric string id (PostgREST bigint)", async () => {
      const audit = createAuditLogger(async () => "42");
      await expect(audit.begin("get_summary", {})).resolves.toBe(42);
    });

    it("returns null when rpc resolves null", async () => {
      const audit = createAuditLogger(async () => null);
      await expect(audit.begin("get_summary", {})).resolves.toBeNull();
    });

    it("returns null for empty or non-numeric bodies", async () => {
      const audit = createAuditLogger(async () => "");
      await expect(audit.begin("get_summary", {})).resolves.toBeNull();
    });

    it("returns null for unexpected bodies", async () => {
      const audit = createAuditLogger(async () => ({ id: 3 }));
      await expect(audit.begin("get_summary", {})).resolves.toBeNull();
    });

    it("returns null on async failure", async () => {
      const audit = createAuditLogger(async () => {
        throw new Error("network error: boom");
      });
      await expect(audit.begin("get_summary", {})).resolves.toBeNull();
    });

    it("returns null on synchronous failure", async () => {
      const audit = createAuditLogger(() => {
        throw new Error("sync boom");
      });
      await expect(audit.begin("get_summary", {})).resolves.toBeNull();
    });
  });

  describe("complete", () => {
    it("calls mcp_complete_audit with p_id/p_ok/p_detail and a timeout signal", async () => {
      const rpc = vi.fn(async (_fn: string, _params?: Record<string, unknown>, _opts?: unknown) => null);
      const audit = createAuditLogger(rpc);

      await audit.complete(7, true, "ticket resolved");

      expect(rpc).toHaveBeenCalledTimes(1);
      const [fn, params, options] = rpc.mock.calls[0]!;
      expect(fn).toBe("mcp_complete_audit");
      expect(params).toEqual({ p_id: 7, p_ok: true, p_detail: "ticket resolved" });
      expect((options as { signal: unknown }).signal).toBeInstanceOf(AbortSignal);
    });

    it("does nothing when the id is null", async () => {
      const rpc = vi.fn(async () => 1);
      const audit = createAuditLogger(rpc);

      await audit.complete(null, false, "refused");

      expect(rpc).not.toHaveBeenCalled();
    });

    it("swallows async failures", async () => {
      const audit = createAuditLogger(async () => {
        throw new Error("network error: boom");
      });
      await expect(audit.complete(7, false, "boom")).resolves.toBeUndefined();
    });

    it("swallows synchronous failures", async () => {
      const audit = createAuditLogger(() => {
        throw new Error("sync boom");
      });
      await expect(audit.complete(7, false, "boom")).resolves.toBeUndefined();
    });
  });
});
