// supabase/functions/_shared/validation.ts

export const MAX_BODY_SIZE = 32 * 1024; // 32 KB

export function isCardId(identifier: string): boolean {
  return /^\d{4,}$/.test(identifier.trim());
}

export function safeLog(action: string, meta: {
  status: number;
  ip?: string;
  identifierType?: "card_id" | "unknown";
  error?: string;
}) {
  const sanitizedIp = meta.ip ? meta.ip.replace(/\.\d+$/, ".xxx") : "unknown";
  console.log(JSON.stringify({
    timestamp: new Date().toISOString(),
    action,
    status: meta.status,
    ip: sanitizedIp,
    identifierType: meta.identifierType ?? "unknown",
    error: meta.error ?? null,
  }));
}
