export const prerender = false;
import type { APIRoute } from 'astro';
import { createSupabaseServerClient } from '../../../lib/supabase';
import type { EmailOtpType } from '@supabase/supabase-js';

export const POST: APIRoute = async (context) => {
  const isJson = context.request.headers.get('content-type')?.includes('application/json');
  let token = '';
  let email = '';
  let type: EmailOtpType = 'signup';

  if (isJson) {
    const body = await context.request.json().catch(() => ({}));
    token = String(body.token ?? '').trim();
    email = String(body.email ?? '').trim();
    if (body.type) type = body.type as EmailOtpType;
  } else {
    const form = await context.request.formData();
    token = String(form.get('token') ?? '').trim();
    email = String(form.get('email') ?? '').trim();
    const formType = form.get('type');
    if (formType) type = String(formType) as EmailOtpType;
  }

  // If email was not sent in body, fall back to cookie
  if (!email) {
    email = context.cookies.get('resivo_pending_email')?.value ?? '';
  }

  if (!token || !email) {
    const errorMsg = 'Please provide both the 6-digit code and your email address.';
    if (isJson) {
      return new Response(JSON.stringify({ error: errorMsg }), { status: 400 });
    }
    return context.redirect(`/verify-email?error=${encodeURIComponent(errorMsg)}`);
  }

  try {
    const supabase = createSupabaseServerClient(context.request, context.cookies);
    const { data, error } = await supabase.auth.verifyOtp({
      email,
      token,
      type,
    });

    if (error) {
      const errorMsg = error.message.includes('Token has expired')
        ? 'This verification code has expired. Please click "Resend code" to get a fresh code.'
        : 'Invalid verification code. Please check your digits and try again.';

      if (isJson) {
        return new Response(JSON.stringify({ error: errorMsg }), { status: 400 });
      }
      return context.redirect(`/verify-email?error=${encodeURIComponent(errorMsg)}`);
    }

    // Clear temporary pending email cookie upon successful verification
    context.cookies.delete('resivo_pending_email', { path: '/' });

    if (type === 'recovery') {
      if (isJson) return new Response(JSON.stringify({ redirect: '/reset-password' }), { status: 200 });
      return context.redirect('/reset-password');
    }

    if (type === 'email_change') {
      if (isJson) return new Response(JSON.stringify({ redirect: '/dashboard/profile?updated=1' }), { status: 200 });
      return context.redirect('/dashboard/profile?updated=1');
    }

    if (isJson) {
      return new Response(JSON.stringify({ redirect: '/login?verified=1' }), { status: 200 });
    }
    return context.redirect('/login?verified=1');
  } catch (err: any) {
    const errorMsg = err?.message || 'Verification failed. Please try again.';
    if (isJson) {
      return new Response(JSON.stringify({ error: errorMsg }), { status: 500 });
    }
    return context.redirect(`/verify-email?error=${encodeURIComponent(errorMsg)}`);
  }
};
