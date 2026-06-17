# CRM Workflow Logic Audit

Audit date: 2026-06-17

Repository: `github_sales_dashboard`

Latest observed HEAD: `9c9b81c fix: guard follow-up cache clearing`

## 1. Audit Scope

This document records a read-only workflow logic audit for the main CRM Streamlit application.

The audit covered these workflow areas:

- Import Excel
- Manual Order
- Customers
- Customer 360 / Customer Detail
- Follow-up
- Product Master
- Dashboard
- Users / Auth / Permission
- Cache / Performance
- Neon / Database Access

The audit was performed from source files only. No database changes, migrations, app actions, staging, commits, or pushes were performed as part of this documentation step.

Files intentionally inspected as source context include:

- `PROJECT_CONTEXT.md`
- `app.py`
- `pages/import_excel.py`
- `pages/dashboard.py`
- `pages/customers.py`
- `pages/customer_detail.py`
- `pages/followup.py`
- `pages/products.py`
- `pages/users.py`
- `ui/import_excel_ui.py`
- `ui/manual_order_ui.py`
- `ui/customer_export_ui.py`
- `auth_utils.py`
- `permissions.py`
- `nav_utils.py`
- `neon_utils.py`

Files intentionally not modified:

- All existing Python source files
- `PROJECT_CONTEXT.md`
- `neon/manual_sql/202606_staff_code_normalization_plan.sql`
- Any database or migration file

## 2. Executive Summary

The CRM app is a Streamlit application with Neon as the CRM database and Supabase used only for authentication/session login. The canonical CRM workflows are split across Streamlit pages and shared helper modules.

The current workflow structure is mostly centralized around `neon_utils.py` for database reads/writes, `auth_utils.py` for login/session handling, and `permissions.py` for role gates. The highest workflow sensitivity areas are Import Excel, Manual Order, Customers owner assignment, Follow-up order popup, Product Master writes, and Users role management.

Recent performance work added low-risk option/dropdown caches and targeted cache clears for owner option caches. A hotfix also guarded Follow-up cache clearing to avoid runtime `AttributeError`. The remaining cache risks are mostly around older global clears, role cache staleness, and write paths that may not yet clear every related cached view.

No workflow logic changes are recommended without a separate focused phase and validation pass. Auth, permission, role, session, and database schema behavior should remain out of scope unless explicitly requested.

## 3. Current Dirty Files

Dirty/untracked files observed before creating this audit document:

```text
 M PROJECT_CONTEXT.md
 M neon/manual_sql/202606_staff_code_normalization_plan.sql
?? apps_script/
```

These files were pre-existing and were not touched by this audit.

Known untracked `apps_script/` contents from repository inspection:

```text
apps_script/order_validation_webapp/Code.gs
apps_script/order_validation_webapp/Index.html
```

This audit created only:

```text
CRM_WORKFLOW_LOGIC_AUDIT.md
```

## 4. Module Map

| Area | Primary files | Main responsibility |
| --- | --- | --- |
| App shell | `app.py`, `nav_utils.py`, `crm_theme.py` | Main dashboard entrypoint, navigation, shared visual theme |
| Import Excel | `pages/import_excel.py`, `ui/import_excel_ui.py`, `neon_utils.py` | Excel upload, field mapping, duplicate analysis, import history, batch delete |
| Manual Order | `pages/import_excel.py`, `ui/manual_order_ui.py`, `neon_utils.py` | Manual order entry, line items, owner/staff assignment, order writes |
| Customers | `pages/customers.py`, `ui/customer_export_ui.py`, `neon_utils.py` | Customer search/filter/list, export, owner assignment, URL assignment, follow-up marker |
| Customer 360 | `pages/customer_detail.py`, `neon_utils.py` | Customer profile, latest order, follow-up update, order/product history |
| Follow-up | `pages/followup.py`, `neon_utils.py` | Follow-up queue, filters, follow-up dialog, add-order popup |
| Product Master | `pages/products.py`, `neon_utils.py` | Product option create/import/edit/disable |
| Dashboard | `app.py`, `pages/dashboard.py`, `neon_utils.py` | KPI cards and sales report |
| Users/Auth/Permission | `auth_utils.py`, `permissions.py`, `pages/users.py`, `neon_utils.py` | Supabase login/session, role loading, role write UI, permission gates |
| Database access | `neon_utils.py` | Neon connection, schema checks, reads, writes, cache helpers |

