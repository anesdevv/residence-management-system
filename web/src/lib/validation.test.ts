// web/src/lib/validation.test.ts
import { describe, it, expect } from 'vitest';
import {
  validateRegistration,
  type RegistrationInput,
  isCardId,
  isEmail,
  normalizeEmail,
  maskEmail,
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

describe('validateRegistration', () => {
  it('accepts a valid input with mandatory real email', () => {
    expect(validateRegistration(base)).toEqual([]);
  });

  it('rejects an empty email', () => {
    expect(validateRegistration({ ...base, email: '' })).toContain('Email address is required.');
  });

  it('rejects a malformed email', () => {
    expect(validateRegistration({ ...base, email: 'nope' })).toContain('Email is invalid.');
  });

  it('rejects synthetic residence.local domain on registration', () => {
    expect(validateRegistration({ ...base, email: '20230001@students.residence.local' }))
      .toContain('A valid personal or university email address is required.');
  });

  it('rejects mismatched email confirmation', () => {
    expect(validateRegistration({ ...base, email: 'student@example.com', confirm_email: 'different@example.com' }))
      .toContain('Email confirmation does not match.');
  });

  it('rejects a short password', () => {
    expect(validateRegistration({ ...base, password: 'short' })).toContain('Password must be at least 8 characters.');
  });

  it('rejects a bad card id', () => {
    expect(validateRegistration({ ...base, card_id: 'abc' })).toContain('Student card ID must be at least 4 digits.');
  });

  it('rejects an invalid study level', () => {
    expect(validateRegistration({ ...base, study_level: 'InvalidLevel' })).toContain('Study level is invalid.');
  });

  it('rejects an invalid birth date format', () => {
    expect(validateRegistration({ ...base, birth_date: '14/05/2003' })).toContain('Birth date must be YYYY-MM-DD.');
  });

  it('rejects an impossible calendar birth date', () => {
    expect(validateRegistration({ ...base, birth_date: '2003-02-31' })).toContain('Birth date is invalid.');
  });

  it('rejects a future birth date', () => {
    expect(validateRegistration({ ...base, birth_date: '2099-01-01' })).toContain('Birth date cannot be in the future.');
  });

  it('rejects missing first or last name', () => {
    const res = validateRegistration({ ...base, first_name: '', last_name: '   ' });
    expect(res).toContain('First name is required.');
    expect(res).toContain('Last name is required.');
  });
});

describe('Helper utilities', () => {
  it('identifies card IDs vs emails', () => {
    expect(isCardId('20230001')).toBe(true);
    expect(isCardId('999')).toBe(false);
    expect(isCardId('abc')).toBe(false);

    expect(isEmail('student@univ-tlemcen.dz')).toBe(true);
    expect(isEmail('notanemail')).toBe(false);
  });

  it('normalizes emails', () => {
    expect(normalizeEmail('  STUDENT@example.COM ')).toBe('student@example.com');
  });

  it('masks emails securely', () => {
    expect(maskEmail('yacine@gmail.com')).toBe('y***e@gmail.com');
    expect(maskEmail('ab@test.dz')).toBe('a***@test.dz');
  });

  it('validates password length', () => {
    expect(validatePassword('1234567')).toContain('Password must be at least 8 characters.');
    expect(validatePassword('12345678')).toEqual([]);
  });
});
