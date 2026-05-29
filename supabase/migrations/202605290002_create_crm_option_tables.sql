create table if not exists public.crm_product_options (
    id uuid primary key default gen_random_uuid(),
    product_group text not null,
    product_name text not null,
    is_active boolean not null default true,
    sort_order integer not null default 0,
    created_by text,
    updated_by text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint crm_product_options_unique unique (product_group, product_name)
);

create index if not exists crm_product_options_active_group_idx
    on public.crm_product_options (is_active, product_group, sort_order, product_name);

alter table public.crm_product_options enable row level security;

drop policy if exists "crm_product_options_read" on public.crm_product_options;
create policy "crm_product_options_read"
on public.crm_product_options
for select
to anon, authenticated
using (true);

drop policy if exists "crm_product_options_service_role_all" on public.crm_product_options;
create policy "crm_product_options_service_role_all"
on public.crm_product_options
for all
to service_role
using (true)
with check (true);

grant select on table public.crm_product_options to anon, authenticated;
grant select, insert, update, delete on table public.crm_product_options to service_role;

create table if not exists public.crm_staff_options (
    id uuid primary key default gen_random_uuid(),
    staff_name text not null unique,
    is_active boolean not null default true,
    sort_order integer not null default 0,
    created_by text,
    updated_by text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists crm_staff_options_active_sort_idx
    on public.crm_staff_options (is_active, sort_order, staff_name);

alter table public.crm_staff_options enable row level security;

drop policy if exists "crm_staff_options_read" on public.crm_staff_options;
create policy "crm_staff_options_read"
on public.crm_staff_options
for select
to anon, authenticated
using (true);

drop policy if exists "crm_staff_options_service_role_all" on public.crm_staff_options;
create policy "crm_staff_options_service_role_all"
on public.crm_staff_options
for all
to service_role
using (true)
with check (true);

grant select on table public.crm_staff_options to anon, authenticated;
grant select, insert, update, delete on table public.crm_staff_options to service_role;
