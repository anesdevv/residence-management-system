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
});
