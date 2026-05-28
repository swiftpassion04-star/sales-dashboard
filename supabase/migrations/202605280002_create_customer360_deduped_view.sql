create or replace view public.crm_customers_deduped
with (security_invoker = true)
as
with base as (
    select
        c.*,
        coalesce(
            nullif(regexp_replace(coalesce(c.phone1::text, ''), '\D', '', 'g'), ''),
            nullif(regexp_replace(coalesce(c.phone2::text, ''), '\D', '', 'g'), ''),
            case
                when nullif(trim(coalesce(c.customer::text, '')), '') is not null
                    then 'name:' || trim(c.customer::text) || ':' || coalesce(c.product_group::text, '')
                else 'row:' || coalesce(c.customer_id::text, c.id::text)
            end
        ) as dedupe_key,
        nullif(trim(coalesce(c.sales_staff::text, '')), '') is not null as has_sales_staff
    from public.crm_customers c
),
ranked as (
    select
        base.*,
        count(*) filter (where has_sales_staff) over (partition by dedupe_key) as staffed_count,
        row_number() over (
            partition by dedupe_key
            order by
                case when updated_at is null then 1 else 0 end,
                updated_at desc,
                customer_id,
                id
        ) as dedupe_rank
    from base
)
select
    id,
    customer_id,
    customer,
    sales_staff,
    product_url,
    product_name,
    phone1,
    phone2,
    product_group,
    note,
    updated_at,
    call_1,
    call_2,
    call_3,
    dedupe_key
from ranked
where (staffed_count > 0 and has_sales_staff)
   or (staffed_count = 0 and dedupe_rank = 1);

grant select on public.crm_customers_deduped to anon, authenticated, service_role;
