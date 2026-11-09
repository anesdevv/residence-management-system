export const prerender = false;
import type { APIRoute } from 'astro';
import { createSupabaseServerClient } from '../../../lib/supabase';
import { normalizeEmail, isEmail } from '../../../lib/validation';

export const POST: APIRoute = async (context) => {
  const user = context.locals.user;
  if (!user) {
    return context.redirect('/login');
  }

  const form = await context.request.formData();
  const email = normalizeEmail(String(form.get('email') ?? ''));
  const confirmEmail = normalizeEmail(String(form.get('confirm_email') ?? ''));

  if (!email || !isEmail(email)) {
    return context.redirect(`/account/add-email?error=${encodeURIComponent('Please enter a valid email address.')}`);
  }
  if (email !== confirmEmail) {
    return context.redirect(`/account/add-email?error=${encodeURIComponent('Email confirmation does not match.')}`);
  }
  if (email.endsWith('@students.residence.local')) {
    return context.redirect(`/account/add-email?error=${encodeURIComponent('Please enter a real email address outside the residence domain.')}`);
  }

  const supabaseUrl = import.meta.env.PUBLIC_SUPABASE_URL;
  const anonKey = import.meta.env.PUBLIC_SUPABASE_ANON_KEY;

  try {
    const supabase = createSupabaseServerClient(context.request, context.cookies);
    const { data: sessionData } = await supabase.auth.getSession();
    const token = sessionData?.session?.access_token;

    if (!token) {
      return context.redirect('/login?error=Session+expired');
    }

    const response = await fetch(`${supabaseUrl}/functions/v1/link-real-email`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'apikey': anonKey,
        'Authorization': `Bearer ${token}`,
      },
      body: JSON.stringify({ email }),
    });

    const result = await response.json().catch(() => ({}));

    if (!response.ok) {
      return context.redirect(`/account/add-email?error=${encodeURIComponent(result.message || 'Failed to update email.')}`);
    }

    context.cookies.set('resivo_pending_email', email, {
      path: '/',
      httpOnly: false,
      sameSite: 'lax',
      maxAge: 3600,
    });

    return context.redirect(`/account/add-email?code_sent=1&email=${encodeURIComponent(email)}`);
  } catch (err: any) {
    return context.redirect(`/account/add-email?error=${encodeURIComponent(err?.message || 'Server error occurred.')}`);
  }
};
