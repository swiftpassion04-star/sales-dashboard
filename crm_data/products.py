import re

import streamlit as st


PRODUCT_PAGE_SIZE = 10
PRODUCT_STATUS_FILTERS = {"all", "active", "inactive"}
PRODUCT_SORT_MODES = {"sku_asc", "sku_desc", "created_asc", "created_desc"}
_SP_SKU_PATTERN = re.compile(r"^SP\s*0*(\d+)", re.IGNORECASE)
_SKU_NUMBER_SQL = """
case
  when upper(btrim(coalesce(sku, ''))) ~ '^SP[[:space:]]*[0-9]+'
    then substring(upper(btrim(sku)) from '^SP[[:space:]]*0*([0-9]+)')::bigint
  else null
end
""".strip()


def sku_sort_key(value) -> tuple[int, int, str]:
    text = str(value or "").strip()
    match = _SP_SKU_PATTERN.match(text)
    if match:
        return 0, int(match.group(1)), text.casefold()
    return 1, 0, text.casefold()


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
    clauses = []
    params = []
    if normalized_status == "active":
        clauses.append("is_active = true")
    elif normalized_status == "inactive":
        clauses.append("is_active = false")
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
