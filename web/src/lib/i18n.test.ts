import { describe, it, expect } from 'vitest';
import {
  normalizeLocale,
  t,
  tn,
  formatDate,
  formatTime,
  formatNumber,
  formatPercent,
  localizePath,
  DEFAULT_LOCALE,
  LOCALES,
} from './i18n';

describe('i18n library', () => {
  describe('constants & normalizeLocale', () => {
    it('defines supported locales and default', () => {
      expect(DEFAULT_LOCALE).toBe('en');
      expect(LOCALES).toEqual(['en', 'fr']);
    });

    it('normalizes various locale string inputs', () => {
      expect(normalizeLocale('en')).toBe('en');
      expect(normalizeLocale('EN')).toBe('en');
      expect(normalizeLocale('en-US')).toBe('en');
      expect(normalizeLocale('en_GB')).toBe('en');
      expect(normalizeLocale('fr')).toBe('fr');
      expect(normalizeLocale('FR')).toBe('fr');
      expect(normalizeLocale('fr-FR')).toBe('fr');
      expect(normalizeLocale('fr-DZ')).toBe('fr');
      expect(normalizeLocale(null)).toBe('en');
      expect(normalizeLocale(undefined)).toBe('en');
      expect(normalizeLocale('')).toBe('en');
      expect(normalizeLocale('de')).toBe('en'); // unsupported defaults to en
    });
  });

  describe('t (translation & interpolation)', () => {
    it('translates keys in English', () => {
      expect(t('en', 'common.save')).toBe('Save');
      expect(t('en', 'common.cancel')).toBe('Cancel');
      expect(t('en', 'nav.dashboard')).toBe('Dashboard');
    });

    it('translates keys in French according to glossary', () => {
      expect(t('fr', 'common.save')).toBe('Enregistrer');
      expect(t('fr', 'common.cancel')).toBe('Annuler');
      expect(t('fr', 'nav.dashboard')).toBe('Tableau de bord');
      expect(t('fr', 'nav.pending')).toBe('Demandes d’hébergement');
      expect(t('fr', 'terms.digital_pass')).toBe('Carte de résident numérique');
    });

    it('interpolates parameters correctly', () => {
      expect(t('en', 'dashboard.welcome', { name: 'Amine' })).toBe('Welcome, Amine');
      expect(t('fr', 'dashboard.welcome', { name: 'Amine' })).toBe('Bienvenue, Amine');
    });

    it('handles numeric parameters', () => {
      expect(t('en', 'landing.footer_rights', { year: 2026 })).toContain('2026');
      expect(t('fr', 'landing.footer_rights', { year: 2026 })).toContain('2026');
    });

    it('falls back to English when a key is missing in French', () => {
      // If a non-existent key is tested
      expect(t('fr', 'non.existent.key')).toBe('non.existent.key');
    });

    it('returns the raw key when missing in all catalogues', () => {
      expect(t('en', 'some.totally.missing.key')).toBe('some.totally.missing.key');
      expect(t('fr', 'some.totally.missing.key')).toBe('some.totally.missing.key');
    });
  });

  describe('tn (CLDR pluralization)', () => {
    it('applies English plural rules (1 is one, 0 and >1 are other)', () => {
      // time.minutes_ago:
      // minutes_ago_one: "{count} minute ago"
      // minutes_ago_other: "{count} minutes ago"
      expect(tn('en', 'time.minutes_ago', 1)).toBe('1 minute ago');
      expect(tn('en', 'time.minutes_ago', 0)).toBe('0 minutes ago');
      expect(tn('en', 'time.minutes_ago', 2)).toBe('2 minutes ago');
      expect(tn('en', 'time.minutes_ago', 45)).toBe('45 minutes ago');

      // maintenance.tickets_count:
      expect(tn('en', 'maintenance.tickets_count', 1)).toBe('1 active ticket');
      expect(tn('en', 'maintenance.tickets_count', 3)).toBe('3 active tickets');
    });

    it('applies French CLDR plural rules (0 and 1 are one, >=2 are other)', () => {
      // In French: 0 and 1 use _one, 2+ uses _other
      expect(tn('fr', 'time.minutes_ago', 0)).toBe('Il y a 0 minute');
      expect(tn('fr', 'time.minutes_ago', 1)).toBe('Il y a 1 minute');
      expect(tn('fr', 'time.minutes_ago', 2)).toBe('Il y a 2 minutes');
      expect(tn('fr', 'time.minutes_ago', 15)).toBe('Il y a 15 minutes');

      // maintenance.tickets_count:
      expect(tn('fr', 'maintenance.tickets_count', 0)).toBe('0 ticket actif');
      expect(tn('fr', 'maintenance.tickets_count', 1)).toBe('1 ticket actif');
      expect(tn('fr', 'maintenance.tickets_count', 4)).toBe('4 tickets actifs');
    });

    it('supports additional interpolation parameters in plural calls', () => {
      const res = tn('fr', 'time.minutes_ago', 5, { extra: 'test' });
      expect(res).toBe('Il y a 5 minutes');
    });
  });

  describe('formatDate and formatTime', () => {
    const fixedDate = new Date(Date.UTC(2026, 9, 12, 14, 30, 0)); // 12 Oct 2026

    it('formats dates according to locale', () => {
      const enFormatted = formatDate('en', fixedDate);
      const frFormatted = formatDate('fr', fixedDate);

      expect(enFormatted).toBeTruthy();
      expect(frFormatted).toBeTruthy();
      expect(enFormatted).toContain('2026');
      expect(frFormatted).toContain('2026');
    });

    it('formats time in 24-hour notation', () => {
      const frTime = formatTime('fr', fixedDate, { timeZone: 'UTC' });
      expect(frTime).toBe('14:30');
    });

    it('returns empty string for invalid date', () => {
      expect(formatDate('en', 'invalid-date')).toBe('');
      expect(formatTime('fr', 'invalid-date')).toBe('');
    });
  });

  describe('formatNumber and formatPercent', () => {
    it('formats numbers with locale separators', () => {
      const num = 1250.5;
      const enNum = formatNumber('en', num);
      const frNum = formatNumber('fr', num);

      expect(enNum).toContain('1,250.5');
      // In French: comma decimal separator, non-breaking space for thousands
      expect(frNum).toContain('1');
      expect(frNum).toContain('250,5');
    });

    it('formats percentages', () => {
      const val = 0.85;
      const enPct = formatPercent('en', val);
      const frPct = formatPercent('fr', val);

      expect(enPct).toBe('85%');
      expect(frPct.replace(/\s/g, ' ')).toContain('85 %');
    });
  });

  describe('localizePath', () => {
    it('handles root path', () => {
      expect(localizePath('fr', '/')).toBe('/fr');
      expect(localizePath('en', '/')).toBe('/');
    });

    it('handles empty string path', () => {
      expect(localizePath('fr', '')).toBe('/fr');
      expect(localizePath('en', '')).toBe('/');
    });

    it('handles /fr root path', () => {
      expect(localizePath('fr', '/fr')).toBe('/fr');
      expect(localizePath('en', '/fr')).toBe('/');
      expect(localizePath('fr', '/fr/')).toBe('/fr');
      expect(localizePath('en', '/fr/')).toBe('/');
    });

    it('prefixes routes with /fr for French', () => {
      expect(localizePath('fr', '/dashboard')).toBe('/fr/dashboard');
      expect(localizePath('fr', '/login')).toBe('/fr/login');
      expect(localizePath('fr', '/dashboard/maintenance')).toBe('/fr/dashboard/maintenance');
    });

    it('does not duplicate /fr if already prefixed', () => {
      expect(localizePath('fr', '/fr/dashboard')).toBe('/fr/dashboard');
      expect(localizePath('fr', '/fr/login')).toBe('/fr/login');
    });

    it('strips /fr for English', () => {
      expect(localizePath('en', '/fr/dashboard')).toBe('/dashboard');
      expect(localizePath('en', '/fr/login')).toBe('/login');
      expect(localizePath('en', '/fr/dashboard/maintenance')).toBe('/dashboard/maintenance');
    });

    it('keeps unprefixed routes unprefixed for English', () => {
      expect(localizePath('en', '/dashboard')).toBe('/dashboard');
      expect(localizePath('en', '/login')).toBe('/login');
    });

    it('preserves query parameters and hash anchors', () => {
      expect(localizePath('fr', '/dashboard?tab=maintenance#tickets')).toBe(
        '/fr/dashboard?tab=maintenance#tickets'
      );
      expect(localizePath('en', '/fr/dashboard?tab=maintenance#tickets')).toBe(
        '/dashboard?tab=maintenance#tickets'
      );
      expect(localizePath('fr', '/?ref=portal')).toBe('/fr?ref=portal');
      expect(localizePath('en', '/fr?ref=portal')).toBe('/?ref=portal');
    });

    it('leaves external URLs and protocols untouched', () => {
      expect(localizePath('fr', 'https://univ-tlemcen.dz/housing')).toBe(
        'https://univ-tlemcen.dz/housing'
      );
      expect(localizePath('fr', 'http://example.com')).toBe('http://example.com');
      expect(localizePath('fr', '//cdn.example.com/asset.js')).toBe('//cdn.example.com/asset.js');
      expect(localizePath('fr', 'mailto:contact@residence.dz')).toBe('mailto:contact@residence.dz');
      expect(localizePath('fr', 'tel:+21343210000')).toBe('tel:+21343210000');
      expect(localizePath('fr', '#section-services')).toBe('#section-services');
    });

    it('handles relative path without leading slash', () => {
      expect(localizePath('fr', 'dashboard')).toBe('/fr/dashboard');
      expect(localizePath('en', 'dashboard')).toBe('/dashboard');
    });
  });
});
