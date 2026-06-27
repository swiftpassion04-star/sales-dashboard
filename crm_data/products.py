import streamlit as st


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
