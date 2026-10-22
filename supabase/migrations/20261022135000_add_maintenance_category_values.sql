-- Migration: 20261022135000_add_maintenance_category_values.sql
-- Step 1: Add new enum values to maintenance_category.
-- Note: Must be in a separate migration from data updates so Postgres commits the new enum values before they are used.

alter type maintenance_category add value if not exists 'electricity';
alter type maintenance_category add value if not exists 'carpentry';
alter type maintenance_category add value if not exists 'others';
