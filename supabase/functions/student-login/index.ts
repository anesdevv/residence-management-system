// supabase/functions/student-login/index.ts
// Called before authentication — deployed with --no-verify-jwt.
// Case B simplified: resolves student Card ID -> auth.users.email (supports both legacy
// <card_id>@students.residence.local and existing real-email auth accounts) and signs in
// with password. Contact email is never used to sign in, and no email verification exists.

import { createClient } from "@supabase/supabase-js";
import { getCorsHeaders, handleCors } from "../_shared/cors.ts";
import { checkRateLimit, getClientIp } from "../_shared/throttler.ts";
import {
  isCardId,
  safeLog,
  MAX_BODY_SIZE,
} from "../_shared/validation.ts";

const GENERIC_ERROR = {
  error: "invalid_credentials",
  message: "Invalid card ID or password.",
};

Deno.serve(async (req) => {
  const corsResponse = handleCors(req);
  if (corsResponse) return corsResponse;

  const corsHeaders = getCorsHeaders(req);
  const ip = getClientIp(req);

  if (req.method !== "POST") {
    return new Response(JSON.stringify({ error: "method_not_allowed" }), {
      status: 405,
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }

  const contentLength = Number(req.headers.get("content-length") ?? 0);
  if (contentLength > MAX_BODY_SIZE) {
    return new Response(JSON.stringify({ error: "payload_too_large" }), {
      status: 413,
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }

  let body: any;
  try {
    body = await req.json();
  } catch {
    return new Response(JSON.stringify({ error: "invalid_json" }), {
      status: 400,
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }

  const cardId = String(body?.card_id ?? body?.identifier ?? "").trim();
  const password = String(body?.password ?? "");

  if (!cardId || !password || !isCardId(cardId)) {
    safeLog("student-login", { status: 401, ip, identifierType: "unknown" });
    return new Response(JSON.stringify(GENERIC_ERROR), {
      status: 401,
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }

  const ipThrottle = checkRateLimit(`ip:${ip}`);
  if (!ipThrottle.allowed) {
    safeLog("student-login", { status: 429, ip, error: "ip_rate_limit" });
    return new Response(
      JSON.stringify({
        error: "rate_limit_exceeded",
        message: `Too many attempts. Please try again in ${ipThrottle.retryAfterSeconds} seconds.`,
        retry_after: ipThrottle.retryAfterSeconds,
      }),
      {
        status: 429,
        headers: {
          ...corsHeaders,
          "Content-Type": "application/json",
          "Retry-After": String(ipThrottle.retryAfterSeconds),
        },
      }
    );
  }

  const idThrottle = checkRateLimit(`id:${cardId}`);
  if (!idThrottle.allowed) {
    safeLog("student-login", { status: 429, ip, error: "identifier_rate_limit" });
    return new Response(
      JSON.stringify({
        error: "rate_limit_exceeded",
        message: `Too many attempts. Please try again in ${idThrottle.retryAfterSeconds} seconds.`,
        retry_after: idThrottle.retryAfterSeconds,
      }),
      {
        status: 429,
        headers: {
          ...corsHeaders,
          "Content-Type": "application/json",
          "Retry-After": String(idThrottle.retryAfterSeconds),
        },
      }
    );
  }

  const url = Deno.env.get("SUPABASE_URL")!;
  const serviceKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
  const anonKey = Deno.env.get("SUPABASE_ANON_KEY")!;

  const admin = createClient(url, serviceKey);
  const anonClient = createClient(url, anonKey);

  let authEmail = `${cardId}@students.residence.local`;
  let hasContactEmail = false;

  try {
    const { data: student } = await admin
      .from("students")
      .select("id, card_id, email")
      .eq("card_id", cardId)
      .maybeSingle();

    if (student?.id) {
      hasContactEmail = Boolean(student.email && String(student.email).trim() !== "");
      const { data: userResp } = await admin.auth.admin.getUserById(student.id);
      if (userResp?.user?.email) {
        authEmail = userResp.user.email;
      }
    }
  } catch {
    // Fall back to synthetic email for consistent timing
  }

  try {
    const { data, error } = await anonClient.auth.signInWithPassword({
      email: authEmail,
      password,
    });

    if (error || !data.session) {
      safeLog("student-login", { status: 401, ip, identifierType: "card_id", error: "invalid_credentials" });
      return new Response(JSON.stringify(GENERIC_ERROR), {
        status: 401,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    safeLog("student-login", { status: 200, ip, identifierType: "card_id" });
    return new Response(
      JSON.stringify({
        session: data.session,
        user: data.user,
        needs_email: !hasContactEmail,
      }),
      {
        status: 200,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      }
    );
  } catch (err: any) {
    safeLog("student-login", { status: 500, ip, identifierType: "card_id", error: err?.message });
    return new Response(
      JSON.stringify({
        error: "server_error",
        message: "An unexpected error occurred. Please try again later.",
      }),
      {
        status: 500,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      }
    );
  }
});
