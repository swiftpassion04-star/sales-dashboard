create or replace view public.crm_customer_filter_options
with (security_invoker = true)
as
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

