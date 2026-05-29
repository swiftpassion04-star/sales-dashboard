create table if not exists public.crm_customers_v2 (
    id uuid primary key default gen_random_uuid(),
    customer_id text not null unique,
    customer text not null,
    sales_staff text,
    product_url text,
    product_name text,
    phone1 text,
    phone2 text,
    product_group text,
    note text,
    source text not null default 'web',
    source_reference text,
    row_hash text,
    deleted_at timestamptz,
    deleted_by text,
    created_by text,
    updated_by text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists crm_customers_v2_phone1_idx on public.crm_customers_v2 (phone1);
create index if not exists crm_customers_v2_phone2_idx on public.crm_customers_v2 (phone2);
create index if not exists crm_customers_v2_customer_idx on public.crm_customers_v2 (customer);
create index if not exists crm_customers_v2_sales_staff_idx on public.crm_customers_v2 (sales_staff);
create index if not exists crm_customers_v2_deleted_at_idx on public.crm_customers_v2 (deleted_at);

alter table public.crm_customers_v2 enable row level security;

drop policy if exists "crm_customers_v2_read" on public.crm_customers_v2;
create policy "crm_customers_v2_read"
on public.crm_customers_v2
for select
to anon, authenticated
using (true);

grant select on table public.crm_customers_v2 to anon, authenticated;
grant select, insert, update, delete on table public.crm_customers_v2 to service_role;

create table if not exists public.data_raw_import_batches (
    id uuid primary key default gen_random_uuid(),
    original_filename text,
    worksheet_name text,
    header_row integer,
    total_rows integer not null default 0,
    imported_rows integer not null default 0,
    skipped_rows integer not null default 0,
    status text not null default 'created',
    created_by text,
    created_at timestamptz not null default now(),
    completed_at timestamptz,
    error_message text
);

alter table public.data_raw_import_batches enable row level security;

drop policy if exists "data_raw_import_batches_service_role_all" on public.data_raw_import_batches;
create policy "data_raw_import_batches_service_role_all"
on public.data_raw_import_batches
for all
to service_role
using (true)
with check (true);

grant select, insert, update, delete on table public.data_raw_import_batches to service_role;

alter table public.order_history
    add column if not exists import_batch_id uuid,
    add column if not exists imported_at timestamptz;

create index if not exists order_history_import_batch_id_idx on public.order_history (import_batch_id);
create index if not exists order_history_tracking_no_idx on public.order_history (tracking_no);

