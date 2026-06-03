-- Run this migration in Neon before importing products where the same
-- product name/group can exist under different SKU values.
--
-- New duplicate rule:
--   Duplicate only when SKU + product_name + product_group all match.

alter table public.crm_product_options
  drop constraint if exists crm_product_options_product_group_product_name_key;

do $$
begin
  alter table public.crm_product_options
    add constraint crm_product_options_sku_group_name_key
    unique (sku, product_group, product_name);
exception
  when duplicate_object then null;
end $$;

create index if not exists idx_crm_product_options_sku_group_name
  on public.crm_product_options (sku, product_group, product_name);
