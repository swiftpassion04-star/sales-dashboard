from datetime import date, datetime, timedelta, timezone

import streamlit as st


def fetch_dashboard_kpis(user: dict | None = None) -> dict:
    from neon_utils import clean, ensure_crm_data_imports_schema, neon_connection

    ensure_crm_data_imports_schema()
    where = ["d.import_status = 'valid'"]
    params: list = []
    role = clean((user or {}).get("role"))
    staff_code = clean((user or {}).get("staff_code"))
    if role not in {"ADMIN", "EDITOR"}:
        if staff_code:
            where.append("d.staff_code = %s")
            params.append(staff_code)
        else:
            where.append("1 = 0")
    where_sql = "where " + " and ".join(where)
    with neon_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                with latest_customers as (
                  select distinct on (
                    case
                      when nullif(phone1, '') is not null and nullif(phone2, '') is not null then least(phone1, phone2)
                      else coalesce(nullif(phone1, ''), nullif(phone2, ''), id::text)
                    end
                  )
                    id,
                    phone1,
                    phone2,
                    updated_at
                  from public.crm_data_imports d
                  {where_sql}
                  order by
                    case
                      when nullif(phone1, '') is not null and nullif(phone2, '') is not null then least(phone1, phone2)
                      else coalesce(nullif(phone1, ''), nullif(phone2, ''), id::text)
                    end,
                    order_date desc nulls last,
                    uploaded_at desc,
                    id desc
                )
                select
                  (select count(*) from latest_customers) as total_customers,
                  count(*) filter (where coalesce(l.next_followup_date, l.follow_up_date) = current_date and coalesce(l.followup_status, l.follow_up_status, 'none') <> 'done') as due_today,
                  count(*) filter (where coalesce(l.next_followup_date, l.follow_up_date) < current_date and coalesce(l.followup_status, l.follow_up_status, 'none') <> 'done') as overdue,
                  count(*) filter (where coalesce(l.lead_status, 'new') = 'interested') as interested,
                  count(*) filter (where coalesce(l.lead_status, 'new') = 'won') as won,
                  max(greatest(coalesce(l.updated_at, 'epoch'::timestamptz), coalesce(d.updated_at, 'epoch'::timestamptz))) as latest_update
                from latest_customers d
                left join lateral (
                  select
                    lead_status,
                    followup_status,
                    follow_up_status,
                    next_followup_date,
                    follow_up_date,
                    updated_at
                  from public.crm_lead_followups l
                  where l.crm_data_import_id = d.id
                     or (nullif(l.phone1, '') is not null and (l.phone1 = d.phone1 or l.phone1 = d.phone2))
                     or (nullif(l.phone2, '') is not null and (l.phone2 = d.phone1 or l.phone2 = d.phone2))
                  order by updated_at desc nulls last, id desc
                  limit 1
                ) l on true
                """,
                params,
            )
            row = cur.fetchone() or {}
            return {
                "total_customers": int(row.get("total_customers") or 0),
                "due_today": int(row.get("due_today") or 0),
                "overdue": int(row.get("overdue") or 0),
                "interested": int(row.get("interested") or 0),
                "won": int(row.get("won") or 0),
                "latest_update": clean(row.get("latest_update")),
            }


def crm_sales_report_ready() -> bool:
    from neon_utils import neon_column_exists

    return all(
        neon_column_exists("crm_data_imports", column)
        for column in ("sale_type", "amount", "address")
    )


def _can_view_all_sales(user: dict | None) -> bool:
    from neon_utils import clean

    return clean((user or {}).get("role")) in {"ADMIN", "EDITOR"}


@st.cache_data(ttl=300)
def fetch_sales_report_owner_options(user: dict | None = None) -> list[str]:
    from neon_utils import clean, ensure_crm_data_imports_schema, neon_connection

    ensure_crm_data_imports_schema()
    if not crm_sales_report_ready() or not _can_view_all_sales(user):
        return []
    with neon_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select distinct owner
                from public.crm_data_imports
                where import_status = 'valid'
                  and owner is not null
                  and owner <> ''
                  and amount is not null
                  and coalesce(nullif(sale_type, ''), 'NEW_ORDER') in ('NEW_ORDER', 'UPSELL')
                order by owner
                """
            )
            return [row["owner"] for row in cur.fetchall() if clean(row.get("owner"))]


def _sales_report_where(user: dict | None, owner_filter: str) -> tuple[list[str], list]:
    from neon_utils import clean

    clauses = [
        "d.import_status = 'valid'",
        "d.created_at >= %s",
        "d.created_at < %s",
        "d.amount is not null",
        "coalesce(nullif(d.sale_type, ''), 'NEW_ORDER') in ('NEW_ORDER', 'UPSELL')",
    ]
    params: list = []
    if _can_view_all_sales(user):
        owner = clean(owner_filter)
        if owner and owner != "ทั้งหมด":
            clauses.append("d.owner = %s")
            params.append(owner)
    else:
        staff_code = clean((user or {}).get("staff_code"))
        if staff_code:
            clauses.append("d.staff_code = %s")
            params.append(staff_code)
        else:
            clauses.append("1 = 0")
    return clauses, params


