export const prerender = false;
import type { APIRoute } from 'astro';
import { createSupabaseServerClient } from '../../lib/supabase';

import { isAllowedCategory } from '../../lib/maintenance';
const ALLOWED_PHOTO_TYPES = ['image/jpeg', 'image/png', 'image/webp', 'image/gif'];
const MAX_PHOTO_BYTES = 4 * 1024 * 1024; // 4MB

export const POST: APIRoute = async (context) => {
  const user = context.locals.user;
  if (!user) {
    return context.redirect('/login');
  }
  const form = await context.request.formData();
  const category = String(form.get('category') ?? '');
  const description = String(form.get('description') ?? '').trim();
  const photo = form.get('photo');

  if (!isAllowedCategory(category) || description.length < 5) {
    return context.redirect('/dashboard/maintenance?error=Invalid+report');
  }

  const supabase = createSupabaseServerClient(context.request, context.cookies);

  const { data: student } = await supabase
    .from('students')
    .select('status')
    .eq('id', user.id)
    .single();

  if (student?.status !== 'active') {
    return context.redirect(
      `/dashboard/maintenance?error=${encodeURIComponent(
        'Your account is pending review. Only active approved residents can submit maintenance reports.',
      )}`,
    );
  }

  let photo_path: string | null = null;

  if (photo instanceof File && photo.size > 0) {
    if (photo.size > MAX_PHOTO_BYTES) {
      return context.redirect(
        `/dashboard/maintenance?error=${encodeURIComponent('Photo exceeds 4MB size limit.')}`,
      );
    }
    if (!ALLOWED_PHOTO_TYPES.includes(photo.type)) {
      return context.redirect(
        `/dashboard/maintenance?error=${encodeURIComponent(
          'Invalid photo type. Only JPEG, PNG, WebP, and GIF images are allowed.',
        )}`,
      );
    }
    const ext = photo.name.split('.').pop()?.toLowerCase() || 'jpg';
    const path = `${user.id}/${crypto.randomUUID()}.${ext}`;
    const { error: upErr } = await supabase.storage
      .from('maintenance-photos')
      .upload(path, photo, { contentType: photo.type });
    if (upErr) {
      return context.redirect(`/dashboard/maintenance?error=${encodeURIComponent(upErr.message)}`);
    }
    photo_path = path;
  }

  const { error } = await supabase.from('maintenance_reports').insert({
    student_id: user.id, category, description, photo_path,
  });
  if (error) {
    return context.redirect(`/dashboard/maintenance?error=${encodeURIComponent(error.message)}`);
  }
  return context.redirect('/dashboard/maintenance?created=1');
};
