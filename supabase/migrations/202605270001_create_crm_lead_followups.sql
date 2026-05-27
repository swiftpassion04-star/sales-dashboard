-- Create an isolated Lead / Follow-up table for Customer 360.
-- This table stores workflow state edited in the Streamlit CRM UI without
-- changing synced customer source rows in public.crm_customers.

create table if not exists public.crm_lead_followups (
    id bigserial primary key,
    customer_key text not null unique,
    customer_id text,
    customer_name text,
    phone_key text,
    phone1 text,
    phone2 text,
    product_group text,
    lead_status text not null default 'new',
    follow_up_status text not null default 'none',
    follow_up_date date,
    follow_up_note text,
    priority text not null default 'normal',
    updated_by text,
    updated_at timestamptz not null default now(),
    created_at timestamptz not null default now(),
    constraint crm_lead_followups_lead_status_chk check (
        lead_status in ('new', 'contacted', 'interested', 'follow_up', 'won', 'lost', 'dormant')
    ),
    constraint crm_lead_followups_follow_up_status_chk check (
        follow_up_status in ('none', 'scheduled', 'done', 'missed')
    ),
    constraint crm_lead_followups_priority_chk check (
        priority in ('normal', 'high', 'urgent')
    )
);

create index if not exists crm_lead_followups_phone_key_idx
    on public.crm_lead_followups (phone_key);
create index if not exists crm_lead_followups_lead_status_idx
    on public.crm_lead_followups (lead_status);
create index if not exists crm_lead_followups_follow_up_date_idx
    on public.crm_lead_followups (follow_up_date);
create index if not exists crm_lead_followups_updated_at_idx
    on public.crm_lead_followups (updated_at desc);

alter table public.crm_lead_followups enable row level security;

drop policy if exists "crm_lead_followups_service_role_all" on public.crm_lead_followups;
create policy "crm_lead_followups_service_role_all"
on public.crm_lead_followups
for all
to service_role
using (true)
with check (true);

grant usage on schema public to service_role;
grant select, insert, update, delete on table public.crm_lead_followups to service_role;
grant usage, select on sequence public.crm_lead_followups_id_seq to service_role;

comment on table public.crm_lead_followups is
'Lead and follow-up workflow state edited from the Customer 360 Streamlit dashboard.';

-- Rollback, if needed:
-- drop table if exists public.crm_lead_followups;
