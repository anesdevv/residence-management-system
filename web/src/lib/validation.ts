// web/src/lib/validation.ts

export interface RegistrationInput {
  card_id: string;
  first_name: string;
  last_name: string;
  birth_date: string;
  gender: string;
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

const STUDY_LEVELS = ['L1', 'L2', 'L3', 'M1', 'M2', 'Doctorat'];

export function isCardId(identifier: string): boolean {
  return /^\d{4,}$/.test(identifier.trim());
}

export function isEmail(identifier: string): boolean {
  return /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(identifier.trim());
}

export function normalizeEmail(email: string): string {
  return email.trim().toLowerCase();
}

export function maskEmail(email: string): string {
  if (!email || !email.includes('@')) return '***@***.***';
  const [local, domain] = email.split('@');
  if (local.length <= 2) {
    return `${local[0]}***@${domain}`;
  }
  return `${local[0]}***${local[local.length - 1]}@${domain}`;
}

export function validatePassword(password: string): string[] {
  const errors: string[] = [];
  if (password.length < 8) {
    errors.push('Password must be at least 8 characters.');
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
  if (!['male', 'female'].includes(d.gender)) errors.push('Gender must be male or female.');
  if (!/^[0-9+\s]{6,}$/.test(d.phone)) errors.push('Phone number is invalid.');

  // Email is strictly required and must be a real address
  const cleanEmail = (d.email ?? '').trim();
  if (!cleanEmail) {
    errors.push('Email address is required.');
  } else if (!isEmail(cleanEmail)) {
    errors.push('Email is invalid.');
  } else if (cleanEmail.toLowerCase().endsWith('@students.residence.local')) {
    errors.push('A valid personal or university email address is required.');
  }

  // Confirm email matching
  if (d.confirm_email !== undefined) {
    if (cleanEmail.toLowerCase() !== d.confirm_email.trim().toLowerCase()) {
      errors.push('Email confirmation does not match.');
    }
  }

  if (!d.university.trim()) errors.push('University is required.');
  if (!d.faculty.trim()) errors.push('Faculty is required.');
  if (!STUDY_LEVELS.includes(d.study_level)) errors.push('Study level is invalid.');
  if (!d.wilaya.trim()) errors.push('Wilaya is required.');

  // Password rules
  errors.push(...validatePassword(d.password));

  if (d.confirm_password !== undefined && d.confirm_password !== d.password) {
    errors.push('Password confirmation does not match.');
  }

  return errors;
}
