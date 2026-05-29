create table if not exists public.crm_data_imports (
  id uuid primary key default gen_random_uuid(),
  dedupe_key text not null unique,
  order_date date,
  order_date_text text,
  order_id text,
  sales_channel text,
  sku text,
  product_name text,
  quantity numeric,
  price numeric,
  payment_method text,
  shipping_provider text,
  tracking_no text,
  url text,
  customer_name text,
  phone1 text,
  phone2 text,
  shipping_address text,
  subdistrict text,
  district text,
  province text,
  postcode text,
  billing_staff text,
  upsell_staff text,
  care_staff text,
  source_filename text,
  source_worksheet text,
  source_row_number integer,
  imported_by text,
  created_by text,
  updated_by text,
  deleted_at timestamp with time zone,
  deleted_by text,
  imported_at timestamp with time zone default now(),
  created_at timestamp with time zone default now(),
  updated_at timestamp with time zone default now()
);

comment on table public.crm_data_imports is
  'SQL-first CRM data table for Excel uploads from the web. Stores order and customer fields from columns A-V in one table.';

create index if not exists idx_crm_data_imports_phone1 on public.crm_data_imports (phone1) where deleted_at is null;
create index if not exists idx_crm_data_imports_phone2 on public.crm_data_imports (phone2) where deleted_at is null;
create index if not exists idx_crm_data_imports_order_id on public.crm_data_imports (order_id) where deleted_at is null;
create index if not exists idx_crm_data_imports_tracking_no on public.crm_data_imports (tracking_no) where deleted_at is null;
create index if not exists idx_crm_data_imports_customer_name on public.crm_data_imports (customer_name) where deleted_at is null;
create index if not exists idx_crm_data_imports_care_staff on public.crm_data_imports (care_staff) where deleted_at is null;
create index if not exists idx_crm_data_imports_updated_at on public.crm_data_imports (updated_at desc) where deleted_at is null;

alter table public.crm_data_imports enable row level security;

drop policy if exists "crm_data_imports_service_role_all" on public.crm_data_imports;
create policy "crm_data_imports_service_role_all"
  on public.crm_data_imports
  for all
  to service_role
  using (true)
  with check (true);

grant select, insert, update, delete on public.crm_data_imports to service_role;

drop view if exists public.crm_customer_filter_options cascade;
drop view if exists public.crm_customers_deduped cascade;
drop view if exists public.customers cascade;
drop view if exists public.orders cascade;

drop table if exists public.order_history cascade;
drop table if exists public.crm_customers cascade;
drop table if exists public.crm_customers_v2 cascade;
