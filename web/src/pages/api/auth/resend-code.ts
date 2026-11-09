export const prerender = false;
import type { APIRoute } from 'astro';
import { createSupabaseServerClient } from '../../../lib/supabase';
import { formatProviderRateLimitError } from '../../../lib/resend-cooldown';

export const POST: APIRoute = async (context) => {
  const body = await context.request.json().catch(() => ({}));
  let email = String(body.email ?? '').trim();
  const flow = String(body.flow ?? 'signup');

  if (!email) {
    email = context.cookies.get('resivo_pending_email')?.value ?? '';
  }

  if (!email) {
    return new Response(JSON.stringify({ error: 'Email address is required.' }), {
      status: 400,
      headers: { 'Content-Type': 'application/json' },
    });
  }

  try {
    const supabase = createSupabaseServerClient(context.request, context.cookies);
    const origin = new URL(context.request.url).origin;

    if (flow === 'recovery') {
      const { error } = await supabase.auth.resetPasswordForEmail(email, {
        redirectTo: `${origin}/auth/confirm?type=recovery&next=/reset-password`,
      });
      if (error) throw error;
    } else if (flow === 'magiclink') {
      const { error } = await supabase.auth.signInWithOtp({
        email,
        options: {
          shouldCreateUser: false,
          emailRedirectTo: `${origin}/auth/confirm?type=magiclink&next=/dashboard`,
        },
      });
      if (error) throw error;
    } else {
      // signup or email_change
      const resendType = flow === 'email_change' ? 'email_change' : 'signup';
      const { error } = await supabase.auth.resend({
        type: resendType,
        email,
        options: {
          emailRedirectTo: `${origin}/auth/confirm?type=email&next=/dashboard`,
        },
      });
      if (error) throw error;
    }

    return new Response(
      JSON.stringify({
        success: true,
        message: 'A fresh verification code has been dispatched to your email.',
      }),
      {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }
    );
  } catch (err: any) {
    const userMsg = formatProviderRateLimitError(err);
    const isRateLimit = userMsg.includes('daily email limit') || err?.status === 429;

    return new Response(
      JSON.stringify({
        error: isRateLimit ? 'rate_limit_exceeded' : 'resend_failed',
        message: userMsg,
      }),
      {
        status: isRateLimit ? 429 : 500,
        headers: { 'Content-Type': 'application/json' },
      }
    );
  }
};
