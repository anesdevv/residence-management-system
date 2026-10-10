export const prerender = false;
import type { APIRoute } from 'astro';
import { createSupabaseServerClient, cardIdToEmail } from '../../lib/supabase';
import { validateRegistration } from '../../lib/validation';

export const POST: APIRoute = async (context) => {
  const form = await context.request.formData();
  const data = {
    card_id: String(form.get('card_id') ?? ''),
    first_name: String(form.get('first_name') ?? ''),
    last_name: String(form.get('last_name') ?? ''),
    birth_date: String(form.get('birth_date') ?? ''),
    gender: String(form.get('gender') ?? ''),
    phone: String(form.get('phone') ?? ''),
    email: String(form.get('email') ?? ''),
    university: String(form.get('university') ?? ''),
    faculty: String(form.get('faculty') ?? ''),
    study_level: String(form.get('study_level') ?? ''),
    wilaya: String(form.get('wilaya') ?? ''),
    password: String(form.get('password') ?? ''),
  };

  const errors = validateRegistration(data);
  if (errors.length) {
    return context.redirect(`/register?error=${encodeURIComponent(errors[0])}`);
  }

  const supabase = createSupabaseServerClient(context.request, context.cookies);
  const { error } = await supabase.auth.signUp({
    email: cardIdToEmail(data.card_id),
    password: data.password,
    options: {
      data: {
        card_id: data.card_id.trim(),
        first_name: data.first_name.trim(),
        last_name: data.last_name.trim(),
        birth_date: data.birth_date,
        gender: data.gender,
        phone: data.phone.trim(),
        email: data.email.trim(),
        university: data.university.trim(),
        faculty: data.faculty.trim(),
        study_level: data.study_level,
        wilaya: data.wilaya.trim(),
      },
    },
  });

  if (error) {
    return context.redirect(`/register?error=${encodeURIComponent(error.message)}`);
  }
  return context.redirect('/login?registered=1');
};
