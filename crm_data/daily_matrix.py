"""Daily, per-staff sales matrix for the Upsell and CRM (ยา อาหารเสริม) teams.

Auto-computed from real orders (crm_data_imports.staff_code), never manually
typed in. Attribution to a team goes through the existing
crm_user_roles.staff_code -> email -> crm_user_team_assignments chain -- no
new roster table. See pages/daily_matrix.py for the rendering side.
"""

import re
from contextlib import contextmanager
from datetime import date, timedelta

import streamlit as st

from crm_data.team_sales import TEAM_CODES, _MANUAL_ROW_SQL, _date_bounds

# Individual UPSELL cell: light-yellow above this, blue above the next one.
UPSELL_YELLOW_THRESHOLD = 3000
UPSELL_BLUE_THRESHOLD = 4500
# UPSELL team-total-for-the-day cell.
UPSELL_TEAM_TOTAL_THRESHOLD = 11000
# Individual CRM (ยา อาหารเสริม) cell.
CRM_INDIVIDUAL_THRESHOLD = 11000
# CRM team-total-for-the-day cell.
CRM_TEAM_TOTAL_THRESHOLD = 40000

DAY_STATUS_VALUES = {"HOLIDAY", "LEAVE"}

# staff_code values with real sales but no active (or no) team assignment
# for that day -- kept as a full team-shaped block (not a flat total) so
# attribution can still be audited per person/day, exactly like a real team.
UNASSIGNED_TEAM_CODE = "UNASSIGNED_TEAM"
UNASSIGNED_TEAM_NAME = "ไม่มีทีม"

# All three matrix blocks share the same {code: name} shape. UPSELL_TEAM/
# CRM_TEAM come from crm_data.team_sales (the real, shared team concept);
# UNASSIGNED_TEAM only exists inside this module -- it isn't a real team.
TEAM_BUCKET_NAMES = {**TEAM_CODES, UNASSIGNED_TEAM_CODE: UNASSIGNED_TEAM_NAME}

# Matches a parenthesized group at the very end of a name, e.g.
# "พรนภา นันที (หนูนา)" -> "หนูนา". Only the trailing group counts -- a
# parenthesized aside in the middle of a name is left alone.
_TRAILING_PAREN_RE = re.compile(r"\(([^()]*)\)\s*$")

_WHITESPACE_RUN_RE = re.compile(r"\s+")


def format_staff_display_name(staff_name, staff_code) -> str:
    """Short display label for a matrix column header.

    Never used for aggregation -- staff_code stays the join/dict key
    everywhere else in this module. This only decides what text a human
    reads in the header.
    """
    name = str(staff_name or "").strip()
    match = _TRAILING_PAREN_RE.search(name)
    if match:
        inner = match.group(1).strip()
        if inner:
            return inner
    if name:
        return name
    return str(staff_code or "").strip()


def resolve_cell_status_highlight(all_status, staff_statuses: dict, staff_code: str):
    """Decide whether one staff's cell on one day gets a personal (STAFF-scope)
    day-off highlight, as opposed to a company-wide (ALL-scope) day-off which
    highlights the whole row instead (handled at the row level, not here).

    Returns None when no personal highlight applies -- either nothing is
    set for this staff_code, or an ALL-scope status already covers the
    whole row so a duplicate per-cell highlight would be redundant. Looks
    up ONLY the exact staff_code passed in, so one person's STAFF-scope
    status can never bleed into another person's cell on the same day.
    """
    if all_status:
        return None
    return staff_statuses.get(staff_code)


def classify_upsell_cell_tone(amount) -> str:
    value = float(amount or 0)
    if value > UPSELL_BLUE_THRESHOLD:
        return "blue"
    if value > UPSELL_YELLOW_THRESHOLD:
        return "yellow"
    return "normal"


def classify_crm_cell_tone(amount) -> str:
    value = float(amount or 0)
    if value > CRM_INDIVIDUAL_THRESHOLD:
        return "green"
    return "normal"


def classify_team_total_tone(amount, threshold) -> str:
    value = float(amount or 0)
    if value > float(threshold):
        return "green"
    return "normal"


@contextmanager
def _connection(conn_or_none=None):
    if conn_or_none is not None:
        yield conn_or_none
        return

    from neon_utils import neon_connection

    with neon_connection() as conn:
        yield conn


