create or replace view public.crm_customer_filter_options as
select 'product_group'::text as option_type, product_group::text as option_value
from public.crm_customers
where nullif(product_group, '') is not null
group by product_group
union all
select 'sales_staff'::text as option_type, sales_staff::text as option_value
from public.crm_customers
where nullif(sales_staff, '') is not null
group by sales_staff;

grant select on public.crm_customer_filter_options to anon, authenticated, service_role;

create index if not exists idx_crm_customers_phone1
    on public.crm_customers (phone1);

create index if not exists idx_crm_customers_phone2
    on public.crm_customers (phone2);

create index if not exists idx_crm_customers_customer_id
    on public.crm_customers (customer_id);

create index if not exists idx_crm_customers_product_group
    on public.crm_customers (product_group);

create index if not exists idx_crm_customers_sales_staff
    on public.crm_customers (sales_staff);

create index if not exists idx_order_history_phone1
    on public.order_history (phone1);

create index if not exists idx_order_history_phone2
    on public.order_history (phone2);

create index if not exists idx_order_history_order_id
    on public.order_history (order_id);

create index if not exists idx_order_history_postcode
    on public.order_history (postcode);

do $$
begin
    if exists (
        select 1 from information_schema.columns
        where table_schema = 'public'
          and table_name = 'order_history'
          and column_name = 'customer_id'
    ) then
        execute 'create index if not exists idx_order_history_customer_id on public.order_history (customer_id)';
    end if;

    if exists (
        select 1 from information_schema.columns
        where table_schema = 'public'
          and table_name = 'order_history'
          and column_name = 'shipment_id'
    ) then
        execute 'create index if not exists idx_order_history_shipment_id on public.order_history (shipment_id)';
    end if;
end $$;
