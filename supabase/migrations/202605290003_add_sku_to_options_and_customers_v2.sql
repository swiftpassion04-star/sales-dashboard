alter table public.crm_product_options
    add column if not exists sku text;

create index if not exists crm_product_options_sku_idx
    on public.crm_product_options (sku);

alter table public.crm_customers_v2
    add column if not exists product_sku text;

create index if not exists crm_customers_v2_product_sku_idx
    on public.crm_customers_v2 (product_sku);
