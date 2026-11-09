// web/src/lib/resend-cooldown.ts

export interface CooldownState {
  canResend: boolean;
  secondsRemaining: number;
  sendsThisHour: number;
  maxSendsPerHour: number;
  isHourlyCapped: boolean;
  statusText: string;
  buttonLabel: string;
}

export const COOLDOWN_SECONDS = 60;
export const MAX_SENDS_PER_HOUR = 5;
export const ONE_HOUR_MS = 60 * 60 * 1000;

/**
 * Pure calculation of cooldown countdown and hourly quota cap.
 */
export function calculateCooldown(
  lastSentTimestamp: number | null,
  historyTimestamps: number[],
  now = Date.now(),
  cooldownSeconds = COOLDOWN_SECONDS,
  maxPerHour = MAX_SENDS_PER_HOUR
): CooldownState {
  const recentHistory = historyTimestamps.filter((t) => now - t < ONE_HOUR_MS);
  const sendsThisHour = recentHistory.length;
  const isHourlyCapped = sendsThisHour >= maxPerHour;

  let secondsRemaining = 0;
  if (lastSentTimestamp !== null) {
    const elapsedSeconds = Math.floor((now - lastSentTimestamp) / 1000);
    if (elapsedSeconds < cooldownSeconds && elapsedSeconds >= 0) {
      secondsRemaining = cooldownSeconds - elapsedSeconds;
    }
  }

  const canResend = !isHourlyCapped && secondsRemaining === 0;

  let statusText = '';
  let buttonLabel = 'Resend code';

  if (isHourlyCapped) {
    const oldestInHour = recentHistory[0] ?? now;
    const minutesToReset = Math.max(1, Math.ceil((ONE_HOUR_MS - (now - oldestInHour)) / (60 * 1000)));
    statusText = `Hourly send limit reached (${maxPerHour}/${maxPerHour}). Try again in ${minutesToReset} minutes.`;
    buttonLabel = 'Hourly limit reached';
  } else if (secondsRemaining > 0) {
    statusText = `Please wait ${secondsRemaining} second${secondsRemaining === 1 ? '' : 's'} before requesting a new code.`;
    buttonLabel = `Resend in ${secondsRemaining}s`;
  } else {
    statusText = sendsThisHour > 0
      ? `You can request another code (${sendsThisHour}/${maxPerHour} sent this hour).`
      : 'You can request a new code.';
    buttonLabel = 'Resend code';
  }

  return {
    canResend,
    secondsRemaining,
    sendsThisHour,
    maxSendsPerHour: maxPerHour,
    isHourlyCapped,
    statusText,
    buttonLabel,
  };
}

/**
 * Formats rate-limiting and provider quota errors into user-friendly messages.
 */
export function formatProviderRateLimitError(err: unknown): string {
  const msg = (err instanceof Error ? err.message : String(err ?? '')).toLowerCase();
  if (
    msg.includes('rate limit') ||
    msg.includes('over_email_send_rate_limit') ||
    msg.includes('429') ||
    msg.includes('daily limit') ||
    msg.includes('quota')
  ) {
    return 'The daily email limit was reached or the delivery service is busy. Please check your spam folder or try again tomorrow.';
  }
  if (msg.includes('security purposes') || msg.includes('once every')) {
    return 'For security reasons, please wait before requesting another code.';
  }
  return 'Unable to send verification code. Please check your connection and try again.';
}
