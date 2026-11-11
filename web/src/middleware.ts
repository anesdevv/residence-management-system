import { defineMiddleware } from 'astro:middleware';
import { createSupabaseServerClient } from './lib/supabase';
import { DEFAULT_LOCALE, localizePath, type SupportedLocale } from './lib/i18n';
import { checkUserNeedsContactEmail } from './lib/email-gate';

export const onRequest = defineMiddleware(async (context, next) => {
  const path = context.url.pathname;
  const isFrenchPath = path === '/fr' || path.startsWith('/fr/');
  const langQuery = context.url.searchParams.get('lang')?.toLowerCase();
  const cookieLocale = context.cookies.get('resivo_locale')?.value?.toLowerCase();

  let locale: SupportedLocale = DEFAULT_LOCALE;

  if (isFrenchPath) {
    locale = 'fr';
    if (cookieLocale !== 'fr') {
      context.cookies.set('resivo_locale', 'fr', {
        path: '/',
        maxAge: 31536000,
        httpOnly: false,
        sameSite: 'lax',
      });
    }
  } else if (langQuery === 'fr') {
    locale = 'fr';
    context.cookies.set('resivo_locale', 'fr', {
      path: '/',
      maxAge: 31536000,
      httpOnly: false,
      sameSite: 'lax',
    });
    if (context.request.method === 'GET' && !path.startsWith('/api/') && !path.startsWith('/_astro/')) {
      return context.redirect(localizePath('fr', path + context.url.search));
    }
  } else if (langQuery === 'en') {
    locale = 'en';
    context.cookies.set('resivo_locale', 'en', {
      path: '/',
      maxAge: 31536000,
      httpOnly: false,
      sameSite: 'lax',
    });
  } else if (cookieLocale === 'fr') {
    locale = 'fr';
    if (
      context.request.method === 'GET' &&
      !path.startsWith('/api/') &&
      !path.startsWith('/_astro/') &&
      path !== '/logout'
    ) {
      return context.redirect(localizePath('fr', path + context.url.search));
    }
  } else if (cookieLocale === 'en') {
    locale = 'en';
  } else {
    const acceptLang = context.request.headers.get('accept-language')?.toLowerCase() || '';
    if (acceptLang.startsWith('fr') || acceptLang.includes(',fr')) {
      if (path === '/' && context.request.method === 'GET') {
        context.cookies.set('resivo_locale', 'fr', {
          path: '/',
          maxAge: 31536000,
          httpOnly: false,
          sameSite: 'lax',
        });
        return context.redirect('/fr');
      }
    }
    locale = 'en';
  }

  context.locals.locale = locale;

  const supabase = createSupabaseServerClient(context.request, context.cookies);
  try {
    const { data } = await supabase.auth.getUser();
    context.locals.user = data.user ?? null;
  } catch {
    context.locals.user = null;
  }

  const user = context.locals.user;

  // Route path normalized for auth gating (stripping /fr prefix)
  const normalizedPath = path === '/fr'
    ? '/'
    : path.startsWith('/fr/')
      ? path.slice(3)
      : path;

  const isDashboardRoute = normalizedPath === '/dashboard' || normalizedPath.startsWith('/dashboard/');
  const isAddEmailPage = normalizedPath === '/account/add-email';
  const PROTECTED_API_ROUTES = ['/api/maintenance', '/api/room-change', '/api/profile', '/api/account/add-email'];
  const isProtectedApi = PROTECTED_API_ROUTES.some(
    (route) => normalizedPath === route || normalizedPath.startsWith(`${route}/`),
  );

  // Unauthenticated protection
  if ((isDashboardRoute || isAddEmailPage) && !user) {
    return context.redirect(localizePath(locale, '/login'));
  }

  if (isProtectedApi && !user) {
    return new Response(JSON.stringify({ error: 'Unauthorized' }), {
      status: 401,
      headers: { 'Content-Type': 'application/json' },
    });
  }

  // Existing students without a contact email must complete /account/add-email first.
  // Students who already have an email and staff/admin users are never redirected.
  if (user && (isDashboardRoute || isAddEmailPage || (isProtectedApi && normalizedPath !== '/api/account/add-email'))) {
    const needsContactEmail = await checkUserNeedsContactEmail(supabase, user.id);

    if (needsContactEmail) {
      if (isDashboardRoute) {
        return context.redirect(localizePath(locale, '/account/add-email'));
      }
      if (isProtectedApi && normalizedPath !== '/api/account/add-email') {
        return new Response(
          JSON.stringify({
            error: 'contact_email_required',
            message: 'Please add a contact email address at /account/add-email to access this feature.',
          }),
          {
            status: 403,
            headers: { 'Content-Type': 'application/json' },
          },
        );
      }
    } else if (isAddEmailPage) {
      return context.redirect(localizePath(locale, '/dashboard'));
    }
  }

  return next();
});
