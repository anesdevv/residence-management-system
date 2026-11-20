import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  getTurnstileSiteKey,
  getTurnstileSecretKey,
  verifyTurnstileToken,
  TURNSTILE_TEST_SITE_KEY,
  TURNSTILE_TEST_SECRET_KEY,
  TURNSTILE_VERIFY_URL,
} from './turnstile';

describe('Cloudflare Turnstile verification', () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
    delete process.env.TURNSTILE_ENABLED;
    delete process.env.TURNSTILE_STRICT;
    delete process.env.PUBLIC_TURNSTILE_SITE_KEY;
    delete process.env.TURNSTILE_SECRET_KEY;
  });

  it('provides default test keys when env vars are missing', () => {
    expect(getTurnstileSiteKey()).toBe(TURNSTILE_TEST_SITE_KEY);
    expect(getTurnstileSecretKey()).toBe(TURNSTILE_TEST_SECRET_KEY);
  });

  it('reads custom site key and secret key from environment', () => {
    process.env.PUBLIC_TURNSTILE_SITE_KEY = '0x4AAAAAAtestkey';
    process.env.TURNSTILE_SECRET_KEY = '0x4AAAAAAtestsecret';

    expect(getTurnstileSiteKey()).toBe('0x4AAAAAAtestkey');
    expect(getTurnstileSecretKey()).toBe('0x4AAAAAAtestsecret');
  });

  it('fails verification when token is missing in strict mode', async () => {
    process.env.TURNSTILE_STRICT = 'true';
    const result = await verifyTurnstileToken('');
    expect(result.success).toBe(false);
    expect(result.errorCodes).toContain('missing-input-response');
  });

  it('bypasses verification when TURNSTILE_ENABLED is false', async () => {
    process.env.TURNSTILE_ENABLED = 'false';
    const result = await verifyTurnstileToken('');
    expect(result.success).toBe(true);
  });

  it('verifies a valid token against Cloudflare siteverify endpoint', async () => {
    process.env.TURNSTILE_STRICT = 'true';
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        success: true,
        challenge_ts: '2026-11-20T12:00:00Z',
        hostname: 'resivo-orcin.vercel.app',
        action: 'login',
        'error-codes': [],
      }),
    });

    const result = await verifyTurnstileToken('valid-token-123', '192.168.1.1');
    expect(result.success).toBe(true);
    expect(result.hostname).toBe('resivo-orcin.vercel.app');
    expect(result.action).toBe('login');
    expect(globalThis.fetch).toHaveBeenCalledWith(
      TURNSTILE_VERIFY_URL,
      expect.objectContaining({
        method: 'POST',
      }),
    );
  });

  it('returns failure when Cloudflare rejects the token', async () => {
    process.env.TURNSTILE_STRICT = 'true';
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        success: false,
        'error-codes': ['invalid-input-response'],
      }),
    });

    const result = await verifyTurnstileToken('invalid-token');
    expect(result.success).toBe(false);
    expect(result.errorCodes).toContain('invalid-input-response');
  });

  it('handles network or fetch errors gracefully', async () => {
    process.env.TURNSTILE_STRICT = 'true';
    globalThis.fetch = vi.fn().mockRejectedValue(new Error('Cloudflare network unreachable'));

    const result = await verifyTurnstileToken('some-token');
    expect(result.success).toBe(false);
    expect(result.errorCodes).toContain('internal-error');
  });
});
