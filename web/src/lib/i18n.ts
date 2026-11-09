/**
 * RÉSIVO — i18n helper library (Phase 4).
 * Pure TypeScript, zero external dependencies, leveraging native Intl API.
 */
import en from '../i18n/en.json';
import fr from '../i18n/fr.json';

export type SupportedLocale = 'en' | 'fr';
export const DEFAULT_LOCALE: SupportedLocale = 'en';
export const LOCALES: readonly SupportedLocale[] = ['en', 'fr'] as const;

export const translations: Record<SupportedLocale, Record<string, any>> = {
  en,
  fr,
};

/**
 * Normalizes input locale string into supported locale ('en' | 'fr').
 */
export function normalizeLocale(locale?: string | null): SupportedLocale {
  if (!locale) return DEFAULT_LOCALE;
  const lower = locale.toLowerCase().trim();
  if (lower.startsWith('fr')) return 'fr';
  return 'en';
}

/**
 * Traverses nested JSON object with dot-notation key (e.g. "common.save").
 */
function getDeepValue(obj: Record<string, any> | undefined, keyPath: string): string | undefined {
  if (!obj) return undefined;
  const parts = keyPath.split('.');
  let current: any = obj;
  for (const part of parts) {
    if (current && typeof current === 'object' && part in current) {
      current = current[part];
    } else {
      return undefined;
    }
  }
  return typeof current === 'string' ? current : undefined;
}

/**
 * Interpolates variables formatted as {paramName} in templates.
 */
function interpolate(template: string, params?: Record<string, string | number>): string {
  if (!params) return template;
  return template.replace(/\{([a-zA-Z0-9_]+)\}/g, (match, paramName) => {
    return paramName in params ? String(params[paramName]) : match;
  });
}

/**
 * Translates a key with fallback chain: requested locale -> default 'en' -> key.
 */
export function t(locale: string, key: string, params?: Record<string, string | number>): string {
  const norm = normalizeLocale(locale);
  const val = getDeepValue(translations[norm], key);
  if (val !== undefined) {
    return interpolate(val, params);
  }
  if (norm !== DEFAULT_LOCALE) {
    const fallbackVal = getDeepValue(translations[DEFAULT_LOCALE], key);
    if (fallbackVal !== undefined) {
      return interpolate(fallbackVal, params);
    }
  }
  return interpolate(key, params);
}

/**
 * Translates a pluralized key based on count and CLDR pluralization rules:
 * - English: count === 1 ? 'one' : 'other'
 * - French: count === 0 || count === 1 ? 'one' : 'other'
 * Looks up key_one / key_other.
 */
export function tn(
  locale: string,
  key: string,
  count: number,
  params?: Record<string, string | number>
): string {
  const norm = normalizeLocale(locale);
  const pluralRules = new Intl.PluralRules(norm);
  const rule = pluralRules.select(count); // 'one' | 'other'

  const fullParams = { count, ...params };
  const pluralKey = `${key}_${rule}`;

  const val = getDeepValue(translations[norm], pluralKey);
  if (val !== undefined) {
    return interpolate(val, fullParams);
  }

  // Fallback to other form in same locale
  if (rule !== 'other') {
    const otherVal = getDeepValue(translations[norm], `${key}_other`);
    if (otherVal !== undefined) {
      return interpolate(otherVal, fullParams);
    }
  }

  // Fallback to English catalog plural
  if (norm !== DEFAULT_LOCALE) {
    const enRules = new Intl.PluralRules(DEFAULT_LOCALE);
    const enRule = enRules.select(count);
    const enVal = getDeepValue(translations[DEFAULT_LOCALE], `${key}_${enRule}`);
    if (enVal !== undefined) {
      return interpolate(enVal, fullParams);
    }
    const enOtherVal = getDeepValue(translations[DEFAULT_LOCALE], `${key}_other`);
    if (enOtherVal !== undefined) {
      return interpolate(enOtherVal, fullParams);
    }
  }

  return t(locale, key, fullParams);
}

/**
 * Formats a date using Intl.DateTimeFormat.
 */