def _fetch_all(sql: str, params: list, conn_or_none=None) -> list[dict]:
    with _connection(conn_or_none) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return [dict(row) for row in cur.fetchall()]


def _month_bounds(year: int, month: int) -> tuple[date, date]:
    if month < 1 or month > 12:
        raise ValueError("month must be between 1 and 12")
    start = date(year, month, 1)
    end = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    return start, end


def _empty_team_bucket(bucket_code: str) -> dict:
    return {
        "team_name": TEAM_BUCKET_NAMES[bucket_code],
        "columns": [],
        "days": {},
    }


# Shared by both queries below so a staff_code/email is resolved identically
# whether we're asking "who's on this team this month" or "whose sale is
# this". staff_code has no unique constraint on crm_user_roles -- resolve
# any duplicate deterministically (never silently drop or silently pick one
# without recording it) via the `ambiguous` CTE, surfaced to the caller.
_ROSTER_CTE_SQL = """
roster_raw as (
  select
    regexp_replace(trim(coalesce(staff_code, '')), '\\s+', ' ', 'g') as staff_code_norm,
    lower(btrim(email)) as email,
    staff_name
  from public.crm_user_roles
  where is_active = true
    and nullif(trim(coalesce(staff_code, '')), '') is not null
),
roster as (
  select distinct on (staff_code_norm)
    staff_code_norm, email, staff_name
  from roster_raw
  order by staff_code_norm, email
),
ambiguous as (
  select staff_code_norm
  from roster_raw
  group by staff_code_norm
  having count(*) > 1
)
""".strip()


def _fetch_team_roster_columns(month_start: date, month_end: date, conn_or_none=None) -> list[dict]:
    """Every staff_code with a team assignment overlapping the month.

    Driven by roster + team assignments, NOT by sales -- a staff member who
    made zero sales all month must still appear as a (zero-filled) column,
    never silently vanish from the matrix.
    """
    last_day = month_end - timedelta(days=1)
    month_start_ts, month_end_ts = _date_bounds(month_start, last_day)
    return _fetch_all(
        f"""
        with {_ROSTER_CTE_SQL}
        select distinct
          a.team_code,
          r.staff_code_norm,
          r.staff_name
        from roster r
        join public.crm_user_team_assignments a on a.user_email = r.email
        where a.team_code in ('CRM_TEAM', 'UPSELL_TEAM')
          and a.effective_from < %s
          and (a.effective_to is null or a.effective_to > %s)
        order by 1, 3, 2
        """,
        [month_end_ts, month_start_ts],
        conn_or_none,
    )


def _build_matrix_from_rows(
    roster_rows: list[dict],
    sales_rows: list[dict],
    month_start: date,
    month_end: date,
) -> dict:
    """Pure transform: roster rows + sales-attribution rows -> matrix dict.

    Deliberately DB/cache-free so this can be unit tested directly, without
    routing a fake connection through @st.cache_data's argument hashing.
    """
    teams = {code: _empty_team_bucket(code) for code in TEAM_BUCKET_NAMES}
    team_columns_seen = {code: {} for code in TEAM_BUCKET_NAMES}
    ambiguous_staff_codes: set[str] = set()

    # Seed every team's column set from roster+assignments FIRST, so a
    # zero-sales staff member still gets a (zero-filled) column below.
    for roster_row in roster_rows:
        team_code = roster_row["team_code"]
        if team_code in TEAM_CODES:
            team_columns_seen[team_code].setdefault(
                roster_row["staff_code_norm"],
                roster_row.get("staff_name") or roster_row["staff_code_norm"],
            )

    for row in sales_rows:
        staff_code = row["staff_code_norm"]
        sales_date = row["sales_date"]
        amount = float(row["day_amount"] or 0)
        team_code = row.get("team_code")
        if row.get("is_ambiguous"):
            ambiguous_staff_codes.add(staff_code)

        # A real team_code routes here exactly like before. Anything else
        # (no roster match, no active assignment that day) routes to
        # UNASSIGNED_TEAM instead of a flat total -- same per-staff/day
        # shape as a real team, so the sale is never lost and attribution
        # stays auditable. _fetch_team_roster_columns already covers any
        # team_code active on this sales_date for UPSELL_TEAM/CRM_TEAM
        # (its month-level overlap window is always a superset of any
        # single day in it) -- this setdefault is defensive only for those
        # two, and the sole source of columns for UNASSIGNED_TEAM (there is
        # no "roster of unassigned people" to pre-seed from).
        bucket_code = team_code if team_code in TEAM_CODES else UNASSIGNED_TEAM_CODE

        team_columns_seen[bucket_code].setdefault(
            staff_code, row.get("staff_name") or staff_code
        )
        day_bucket = teams[bucket_code]["days"].setdefault(
            sales_date, {"per_staff": {}, "team_total": 0.0}
        )
        day_bucket["per_staff"][staff_code] = amount
        day_bucket["team_total"] += amount

    for bucket_code in TEAM_BUCKET_NAMES:
        columns = [
            {"staff_code": code, "staff_name": name}
            for code, name in team_columns_seen[bucket_code].items()
        ]
        columns.sort(key=lambda item: (item["staff_name"], item["staff_code"]))
        teams[bucket_code]["columns"] = columns

    unassigned_total = sum(
        day["team_total"] for day in teams[UNASSIGNED_TEAM_CODE]["days"].values()
    )

    return {
        "month_start": month_start,
        "month_end_exclusive": month_end,
        "teams": teams,
        "unassigned": {"total": unassigned_total},
        "ambiguous_staff_codes": sorted(ambiguous_staff_codes),
    }


