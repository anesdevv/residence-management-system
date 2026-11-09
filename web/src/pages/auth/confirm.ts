export const prerender = false;
import type { APIRoute } from 'astro';
import { createSupabaseServerClient } from '../../lib/supabase';
import type { EmailOtpType } from '@supabase/supabase-js';

export const GET: APIRoute = async (context) => {
  const url = new URL(context.request.url);
  const token_hash = url.searchParams.get('token_hash');
  const type = url.searchParams.get('type') as EmailOtpType | null;
  const next = url.searchParams.get('next') || '/dashboard';

  if (!token_hash || !type) {
    return context.redirect('/login?error=Invalid+or+missing+confirmation+parameters');
  }

  try {
    const supabase = createSupabaseServerClient(context.request, context.cookies);
    const { error } = await supabase.auth.verifyOtp({
      token_hash,
      type,
    });

    if (error) {
      if (type === 'recovery') {
        return context.redirect(`/forgot-password?error=${encodeURIComponent(error.message)}`);
      }
      return context.redirect(`/login?error=${encodeURIComponent(error.message)}`);
    }

    if (type === 'recovery') {
      return context.redirect('/reset-password');
    }

    if (type === 'email_change') {
      return context.redirect('/dashboard/profile?updated=1');
    }

    return context.redirect(next);
  } catch (err: any) {
    return context.redirect(`/login?error=${encodeURIComponent(err?.message || 'Verification link failed.')}`);
  }
};
