export const prerender = false;
import type { APIRoute } from 'astro';
import { createSupabaseServerClient } from '../../lib/supabase';

export const GET: APIRoute = async (context) => {
  const user = context.locals.user;
  if (!user) {
    return new Response(JSON.stringify({ error: 'Unauthorized' }), {
      status: 401,
      headers: { 'Content-Type': 'application/json' },
    });
  }

  const path = context.url.searchParams.get('path');
  if (!path || typeof path !== 'string' || path.includes('..')) {
    return new Response(JSON.stringify({ error: 'Invalid path' }), {
      status: 400,
      headers: { 'Content-Type': 'application/json' },
    });
  }

  try {
    const supabase = createSupabaseServerClient(context.request, context.cookies);

    // Ensure user has access: either their own photo or authorized staff
    const isOwner = path.startsWith(`${user.id}/`);
    if (!isOwner) {
      const { data: profile } = await supabase
        .from('profiles')
        .select('role')
        .eq('id', user.id)
        .single();
      const role = String(profile?.role || '').toLowerCase();
      if (role !== 'staff' && role !== 'admin') {
        return new Response(JSON.stringify({ error: 'Forbidden' }), {
          status: 403,
          headers: { 'Content-Type': 'application/json' },
        });
      }
    }

    // 1-hour validity signed URL
    const expiresIn = 3600;
    const { data, error } = await supabase.storage
      .from('maintenance-photos')
      .createSignedUrl(path, expiresIn);

    if (error || !data?.signedUrl) {
      return new Response(JSON.stringify({ error: error?.message || 'Could not create signed URL' }), {
        status: 502,
        headers: { 'Content-Type': 'application/json' },
      });
    }

    return new Response(
      JSON.stringify({
        url: data.signedUrl,
        expiresAt: Date.now() + expiresIn * 1000,
        path,
      }),
      {
        status: 200,
        headers: {
          'Content-Type': 'application/json',
          'Cache-Control': 'private, max-age=3000',
        },
      },
    );
  } catch (err: any) {
    return new Response(JSON.stringify({ error: err?.message || 'Internal server error' }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' },
    });
  }
};
