from supabase import create_client, Client
from .config import SUPABASE_URL, SUPABASE_ANON_KEY


def make_client() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_ANON_KEY)


def sign_in(client: Client, email: str, password: str):
    return client.auth.sign_in_with_password({"email": email, "password": password})


def current_role(client: Client) -> str | None:
    user = client.auth.get_user().user
    if not user:
        return None
    resp = client.table("profiles").select("role").eq("id", user.id).single().execute()
    return (resp.data or {}).get("role")


def room_occupancy(client: Client) -> dict[str, int]:
    resp = client.table("students").select("room_id").eq("status", "active").execute()
    counts: dict[str, int] = {}
    for row in resp.data or []:
        rid = row["room_id"]
        if rid:
            counts[rid] = counts.get(rid, 0) + 1
    return counts


def official_lookup(client: Client) -> dict[str, dict]:
    resp = client.table("official_residents").select("*").execute()
    return {r["card_id"]: r for r in (resp.data or [])}