def summarize_sales_report_rows(rows: list[dict]) -> dict:
    from neon_utils import clean

    summary = {
        "NEW_ORDER": {"sales_amount": 0.0, "order_count": 0, "aov": 0.0},
        "UPSELL": {"sales_amount": 0.0, "order_count": 0, "aov": 0.0},
    }
    order_ids: dict[str, set[str]] = {"NEW_ORDER": set(), "UPSELL": set()}
    for row in rows or []:
        sale_type = clean(row.get("sale_type")) or "NEW_ORDER"
        if sale_type not in summary:
            summary[sale_type] = {"sales_amount": 0.0, "order_count": 0, "aov": 0.0}
            order_ids[sale_type] = set()
        summary[sale_type]["sales_amount"] += float(row.get("amount") or 0)
        order_id = clean(row.get("order_id"))
        if order_id:
            order_ids[sale_type].add(order_id)

    for sale_type, values in summary.items():
        count = len(order_ids.get(sale_type, set()))
        values["order_count"] = count
        values["aov"] = values["sales_amount"] / count if count else 0.0

    total_amount = sum(value["sales_amount"] for value in summary.values())
    total_count = sum(value["order_count"] for value in summary.values())
    summary["TOTAL"] = {
        "sales_amount": total_amount,
        "order_count": total_count,
        "aov": total_amount / total_count if total_count else 0.0,
    }
    return summary


def fetch_sales_report(
    user: dict | None,
    start_date: date,
    end_date: date,
    owner_filter: str = "ทั้งหมด",
) -> dict:
    from neon_utils import BANGKOK_TZ, ensure_crm_data_imports_schema, neon_connection

    ensure_crm_data_imports_schema()
    if not crm_sales_report_ready():
        return {"ready": False, "summary": {}, "daily": [], "rows": []}

    rows = fetch_sales_report_rows(user, start_date, end_date, owner_filter)
    summary = summarize_sales_report_rows(rows)

    start_ts = datetime.combine(start_date, datetime.min.time(), tzinfo=BANGKOK_TZ).astimezone(timezone.utc)
    end_ts = datetime.combine(end_date + timedelta(days=1), datetime.min.time(), tzinfo=BANGKOK_TZ).astimezone(timezone.utc)
    clauses, extra_params = _sales_report_where(user, owner_filter)
    params = [start_ts, end_ts, *extra_params]
    where_sql = "where " + " and ".join(clauses)

    with neon_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                select
                  (d.created_at at time zone 'Asia/Bangkok')::date as sales_date,
                  coalesce(nullif(d.sale_type, ''), 'NEW_ORDER') as sale_type,
                  coalesce(sum(d.amount), 0) as sales_amount
                from public.crm_data_imports d
                {where_sql}
                group by (d.created_at at time zone 'Asia/Bangkok')::date, coalesce(nullif(d.sale_type, ''), 'NEW_ORDER')
                order by (d.created_at at time zone 'Asia/Bangkok')::date asc
                """,
                params,
            )
            daily_rows = cur.fetchall()

    return {"ready": True, "summary": summary, "daily": daily_rows, "rows": rows}


def fetch_sales_report_rows(
    user: dict | None,
    start_date: date,
    end_date: date,
    owner_filter: str = "ทั้งหมด",
    limit: int = 1000,
) -> list[dict]:
    from neon_utils import (
        BANGKOK_TZ,
        ensure_crm_data_imports_schema,
        neon_column_exists,
        neon_connection,
    )

    ensure_crm_data_imports_schema()
    if not crm_sales_report_ready():
        return []

    start_ts = datetime.combine(start_date, datetime.min.time(), tzinfo=BANGKOK_TZ).astimezone(timezone.utc)
    end_ts = datetime.combine(end_date + timedelta(days=1), datetime.min.time(), tzinfo=BANGKOK_TZ).astimezone(timezone.utc)
    clauses, extra_params = _sales_report_where(user, owner_filter)
    params = [start_ts, end_ts, *extra_params, int(limit)]
    where_sql = "where " + " and ".join(clauses)
    raw_qty_expr = (
        "case when nullif(d.raw_data->>'qty', '') ~ '^[0-9]+(\\.[0-9]+)?$' "
        "then (d.raw_data->>'qty')::numeric end"
    )
    raw_thai_qty_expr = (
        "case when nullif(d.raw_data->>'จำนวน', '') ~ '^[0-9]+(\\.[0-9]+)?$' "
        "then (d.raw_data->>'จำนวน')::numeric end"
    )
    if neon_column_exists("crm_data_imports", "quantity"):
        qty_expr = f"coalesce(d.quantity, {raw_qty_expr}, {raw_thai_qty_expr}, 1)"
    else:
        qty_expr = f"coalesce({raw_qty_expr}, {raw_thai_qty_expr}, 1)"
    creator_sources = []
    if neon_column_exists("crm_data_imports", "created_by"):
        creator_sources.append("nullif(d.created_by, '')")
    if neon_column_exists("crm_data_imports", "uploaded_by"):
        creator_sources.append("nullif(d.uploaded_by, '')")
    creator_expr = f"coalesce({', '.join(creator_sources)}, '')" if creator_sources else "''"

    with neon_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                with base as (
                  select
                    min(d.created_at) as created_at,
                    coalesce(nullif(d.sale_type, ''), 'NEW_ORDER') as sale_type,
                    coalesce(nullif(d.order_id, ''), d.id::text) as order_id,
                    coalesce(nullif(d.sku, ''), '-') as sku,
                    coalesce(nullif(d.product_name, ''), '-') as product_name,
                    {qty_expr} as quantity,
                    coalesce(d.amount, 0) as amount,
                    coalesce(nullif(creator.staff_name, ''), {creator_expr}) as created_staff,
                    min(d.id) as first_id,
                    array_agg(d.id::text order by d.id) as record_ids,
                    bool_and(
                      coalesce(nullif(d.source_type, ''), '') = 'manual'
                      or coalesce(nullif(d.source_file_name, ''), '') = 'manual_order'
                      or coalesce(nullif(d.raw_data->>'source', ''), '') = 'manual_order'
                    ) as can_delete
                  from public.crm_data_imports d
                  left join public.crm_user_roles creator
                    on lower(creator.email) = lower({creator_expr})
                  {where_sql}
                  group by
                    coalesce(nullif(d.sale_type, ''), 'NEW_ORDER'),
                    coalesce(nullif(d.order_id, ''), d.id::text),
                    coalesce(nullif(d.sku, ''), '-'),
                    coalesce(nullif(d.product_name, ''), '-'),
                    {qty_expr},
                    coalesce(d.amount, 0),
                    coalesce(nullif(creator.staff_name, ''), {creator_expr})
                )
                select
                  to_char(created_at at time zone 'Asia/Bangkok', 'HH24:MI') as sale_time,
                  sale_type,
                  order_id,
                  sku,
                  product_name,
                  quantity,
                  amount,
                  created_staff,
                  record_ids,
                  can_delete
                from base
                order by created_at asc, first_id asc
                limit %s
                """,
                params,
            )
            return cur.fetchall()


