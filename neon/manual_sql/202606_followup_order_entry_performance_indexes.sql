-- REVIEW REQUIRED
-- MANUAL EXECUTION ONLY
-- DO NOT RUN UNTIL APPROVED
--
-- Purpose:
--   Optional indexes for Follow-up and Manual Order / Order Entry screens.
--   These indexes are additive only. They do not change data or application behavior.
--
-- Notes:
--   CREATE INDEX CONCURRENTLY cannot run inside a transaction block.
--   Run one statement at a time in Neon SQL Editor during a low-traffic window.
--   If an index already exists, IF NOT EXISTS makes the statement safe to skip.

-- 1) Follow-up and customer visibility by canonical staff_code.
create index concurrently if not exists idx_crm_data_imports_valid_staff_order
  on public.crm_data_imports (staff_code, order_date desc, uploaded_at desc, id desc)
  where import_status = 'valid';

-- 2) Manual order conflict checks and customer search by phone.
create index concurrently if not exists idx_crm_data_imports_valid_phone1
  on public.crm_data_imports (phone1)
  where import_status = 'valid'
    and phone1 is not null
    and phone1 <> '';

create index concurrently if not exists idx_crm_data_imports_valid_phone2
  on public.crm_data_imports (phone2)
  where import_status = 'valid'
    and phone2 is not null
    and phone2 <> '';

-- 3) Order and SKU lookups used by Customer 360 and reporting.
create index concurrently if not exists idx_crm_data_imports_valid_order_id
  on public.crm_data_imports (order_id, uploaded_at desc, id desc)
  where import_status = 'valid'
    and order_id is not null
    and order_id <> '';

create index concurrently if not exists idx_crm_data_imports_valid_sku
  on public.crm_data_imports (sku, uploaded_at desc, id desc)
  where import_status = 'valid'
    and sku is not null
    and sku <> '';

-- 4) Sales dashboard date/owner filters.
create index concurrently if not exists idx_crm_data_imports_created_staff_sale
  on public.crm_data_imports (created_at, staff_code, sale_type);

-- 5) Follow-up status/date ordering.
create index concurrently if not exists idx_crm_lead_followups_status_date
  on public.crm_lead_followups (next_followup_date, priority, followup_status, updated_at desc);

create index concurrently if not exists idx_crm_lead_followups_customer_key_updated
  on public.crm_lead_followups (customer_key, updated_at desc);

-- 6) Product dropdown options.
create index concurrently if not exists idx_crm_product_options_active_sku_name
  on public.crm_product_options (is_active, sku, product_name);
