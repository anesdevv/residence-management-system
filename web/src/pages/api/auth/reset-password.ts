export const prerender = false;
import type { APIRoute } from 'astro';
import { createSupabaseServerClient } from '../../../lib/supabase';
import { validatePassword } from '../../../lib/validation';

export const POST: APIRoute = async (context) => {
  const form = await context.request.formData();
  const password = String(form.get('password') ?? '');
  const confirmPassword = String(form.get('confirm_password') ?? '');

  const errors = validatePassword(password);
  if (password !== confirmPassword) {
    errors.push('Password confirmation does not match.');
  }

  if (errors.length) {
    return context.redirect(`/reset-password?error=${encodeURIComponent(errors[0])}`);
  }

  try {
    const supabase = createSupabaseServerClient(context.request, context.cookies);
    const { error } = await supabase.auth.updateUser({ password });

    if (error) {
      return context.redirect(`/reset-password?error=${encodeURIComponent(error.message)}`);
    }

    // Invalidate other active sessions
    try {
      await supabase.auth.signOut({ scope: 'others' });
    } catch {
      // Best-effort session revocation
    }

    return context.redirect('/login?reset=1');
  } catch (err: any) {
    return context.redirect(`/reset-password?error=${encodeURIComponent(err?.message || 'Password update failed.')}`);
  }
};
