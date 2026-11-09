// supabase/functions/_shared/validation.ts

export const MAX_BODY_SIZE = 32 * 1024; // 32 KB

export function isCardId(identifier: string): boolean {
  return /^\d{4,}$/.test(identifier.trim());
}

export function isEmail(identifier: string): boolean {
  return /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(identifier.trim());
}

export function normalizeEmail(email: string): string {
  return email.trim().toLowerCase();
}

export function maskEmail(email: string): string {
  if (!email || !email.includes("@")) return "***@***.***";
  const [local, domain] = email.split("@");
  if (local.length <= 2) {
    return `${local[0]}***@${domain}`;
  }
  return `${local[0]}***${local[local.length - 1]}@${domain}`;
}

export function maskIdentifier(identifier: string): string {
  if (isEmail(identifier)) {
    return maskEmail(identifier);
  }
  const clean = identifier.trim();
  if (clean.length <= 4) return "****";
  return `${clean.slice(0, 2)}****${clean.slice(-2)}`;
}

export function safeLog(action: string, meta: {
  status: number;
  ip?: string;
  identifierType?: "card_id" | "email" | "unknown";
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
