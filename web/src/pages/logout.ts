export const prerender = false;
import type { APIRoute } from 'astro';
import { createSupabaseServerClient } from '../lib/supabase';

export const GET: APIRoute = async (context) => {
  try {
    const supabase = createSupabaseServerClient(context.request, context.cookies);
    await supabase.auth.signOut();
  } catch {
    // Session clearance must proceed even if the network is unreachable
  }
  return context.redirect('/');
};

export const POST: APIRoute = GET;
