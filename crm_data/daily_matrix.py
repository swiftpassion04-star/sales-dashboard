"""Daily, per-staff sales matrix for the Upsell and CRM (ยา อาหารเสริม) teams.

Auto-computed from real orders (crm_data_imports.staff_code), never manually
typed in. Attribution to a team goes through the existing
crm_user_roles.staff_code -> email -> crm_user_team_assignments chain -- no
new roster table. See pages/daily_matrix.py for the rendering side.
"""

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


def _empty_team_bucket(team_code: str) -> dict:
    return {
        "team_name": TEAM_CODES[team_code],
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


@st.cache_data(ttl=120, show_spinner=False)
def fetch_daily_matrix(year: int, month: int, conn_or_none=None) -> dict:
    month_start, month_end = _month_bounds(year, month)

    teams = {code: _empty_team_bucket(code) for code in TEAM_CODES}
    team_columns_seen = {code: {} for code in TEAM_CODES}
    ambiguous_staff_codes: set[str] = set()

    # Seed every team's column set from roster+assignments FIRST, so a
    # zero-sales staff member still gets a (zero-filled) column below.
    for roster_row in _fetch_team_roster_columns(month_start, month_end, conn_or_none):
        team_code = roster_row["team_code"]
        if team_code in TEAM_CODES:
            team_columns_seen[team_code].setdefault(
                roster_row["staff_code_norm"],
                roster_row.get("staff_name") or roster_row["staff_code_norm"],
            )

    rows = _fetch_all(
        f"""
        with {_ROSTER_CTE_SQL},
        sales as (
          select
            regexp_replace(trim(coalesce(d.staff_code, '')), '\\s+', ' ', 'g') as staff_code_norm,
            d.order_date,
            sum(d.amount) as day_amount
          from public.crm_data_imports d
          where d.order_date >= %s
            and d.order_date < %s
            and {_MANUAL_ROW_SQL}
            and d.sale_type in ('NEW_ORDER', 'UPSELL', '⭐NEW_ORDER', '⭐UPSELL')
            and nullif(trim(coalesce(d.staff_code, '')), '') is not null
          group by 1, 2
        )
        select
          s.staff_code_norm,
          s.order_date,
          s.day_amount,
          r.staff_name,
          a.team_code,
          (a2.staff_code_norm is not null) as is_ambiguous
        from sales s
        left join roster r on r.staff_code_norm = s.staff_code_norm
        left join public.crm_user_team_assignments a
          on a.user_email = r.email
         and a.effective_from <= (s.order_date::timestamp at time zone 'Asia/Bangkok')
         and (a.effective_to is null or a.effective_to > (s.order_date::timestamp at time zone 'Asia/Bangkok'))
        left join ambiguous a2 on a2.staff_code_norm = s.staff_code_norm
        order by s.order_date, s.staff_code_norm
        """,
        [month_start, month_end],
        conn_or_none,
    )

    unassigned_days: dict[date, float] = {}
    unassigned_total = 0.0

    for row in rows:
        staff_code = row["staff_code_norm"]
        order_date = row["order_date"]
        amount = float(row["day_amount"] or 0)
        team_code = row.get("team_code")
        if row.get("is_ambiguous"):
            ambiguous_staff_codes.add(staff_code)

        if team_code in TEAM_CODES:
            # Defensive only: _fetch_team_roster_columns already covers any
            # team_code active on this order_date, since its month-level
            # overlap window is always a superset of any single day in it.
            team_columns_seen[team_code].setdefault(
                staff_code, row.get("staff_name") or staff_code
            )
            day_bucket = teams[team_code]["days"].setdefault(
                order_date, {"per_staff": {}, "team_total": 0.0}
            )
            day_bucket["per_staff"][staff_code] = amount
            day_bucket["team_total"] += amount
        else:
            unassigned_days[order_date] = unassigned_days.get(order_date, 0.0) + amount
            unassigned_total += amount

    for team_code in TEAM_CODES:
        columns = [
            {"staff_code": code, "staff_name": name}
            for code, name in team_columns_seen[team_code].items()
        ]
        columns.sort(key=lambda item: (item["staff_name"], item["staff_code"]))
        teams[team_code]["columns"] = columns

    return {
        "month_start": month_start,
        "month_end_exclusive": month_end,
        "teams": teams,
        "unassigned": {"days": unassigned_days, "total": unassigned_total},
        "ambiguous_staff_codes": sorted(ambiguous_staff_codes),
    }


@st.cache_data(ttl=120, show_spinner=False)
def fetch_day_statuses(year: int, month: int, conn_or_none=None) -> dict:
    month_start, month_end = _month_bounds(year, month)
    rows = _fetch_all(
        """
        select status_date, status, note
        from public.crm_daily_status
        where status_date >= %s and status_date < %s
        order by status_date
        """,
        [month_start, month_end],
        conn_or_none,
    )
    return {row["status_date"]: {"status": row["status"], "note": row["note"]} for row in rows}


def _normalized_actor_email(value: str | None) -> str | None:
    email = str(value or "").strip().lower()
    return email or None


def save_day_status(
    *,
    status_date: date,
    status: str,
    note: str | None = None,
    actor_email: str | None = None,
    conn_or_none=None,
) -> dict:
    normalized_status = str(status or "").strip().upper()
    if normalized_status not in DAY_STATUS_VALUES:
        raise ValueError("status must be HOLIDAY or LEAVE")
    normalized_note = str(note or "").strip() or None
    normalized_actor = _normalized_actor_email(actor_email)

    with _connection(conn_or_none) as conn:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    insert into public.crm_daily_status (
                      status_date, status, note, created_by, updated_by
                    )
                    values (%s, %s, %s, %s, %s)
                    on conflict (status_date) do update
                    set status = excluded.status,
                        note = excluded.note,
                        updated_at = now(),
                        updated_by = excluded.updated_by
                    returning status_date, status, note
                    """,
                    [status_date, normalized_status, normalized_note, normalized_actor, normalized_actor],
                )
                result = dict(cur.fetchone())
            conn.commit()
            return result
        except Exception:
            conn.rollback()
            raise


def clear_day_status(*, status_date: date, actor_email: str | None = None, conn_or_none=None) -> dict:
    with _connection(conn_or_none) as conn:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "delete from public.crm_daily_status where status_date = %s",
                    [status_date],
                )
                deleted = cur.rowcount
            conn.commit()
            return {"status_date": status_date, "deleted": bool(deleted)}
        except Exception:
            conn.rollback()
            raise


def clear_daily_matrix_caches() -> None:
    fetch_daily_matrix.clear()
    fetch_day_statuses.clear()
