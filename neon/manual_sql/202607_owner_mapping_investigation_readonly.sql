-- ============================================================================
-- Owner/Staff Mapping investigation -- READ-ONLY, safe to run anytime.
-- ============================================================================
-- Purpose: confirm the specific counts referenced in the Owner Mapping review
-- (2026-07-23) against real data, and surface exact row identifiers for
-- human review where judgment is required. Every statement below is a
-- SELECT -- nothing here writes, updates, or deletes anything.
--
-- The environment that authored this script has no NEON_DATABASE_URL and
-- cannot run these queries itself. Run each section with:
--   psql "$NEON_DATABASE_URL" -f 202607_owner_mapping_investigation_readonly.sql
-- and share the output back for review before any fix is written.
-- ============================================================================


-- ----------------------------------------------------------------------------
-- SECTION A: Follow-up rows that are alias variants of the SAME person
-- (expected ~173). Groups crm_lead_followups by staff_code, showing every
-- distinct raw owner text on file for that code -- a staff_code with more
-- than one owner-text variant is exactly the "alias fragmentation" case.
-- ----------------------------------------------------------------------------

select
  staff_code,
  count(distinct regexp_replace(trim(coalesce(owner, '')), '\s+', ' ', 'g')) as distinct_owner_text_variants,
  count(*) as row_count,
  array_agg(distinct regexp_replace(trim(coalesce(owner, '')), '\s+', ' ', 'g')) as owner_text_variants
from public.crm_lead_followups
where nullif(trim(coalesce(staff_code, '')), '') is not null
group by staff_code
having count(distinct regexp_replace(trim(coalesce(owner, '')), '\s+', ' ', 'g')) > 1
order by row_count desc;

-- Total row count across every staff_code that has more than one owner-text
-- variant -- compare this sum against the expected ~173.
with variant_groups as (
  select staff_code
  from public.crm_lead_followups
  where nullif(trim(coalesce(staff_code, '')), '') is not null
  group by staff_code
  having count(distinct regexp_replace(trim(coalesce(owner, '')), '\s+', ' ', 'g')) > 1
)
select count(*) as total_alias_variant_rows
from public.crm_lead_followups f
join variant_groups g on g.staff_code = f.staff_code;


-- ----------------------------------------------------------------------------
-- SECTION B: Follow-up rows that LOOK like alias variants (same normalized
-- owner display text) but are actually DIFFERENT real people (expected 3).
-- This is the dangerous case rule #7/#8 in the review explicitly forbid
-- auto-merging -- surfaced here for a human to inspect row-by-row, never
-- to be resolved automatically.
-- ----------------------------------------------------------------------------

select
  regexp_replace(trim(coalesce(owner, '')), '\s+', ' ', 'g') as owner_text_normalized,
  count(distinct staff_code) as distinct_staff_codes,
  array_agg(distinct staff_code) as staff_codes,
  array_agg(id order by id) as row_ids
from public.crm_lead_followups
where nullif(trim(coalesce(owner, '')), '') is not null
  and nullif(trim(coalesce(staff_code, '')), '') is not null
group by regexp_replace(trim(coalesce(owner, '')), '\s+', ' ', 'g')
having count(distinct staff_code) > 1
order by distinct_staff_codes desc;

-- Row-level detail for manual inspection (id, staff_code, owner text, phone,
-- customer name, last updated) -- the minimum needed to tell whether each
-- row is a genuine distinct person, without exposing more than necessary.
select
  f.id,
  f.staff_code,
  regexp_replace(trim(coalesce(f.owner, '')), '\s+', ' ', 'g') as owner_text_normalized,
  f.customer_name,
  f.updated_at
from public.crm_lead_followups f
join (
  select regexp_replace(trim(coalesce(owner, '')), '\s+', ' ', 'g') as owner_text_normalized
  from public.crm_lead_followups
  where nullif(trim(coalesce(owner, '')), '') is not null
    and nullif(trim(coalesce(staff_code, '')), '') is not null
  group by 1
  having count(distinct staff_code) > 1
) as ambiguous on regexp_replace(trim(coalesce(f.owner, '')), '\s+', ' ', 'g') = ambiguous.owner_text_normalized
order by owner_text_normalized, f.staff_code, f.id;


-- ----------------------------------------------------------------------------
-- SECTION C: Order rows where staff_code does not correspond to owner text
-- (expected 1). This is the exact inconsistency the new
-- staff_identity.validate_owner_staff_code() now blocks on future writes --
-- this query finds it in EXISTING data.
-- ----------------------------------------------------------------------------

select
  d.id,
  d.order_id,
  d.owner,
  d.staff_code,
  regexp_replace(trim(coalesce(d.owner, '')), '\s+', ' ', 'g') as owner_text_normalized
from public.crm_data_imports d
where nullif(trim(coalesce(d.owner, '')), '') is not null
  and nullif(trim(coalesce(d.staff_code, '')), '') is not null
  -- Owner text does not match ANY known staff_name for that same staff_code
  -- in either source-of-truth table.
  and not exists (
    select 1
    from (
      select staff_code, staff_name from public.crm_user_roles
      union all
      select staff_code, staff_name from public.crm_staff_options
    ) as directory
    where directory.staff_code = d.staff_code
      and regexp_replace(trim(coalesce(directory.staff_name, '')), '\s+', ' ', 'g')
        = regexp_replace(trim(coalesce(d.owner, '')), '\s+', ' ', 'g')
  );


-- ----------------------------------------------------------------------------
-- SECTION D: Follow-up rows where staff_code holds a full Thai name instead
-- of a short code (expected ~35). Heuristic: contains whitespace, is longer
-- than a reasonable code, or contains non-ASCII (Thai) characters.
-- ----------------------------------------------------------------------------

select
  id,
  staff_code,
  owner,
  customer_name,
  updated_at
from public.crm_lead_followups
where nullif(trim(coalesce(staff_code, '')), '') is not null
  and (
    staff_code ~ '\s'
    or length(staff_code) > 12
    or staff_code ~ '[^\x00-\x7F]'
  )
order by id;

select count(*) as full_name_as_staff_code_row_count
from public.crm_lead_followups
where nullif(trim(coalesce(staff_code, '')), '') is not null
  and (
    staff_code ~ '\s'
    or length(staff_code) > 12
    or staff_code ~ '[^\x00-\x7F]'
  );


-- ----------------------------------------------------------------------------
-- SECTION E: Overall sanity numbers, for context alongside the above.
-- ----------------------------------------------------------------------------

select
  count(*) as total_followups,
  count(*) filter (where nullif(trim(coalesce(staff_code, '')), '') is null) as blank_staff_code,
  count(*) filter (where nullif(trim(coalesce(owner, '')), '') is null) as blank_owner
from public.crm_lead_followups;

select
  count(*) as total_orders,
  count(*) filter (where nullif(trim(coalesce(staff_code, '')), '') is null) as blank_staff_code,
  count(*) filter (where nullif(trim(coalesce(owner, '')), '') is null) as blank_owner
from public.crm_data_imports;
