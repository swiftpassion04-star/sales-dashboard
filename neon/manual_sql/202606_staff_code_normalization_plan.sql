-- Staff code normalization plan for CRM Neon database.
--
-- DO NOT RUN UNTIL APPROVED
-- REVIEW REQUIRED
-- MANUAL EXECUTION ONLY
--
-- This file is a manual SQL plan. It must be reviewed and approved before
-- being executed in Neon. Do not run this from automation or CI.
--
-- Goal:
-- - Normalize crm_data_imports.staff_code to canonical English codes.
-- - Normalize crm_user_roles.staff_code to the same canonical codes.
-- - Keep owner display names unchanged, except blank owner/staff_code rows assigned to AU.
--
-- Confirmed mapping:
-- SAIFON = สายฝน ราวิชัย (สายฝน)
-- TAEW   = พรณกมล ดวงจันทร์ (แต้ว)
-- YING   = พรธนนันท์ กานต์รพีพร (หญิง)
-- NOONA  = records previously owned by กัญญพักฒ์ อิ่มยวง (เจี๊ยบ)
-- AU     = rows where owner and staff_code are both blank
-- LEK    = ธัญญรัตน์ หอมระรื่น (เล็ก)
-- CREAM  = จินดามณี คงมี (ครีม)
-- KO     = สุมนตรา ทัศน์ศรี (โก้)
--
-- Transaction guide:
-- Block A: Run backup SQL and pre-update verification first.
-- Block B: Start BEGIN, run update SQL, run post-update verification and assertions.
-- Block C: COMMIT only if all assertion counts are correct. If any assertion fails,
--          Postgres raises an exception and the transaction should be rolled back.
--
-- Recommended execution shape:
-- 1) Run section 1 and 2.
-- 2) Run: BEGIN;
-- 3) Run section 3 and 4.
-- 4) If all assertions pass: COMMIT;
-- 5) If any assertion fails: ROLLBACK;

-- ============================================================
-- 1) BACKUP SQL
-- ============================================================

-- Drop only this dedicated backup name to avoid reusing an old backup schema.
-- Do not drop production tables.
drop table if exists public.crm_data_imports_staff_backup_202606;

create table public.crm_data_imports_staff_backup_202606 as
select
    id,
    owner,
    staff_code,
    updated_at
from public.crm_data_imports;

drop table if exists public.crm_user_roles_staff_backup_202606;

create table public.crm_user_roles_staff_backup_202606 as
select
    email,
    role,
    staff_code,
    staff_name,
    owner_alias,
    is_active,
    updated_at
from public.crm_user_roles;

-- Confirm backup counts before update.
select 'crm_data_imports source rows' as check_name, count(*) as rows
from public.crm_data_imports;

select 'crm_data_imports backup rows' as check_name, count(*) as rows
from public.crm_data_imports_staff_backup_202606;

select 'crm_user_roles source rows' as check_name, count(*) as rows
from public.crm_user_roles;

select 'crm_user_roles backup rows' as check_name, count(*) as rows
from public.crm_user_roles_staff_backup_202606;

-- ============================================================
-- 2) VERIFICATION BEFORE UPDATE
-- ============================================================

select
    coalesce(nullif(regexp_replace(btrim(coalesce(owner, '')), '\s+', ' ', 'g'), ''), '(ว่าง)') as owner_norm,
    coalesce(nullif(regexp_replace(btrim(coalesce(staff_code, '')), '\s+', ' ', 'g'), ''), '(ว่าง)') as staff_code_current,
    count(*) as records
from public.crm_data_imports
group by owner_norm, staff_code_current
order by records desc, owner_norm, staff_code_current;

select
    email,
    role,
    staff_name,
    staff_code,
    owner_alias,
    is_active,
    updated_at
from public.crm_user_roles
order by email;

-- Dry-run expected mapping counts before update.
with normalized as (
    select
        case
            when regexp_replace(btrim(coalesce(owner, '')), '\s+', ' ', 'g') = 'สายฝน ราวิชัย (สายฝน)' then 'SAIFON'
            when regexp_replace(btrim(coalesce(owner, '')), '\s+', ' ', 'g') = 'พรณกมล ดวงจันทร์ (แต้ว)' then 'TAEW'
            when regexp_replace(btrim(coalesce(owner, '')), '\s+', ' ', 'g') = 'พรธนนันท์ กานต์รพีพร (หญิง)' then 'YING'
            when regexp_replace(btrim(coalesce(owner, '')), '\s+', ' ', 'g') = 'กัญญพักฒ์ อิ่มยวง (เจี๊ยบ)' then 'NOONA'
            when regexp_replace(btrim(coalesce(owner, '')), '\s+', ' ', 'g') = 'ธัญญรัตน์ หอมระรื่น (เล็ก)' then 'LEK'
            when regexp_replace(btrim(coalesce(owner, '')), '\s+', ' ', 'g') = 'จินดามณี คงมี (ครีม)' then 'CREAM'
            when regexp_replace(btrim(coalesce(owner, '')), '\s+', ' ', 'g') = 'สุมนตรา ทัศน์ศรี (โก้)' then 'KO'
            when nullif(btrim(coalesce(owner, '')), '') is null
             and nullif(btrim(coalesce(staff_code, '')), '') is null then 'AU'
            else '(UNMAPPED)'
        end as proposed_staff_code
    from public.crm_data_imports
)
select proposed_staff_code, count(*) as records
from normalized
group by proposed_staff_code
order by
    case proposed_staff_code
        when 'SAIFON' then 1
        when 'TAEW' then 2
        when 'YING' then 3
        when 'NOONA' then 4
        when 'LEK' then 5
        when 'CREAM' then 6
        when 'KO' then 7
        when 'AU' then 8
        else 99
    end;

