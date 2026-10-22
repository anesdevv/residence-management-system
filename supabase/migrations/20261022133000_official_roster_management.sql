-- Migration: 20261022133000_official_roster_management.sql
-- Description: Management RPCs for official_residents (add, update, delete, clear) with admin role verification.

-- 1. Helper / RPC to add a single official resident entry
create or replace function public.add_official_resident(
  p_card_id text,
  p_first_name text,
  p_last_name text,
  p_birth_date date default null,
  p_gender text default null,
  p_university text default null,
  p_faculty text default null
) returns public.official_residents
language plpgsql
security definer
set search_path = public, auth, pg_temp
as $$
declare
  v_card_id text;
  v_first_name text;
  v_last_name text;
  v_gender text;
  v_university text;
  v_faculty text;
  v_row public.official_residents;
begin
  -- Validate caller is admin
  if not exists (
    select 1 from public.profiles
    where id = auth.uid() and role = 'admin'
  ) then
    raise exception 'admin only';
  end if;

  v_card_id := trim(coalesce(p_card_id, ''));
  v_first_name := trim(coalesce(p_first_name, ''));
  v_last_name := trim(coalesce(p_last_name, ''));
  v_university := nullif(trim(coalesce(p_university, '')), '');
  v_faculty := nullif(trim(coalesce(p_faculty, '')), '');
  v_gender := lower(trim(coalesce(p_gender, '')));

  if v_card_id = '' then
    raise exception 'Card ID is required';
  end if;
  if v_first_name = '' then
    raise exception 'First name is required';
  end if;
  if v_last_name = '' then
    raise exception 'Last name is required';
  end if;

  if v_gender = '' then
    v_gender := null;
  elsif v_gender not in ('male', 'female') then
    raise exception 'Gender must be male, female, or empty';
  end if;

  if exists (select 1 from public.official_residents where card_id = v_card_id) then
    raise exception 'Card ID % already exists in official roster', v_card_id;
  end if;

  insert into public.official_residents (
    card_id, first_name, last_name, birth_date, gender, university, faculty
  ) values (
    v_card_id, v_first_name, v_last_name, p_birth_date, v_gender::gender, v_university, v_faculty
  )
  returning * into v_row;

  return v_row;
end;
$$;

-- 2. RPC to update an existing official resident entry
create or replace function public.update_official_resident(
  p_old_card_id text,
  p_card_id text,
  p_first_name text,
  p_last_name text,
  p_birth_date date default null,
  p_gender text default null,
  p_university text default null,
  p_faculty text default null
) returns public.official_residents
language plpgsql
security definer
set search_path = public, auth, pg_temp
as $$
declare
  v_old_card_id text;
  v_card_id text;
  v_first_name text;
  v_last_name text;
  v_gender text;
  v_university text;
  v_faculty text;
  v_row public.official_residents;
begin
  -- Validate caller is admin
  if not exists (
    select 1 from public.profiles
    where id = auth.uid() and role = 'admin'
  ) then
    raise exception 'admin only';
  end if;

  v_old_card_id := trim(coalesce(p_old_card_id, ''));
  v_card_id := trim(coalesce(p_card_id, ''));
  v_first_name := trim(coalesce(p_first_name, ''));
  v_last_name := trim(coalesce(p_last_name, ''));
  v_university := nullif(trim(coalesce(p_university, '')), '');
  v_faculty := nullif(trim(coalesce(p_faculty, '')), '');
  v_gender := lower(trim(coalesce(p_gender, '')));

  if v_old_card_id = '' then
    raise exception 'Original Card ID is required';
  end if;
  if v_card_id = '' then
    raise exception 'Card ID is required';
  end if;
  if v_first_name = '' then
    raise exception 'First name is required';
  end if;
  if v_last_name = '' then
    raise exception 'Last name is required';
  end if;

  if v_gender = '' then
    v_gender := null;
  elsif v_gender not in ('male', 'female') then
    raise exception 'Gender must be male, female, or empty';
  end if;

  if not exists (select 1 from public.official_residents where card_id = v_old_card_id) then
    raise exception 'Official resident not found with card ID %', v_old_card_id;
  end if;

  if v_card_id <> v_old_card_id and exists (
    select 1 from public.official_residents where card_id = v_card_id
  ) then
    raise exception 'Card ID % already exists in official roster', v_card_id;
  end if;

  update public.official_residents
  set card_id = v_card_id,
      first_name = v_first_name,
      last_name = v_last_name,
      birth_date = p_birth_date,
      gender = v_gender::gender,
      university = v_university,
      faculty = v_faculty
  where card_id = v_old_card_id
  returning * into v_row;

  return v_row;
end;
$$;

-- 3. RPC to delete listed entries
create or replace function public.delete_official_residents(
  p_card_ids text[]
) returns int
language plpgsql
security definer
set search_path = public, auth, pg_temp
as $$
declare
  v_count int;
begin
  if not exists (
    select 1 from public.profiles
    where id = auth.uid() and role = 'admin'
  ) then
    raise exception 'admin only';
  end if;

  if p_card_ids is null or array_length(p_card_ids, 1) is null then
    return 0;
  end if;

  delete from public.official_residents
  where card_id = any(p_card_ids);

  get diagnostics v_count = row_count;
  return v_count;
end;
$$;

-- 4. RPC to clear ALL entries
create or replace function public.clear_official_residents() returns int
language plpgsql
security definer
set search_path = public, auth, pg_temp
as $$
declare
  v_count int;
begin
  if not exists (
    select 1 from public.profiles
    where id = auth.uid() and role = 'admin'
  ) then
    raise exception 'admin only';
  end if;

  delete from public.official_residents;

  get diagnostics v_count = row_count;
  return v_count;
end;
$$;

-- Permissions
grant execute on function public.add_official_resident(text, text, text, date, text, text, text) to authenticated;
grant execute on function public.update_official_resident(text, text, text, text, date, text, text, text) to authenticated;
grant execute on function public.delete_official_residents(text[]) to authenticated;
grant execute on function public.clear_official_residents() to authenticated;
