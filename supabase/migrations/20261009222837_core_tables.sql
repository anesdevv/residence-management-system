create or replace function set_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end; $$;

create table profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  role user_role not null default 'student',
  created_at timestamptz not null default now()
);

create table staff (
  id uuid primary key references profiles(id) on delete cascade,
  full_name text not null,
  position text,
  created_at timestamptz not null default now()
);

create table rooms (
  id uuid primary key default gen_random_uuid(),
  block text not null,
  floor int not null default 0,
  number text not null,
  capacity int not null default 1 check (capacity > 0),
  gender gender not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (block, number)
);

create table students (
  id uuid primary key references profiles(id) on delete cascade,
  card_id text not null unique,
  first_name text not null,
  last_name text not null,
  birth_date date not null,
  gender gender not null,
  phone text not null,
  email text,
  university text not null,
  faculty text not null,
  study_level study_level not null,
  wilaya text not null,
  status student_status not null default 'pending',
  rejection_reason text,
  room_id uuid references rooms(id) on delete set null,
  reviewed_by uuid references staff(id) on delete set null,
  reviewed_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create trigger rooms_set_updated_at before update on rooms
  for each row execute function set_updated_at();
create trigger students_set_updated_at before update on students
  for each row execute function set_updated_at();