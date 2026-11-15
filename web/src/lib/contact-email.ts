// web/src/lib/contact-email.ts
// Pre-flight contact email availability check used by the registration route.
// Supabase Auth masks trigger errors ("Database error saving new user"), so the
// duplicate-email rule must be checked before auth.signUp() is called.

export async function isContactEmailTaken(supabase: any, email: string): Promise<boolean> {
  if (!supabase || typeof supabase.rpc !== 'function') return false;

  try {
    const { data, error } = await supabase.rpc('contact_email_available', { p_email: email });
    // Fail open: the auth trigger and unique index still enforce uniqueness.
    if (error || typeof data !== 'boolean') return false;
    return data === false;
  } catch {
    return false;
  }
}
