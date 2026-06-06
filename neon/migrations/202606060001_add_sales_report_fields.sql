-- Add manual sales reporting fields for CRM orders.
-- Run this migration in Neon before using Amount / Address / Sale Type
-- in the manual order form and Dashboard sales report.

alter table public.crm_data_imports
  add column if not exists sale_type text,
  add column if not exists amount numeric(12,2),
  add column if not exists address text;

create index if not exists idx_crm_data_imports_created_staff_sale
  on public.crm_data_imports (created_at, staff_code, sale_type);

create index if not exists idx_crm_data_imports_owner_created_sale
  on public.crm_data_imports (owner, created_at, sale_type);
