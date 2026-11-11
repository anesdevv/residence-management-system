// web/src/lib/email-gate.ts
// Determines whether an authenticated user is an existing student missing a contact email.
// Staff/admin accounts and students who already have a contact email are never redirected.

export function isStaffRole(role?: string | null): boolean {
  const normalized = (role ?? '').trim().toLowerCase();
  return normalized === 'staff' || normalized === 'admin';
}

export function shouldGateStudentForEmail(opts: {
  role?: string | null;
  studentRow?: { email?: string | null } | null;
}): boolean {
  if (isStaffRole(opts.role)) {
    return false;
  }
  if (!opts.studentRow) {
    return false;
  }
  const email = opts.studentRow.email ?? '';
  return email.trim() === '';
}

export async function checkUserNeedsContactEmail(supabase: any, userId: string): Promise<boolean> {
  if (!supabase || !userId) return false;

  try {
    const [profileRes, studentRes] = await Promise.all([
      supabase.from('profiles').select('role').eq('id', userId).maybeSingle(),
      supabase.from('students').select('email').eq('id', userId).maybeSingle(),
    ]);

    return shouldGateStudentForEmail({
      role: profileRes?.data?.role ?? null,
      studentRow: studentRes?.data ?? null,
    });
  } catch {
    return false;
  }
}
