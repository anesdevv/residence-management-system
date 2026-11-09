export const prerender = false;
import type { APIRoute } from 'astro';
import { createSupabaseServerClient, cardIdToEmail } from '../../lib/supabase';
import { TIMEOUT_MESSAGES } from '../../lib/timeouts';

export const POST: APIRoute = async (context) => {
  const form = await context.request.formData();
  const identifier = String(form.get('identifier') ?? form.get('card_id') ?? '').trim();
  const password = String(form.get('password') ?? '');

  if (!identifier || !password) {
    return context.redirect(`/login?error=${encodeURIComponent('Please enter your card ID or email and password.')}`);
  }

  const supabaseUrl = import.meta.env.PUBLIC_SUPABASE_URL;
  const anonKey = import.meta.env.PUBLIC_SUPABASE_ANON_KEY;

  try {
    const supabase = createSupabaseServerClient(context.request, context.cookies);
    let sessionResult: any = null;
    let needsRealEmail = false;

    // Fast-path: Invoke student-login Edge Function for server-side identifier resolution
    try {
      const edgeRes = await fetch(`${supabaseUrl}/functions/v1/student-login`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'apikey': anonKey,
        },
        body: JSON.stringify({ identifier, password }),
      });

      const data = await edgeRes.json().catch(() => ({}));

      if (!edgeRes.ok) {
        if (edgeRes.status === 403 && data.error === 'email_not_verified') {
          if (data.email) {
            context.cookies.set('resivo_pending_email', data.email, {
              path: '/',
              httpOnly: false,
              sameSite: 'lax',
              maxAge: 3600,
            });
          }
          return context.redirect('/verify-email?unverified=1');
        }

        const errMsg = data.message || 'Invalid card ID/email or password.';
        return context.redirect(`/login?error=${encodeURIComponent(errMsg)}`);
      }

      sessionResult = data.session;
      needsRealEmail = Boolean(data.needs_real_email);
    } catch {
      // Fallback path: Direct signInWithPassword if edge function is offline/unreachable in local mock
      const targetEmail = identifier.includes('@') ? identifier.toLowerCase() : cardIdToEmail(identifier);
      const { data, error } = await supabase.auth.signInWithPassword({
        email: targetEmail,
        password,
      });

      if (error) {
        const msg = error.message.toLowerCase();
        if (msg.includes('email not confirmed')) {
          if (identifier.includes('@')) {
            context.cookies.set('resivo_pending_email', identifier.toLowerCase(), { path: '/', maxAge: 3600 });
          }
          return context.redirect('/verify-email?unverified=1');
        }
        return context.redirect(`/login?error=${encodeURIComponent('Invalid card ID/email or password.')}`);
      }

      sessionResult = data.session;
      needsRealEmail = (data.user?.email ?? '').endsWith('@students.residence.local');
    }

    if (sessionResult) {
      await supabase.auth.setSession({
        access_token: sessionResult.access_token,
        refresh_token: sessionResult.refresh_token,
      });
    }

    if (needsRealEmail) {
      return context.redirect('/account/add-email');
    }

    return context.redirect('/dashboard');
  } catch (err: any) {
    const message = err?.message || TIMEOUT_MESSAGES.READ;
    return context.redirect(`/login?error=${encodeURIComponent(message)}`);
  }
};
