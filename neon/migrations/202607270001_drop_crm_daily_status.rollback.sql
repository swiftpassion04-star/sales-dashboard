-- Roll back only the table created by the paired migration.

DROP TABLE IF EXISTS public.crm_daily_status;
