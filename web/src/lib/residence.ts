/**
 * Shared public residence configuration helpers for SSR pages and API routes.
 */
import { t, type SupportedLocale } from './i18n';

export const DEFAULT_RESIDENCE_NAME = 'Cité Universitaire · Tlemcen';

export type ResidenceGender = 'male' | 'female';

export interface ResidencePublic {
  residenceName: string;
  residenceGender: ResidenceGender | null;
  loaded: boolean;
}

export function normalizeResidencePublic(raw: unknown): ResidencePublic {
  const row = Array.isArray(raw) ? raw[0] : raw;
  if (!row || typeof row !== 'object') {
    return {
      residenceName: DEFAULT_RESIDENCE_NAME,
      residenceGender: null,
      loaded: false,
    };
  }
  const obj = row as Record<string, unknown>;
  const rawName = typeof obj.residence_name === 'string' ? obj.residence_name.trim() : '';
  const rawGender = typeof obj.residence_gender === 'string' ? obj.residence_gender.trim().toLowerCase() : '';
  const residenceGender: ResidenceGender | null =
    rawGender === 'male' || rawGender === 'female' ? rawGender : null;

  return {
    residenceName: rawName || DEFAULT_RESIDENCE_NAME,
    residenceGender,
    loaded: 'residence_gender' in obj,
  };
}

export function isRegistrationOpen(residence: ResidencePublic): boolean {
  return residence.residenceGender === 'male' || residence.residenceGender === 'female';
}

export function residenceHeaderLabel(locale: SupportedLocale, residence: ResidencePublic): string {
  if (residence.residenceGender === 'male') {
    return t(locale, 'auth.register_for_male');
  }
  if (residence.residenceGender === 'female') {
    return t(locale, 'auth.register_for_female');
  }
  return t(locale, 'auth.registration_closed_title');
}

export async function getResidencePublic(supabase: any): Promise<ResidencePublic> {
  if (!supabase || typeof supabase.rpc !== 'function') {
    return {
      residenceName: DEFAULT_RESIDENCE_NAME,
      residenceGender: null,
      loaded: false,
    };
  }
  try {
    const { data, error } = await supabase.rpc('get_residence_public');
    if (error || !data) {
      return {
        residenceName: DEFAULT_RESIDENCE_NAME,
        residenceGender: null,
        loaded: false,
      };
    }
    return normalizeResidencePublic(data);
  } catch {
    return {
      residenceName: DEFAULT_RESIDENCE_NAME,
      residenceGender: null,
      loaded: false,
    };
  }
}

export function checkRegistrationGate(
  residence: ResidencePublic,
  locale: SupportedLocale = 'en',
): string | null {
  if (residence.loaded && !isRegistrationOpen(residence)) {
    return t(locale, 'auth.registration_closed_title');
  }
  return null;
}
