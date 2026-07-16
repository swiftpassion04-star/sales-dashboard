from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone

from crm_data.common import BANGKOK_TZ


TEAM_CODES = {
    "CRM_TEAM": "CRM Team",
    "UPSELL_TEAM": "Upsell Team",
}

UNASSIGNED_TEAM_CODE = "UNASSIGNED"
UNASSIGNED_TEAM_NAME = "ยังไม่เลือกทีม"
_SALE_TYPES = {"NEW_ORDER", "UPSELL", "⭐NEW_ORDER", "⭐UPSELL"}

_MANUAL_ROW_SQL = """
(
  coalesce(d.source_type, '') = 'manual'
  or coalesce(d.source_file_name, '') = 'manual_order'
  or coalesce(d.raw_data->>'source', '') = 'manual_order'
)
""".strip()

_RAW_QUANTITY_SQL = """
case
  when nullif(btrim(d.raw_data->>'qty'), '') ~ '^[0-9]+(\\.[0-9]+)?$'
    then (d.raw_data->>'qty')::numeric
end
""".strip()

_RAW_THAI_QUANTITY_SQL = """
case
  when nullif(btrim(d.raw_data->>'จำนวน'), '') ~ '^[0-9]+(\\.[0-9]+)?$'
    then (d.raw_data->>'จำนวน')::numeric
end
""".strip()

_EFFECTIVE_QUANTITY_SQL = (
    f"coalesce(d.quantity, {_RAW_QUANTITY_SQL}, {_RAW_THAI_QUANTITY_SQL}, 1)"
)
_BASE_RAW_QUANTITY_SQL = _RAW_QUANTITY_SQL.replace("d.", "")
_BASE_RAW_THAI_QUANTITY_SQL = _RAW_THAI_QUANTITY_SQL.replace("d.", "")


@contextmanager
def _connection(conn_or_none=None):
    if conn_or_none is not None:
        yield conn_or_none
        return

    from neon_utils import neon_connection

    with neon_connection() as conn:
        yield conn


def _date_bounds(start_date: date, end_date: date) -> tuple[datetime, datetime]:
    if end_date < start_date:
        raise ValueError("end_date must be on or after start_date")
    start_ts = datetime.combine(
        start_date, datetime.min.time(), tzinfo=BANGKOK_TZ
    ).astimezone(timezone.utc)
    end_ts = datetime.combine(
        end_date + timedelta(days=1), datetime.min.time(), tzinfo=BANGKOK_TZ
    ).astimezone(timezone.utc)
    return start_ts, end_ts


def _sale_type_filter(sale_type_filter: str | None) -> tuple[str, list]:
    if sale_type_filter is None or not str(sale_type_filter).strip():
        return "", []
    sale_type = str(sale_type_filter).strip().upper()
    if sale_type not in _SALE_TYPES:
        raise ValueError("sale_type_filter must be NEW_ORDER, UPSELL, starred NEW_ORDER, starred UPSELL, or None")
    return "and d.sale_type = %s", [sale_type]


def _team_filter(team_code: str | None) -> tuple[str, list, str, str]:
    if team_code is None or not str(team_code).strip():
        return "", [], "null::text", "null::text"
    normalized = str(team_code).strip().upper()
    if normalized not in TEAM_CODES:
        raise ValueError("team_code must be CRM_TEAM, UPSELL_TEAM, or None")
    return "and a.team_code = %s", [normalized], "a.team_code", "a.team_name"


def _fetch_all(sql: str, params: list, conn_or_none=None) -> list[dict]:
    with _connection(conn_or_none) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return [dict(row) for row in cur.fetchall()]


def fetch_team_assignment_users(conn_or_none=None) -> list[dict]:
    return _fetch_all(
        """
        select
          u.email,
          u.role,
          u.staff_code,
          u.staff_name,
          u.is_active,
          a.team_code as current_team_code,
          a.team_name as current_team_name,
          a.effective_from,
          a.effective_to
        from public.crm_user_roles u
        left join public.crm_user_team_assignments a
          on a.user_email = lower(btrim(u.email))
         and a.effective_to is null
        where u.is_active = true
        order by coalesce(nullif(u.staff_name, ''), u.email), u.email
        """,
        [],
        conn_or_none,
    )


