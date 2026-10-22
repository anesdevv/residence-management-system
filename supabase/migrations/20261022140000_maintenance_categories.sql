-- Migration: 20261022140000_maintenance_categories.sql
-- T3: Rename "Heating" to "Others" and REMOVE "General"
-- Canonical categories everywhere: Plumbing, Electricity, Carpentry, Others (4 options).

-- 1. Extend the enum with new categories if missing.
alter type maintenance_category add value if not exists 'electricity';
alter type maintenance_category add value if not exists 'carpentry';
alter type maintenance_category add value if not exists 'others';

-- 2. Migrate existing records to the canonical set:
-- 'electrical' -> 'electricity'
-- 'furniture'  -> 'carpentry'
-- 'heating', 'general', 'other', 'internet', etc. -> 'others'
update maintenance_reports
set category = 'electricity'::maintenance_category
where category::text = 'electrical';

update maintenance_reports
set category = 'carpentry'::maintenance_category
where category::text = 'furniture';

update maintenance_reports
set category = 'others'::maintenance_category
where category::text in ('other', 'heating', 'general', 'internet');

-- Fallback for any other legacy value not in the 4 canonical options:
update maintenance_reports
set category = 'others'::maintenance_category
where category::text not in ('plumbing', 'electricity', 'carpentry', 'others');

-- 3. Replace/add CHECK constraint so only the 4 canonical values are accepted for NEW rows.
-- Note: Postgres does not safely allow dropping values from an existing enum type,
-- so legacy values ('electrical', 'furniture', 'internet', 'other') remain in the enum
-- type definition for backwards compatibility, but are strictly blocked from insertion
-- by this CHECK constraint.
alter table maintenance_reports drop constraint if exists maintenance_reports_category_check;

alter table maintenance_reports add constraint maintenance_reports_category_check
  check (category::text in ('plumbing', 'electricity', 'carpentry', 'others'));
