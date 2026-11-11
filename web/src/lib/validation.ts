// web/src/lib/validation.ts
import { t, type SupportedLocale } from './i18n';

export const MAX_EMAIL_LENGTH = 254;

export interface RegistrationInput {
  card_id: string;
  first_name: string;
  last_name: string;
  birth_date: string;
  phone: string;
  email: string;
  confirm_email?: string;
  university: string;
  faculty: string;
  study_level: string;
  wilaya: string;
  password: string;
  confirm_password?: string;
}

export type EmailErrorCode =
  | 'email_required'
  | 'email_invalid'
  | 'email_mismatch'
  | 'email_in_use';

export type EmailValidationResult =
  | { ok: true; email: string }
  | { ok: false; code: EmailErrorCode; message: string };

const STUDY_LEVELS = ['L1', 'L2', 'L3', 'M1', 'M2', 'Doctorat'];

export function isCardId(identifier: string): boolean {
  return /^\d{4,}$/.test(identifier.trim());
}

export function normalizeEmail(email: string): string {
  return email.trim().toLowerCase();
}

export function isEmail(identifier: string): boolean {
  const clean = normalizeEmail(identifier);
  if (!clean || clean.length > MAX_EMAIL_LENGTH) return false;
  if (/\s/.test(clean) || !/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(clean)) return false;
  const domain = clean.split('@')[1] ?? '';
  if (!domain || domain.includes('..') || domain.startsWith('.') || domain.endsWith('.')) {
    return false;
  }
  return true;
}

export function validateContactEmailPair(
  email: string,
  confirmEmail?: string,
  locale: SupportedLocale = 'en',
): EmailValidationResult {
  const normalized = normalizeEmail(email ?? '');
  if (!normalized) {
    return {
      ok: false,
      code: 'email_required',
      message: t(locale, 'errors.email_required'),
    };
  }
  if (!isEmail(normalized) || normalized.endsWith('@students.residence.local')) {
    return {
      ok: false,
      code: 'email_invalid',
      message: t(locale, 'errors.email_invalid'),
    };
  }
  if (confirmEmail !== undefined && normalized !== normalizeEmail(confirmEmail ?? '')) {
    return {
      ok: false,
      code: 'email_mismatch',
      message: t(locale, 'errors.email_mismatch'),
    };
  }
  return { ok: true, email: normalized };
}

export function mapEmailErrorCode(
  codeOrMessage: string,
  locale: SupportedLocale = 'en',
): string {
  const raw = (codeOrMessage ?? '').trim();
  const lower = raw.toLowerCase();

  if (
    lower === 'email_in_use' ||
    lower.includes('email_in_use:') ||
    lower.includes('idx_students_unique_lower_email') ||
    lower.includes('already registered') ||
    lower.includes('already exists') ||
    lower.includes('23505')
  ) {
    return t(locale, 'errors.email_in_use');
  }
  if (lower === 'email_mismatch' || lower.includes('email_mismatch:') || lower.includes('do not match')) {
    return t(locale, 'errors.email_mismatch');
  }
  if (lower === 'email_required' || lower.includes('email_required:')) {
    return t(locale, 'errors.email_required');
  }
  if (lower === 'email_invalid' || lower.includes('email_invalid:') || lower.includes('invalid email')) {
    return t(locale, 'errors.email_invalid');
  }

  return raw || t(locale, 'errors.generic');
}

export function validatePassword(password: string): string[] {
  const errors: string[] = [];
  if (password.length < 8) {
    errors.push('Password must be at least 8 characters.');
  }
  return errors;
}

export function validateContactUpdate(
  phone: string,
  email: string,
  confirmEmail?: string,
  locale: SupportedLocale = 'en',
): string[] {
  const errors: string[] = [];
  if (!/^[0-9+\s]{6,}$/.test((phone ?? '').trim())) {
    errors.push(t(locale, 'errors.invalid_phone'));
  }
  const emailRes = validateContactEmailPair(email, confirmEmail, locale);
  if (!emailRes.ok) {
    errors.push(emailRes.message);
  }
  return errors;
}

export function validateRegistration(d: RegistrationInput): string[] {
  const errors: string[] = [];
  if (!/^\d{4,}$/.test(d.card_id.trim())) errors.push('Student card ID must be at least 4 digits.');
  if (!d.first_name.trim()) errors.push('First name is required.');
  if (!d.last_name.trim()) errors.push('Last name is required.');
  if (!/^\d{4}-\d{2}-\d{2}$/.test(d.birth_date)) {
    errors.push('Birth date must be YYYY-MM-DD.');
  } else {
    const [year, month, day] = d.birth_date.split('-').map(Number);
    const parsed = new Date(Date.UTC(year, month - 1, day));
    if (
      isNaN(parsed.getTime()) ||
      parsed.getUTCFullYear() !== year ||
      parsed.getUTCMonth() + 1 !== month ||
      parsed.getUTCDate() !== day
    ) {
      errors.push('Birth date is invalid.');
    } else if (parsed > new Date()) {
      errors.push('Birth date cannot be in the future.');
    }
  }
  if (!/^[0-9+\s]{6,}$/.test(d.phone)) errors.push('Phone number is invalid.');

  const emailRes = validateContactEmailPair(d.email, d.confirm_email, 'en');
  if (!emailRes.ok) {
    errors.push(emailRes.message);
  }

  if (!d.university.trim()) errors.push('University is required.');
  if (!d.faculty.trim()) errors.push('Faculty is required.');
  if (!STUDY_LEVELS.includes(d.study_level)) errors.push('Study level is invalid.');
  if (!d.wilaya.trim()) errors.push('Wilaya is required.');

  errors.push(...validatePassword(d.password));

  if (d.confirm_password !== undefined && d.confirm_password !== d.password) {
    errors.push('Password confirmation does not match.');
  }

  return errors;
}
