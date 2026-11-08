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
  if ((path === '/dashboard' || path.startsWith('/dashboard/')) && !context.locals.user) {
    return context.redirect('/login');
  }

  const PROTECTED_API_ROUTES = ['/api/maintenance', '/api/room-change', '/api/profile'];
  if (PROTECTED_API_ROUTES.some((route) => path === route || path.startsWith(`${route}/`)) && !context.locals.user) {
    return new Response(JSON.stringify({ error: 'Unauthorized' }), {
      status: 401,
      headers: { 'Content-Type': 'application/json' },
    });
  }

  return next();
});