def fetch_team_sales_summary(
    start_date: date,
    end_date: date,
    sale_type_filter: str | None = None,
) -> dict:
    start_ts, end_ts = _date_bounds(start_date, end_date)
    sale_clause, sale_params = _sale_type_filter(sale_type_filter)
    rows = _fetch_all(
        f"""
        with attributed as (
          select
            d.order_id,
            d.amount,
            a.team_code,
            a.team_name
          from public.crm_data_imports d
          left join public.crm_user_team_assignments a
            on a.user_email = lower(btrim(d.uploaded_by))
           and d.created_at >= a.effective_from
           and (a.effective_to is null or d.created_at < a.effective_to)
          where d.created_at >= %s
            and d.created_at < %s
            and {_MANUAL_ROW_SQL}
            and d.sale_type in ('NEW_ORDER', 'UPSELL', '⭐NEW_ORDER', '⭐UPSELL')
            {sale_clause}
        )
        select
          coalesce(team_code, %s) as team_code,
          coalesce(team_name, %s) as team_name,
          count(distinct nullif(btrim(order_id), '')) as order_count,
          coalesce(sum(amount), 0) as sales_amount,
          count(*) as row_count
        from attributed
        group by team_code, team_name
        order by team_code nulls last
        """,
        [
            start_ts,
            end_ts,
            *sale_params,
            UNASSIGNED_TEAM_CODE,
            UNASSIGNED_TEAM_NAME,
        ],
    )

    teams = {
        code: {
            "team_code": code,
            "team_name": name,
            "order_count": 0,
            "sales_amount": 0.0,
            "row_count": 0,
        }
        for code, name in TEAM_CODES.items()
    }
    unassigned = {
        "team_code": UNASSIGNED_TEAM_CODE,
        "team_name": UNASSIGNED_TEAM_NAME,
        "order_count": 0,
        "sales_amount": 0.0,
        "row_count": 0,
    }
    for row in rows:
        item = {
            "team_code": row.get("team_code"),
            "team_name": row.get("team_name"),
            "order_count": int(row.get("order_count") or 0),
            "sales_amount": float(row.get("sales_amount") or 0),
            "row_count": int(row.get("row_count") or 0),
        }
        if item["team_code"] in teams:
            teams[item["team_code"]] = item
        elif item["team_code"] == UNASSIGNED_TEAM_CODE:
            unassigned = item

    return {
        "teams": [teams[code] for code in TEAM_CODES],
        "unassigned": unassigned,
        "unassigned_count": unassigned["row_count"],
    }


def fetch_team_top_products(
    start_date: date,
    end_date: date,
    team_code: str | None = None,
    sale_type_filter: str | None = None,
    limit: int = 10,
) -> list[dict]:
    start_ts, end_ts = _date_bounds(start_date, end_date)
    sale_clause, sale_params = _sale_type_filter(sale_type_filter)
    team_clause, team_params, team_select, team_name_select = _team_filter(team_code)
    limit_value = int(limit)
    if limit_value < 1 or limit_value > 100:
        raise ValueError("limit must be between 1 and 100")

    rows = _fetch_all(
        f"""
        select
          coalesce(nullif(btrim(d.sku), ''), '') as sku,
          coalesce(nullif(btrim(d.product_name), ''), '') as product_name,
          {team_select} as team_code,
          {team_name_select} as team_name,
          sum({_EFFECTIVE_QUANTITY_SQL}) as total_quantity,
          count(distinct nullif(btrim(d.order_id), '')) as order_count
        from public.crm_data_imports d
        join public.crm_user_team_assignments a
          on a.user_email = lower(btrim(d.uploaded_by))
         and d.created_at >= a.effective_from
         and (a.effective_to is null or d.created_at < a.effective_to)
        where d.created_at >= %s
          and d.created_at < %s
          and {_MANUAL_ROW_SQL}
          and d.sale_type in ('NEW_ORDER', 'UPSELL', '⭐NEW_ORDER', '⭐UPSELL')
          {sale_clause}
          {team_clause}
        group by
          coalesce(nullif(btrim(d.sku), ''), ''),
          coalesce(nullif(btrim(d.product_name), ''), ''),
          {team_select},
          {team_name_select}
        order by total_quantity desc, product_name, sku
        limit %s
        """,
        [start_ts, end_ts, *sale_params, *team_params, limit_value],
    )
    return [
        {
            **row,
            "total_quantity": float(row.get("total_quantity") or 0),
            "order_count": int(row.get("order_count") or 0),
        }
        for row in rows
    ]


