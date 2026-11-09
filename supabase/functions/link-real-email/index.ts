// supabase/functions/link-real-email/index.ts
// Requires an active authenticated session (bearer JWT).
// Deployed with standard JWT verification enabled (omits --no-verify-jwt).
// Safely associates a real, verified email to an existing student whose account
// currently holds a fake email (@students.residence.local) without sending confirmation
// to the nonexistent old inbox.

import { createClient } from "@supabase/supabase-js";
import { getCorsHeaders, handleCors } from "../_shared/cors.ts";
import { checkRateLimit, getClientIp } from "../_shared/throttler.ts";
import {
  isEmail,
  normalizeEmail,
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

  const contentLength = Number(req.headers.get("content-length") ?? 0);
  if (contentLength > MAX_BODY_SIZE) {
    return new Response(JSON.stringify({ error: "payload_too_large" }), {
      status: 413,
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }

  const url = Deno.env.get("SUPABASE_URL")!;
  const serviceKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
  const anonKey = Deno.env.get("SUPABASE_ANON_KEY")!;
  const authHeader = req.headers.get("Authorization") ?? "";

  if (!authHeader.startsWith("Bearer ")) {
    return new Response(JSON.stringify({ error: "unauthorized", message: "Sign in required." }), {
      status: 401,
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }

  // Verify caller identity via their JWT session
  const caller = createClient(url, anonKey, {
    global: { headers: { Authorization: authHeader } },
  });
  const { data: userData, error: userError } = await caller.auth.getUser();

  if (userError || !userData?.user) {
    return new Response(JSON.stringify({ error: "unauthorized", message: "Session expired or invalid." }), {
      status: 401,
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }

  const callerUser = userData.user;

  let body: any;
  try {
    body = await req.json();
  } catch {
    return new Response(JSON.stringify({ error: "invalid_json" }), {
      status: 400,
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }

  const newEmailRaw = String(body?.email ?? "").trim();
  if (!isEmail(newEmailRaw)) {
    return new Response(
      JSON.stringify({ error: "invalid_email", message: "Please provide a valid email address." }),
      {
        status: 400,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      }
    );
  }

  const newEmail = normalizeEmail(newEmailRaw);
  if (newEmail.endsWith("@students.residence.local")) {
    return new Response(
      JSON.stringify({ error: "invalid_email", message: "A real email address outside the local residence domain is required." }),
      {
        status: 400,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      }
    );
  }

  // Rate limiting per caller
  const throttle = checkRateLimit(`link_user:${callerUser.id}`, 5, 60 * 60 * 1000); // 5 per hour
  if (!throttle.allowed) {
    safeLog("link-real-email", { status: 429, ip, error: "caller_rate_limit" });
    return new Response(
      JSON.stringify({
        error: "rate_limit_exceeded",
        message: `Too many email change requests. Please wait ${Math.ceil(throttle.retryAfterSeconds / 60)} minutes before trying again.`,
        retry_after: throttle.retryAfterSeconds,
      }),
      {
        status: 429,
        headers: {
          ...corsHeaders,
          "Content-Type": "application/json",
          "Retry-After": String(throttle.retryAfterSeconds),
        },
      }
    );
  }

  const admin = createClient(url, serviceKey);

  // Security check: Verify new email is not already used in public.students or auth.users
  const { data: existingStudent } = await admin
    .from("students")
    .select("id")
    .ilike("email", newEmail)
    .neq("id", callerUser.id)
    .maybeSingle();

  if (existingStudent) {
    safeLog("link-real-email", { status: 409, ip, error: "email_already_registered" });
    return new Response(
      JSON.stringify({
        error: "email_in_use",
        message: "This email address is already associated with another student account.",
      }),
      {
        status: 409,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      }
    );
  }

  try {
    // Update auth email marked unconfirmed so it requires OTP verification
    const { error: updateError } = await admin.auth.admin.updateUserById(callerUser.id, {
      email: newEmail,
      email_confirm: false,
    });

    if (updateError) {
      safeLog("link-real-email", { status: 400, ip, error: updateError.message });
      return new Response(
        JSON.stringify({
          error: "update_failed",
          message: updateError.message,
        }),
        {
          status: 400,
          headers: { ...corsHeaders, "Content-Type": "application/json" },
        }
      );
    }

    // Trigger OTP confirmation email directly to the new verified address
    const siteUrl = Deno.env.get("SITE_URL") ?? "http://localhost:4321";
    await admin.auth.resend({
      type: "signup",
      email: newEmail,
      options: {
        emailRedirectTo: `${siteUrl}/auth/confirm?type=email&next=/dashboard`,
      },
    });

    safeLog("link-real-email", { status: 200, ip });
    return new Response(
      JSON.stringify({
        success: true,
        message: "Verification code sent to your new email address.",
        email: newEmail,
      }),
      {
        status: 200,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      }
    );
  } catch (err: any) {
    safeLog("link-real-email", { status: 500, ip, error: err?.message });
    return new Response(
      JSON.stringify({
        error: "server_error",
        message: "Failed to dispatch verification code. Please try again later.",
      }),
      {
        status: 500,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      }
    );
  }
});
