import re

import streamlit as st


PRODUCT_PAGE_SIZE = 10
PRODUCT_STATUS_FILTERS = {"all", "active", "inactive", "archived"}
PRODUCT_SORT_MODES = {"sku_asc", "sku_desc", "created_asc", "created_desc"}
_PRODUCT_STATUS_CLAUSES = {
    "active": ("is_active = true", "archived_at is null"),
    "inactive": ("is_active = false", "archived_at is null"),
    "all": ("archived_at is null",),
    "archived": ("archived_at is not null",),
}
_SP_SKU_PATTERN = re.compile(r"^SP\s*0*(\d+)", re.IGNORECASE)
_SKU_NUMBER_SQL = """
case
  when upper(btrim(coalesce(sku, ''))) ~ '^SP[[:space:]]*[0-9]+'
    then substring(upper(btrim(sku)) from '^SP[[:space:]]*0*([0-9]+)')::bigint
  else null
end
""".strip()
_PRODUCT_DELETE_READINESS_SQL = """
select
  p.id::bigint as product_id,
  p.sku,
  p.product_name,
  (
    select count(*)::int
    from public.crm_data_imports d
    where nullif(btrim(p.sku), '') is not null
      and lower(btrim(coalesce(d.sku, ''))) = lower(btrim(p.sku))
  ) as imports_sku_count,
  (
    select count(*)::int
    from public.crm_data_imports d
    where nullif(btrim(p.product_name), '') is not null
      and lower(btrim(coalesce(d.product_name, ''))) = lower(btrim(p.product_name))
  ) as imports_name_count,
  (
    select count(*)::int
    from public.crm_data_imports d
    where nullif(btrim(p.sku), '') is not null
      and lower(btrim(coalesce(d.raw_data->>'sku', ''))) = lower(btrim(p.sku))
  ) as imports_raw_sku_count,
  (
    select count(*)::int
    from public.crm_order_items i
    where nullif(btrim(p.sku), '') is not null
      and lower(btrim(coalesce(i.sku, ''))) = lower(btrim(p.sku))
  ) as order_items_sku_count,
  (
    select count(*)::int
    from public.crm_order_items i
    where nullif(btrim(p.product_name), '') is not null
      and lower(btrim(coalesce(i.product_name, ''))) = lower(btrim(p.product_name))
  ) as order_items_name_count
from public.crm_product_options p
where p.id = any(%s::bigint[])
order by p.id
""".strip()
_ARCHIVE_PRODUCTS_SQL = """
update public.crm_product_options
set archived_at = now(),
    archived_by = %s,
    archive_reason = %s,
    is_active = false,
    updated_at = now(),
    updated_by = %s
where id = any(%s::bigint[])
  and archived_at is null
""".strip()
_RESTORE_ARCHIVED_PRODUCTS_SQL = """
update public.crm_product_options
set archived_at = null,
    archived_by = null,
    archive_reason = null,
    is_active = false,
    updated_at = now(),
    updated_by = %s
where id = any(%s::bigint[])
  and archived_at is not null
""".strip()


def sku_sort_key(value) -> tuple[int, int, str]:
    text = str(value or "").strip()
    match = _SP_SKU_PATTERN.match(text)
    if match:
        return 0, int(match.group(1)), text.casefold()
    return 1, 0, text.casefold()


def validate_product_ids(product_ids: list[int]) -> list[int]:
    if not isinstance(product_ids, list):
        raise ValueError("product_ids must be a list of positive integers")

    normalized_ids = []
    seen_ids = set()
    for product_id in product_ids:
        if isinstance(product_id, bool) or not isinstance(product_id, int) or product_id <= 0:
            raise ValueError("product_ids must contain only positive integers")
        if product_id not in seen_ids:
            normalized_ids.append(product_id)
            seen_ids.add(product_id)
    return normalized_ids


def build_product_delete_readiness(
    product_ids: list[int],
    rows: list[dict],
    check_error: str = "",
) -> dict[int, dict]:
    normalized_ids = validate_product_ids(product_ids)
    rows_by_id = {
        int(row["product_id"]): row
        for row in rows
        if row.get("product_id") is not None
    }
    results = {}
    for product_id in normalized_ids:
        row = rows_by_id.get(product_id)
        if check_error:
            results[product_id] = {
                "product_id": product_id,
                "sku": str((row or {}).get("sku") or "").strip(),
                "product_name": str((row or {}).get("product_name") or "").strip(),
                "status": "unsafe_unknown",
                "reason": f"usage_check_error:{check_error}",
                "usage_sources": [],
                "usage_count": 0,
            }
            continue
        if row is None:
            results[product_id] = {
                "product_id": product_id,
                "sku": "",
                "product_name": "",
                "status": "unsafe_unknown",
                "reason": "product_not_found",
                "usage_sources": [],
                "usage_count": 0,
            }
            continue

        sku = str(row.get("sku") or "").strip()
        product_name = str(row.get("product_name") or "").strip()
        if not sku and not product_name:
            results[product_id] = {
                "product_id": product_id,
                "sku": "",
                "product_name": "",
                "status": "unsafe_unknown",
                "reason": "blank_sku_and_product_name",
                "usage_sources": [],
                "usage_count": 0,
            }
            continue

        usage_fields = {
            "crm_data_imports.sku": int(row.get("imports_sku_count") or 0),
            "crm_data_imports.product_name": int(row.get("imports_name_count") or 0),
            "crm_data_imports.raw_data.sku": int(row.get("imports_raw_sku_count") or 0),
            "crm_order_items.sku": int(row.get("order_items_sku_count") or 0),
            "crm_order_items.product_name": int(row.get("order_items_name_count") or 0),
        }
        usage_sources = [source for source, count in usage_fields.items() if count > 0]
        usage_count = sum(usage_fields.values())
        status = "blocked_used" if usage_sources else "tentative_no_usage"
        reason = "usage_found" if usage_sources else "no_usage_found_in_text_checks"
        results[product_id] = {
            "product_id": product_id,
            "sku": sku,
            "product_name": product_name,
            "status": status,
            "reason": reason,
            "usage_sources": usage_sources,
            "usage_count": usage_count,
        }
    return results


