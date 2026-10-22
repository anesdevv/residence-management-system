import { describe, it, expect } from 'vitest';
import {
  MAINTENANCE_STAGES,
  getStageIndex,
  normalizeMaintenanceStatus,
  getMaintenanceStatusLabel,
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
