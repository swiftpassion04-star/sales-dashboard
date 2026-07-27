-- Create crm_daily_status: marks a calendar date as a company holiday or a
-- leave day, either for everyone (scope_type = 'ALL', whole matrix row
-- turns red) or for one specific staff_code (scope_type = 'STAFF', only
-- that person's cell turns red that day), for the Daily Sales Matrix page
-- (pages/daily_matrix.py).
--
-- REV 2: adds scope_type/staff_code so a single date can carry both a
-- company-wide status and any number of independent per-staff statuses at
-- once, without colliding. This migration has never been applied anywhere
-- (no NEON_DATABASE_URL / DB connection was used while authoring either
-- revision -- confirmed, not assumed), so this file is edited in place
-- rather than layered with a separate ALTER migration: there is no
-- existing data or deployed schema to preserve or migrate away from.
--
-- This migration creates the table only. It does not seed any rows.
-- DO NOT RUN until reviewed and approved -- manual psql execution only,
-- same as every other file under neon/migrations and neon/manual_sql in
-- this repo (no automated migration runner exists).

create table if not exists public.crm_daily_status (
  id bigserial primary key,
  status_date date not null,
  scope_type text not null check (scope_type in ('ALL', 'STAFF')),
  staff_code text,
  status text not null check (status in ('HOLIDAY', 'LEAVE')),
  note text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  created_by text,
  updated_by text,
  constraint crm_daily_status_scope_staff_code_chk check (
    (scope_type = 'ALL' and staff_code is null)
    or (scope_type = 'STAFF' and staff_code is not null and btrim(staff_code) <> '')
  )
);

-- One row per (date, scope, person). coalesce(staff_code, '') lets an
-- ALL-scope row (staff_code is null) and any number of distinct STAFF-scope
-- rows for the same date coexist, while still preventing a duplicate ALL
-- row or a duplicate STAFF row for the same person on the same date.
-- save_day_status's ON CONFLICT target must list this exact expression.
create unique index if not exists ux_crm_daily_status_date_scope_staff
  on public.crm_daily_status (status_date, scope_type, (coalesce(staff_code, '')));

create index if not exists idx_crm_daily_status_status
  on public.crm_daily_status (status);

create index if not exists idx_crm_daily_status_staff_code
  on public.crm_daily_status (staff_code)
  where staff_code is not null;
