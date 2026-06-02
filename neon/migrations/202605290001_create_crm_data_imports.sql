create table if not exists public.crm_data_imports (
  id bigserial primary key,
  import_batch_id uuid not null,
  source_file_name text,
  sheet_name text,
  row_number integer,
  uploaded_by text,
  uploaded_at timestamptz not null default now(),
  raw_data jsonb not null default '{}'::jsonb,
  order_id text,
  url text,
  customer_name text,
  phone1 text,
  phone2 text,
  product_name text,
  sku text,
  order_date date,
  province text,
  city text,
  postal_code text,
  tracking_no text,
  carrier text,
  order_status text,
  total_amount numeric,
  owner text,
  source_type text,
  import_status text not null default 'valid',
  validation_error text,
  dedupe_key text,
  updated_by text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table public.crm_data_imports
  add column if not exists order_id text,
  add column if not exists url text,
  add column if not exists source_type text,
  add column if not exists updated_by text;

create index if not exists idx_crm_data_imports_phone1
  on public.crm_data_imports (phone1);
create index if not exists idx_crm_data_imports_phone2
  on public.crm_data_imports (phone2);
create index if not exists idx_crm_data_imports_sku
  on public.crm_data_imports (sku);
create index if not exists idx_crm_data_imports_order_id
  on public.crm_data_imports (order_id);
create index if not exists idx_crm_data_imports_order_date
  on public.crm_data_imports (order_date);
create index if not exists idx_crm_data_imports_uploaded_at
  on public.crm_data_imports (uploaded_at desc);
create index if not exists idx_crm_data_imports_import_batch_id
  on public.crm_data_imports (import_batch_id);
create index if not exists idx_crm_data_imports_owner
  on public.crm_data_imports (owner);
create index if not exists idx_crm_data_imports_tracking_no
  on public.crm_data_imports (tracking_no);
create index if not exists idx_crm_data_imports_customer_phone_latest
  on public.crm_data_imports (
    (
      case
        when nullif(phone1, '') is not null and nullif(phone2, '') is not null then least(phone1, phone2)
        else coalesce(nullif(phone1, ''), nullif(phone2, ''), id::text)
      end
    ),
    order_date desc,
    uploaded_at desc
  )
  where import_status = 'valid';

create table if not exists public.crm_owner_assignments (
  phone_key text primary key,
  owner text not null,
  updated_by text,
  updated_at timestamptz not null default now()
);

create index if not exists idx_crm_owner_assignments_owner
  on public.crm_owner_assignments (owner);

create table if not exists public.crm_lead_followups (
  customer_key text primary key,
  customer_id text,
  customer_name text,
  phone_key text,
  phone1 text,
  phone2 text,
  product_group text,
  lead_status text,
  follow_up_status text,
  follow_up_date date,
  follow_up_note text,
  priority text,
  updated_by text,
  updated_at timestamptz not null default now(),
  created_at timestamptz not null default now()
);

create index if not exists idx_crm_lead_followups_phone_key
  on public.crm_lead_followups (phone_key);
create index if not exists idx_crm_lead_followups_updated_at
  on public.crm_lead_followups (updated_at desc);

create table if not exists public.crm_product_options (
  id bigserial primary key,
  sku text,
  product_group text not null,
  product_name text not null,
  sort_order integer not null default 0,
  is_active boolean not null default true,
  created_by text,
  updated_by text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (product_group, product_name)
);

create index if not exists idx_crm_product_options_active_sort
  on public.crm_product_options (is_active, sku, sort_order, product_group, product_name);
