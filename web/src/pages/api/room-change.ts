export const prerender = false;
import type { APIRoute } from 'astro';
import { createSupabaseServerClient } from '../../lib/supabase';

export const POST: APIRoute = async (context) => {
  const user = context.locals.user!;
  const form = await context.request.formData();
  const reason = String(form.get('reason') ?? '').trim();
  const preferred = String(form.get('preferred_room_id') ?? '').trim();

  if (reason.length < 5) {
    return context.redirect('/dashboard/room-change?error=Please+describe+your+reason');
  }

  const supabase = createSupabaseServerClient(context.request, context.cookies);
  const { data: student } = await supabase
    .from('students').select('room_id').eq('id', user.id).single();

  const { error } = await supabase.from('room_change_requests').insert({
    student_id: user.id,
    current_room_id: student?.room_id ?? null,
    preferred_room_id: preferred || null,
    reason,
  });
  if (error) {
    return context.redirect(`/dashboard/room-change?error=${encodeURIComponent(error.message)}`);
  }
  return context.redirect('/dashboard/room-change?created=1');
};