Legacy or non-canonical risk note:

- `customer360.py` still exists with older cache decorators, but project context says not to revive it. The canonical Customer 360 page is `pages/customer_detail.py`.

## 5. Import Excel Workflow

Primary files:

- `pages/import_excel.py`
- `ui/import_excel_ui.py`
- `neon_utils.py`

Workflow summary:

1. User enters the Import Excel page through `pages/import_excel.py`.
2. `require_login()` and `current_user()` establish the authenticated user context.
3. `can_import_excel(user)` controls Excel import/history access.
4. `can_add_manual_order(user)` controls whether the manual order panel is available.
5. `neon.require_neon_config()` and `neon.ensure_crm_data_imports_schema()` run before CRM import/manual order tools render.
6. Excel import uses `render_excel_import(user)` in `ui/import_excel_ui.py`.
7. Upload accepts `.xlsx`, reads workbook sheets, allows selecting sheet/header row, maps source columns to CRM fields, validates required fields, builds records, analyzes duplicates, previews rows, and imports confirmed records.
8. Import history uses `render_import_history()` and allows deleting an import batch after confirmation.

Important logic:

- Required import mapping includes `customer_name` and at least one phone field.
- Import records are built through `neon.build_record_from_mapping`.
- Duplicate and merge behavior is analyzed by `neon.analyze_import_records(records)`.
- The actual write path is `neon.insert_import_records(records, batch_size=BATCH_SIZE)`.
- Batch delete uses `neon.delete_import_batch(selected_batch)`.

Cache behavior:

- After successful import, `ui/import_excel_ui.py` calls global `st.cache_data.clear()`.
- After deleting an import batch, `ui/import_excel_ui.py` calls global `st.cache_data.clear()`.
- This supports correctness for many downstream caches, but can cause a heavier rerun after import/delete.

Workflow risk:

- `ensure_crm_data_imports_schema()` can create/alter schema at runtime if missing columns/tables are detected. This is convenient but is still schema mutation behavior and should stay carefully controlled.
- Replacing global cache clear in import/delete paths should not be done casually because import affects many downstream views: Customers, Follow-up, Dashboard, owner options, products/order context, and Customer 360.
- Import mapping and duplicate handling are business-critical. Do not change SQL or merge logic without a dedicated audit and test plan.

## 6. Manual Order Workflow

Primary files:

- `pages/import_excel.py`
- `ui/manual_order_ui.py`
- `neon_utils.py`

Workflow summary:

1. Manual Order is rendered from the Import Excel page for users allowed by `can_add_manual_order(user)`.
2. Editors/admin-like users can choose the owner/staff from active owner options.
3. Non-editor telesell users are locked to their own staff identity.
4. Product rows are added from active product options.
5. The form validates order id, customer name, phone, owner/staff, and line items.
6. Non-editor users are blocked if the entered phone belongs to another owner.
7. Save calls `neon.upsert_manual_order_items(payload, manual_items)`.

Important logic:

- Owner options come from `neon.fetch_owner_user_options(active_only=True)`.
- Product options come from `neon.fetch_product_options()` filtered for active products.
- Existing owner conflicts are checked through `neon.fetch_existing_owner_rows_by_phones`.
- Save uses `force_owner_update=bool(is_editor)`, allowing editors to update owner data more broadly than non-editors.

Cache behavior:

- After save, current targeted clears include:
  - `neon.fetch_followup_filter_options`
  - `neon.fetch_filter_options`
  - `neon.fetch_sales_report_owner_options`
  - `neon.fetch_crm_owner_options`

Workflow risk:

- Manual Order writes both customer/order-facing data and owner/staff fields. Cache invalidation must keep Customers, Follow-up, Dashboard owner dropdowns, and Users owner mapping options reasonably fresh.
- Owner conflict handling is a workflow safety control for non-editor users and should not be changed without a business approval phase.
- Direct use of shared cache clear helpers should remain guarded by validation, as recent production hotfixes were related to cache clear helper imports/availability.

## 7. Customers Workflow

Primary files:

- `pages/customers.py`
- `ui/customer_export_ui.py`
- `neon_utils.py`

Workflow summary:

