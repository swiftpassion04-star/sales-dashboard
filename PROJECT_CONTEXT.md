# Project CRM Context

## Purpose
Project CRM is a Streamlit dashboard backed by Supabase. Google Sheets remain the working/assignment surface; Supabase is the central database; Streamlit is the shared dashboard for team review.

## Keep In Repo
- App: `crm_dashboard.py`, `app.py`, `pages/`
- Sync: `sync_data_raw_to_supabase.py`, `sync_to_supabase.py`
- Workflow: `.github/workflows/`
- Deployment: `requirements.txt`, `requirements-sync.txt`, `runtime.txt`
- Context: `PROJECT_CONTEXT.md`

## Data Flow
1. Staff/manager Google Sheets are edited by the team.
2. Apps Script or GitHub Actions syncs data into Supabase.
3. Streamlit reads from Supabase and renders dashboard/search pages.

## Main Tables
- `crm_customers`: active CRM customer rows from working sheets.
- `order_history`: historical DATA_RAW rows from DATA 2565-2569.
- `sync_control`, `sync_runs`: DATA_RAW sync status and control.

## Operational Rules
- Do not commit secrets, service account JSON, exports, logs, backups, or local outputs.
- Do not change dashboard/sync logic during repository cleanup.
- Use Streamlit Cloud secrets for Supabase keys and sync admin password.
- DATA_RAW sync runs on GitHub Actions every 30 minutes and can also be run manually.

## Current Workflow Files
- `sync-data.yml`: scheduled/manual DATA_RAW sync to Supabase.
- `deploy-dashboard.yml`: dashboard dependency and syntax validation.
- `cleanup.yml`: repository hygiene audit.
