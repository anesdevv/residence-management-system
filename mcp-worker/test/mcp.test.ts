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
  SERVER_INSTRUCTIONS,
  SERVER_NAME,
  buildMcpServer,
  registerAdminTools,
  type ToolDeps,
} from "../src/mcp";

type HandlerResult = { content: Array<{ type: string; text: string }> };
type Handler = (args: Record<string, unknown>) => Promise<HandlerResult>;

interface Registered {
  name: string;
  description: string;
  inputSchema: unknown;
  handler: Handler;
}

function captureTools(deps: ToolDeps): Registered[] {
  const registered: Registered[] = [];
  const fake = {
    registerTool(
      name: string,
      config: { description: string; inputSchema: unknown },
      handler: Handler,
    ) {
      registered.push({
        name,
        description: config.description,
        inputSchema: config.inputSchema,
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
    begin: vi.fn(async (_tool: string, _args: Record<string, unknown>) => 1),
    complete: vi.fn(async (_id: number | null, _ok: boolean, _detail: string) => {}),
  };
  const rpc = vi.fn(async (_fn: string, _params?: Record<string, unknown>): Promise<unknown> => []);
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

describe("tool registration", () => {
  it("registers exactly the 6 Python tools, in order, with verbatim descriptions", () => {
    const { deps } = makeDeps();
    const tools = captureTools(deps);
    expect(tools.map((tool) => tool.name)).toEqual(TOOL_ORDER);
    for (const tool of tools) {
      expect(tool.description).toBe(DESCRIPTIONS[tool.name as keyof typeof DESCRIPTIONS]);
      expect(tool.inputSchema).toBeDefined();
    }
  });

  it("uses the server name and instructions from mcp/server.py verbatim", () => {
    expect(SERVER_NAME).toBe("Residence Tlemcen Admin");
    expect(SERVER_INSTRUCTIONS).toBe(
      "Read-only administrator tools for the Residence Tlemcen university " +
        "residence (maintenance tickets, room change requests, pending " +
        "registrations, student lookup, rooms and an overall summary). " +
        "All data comes from the live Supabase project. The tools never " +
        "modify anything.",
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
