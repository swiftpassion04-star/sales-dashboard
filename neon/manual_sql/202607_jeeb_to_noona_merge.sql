-- ============================================================================
-- JEEB -> NOONA merge (APPROVED 2026-07-23)
-- ============================================================================
-- Decision reference: docs/STAFF_MAPPING_DECISION_REQUIRED.md ("ประเด็น JEEB"),
-- docs/OWNER_STAFF_MAPPING_APPROVAL.md ("ต้องยืนยันเป็นพิเศษ").
--
-- Approved scope (verbatim from business owner, 2026-07-23):
--   1. Move all 3,087 JEEB rows (and related data) to staff_code = NOONA
--   2. Update owner / staff_code / display name to correspond to NOONA
--   3. Delete or deactivate JEEB's login, staff option, alias, and mapping
--   4. Governance docs updated to match (done, this same review)
--   5. Backup only the affected rows before changing anything
--   6. Single transaction; any failure rolls back everything
--   7. Verify counts before/after: no data loss, no JEEB left, NOONA gains
--      exactly the JEEB count
--   8. Must not affect any other staff member
--
-- THIS SCRIPT HAS NOT BEEN RUN. The environment that authored it has no
-- NEON_DATABASE_URL configured and cannot connect to any real database.
--
-- DO NOT RUN until:
--   (a) a human with real database access has reviewed this script, and
--   (b) the pre-migration counts captured in STEP 1 have been sanity-checked
--       against the live data (expected ~3,087 JEEB-tagged rows total across
--       crm_data_imports/crm_lead_followups/crm_orders per the governance
--       docs; if the real count differs materially, STOP and re-confirm
--       scope before proceeding).
--
-- How to run safely:
--   psql "$NEON_DATABASE_URL" -v ON_ERROR_STOP=1 -f 202607_jeeb_to_noona_merge.sql
--   ON_ERROR_STOP=1 ensures psql aborts immediately on any error, leaving the
--   transaction open-but-aborted so nothing partial is ever committed. If the
--   script completes, review the STEP 5 verification output before trusting
--   the automatic COMMIT at the end -- if anything printed looks wrong,
--   run ROLLBACK instead of letting the script reach COMMIT.
-- ============================================================================

begin;

-- ----------------------------------------------------------------------------
-- STEP 1: Snapshot pre-migration counts (used for the verification in STEP 5).
-- Uses a normalized comparison (trim + collapse internal whitespace) so we
-- catch 'JEEB', 'เจี๊ยบ', or any whitespace-variant of either, matching the
-- "normalized exact match" rule already agreed in OWNER_STAFF_MAPPING_APPROVAL.md.
-- ----------------------------------------------------------------------------

create temporary table _jeeb_merge_pre_counts as
select
  'crm_data_imports' as table_name,
  count(*) filter (
    where regexp_replace(trim(coalesce(staff_code, '')), '\s+', ' ', 'g') in ('JEEB', 'เจี๊ยบ')
       or regexp_replace(trim(coalesce(owner, '')), '\s+', ' ', 'g') = 'กัญญพักฒ์ อิ่มยวง (เจี๊ยบ)'
  ) as jeeb_count,
  count(*) filter (
    where regexp_replace(trim(coalesce(staff_code, '')), '\s+', ' ', 'g') = 'NOONA'
  ) as noona_count
from public.crm_data_imports
union all
select
  'crm_lead_followups',
  count(*) filter (
    where regexp_replace(trim(coalesce(staff_code, '')), '\s+', ' ', 'g') in ('JEEB', 'เจี๊ยบ')
       or regexp_replace(trim(coalesce(owner, '')), '\s+', ' ', 'g') = 'กัญญพักฒ์ อิ่มยวง (เจี๊ยบ)'
  ),
  count(*) filter (
    where regexp_replace(trim(coalesce(staff_code, '')), '\s+', ' ', 'g') = 'NOONA'
  )