@st.cache_data(ttl=120, show_spinner=False)
def fetch_daily_matrix(year: int, month: int, conn_or_none=None) -> dict:
    month_start, month_end = _month_bounds(year, month)
    last_day = month_end - timedelta(days=1)
    month_start_ts, month_end_ts = _date_bounds(month_start, last_day)

    roster_rows = _fetch_team_roster_columns(month_start, month_end, conn_or_none)

    sales_rows = _fetch_all(
        f"""
        with {_ROSTER_CTE_SQL},
        sales as (
          select
            regexp_replace(trim(coalesce(d.staff_code, '')), '\\s+', ' ', 'g') as staff_code_norm,
            (d.created_at at time zone 'Asia/Bangkok')::date as sales_date,
            sum(d.amount) as day_amount
          from public.crm_data_imports d
          where d.created_at >= %s
            and d.created_at < %s
            and {_MANUAL_ROW_SQL}
            and d.sale_type in ('NEW_ORDER', 'UPSELL', '⭐NEW_ORDER', '⭐UPSELL')
            and nullif(trim(coalesce(d.staff_code, '')), '') is not null
          group by 1, 2
        )
        select
          s.staff_code_norm,
          s.sales_date,
          s.day_amount,
          r.staff_name,
          a.team_code,
          (a2.staff_code_norm is not null) as is_ambiguous
        from sales s
        left join roster r on r.staff_code_norm = s.staff_code_norm
        left join public.crm_user_team_assignments a
          on a.user_email = r.email
         and a.effective_from <= (s.sales_date::timestamp at time zone 'Asia/Bangkok')
         and (a.effective_to is null or a.effective_to > (s.sales_date::timestamp at time zone 'Asia/Bangkok'))
        left join ambiguous a2 on a2.staff_code_norm = s.staff_code_norm
        order by s.sales_date, s.staff_code_norm
        """,
        [month_start_ts, month_end_ts],
        conn_or_none,
    )

    return _build_matrix_from_rows(roster_rows, sales_rows, month_start, month_end)


DAY_STATUS_SCOPES = {"ALL", "STAFF"}


def _build_day_statuses_from_rows(rows: list[dict]) -> dict:
    """Pure transform: crm_daily_status rows -> {date: {"all", "staff"}}.

    DB/cache-free so this can be unit tested directly, without routing a
    fake connection through @st.cache_data's argument hashing.
    """
    result: dict = {}
    for row in rows:
        bucket = result.setdefault(row["status_date"], {"all": None, "staff": {}})
        entry = {"status": row["status"], "note": row["note"]}
        if row["scope_type"] == "ALL":
            bucket["all"] = entry
        else:
            bucket["staff"][row["staff_code"]] = entry
    return result


@st.cache_data(ttl=120, show_spinner=False)
def fetch_day_statuses(year: int, month: int, conn_or_none=None) -> dict:
    """{date: {"all": {"status","note"} | None, "staff": {staff_code: {"status","note"}}}}

    A date can carry one company-wide (ALL) status and any number of
    independent per-staff (STAFF) statuses at once -- both are surfaced
    together, never collapsed into a single value.
    """
    month_start, month_end = _month_bounds(year, month)
    rows = _fetch_all(
        """
        select status_date, scope_type, staff_code, status, note
        from public.crm_daily_status
        where status_date >= %s and status_date < %s
        order by status_date, scope_type, staff_code
        """,
        [month_start, month_end],
        conn_or_none,
    )
    return _build_day_statuses_from_rows(rows)


