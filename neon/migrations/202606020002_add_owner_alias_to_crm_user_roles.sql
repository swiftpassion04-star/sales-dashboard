alter table public.crm_user_roles
  add column if not exists owner_alias text;

create index if not exists idx_crm_user_roles_owner_alias
  on public.crm_user_roles (owner_alias);
