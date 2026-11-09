// supabase/functions/_shared/throttler.ts

interface AttemptRecord {
  timestamps: number[];
}

const attemptsMap = new Map<string, AttemptRecord>();

const WINDOW_MS = 10 * 60 * 1000; // 10 minutes
const MAX_ATTEMPTS = 10;

/**
 * Clean up entries older than 2 * WINDOW_MS to prevent memory growth
 */
function cleanup() {
  const now = Date.now();
  for (const [key, record] of attemptsMap.entries()) {
    const valid = record.timestamps.filter((t) => now - t < WINDOW_MS);
    if (valid.length === 0) {
      attemptsMap.delete(key);
    } else {
      record.timestamps = valid;
    }
  }
}

let lastCleanup = Date.now();

export function checkRateLimit(key: string, limit = MAX_ATTEMPTS, windowMs = WINDOW_MS): {
  allowed: boolean;
  retryAfterSeconds: number;
} {
  const now = Date.now();

  if (now - lastCleanup > 60 * 1000) {
    cleanup();
    lastCleanup = now;
  }

  const record = attemptsMap.get(key) ?? { timestamps: [] };
  const validTimestamps = record.timestamps.filter((t) => now - t < windowMs);

  if (validTimestamps.length >= limit) {
    const oldest = validTimestamps[0];
    const retryAfterSeconds = Math.max(1, Math.ceil((windowMs - (now - oldest)) / 1000));
    return { allowed: false, retryAfterSeconds };
  }

  validTimestamps.push(now);
  attemptsMap.set(key, { timestamps: validTimestamps });

  return { allowed: true, retryAfterSeconds: 0 };
}

export function getClientIp(req: Request): string {
  const forwarded = req.headers.get("x-forwarded-for");
  if (forwarded) {
    return forwarded.split(",")[0].trim();
  }
  return req.headers.get("cf-connecting-ip") ?? req.headers.get("x-real-ip") ?? "unknown-ip";
}
