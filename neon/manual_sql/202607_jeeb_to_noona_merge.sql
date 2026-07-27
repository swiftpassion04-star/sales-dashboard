-- ============================================================================
-- JEEB -> NOONA merge (APPROVED 2026-07-23) -- REV 2 (2026-07-24)
-- ============================================================================
-- Decision reference: docs/STAFF_MAPPING_DECISION_REQUIRED.md ("ประเด็น JEEB"),
-- docs/OWNER_STAFF_MAPPING_APPROVAL.md ("ต้องยืนยันเป็นพิเศษ").
--
-- Approved scope (verbatim from business owner, 2026-07-23):
--   1. Move all JEEB rows (and related data) to staff_code = NOONA
--   2. Update owner / staff_code / display name to correspond to NOONA
--   3. Delete or deactivate JEEB's login, staff option, alias, and mapping
--   4. Governance docs updated to match (done, this same review)
--   5. Backup only the affected rows before changing anything
--   6. Single transaction; any failure rolls back everything
--   7. Verify counts before/after: no data loss, no JEEB left, NOONA gains
--      exactly the JEEB count
--   8. Must not affect any other staff member (explicitly including AU and
--      the known YING/NOONA data-quality mismatch row -- see STEP 5)
--
-- ----------------------------------------------------------------------------
-- REV 2 CHANGE LOG (why this file was rewritten, offline, 2026-07-24):
-- ----------------------------------------------------------------------------
-- A 2026-07-24 read-only investigation against real Production (see
-- neon/manual_sql/202607_owner_mapping_investigation_readonly.sql, run
-- verbatim, ROLLBACK-only, no writes) found REV 1 of this script would have
-- FAILED on first execution and had gaps REV 2 fixes:
--
--   1. `public.crm_orders` DOES NOT EXIST in Production. REV 1 referenced it
--      in STEP 1 (pre-count), STEP 2 (backup), STEP 3 (update), and STEP 5
--      (verification) -- the very first statement touching it
--      (`... union all select 'crm_orders', ... from public.crm_orders`)
--      would have raised `UndefinedTable` and aborted the whole transaction
--      before anything else ran. Every crm_orders reference is removed below.
--      This is NOT a schema-mismatch to paper over with dynamic SQL -- it is
--      removed entirely because the table is not part of this migration's
--      real scope. If a future project adds order-level staff attribution,
--      that is a separate, deliberately-scoped migration.
--
--   2. The same investigation's migration-impact simulation (SELECT COUNT(*)
--      mirroring each UPDATE's WHERE clause, read-only, no writes) found the
--      REAL current impact is much smaller than the ~3,087-row figure in the
--      governance docs:
--        - crm_data_imports:   0 rows currently match the JEEB pattern
--        - crm_lead_followups: 0 rows currently match the JEEB pattern
--        - crm_user_roles:     0 rows currently match the JEEB pattern
--        - crm_staff_options:  1 row currently matches (staff_code
--                              normalizes to 'เจี๊ยบ', is_active = true)
--      This is consistent with backup tables already present in Production
--      (e.g. `crm_data_imports_owner_backup_noona_20260615`) that this
--      project did not create -- strong evidence an uncoordinated, separate
--      process already moved the bulk of JEEB's data to NOONA before this
--      script was ever going to run. REV 2 treats "0 rows to move" in the
--      three data/identity tables as a VALID, expected outcome (see STEP 5)
--      rather than an error -- the verification logic checks internal
--      consistency (moved count vs. NOONA delta), never a hardcoded nonzero
--      expectation. The remaining real work is retiring the stale
--      `crm_staff_options` row for JEEB, which this script still does.
--
--   3. REV 1's conflict handling was implicit: an owner-text match
--      (`owner = 'กัญญพักฒ์ อิ่มยวง (เจี๊ยบ)'`) was OR'd directly into the
--      UPDATE's WHERE clause with no check for the case where that owner
--      text is paired with a DIFFERENT, already-assigned staff_code (e.g.
--      the real row this investigation found: owner text equal to YING's
--      full name paired with staff_code = 'NOONA' -- proving this exact
--      shape of mismatch really occurs in this data). REV 2 adds an
--      explicit STEP 0 conflict guard per table that RAISES EXCEPTION and
--      aborts (before any backup or UPDATE runs) if any row's owner/
--      staff_name text matches JEEB's name while its staff_code is some
--      OTHER real, non-blank code. Nothing is auto-merged across a
--      staff_code boundary -- ambiguous rows stop the whole script for a
--      human to review, per this project's standing rule.
--
--   4. REV 1's rollback notes said "repeat the same pattern... using their
--      respective ... primary keys" without stating what those keys
--      actually are. `crm_user_roles` is keyed by `email`, not `id` --
--      restoring it by `id` would silently do nothing (or corrupt an
--      unrelated row if `id` happens to collide) since there is no
--      guarantee `crm_user_roles.id` is even a stable, present column.
--      REV 2's rollback section (bottom of this file) gives a complete,
--      independently-runnable statement per table with its real key.
--
--   5. REV 2 adds a STEP 0 preflight that verifies (via information_schema,
--      hardcoded static table/column names, no dynamically-built
--      identifiers) that every table/column this script touches actually
--      exists with the expected primary key, and that an active NOONA
--      target exists in at least one staff directory table, before doing
--      anything else. This does not guess -- it checks, and refuses to
--      proceed on any mismatch.
--
-- Scope is UNCHANGED and still deliberately narrow. This script still must
-- NOT:
--   - touch the YING/NOONA owner-text mismatch row found during
--     investigation (staff_code = 'NOONA', owner text = YING's full name) --
--     that is a separate, unscoped data-quality issue for a future decision.
--   - touch staff_code = 'AU' or assign any blank-owner row to AU.
--   - touch the KO/TAEW-adjacent merge already performed by a separate,
--     uncoordinated process on 2026-07-23.
--   - resolve any inactive-alias case other than JEEB/เจี๊ยบ -> NOONA.
--
-- THIS SCRIPT HAS STILL NOT BEEN RUN. It was rewritten entirely offline: no
-- database connection was made while authoring this revision.
--
-- DO NOT RUN until:
--   (a) a human with real database access has reviewed this script, and
--   (b) the STEP 0 preflight output (schema/PK verification, conflict guard
--       results, pre-migration counts) has been read and makes sense, and
--   (c) the operator understands that 0 affected rows in
--       crm_data_imports/crm_lead_followups/crm_user_roles is the CURRENTLY
--       EXPECTED outcome, not a sign something is broken.
--
-- How to run safely:
--   psql "$NEON_DATABASE_URL" -v ON_ERROR_STOP=1 -f 202607_jeeb_to_noona_merge.sql
--   ON_ERROR_STOP=1 ensures psql aborts immediately on any error, leaving the
--   transaction open-but-aborted so nothing partial is ever committed. If the
--   script completes, review the STEP 5 verification NOTICE output before
--   trusting the automatic COMMIT at the end -- if anything printed looks
--   wrong, run ROLLBACK instead of letting the script reach COMMIT.
-- ============================================================================

begin;

-- ----------------------------------------------------------------------------
-- STEP 0a: Preflight -- verify every table/column this script touches
-- actually exists with the expected shape, and verify each table's real
-- primary key column(s) instead of assuming them. Hardcoded, static
-- table/column names only -- this is a verification gate, not a mechanism
-- for silently adapting to whatever schema happens to be present.
-- ----------------------------------------------------------------------------

do $$
declare
  missing_cols text;
  pk_data_imports text;
  pk_lead_followups text;
  pk_user_roles text;
  pk_staff_options text;
begin
  -- Required columns per table. If any are missing, stop now -- every
  -- statement below assumes these exist.
  select string_agg(t.table_name || '.' || t.column_name, ', ')
  into missing_cols
  from (values
    ('crm_data_imports', 'id'), ('crm_data_imports', 'owner'),
    ('crm_data_imports', 'staff_code'), ('crm_data_imports', 'updated_at'),
    ('crm_lead_followups', 'id'), ('crm_lead_followups', 'owner'),
    ('crm_lead_followups', 'staff_code'), ('crm_lead_followups', 'updated_at'),
    ('crm_user_roles', 'email'), ('crm_user_roles', 'staff_code'),
    ('crm_user_roles', 'staff_name'), ('crm_user_roles', 'is_active'),
    ('crm_user_roles', 'updated_at'),
    ('crm_staff_options', 'id'), ('crm_staff_options', 'staff_code'),
    ('crm_staff_options', 'staff_name'), ('crm_staff_options', 'is_active'),
    ('crm_staff_options', 'updated_at')
  ) as t(table_name, column_name)
  where not exists (
    select 1 from information_schema.columns c
    where c.table_schema = 'public'
      and c.table_name = t.table_name
      and c.column_name = t.column_name
  );

  if missing_cols is not null then
    raise exception 'PREFLIGHT FAILED: expected column(s) not found in Production schema: %. This script must not proceed against a schema it has not verified.', missing_cols;
  end if;

  -- Real primary key column(s) per table, looked up rather than assumed.
  select string_agg(kcu.column_name, ',' order by kcu.ordinal_position)
  into pk_data_imports
  from information_schema.table_constraints tc
  join information_schema.key_column_usage kcu
    on kcu.constraint_name = tc.constraint_name and kcu.table_schema = tc.table_schema
  where tc.table_schema = 'public' and tc.table_name = 'crm_data_imports' and tc.constraint_type = 'PRIMARY KEY';

  select string_agg(kcu.column_name, ',' order by kcu.ordinal_position)
  into pk_lead_followups
  from information_schema.table_constraints tc
  join information_schema.key_column_usage kcu
    on kcu.constraint_name = tc.constraint_name and kcu.table_schema = tc.table_schema
  where tc.table_schema = 'public' and tc.table_name = 'crm_lead_followups' and tc.constraint_type = 'PRIMARY KEY';

  select string_agg(kcu.column_name, ',' order by kcu.ordinal_position)
  into pk_user_roles
  from information_schema.table_constraints tc
  join information_schema.key_column_usage kcu
    on kcu.constraint_name = tc.constraint_name and kcu.table_schema = tc.table_schema
  where tc.table_schema = 'public' and tc.table_name = 'crm_user_roles' and tc.constraint_type = 'PRIMARY KEY';

  select string_agg(kcu.column_name, ',' order by kcu.ordinal_position)
  into pk_staff_options
  from information_schema.table_constraints tc
  join information_schema.key_column_usage kcu
    on kcu.constraint_name = tc.constraint_name and kcu.table_schema = tc.table_schema
  where tc.table_schema = 'public' and tc.table_name = 'crm_staff_options' and tc.constraint_type = 'PRIMARY KEY';

  raise notice 'PREFLIGHT primary keys found -- crm_data_imports: %, crm_lead_followups: %, crm_user_roles: %, crm_staff_options: %',
    coalesce(pk_data_imports, '(none found)'), coalesce(pk_lead_followups, '(none found)'),
    coalesce(pk_user_roles, '(none found)'), coalesce(pk_staff_options, '(none found)');

  -- The rollback plan at the bottom of this file is only correct if these
  -- match what it assumes. Abort rather than silently trust a mismatch.
  if pk_data_imports is distinct from 'id' then
    raise exception 'PREFLIGHT FAILED: crm_data_imports primary key is "%", expected "id". The rollback plan in this file assumes "id" -- update it and re-review before proceeding.', coalesce(pk_data_imports, 'NONE');
  end if;
  if pk_lead_followups is distinct from 'id' then
    raise exception 'PREFLIGHT FAILED: crm_lead_followups primary key is "%", expected "id". The rollback plan in this file assumes "id" -- update it and re-review before proceeding.', coalesce(pk_lead_followups, 'NONE');
  end if;
  if pk_user_roles is distinct from 'email' then
    raise exception 'PREFLIGHT FAILED: crm_user_roles primary key is "%", expected "email". The rollback plan in this file assumes "email" -- update it and re-review before proceeding.', coalesce(pk_user_roles, 'NONE');
  end if;
  if pk_staff_options is distinct from 'id' then
    raise exception 'PREFLIGHT FAILED: crm_staff_options primary key is "%", expected "id". The rollback plan in this file assumes "id" -- update it and re-review before proceeding.', coalesce(pk_staff_options, 'NONE');
  end if;
end $$;

-- ----------------------------------------------------------------------------
-- STEP 0b: Preflight -- confirm an ACTIVE NOONA target actually exists before
-- merging anything into that identity. Refuse to create a merge destination
-- that does not already exist.
-- ----------------------------------------------------------------------------

do $$
declare
  noona_target_exists boolean;
begin
  select exists (
    select 1 from public.crm_user_roles
    where regexp_replace(trim(coalesce(staff_code, '')), '\s+', ' ', 'g') = 'NOONA' and is_active
    union all
    select 1 from public.crm_staff_options
    where regexp_replace(trim(coalesce(staff_code, '')), '\s+', ' ', 'g') = 'NOONA' and is_active
  ) into noona_target_exists;

  if not noona_target_exists then
    raise exception 'PREFLIGHT FAILED: no active NOONA entry found in crm_user_roles or crm_staff_options. Refusing to merge JEEB into a target identity that does not exist.';
  end if;
end $$;

-- ----------------------------------------------------------------------------
-- STEP 0c: Conflict guard -- detect rows where owner/staff_name text matches
-- JEEB's known display name while staff_code is a DIFFERENT, already-assigned
-- real code (not blank, not JEEB/เจี๊ยบ). This is the exact shape of the real
-- YING/NOONA mismatch row found during investigation -- it must never be
-- silently swept into this migration just because of matching display text.
-- Any hit here aborts the whole transaction for manual review; nothing is
-- auto-resolved.
-- ----------------------------------------------------------------------------

do $$
declare
  conflict_count bigint;
  conflict_detail text;
begin
  select count(*), string_agg(format('crm_data_imports.id=%s (staff_code=%s)', id, staff_code), '; ')
  into conflict_count, conflict_detail
  from public.crm_data_imports
  where regexp_replace(trim(coalesce(owner, '')), '\s+', ' ', 'g') = 'กัญญพักฒ์ อิ่มยวง (เจี๊ยบ)'
    and regexp_replace(trim(coalesce(staff_code, '')), '\s+', ' ', 'g') not in ('', 'JEEB', 'เจี๊ยบ');

  if conflict_count > 0 then
    raise exception 'CONFLICT GUARD TRIPPED in crm_data_imports: % row(s) have JEEB owner text but a DIFFERENT staff_code already assigned -- refusing to auto-merge. Rows: %', conflict_count, conflict_detail;
  end if;

  select count(*), string_agg(format('crm_lead_followups.id=%s (staff_code=%s)', id, staff_code), '; ')
  into conflict_count, conflict_detail
  from public.crm_lead_followups
  where regexp_replace(trim(coalesce(owner, '')), '\s+', ' ', 'g') = 'กัญญพักฒ์ อิ่มยวง (เจี๊ยบ)'
    and regexp_replace(trim(coalesce(staff_code, '')), '\s+', ' ', 'g') not in ('', 'JEEB', 'เจี๊ยบ');

  if conflict_count > 0 then
    raise exception 'CONFLICT GUARD TRIPPED in crm_lead_followups: % row(s) have JEEB owner text but a DIFFERENT staff_code already assigned -- refusing to auto-merge. Rows: %', conflict_count, conflict_detail;
  end if;

  select count(*), string_agg(format('crm_staff_options.id=%s (staff_code=%s)', id, staff_code), '; ')
  into conflict_count, conflict_detail
  from public.crm_staff_options
  where regexp_replace(trim(coalesce(staff_name, '')), '\s+', ' ', 'g') = 'กัญญพักฒ์ อิ่มยวง (เจี๊ยบ)'
    and regexp_replace(trim(coalesce(staff_code, '')), '\s+', ' ', 'g') not in ('', 'JEEB', 'เจี๊ยบ');

  if conflict_count > 0 then
    raise exception 'CONFLICT GUARD TRIPPED in crm_staff_options: % row(s) have JEEB display name but a DIFFERENT staff_code already assigned -- refusing to auto-merge. Rows: %', conflict_count, conflict_detail;
  end if;
end $$;

-- ----------------------------------------------------------------------------
-- STEP 1: Snapshot pre-migration counts (used for the verification in
-- STEP 5). Uses a normalized comparison (trim + collapse internal
-- whitespace) so we catch 'JEEB', 'เจี๊ยบ', or any whitespace-variant of
-- either. crm_orders is NOT included -- confirmed not to exist in
-- Production (see REV 2 change log above).
--
-- By this point STEP 0c has already proven there are zero conflicting rows,
-- so it is now safe for the "affected" definition below to match on
-- staff_code OR owner/staff_name text without re-introducing the danger
-- STEP 0c guards against.
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
from public.crm_lead_followups;

-- Print the pre-migration snapshot for the operator to eyeball before
-- continuing. Expect 0/0 for both rows given the 2026-07-24 investigation --
-- that is normal here, not an error (see REV 2 change log, point 2).
select * from _jeeb_merge_pre_counts order by table_name;

select sum(jeeb_count) as total_jeeb_rows_about_to_move_in_data_tables from _jeeb_merge_pre_counts;

-- Snapshot every OTHER staff_code's row count too (crm_data_imports and
-- crm_lead_followups), so STEP 5 can prove this migration touched nobody
-- else -- approved-scope requirement #8. AU is not special-cased here: it
-- is just one more row in this "everyone else" snapshot, exactly as it
-- should be for this migration.
create temporary table _other_staff_pre_counts as
select
  'crm_data_imports' as table_name,
  regexp_replace(trim(coalesce(staff_code, '')), '\s+', ' ', 'g') as staff_code_norm,
  count(*) as row_count
