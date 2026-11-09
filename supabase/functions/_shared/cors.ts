// supabase/functions/_shared/cors.ts

const ALLOWED_ORIGINS = [
  "http://localhost:4321",
  "http://127.0.0.1:4321",
  "http://localhost:3000",
  "http://127.0.0.1:3000",
  "https://resivo.univ-tlemcen.dz",
];

export function getCorsHeaders(req?: Request): Record<string, string> {
  const origin = req?.headers.get("origin") ?? "";
  const allowOrigin = ALLOWED_ORIGINS.includes(origin) ? origin : (origin || "*");

  return {
    "Access-Control-Allow-Origin": allowOrigin,
    "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
  };
}

export function handleCors(req: Request): Response | null {
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: getCorsHeaders(req) });
  }
  return null;
}
