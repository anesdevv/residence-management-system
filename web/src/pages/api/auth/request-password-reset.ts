export const prerender = false;
import type { APIRoute } from 'astro';

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

  const supabaseUrl = import.meta.env.PUBLIC_SUPABASE_URL;
  const anonKey = import.meta.env.PUBLIC_SUPABASE_ANON_KEY;

  const genericSuccess = 'If an account exists for this card ID or email, instructions have been sent to the verified email address on file.';

  if (!identifier) {
    if (isJson) return new Response(JSON.stringify({ success: true, message: genericSuccess }), { status: 200 });
    return context.redirect(`/forgot-password?sent=1`);
  }

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
      if (isJson) {
        return new Response(JSON.stringify({ error: 'rate_limit_exceeded', message: data.message }), { status: 429 });
      }
      return context.redirect(`/forgot-password?error=${encodeURIComponent(data.message || 'Too many attempts.')}`);
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
    return context.redirect(`/forgot-password?sent=1&identifier=${encodeURIComponent(identifier)}`);
  } catch {
    if (isJson) {
      return new Response(JSON.stringify({ success: true, message: genericSuccess }), { status: 200 });
    }
    return context.redirect(`/forgot-password?sent=1`);
  }
};
