-- Ensure the Customer 360 source table exists and is readable by the Streamlit dashboard.
-- This matches the current Project CRM production shape in Supabase.

create table if not exists public.crm_customers (
    id bigserial primary key,
    customer_id text not null unique,
    customer text,
    sales_staff text,
    product_url text,
    product_name text,
    phone1 text,
    phone2 text,
    product_group text not null,
    call_1 text,
    call_date_1 date,
    call_2 text,
    call_date_2 date,
    call_3 text,
    call_date_3 date,
    note text,
    source_spreadsheet_id text,
    source_sheet text,
    row_hash text,
    updated_at timestamptz default now(),
    synced_at timestamptz default now()
);

create index if not exists crm_customers_customer_idx on public.crm_customers (customer);
create index if not exists crm_customers_product_group_idx on public.crm_customers (product_group);
create index if not exists crm_customers_sales_staff_idx on public.crm_customers (sales_staff);
create index if not exists crm_customers_phone1_idx on public.crm_customers (phone1);
create index if not exists crm_customers_phone2_idx on public.crm_customers (phone2);
create index if not exists crm_customers_updated_at_idx on public.crm_customers (updated_at desc);

alter table public.crm_customers enable row level security;

drop policy if exists "crm_customers_dashboard_read" on public.crm_customers;
create policy "crm_customers_dashboard_read"
on public.crm_customers
for select
to anon, authenticated
using (true);

grant usage on schema public to anon, authenticated, service_role;
grant select on table public.crm_customers to anon, authenticated;
grant select, insert, update, delete on table public.crm_customers to service_role;

comment on table public.crm_customers is
'Active CRM customer rows from manager product-group sheets for Customer 360.';

-- Rollback, if needed and only if this table was created by this migration:
-- drop table if exists public.crm_customers;
