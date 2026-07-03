-- Warning: rolling back after products have been archived permanently loses archive metadata.
ALTER TABLE public.crm_product_options
  DROP COLUMN IF EXISTS archive_reason,
  DROP COLUMN IF EXISTS archived_by,
  DROP COLUMN IF EXISTS archived_at;
