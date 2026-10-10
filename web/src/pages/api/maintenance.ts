export const prerender = false;
import type { APIRoute } from 'astro';
import { createSupabaseServerClient } from '../../lib/supabase';

const CATEGORIES = ['plumbing', 'electrical', 'furniture', 'internet', 'other'];

export const POST: APIRoute = async (context) => {
  const user = context.locals.user!;
  const form = await context.request.formData();
  const category = String(form.get('category') ?? '');
  const description = String(form.get('description') ?? '').trim();
  const photo = form.get('photo');

  if (!CATEGORIES.includes(category) || description.length < 5) {
    return context.redirect('/dashboard/maintenance?error=Invalid+report');
  }

  const supabase = createSupabaseServerClient(context.request, context.cookies);
  let photo_path: string | null = null;

  if (photo instanceof File && photo.size > 0) {
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
