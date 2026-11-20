/**
 * Cloudflare Turnstile bot verification helper for RÉSIVO.
 *
 * Provides client and server utilities to verify CAPTCHA/Turnstile response tokens
 * against Cloudflare's siteverify endpoint.
 *
 * Cloudflare Turnstile Testing Keys:
 * - Always passes sitekey: '1x00000000000000000000AA'
 * - Always passes secret:  '1x0000000000000000000000000000000AA'
 */

export const TURNSTILE_TEST_SITE_KEY = '1x00000000000000000000AA';
export const TURNSTILE_TEST_SECRET_KEY = '1x0000000000000000000000000000000AA';

export const TURNSTILE_VERIFY_URL = 'https://challenges.cloudflare.com/turnstile/v0/siteverify';

export interface TurnstileVerifyResult {
  success: boolean;
  errorCodes?: string[];
  challengeTs?: string;
  hostname?: string;
  action?: string;
  cdata?: string;
}

/**
 * Get the public Turnstile site key for client-side rendering.
 */
export function getTurnstileSiteKey(): string {
  const envKey =
    typeof import.meta !== 'undefined' && import.meta.env?.PUBLIC_TURNSTILE_SITE_KEY
      ? import.meta.env.PUBLIC_TURNSTILE_SITE_KEY
      : typeof process !== 'undefined'
        ? process.env.PUBLIC_TURNSTILE_SITE_KEY
        : undefined;

  return envKey?.trim() || TURNSTILE_TEST_SITE_KEY;
}

/**
 * Get the secret Turnstile key for server-side verification.
 */
export function getTurnstileSecretKey(): string {
  const envSecret =
    typeof import.meta !== 'undefined' && import.meta.env?.TURNSTILE_SECRET_KEY
      ? import.meta.env.TURNSTILE_SECRET_KEY
      : typeof process !== 'undefined'
        ? process.env.TURNSTILE_SECRET_KEY
        : undefined;

  return envSecret?.trim() || TURNSTILE_TEST_SECRET_KEY;
}

/**
 * Verify a Turnstile response token with Cloudflare's siteverify API.
 *
 * @param token The token from formData ('cf-turnstile-response')
 * @param remoteIp Optional client IP address
 */
export async function verifyTurnstileToken(
  token: string | null | undefined,
  remoteIp?: string | null,
): Promise<TurnstileVerifyResult> {
  // If explicitly disabled via env var (e.g. for specific CI environments)
  const isExplicitlyDisabled =
    (typeof process !== 'undefined' && process.env.TURNSTILE_ENABLED === 'false') ||
    (typeof import.meta !== 'undefined' && import.meta.env?.TURNSTILE_ENABLED === 'false');

  if (isExplicitlyDisabled) {
    return { success: true };
  }

  // In test environment, bypass only when no token is provided and strict mode is off
  const isTest =
    (typeof process !== 'undefined' && process.env.NODE_ENV === 'test') ||
    (typeof import.meta !== 'undefined' && import.meta.env?.MODE === 'test');

  const isStrict = typeof process !== 'undefined' && process.env.TURNSTILE_STRICT === 'true';

  if (isTest && !isStrict && !token) {
    return { success: true };
  }

  const cleanToken = token?.trim();
  if (!cleanToken) {
    return {
      success: false,
      errorCodes: ['missing-input-response'],
    };
  }

  const secretKey = getTurnstileSecretKey();

  try {
    const formData = new URLSearchParams();
    formData.append('secret', secretKey);
    formData.append('response', cleanToken);
    if (remoteIp?.trim()) {
      formData.append('remoteip', remoteIp.trim());
    }

    const res = await fetch(TURNSTILE_VERIFY_URL, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body: formData,
    });

    if (!res.ok) {
      return {
        success: false,
        errorCodes: [`http-status-${res.status}`],
      };
    }

    const data = (await res.json()) as {
      success: boolean;
      'error-codes'?: string[];
      challenge_ts?: string;
      hostname?: string;
      action?: string;
      cdata?: string;
    };

    return {
      success: Boolean(data.success),
      errorCodes: data['error-codes'] || [],
      challengeTs: data.challenge_ts,
      hostname: data.hostname,
      action: data.action,
      cdata: data.cdata,
    };
  } catch (err: any) {
    // Return failed verification on network or parsing error
    return {
      success: false,
      errorCodes: ['internal-error', err?.message || 'unknown-error'],
    };
  }
}
