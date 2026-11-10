import { describe, it, expect, vi } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';
import en from '../i18n/en.json';
import fr from '../i18n/fr.json';
import {
  DEFAULT_RESIDENCE_NAME,
  checkRegistrationGate,
  getResidencePublic,
  isRegistrationOpen,
  normalizeResidencePublic,
  residenceHeaderLabel,
} from './residence';
import { validateRegistration } from './validation';

function flattenKeys(obj: Record<string, unknown>, prefix = ''): string[] {
  const keys: string[] = [];
  for (const [k, v] of Object.entries(obj)) {
    const full = prefix ? `${prefix}.${k}` : k;
    if (v && typeof v === 'object' && !Array.isArray(v)) {
      keys.push(...flattenKeys(v as Record<string, unknown>, full));
    } else {
      keys.push(full);
    }
  }
  return keys;
}

describe('Single-gender residence helpers', () => {
  it('normalizes configured residence payload cleanly', () => {
    const res = normalizeResidencePublic({
      residence_name: 'Cité Universitaire Benboulaid',
      residence_gender: 'female',
    });
    expect(res).toEqual({
      residenceName: 'Cité Universitaire Benboulaid',
      residenceGender: 'female',
      loaded: true,
    });
    expect(isRegistrationOpen(res)).toBe(true);
    expect(residenceHeaderLabel('en', res)).toBe('Registration for the female residence');
    expect(residenceHeaderLabel('fr', res)).toBe('Inscription pour la résidence féminine');
    expect(checkRegistrationGate(res, 'en')).toBeNull();
  });

  it('blocks registration when residence_gender is null', async () => {
    const mockSupabase = {
      rpc: vi.fn().mockResolvedValue({
        data: { residence_name: DEFAULT_RESIDENCE_NAME, residence_gender: null },
        error: null,
      }),
    };

    const res = await getResidencePublic(mockSupabase);
    expect(res.loaded).toBe(true);
    expect(res.residenceGender).toBeNull();
    expect(isRegistrationOpen(res)).toBe(false);
    expect(checkRegistrationGate(res, 'en')).toBe('Registration is not open yet');
    expect(checkRegistrationGate(res, 'fr')).toBe('Les inscriptions ne sont pas encore ouvertes');
    expect(residenceHeaderLabel('en', res)).toBe('Registration is not open yet');
  });

  it('degrades gracefully when get_residence_public fails', async () => {
    const mockSupabase = {
      rpc: vi.fn().mockResolvedValue({ data: null, error: { message: 'timeout' } }),
    };

    const res = await getResidencePublic(mockSupabase);
    expect(res).toEqual({
      residenceName: DEFAULT_RESIDENCE_NAME,
      residenceGender: null,
      loaded: false,
    });
    expect(isRegistrationOpen(res)).toBe(false);
    expect(checkRegistrationGate(res, 'en')).toBeNull();
  });

  it('accepts registration payloads without any gender field', () => {
    const errors = validateRegistration({
      card_id: '202438011223',
      first_name: 'Amira',
      last_name: 'Khelifi',
      birth_date: '2004-03-11',
      phone: '0550123456',
      email: 'amira.khelifi@univ-tlemcen.dz',
      confirm_email: 'amira.khelifi@univ-tlemcen.dz',
      university: 'Université Abou Bekr Belkaïd',
      faculty: 'Sciences',
      study_level: 'L2',
      wilaya: 'Tlemcen',
      password: 'Password123!',
    });
    expect(errors).toEqual([]);
  });
});

describe('Single-gender portal source & i18n contracts', () => {
  it('keeps 100% key parity between en.json and fr.json', () => {
    const enKeys = new Set(flattenKeys(en));
    const frKeys = new Set(flattenKeys(fr));
    expect([...enKeys].filter((k) => !frKeys.has(k))).toEqual([]);
    expect([...frKeys].filter((k) => !enKeys.has(k))).toEqual([]);
  });

  it('removes gender inputs and room-gender filters from registration and room-change portal code', () => {
    const srcDir = path.resolve(import.meta.dirname, '..');
    const registerAstro = fs.readFileSync(path.join(srcDir, 'pages/register.astro'), 'utf8');
    const registerApi = fs.readFileSync(path.join(srcDir, 'pages/api/register.ts'), 'utf8');
    const roomChangeAstro = fs.readFileSync(path.join(srcDir, 'pages/dashboard/room-change.astro'), 'utf8');
    const roomChangeApi = fs.readFileSync(path.join(srcDir, 'pages/api/room-change.ts'), 'utf8');
    const dashboardAstro = fs.readFileSync(path.join(srcDir, 'pages/dashboard/index.astro'), 'utf8');
    const passAstro = fs.readFileSync(path.join(srcDir, 'components/ResidentPass.astro'), 'utf8');

    expect(registerAstro).not.toContain('name="gender"');
    expect(registerAstro).not.toContain('Bloc Garçons');
    expect(registerAstro).not.toContain('Bloc Filles');
    expect(registerApi).not.toContain("form.get('gender')");
    expect(registerApi).toContain('getResidencePublic');

    expect(roomChangeAstro).not.toContain(".eq('gender'");
    expect(roomChangeApi).not.toContain('targetRoom.gender');
    expect(dashboardAstro).not.toContain('gender');
    expect(passAstro).not.toContain('gender');
  });
});
