import { defineMiddleware } from 'astro:middleware';
import { createSupabaseServerClient } from './lib/supabase';

export const onRequest = defineMiddleware(async (context, next) => {
  const supabase = createSupabaseServerClient(context.request, context.cookies);
  try {
    const { data } = await supabase.auth.getUser();
    context.locals.user = data.user ?? null;
  } catch {
    context.locals.user = null;
  }

  const path = context.url.pathname;
  const user = context.locals.user;

  // Unauthenticated protection
  if ((path === '/dashboard' || path.startsWith('/dashboard/')) && !user) {
    return context.redirect('/login');
  }

  if (path === '/account/add-email' && !user) {
    return context.redirect('/login');
  }

  const PROTECTED_API_ROUTES = ['/api/maintenance', '/api/room-change', '/api/profile'];
  if (PROTECTED_API_ROUTES.some((route) => path === route || path.startsWith(`${route}/`)) && !user) {
    return new Response(JSON.stringify({ error: 'Unauthorized' }), {
      status: 401,
      headers: { 'Content-Type': 'application/json' },
    });
  }

  // Legacy synthetic email gating for resident accounts
  if (user && user.email && user.email.toLowerCase().endsWith('@students.residence.local')) {
    // If accessing dashboard, redirect to link a verified real email
    if (path === '/dashboard' || path.startsWith('/dashboard/')) {
      return context.redirect('/account/add-email');
    }

    if (PROTECTED_API_ROUTES.some((route) => path === route || path.startsWith(`${route}/`))) {
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
