export const prerender = false;
import type { APIRoute } from 'astro';
import { createSupabaseServerClient } from '../../lib/supabase';

export const POST: APIRoute = async (context) => {
  const user = context.locals.user;
  if (!user) {
    return context.redirect('/login');
  }
  const form = await context.request.formData();
  const reason = String(form.get('reason') ?? '').trim();
  const preferred = String(form.get('preferred_room_id') ?? '').trim();

  if (reason.length < 5) {
    return context.redirect('/dashboard/room-change?error=Please+describe+your+reason');
  }

  const supabase = createSupabaseServerClient(context.request, context.cookies);
  const { data: student } = await supabase
    .from('students')
    .select('room_id, status, gender')
    .eq('id', user.id)
    .single();

  if (student?.status !== 'active' || !student?.room_id) {
    return context.redirect(
      `/dashboard/room-change?error=${encodeURIComponent(
        'Your account is pending review. Only active residents with an assigned room can request a room change.',
      )}`,
    );
  }

  const { data: existingPending } = await supabase
    .from('room_change_requests')
    .select('id')
    .eq('student_id', user.id)
    .eq('status', 'pending')
    .maybeSingle();

  if (existingPending) {
    return context.redirect(
      `/dashboard/room-change?error=${encodeURIComponent(
        'You already have a pending room transfer request undergoing administrative review.',
      )}`,
    );
  }

  if (preferred) {
    if (preferred === student.room_id) {
      return context.redirect(
        `/dashboard/room-change?error=${encodeURIComponent(
          'Preferred room cannot be your current room.',
        )}`,
      );
    }
    const { data: targetRoom } = await supabase
      .from('rooms')
      .select('gender')
      .eq('id', preferred)
      .maybeSingle();

    if (!targetRoom) {
      return context.redirect(
        `/dashboard/room-change?error=${encodeURIComponent('The selected room does not exist.')}`,
      );
    }
    if (targetRoom.gender !== student.gender) {
      return context.redirect(
        `/dashboard/room-change?error=${encodeURIComponent(
          'Selected room is not designated for your gender block.',
        )}`,
      );
    }
  }

  const { error } = await supabase.from('room_change_requests').insert({
    student_id: user.id,
    current_room_id: student.room_id,
    preferred_room_id: preferred || null,
    reason,
  });
  if (error) {
    return context.redirect(`/dashboard/room-change?error=${encodeURIComponent(error.message)}`);
  }
  return context.redirect('/dashboard/room-change?created=1');
};
