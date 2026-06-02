alter table public.crm_product_options
  add column if not exists active boolean not null default true;

update public.crm_product_options
set active = is_active
where active is distinct from is_active;

alter table public.crm_data_imports
  add column if not exists quantity integer;

create table if not exists public.crm_orders (
  id bigserial primary key,
  order_id text not null,
  customer_name text,
  phone1 text,
  phone2 text,
  url text,
  owner text,
  staff_code text,
  source_type text not null default 'manual',
  created_by text,
  updated_by text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create unique index if not exists ux_crm_orders_order_phone
  on public.crm_orders (
    order_id,
    (coalesce(phone1, '')),
    (coalesce(phone2, ''))
  );

create table if not exists public.crm_order_items (
  id bigserial primary key,
  crm_order_id bigint references public.crm_orders(id) on delete cascade,
  crm_data_import_id bigint,
  order_id text not null,
  sku text not null,
  product_name text not null,
  qty integer not null default 1 check (qty > 0),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create unique index if not exists ux_crm_order_items_order_sku
  on public.crm_order_items (crm_order_id, sku);

create index if not exists idx_crm_product_options_active_sku
  on public.crm_product_options (active, sku, product_name);

create index if not exists idx_crm_orders_order_id
  on public.crm_orders (order_id);

create index if not exists idx_crm_orders_phone1
  on public.crm_orders (phone1);

create index if not exists idx_crm_orders_phone2
  on public.crm_orders (phone2);

create index if not exists idx_crm_order_items_order_id
  on public.crm_order_items (order_id);

create index if not exists idx_crm_order_items_sku
  on public.crm_order_items (sku);
