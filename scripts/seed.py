import os
from datetime import date
from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client

# Load environment from root .env or desktop/.env
for env_path in [
    Path(__file__).resolve().parent.parent / ".env",
    Path(__file__).resolve().parent.parent / "desktop" / ".env",
]:
    if env_path.exists():
        load_dotenv(env_path)

URL = os.environ.get("SUPABASE_URL", "")
SERVICE = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
if not URL or not SERVICE:
    raise SystemExit("Error: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required in .env to run the seed script.")

sb = create_client(URL, SERVICE)



def ensure_user(email, password, role, meta=None):
    users = sb.auth.admin.list_users()
    users = getattr(users, "users", users)
    existing = next((u for u in users if u.email == email), None)
    if existing:
        uid = existing.id
    else:
        uid = sb.auth.admin.create_user({
            "email": email, "password": password, "email_confirm": True,
            "user_metadata": meta or {},
        }).user.id
    sb.table("profiles").upsert({"id": uid, "role": role}).execute()
    return uid


def main():
    admin_id = ensure_user("admin@residence.test", "Admin1234!", "admin")
    sb.table("staff").upsert({
        "id": admin_id, "full_name": "Residence Admin", "position": "Administrator",
    }).execute()

    staff_id = ensure_user("staff@residence.test", "Staff1234!", "staff")
    sb.table("staff").upsert({
        "id": staff_id, "full_name": "Amina Staff", "position": "Front desk",
    }).execute()

    rooms = [
        {"block": "A", "floor": 1, "number": "101", "capacity": 2, "gender": "male"},
        {"block": "A", "floor": 1, "number": "102", "capacity": 2, "gender": "male"},
        {"block": "B", "floor": 1, "number": "101", "capacity": 2, "gender": "female"},
    ]
    for r in rooms:
        sb.table("rooms").upsert(r, on_conflict="block,number").execute()

    # Sample student: created via admin API (metadata fills students via trigger).
    ensure_user(
        "20230001@students.residence.local", "Student1234!", "student",
        meta={
            "card_id": "20230001", "first_name": "Yacine", "last_name": "Benali",
            "birth_date": "2003-05-14", "gender": "male", "phone": "0550000001",
            "email": "", "university": "Abou Bekr Belkaid",
            "faculty": "Sciences", "study_level": "L2", "wilaya": "Tlemcen",
        },
    )

    sb.table("official_residents").upsert([
        {"card_id": "20230001", "first_name": "Yacine", "last_name": "Benali",
         "birth_date": "2003-05-14", "gender": "male",
         "university": "Abou Bekr Belkaid", "faculty": "Sciences"},
        {"card_id": "20230002", "first_name": "Nadia", "last_name": "Cherif",
         "birth_date": "2002-11-02", "gender": "female",
         "university": "Abou Bekr Belkaid", "faculty": "Medicine"},
        {"card_id": "20230003", "first_name": "Omar", "last_name": "Tazi",
         "birth_date": "2001-01-20", "gender": "male",
         "university": "Abou Bekr Belkaid", "faculty": "Law"},
    ], on_conflict="card_id").execute()

    print("Seed complete.")


if __name__ == "__main__":
    main()