def fetch_team_sales_data_quality(start_date: date, end_date: date) -> dict:
    start_ts, end_ts = _date_bounds(start_date, end_date)
    rows = _fetch_all(
        f"""
        with base as (
          select
            d.*,
            a.id as assignment_id
          from public.crm_data_imports d
          left join public.crm_user_team_assignments a
            on a.user_email = lower(btrim(d.uploaded_by))
           and d.created_at >= a.effective_from
           and (a.effective_to is null or d.created_at < a.effective_to)
          where d.created_at >= %s
            and d.created_at < %s
            and {_MANUAL_ROW_SQL}
            and d.sale_type in ('NEW_ORDER', 'UPSELL', '⭐NEW_ORDER', '⭐UPSELL')
        ), creator_conflicts as (
          select order_id
          from base
          where nullif(btrim(order_id), '') is not null
          group by order_id
          having count(distinct lower(btrim(uploaded_by))) > 1
        )
        select
          count(*) as manual_row_count,
          count(*) filter (where assignment_id is null) as unassigned_row_count,
          count(*) filter (where amount is null) as null_amount_count,
          count(*) filter (where amount = 0) as zero_amount_count,
          count(*) filter (
            where quantity is null
              and ({_BASE_RAW_QUANTITY_SQL}) is null
              and ({_BASE_RAW_THAI_QUANTITY_SQL}) is null
          ) as quantity_default_one_count,
          count(*) filter (where nullif(btrim(coalesce(sku, '')), '') is null) as blank_sku_count,
          (select count(*) from creator_conflicts) as multiple_creator_order_count
        from base
        """,
        [start_ts, end_ts],
    )
    row = rows[0] if rows else {}
    return {key: int(value or 0) for key, value in row.items()}


def _normalized_email(value: str | None, *, required: bool) -> str | None:
    email = str(value or "").strip().lower()
    if required and not email:
        raise ValueError("user_email is required")
    return email or None


def _set_user_team_assignment(
    *,
    user_email: str,
    team_code: str | None,
    actor_email: str | None,
) -> dict:
    normalized_user_email = _normalized_email(user_email, required=True)
    normalized_actor_email = _normalized_email(actor_email, required=False)
    normalized_team_code = str(team_code or "").strip().upper() or None
    if normalized_team_code is not None and normalized_team_code not in TEAM_CODES:
        raise ValueError("team_code must be CRM_TEAM or UPSELL_TEAM")

    with _connection() as conn:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    select
                      id,
                      user_email,
                      team_code,
                      team_name,
                      effective_from,
                      effective_to
                    from public.crm_user_team_assignments
                    where user_email = %s
                      and effective_to is null
                    order by effective_from desc
                    limit 1
                    for update
                    """,
                    [normalized_user_email],
                )
                current = cur.fetchone()

                if current and current.get("team_code") == normalized_team_code:
                    conn.commit()
                    return {
                        **dict(current),
                        "changed": False,
                        "action": "unchanged",
                    }

                if current is None and normalized_team_code is None:
                    conn.commit()
                    return {
                        "user_email": normalized_user_email,
                        "team_code": None,
                        "team_name": None,
                        "changed": False,
                        "action": "unchanged",
                    }

                cur.execute("select clock_timestamp() as now_ts")
                now_ts = cur.fetchone()["now_ts"]
                if current and now_ts <= current["effective_from"]:
                    now_ts = current["effective_from"] + timedelta(microseconds=1)

                if current:
                    cur.execute(
                        """
                        update public.crm_user_team_assignments
                        set effective_to = %s,
                            updated_at = %s,
                            updated_by = %s
                        where id = %s
                        """,
                        [now_ts, now_ts, normalized_actor_email, current["id"]],
                    )

                if normalized_team_code is None:
                    result = {
                        "user_email": normalized_user_email,
                        "team_code": None,
                        "team_name": None,
                        "effective_from": None,
                        "effective_to": now_ts,
                        "changed": True,
                        "action": "cleared",
                    }
                else:
                    cur.execute(
                        """
                        insert into public.crm_user_team_assignments (
                          user_email,
                          team_code,
                          effective_from,
                          created_by,
                          updated_by
                        )
                        values (%s, %s, %s, %s, %s)
                        returning
                          id,
                          user_email,
                          team_code,
                          team_name,
                          effective_from,
                          effective_to
                        """,
                        [
                            normalized_user_email,
                            normalized_team_code,
                            now_ts,
                            normalized_actor_email,
                            normalized_actor_email,
                        ],
                    )
                    result = {
                        **dict(cur.fetchone()),
                        "changed": True,
                        "action": "created" if current is None else "changed",
                    }
            conn.commit()
            return result
        except Exception:
            conn.rollback()
            raise


def save_user_team_assignment(
    *,
    user_email: str,
    team_code: str,
    actor_email: str | None,
) -> dict:
    return _set_user_team_assignment(
        user_email=user_email,
        team_code=team_code,
        actor_email=actor_email,
    )


def clear_user_team_assignment(
    *,
    user_email: str,
    actor_email: str | None,
) -> dict:
    return _set_user_team_assignment(
        user_email=user_email,
        team_code=None,
        actor_email=actor_email,
    )