export function formatDate(
  locale: string,
  date: Date | string | number,
  options?: Intl.DateTimeFormatOptions
): string {
  const norm = normalizeLocale(locale);
  const d = typeof date === 'string' || typeof date === 'number' ? new Date(date) : date;
  if (isNaN(d.getTime())) return '';
  const defaultOptions: Intl.DateTimeFormatOptions = {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  };
  return new Intl.DateTimeFormat(norm, { ...defaultOptions, ...options }).format(d);
}

/**
 * Formats a time using 24-hour notation conforming to Algerian institutional standards.
 */
export function formatTime(
  locale: string,
  date: Date | string | number,
  options?: Intl.DateTimeFormatOptions
): string {
  const norm = normalizeLocale(locale);
  const d = typeof date === 'string' || typeof date === 'number' ? new Date(date) : date;
  if (isNaN(d.getTime())) return '';
  const defaultOptions: Intl.DateTimeFormatOptions = {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  };
  return new Intl.DateTimeFormat(norm, { ...defaultOptions, ...options }).format(d);
}

/**
 * Formats a combined date and time.
 */
export function formatDateTime(
  locale: string,
  date: Date | string | number,
  options?: Intl.DateTimeFormatOptions
): string {
  const norm = normalizeLocale(locale);
  const d = typeof date === 'string' || typeof date === 'number' ? new Date(date) : date;
  if (isNaN(d.getTime())) return '';
  const defaultOptions: Intl.DateTimeFormatOptions = {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  };
  return new Intl.DateTimeFormat(norm, { ...defaultOptions, ...options }).format(d);
}

/**
 * Formats a number with proper decimal and thousands separators (French space vs English comma).
 */
export function formatNumber(
  locale: string,
  value: number,
  options?: Intl.NumberFormatOptions
): string {
  const norm = normalizeLocale(locale);
  return new Intl.NumberFormat(norm, options).format(value);
}

/**
 * Formats a ratio as percentage with locale-appropriate spacing.
 */
export function formatPercent(
  locale: string,
  value: number,
  options?: Intl.NumberFormatOptions
): string {
  const norm = normalizeLocale(locale);
  return new Intl.NumberFormat(norm, {
    style: 'percent',
    ...options,
  }).format(value);
}

/**
 * Localizes a path for the active locale:
 * - Prepend /fr if locale === 'fr' and path is not already prefixed.
 * - Strips /fr if locale === 'en'.
 * Preserves query strings, hash anchors, and handles root/edge cases cleanly.
 */
export function localizePath(locale: string, path: string): string {
  const norm = normalizeLocale(locale);

  if (!path || path.trim() === '') {
    return norm === 'fr' ? '/fr' : '/';
  }

  // Keep external and protocol-relative links untouched
  if (/^(?:[a-z]+:)?\/\//i.test(path) || path.startsWith('mailto:') || path.startsWith('tel:') || path.startsWith('#')) {
    return path;
  }

  // Separate pathname from query/hash
  const match = path.match(/^([^?#]*)(.*)$/);
  let pathname = match ? match[1] : path;
  const suffix = match ? match[2] : '';

  if (!pathname.startsWith('/')) {
    pathname = `/${pathname}`;
  }

  // Strip trailing slash if longer than 1 character
  if (pathname.length > 1 && pathname.endsWith('/')) {
    pathname = pathname.slice(0, -1);
  }

  // Check if pathname starts with /fr
  const hasFrPrefix = pathname === '/fr' || pathname.startsWith('/fr/');

  // Clean pathname without /fr prefix
  let cleanPath = pathname;
  if (hasFrPrefix) {
    cleanPath = pathname.slice(3);
    if (!cleanPath.startsWith('/')) {
      cleanPath = `/${cleanPath}`;
    }
  }
  if (!cleanPath || cleanPath === '') {
    cleanPath = '/';
  }

  if (norm === 'fr') {
    if (cleanPath === '/') {
      return `/fr${suffix}`;
    }
    return `/fr${cleanPath}${suffix}`;
  } else {
    // English default - no prefix
    return `${cleanPath}${suffix}`;
  }
}
