# Supabase Usage Optimization Notes

## Current findings

- `order_history` is the largest table: about 362k rows and 488 MB total size.
- `crm_customers` is the second largest table: about 35k rows and 59 MB total size.
- No active `import_*`, `staging`, `temp`, `backup`, or `log` tables currently exist in the production Supabase project.
- The customer report must keep these customer fields available: `customer_id`, `customer`, `sales_staff`, `product_url`, `product_name`, `phone1`, `phone2`, `product_group`, `note`, `updated_at`, `call_1`, `call_2`, `call_3`.
- The customer detail/order history must keep these order fields available: `source_key`, `order_id`, `year`, `month`, `day`, `date_text`, `customer`, `phone1`, `phone2`, `address`, `subdistrict`, `district`, `province`, `postcode`, `sales_staff`, `upsell_staff`, `care_staff`, `product_group`, `total_sales`, `order_status`, `payment_method`, `delivery_status`, `shipping`, `tracking_no`, `channel_url`, `products`, `note`, `source_sheet`, `year_file`, `synced_at`.

## Safe changes applied

- Removed remaining app-side `select=*` from Customer 360 lead/follow-up loading.
- Removed `select=*` from sync control reads.
- Changed Supabase write requests that do not need returned rows to `return=minimal`.
- Customer order lookup now tries indexed exact phone matches before falling back to slower fuzzy phone matching.
- Disabled the unused Upload Excel page by moving it out of Streamlit `pages/`.

## Retention options for `order_history`

1. Keep all rows, optimize reads only.
   - Lowest operational risk.
   - Does not reduce database size.

2. Archive old years to CSV/Google Drive, then delete from Supabase after verification.
   - Highest database-size reduction.
   - Requires a tested restore workflow before deleting.

3. Keep recent 24-36 months in `order_history`, move older years to `order_history_archive`.
   - Keeps CRM detail fast for recent work.
   - Still uses database size unless archive is exported outside Supabase.

4. Create summary/materialized tables for dashboards and keep raw order history only for customer detail search.
   - Best egress reduction for dashboards.
   - Needs sync workflow changes and scheduled refresh.

Recommended next step: use option 1 now, then design option 2 with export verification before any delete.

