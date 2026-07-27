-- Create crm_daily_status: marks a single calendar date as a company
-- holiday or a leave day, for the Daily Sales Matrix page (pages/daily_matrix.py).
-- Global per-date (not per-team/per-staff) -- the whole matrix row for that
-- date renders in red regardless of which team block it's in.
--
-- This migration creates the table only. It does not seed any rows.
-- DO NOT RUN until reviewed and approved -- manual psql execution only,
-- same as every other file under neon/migrations and neon/manual_sql in
-- this repo (no automated migration runner exists).

create table if not exists public.crm_daily_status (
  status_date date primary key,
  status text not null check (status in ('HOLIDAY', 'LEAVE')),
  note text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  created_by text,
  updated_by text
);

create index if not exists idx_crm_daily_status_status
  on public.crm_daily_status (status);