from public.crm_data_imports
where regexp_replace(trim(coalesce(staff_code, '')), '\s+', ' ', 'g') not in ('JEEB', 'เจี๊ยบ', 'NOONA', '')
group by 1, 2
union all
select
  'crm_lead_followups',
  regexp_replace(trim(coalesce(staff_code, '')), '\s+', ' ', 'g'),
  count(*)
from public.crm_lead_followups
where regexp_replace(trim(coalesce(staff_code, '')), '\s+', ' ', 'g') not in ('JEEB', 'เจี๊ยบ', 'NOONA', '')
group by 1, 2;

-- Snapshot the one specific known data-quality row this migration must
-- leave untouched (owner text = YING's full name, staff_code = 'NOONA').
-- Recorded here by its real id so STEP 5 can prove it did not change.
create temporary table _ying_noona_mismatch_pre as
select id, staff_code, owner, updated_at
from public.crm_data_imports
where id = 536766;

-- ----------------------------------------------------------------------------
-- STEP 2: Backup only the affected rows (full row snapshot, restorable by
-- each table's real primary key -- confirmed in STEP 0a, not assumed).
-- Guard against accidentally overwriting a pre-existing backup table from
-- an earlier partial run.
-- ----------------------------------------------------------------------------

do $$
declare
  existing_backup_tables text;
begin
  select string_agg(table_name, ', ')
  into existing_backup_tables
  from information_schema.tables
  where table_schema = 'public'
    and table_name in (
      'crm_jeeb_noona_merge_backup_20260724_data_imports',
      'crm_jeeb_noona_merge_backup_20260724_lead_followups',
      'crm_jeeb_noona_merge_backup_20260724_user_roles',
      'crm_jeeb_noona_merge_backup_20260724_staff_options'
    );

  if existing_backup_tables is not null then
    raise exception 'BACKUP GUARD TRIPPED: backup table(s) already exist from a prior run: %. Rename/drop them deliberately (after confirming they are no longer needed) before re-running this script, so this run never overwrites a prior backup.', existing_backup_tables;
  end if;
end $$;

create table public.crm_jeeb_noona_merge_backup_20260724_data_imports as
select *
from public.crm_data_imports
where regexp_replace(trim(coalesce(staff_code, '')), '\s+', ' ', 'g') in ('JEEB', 'เจี๊ยบ')
   or regexp_replace(trim(coalesce(owner, '')), '\s+', ' ', 'g') = 'กัญญพักฒ์ อิ่มยวง (เจี๊ยบ)';

create table public.crm_jeeb_noona_merge_backup_20260724_lead_followups as
select *
from public.crm_lead_followups
where regexp_replace(trim(coalesce(staff_code, '')), '\s+', ' ', 'g') in ('JEEB', 'เจี๊ยบ')
   or regexp_replace(trim(coalesce(owner, '')), '\s+', ' ', 'g') = 'กัญญพักฒ์ อิ่มยวง (เจี๊ยบ)';

create table public.crm_jeeb_noona_merge_backup_20260724_user_roles as
select *
from public.crm_user_roles
where regexp_replace(trim(coalesce(staff_code, '')), '\s+', ' ', 'g') in ('JEEB', 'เจี๊ยบ');

create table public.crm_jeeb_noona_merge_backup_20260724_staff_options as
select *
from public.crm_staff_options
where regexp_replace(trim(coalesce(staff_code, '')), '\s+', ' ', 'g') in ('JEEB', 'เจี๊ยบ')
   or regexp_replace(trim(coalesce(staff_name, '')), '\s+', ' ', 'g') = 'กัญญพักฒ์ อิ่มยวง (เจี๊ยบ)';

-- ----------------------------------------------------------------------------
-- STEP 3: Re-attribute JEEB's data to NOONA (staff_code + display owner
-- name) in crm_data_imports and crm_lead_followups. crm_orders is
-- intentionally absent -- it does not exist in Production (REV 2 change
-- log, point 1). Safe to match on staff_code OR owner text here because
-- STEP 0c already proved there is no row where that owner text belongs to
-- a different real staff_code.
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

-- ----------------------------------------------------------------------------
-- STEP 4: Retire JEEB from the staff directory (approved-scope item #3).
-- Deactivate rather than hard-delete by default -- reversible, and per the
-- governance docs' own rule ("ห้ามแก้ข้อมูล production โดยไม่มี backup ก่อน")
-- a soft-disable is the lower-risk choice. The 2026-07-24 investigation
-- found crm_user_roles currently has 0 matching rows (no JEEB login exists
-- to deactivate) and crm_staff_options has exactly 1 (the stale 'เจี๊ยบ'
-- entry, is_active = true) -- both outcomes below are written to handle
-- either 0 or 1+ matching rows correctly, with no special-casing required.
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
-- is committed. Do not remove or weaken these checks. crm_orders is not
-- checked -- it does not exist in Production.
--
-- "0 rows moved" in a given table is treated as PASS, not an error: the
-- check below only compares moved-count against the NOONA delta (internal
-- consistency), so a legitimate 0-before/0-after/0-moved table still
-- verifies cleanly. It never asserts a nonzero row count must exist.
-- ----------------------------------------------------------------------------

do $$
declare
  jeeb_remaining bigint;
  noona_before bigint;
  noona_after bigint;
  jeeb_total_before bigint;
  mismatched_staff text;
  jeeb_staff_options_remaining bigint;
  jeeb_user_roles_remaining bigint;
  au_before bigint;
  au_after bigint;
  ying_noona_owner_before text;
  ying_noona_owner_after text;
  ying_noona_staff_code_after text;
begin
  select coalesce(sum(jeeb_count), 0) into jeeb_total_before from _jeeb_merge_pre_counts;
  select coalesce(sum(noona_count), 0) into noona_before from _jeeb_merge_pre_counts;

  -- 5a. No JEEB left anywhere in scope (crm_data_imports, crm_lead_followups
  -- by staff_code/owner; crm_user_roles/crm_staff_options by staff_code).
  select count(*) into jeeb_remaining
  from (
    select 1 from public.crm_data_imports
    where regexp_replace(trim(coalesce(staff_code, '')), '\s+', ' ', 'g') in ('JEEB', 'เจี๊ยบ')
       or regexp_replace(trim(coalesce(owner, '')), '\s+', ' ', 'g') = 'กัญญพักฒ์ อิ่มยวง (เจี๊ยบ)'
    union all
    select 1 from public.crm_lead_followups
    where regexp_replace(trim(coalesce(staff_code, '')), '\s+', ' ', 'g') in ('JEEB', 'เจี๊ยบ')
       or regexp_replace(trim(coalesce(owner, '')), '\s+', ' ', 'g') = 'กัญญพักฒ์ อิ่มยวง (เจี๊ยบ)'
    union all
    select 1 from public.crm_user_roles
    where regexp_replace(trim(coalesce(staff_code, '')), '\s+', ' ', 'g') in ('JEEB', 'เจี๊ยบ')
    union all
    select 1 from public.crm_staff_options
    where regexp_replace(trim(coalesce(staff_code, '')), '\s+', ' ', 'g') in ('JEEB', 'เจี๊ยบ')
       or regexp_replace(trim(coalesce(staff_name, '')), '\s+', ' ', 'g') = 'กัญญพักฒ์ อิ่มยวง (เจี๊ยบ)'
  ) as remaining;

  if jeeb_remaining <> 0 then
    raise exception 'JEEB merge verification FAILED: % JEEB-tagged row(s) still remain after migration (expected 0)', jeeb_remaining;
  end if;

  -- 5b. NOONA gained exactly the number of rows moved out of JEEB in the two
  -- data tables (crm_user_roles/crm_staff_options don't carry a NOONA
  -- "count" in the same sense -- they are directory rows, not customer
  -- data -- so they are verified separately in 5a/5f instead).
  select
    (select count(*) from public.crm_data_imports where regexp_replace(trim(coalesce(staff_code, '')), '\s+', ' ', 'g') = 'NOONA')
    + (select count(*) from public.crm_lead_followups where regexp_replace(trim(coalesce(staff_code, '')), '\s+', ' ', 'g') = 'NOONA')
  into noona_after;

  if noona_after <> (noona_before + jeeb_total_before) then
    raise exception 'JEEB merge verification FAILED: NOONA row count is % after migration, expected % (% before + % moved from JEEB) -- possible data loss or duplication',
      noona_after, noona_before + jeeb_total_before, noona_before, jeeb_total_before;
  end if;

  -- 5c. Approved-scope item #8: prove no other staff member's row count
  -- changed in crm_data_imports or crm_lead_followups.
  select string_agg(pre.table_name || '/' || pre.staff_code_norm || ' (' || pre.row_count || ' -> ' || post.row_count || ')', ', ')
  into mismatched_staff
  from _other_staff_pre_counts pre
  join (
    select 'crm_data_imports' as table_name,
      regexp_replace(trim(coalesce(staff_code, '')), '\s+', ' ', 'g') as staff_code_norm,
      count(*) as row_count
    from public.crm_data_imports
    where regexp_replace(trim(coalesce(staff_code, '')), '\s+', ' ', 'g') not in ('JEEB', 'เจี๊ยบ', 'NOONA', '')
    group by 1, 2
    union all
    select 'crm_lead_followups',
      regexp_replace(trim(coalesce(staff_code, '')), '\s+', ' ', 'g'),
      count(*)
    from public.crm_lead_followups
    where regexp_replace(trim(coalesce(staff_code, '')), '\s+', ' ', 'g') not in ('JEEB', 'เจี๊ยบ', 'NOONA', '')
    group by 1, 2
  ) as post on post.table_name = pre.table_name and post.staff_code_norm = pre.staff_code_norm
  where post.row_count <> pre.row_count;

  if mismatched_staff is not null then
    raise exception 'JEEB merge verification FAILED: other staff row counts changed unexpectedly: %', mismatched_staff;
  end if;

  -- 5d. AU explicitly, by name, unchanged (governance docs flag AU as a
  -- sensitive case that must never be touched by an unrelated merge). This
  -- is redundant with 5c (AU is just one more staff_code_norm value in that
  -- comparison) -- kept separate for an explicit, human-readable check.
  select count(*) into au_after from public.crm_data_imports
  where regexp_replace(trim(coalesce(staff_code, '')), '\s+', ' ', 'g') = 'AU';
  select row_count into au_before from _other_staff_pre_counts
  where table_name = 'crm_data_imports' and staff_code_norm = 'AU';
  if au_before is not null and au_before <> au_after then
    raise exception 'JEEB merge verification FAILED: AU row count changed (% -> %) -- this migration must never affect AU.', au_before, au_after;
  end if;

  -- 5e. The known YING/NOONA owner-text mismatch row (crm_data_imports.id =
  -- 536766) must be byte-for-byte unchanged -- this migration is JEEB-only
  -- and must not accidentally "fix" or touch this separate, unscoped issue.
  select staff_code, owner into ying_noona_staff_code_after, ying_noona_owner_after
  from public.crm_data_imports where id = 536766;

  select owner into ying_noona_owner_before from _ying_noona_mismatch_pre where id = 536766;

  if (select count(*) from _ying_noona_mismatch_pre) = 1 then
    if ying_noona_owner_after is distinct from ying_noona_owner_before then
      raise exception 'JEEB merge verification FAILED: crm_data_imports.id=536766 (the known YING/NOONA mismatch row) owner text changed from % to % -- this migration must not touch it.', ying_noona_owner_before, ying_noona_owner_after;
    end if;
  end if;

  -- 5f. crm_user_roles / crm_staff_options: no JEEB-tagged rows remain
  -- (redundant with 5a, kept separate for a clearer per-table NOTICE).
  select count(*) into jeeb_user_roles_remaining from public.crm_user_roles
  where regexp_replace(trim(coalesce(staff_code, '')), '\s+', ' ', 'g') in ('JEEB', 'เจี๊ยบ');
  select count(*) into jeeb_staff_options_remaining from public.crm_staff_options
  where regexp_replace(trim(coalesce(staff_code, '')), '\s+', ' ', 'g') in ('JEEB', 'เจี๊ยบ')
     or regexp_replace(trim(coalesce(staff_name, '')), '\s+', ' ', 'g') = 'กัญญพักฒ์ อิ่มยวง (เจี๊ยบ)';

  raise notice 'JEEB merge verification PASSED. Data tables: % row(s) moved from JEEB to NOONA (0 is expected and valid if a prior process already migrated this data). Directory tables: crm_user_roles JEEB-remaining=%, crm_staff_options JEEB-remaining=%. No other staff, AU, or the known YING/NOONA mismatch row (id=536766) were affected.',
    jeeb_total_before, jeeb_user_roles_remaining, jeeb_staff_options_remaining;
end $$;

-- If you reach this line, every check above passed. Review the NOTICE
-- output once more, then either COMMIT (accept) or ROLLBACK (undo
-- everything -- note that the backup tables created in STEP 2 are inside
-- this same transaction, so ROLLBACK undoes them too. If you need the
-- backups to survive a decision to abort the live-table changes, run
-- STEP 0/1/2 as their own committed transaction first, then run
-- STEPs 3/4/5 separately).
commit;

-- ============================================================================
-- ROLLBACK PLAN (only if something is discovered wrong AFTER this script
-- already committed). Each statement below is independently runnable and
-- uses that table's REAL primary key, confirmed in STEP 0a above -- not
-- assumed. Run in this order (reverse of how the migration applied changes:
-- STEP 4 undone first, then STEP 3), inside its own transaction:
--
--   Before restoring anything: compare the CURRENT state of each row
--   against its backup row. If the current row's updated_at is much later
--   than this migration's run time, something else has modified it since
--   (this project already found one uncoordinated process editing this
--   exact data on 2026-07-23) -- stop and review that row by hand instead
--   of blindly overwriting a newer, possibly-intentional change.
--
-- begin;
--
-- -- 1. crm_staff_options (restore by id -- confirmed primary key)
-- update public.crm_staff_options s
-- set staff_code = b.staff_code, staff_name = b.staff_name,
--     is_active = b.is_active, updated_at = b.updated_at
-- from public.crm_jeeb_noona_merge_backup_20260724_staff_options b
-- where s.id = b.id;
--
-- -- 2. crm_user_roles (restore by email -- confirmed primary key, NOT id)
-- update public.crm_user_roles u
-- set staff_code = b.staff_code, staff_name = b.staff_name,
--     is_active = b.is_active, updated_at = b.updated_at
-- from public.crm_jeeb_noona_merge_backup_20260724_user_roles b
-- where u.email = b.email;
--
-- -- 3. crm_lead_followups (restore by id -- confirmed primary key)
-- update public.crm_lead_followups f
-- set staff_code = b.staff_code, owner = b.owner, updated_at = b.updated_at
-- from public.crm_jeeb_noona_merge_backup_20260724_lead_followups b
-- where f.id = b.id;
--
-- -- 4. crm_data_imports (restore by id -- confirmed primary key)
-- update public.crm_data_imports d
-- set staff_code = b.staff_code, owner = b.owner, updated_at = b.updated_at
-- from public.crm_jeeb_noona_merge_backup_20260724_data_imports b
-- where d.id = b.id;
--
-- -- Verify each table's affected row count matches its backup's row count
-- -- before committing the rollback, then:
-- commit;
-- ============================================================================
