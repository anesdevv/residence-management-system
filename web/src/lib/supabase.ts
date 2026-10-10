import { createServerClient, createBrowserClient, parseCookieHeader, serializeCookieHeader } from '@supabase/ssr';
import type { AstroCookies } from 'astro';

const URL = import.meta.env.PUBLIC_SUPABASE_URL;
const ANON = import.meta.env.PUBLIC_SUPABASE_ANON_KEY;

export function createSupabaseServerClient(
  request: Request,
  cookies: AstroCookies,
) {
  return createServerClient(URL, ANON, {
    cookies: {
      getAll() {
        return parseCookieHeader(request.headers.get('Cookie') ?? '');
      },
      setAll(cookiesToSet) {
        cookiesToSet.forEach(({ name, value, options }) =>
          cookies.set(name, value, { ...options, path: '/' }),
        );
      },
    },
  });
}

export function createSupabaseBrowserClient() {
  return createBrowserClient(URL, ANON);
}

export function cardIdToEmail(cardId: string) {
  return `${cardId.trim()}@students.residence.local`;
}
