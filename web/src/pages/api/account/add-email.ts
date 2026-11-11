export const prerender = false;
import type { APIRoute } from 'astro';
import { createSupabaseServerClient } from '../../../lib/supabase';
import { validateContactEmailPair, mapEmailErrorCode } from '../../../lib/validation';
import { localizePath, resolveRequestLocale } from '../../../lib/i18n';
import { TIMEOUT_MESSAGES } from '../../../lib/timeouts';

export const POST: APIRoute = async (context) => {
  const locale = resolveRequestLocale(context.locals?.locale, context.request.headers.get('referer'));
  const addEmailPath = localizePath(locale, '/account/add-email');
  const dashboardPath = localizePath(locale, '/dashboard');
  const loginPath = localizePath(locale, '/login');

  const user = context.locals.user;
  if (!user) {
    return context.redirect(loginPath);
  }

  const form = await context.request.formData();
  const email = String(form.get('email') ?? '');
  const confirmEmail = String(form.get('confirm_email') ?? '');

  const validation = validateContactEmailPair(email, confirmEmail, locale);
  if (!validation.ok) {
    return context.redirect(`${addEmailPath}?error=${encodeURIComponent(validation.message)}`);
  }

  try {
    const supabase = createSupabaseServerClient(context.request, context.cookies);

    const { data: student, error: studentErr } = await supabase
      .from('students')
      .select('phone')
      .eq('id', user.id)
      .maybeSingle();

    if (studentErr || !student) {
      return context.redirect(dashboardPath);
    }

    const { error } = await supabase.rpc('update_my_contact', {
      p_phone: student.phone,
      p_email: validation.email,
    });

    if (error) {
      const friendly = mapEmailErrorCode(error.message, locale);
      return context.redirect(`${addEmailPath}?error=${encodeURIComponent(friendly)}`);
    }

    return context.redirect(dashboardPath);
  } catch (err: any) {
    const message = err?.message || TIMEOUT_MESSAGES.WRITE;
    return context.redirect(`${addEmailPath}?error=${encodeURIComponent(message)}`);
  }
};
