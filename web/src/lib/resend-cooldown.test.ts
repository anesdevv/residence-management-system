// web/src/lib/resend-cooldown.test.ts
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  calculateCooldown,
  formatProviderRateLimitError,
  COOLDOWN_SECONDS,
  MAX_SENDS_PER_HOUR,
} from './resend-cooldown';

describe('calculateCooldown', () => {
  const baseTime = 1700000000000;

  it('allows resending initially when no sends have occurred', () => {
    const res = calculateCooldown(null, [], baseTime);
    expect(res.canResend).toBe(true);
    expect(res.secondsRemaining).toBe(0);
    expect(res.sendsThisHour).toBe(0);
    expect(res.isHourlyCapped).toBe(false);
    expect(res.buttonLabel).toBe('Resend code');
  });

  it('enforces 60-second cooldown after a send', () => {
    const lastSent = baseTime - 20 * 1000; // 20s ago
    const res = calculateCooldown(lastSent, [lastSent], baseTime);
    expect(res.canResend).toBe(false);
    expect(res.secondsRemaining).toBe(40);
    expect(res.buttonLabel).toBe('Resend in 40s');
    expect(res.statusText).toContain('Please wait 40 seconds');
  });

  it('allows resending once the 60-second cooldown expires', () => {
    const lastSent = baseTime - 61 * 1000; // 61s ago
    const res = calculateCooldown(lastSent, [lastSent], baseTime);
    expect(res.canResend).toBe(true);
    expect(res.secondsRemaining).toBe(0);
    expect(res.buttonLabel).toBe('Resend code');
  });

  it('enforces the 5 sends per hour cap', () => {
    const history = [
      baseTime - 50 * 60 * 1000,
      baseTime - 40 * 60 * 1000,
      baseTime - 30 * 60 * 1000,
      baseTime - 20 * 60 * 1000,
      baseTime - 10 * 60 * 1000, // 5th send, 10 min ago (> 60s cooldown passed)
    ];
    const lastSent = history[history.length - 1];

    const res = calculateCooldown(lastSent, history, baseTime);
    expect(res.isHourlyCapped).toBe(true);
    expect(res.canResend).toBe(false);
    expect(res.sendsThisHour).toBe(5);
    expect(res.buttonLabel).toBe('Hourly limit reached');
    expect(res.statusText).toContain('Hourly send limit reached (5/5)');
  });

  it('drops timestamps older than 1 hour from the hourly quota', () => {
    const history = [
      baseTime - 65 * 60 * 1000, // 65 min ago (> 1 hour old)
      baseTime - 40 * 60 * 1000,
      baseTime - 30 * 60 * 1000,
      baseTime - 20 * 60 * 1000,
      baseTime - 10 * 60 * 1000,
    ];
    const lastSent = history[history.length - 1];

    const res = calculateCooldown(lastSent, history, baseTime);
    // Only 4 are within the last hour
    expect(res.sendsThisHour).toBe(4);
    expect(res.isHourlyCapped).toBe(false);
    expect(res.canResend).toBe(true);
  });
});

describe('formatProviderRateLimitError', () => {
  it('formats over_email_send_rate_limit friendly message', () => {
    const msg = formatProviderRateLimitError(new Error('over_email_send_rate_limit: rate limit exceeded'));
    expect(msg).toContain('The daily email limit was reached');
  });

  it('formats HTTP 429 errors', () => {
    const msg = formatProviderRateLimitError('Request failed with status code 429');
    expect(msg).toContain('The daily email limit was reached');
  });

  it('falls back to generic network message for other errors', () => {
    const msg = formatProviderRateLimitError(new Error('Failed to fetch'));
    expect(msg).toContain('Unable to send verification code');
  });
});