1. User enters Customers page after login.
2. Filter options are loaded through `fetch_filter_options()`.
3. Customer page rows are loaded through `fetch_customer_page(filters, page_size, page, user, enforce_user_scope=False)`.
4. Customer export is visible only to users allowed by `can_export_customers(user)`.
5. Customer rows can be opened inline for detail.
6. Follow marker updates are allowed by `can_edit_customer_follow_action`.
7. Owner assignment is available through `can_assign_customer_owner(user)`.
8. URL assignment is available through the page action controls.

Important logic:

- Owner assignment uses `assign_owner_to_order_record(...)`.
- URL assignment uses `assign_url_to_phones(...)`.
- Follow-up marker writes through `upsert_lead_followup(payload)`.
- Owner assignment options use `fetch_owner_user_options(active_only=True)`.

Cache behavior:

- Owner assignment clears:
  - `fetch_filter_options`
  - `fetch_sales_report_owner_options`
  - `fetch_crm_owner_options`
- Follow marker updates rerun the page but do not appear to clear follow-up-related caches in the same explicit way.
- URL assignment reruns after save but does not appear to clear a targeted cached Customer 360/order cache, because canonical Customer 360 helpers are not currently cached.

Workflow risk:

- `enforce_user_scope=False` on `fetch_customer_page` appears intentional in current workflow, with action-level permissions controlling write capabilities. Changing this would be high risk because it could alter who can see customers.
- Follow marker update and URL assignment cache behavior should be audited before adding any new invalidation, because they touch customer/follow-up views.
- Export access must remain permission-gated.

## 8. Customer 360 Workflow

Primary files:

- `pages/customer_detail.py`
- `neon_utils.py`

Workflow summary:

1. Customer 360 is opened through `pages/customer_detail.py` with query parameter `customer_id`.
2. User must be logged in.
3. Base customer data is loaded through `fetch_customer_360_base(customer_id)`.
4. `can_manage_all(user)` can view all customers.
5. Non-manager users can view only if their `staff_code` matches the customer row.
6. The page loads latest follow-up, order history, product history, URL, and owner context.
7. Follow-up save updates lead/follow-up state and reruns the page.

Important logic:

- Customer permission is enforced before rendering detail data.
- Local `fetch_customer_followup(customer)` directly queries `crm_lead_followups`.
- Order history uses `fetch_customer_360_orders(phone1, phone2, limit=20)`.
- Product history uses `fetch_customer_360_products(phone1, phone2, limit=50)`.
- Follow-up save uses `upsert_lead_followup(payload)`.

Cache behavior:

- Follow-up save clears `fetch_followup_filter_options` through `clear_cached_data_functions`.
- Customer 360 helper queries in the canonical page are not currently cached.

Workflow risk:

- Customer 360 is permission-sensitive because it exposes detailed customer/order context. Avoid caching data here unless the cache key includes the correct customer/user scope and a clear invalidation path exists.
- Do not revive or route back to legacy `customer360.py`.
- Adding cache to Customer 360 should be a separate audit-only phase first.

## 9. Follow-up Workflow

Primary files:

- `pages/followup.py`
- `neon_utils.py`

Workflow summary:

1. User enters Follow-up page after login.
2. `can_view_followup(user)` gates page access.
3. Filters use `fetch_followup_filter_options(user)`.
4. Owners filter is visible only when `can_view_followup_owner_filter(user)` allows it.
5. Rows are loaded through `fetch_followup_page(filters, user, page_size, page)`.
6. Follow-up dialog updates lead status, priority, next follow-up date, and notes.
7. Add-order popup lets a user create a manual order from a follow-up row when owner/staff data is available.

Important logic:

- Follow-up save uses `upsert_lead_followup(payload)`.
- Follow-up order popup uses `upsert_manual_order_items(...)`.
- Order popup performs owner conflict checks for users without manage-all capability.
- The recent hotfix added a local guarded cache clear helper to avoid `AttributeError` when clearing follow-up caches.

Cache behavior:

- Follow-up save clears `fetch_followup_filter_options` through the guarded helper.
- Follow-up order popup clears:
  - `fetch_followup_filter_options`
  - `fetch_filter_options`
  - `fetch_sales_report_owner_options`
  - `fetch_crm_owner_options`

Workflow risk:

- `pages/followup.py` appears to contain duplicate `render_followup_table` function definitions, where the later definition overrides the earlier one. This is not necessarily a runtime bug, but it is a maintainability risk and should be audited before refactoring.
- Follow-up dialog and order popup share customer/order data assumptions. Do not change save logic or owner conflict behavior without focused tests.
- Cache helper import/availability has already caused production issues, so future cache edits should include runtime import validation and page smoke tests.

