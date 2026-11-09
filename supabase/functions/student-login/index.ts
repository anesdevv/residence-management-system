// supabase/functions/student-login/index.ts
// Called before authentication — deployed with --no-verify-jwt.
// Authenticates students by Card ID OR Email without exposing account existence.

import { createClient } from "@supabase/supabase-js";
import { getCorsHeaders, handleCors } from "../_shared/cors.ts";
import { checkRateLimit, getClientIp } from "../_shared/throttler.ts";
import {
  isCardId,
  isEmail,
  normalizeEmail,
  maskEmail,
  safeLog,
  MAX_BODY_SIZE,
} from "../_shared/validation.ts";

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

  // Enforce body size limit
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

  const identifier = String(body?.identifier ?? "").trim();
  const password = String(body?.password ?? "");

  if (!identifier || !password) {
    return new Response(
      JSON.stringify({
        error: "invalid_credentials",
        message: "Invalid card ID/email or password.",
      }),
      {
        status: 401,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      }
    );
  }

  // Rate limiting per IP and per identifier
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

  const idThrottle = checkRateLimit(`id:${identifier.toLowerCase()}`);
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

  let authEmail: string | null = null;
  let identifierType: "card_id" | "email" | "unknown" = "unknown";

  if (isEmail(identifier)) {
    identifierType = "email";
    authEmail = normalizeEmail(identifier);
  } else if (isCardId(identifier)) {
    identifierType = "card_id";
    try {
      // Resolve student by card_id
      const { data: student } = await admin
        .from("students")
        .select("id, card_id")
        .eq("card_id", identifier)
        .maybeSingle();

      if (student?.id) {
        const { data: userResp } = await admin.auth.admin.getUserById(student.id);
        if (userResp?.user?.email) {
          authEmail = userResp.user.email;
        }
      }

      // If no student matched, construct synthetic email as plausible target for signInWithPassword
      if (!authEmail) {
        authEmail = `${identifier}@students.residence.local`;
      }
    } catch {
      authEmail = `${identifier}@students.residence.local`;
    }
  } else {
    // Neither valid card id nor valid email
    safeLog("student-login", { status: 401, ip, identifierType: "unknown" });
    return new Response(
      JSON.stringify({
        error: "invalid_credentials",
        message: "Invalid card ID/email or password.",
      }),
      {
        status: 401,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      }
    );
  }

  // Authenticate user via Supabase Auth
  try {
    const { data, error } = await anonClient.auth.signInWithPassword({
      email: authEmail,
      password,
    });

    if (error) {
      const errMsg = error.message.toLowerCase();
      // Only disclose unverified email state after the user has submitted the CORRECT password
      if (errMsg.includes("email not confirmed") || errMsg.includes("email is not confirmed")) {
        safeLog("student-login", { status: 403, ip, identifierType, error: "email_not_verified" });
        return new Response(
          JSON.stringify({
            error: "email_not_verified",
            message: "Your email is not verified yet. Please verify your email before signing in.",
            email: authEmail.includes("@students.residence.local") ? null : authEmail,
            masked_email: authEmail.includes("@students.residence.local") ? null : maskEmail(authEmail),
          }),
          {
            status: 403,
            headers: { ...corsHeaders, "Content-Type": "application/json" },
          }
        );
      }

      // Any other failure (wrong password, user doesn't exist, etc.) returns the same generic 401
      safeLog("student-login", { status: 401, ip, identifierType, error: "invalid_credentials" });
      return new Response(
        JSON.stringify({
          error: "invalid_credentials",
          message: "Invalid card ID/email or password.",
        }),
        {
          status: 401,
          headers: { ...corsHeaders, "Content-Type": "application/json" },
        }
      );
    }

    const isSynthetic = (data.user?.email ?? "").endsWith("@students.residence.local");
    safeLog("student-login", { status: 200, ip, identifierType });

    return new Response(
      JSON.stringify({
        session: data.session,
        user: data.user,
        needs_real_email: isSynthetic,
      }),
      {
        status: 200,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      }
    );
  } catch (err: any) {
    safeLog("student-login", { status: 500, ip, identifierType, error: err?.message });
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
