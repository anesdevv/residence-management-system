export const prerender = false;
import type { APIRoute } from 'astro';
import { createSupabaseServerClient, cardIdToEmail } from '../../lib/supabase';
import { validateRegistration, normalizeEmail, mapEmailErrorCode } from '../../lib/validation';
import { checkRegistrationGate, getResidencePublic } from '../../lib/residence';
import { localizePath, resolveRequestLocale } from '../../lib/i18n';
import { TIMEOUT_MESSAGES } from '../../lib/timeouts';

export const POST: APIRoute = async (context) => {
  const locale = resolveRequestLocale(context.locals?.locale, context.request.headers.get('referer'));
  const registerPath = localizePath(locale, '/register');
  const loginPath = localizePath(locale, '/login');

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
    return context.redirect(`${registerPath}?error=${encodeURIComponent(errors[0])}`);
  }

  const cleanEmail = normalizeEmail(data.email);
  const cleanCardId = data.card_id.trim();

  try {
    const supabase = createSupabaseServerClient(context.request, context.cookies);
    const residence = await getResidencePublic(supabase);
    const gateError = checkRegistrationGate(residence, locale);
    if (gateError) {
      return context.redirect(`${registerPath}?error=${encodeURIComponent(gateError)}`);
    }

    // Contact email is stored only in students.email via handle_new_user() metadata;
    // auth.users uses the hidden synthetic card-ID address so zero emails are ever sent.
    const { data: signUpData, error } = await supabase.auth.signUp({
      email: cardIdToEmail(cleanCardId),
      password: data.password,
      options: {
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
      const lower = error.message.toLowerCase();
      if (
        lower.includes('email_in_use') ||
        lower.includes('idx_students_unique_lower_email') ||
        lower.includes('email_invalid') ||
        lower.includes('email_required')
      ) {
        return context.redirect(`${registerPath}?error=${encodeURIComponent(mapEmailErrorCode(error.message, locale))}`);
      }
      if (lower.includes('already registered') || lower.includes('user already exists')) {
        return context.redirect(
          `${registerPath}?error=${encodeURIComponent('An account with this student card ID already exists. Please sign in.')}`,
        );
      }
      return context.redirect(`${registerPath}?error=${encodeURIComponent(error.message)}`);
    }

    if (signUpData?.user && Array.isArray(signUpData.user.identities) && signUpData.user.identities.length === 0) {
      return context.redirect(
        `${registerPath}?error=${encodeURIComponent('An account with this student card ID already exists. Please sign in.')}`,
      );
    }

    // Sign out if signup created a session so the student returns cleanly to /login
    if (signUpData?.session) {
      await supabase.auth.signOut();
    }

    return context.redirect(`${loginPath}?registered=1`);
  } catch (err: any) {
    const message = err?.message || TIMEOUT_MESSAGES.WRITE;
    return context.redirect(`${registerPath}?error=${encodeURIComponent(message)}`);
  }
};
