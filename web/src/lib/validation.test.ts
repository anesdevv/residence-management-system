import { describe, it, expect } from 'vitest';
import { validateRegistration, type RegistrationInput } from './validation';

const base: RegistrationInput = {
  card_id: '20230001', first_name: 'Yacine', last_name: 'Benali',
  birth_date: '2003-05-14', gender: 'male', phone: '0550000001', email: '',
  university: 'Abou Bekr Belkaid', faculty: 'Sciences', study_level: 'L2',
  wilaya: 'Tlemcen', password: 'Student1234!',
};

describe('validateRegistration', () => {
  it('accepts a valid input', () => {
    expect(validateRegistration(base)).toEqual([]);
  });
  it('rejects a short password', () => {
    expect(validateRegistration({ ...base, password: 'short' })).toContain('Password must be at least 8 characters.');
  });
  it('rejects a bad card id', () => {
    expect(validateRegistration({ ...base, card_id: 'abc' })).toContain('Student card ID must be at least 4 digits.');
  });
  it('rejects a bad email when provided', () => {
    expect(validateRegistration({ ...base, email: 'nope' })).toContain('Email is invalid.');
  });
  it('rejects an invalid study level', () => {
    expect(validateRegistration({ ...base, study_level: 'InvalidLevel' })).toContain('Study level is invalid.');
  });
  it('rejects an invalid gender', () => {
    expect(validateRegistration({ ...base, gender: 'other' })).toContain('Gender must be male or female.');
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

