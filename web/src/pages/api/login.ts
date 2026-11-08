export const prerender = false;
import type { APIRoute } from 'astro';
import { createSupabaseServerClient, cardIdToEmail } from '../../lib/supabase';
import { TIMEOUT_MESSAGES } from '../../lib/timeouts';

export const POST: APIRoute = async (context) => {
  const form = await context.request.formData();
  const cardId = String(form.get('card_id') ?? '').trim();
  const password = String(form.get('password') ?? '');

  try {
    const supabase = createSupabaseServerClient(context.request, context.cookies);
    const { error } = await supabase.auth.signInWithPassword({
      email: cardIdToEmail(cardId),
      password,
    });

    if (error) {
      return context.redirect(`/login?error=${encodeURIComponent('Invalid card ID or password.')}`);
    }
    return context.redirect('/dashboard');
  } catch (err: any) {
    const message = err?.message || TIMEOUT_MESSAGES.READ;
    return context.redirect(`/login?error=${encodeURIComponent(message)}`);
  }
};