-- ============================================================
-- 3) UPDATE SQL
-- ============================================================

-- REVIEW REQUIRED before running this section.
-- crm_data_imports: update staff_code only for normalized exact owner matches.
-- Owner display name is kept unchanged except AU blank rows.

update public.crm_data_imports
set staff_code = 'SAIFON'
where regexp_replace(btrim(coalesce(owner, '')), '\s+', ' ', 'g') = 'สายฝน ราวิชัย (สายฝน)';

update public.crm_data_imports
set staff_code = 'TAEW'
where regexp_replace(btrim(coalesce(owner, '')), '\s+', ' ', 'g') = 'พรณกมล ดวงจันทร์ (แต้ว)';

update public.crm_data_imports
set staff_code = 'YING'
where regexp_replace(btrim(coalesce(owner, '')), '\s+', ' ', 'g') = 'พรธนนันท์ กานต์รพีพร (หญิง)';

update public.crm_data_imports
set staff_code = 'NOONA'
where regexp_replace(btrim(coalesce(owner, '')), '\s+', ' ', 'g') = 'กัญญพักฒ์ อิ่มยวง (เจี๊ยบ)';

update public.crm_data_imports
set staff_code = 'LEK'
where regexp_replace(btrim(coalesce(owner, '')), '\s+', ' ', 'g') = 'ธัญญรัตน์ หอมระรื่น (เล็ก)';

update public.crm_data_imports
set staff_code = 'CREAM'
where regexp_replace(btrim(coalesce(owner, '')), '\s+', ' ', 'g') = 'จินดามณี คงมี (ครีม)';

update public.crm_data_imports
set staff_code = 'KO'
where regexp_replace(btrim(coalesce(owner, '')), '\s+', ' ', 'g') = 'สุมนตรา ทัศน์ศรี (โก้)';

-- AU decision: only rows where both owner and staff_code were blank in the dry run.
-- This is the only data update that changes owner display name.
update public.crm_data_imports
set
    staff_code = 'AU',
    owner = 'ศิวพร ถีติปริวัตร (อุ๊)'
where nullif(btrim(coalesce(owner, '')), '') is null
  and nullif(btrim(coalesce(staff_code, '')), '') is null;

-- crm_user_roles: normalize staff_code and keep Thai display names for staff_name/owner_alias.
update public.crm_user_roles
set
    staff_code = 'SAIFON',
    staff_name = 'สายฝน ราวิชัย (สายฝน)',
    owner_alias = 'สายฝน ราวิชัย (สายฝน)',
    is_active = true,
    updated_at = now()
where email = 'swiftpassion.com18@gmail.com';

update public.crm_user_roles
set
    staff_code = 'TAEW',
    staff_name = 'พรณกมล ดวงจันทร์ (แต้ว)',
    owner_alias = 'พรณกมล ดวงจันทร์ (แต้ว)',
    is_active = true,
    updated_at = now()
where email = 'swiftpassion.com17@gmail.com';

update public.crm_user_roles
set
    staff_code = 'YING',
    staff_name = 'พรธนนันท์ กานต์รพีพร (หญิง)',
    owner_alias = 'พรธนนันท์ กานต์รพีพร (หญิง)',
    is_active = true,
    updated_at = now()
where email = 'swiftpassion.com21@gmail.com';

update public.crm_user_roles
set
    staff_code = 'NOONA',
    staff_name = 'พรนภา นันที (หนูนา)',
    owner_alias = 'กัญญพักฒ์ อิ่มยวง (เจี๊ยบ)',
    is_active = true,
    updated_at = now()
where email = 'swiftpassion.com19@gmail.com';

update public.crm_user_roles
set
    staff_code = 'AU',
    staff_name = 'ศิวพร ถีติปริวัตร (อุ๊)',
    owner_alias = 'ศิวพร ถีติปริวัตร (อุ๊)',
    is_active = true,
    updated_at = now()
where email = 'swiftpassion.com22@gmail.com';

update public.crm_user_roles
set
    staff_code = 'LEK',
    staff_name = 'ธัญญรัตน์ หอมระรื่น (เล็ก)',
    owner_alias = 'ธัญญรัตน์ หอมระรื่น (เล็ก)',
    is_active = true,
    updated_at = now()
