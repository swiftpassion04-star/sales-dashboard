-- Excel/CSV upload pipeline for CRM Dashboard.
-- Flow: upload file -> import_staging -> validate/confirm -> order_history or crm_customers.

create table if not exists public.import_batches (
    id uuid primary key,
    target_table text not null check (target_table in ('order_history', 'crm_customers')),
    original_filename text,
    worksheet_name text,
    status text not null default 'staged'
        check (status in ('staged', 'importing', 'success', 'failed', 'rolled_back', 'cleaned')),
    total_rows integer not null default 0,
    valid_rows integer not null default 0,
    invalid_rows integer not null default 0,
    duplicate_rows integer not null default 0,
    imported_rows integer not null default 0,
    skipped_rows integer not null default 0,
    overwrite_confirmed boolean not null default false,
    incremental_import boolean not null default true,
    created_by text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    completed_at timestamptz
);

create table if not exists public.import_staging (
    id bigserial primary key,
    batch_id uuid not null references public.import_batches(id) on delete cascade,
    target_table text not null check (target_table in ('order_history', 'crm_customers')),
    row_number integer not null,
    raw_record jsonb not null default '{}'::jsonb,
    mapped_record jsonb not null default '{}'::jsonb,
    unique_key text,
    row_hash text,
    validation_errors text[] not null default array[]::text[],
    duplicate_in_file boolean not null default false,
    duplicate_in_database boolean not null default false,
    status text not null default 'pending'
        check (status in ('pending', 'valid', 'invalid', 'imported', 'skipped', 'failed')),
    error_message text,
    created_at timestamptz not null default now(),
    imported_at timestamptz
);

create table if not exists public.import_logs (
    id bigserial primary key,
    batch_id uuid references public.import_batches(id) on delete cascade,
    level text not null default 'info' check (level in ('info', 'warning', 'error')),
    message text not null,
    detail jsonb,
    created_at timestamptz not null default now()
);

create table if not exists public.import_backups (
    id bigserial primary key,
    batch_id uuid not null references public.import_batches(id) on delete cascade,
    target_table text not null check (target_table in ('order_history', 'crm_customers')),
    unique_key text not null,
    previous_record jsonb not null,
    created_at timestamptz not null default now(),
    unique (batch_id, target_table, unique_key)
);

alter table public.order_history
    add column if not exists import_batch_id uuid,
    add column if not exists imported_at timestamptz;

alter table public.crm_customers
    add column if not exists import_batch_id uuid,
    add column if not exists imported_at timestamptz;

create index if not exists import_batches_created_at_idx on public.import_batches (created_at desc);
create index if not exists import_batches_status_idx on public.import_batches (status);
create index if not exists import_staging_batch_idx on public.import_staging (batch_id);
create index if not exists import_staging_unique_key_idx on public.import_staging (target_table, unique_key);
create index if not exists import_staging_status_idx on public.import_staging (status);
create index if not exists import_logs_batch_idx on public.import_logs (batch_id, created_at desc);
create index if not exists import_backups_batch_idx on public.import_backups (batch_id);
create index if not exists order_history_import_batch_idx on public.order_history (import_batch_id);
create index if not exists crm_customers_import_batch_idx on public.crm_customers (import_batch_id);

alter table public.import_batches enable row level security;
alter table public.import_staging enable row level security;
alter table public.import_logs enable row level security;
alter table public.import_backups enable row level security;

drop policy if exists "import_batches_service_role_all" on public.import_batches;
create policy "import_batches_service_role_all"
on public.import_batches
for all
to service_role
using (true)
with check (true);

drop policy if exists "import_staging_service_role_all" on public.import_staging;
create policy "import_staging_service_role_all"
on public.import_staging
for all
to service_role
using (true)
with check (true);

drop policy if exists "import_logs_service_role_all" on public.import_logs;
create policy "import_logs_service_role_all"
on public.import_logs
for all
to service_role
using (true)
with check (true);

drop policy if exists "import_backups_service_role_all" on public.import_backups;
create policy "import_backups_service_role_all"
on public.import_backups
for all
to service_role
using (true)
with check (true);

grant usage on schema public to service_role;
grant select, insert, update, delete on table public.import_batches to service_role;
grant select, insert, update, delete on table public.import_staging to service_role;
grant select, insert, update, delete on table public.import_logs to service_role;
grant select, insert, update, delete on table public.import_backups to service_role;
grant usage, select on sequence public.import_staging_id_seq to service_role;
grant usage, select on sequence public.import_logs_id_seq to service_role;
grant usage, select on sequence public.import_backups_id_seq to service_role;

comment on table public.import_batches is 'Upload batches staged from Streamlit before confirmation into CRM production tables.';
comment on table public.import_staging is 'Validated mapped rows waiting for user confirmation before import.';
comment on table public.import_logs is 'Audit log for Excel/CSV upload, validation, import, cleanup, and rollback actions.';
comment on table public.import_backups is 'Previous records captured before confirmed overwrite imports for best-effort rollback.';

-- Rollback, if needed:
-- drop table if exists public.import_logs;
-- drop table if exists public.import_backups;
-- drop table if exists public.import_staging;
-- drop table if exists public.import_batches;
-- alter table public.order_history drop column if exists import_batch_id, drop column if exists imported_at;
-- alter table public.crm_customers drop column if exists import_batch_id, drop column if exists imported_at;