## 10. Product Master Workflow

Primary files:

- `pages/products.py`
- `neon_utils.py`

Workflow summary:

1. Product page requires login.
2. `can_edit_products(auth_user)` controls whether the user can edit product master data.
3. All logged-in users may view product options, but only allowed users can create/import/edit/disable.
4. Product list is loaded through `neon.fetch_product_options()`.
5. Create, import, edit, and disable actions write through `neon_utils.py` helpers.

Important logic:

- Create uses `neon.upsert_product_options([...])`.
- Import expects an Excel file with columns `SKU`, `product_name`, and `product_group`.
- Import builds a preview and inserts only rows that are not already exact matches.
- Edit/disable use `neon.update_product_option(...)`.

Cache behavior:

- Product list uses `fetch_product_options` with TTL cache.
- Product writes currently call global `st.cache_data.clear()`.

Workflow risk:

- Product Master affects Manual Order and Follow-up order popup product dropdowns.
- Global cache clear after product writes is safe for correctness but less efficient.
- Replacing global clear with targeted clears should be a separate phase because product options are used by multiple workflows.

## 11. Dashboard Workflow

Primary files:

- `app.py`
- `pages/dashboard.py`
- `neon_utils.py`

Workflow summary:

1. `app.py` renders the main dashboard after login.
2. KPI data is loaded through `fetch_dashboard_kpis(user)`.
3. `pages/dashboard.py` renders a fuller dashboard/sales report page.
4. Editors/admin-like users can use owner filters.
5. Sales report data is loaded through `fetch_sales_report(user, start_date, end_date, owner_filter)`.

Important logic:

- Dashboard owner options use `fetch_sales_report_owner_options(user)`.
- Sales report warns if required columns are missing and references migration readiness.
- Dashboard data is role-aware through user context.

Cache behavior:

- `fetch_sales_report_owner_options(user)` is cached for 300 seconds.
- Dashboard KPI and report query caching should be handled carefully because the data is operational and date/user scoped.

Workflow risk:

- Dashboard owner options may be stale for up to 300 seconds after import/manual order/owner changes.
- Sales report behavior depends on database schema readiness.
- Do not cache role-sensitive dashboard result sets without a clear key and invalidation model.

## 12. Users / Auth / Permission Workflow

Primary files:

- `auth_utils.py`
- `permissions.py`
- `pages/users.py`
- `neon_utils.py`

Workflow summary:

1. Supabase is used for authentication and session token handling.
2. CRM role data is loaded from Neon, not Supabase.
3. `auth_utils.require_login()` restores session or presents login UI.
4. `fetch_user_role(email)` maps authenticated email to CRM role information.
5. `permissions.py` centralizes workflow gates.
6. Users page is editable only for users allowed by `can_edit_users(user)`.
7. User role create/update/deactivate writes to Neon role tables.

Important permission gates:

- `can_manage_all`: `ADMIN` or `EDITOR`
- `can_edit_users`: manage-all only
- `can_edit_products`: manage-all only
- `can_import_excel`: manage-all only
- `can_add_manual_order`: manage-all or telesell
- `can_export_customers`: `EDITOR` only
- `can_assign_customer_owner`: `EDITOR` only
- `can_view_followup`: editor or scoped telesell/staff user
- `can_view_followup_owner_filter`: `EDITOR` only

Cache behavior:

- `auth_utils.fetch_user_role(email)` is cached for 600 seconds.
- `neon_utils.fetch_user_roles()` should remain uncached unless there is a clear and explicit invalidation model.
- Users page currently calls global `st.cache_data.clear()` after role writes.

Workflow risk:

- Auth/session/role logic is high sensitivity. Do not modify without a separate audit and explicit approval.
- Role cache staleness may briefly affect permission visibility after a role update, though Users page global clear helps within the same runtime.
- Do not cache permission/session objects without a clear path.

## 13. Cache Inventory

Current relevant active cache decorators:

