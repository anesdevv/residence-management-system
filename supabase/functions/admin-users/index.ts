import { createClient } from "@supabase/supabase-js";

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: CORS });

  const url = Deno.env.get("SUPABASE_URL")!;
  const serviceKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
  const anonKey = Deno.env.get("SUPABASE_ANON_KEY")!;
  const authHeader = req.headers.get("Authorization") ?? "";

  // Identify the caller using their JWT.
  const caller = createClient(url, anonKey, {
    global: { headers: { Authorization: authHeader } },
  });
  const { data: userData } = await caller.auth.getUser();
  if (!userData?.user) {
    return new Response(JSON.stringify({ error: "unauthorized" }), {
      status: 401, headers: { ...CORS, "Content-Type": "application/json" },
    });
  }

  // Only admins may proceed.
  const admin = createClient(url, serviceKey);
  const { data: profile } = await admin
    .from("profiles").select("role").eq("id", userData.user.id).single();
  if (profile?.role !== "admin") {
    return new Response(JSON.stringify({ error: "forbidden" }), {
      status: 403, headers: { ...CORS, "Content-Type": "application/json" },
    });
  }

  const body = await req.json();

  if (body.action === "create_staff") {
    const { email, password, full_name, position } = body;
    if (!email || !password || !full_name) {
      return new Response(JSON.stringify({ error: "email, password, full_name required" }), {
        status: 400, headers: { ...CORS, "Content-Type": "application/json" },
      });
    }
    const { data: created, error } = await admin.auth.admin.createUser({
      email, password, email_confirm: true,
    });
    if (error) {
      return new Response(JSON.stringify({ error: error.message }), {
        status: 400, headers: { ...CORS, "Content-Type": "application/json" },
      });
    }
    await admin.from("profiles").update({ role: "staff" }).eq("id", created.user.id);
    await admin.from("staff").insert({
      id: created.user.id, full_name, position: position ?? null,
    });
    return new Response(JSON.stringify({ id: created.user.id }), {
      status: 201, headers: { ...CORS, "Content-Type": "application/json" },
    });
  }

  if (body.action === "list_staff") {
    const { data } = await admin.from("staff").select("id, full_name, position");
    return new Response(JSON.stringify(data ?? []), {
      headers: { ...CORS, "Content-Type": "application/json" },
    });
  }

  return new Response(JSON.stringify({ error: "unknown action" }), {
    status: 400, headers: { ...CORS, "Content-Type": "application/json" },
  });
});
