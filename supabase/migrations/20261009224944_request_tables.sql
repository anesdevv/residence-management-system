create table maintenance_reports (
  id uuid primary key default gen_random_uuid(),
  student_id uuid not null references students(id) on delete cascade,
  category maintenance_category not null,
  description text not null,
  photo_path text,
  status report_status not null default 'pending',
  staff_note text,
  handled_by uuid references staff(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table room_change_requests (
  id uuid primary key default gen_random_uuid(),
  student_id uuid not null references students(id) on delete cascade,
  current_room_id uuid references rooms(id) on delete set null,
  preferred_room_id uuid references rooms(id) on delete set null,
  reason text not null,
  status request_status not null default 'pending',
  decision_note text,
  decided_by uuid references staff(id) on delete set null,
  decided_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table official_residents (
  id uuid primary key default gen_random_uuid(),
  card_id text not null unique,
  first_name text not null,
  last_name text not null,
  birth_date date,
  gender gender,
  university text,
  faculty text,
  created_at timestamptz not null default now()
);

create trigger maintenance_reports_set_updated_at before update on maintenance_reports
  for each row execute function set_updated_at();
create trigger room_change_requests_set_updated_at before update on room_change_requests
  for each row execute function set_updated_at();
