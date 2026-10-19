export interface RegistrationInput {
  card_id: string;
  first_name: string;
  last_name: string;
  birth_date: string;
  gender: string;
  phone: string;
  email: string;
  university: string;
  faculty: string;
  study_level: string;
  wilaya: string;
  password: string;
}

const STUDY_LEVELS = ['L1', 'L2', 'L3', 'M1', 'M2', 'Doctorat'];

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
  if (d.email.trim() && !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(d.email.trim())) errors.push('Email is invalid.');
  if (!d.university.trim()) errors.push('University is required.');
  if (!d.faculty.trim()) errors.push('Faculty is required.');
  if (!STUDY_LEVELS.includes(d.study_level)) errors.push('Study level is invalid.');
  if (!d.wilaya.trim()) errors.push('Wilaya is required.');
  if (d.password.length < 8) errors.push('Password must be at least 8 characters.');
  return errors;
}
