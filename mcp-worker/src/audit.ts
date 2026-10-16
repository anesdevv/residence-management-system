/**
 * Audit trail for tool calls: `mcp_log_audit(p_tool, p_args)`.
 *
 * Ports `mcp/server.py::audit_tool_call` semantics to the worker: awaited
 * before the tool runs, bounded by a 2 s timeout, and every failure is
 * swallowed — audit logging must never fail a tool call. Records tool name +
 * arguments + timestamp (server-side); never results, never tokens.
 */
import type { RpcOptions } from "./supabase";

/** Hard ceiling on the audit roundtrip (plan D7). */
export const AUDIT_TIMEOUT_MS = 2000;

export type RpcCall = (
  functionName: string,
  params?: Record<string, unknown>,
  options?: RpcOptions,
) => Promise<unknown>;

export type AuditLog = (tool: string, args: Record<string, unknown>) => Promise<void>;

/** Build the audit logger around the admin rpc function. */
export function createAuditLogger(rpc: RpcCall): AuditLog {
  return async (tool, args) => {
    try {
      await rpc(
        "mcp_log_audit",
        { p_tool: tool, p_args: args },
        { signal: AbortSignal.timeout(AUDIT_TIMEOUT_MS) },
      );
    } catch {
      // Swallow everything (timeouts, network, permission errors): parity
      // with Python's `except OSError: pass`.
    }
  };
}
