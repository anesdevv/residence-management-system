export const prerender = false;
import type { APIRoute } from 'astro';
import { createSupabaseServerClient } from '../lib/supabase';

export const GET: APIRoute = async (context) => {
  const supabase = createSupabaseServerClient(context.request, context.cookies);
  await supabase.auth.signOut();
  return context.redirect('/');
};

export const POST: APIRoute = GET;

