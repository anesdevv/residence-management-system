/**
 * Two-phase audit trail for tool calls (plan D7 / spec B3).
 *
 * Phase 1 — `begin`: `mcp_log_audit(p_tool, p_args)` opens a row and returns
 * its id. Phase 2 — `complete`: `mcp_complete_audit(p_id, p_ok, p_detail)`
 * fills the outcome. Reads only use `begin` (ok stays null); writes use both,
 * so a row stuck at `ok = null` means "outcome unknown" — visible, never
 * silent. Each roundtrip is bounded by a 2 s timeout.
 *
 * The logger itself never throws: `begin` degrades to null (the write flow
 * then refuses the change — "no audit row, no write"), `complete` is
 * best-effort. Records tool name + arguments + timestamp + short outcome
 * detail (server-side); never tokens.
 */
import type { RpcOptions } from "./supabase";

/** Hard ceiling on each audit roundtrip (plan D7). */
export const AUDIT_TIMEOUT_MS = 2000;

export type RpcCall = (
  functionName: string,
  params?: Record<string, unknown>,
  options?: RpcOptions,
) => Promise<unknown>;

export interface AuditTrail {
  /**
   * Open an audit row for a tool call; resolves with its id, or `null` when
   * the row could not be recorded (timeout, network, permission errors).
   */
  begin(tool: string, args: Record<string, unknown>): Promise<number | null>;
  /**
   * Fill the outcome of an audit row opened by `begin`; best-effort no-op for
   * a `null` id and every failure is swallowed.
   */
  complete(id: number | null, ok: boolean, detail: string): Promise<void>;
}

/**
 * PostgREST serializes a bigint column as a JSON number; tolerate a numeric
 * string too. Anything else (null, object, empty/non-numeric string) → null.
 */
function toAuditId(body: unknown): number | null {
  if (typeof body === "number") return Number.isFinite(body) ? body : null;
  if (typeof body === "string" && body.trim() !== "") {
    const value = Number(body);
    return Number.isFinite(value) ? value : null;
  }
  return null;
}

/** Build the two-phase audit trail around the admin rpc function. */
export function createAuditLogger(rpc: RpcCall): AuditTrail {
  return {
    async begin(tool, args) {
      try {
        const body = await rpc(
          "mcp_log_audit",
          { p_tool: tool, p_args: args },
          { signal: AbortSignal.timeout(AUDIT_TIMEOUT_MS) },
        );
        return toAuditId(body);
      } catch {
        // Swallow everything (timeouts, network, permission errors): parity
        // with Python's `except OSError: pass`. The null return tells the
        // caller to refuse the write (fail closed).
        return null;
      }
    },
    async complete(id, ok, detail) {
      if (id === null) return;
      try {
        await rpc(
          "mcp_complete_audit",
          { p_id: id, p_ok: ok, p_detail: detail },
          { signal: AbortSignal.timeout(AUDIT_TIMEOUT_MS) },
        );
      } catch {
        // Best-effort by design: completion must never fail a tool call. A
        // row left at `ok = null` stays visible as "outcome unknown".
      }
    },
  };
}
