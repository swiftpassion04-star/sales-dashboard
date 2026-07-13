ALTER TABLE public.crm_product_options
  ADD COLUMN IF NOT EXISTS image_url text NULL;
