# University Residence Management System (Tlemcen)

Backend: Supabase (Postgres + Auth + Storage).
Websites/clients: `web/` (Astro, students), `desktop/` (PySide6, staff).

## Backend setup
1. `npx supabase login` 
2. `npx supabase link --project-ref <your-ref>` 
3. `npx supabase db push`          # apply migrations
4. Copy `.env.example` to `.env` and fill in real keys (never commit `.env`).
5. Seed: `python scripts/seed.py`  # needs SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY
6. Tests: `pip install -r tests/requirements.txt` then `python -m pytest tests -v` 

