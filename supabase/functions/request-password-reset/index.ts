// supabase/functions/request-password-reset/index.ts
// Called before authentication — deployed with --no-verify-jwt.
// Initiates password recovery without enumerating whether an account exists.

import { createClient } from "@supabase/supabase-js";
import { getCorsHeaders, handleCors } from "../_shared/cors.ts";
import { checkRateLimit, getClientIp } from "../_shared/throttler.ts";
import {
  isCardId,
  isEmail,
  normalizeEmail,
  safeLog,
  MAX_BODY_SIZE,
} from "../_shared/validation.ts";

const GENERIC_RESPONSE = {
  success: true,
  message: "If an account exists for this card ID or email, password recovery instructions have been sent to the verified email address on file.",
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

  const identifier = String(body?.identifier ?? "").trim();
  if (!identifier) {
    // Return generic success to prevent probing empty inputs
    return new Response(JSON.stringify(GENERIC_RESPONSE), {
      status: 200,
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }

  // Rate limiting per IP and per identifier
  const ipThrottle = checkRateLimit(`pw_ip:${ip}`);
  if (!ipThrottle.allowed) {
    safeLog("request-password-reset", { status: 429, ip, error: "ip_rate_limit" });
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

  const idThrottle = checkRateLimit(`pw_id:${identifier.toLowerCase()}`);
  if (!idThrottle.allowed) {
    safeLog("request-password-reset", { status: 429, ip, error: "identifier_rate_limit" });
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
  const admin = createClient(url, serviceKey);

  let targetEmail: string | null = null;

  try {
    if (isEmail(identifier)) {
      targetEmail = normalizeEmail(identifier);
    } else if (isCardId(identifier)) {
      const { data: student } = await admin
        .from("students")
        .select("id")
        .eq("card_id", identifier)
        .maybeSingle();

      if (student?.id) {
        const { data: userResp } = await admin.auth.admin.getUserById(student.id);
        if (userResp?.user?.email) {
          targetEmail = userResp.user.email;
        }
      }
    }

    // Only dispatch recovery email if a valid, non-synthetic address is found
    if (targetEmail && !targetEmail.endsWith("@students.residence.local")) {
      const siteUrl = Deno.env.get("SITE_URL") ?? "http://localhost:4321";
      await admin.auth.resetPasswordForEmail(targetEmail, {
        redirectTo: `${siteUrl}/auth/confirm?type=recovery&next=/reset-password`,
      });
    }

    safeLog("request-password-reset", { status: 200, ip });
    return new Response(JSON.stringify(GENERIC_RESPONSE), {
      status: 200,
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  } catch (err: any) {
    // If rate limit error from Supabase Auth or email provider
    const msg = (err?.message ?? "").toLowerCase();
    if (msg.includes("rate limit") || msg.includes("over_email_send_rate_limit")) {
      safeLog("request-password-reset", { status: 429, ip, error: "provider_rate_limit" });
      return new Response(
        JSON.stringify({
          error: "rate_limit_exceeded",
          message: "The email delivery service is currently busy or rate limited. Please try again shortly.",
        }),
        {
          status: 429,
          headers: { ...corsHeaders, "Content-Type": "application/json" },
        }
      );
    }

    safeLog("request-password-reset", { status: 200, ip, error: "generic_suppressed_error" });
    // Always return generic response to prevent timing/probing leaks
    return new Response(JSON.stringify(GENERIC_RESPONSE), {
      status: 200,
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }
});
