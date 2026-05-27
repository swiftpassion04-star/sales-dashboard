create table if not exists public.crm_user_roles (
    email text primary key,
    role text not null check (role in ('CEO', 'EDITOR', 'พนักงาน', 'ทั่วไป')),
    staff_name text,
    is_active boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists idx_crm_user_roles_role
    on public.crm_user_roles (role);

create index if not exists idx_crm_user_roles_staff_name
    on public.crm_user_roles (staff_name)
    where staff_name is not null and staff_name <> '';

alter table public.crm_user_roles enable row level security;

do $$
begin
    if not exists (
        select 1
        from pg_policies
        where schemaname = 'public'
          and tablename = 'crm_user_roles'
          and policyname = 'service_role_full_access_crm_user_roles'
    ) then
        create policy service_role_full_access_crm_user_roles
        on public.crm_user_roles
        for all
        to service_role
        using (true)
        with check (true);
    end if;
end $$;

grant select, insert, update, delete on public.crm_user_roles to service_role;

comment on table public.crm_user_roles is
    'CRM web role mapping for Supabase Auth users. One email maps to one role and one staff_name.';