def fetch_product_delete_readiness(product_ids: list[int]) -> dict[int, dict]:
    normalized_ids = validate_product_ids(product_ids)
    if not normalized_ids:
        return {}

    from neon_utils import neon_connection

    try:
        with neon_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(_PRODUCT_DELETE_READINESS_SQL, [normalized_ids])
                rows = cur.fetchall()
    except Exception as exc:
        return build_product_delete_readiness(
            normalized_ids,
            [],
            check_error=exc.__class__.__name__,
        )
    return build_product_delete_readiness(normalized_ids, rows)


@st.cache_data(ttl=900, show_spinner=False)
def fetch_product_options() -> list[dict]:
    from neon_utils import ensure_crm_data_imports_schema, neon_connection

    ensure_crm_data_imports_schema()
    with neon_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select
                  id::text as id,
                  sku,
                  product_group,
                  product_name,
                  is_active,
                  sort_order,
                  updated_at
                from public.crm_product_options
                order by sku asc nulls last, sort_order asc, product_group asc, product_name asc
                """
            )
            return cur.fetchall()


@st.cache_data(ttl=300, show_spinner=False)
def fetch_product_page(
    status_filter: str = "active",
    sort_mode: str = "sku_asc",
    page: int = 1,
    page_size: int = PRODUCT_PAGE_SIZE,
    search: str = "",
) -> tuple[list[dict], int]:
    from neon_utils import ensure_crm_data_imports_schema, neon_connection

    normalized_status = str(status_filter or "active").strip().lower()
    normalized_sort = str(sort_mode or "sku_asc").strip().lower()
    if normalized_status not in PRODUCT_STATUS_FILTERS:
        raise ValueError(f"unsupported product status filter: {status_filter}")
    if normalized_sort not in PRODUCT_SORT_MODES:
        raise ValueError(f"unsupported product sort mode: {sort_mode}")

    safe_page = max(int(page or 1), 1)
    safe_page_size = max(int(page_size or PRODUCT_PAGE_SIZE), 1)
    search_text = str(search or "").strip()
    clauses = list(_PRODUCT_STATUS_CLAUSES[normalized_status])
    params = []
    if search_text:
        clauses.append("(sku ilike %s or product_name ilike %s)")
        search_pattern = f"%{search_text}%"
        params.extend([search_pattern, search_pattern])

    where_sql = f"where {' and '.join(clauses)}" if clauses else ""
    sort_sql = {
        "sku_asc": "sku_number asc nulls last, lower(btrim(coalesce(sku, ''))) asc, id asc",
        "sku_desc": "sku_number desc nulls last, lower(btrim(coalesce(sku, ''))) desc, id desc",
        "created_asc": "created_at asc, lower(btrim(coalesce(sku, ''))) asc, id asc",
        "created_desc": "created_at desc, lower(btrim(coalesce(sku, ''))) asc, id desc",
    }[normalized_sort]

    ensure_crm_data_imports_schema()
    with neon_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"select count(*)::int as total from public.crm_product_options {where_sql}",
                params,
            )
            count_row = cur.fetchone() or {}
            total = int(count_row.get("total") or 0)
            cur.execute(
                f"""
                select
                  id::text as id,
                  sku,
                  product_group,
                  product_name,
                  is_active,
                  archived_at,
                  archived_by,
                  archive_reason,
                  sort_order,
                  created_at,
                  updated_at
                from (
                  select *, {_SKU_NUMBER_SQL} as sku_number
                  from public.crm_product_options
                  {where_sql}
                ) product_page
                order by {sort_sql}
                limit %s offset %s
                """,
                [*params, safe_page_size, (safe_page - 1) * safe_page_size],
            )
            return cur.fetchall(), total


def upsert_product_options(records: list[dict]) -> None:
    if not records:
        return
    from neon_utils import ensure_crm_data_imports_schema, neon_connection

    ensure_crm_data_imports_schema()
    columns = [
        "sku",
        "product_group",
        "product_name",
        "sort_order",
        "is_active",
        "created_by",
        "updated_by",
        "updated_at",
    ]
    with neon_connection() as conn:
        try:
            with conn.cursor() as cur:
                for record in records:
                    cur.execute(
                        """
                        select id
                        from public.crm_product_options
                        where coalesce(sku, '') = coalesce(%s, '')
                          and product_group = %s
                          and product_name = %s
                        limit 1
                        """,
                        [record.get("sku"), record.get("product_group"), record.get("product_name")],
                    )
                    existing = cur.fetchone()
                    if existing:
                        cur.execute(
                            """
                            update public.crm_product_options
                            set sort_order = %s,
                                is_active = %s,
                                updated_by = %s,
                                updated_at = %s
                            where id = %s
                            """,
                            [
                                record.get("sort_order"),
                                record.get("is_active"),
                                record.get("updated_by"),
                                record.get("updated_at"),
                                existing["id"],
                            ],
                        )
                    else:
                        cur.execute(
                            f"""
                            insert into public.crm_product_options ({', '.join(columns)})
                            values ({', '.join(['%s'] * len(columns))})
                            """,
                            tuple(record.get(column) for column in columns),
                        )
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def insert_product_options(records: list[dict]) -> None:
    if not records:
        return
    from neon_utils import ensure_crm_data_imports_schema, neon_connection

    ensure_crm_data_imports_schema()
    columns = [
        "sku",
        "product_group",
        "product_name",
        "sort_order",
        "is_active",
        "created_by",
        "updated_by",
        "updated_at",
    ]
    with neon_connection() as conn:
        try:
            with conn.cursor() as cur:
                cur.executemany(
                    f"""
                    insert into public.crm_product_options ({', '.join(columns)})
                    values ({', '.join(['%s'] * len(columns))})
                    """,
                    [tuple(record.get(column) for column in columns) for record in records],
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def update_product_option(option_id: str, payload: dict) -> None:
    from neon_utils import ensure_crm_data_imports_schema, neon_connection

    ensure_crm_data_imports_schema()
    fields = ["sku", "product_group", "product_name", "sort_order", "is_active", "updated_by", "updated_at"]
    with neon_connection() as conn:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    update public.crm_product_options
                    set {', '.join([f'{field} = %s' for field in fields])}
                    where id = %s
                    """,
                    [payload.get(field) for field in fields] + [option_id],
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def bulk_update_product_active(
    product_ids: list[int],
    is_active: bool,
    updated_by: str | None = None,
) -> int:
    normalized_ids = validate_product_ids(product_ids)
    if not normalized_ids:
        return 0

    from neon_utils import ensure_crm_data_imports_schema, neon_connection

    ensure_crm_data_imports_schema()
    with neon_connection() as conn:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    update public.crm_product_options
                    set is_active = %s,
                        updated_by = %s,
                        updated_at = now()
                    where id = any(%s::bigint[])
                    """,
                    [bool(is_active), updated_by, normalized_ids],
                )
                updated_count = int(cur.rowcount or 0)
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    fetch_product_page.clear()
    fetch_product_options.clear()
    return updated_count


def archive_products(
    product_ids: list[int],
    archived_by: str | None = None,
    reason: str | None = None,
) -> dict:
    normalized_ids = validate_product_ids(product_ids)
    if not normalized_ids:
        return {"requested": 0, "updated": 0, "skipped": 0}

    from neon_utils import neon_connection

    actor = str(archived_by or "").strip() or None
    archive_reason = str(reason or "").strip() or None
    with neon_connection() as conn:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    _ARCHIVE_PRODUCTS_SQL,
                    [actor, archive_reason, actor, normalized_ids],
                )
                updated_count = int(cur.rowcount or 0)
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    if updated_count:
        fetch_product_page.clear()
        fetch_product_options.clear()
    return {
        "requested": len(normalized_ids),
        "updated": updated_count,
        "skipped": len(normalized_ids) - updated_count,
    }


def restore_archived_products(
    product_ids: list[int],
    restored_by: str | None = None,
) -> dict:
    normalized_ids = validate_product_ids(product_ids)
    if not normalized_ids:
        return {"requested": 0, "updated": 0, "skipped": 0}

    from neon_utils import neon_connection

    actor = str(restored_by or "").strip() or None
    with neon_connection() as conn:
        try:
            with conn.cursor() as cur:
                cur.execute(_RESTORE_ARCHIVED_PRODUCTS_SQL, [actor, normalized_ids])
                updated_count = int(cur.rowcount or 0)
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    if updated_count:
        fetch_product_page.clear()
        fetch_product_options.clear()
    return {
        "requested": len(normalized_ids),
        "updated": updated_count,
        "skipped": len(normalized_ids) - updated_count,
    }


def delete_product_option(option_id: str) -> None:
    from neon_utils import ensure_crm_data_imports_schema, neon_connection

    ensure_crm_data_imports_schema()
    with neon_connection() as conn:
        try:
            with conn.cursor() as cur:
                cur.execute("delete from public.crm_product_options where id = %s", [option_id])
            conn.commit()
        except Exception:
            conn.rollback()
            raise
