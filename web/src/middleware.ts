import { defineMiddleware } from 'astro:middleware';
import { createSupabaseServerClient } from './lib/supabase';
import { DEFAULT_LOCALE, localizePath, type SupportedLocale } from './lib/i18n';

export const onRequest = defineMiddleware(async (context, next) => {
  // Locale detection
  const path = context.url.pathname;
  const originPath = context.originPathname || path;
  let locale: SupportedLocale = DEFAULT_LOCALE;

  // 1. URL path prefix (/fr or /fr/...)
  if (path === '/fr' || path.startsWith('/fr/') || originPath === '/fr' || originPath.startsWith('/fr/')) {
    locale = 'fr';
  } else {
    // 2. Cookie resivo_locale ('fr' or 'en')
    const cookieLocale = context.cookies.get('resivo_locale')?.value?.toLowerCase();
    if (cookieLocale === 'fr') {
      locale = 'fr';
    } else if (cookieLocale === 'en') {
      locale = 'en';
    } else {
      // 3. Request Accept-Language header (if starts with fr -> fr)
      const acceptLang = context.request.headers.get('accept-language')?.toLowerCase() || '';
      if (acceptLang.startsWith('fr') || acceptLang.includes(',fr')) {
        locale = 'fr';
      } else {
        // 4. Default: en
        locale = 'en';
      }
    }
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
    // If accessing dashboard, redirect to link a verified real email
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

  // Rewrite /fr/... paths internally to standard page paths
  if (
    !path.startsWith('/api/') &&
    !path.startsWith('/_astro/') &&
    (path === '/fr' || path.startsWith('/fr/'))
  ) {
    return context.rewrite(new URL(normalizedPath + context.url.search, context.url));
  }

  return next();
});
