export const prerender = false;
import type { APIRoute } from 'astro';
import { createSupabaseServerClient } from '../../lib/supabase';
import { TIMEOUT_MESSAGES } from '../../lib/timeouts';

export const POST: APIRoute = async (context) => {
  const user = context.locals.user;
  if (!user) {
    return context.redirect('/login');
  }
  const form = await context.request.formData();
  const phone = String(form.get('phone') ?? '').trim();
  const email = String(form.get('email') ?? '').trim();

  if (!/^[0-9+\s]{6,}$/.test(phone)) {
    return context.redirect('/dashboard/profile?error=Invalid+phone');
  }
  if (email && !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) {
    return context.redirect('/dashboard/profile?error=Invalid+email');
  }

  try {
    const supabase = createSupabaseServerClient(context.request, context.cookies);
    const { error } = await supabase.rpc('update_my_contact', { p_phone: phone, p_email: email });
    if (error) {
      return context.redirect(`/dashboard/profile?error=${encodeURIComponent(error.message)}`);
    }
    return context.redirect('/dashboard/profile?updated=1');
  } catch (err: any) {
    const message = err?.message || TIMEOUT_MESSAGES.WRITE;
    return context.redirect(`/dashboard/profile?error=${encodeURIComponent(message)}`);
  }
};
