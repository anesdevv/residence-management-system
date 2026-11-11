export const prerender = false;
import type { APIRoute } from 'astro';
import { createSupabaseServerClient } from '../../lib/supabase';
import { validateContactUpdate, normalizeEmail, mapEmailErrorCode } from '../../lib/validation';
import { localizePath, resolveRequestLocale } from '../../lib/i18n';
import { TIMEOUT_MESSAGES } from '../../lib/timeouts';

export const POST: APIRoute = async (context) => {
  const locale = resolveRequestLocale(context.locals?.locale, context.request.headers.get('referer'));
  const profilePath = localizePath(locale, '/dashboard/profile');
  const loginPath = localizePath(locale, '/login');

  const user = context.locals.user;
  if (!user) {
    return context.redirect(loginPath);
  }

  const form = await context.request.formData();
  const phone = String(form.get('phone') ?? '').trim();
  const email = String(form.get('email') ?? '');
  const confirmEmail = String(form.get('confirm_email') ?? '');

  const errors = validateContactUpdate(phone, email, confirmEmail, locale);
  if (errors.length) {
    return context.redirect(`${profilePath}?error=${encodeURIComponent(errors[0])}`);
  }

  try {
    const supabase = createSupabaseServerClient(context.request, context.cookies);
    const { error } = await supabase.rpc('update_my_contact', {
      p_phone: phone,
      p_email: normalizeEmail(email),
    });

    if (error) {
      const friendly = mapEmailErrorCode(error.message, locale);
      return context.redirect(`${profilePath}?error=${encodeURIComponent(friendly)}`);
    }

    return context.redirect(`${profilePath}?updated=1`);
  } catch (err: any) {
    const message = err?.message || TIMEOUT_MESSAGES.WRITE;
    return context.redirect(`${profilePath}?error=${encodeURIComponent(message)}`);
  }
};
