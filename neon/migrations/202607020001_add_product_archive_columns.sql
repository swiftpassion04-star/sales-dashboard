-- Adds nullable archive metadata only. Existing rows are not changed.
-- Deploy runtime code that reads these columns only after this migration is ready in production.
ALTER TABLE public.crm_product_options
  ADD COLUMN IF NOT EXISTS archived_at timestamptz NULL,
  ADD COLUMN IF NOT EXISTS archived_by text NULL,
  ADD COLUMN IF NOT EXISTS archive_reason text NULL;
