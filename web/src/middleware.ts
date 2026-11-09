import { defineMiddleware } from 'astro:middleware';
import { createSupabaseServerClient } from './lib/supabase';
import { DEFAULT_LOCALE, localizePath, type SupportedLocale } from './lib/i18n';

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
      !path.startsWith('/auth/') &&
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

  // Unauthenticated protection
  if ((normalizedPath === '/dashboard' || normalizedPath.startsWith('/dashboard/')) && !user) {
    return context.redirect(localizePath(locale, '/login'));
  }

  if (normalizedPath === '/account/add-email' && !user) {
    return context.redirect(localizePath(locale, '/login'));
  }

  const PROTECTED_API_ROUTES = ['/api/maintenance', '/api/room-change', '/api/profile'];
  if (PROTECTED_API_ROUTES.some((route) => normalizedPath === route || normalizedPath.startsWith(`${route}/`)) && !user) {
    return new Response(JSON.stringify({ error: 'Unauthorized' }), {
      status: 401,
      headers: { 'Content-Type': 'application/json' },
    });
  }

  // Legacy synthetic email gating for resident accounts
  if (user && user.email && user.email.toLowerCase().endsWith('@students.residence.local')) {
    if (normalizedPath === '/dashboard' || normalizedPath.startsWith('/dashboard/')) {
      return context.redirect(localizePath(locale, '/account/add-email'));
    }

    if (PROTECTED_API_ROUTES.some((route) => normalizedPath === route || normalizedPath.startsWith(`${route}/`))) {
      return new Response(
        JSON.stringify({
          error: 'real_email_required',
          message: 'Please link and verify a real email address at /account/add-email to access this feature.',
        }),
        {
          status: 403,
          headers: { 'Content-Type': 'application/json' },
        }
      );
    }
  }

  return next();
});
