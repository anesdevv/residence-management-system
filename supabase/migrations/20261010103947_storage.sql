insert into storage.buckets (id, name, public)
values ('maintenance-photos', 'maintenance-photos', false)
on conflict (id) do nothing;

create policy maint_photos_self_read on storage.objects for select
  using (bucket_id = 'maintenance-photos'
         and (storage.foldername(name))[1] = auth.uid()::text);

create policy maint_photos_self_insert on storage.objects for insert
  with check (bucket_id = 'maintenance-photos'
              and (storage.foldername(name))[1] = auth.uid()::text);

create policy maint_photos_staff_read on storage.objects for select
  using (bucket_id = 'maintenance-photos' and is_staff());