def delete_sales_report_records(record_ids: list[str], user: dict | None) -> int:
    from neon_utils import (
        clean,
        ensure_crm_data_imports_schema,
        neon_column_exists,
        neon_connection,
        neon_table_exists,
    )
    from permissions import can_delete_order

    if not can_delete_order(user):
        raise PermissionError("User cannot delete sales report records")

    clean_ids = [clean(record_id) for record_id in (record_ids or []) if clean(record_id)]
    if not clean_ids:
        return 0

    ensure_crm_data_imports_schema()
    has_order_items = neon_table_exists("crm_order_items")
    has_order_item_import_id = has_order_items and neon_column_exists("crm_order_items", "crm_data_import_id")
    has_orders = neon_table_exists("crm_orders")
    with neon_connection() as conn:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    select distinct order_id
                    from public.crm_data_imports
                    where id::text = any(%s)
                      and (
                        coalesce(nullif(source_type, ''), '') = 'manual'
                        or coalesce(nullif(source_file_name, ''), '') = 'manual_order'
                        or coalesce(nullif(raw_data->>'source', ''), '') = 'manual_order'
                      )
                    """,
                    [clean_ids],
                )
                order_ids = [clean(row.get("order_id")) for row in cur.fetchall() if clean(row.get("order_id"))]

                if has_order_item_import_id:
                    cur.execute(
                        """
                        delete from public.crm_order_items
                        where crm_data_import_id::text = any(%s)
                        """,
                        [clean_ids],
                    )

                cur.execute(
                    """
                    delete from public.crm_data_imports
                    where id::text = any(%s)
                      and (
                        coalesce(nullif(source_type, ''), '') = 'manual'
                        or coalesce(nullif(source_file_name, ''), '') = 'manual_order'
                        or coalesce(nullif(raw_data->>'source', ''), '') = 'manual_order'
                      )
                    """,
                    [clean_ids],
                )
                deleted = int(cur.rowcount or 0)

                if has_orders and order_ids:
                    cur.execute(
                        """
                        delete from public.crm_orders o
                        where o.order_id = any(%s)
                          and not exists (
                            select 1
                            from public.crm_order_items i
                            where i.crm_order_id = o.id
                          )
                          and not exists (
                            select 1
                            from public.crm_data_imports d
                            where d.order_id = o.order_id
                              and d.import_status = 'valid'
                          )
                        """,
                        [order_ids],
                    )
            conn.commit()
            return deleted
        except Exception:
            conn.rollback()
            raise
