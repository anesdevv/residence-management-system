// web/src/lib/validation.test.ts
import { describe, it, expect } from 'vitest';
import {
  MAX_EMAIL_LENGTH,
  validateRegistration,
  validateContactEmailPair,
  validateContactUpdate,
  mapEmailErrorCode,
  type RegistrationInput,
  isCardId,
  isEmail,
  normalizeEmail,
  validatePassword,
} from './validation';

const base: RegistrationInput = {
  card_id: '20230001',
  first_name: 'Yacine',
  last_name: 'Benali',
  birth_date: '2003-05-14',
  phone: '0550000001',
  email: 'yacine.benali@univ-tlemcen.dz',
  confirm_email: 'yacine.benali@univ-tlemcen.dz',
  university: 'Abou Bekr Belkaid',
  faculty: 'Sciences',
  study_level: 'L2',
  wilaya: 'Tlemcen',
  password: 'Student1234!',
};

describe('Email validation, normalization & error mapping', () => {
  it('normalizes emails by trimming and lowercasing', () => {
    expect(normalizeEmail('  STUDENT.Name@Univ-Tlemcen.DZ  ')).toBe('student.name@univ-tlemcen.dz');
  });

  it('validates email format and enforces max length of 254 characters', () => {
    expect(isEmail('student@univ-tlemcen.dz')).toBe(true);
    expect(isEmail('  first.last+tag@sub.domain.dz  ')).toBe(true);
    expect(isEmail('nope')).toBe(false);
    expect(isEmail('user@domain')).toBe(false);
    expect(isEmail('user@domain..com')).toBe(false);
    expect(isEmail('user@.domain.com')).toBe(false);
    expect(isEmail('user name@domain.com')).toBe(false);

    const domain = '@example.com';
    const ok254 = `${'a'.repeat(MAX_EMAIL_LENGTH - domain.length)}${domain}`;
    const tooLong255 = `${'a'.repeat(MAX_EMAIL_LENGTH + 1 - domain.length)}${domain}`;
    expect(ok254.length).toBe(254);
    expect(tooLong255.length).toBe(255);
    expect(isEmail(ok254)).toBe(true);
    expect(isEmail(tooLong255)).toBe(false);
  });

  it('validates email + confirm_email pair (required, format, domain, case-insensitive match)', () => {
    expect(validateContactEmailPair('', '')).toEqual({
      ok: false,
      code: 'email_required',
      message: 'Email address is required.',
    });

    expect(validateContactEmailPair('bad-email', 'bad-email')).toEqual({
      ok: false,
      code: 'email_invalid',
      message: 'Please enter a valid contact email address.',
    });

    expect(
      validateContactEmailPair('20230001@students.residence.local', '20230001@students.residence.local'),
    ).toEqual({
      ok: false,
      code: 'email_invalid',
      message: 'Please enter a valid contact email address.',
    });

    expect(validateContactEmailPair('alice@univ-tlemcen.dz', 'bob@univ-tlemcen.dz')).toEqual({
      ok: false,
      code: 'email_mismatch',
      message: 'The emails do not match',
    });

    expect(
      validateContactEmailPair('  Alice.Benali@Univ-Tlemcen.DZ ', 'alice.benali@univ-tlemcen.dz'),
    ).toEqual({
      ok: true,
      email: 'alice.benali@univ-tlemcen.dz',
    });
  });

  it('maps backend error codes and constraints to friendly EN and FR messages', () => {
    expect(mapEmailErrorCode('email_in_use', 'en')).toContain('already registered');
    expect(mapEmailErrorCode('email_in_use: duplicate', 'fr')).toContain('déjà utilisée');
    expect(mapEmailErrorCode('duplicate key value violates unique constraint "idx_students_unique_lower_email"', 'en')).toContain('already registered');
    expect(mapEmailErrorCode('email_invalid', 'en')).toContain('valid contact email');
    expect(mapEmailErrorCode('email_invalid', 'fr')).toContain('adresse e-mail de contact valide');
    expect(mapEmailErrorCode('email_mismatch', 'en')).toBe('The emails do not match');
    expect(mapEmailErrorCode('email_mismatch', 'fr')).toBe('Les adresses e-mail ne correspondent pas.');
    expect(mapEmailErrorCode('email_required', 'en')).toBe('Email address is required.');
  });
});

