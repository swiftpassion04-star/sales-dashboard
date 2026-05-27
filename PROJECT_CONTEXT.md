# Project CRM Context

## Purpose
Project CRM is a Streamlit dashboard backed by Supabase. Google Sheets remain the working/assignment surface; Supabase is the central database; Streamlit is the shared dashboard for team review.

## Keep In Repo
- App: `crm_dashboard.py`, `app.py`, `pages/`
- Customer 360: `customer360.py`
- Sync: `sync_data_raw_to_supabase.py`, `sync_crm_customers_to_supabase.py`, `sync_to_supabase.py`
- Workflow: `.github/workflows/`
- Database migrations: `supabase/migrations/`
- Deployment: `requirements.txt`, `requirements-sync.txt`, `runtime.txt`
- Context: `PROJECT_CONTEXT.md`

## Data Flow
1. Staff/manager Google Sheets or curated Excel/CSV uploads are prepared by the team.
2. Streamlit Excel Upload writes files to `import_staging` first, then confirmed imports update Supabase production tables.
3. Legacy GitHub Actions syncs remain available for manual fallback only where noted.
4. Streamlit reads from Supabase and renders dashboard/search pages.

## Main Tables
- `crm_customers`: active CRM customer rows from working sheets.
- `order_history`: historical DATA_RAW rows from DATA 2565-2569.
- `sync_control`, `sync_runs`: DATA_RAW sync status and control.
- `import_batches`, `import_staging`, `import_logs`, `import_backups`: Excel/CSV upload pipeline with staging, audit logs, and rollback support.

## Operational Rules
- Do not commit secrets, service account JSON, exports, logs, backups, or local outputs.
- Do not change dashboard/sync logic during repository cleanup.
- Use Streamlit Cloud secrets for Supabase keys and sync admin password.
- DATA_RAW legacy sync is manual-only to protect Supabase Free Plan limits. Prefer the Streamlit Excel Upload page for curated imports.

## Current Workflow Files
- `sync-data.yml`: manual-only legacy DATA_RAW sync to Supabase.
- `sync-crm-customers.yml`: scheduled/manual manager-sheet CRM customer sync to Supabase.
- `deploy-dashboard.yml`: dashboard dependency and syntax validation.
- `cleanup.yml`: repository hygiene audit.
