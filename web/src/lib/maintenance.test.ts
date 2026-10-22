import { describe, it, expect } from 'vitest';
import {
  MAINTENANCE_STAGES,
  getStageIndex,
  normalizeMaintenanceStatus,
  getMaintenanceStatusLabel,
  MAINTENANCE_CATEGORIES,
  ALLOWED_CATEGORY_IDS,
  isAllowedCategory,
  normalizeMaintenanceCategory,
  getCategoryMeta,
} from './maintenance';

describe('Maintenance Lifecycle (T2: Exactly 3 Stages)', () => {
  it('has exactly three lifecycle stages in order: Pending, In progress, Resolved', () => {
    expect(MAINTENANCE_STAGES).toEqual(['Pending', 'In progress', 'Resolved']);
    expect(MAINTENANCE_STAGES).not.toContain('Under review');
    expect(MAINTENANCE_STAGES).not.toContain('Submitted');
    expect(MAINTENANCE_STAGES).not.toContain('Triaged');
  });

  it('computes correct stage indices for standard statuses', () => {
    expect(getStageIndex('pending')).toBe(0);
    expect(getStageIndex('in_progress')).toBe(1);
    expect(getStageIndex('resolved')).toBe(2);
  });

  it('normalizes legacy under_review status to pending with index 0', () => {
    expect(normalizeMaintenanceStatus('under_review')).toBe('pending');
    expect(getMaintenanceStatusLabel('under_review')).toBe('Pending');
    expect(getStageIndex('under_review')).toBe(0);
  });

  it('handles unknown or empty statuses as pending', () => {
    expect(normalizeMaintenanceStatus('')).toBe('pending');
    expect(getStageIndex('unknown_status')).toBe(0);
  });
});

describe('Maintenance Categories (T3: Plumbing, Electricity, Carpentry, Others)', () => {
  it('defines exactly the 4 allowed categories in order', () => {
    expect(ALLOWED_CATEGORY_IDS).toEqual(['plumbing', 'electricity', 'carpentry', 'others']);
    expect(MAINTENANCE_CATEGORIES.map((c) => c.label)).toEqual([
      'Plumbing',
      'Electricity',
      'Carpentry',
      'Others',
    ]);
  });

  it('accepts valid category "others" and canonical categories', () => {
    expect(isAllowedCategory('plumbing')).toBe(true);
    expect(isAllowedCategory('electricity')).toBe(true);
    expect(isAllowedCategory('carpentry')).toBe(true);
    expect(isAllowedCategory('others')).toBe(true);
  });

  it('strictly rejects "heating" and "general"', () => {
    expect(isAllowedCategory('heating')).toBe(false);
    expect(isAllowedCategory('general')).toBe(false);
    expect(isAllowedCategory('other')).toBe(false);
    expect(isAllowedCategory('furniture')).toBe(false);
    expect(isAllowedCategory('internet')).toBe(false);
  });

  it('migrates legacy General, Heating, and Other tickets to display as Others', () => {
    expect(normalizeMaintenanceCategory('heating')).toBe('others');
    expect(normalizeMaintenanceCategory('general')).toBe('others');
    expect(normalizeMaintenanceCategory('other')).toBe('others');
    expect(normalizeMaintenanceCategory('others')).toBe('others');

    expect(getCategoryMeta('heating').label).toBe('Others');
    expect(getCategoryMeta('heating').icon).toBe('wrench');

    expect(getCategoryMeta('general').label).toBe('Others');
    expect(getCategoryMeta('general').icon).toBe('wrench');

    expect(getCategoryMeta('other').label).toBe('Others');
    expect(getCategoryMeta('others').label).toBe('Others');
  });

  it('migrates legacy Electrical and Furniture tickets correctly', () => {
    expect(normalizeMaintenanceCategory('electrical')).toBe('electricity');
    expect(getCategoryMeta('electrical').label).toBe('Electricity');

    expect(normalizeMaintenanceCategory('furniture')).toBe('carpentry');
    expect(getCategoryMeta('furniture').label).toBe('Carpentry');
  });
});