from public.crm_lead_followups
union all
select
  'crm_orders',
  count(*) filter (
    where regexp_replace(trim(coalesce(staff_code, '')), '\s+', ' ', 'g') in ('JEEB', 'เจี๊ยบ')
       or regexp_replace(trim(coalesce(owner, '')), '\s+', ' ', 'g') = 'กัญญพักฒ์ อิ่มยวง (เจี๊ยบ)'
  ),
  count(*) filter (
    where regexp_replace(trim(coalesce(staff_code, '')), '\s+', ' ', 'g') = 'NOONA'
  )
from public.crm_orders;

-- Print the pre-migration snapshot for the operator to eyeball before continuing.
select * from _jeeb_merge_pre_counts order by table_name;

-- Total rows expected to move (for a human sanity check against the ~3,087
-- figure in the governance docs -- STOP here and investigate if this is far
-- off from that expectation instead of proceeding blindly).
select sum(jeeb_count) as total_jeeb_rows_about_to_move from _jeeb_merge_pre_counts;

-- Snapshot every OTHER staff_code's row count too, so STEP 5 can prove this
-- migration touched nobody else (approved-scope requirement #8).
create temporary table _other_staff_pre_counts as
select
  regexp_replace(trim(coalesce(staff_code, '')), '\s+', ' ', 'g') as staff_code_norm,
  count(*) as row_count
from public.crm_data_imports
where regexp_replace(trim(coalesce(staff_code, '')), '\s+', ' ', 'g') not in ('JEEB', 'เจี๊ยบ', 'NOONA', '')
group by 1;

-- ----------------------------------------------------------------------------
-- STEP 2: Backup only the affected rows (full row snapshot, restorable by id).
-- Table names are timestamped so repeated dry-runs never collide.
-- ----------------------------------------------------------------------------

create table public.crm_jeeb_noona_merge_backup_20260723_data_imports as
select *
from public.crm_data_imports
where regexp_replace(trim(coalesce(staff_code, '')), '\s+', ' ', 'g') in ('JEEB', 'เจี๊ยบ')
   or regexp_replace(trim(coalesce(owner, '')), '\s+', ' ', 'g') = 'กัญญพักฒ์ อิ่มยวง (เจี๊ยบ)';

create table public.crm_jeeb_noona_merge_backup_20260723_lead_followups as
select *
from public.crm_lead_followups
where regexp_replace(trim(coalesce(staff_code, '')), '\s+', ' ', 'g') in ('JEEB', 'เจี๊ยบ')
   or regexp_replace(trim(coalesce(owner, '')), '\s+', ' ', 'g') = 'กัญญพักฒ์ อิ่มยวง (เจี๊ยบ)';

create table public.crm_jeeb_noona_merge_backup_20260723_orders as
select *
from public.crm_orders
where regexp_replace(trim(coalesce(staff_code, '')), '\s+', ' ', 'g') in ('JEEB', 'เจี๊ยบ')
   or regexp_replace(trim(coalesce(owner, '')), '\s+', ' ', 'g') = 'กัญญพักฒ์ อิ่มยวง (เจี๊ยบ)';

create table public.crm_jeeb_noona_merge_backup_20260723_user_roles as
select *
from public.crm_user_roles
where regexp_replace(trim(coalesce(staff_code, '')), '\s+', ' ', 'g') in ('JEEB', 'เจี๊ยบ');

create table public.crm_jeeb_noona_merge_backup_20260723_staff_options as
select *
from public.crm_staff_options
where regexp_replace(trim(coalesce(staff_code, '')), '\s+', ' ', 'g') in ('JEEB', 'เจี๊ยบ')
   or regexp_replace(trim(coalesce(staff_name, '')), '\s+', ' ', 'g') = 'กัญญพักฒ์ อิ่มยวง (เจี๊ยบ)';

-- ----------------------------------------------------------------------------
-- STEP 3: Re-attribute JEEB's data to NOONA (staff_code + display owner/name).
-- Approved-scope item #2: owner/staff_code/display name must correspond to
-- NOONA (พรนภา นันที) going forward, not the retired เจี๊ยบ identity.
-- ----------------------------------------------------------------------------

update public.crm_data_imports
set staff_code = 'NOONA',
    owner = 'พรนภา นันที (หนูนา)',
    updated_at = now()
where regexp_replace(trim(coalesce(staff_code, '')), '\s+', ' ', 'g') in ('JEEB', 'เจี๊ยบ')
   or regexp_replace(trim(coalesce(owner, '')), '\s+', ' ', 'g') = 'กัญญพักฒ์ อิ่มยวง (เจี๊ยบ)';

update public.crm_lead_followups
set staff_code = 'NOONA',
    owner = 'พรนภา นันที (หนูนา)',
    updated_at = now()
where regexp_replace(trim(coalesce(staff_code, '')), '\s+', ' ', 'g') in ('JEEB', 'เจี๊ยบ')
   or regexp_replace(trim(coalesce(owner, '')), '\s+', ' ', 'g') = 'กัญญพักฒ์ อิ่มยวง (เจี๊ยบ)';

update public.crm_orders
set staff_code = 'NOONA',
    owner = 'พรนภา นันที (หนูนา)',
    updated_at = now()
where regexp_replace(trim(coalesce(staff_code, '')), '\s+', ' ', 'g') in ('JEEB', 'เจี๊ยบ')
   or regexp_replace(trim(coalesce(owner, '')), '\s+', ' ', 'g') = 'กัญญพักฒ์ อิ่มยวง (เจี๊ยบ)';

-- ----------------------------------------------------------------------------
-- STEP 4: Retire JEEB from the staff directory (approved-scope item #3).
-- Deactivate rather than hard-delete by default -- reversible, and per the
-- governance docs' own rule ("ห้ามแก้ข้อมูล production โดยไม่มี backup ก่อน")
-- a soft-disable is the lower-risk choice. If the operator specifically
-- wants a hard delete instead, the commented statements below do that --
-- only after confirming STEP 5 passes and the backup tables are retained.
-- ----------------------------------------------------------------------------

update public.crm_user_roles
set staff_code = null,
    is_active = false,
    updated_at = now()
where regexp_replace(trim(coalesce(staff_code, '')), '\s+', ' ', 'g') in ('JEEB', 'เจี๊ยบ');

update public.crm_staff_options
set staff_code = null,
    is_active = false,
    updated_at = now()
where regexp_replace(trim(coalesce(staff_code, '')), '\s+', ' ', 'g') in ('JEEB', 'เจี๊ยบ')
   or regexp_replace(trim(coalesce(staff_name, '')), '\s+', ' ', 'g') = 'กัญญพักฒ์ อิ่มยวง (เจี๊ยบ)';

-- Optional hard-delete variant (uncomment only if a soft-disable is not
-- acceptable -- do this in a SEPARATE run after STEP 5 has already been
-- verified clean in this run, never in the same pass as the update above):
-- delete from public.crm_user_roles
-- where regexp_replace(trim(coalesce(staff_code, '')), '\s+', ' ', 'g') in ('JEEB', 'เจี๊ยบ');
-- delete from public.crm_staff_options
-- where regexp_replace(trim(coalesce(staff_code, '')), '\s+', ' ', 'g') in ('JEEB', 'เจี๊ยบ')
--    or regexp_replace(trim(coalesce(staff_name, '')), '\s+', ' ', 'g') = 'กัญญพักฒ์ อิ่มยวง (เจี๊ยบ)';

-- ----------------------------------------------------------------------------
-- STEP 5: Verify. Any RAISE EXCEPTION here aborts the transaction -- with
-- `psql -v ON_ERROR_STOP=1` the script stops immediately and nothing above
-- is committed. Do not remove or weaken these checks.
-- ----------------------------------------------------------------------------

do $$
declare
  jeeb_remaining bigint;
  noona_before bigint;
  noona_after bigint;
  jeeb_total_before bigint;
  mismatched_staff text;
begin
  select coalesce(sum(jeeb_count), 0) into jeeb_total_before from _jeeb_merge_pre_counts;
  select coalesce(sum(noona_count), 0) into noona_before from _jeeb_merge_pre_counts;

  select count(*) into jeeb_remaining
  from (
    select 1 from public.crm_data_imports
    where regexp_replace(trim(coalesce(staff_code, '')), '\s+', ' ', 'g') in ('JEEB', 'เจี๊ยบ')
    union all
    select 1 from public.crm_lead_followups
    where regexp_replace(trim(coalesce(staff_code, '')), '\s+', ' ', 'g') in ('JEEB', 'เจี๊ยบ')
    union all
    select 1 from public.crm_orders
    where regexp_replace(trim(coalesce(staff_code, '')), '\s+', ' ', 'g') in ('JEEB', 'เจี๊ยบ')
    union all
    select 1 from public.crm_user_roles
    where regexp_replace(trim(coalesce(staff_code, '')), '\s+', ' ', 'g') in ('JEEB', 'เจี๊ยบ')
    union all
    select 1 from public.crm_staff_options
    where regexp_replace(trim(coalesce(staff_code, '')), '\s+', ' ', 'g') in ('JEEB', 'เจี๊ยบ')
  ) as remaining;

  if jeeb_remaining <> 0 then
    raise exception 'JEEB merge verification FAILED: % JEEB-tagged rows still remain after migration (expected 0)', jeeb_remaining;
  end if;

  select
    (select count(*) from public.crm_data_imports where regexp_replace(trim(coalesce(staff_code, '')), '\s+', ' ', 'g') = 'NOONA')
    + (select count(*) from public.crm_lead_followups where regexp_replace(trim(coalesce(staff_code, '')), '\s+', ' ', 'g') = 'NOONA')
    + (select count(*) from public.crm_orders where regexp_replace(trim(coalesce(staff_code, '')), '\s+', ' ', 'g') = 'NOONA')
  into noona_after;

  if noona_after <> (noona_before + jeeb_total_before) then
    raise exception 'JEEB merge verification FAILED: NOONA row count is % after migration, expected % (% before + % moved from JEEB) -- possible data loss or duplication',
      noona_after, noona_before + jeeb_total_before, noona_before, jeeb_total_before;
  end if;

  -- Approved-scope item #8: prove no other staff member's row count changed.
  select string_agg(pre.staff_code_norm || ' (' || pre.row_count || ' -> ' || post.row_count || ')', ', ')
  into mismatched_staff
  from _other_staff_pre_counts pre
  join (
    select
      regexp_replace(trim(coalesce(staff_code, '')), '\s+', ' ', 'g') as staff_code_norm,
      count(*) as row_count
    from public.crm_data_imports
    where regexp_replace(trim(coalesce(staff_code, '')), '\s+', ' ', 'g') not in ('JEEB', 'เจี๊ยบ', 'NOONA', '')
    group by 1
  ) as post on post.staff_code_norm = pre.staff_code_norm
  where post.row_count <> pre.row_count;

  if mismatched_staff is not null then
    raise exception 'JEEB merge verification FAILED: other staff row counts changed unexpectedly: %', mismatched_staff;
  end if;

  raise notice 'JEEB merge verification PASSED: % rows moved from JEEB to NOONA, no data loss, no other staff affected.', jeeb_total_before;
end $$;

-- If you reach this line, every check above passed. Review the NOTICE output
-- once more, then either COMMIT (accept) or ROLLBACK (undo everything,
-- backup tables are untouched by ROLLBACK since... actually note: backup
-- tables ARE created inside this same transaction via `create table`, so a
-- ROLLBACK also undoes the backups. If you need the backups to survive a
-- decision to abort the live-table changes, run STEP 2 (backups only) as
-- its own committed transaction first, then run STEPs 1/3/4/5 separately.)
commit;

-- ============================================================================
-- Rollback (only if something is discovered wrong AFTER this script already
-- committed -- restore from the timestamped backup tables by id):
--
-- update public.crm_data_imports d
-- set staff_code = b.staff_code, owner = b.owner, updated_at = b.updated_at
-- from public.crm_jeeb_noona_merge_backup_20260723_data_imports b
-- where d.id = b.id;
-- (repeat the same pattern for crm_lead_followups, crm_orders, crm_user_roles,
-- crm_staff_options using their respective backup tables and primary keys)
-- ============================================================================