describe('validateRegistration', () => {
  it('accepts a valid input with normalized matching contact email', () => {
    expect(validateRegistration(base)).toEqual([]);
    expect(
      validateRegistration({
        ...base,
        email: '  Yacine.Benali@Univ-Tlemcen.DZ ',
        confirm_email: 'yacine.benali@univ-tlemcen.dz',
      }),
    ).toEqual([]);
  });

  it('rejects an empty email', () => {
    expect(validateRegistration({ ...base, email: '' })).toContain('Email address is required.');
  });

  it('rejects a malformed or oversized email', () => {
    expect(validateRegistration({ ...base, email: 'nope', confirm_email: 'nope' })).toContain(
      'Please enter a valid contact email address.',
    );
    const tooLong = `${'a'.repeat(250)}@b.dz`;
    expect(validateRegistration({ ...base, email: tooLong, confirm_email: tooLong })).toContain(
      'Please enter a valid contact email address.',
    );
  });

  it('rejects synthetic residence.local domain on registration', () => {
    expect(
      validateRegistration({
        ...base,
        email: '20230001@students.residence.local',
        confirm_email: '20230001@students.residence.local',
      }),
    ).toContain('Please enter a valid contact email address.');
  });

  it('rejects mismatched email confirmation with "The emails do not match"', () => {
    expect(
      validateRegistration({
        ...base,
        email: 'student@example.com',
        confirm_email: 'different@example.com',
      }),
    ).toContain('The emails do not match');
  });

  it('rejects a short password', () => {
    expect(validateRegistration({ ...base, password: 'short' })).toContain(
      'Password must be at least 8 characters.',
    );
  });

  it('rejects a bad card id', () => {
    expect(validateRegistration({ ...base, card_id: 'abc' })).toContain(
      'Student card ID must be at least 4 digits.',
    );
  });

  it('rejects an invalid study level', () => {
    expect(validateRegistration({ ...base, study_level: 'InvalidLevel' })).toContain(
      'Study level is invalid.',
    );
  });

  it('rejects an invalid birth date format and impossible/future dates', () => {
    expect(validateRegistration({ ...base, birth_date: '14/05/2003' })).toContain(
      'Birth date must be YYYY-MM-DD.',
    );
    expect(validateRegistration({ ...base, birth_date: '2003-02-31' })).toContain(
      'Birth date is invalid.',
    );
    expect(validateRegistration({ ...base, birth_date: '2099-01-01' })).toContain(
      'Birth date cannot be in the future.',
    );
  });

  it('rejects missing first or last name', () => {
    const res = validateRegistration({ ...base, first_name: '', last_name: '   ' });
    expect(res).toContain('First name is required.');
    expect(res).toContain('Last name is required.');
  });
});

describe('validateContactUpdate & helpers', () => {
  it('validates phone and matching contact email on profile update', () => {
    expect(validateContactUpdate('0555123456', 'new@univ-tlemcen.dz', 'NEW@univ-tlemcen.dz')).toEqual([]);
    expect(validateContactUpdate('123', 'new@univ-tlemcen.dz', 'new@univ-tlemcen.dz').length).toBeGreaterThan(0);
    expect(validateContactUpdate('0555123456', 'a@univ-tlemcen.dz', 'b@univ-tlemcen.dz')).toContain(
      'The emails do not match',
    );
  });

  it('identifies card IDs and validates password length', () => {
    expect(isCardId('20230001')).toBe(true);
    expect(isCardId('999')).toBe(false);
    expect(isCardId('abc')).toBe(false);
    expect(validatePassword('1234567')).toContain('Password must be at least 8 characters.');
    expect(validatePassword('12345678')).toEqual([]);
  });
});
