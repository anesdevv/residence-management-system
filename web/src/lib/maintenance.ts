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

export const MAINTENANCE_CATEGORIES = [
  { id: 'plumbing', label: 'Plumbing', icon: 'droplet', desc: 'Leaks, faucets, drainage, pipes' },
  { id: 'electricity', label: 'Electricity', icon: 'zap', desc: 'Lighting, power outlets, switches' },
  { id: 'carpentry', label: 'Carpentry', icon: 'hammer', desc: 'Beds, desks, doors, locks, closets' },
  { id: 'others', label: 'Others', icon: 'wrench', desc: 'Radiators, windows, structural & other issues' },
] as const;

export const ALLOWED_CATEGORY_IDS = ['plumbing', 'electricity', 'carpentry', 'others'] as const;
export type MaintenanceCategoryId = (typeof ALLOWED_CATEGORY_IDS)[number];

export function isAllowedCategory(category: string): boolean {
  return (ALLOWED_CATEGORY_IDS as readonly string[]).includes(category);
}

export function normalizeMaintenanceCategory(category: string): MaintenanceCategoryId {
  const c = String(category || '').toLowerCase().trim();
  if (c === 'plumbing') return 'plumbing';
  if (c === 'electricity' || c === 'electrical') return 'electricity';
  if (c === 'carpentry' || c === 'furniture') return 'carpentry';
  return 'others'; // 'others', 'other', 'heating', 'general', etc.
}

export function getCategoryMeta(category: string): { id: MaintenanceCategoryId; label: string; icon: string } {
  const norm = normalizeMaintenanceCategory(category);
  const found = MAINTENANCE_CATEGORIES.find((c) => c.id === norm);
  return found ?? { id: 'others', label: 'Others', icon: 'wrench' };
}


export async function batchResolveSignedUrls(
  storageClient: { from: (bucket: string) => { createSignedUrls: (paths: string[], expiresIn: number) => Promise<{ data: Array<{ path: string; signedUrl: string }> | null }> } },
  bucket: string,
  paths: string[],
  expiresIn: number = 300,
): Promise<Map<string, string>> {
  const urlMap = new Map<string, string>();
  const validPaths = paths.filter((p): p is string => typeof p === 'string' && p.length > 0);
  if (validPaths.length === 0) return urlMap;

  try {
    const { data } = await storageClient.from(bucket).createSignedUrls(validPaths, expiresIn);
    for (const entry of data ?? []) {
      if (entry?.signedUrl && entry?.path) {
        urlMap.set(entry.path, entry.signedUrl);
      }
    }
  } catch {
    // Graceful fallback if storage batching fails
  }
  return urlMap;
}