| Function | File | TTL | Notes |
| --- | --- | --- | --- |
| `fetch_user_role` | `auth_utils.py` | 600s | Role lookup; permission-sensitive |
| `neon_table_exists` | `neon_utils.py` | 300s | Schema existence helper |
| `neon_column_exists` | `neon_utils.py` | 300s | Schema existence helper |
| `fetch_sales_report_owner_options` | `neon_utils.py` | 300s | Dashboard owner dropdown |
| `fetch_filter_options` | `neon_utils.py` | 900s | Customers filter dropdown |
| `fetch_import_history` | `neon_utils.py` | 300s | Import history |
| `fetch_followup_filter_options` | `neon_utils.py` | 900s | Follow-up filters |
| `fetch_product_options` | `neon_utils.py` | 900s | Product dropdown/master list |
| `fetch_crm_owner_options` | `neon_utils.py` | 900s | Users/admin owner mapping dropdown |
| `fetch_owner_user_options` | `neon_utils.py` | 900s | Manual Order/owner assignment user options |

Current global cache clear points in canonical workflows:

| File | Trigger | Behavior |
| --- | --- | --- |
| `ui/import_excel_ui.py` | Import success | `st.cache_data.clear()` |
| `ui/import_excel_ui.py` | Delete import batch success | `st.cache_data.clear()` |
| `pages/products.py` | Product create/import/edit/disable | `st.cache_data.clear()` |
| `pages/users.py` | User create/update/deactivate | `st.cache_data.clear()` |
| `pages/system_status.py` | Manual refresh action | `st.cache_data.clear()` |

Current targeted cache clear points:

| File | Trigger | Caches cleared |
| --- | --- | --- |
| `ui/manual_order_ui.py` | Manual Order save | Follow-up filters, Customers filters, Dashboard owner options, CRM owner options |
| `pages/followup.py` | Follow-up save | Follow-up filters |
| `pages/followup.py` | Follow-up order popup save | Follow-up filters, Customers filters, Dashboard owner options, CRM owner options |
| `pages/customers.py` | Owner assignment update | Customers filters, Dashboard owner options, CRM owner options |
| `pages/customer_detail.py` | Customer 360 follow-up save | Follow-up filters |

Cache risks:

- Global clears are correct but can slow first rerun after write actions.
- Role/permission cache should remain conservative.
- Customer 360 query caching should not be introduced without user-scope and customer-scope analysis.
- Legacy `customer360.py` cache decorators should not be used as the basis for canonical workflow changes.

## 14. Database / Neon Access Summary

Primary database module:

- `neon_utils.py`

Connection and configuration helpers:

- `get_neon_database_url`
- `require_neon_config`
- `neon_connection`
- `neon_table_exists`
- `neon_column_exists`
- `ensure_crm_data_imports_schema`

Primary Neon-backed tables observed in source:

- `public.crm_data_imports`
- `public.crm_lead_followups`
- `public.crm_product_options`
- `public.crm_user_roles`
- `public.crm_orders`
- `public.crm_order_items`
- `public.crm_owner_assignments`
- `public.crm_staff_options`

Key write paths:

| Workflow | Write helper |
| --- | --- |
| Import Excel | `insert_import_records`, import plan helpers, latest-customer update helpers |
| Delete import batch | `delete_import_batch` |
| Manual Order | `upsert_manual_order`, `upsert_manual_order_items` |
| Follow-up save | `upsert_lead_followup` |
| Customer owner assignment | `assign_owner_to_phones`, `assign_owner_to_order_record` |
| Customer URL assignment | `assign_url_to_phones` |
| Product Master | `upsert_product_options`, `insert_product_options`, `update_product_option`, `delete_product_option` |
| Users | `upsert_user_role`, `set_user_role_active` |

Key read paths:

| Workflow | Read helper |
| --- | --- |
| Customers | `fetch_customer_page`, `fetch_customer_export_rows`, `fetch_filter_options` |
| Customer 360 | `fetch_customer_360_base`, `fetch_customer_360_orders`, `fetch_customer_360_products` |
| Follow-up | `fetch_followup_page`, `fetch_followup_filter_options` |
| Dashboard | `fetch_dashboard_kpis`, `fetch_sales_report`, `fetch_sales_report_owner_options` |
| Products | `fetch_product_options` |
| Users | `fetch_user_roles`, `fetch_crm_owner_options`, `fetch_owner_user_options` |
| Import history | `fetch_import_history` |

Database risk:

- `ensure_crm_data_imports_schema()` can mutate schema at runtime. This should not be expanded without explicit approval.
- Any SQL or schema change should remain out of performance/cache phases unless separately approved.
- Staff identity must use canonical staff/user fields and must not be derived from owner Thai names.

## 15. Risk Register