where email = 'swiftpassion.com03@gmail.com';

update public.crm_user_roles
set
    staff_code = 'CREAM',
    staff_name = 'จินดามณี คงมี (ครีม)',
    owner_alias = 'จินดามณี คงมี (ครีม)',
    is_active = true,
    updated_at = now()
where email = 'swiftpassion.com16@gmail.com';

update public.crm_user_roles
set
    staff_code = 'KO',
    staff_name = 'สุมนตรา ทัศน์ศรี (โก้)',
    owner_alias = 'สุมนตรา ทัศน์ศรี (โก้)',
    is_active = true,
    updated_at = now()
where email = 'swiftpassion.com14@gmail.com';

-- ============================================================
-- 4) VERIFICATION AFTER UPDATE + ASSERTIONS
-- ============================================================

select
    staff_code,
    count(*) as records
from public.crm_data_imports
where staff_code in ('SAIFON', 'TAEW', 'YING', 'NOONA', 'AU', 'LEK', 'CREAM', 'KO')
group by staff_code
order by
    case staff_code
        when 'SAIFON' then 1
        when 'TAEW' then 2
        when 'YING' then 3
        when 'NOONA' then 4
        when 'AU' then 5
        when 'LEK' then 6
        when 'CREAM' then 7
        when 'KO' then 8
        else 99
    end;

-- Expected result:
-- SAIFON = 6502
-- TAEW   = 4669
-- YING   = 3100
-- NOONA  = 3087
-- AU     = 730
-- LEK    = 9
-- CREAM  = 1
-- KO     = 1

do $$
declare
    actual_count integer;
begin
    select count(*) into actual_count from public.crm_data_imports where staff_code = 'SAIFON';
    if actual_count <> 6502 then raise exception 'SAIFON expected 6502, got %', actual_count; end if;

    select count(*) into actual_count from public.crm_data_imports where staff_code = 'TAEW';
    if actual_count <> 4669 then raise exception 'TAEW expected 4669, got %', actual_count; end if;

    select count(*) into actual_count from public.crm_data_imports where staff_code = 'YING';
    if actual_count <> 3100 then raise exception 'YING expected 3100, got %', actual_count; end if;

    select count(*) into actual_count from public.crm_data_imports where staff_code = 'NOONA';
    if actual_count <> 3087 then raise exception 'NOONA expected 3087, got %', actual_count; end if;

    select count(*) into actual_count from public.crm_data_imports where staff_code = 'AU';
    if actual_count <> 730 then raise exception 'AU expected 730, got %', actual_count; end if;

    select count(*) into actual_count from public.crm_data_imports where staff_code = 'LEK';
    if actual_count <> 9 then raise exception 'LEK expected 9, got %', actual_count; end if;

    select count(*) into actual_count from public.crm_data_imports where staff_code = 'CREAM';
    if actual_count <> 1 then raise exception 'CREAM expected 1, got %', actual_count; end if;

    select count(*) into actual_count from public.crm_data_imports where staff_code = 'KO';
    if actual_count <> 1 then raise exception 'KO expected 1, got %', actual_count; end if;

    select count(*) into actual_count
    from public.crm_data_imports
    where coalesce(nullif(staff_code, ''), '') not in (
        'SAIFON',
        'TAEW',
        'YING',
        'NOONA',
        'AU',
        'LEK',
        'CREAM',
        'KO'
    );
    if actual_count <> 0 then raise exception 'Remaining unmapped rows expected 0, got %', actual_count; end if;
end $$;

select
    email,
    role,
    staff_code,
    staff_name,
    owner_alias,
    is_active,
    updated_at
from public.crm_user_roles
order by email;

-- ============================================================
-- 5) ROLLBACK SQL
-- ============================================================

-- Run rollback only if verification fails and you need to restore pre-update values.
-- Rollback must be run manually and only after confirming the backup tables exist.

update public.crm_data_imports d
set
    owner = b.owner,
    staff_code = b.staff_code,
    updated_at = b.updated_at
from public.crm_data_imports_staff_backup_202606 b
where b.id = d.id;

update public.crm_user_roles u
set
    role = b.role,
    staff_code = b.staff_code,
    staff_name = b.staff_name,
    owner_alias = b.owner_alias,
    is_active = b.is_active,
    updated_at = b.updated_at
from public.crm_user_roles_staff_backup_202606 b
where b.email = u.email;

-- Rollback verification.
select
    coalesce(nullif(regexp_replace(btrim(coalesce(owner, '')), '\s+', ' ', 'g'), ''), '(ว่าง)') as owner_norm,
    coalesce(nullif(regexp_replace(btrim(coalesce(staff_code, '')), '\s+', ' ', 'g'), ''), '(ว่าง)') as staff_code_restored,
    count(*) as records
from public.crm_data_imports
group by owner_norm, staff_code_restored
order by records desc, owner_norm, staff_code_restored;