def _normalized_actor_email(value: str | None) -> str | None:
    email = str(value or "").strip().lower()
    return email or None


def _normalize_staff_code(value) -> str:
    text = str(value or "").strip()
    return _WHITESPACE_RUN_RE.sub(" ", text) if text else ""


def _validate_status_scope(status: str, scope_type: str, staff_code) -> tuple[str, str, str]:
    """Shared validation for save/clear -- returns (status, scope_type, staff_code_or_empty).

    Mirrors the DB CHECK constraint exactly (crm_daily_status_scope_staff_code_chk)
    so a caller gets the same rejection locally, before ever touching the DB.
    """
    normalized_status = str(status or "").strip().upper()
    if normalized_status not in DAY_STATUS_VALUES:
        raise ValueError("status must be HOLIDAY or LEAVE")

    normalized_scope = str(scope_type or "").strip().upper()
    if normalized_scope not in DAY_STATUS_SCOPES:
        raise ValueError("scope_type must be ALL or STAFF")

    normalized_staff_code = _normalize_staff_code(staff_code)
    if normalized_scope == "STAFF" and not normalized_staff_code:
        raise ValueError("staff_code is required when scope_type is STAFF")
    if normalized_scope == "ALL" and normalized_staff_code:
        raise ValueError("staff_code must not be set when scope_type is ALL")

    return normalized_status, normalized_scope, normalized_staff_code


def save_day_status(
    *,
    status_date: date,
    status: str,
    scope_type: str,
    staff_code: str | None = None,
    note: str | None = None,
    actor_email: str | None = None,
    conn_or_none=None,
) -> dict:
    normalized_status, normalized_scope, normalized_staff_code = _validate_status_scope(
        status, scope_type, staff_code
    )
    staff_code_param = normalized_staff_code or None
    normalized_note = str(note or "").strip() or None
    normalized_actor = _normalized_actor_email(actor_email)

    with _connection(conn_or_none) as conn:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    insert into public.crm_daily_status (
                      status_date, scope_type, staff_code, status, note, created_by, updated_by
                    )
                    values (%s, %s, %s, %s, %s, %s, %s)
                    on conflict (status_date, scope_type, (coalesce(staff_code, '')))
                    do update
                    set status = excluded.status,
                        note = excluded.note,
                        updated_at = now(),
                        updated_by = excluded.updated_by
                    returning status_date, scope_type, staff_code, status, note
                    """,
                    [
                        status_date,
                        normalized_scope,
                        staff_code_param,
                        normalized_status,
                        normalized_note,
                        normalized_actor,
                        normalized_actor,
                    ],
                )
                result = dict(cur.fetchone())
            conn.commit()
            return result
        except Exception:
            conn.rollback()
            raise


def clear_day_status(
    *,
    status_date: date,
    scope_type: str,
    staff_code: str | None = None,
    actor_email: str | None = None,
    conn_or_none=None,
) -> dict:
    normalized_scope = str(scope_type or "").strip().upper()
    if normalized_scope not in DAY_STATUS_SCOPES:
        raise ValueError("scope_type must be ALL or STAFF")
    normalized_staff_code = _normalize_staff_code(staff_code)
    if normalized_scope == "STAFF" and not normalized_staff_code:
        raise ValueError("staff_code is required when scope_type is STAFF")
    if normalized_scope == "ALL" and normalized_staff_code:
        raise ValueError("staff_code must not be set when scope_type is ALL")
    staff_code_param = normalized_staff_code or None

    with _connection(conn_or_none) as conn:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    delete from public.crm_daily_status
                    where status_date = %s
                      and scope_type = %s
                      and coalesce(staff_code, '') = coalesce(%s, '')
                    """,
                    [status_date, normalized_scope, staff_code_param],
                )
                deleted = cur.rowcount
            conn.commit()
            return {
                "status_date": status_date,
                "scope_type": normalized_scope,
                "staff_code": staff_code_param,
                "deleted": bool(deleted),
            }
        except Exception:
            conn.rollback()
            raise


def clear_daily_matrix_caches() -> None:
    fetch_daily_matrix.clear()
    fetch_day_statuses.clear()
