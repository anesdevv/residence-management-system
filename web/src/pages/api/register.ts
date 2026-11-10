export const prerender = false;
import type { APIRoute } from 'astro';
import { createSupabaseServerClient } from '../../lib/supabase';
import { validateRegistration, normalizeEmail } from '../../lib/validation';
import { checkRegistrationGate, getResidencePublic } from '../../lib/residence';
import { TIMEOUT_MESSAGES } from '../../lib/timeouts';

export const POST: APIRoute = async (context) => {
  const form = await context.request.formData();
  const rawEmail = String(form.get('email') ?? '');
  const data = {
    card_id: String(form.get('card_id') ?? ''),
    first_name: String(form.get('first_name') ?? ''),
    last_name: String(form.get('last_name') ?? ''),
    birth_date: String(form.get('birth_date') ?? ''),
    phone: String(form.get('phone') ?? ''),
    email: rawEmail,
    confirm_email: String(form.get('confirm_email') ?? ''),
    university: String(form.get('university') ?? ''),
    faculty: String(form.get('faculty') ?? ''),
    study_level: String(form.get('study_level') ?? ''),
    wilaya: String(form.get('wilaya') ?? ''),
    password: String(form.get('password') ?? ''),
  };

  const errors = validateRegistration(data);
  if (errors.length) {
    return context.redirect(`/register?error=${encodeURIComponent(errors[0])}`);
  }

  const cleanEmail = normalizeEmail(data.email);
  const cleanCardId = data.card_id.trim();

  try {
    const supabase = createSupabaseServerClient(context.request, context.cookies);
    const residence = await getResidencePublic(supabase);
    const gateError = checkRegistrationGate(residence, context.locals?.locale || 'en');
    if (gateError) {
      return context.redirect(`/register?error=${encodeURIComponent(gateError)}`);
    }

    const origin = new URL(context.request.url).origin;

    const { data: signUpData, error } = await supabase.auth.signUp({
      email: cleanEmail,
      password: data.password,
      options: {
        emailRedirectTo: `${origin}/auth/confirm?type=email&next=/dashboard`,
        data: {
          card_id: cleanCardId,
          first_name: data.first_name.trim(),
          last_name: data.last_name.trim(),
          birth_date: data.birth_date,
          phone: data.phone.trim(),
          email: cleanEmail,
          university: data.university.trim(),
          faculty: data.faculty.trim(),
          study_level: data.study_level,
          wilaya: data.wilaya.trim(),
        },
      },
    });

    if (error) {
      const msg = error.message.toLowerCase();
      if (msg.includes('already registered') || msg.includes('user already exists') || msg.includes('unique')) {
        return context.redirect(
          `/register?error=${encodeURIComponent('An account with this email address or student card ID already exists. Please sign in or reset your password.')}`
        );
      }
      return context.redirect(`/register?error=${encodeURIComponent(error.message)}`);
    }

    if (signUpData?.user && Array.isArray(signUpData.user.identities) && signUpData.user.identities.length === 0) {
      return context.redirect(
        `/register?error=${encodeURIComponent('An account with this student card ID or email already exists. Please log in or reset your password.')}`
      );
    }

    // Set temporary verification cookie with masked email for /verify-email screen
    context.cookies.set('resivo_pending_email', cleanEmail, {
      path: '/',
      httpOnly: false,
      secure: origin.startsWith('https:'),
      sameSite: 'lax',
      maxAge: 3600, // 1 hour
    });

    return context.redirect(`/verify-email`);
  } catch (err: any) {
    const message = err?.message || TIMEOUT_MESSAGES.WRITE;
    return context.redirect(`/register?error=${encodeURIComponent(message)}`);
  }
};
