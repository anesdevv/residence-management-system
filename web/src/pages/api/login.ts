export const prerender = false;
import type { APIRoute } from 'astro';
import { createSupabaseServerClient, cardIdToEmail } from '../../lib/supabase';
import { isCardId } from '../../lib/validation';
import { checkUserNeedsContactEmail } from '../../lib/email-gate';
import { localizePath, resolveRequestLocale, t } from '../../lib/i18n';
import { TIMEOUT_MESSAGES } from '../../lib/timeouts';

export const POST: APIRoute = async (context) => {
  const locale = resolveRequestLocale(context.locals?.locale, context.request.headers.get('referer'));
  const loginPath = localizePath(locale, '/login');
  const invalidCredsMsg = t(locale, 'errors.invalid_credentials');

  const form = await context.request.formData();
  const cardId = String(form.get('card_id') ?? form.get('identifier') ?? '').trim();
  const password = String(form.get('password') ?? '');

  if (!cardId || !password || !isCardId(cardId)) {
    return context.redirect(`${loginPath}?error=${encodeURIComponent(invalidCredsMsg)}`);
  }

  const supabaseUrl = import.meta.env.PUBLIC_SUPABASE_URL;
  const anonKey = import.meta.env.PUBLIC_SUPABASE_ANON_KEY;

  try {
    const supabase = createSupabaseServerClient(context.request, context.cookies);
    let sessionResult: any = null;
    let signedInUserId = '';
    let needsEmail: boolean | null = null;

    // Primary path (Case B): student-login resolves Card ID -> auth.users.email
    // (works for both legacy synthetic accounts and existing real-email auth accounts).
    try {
      const edgeRes = await fetch(`${supabaseUrl}/functions/v1/student-login`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'apikey': anonKey,
        },
        body: JSON.stringify({ card_id: cardId, password }),
      });

      const data = await edgeRes.json().catch(() => ({}));

      if (!edgeRes.ok) {
        const errMsg = edgeRes.status === 429 && data.message ? data.message : invalidCredsMsg;
        return context.redirect(`${loginPath}?error=${encodeURIComponent(errMsg)}`);
      }

      sessionResult = data.session;
      signedInUserId = data.user?.id ?? '';
      if (typeof data.needs_email === 'boolean') {
        needsEmail = data.needs_email;
      }
    } catch {
      // Fallback path if Edge Function is offline in local development
      const { data, error } = await supabase.auth.signInWithPassword({
        email: cardIdToEmail(cardId),
        password,
      });

      if (error || !data.session) {
        return context.redirect(`${loginPath}?error=${encodeURIComponent(invalidCredsMsg)}`);
      }

      sessionResult = data.session;
      signedInUserId = data.user?.id ?? '';
    }

    if (sessionResult) {
      await supabase.auth.setSession({
        access_token: sessionResult.access_token,
        refresh_token: sessionResult.refresh_token,
      });
    }

    const shouldRedirectToAddEmail =
      needsEmail !== null
        ? needsEmail
        : await checkUserNeedsContactEmail(supabase, signedInUserId);

    if (shouldRedirectToAddEmail) {
      return context.redirect(localizePath(locale, '/account/add-email'));
    }

    return context.redirect(localizePath(locale, '/dashboard'));
  } catch (err: any) {
    const message = err?.message || TIMEOUT_MESSAGES.READ;
    return context.redirect(`${loginPath}?error=${encodeURIComponent(message)}`);
  }
};
