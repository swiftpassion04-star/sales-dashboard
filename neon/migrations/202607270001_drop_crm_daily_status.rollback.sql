-- Roll back only the table created by the paired migration. Safe at either
-- revision of that migration (single-scope or ALL/STAFF-scope) -- dropping
-- the table removes all its columns/constraints/indexes regardless of
-- schema version, and it has never been applied anywhere.

DROP TABLE IF EXISTS public.crm_daily_status;
