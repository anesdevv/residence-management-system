// web/src/lib/auth-flow.test.ts
import { describe, it, expect } from 'vitest';
import {
  isCardId,
  isEmail,
  normalizeEmail,
  maskEmail,
  validatePassword,
  validateRegistration,
} from './validation';
import {
  calculateCooldown,
  formatProviderRateLimitError,
} from './resend-cooldown';

describe('Auth Validation & Email Formatting', () => {
  it('correctly distinguishes card IDs from emails', () => {
    expect(isCardId('202338012345')).toBe(true);
    expect(isCardId('1234')).toBe(true);
    expect(isCardId('123')).toBe(false);
    expect(isCardId('student@univ-tlemcen.dz')).toBe(false);

    expect(isEmail('student@univ-tlemcen.dz')).toBe(true);
    expect(isEmail('resident.oran@gmail.com')).toBe(true);
    expect(isEmail('not-an-email')).toBe(false);
    expect(isEmail('202338012345')).toBe(false);
  });

  it('normalizes email to lowercase trimmed', () => {
    expect(normalizeEmail('  Mohamed.Benali@Univ-Tlemcen.DZ  ')).toBe('mohamed.benali@univ-tlemcen.dz');
  });

  it('masks emails preserving privacy', () => {
    expect(maskEmail('student@univ-tlemcen.dz')).toBe('s***t@univ-tlemcen.dz');
    expect(maskEmail('ab@domain.com')).toBe('a***@domain.com');
    expect(maskEmail('invalid')).toBe('***@***.***');
    expect(maskEmail('')).toBe('***@***.***');
  });

  it('enforces password rules', () => {
    expect(validatePassword('short')).toContain('Password must be at least 8 characters.');
    expect(validatePassword('validPassword123')).toEqual([]);
  });

  it('strictly rejects synthetic @students.residence.local on registration', () => {
    const validData = {
      card_id: '202338099999',
      first_name: 'Karim',
      last_name: 'Mansouri',
      birth_date: '2003-05-15',
      phone: '0555123456',
      email: 'karim@students.residence.local',
      confirm_email: 'karim@students.residence.local',
      university: 'Université de Tlemcen',
      faculty: 'Sciences',
      study_level: 'L3',
      wilaya: 'Tlemcen',
      password: 'StrongPassword123',
    };

    const errors = validateRegistration(validData);
    expect(errors).toContain('A valid personal or university email address is required.');
  });

  it('validates email confirmation match', () => {
    const data = {
      card_id: '202338099999',
      first_name: 'Karim',
      last_name: 'Mansouri',
      birth_date: '2003-05-15',
      phone: '0555123456',
      email: 'karim@univ-tlemcen.dz',
      confirm_email: 'different@univ-tlemcen.dz',
      university: 'Université de Tlemcen',
      faculty: 'Sciences',
      study_level: 'L3',
      wilaya: 'Tlemcen',
      password: 'StrongPassword123',
    };

    const errors = validateRegistration(data);
    expect(errors).toContain('Email confirmation does not match.');
  });
});

describe('Resend Cooldown & Provider Error Formatting', () => {
  it('allows resend when no prior send has occurred', () => {
    const state = calculateCooldown(null, []);
    expect(state.canResend).toBe(true);
    expect(state.secondsRemaining).toBe(0);
    expect(state.buttonLabel).toBe('Resend code');
  });

  it('enforces 60-second cooldown immediately after a send', () => {
    const now = Date.now();
    const state = calculateCooldown(now - 10000, [now - 10000]); // 10s ago
    expect(state.canResend).toBe(false);
    expect(state.secondsRemaining).toBe(50);
    expect(state.buttonLabel).toBe('Resend in 50s');
  });

  it('enforces 5 sends per hour session cap', () => {
    const now = Date.now();
    // 5 sends within the last 15 minutes, but last send was 70s ago
    const history = [
      now - 900000,
      now - 800000,
      now - 700000,
      now - 600000,
      now - 70000,
    ];
    const state = calculateCooldown(now - 70000, history);
    expect(state.canResend).toBe(false);
    expect(state.isHourlyCapped).toBe(true);
    expect(state.statusText).toContain('Hourly send limit reached');
  });

  it('formats Brevo and Supabase rate limit errors gracefully', () => {
    const brevoDailyError = new Error('SMTP daily quota exceeded: daily email limit reached');
    expect(formatProviderRateLimitError(brevoDailyError)).toContain('daily email limit was reached');

    const supabaseSecurityError = new Error('For security purposes, you can only request this once every 60 seconds');
    expect(formatProviderRateLimitError(supabaseSecurityError)).toContain('security reasons');

    const genericError = new Error('Unexpected connection timeout');
    expect(formatProviderRateLimitError(genericError)).toContain('Unable to send verification code');
  });
});