| Risk | Area | Severity | Why it matters | Recommended handling |
| --- | --- | --- | --- | --- |
| Runtime schema mutation through `ensure_crm_data_imports_schema()` | Import/Neon | HIGH | Can create/alter tables or indexes at runtime | Keep as-is unless a migration-control phase is approved |
| Auth/session/role cache staleness | Users/Auth | HIGH | Could temporarily affect permission visibility | Do not add new auth/session caches; audit role invalidation separately |
| Duplicate `render_followup_table` definitions | Follow-up | MEDIUM | Later definition overrides earlier definition, increasing maintenance risk | Audit-only cleanup phase before any refactor |
| Global cache clears remain in Import/Product/Users | Cache/Performance | MEDIUM | Correct but can slow reruns after writes | Replace only in small targeted phases with validation |
| Customer follow marker update may not clear follow-up caches explicitly | Customers/Follow-up | MEDIUM | Follow-up filters/list could remain stale until rerun/TTL | Audit write impact before adding invalidation |
| Customer URL update does not clear broader customer/detail caches | Customers/Customer 360 | MEDIUM | URL display may stale if future caches are added | Keep as-is now; include in future cache map |
| Dashboard sales report depends on schema readiness | Dashboard/Neon | MEDIUM | Missing columns alter dashboard behavior | Keep warning path; do not change SQL without migration approval |
| Product Master global clear | Product/Cache | LOW | Correct but broader than necessary | Future targeted clear phase can reduce overhead |
| Users page global clear | Users/Cache | LOW to MEDIUM | Correct but broad; role-sensitive | Handle carefully, avoid caching role lists |
| Untracked `apps_script/` | Working tree hygiene | LOW | Could be accidentally committed | Decide whether to ignore, track, or move in a separate hygiene task |
| Legacy `customer360.py` | Routing/Cache | LOW to MEDIUM | Old route/helper code could confuse future work | Do not revive; document canonical route |

## 16. Recommended Next Phases

Recommended phased work, in priority order:

1. Phase 4.1 - Cache invalidation audit for remaining Customers write paths
   - Focus: follow marker save and URL assignment.
   - Mode: audit-only first.
   - Reason: these are write actions that may affect Follow-up and Customer 360 views.

2. Phase 4.2 - Product Master targeted cache clear
   - Focus: replace Product Master global clears with targeted `fetch_product_options.clear()` and any dependent dropdown clears.
   - Mode: audit-only, then small implementation.
   - Reason: Product Master writes are lower frequency but currently clear all caches.

3. Phase 4.3 - Import Excel global clear replacement feasibility
   - Focus: determine whether import/delete batch can move from global clear to a complete targeted clear set.
   - Mode: audit-only first.
   - Reason: Import touches the broadest set of CRM views and is higher risk.

4. Phase 4.4 - Users/Auth cache safety audit
   - Focus: role cache invalidation, `fetch_user_role`, and Users page global clear behavior.
   - Mode: audit-only only until approved.
   - Reason: auth/permission/session logic is high sensitivity.

5. Phase 4.5 - Follow-up module cleanup audit
   - Focus: duplicate `render_followup_table` definitions and cache helper consistency.
   - Mode: audit-only first.
   - Reason: cleanup could affect page rendering if done casually.

6. Phase 4.6 - Customer 360 performance audit
   - Focus: query frequency and safe cache candidates.
   - Mode: audit-only first.
   - Reason: data is customer-specific and permission-sensitive.

7. Working Tree Hygiene - `apps_script/` decision
   - Focus: decide whether `apps_script/` should be tracked, ignored, moved outside repo, or deleted locally.
   - Mode: user decision required before any action.

## 17. No-change Confirmation

This audit document was created with the following safety constraints:

- No existing code file was intentionally modified.
- `PROJECT_CONTEXT.md` was read only and not modified.
- `neon/manual_sql/202606_staff_code_normalization_plan.sql` was not modified.
- `apps_script/` was not modified or deleted.
- No database command was run.
- No migration was run.
- No auth, permission, or session logic was modified.
- No SQL logic was modified.
- No UI/UX behavior was modified.
- No files were staged.
- No commit was created.
- No push was performed.

Expected git status after this document is created:

```text
 M PROJECT_CONTEXT.md
 M neon/manual_sql/202606_staff_code_normalization_plan.sql
?? CRM_WORKFLOW_LOGIC_AUDIT.md
?? apps_script/
```
