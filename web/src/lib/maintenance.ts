export const MAINTENANCE_STAGES = ['Pending', 'In progress', 'Resolved'] as const;
export type MaintenanceStage = (typeof MAINTENANCE_STAGES)[number];

export function getStageIndex(status: string): number {
  const s = String(status || '').toLowerCase().trim();
  if (s === 'resolved') return 2;
  if (s === 'in_progress') return 1;
  return 0; // pending, including legacy 'under_review'
}

export function normalizeMaintenanceStatus(status: string): 'pending' | 'in_progress' | 'resolved' {
  const s = String(status || '').toLowerCase().trim();
  if (s === 'resolved') return 'resolved';
  if (s === 'in_progress') return 'in_progress';
  return 'pending'; // maps 'under_review' and unrecognized to 'pending'
}

export function getMaintenanceStatusLabel(status: string): string {
  const norm = normalizeMaintenanceStatus(status);
  if (norm === 'resolved') return 'Resolved';
  if (norm === 'in_progress') return 'In progress';
  return 'Pending';
}
