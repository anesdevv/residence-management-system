import { defineMiddleware } from 'astro:middleware';
import { createSupabaseServerClient } from './lib/supabase';

export const onRequest = defineMiddleware(async (context, next) => {
  const supabase = createSupabaseServerClient(context.request, context.cookies);
  const { data } = await supabase.auth.getUser();
  context.locals.user = data.user ?? null;

  const path = context.url.pathname;
  if ((path === '/dashboard' || path.startsWith('/dashboard/')) && !data.user) {
    return context.redirect('/login');
  }
  return next();
});
