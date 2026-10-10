-- Role of the currently authenticated user (null if none/no profile).
create or replace function auth_role() returns user_role
language sql stable security definer set search_path = public as $$
  select role from profiles where id = auth.uid();
$$;

-- True when the caller is staff or admin.
create or replace function is_staff() returns boolean
language sql stable security definer set search_path = public as $$
  select coalesce(
    (select role in ('staff','admin') from profiles where id = auth.uid()),
    false);
$$;

-- Materialize a profile for every new auth user.
-- Students self-register with a card_id in metadata; role is ALWAYS 'student'
-- here -- privilege escalation is impossible because metadata.role is ignored.
create or replace function handle_new_user() returns trigger
language plpgsql security definer set search_path = public as $$
begin
  insert into profiles (id, role) values (new.id, 'student');

  if new.raw_user_meta_data ? 'card_id' then
    insert into students (
      id, card_id, first_name, last_name, birth_date, gender, phone, email,
      university, faculty, study_level, wilaya
    ) values (
      new.id,
      new.raw_user_meta_data->>'card_id',
      new.raw_user_meta_data->>'first_name',
      new.raw_user_meta_data->>'last_name',
      (new.raw_user_meta_data->>'birth_date')::date,
      (new.raw_user_meta_data->>'gender')::gender,
      new.raw_user_meta_data->>'phone',
      nullif(new.raw_user_meta_data->>'email', ''),
      new.raw_user_meta_data->>'university',
      new.raw_user_meta_data->>'faculty',
      (new.raw_user_meta_data->>'study_level')::study_level,
      new.raw_user_meta_data->>'wilaya'
    );
  end if;

  return new;
end; $$;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function handle_new_user();
