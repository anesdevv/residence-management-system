export const prerender = false;
import type { APIRoute } from 'astro';
import { createSupabaseServerClient } from '../../../lib/supabase';
import { formatProviderRateLimitError } from '../../../lib/resend-cooldown';

export const POST: APIRoute = async (context) => {
  const isJson = context.request.headers.get('content-type')?.includes('application/json');
  let identifier = '';

  if (isJson) {
    const body = await context.request.json().catch(() => ({}));
    identifier = String(body.identifier ?? '').trim();
  } else {
    const form = await context.request.formData();
    identifier = String(form.get('identifier') ?? '').trim();
  }

  const cookieLocale = context.cookies.get('resivo_locale')?.value?.toLowerCase();
  const referer = context.request.headers.get('referer') || '';
  const isFrench = cookieLocale === 'fr' || referer.includes('/fr/');
  const basePath = isFrench ? '/fr/forgot-password' : '/forgot-password';

  const supabaseUrl = import.meta.env.PUBLIC_SUPABASE_URL;
  const anonKey = import.meta.env.PUBLIC_SUPABASE_ANON_KEY;

  const genericSuccess = isFrench
    ? 'Si un compte existe pour cet identifiant ou e-mail, les instructions ont été envoyées à l’adresse vérifiée.'
    : 'If an account exists for this card ID or email, instructions have been sent to the verified email address on file.';

  if (!identifier) {
    if (isJson) return new Response(JSON.stringify({ success: true, message: genericSuccess }), { status: 200 });
    return context.redirect(`${basePath}?sent=1`);
  }

  let success = false;
  let rateLimited = false;
  let errorMessage = '';

  // 1. Try calling the deployed Edge Function
  try {
    const response = await fetch(`${supabaseUrl}/functions/v1/request-password-reset`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'apikey': anonKey,
      },
      body: JSON.stringify({ identifier }),
    });

    const data = await response.json().catch(() => ({}));

    if (response.status === 429) {
      rateLimited = true;
      errorMessage = data.message || 'Too many attempts.';
    } else if (response.ok) {
      success = true;
    }
  } catch {
    // Edge function unreachable or network error, will fall back below
  }

  // 2. Direct Supabase Auth client fallback if Edge Function was not successful and identifier is an email
  if (!success && !rateLimited && identifier.includes('@')) {
    try {
      const supabase = createSupabaseServerClient(context.request, context.cookies);
      const origin = new URL(context.request.url).origin;
      const { error: resetError } = await supabase.auth.resetPasswordForEmail(identifier.toLowerCase(), {
        redirectTo: `${origin}/auth/confirm?type=recovery&next=/reset-password`,
      });

      if (resetError) {
        if (resetError.status === 429 || resetError.message?.toLowerCase().includes('rate limit')) {
          rateLimited = true;
          errorMessage = formatProviderRateLimitError(resetError);
        }
      } else {
        success = true;
      }
    } catch (fallbackErr) {
      errorMessage = formatProviderRateLimitError(fallbackErr);
    }
  }

  if (rateLimited) {
    if (isJson) {
      return new Response(JSON.stringify({ error: 'rate_limit_exceeded', message: errorMessage }), { status: 429 });
    }
    return context.redirect(`${basePath}?error=${encodeURIComponent(errorMessage || 'Too many attempts.')}`);
  }

  if (identifier.includes('@')) {
    context.cookies.set('resivo_pending_email', identifier.toLowerCase(), {
      path: '/',
      maxAge: 3600,
      sameSite: 'lax',
    });
  }

  if (isJson) {
    return new Response(JSON.stringify({ success: true, message: genericSuccess }), { status: 200 });
  }
  return context.redirect(`${basePath}?sent=1&identifier=${encodeURIComponent(identifier)}`);
};
