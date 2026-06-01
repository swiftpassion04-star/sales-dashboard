import hashlib
import json
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from uuid import uuid4

import pandas as pd
import streamlit as st

try:
    import psycopg
    from psycopg.rows import dict_row
    from psycopg.types.json import Jsonb
except ImportError:  # pragma: no cover - shown in the UI when dependency is missing.
    psycopg = None
    dict_row = None
    Jsonb = None


CRM_DATA_IMPORTS_DDL = """
create table if not exists public.crm_data_imports (
  id bigserial primary key,
  import_batch_id uuid not null,
  source_file_name text,
  sheet_name text,
  row_number integer,
  uploaded_by text,
  uploaded_at timestamptz not null default now(),
  raw_data jsonb not null default '{}'::jsonb,
  order_id text,
  url text,
  customer_name text,
  phone1 text,
  phone2 text,
  product_name text,
  sku text,
  order_date date,
  province text,
  city text,
  postal_code text,
  tracking_no text,
  carrier text,
  order_status text,
  total_amount numeric,
  owner text,
  import_status text not null default 'valid',
  validation_error text,
  dedupe_key text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table public.crm_data_imports
  add column if not exists order_id text,
  add column if not exists url text;

create index if not exists idx_crm_data_imports_phone1
  on public.crm_data_imports (phone1);
create index if not exists idx_crm_data_imports_phone2
  on public.crm_data_imports (phone2);
create index if not exists idx_crm_data_imports_sku
  on public.crm_data_imports (sku);
create index if not exists idx_crm_data_imports_order_id
  on public.crm_data_imports (order_id);
create index if not exists idx_crm_data_imports_order_date
  on public.crm_data_imports (order_date);
create index if not exists idx_crm_data_imports_uploaded_at
  on public.crm_data_imports (uploaded_at desc);
create index if not exists idx_crm_data_imports_import_batch_id
  on public.crm_data_imports (import_batch_id);
create index if not exists idx_crm_data_imports_owner
  on public.crm_data_imports (owner);
create index if not exists idx_crm_data_imports_tracking_no
  on public.crm_data_imports (tracking_no);
create index if not exists idx_crm_data_imports_customer_phone_latest
  on public.crm_data_imports (
    (
      case
        when nullif(phone1, '') is not null and nullif(phone2, '') is not null then least(phone1, phone2)
        else coalesce(nullif(phone1, ''), nullif(phone2, ''), id::text)
      end
    ),
    order_date desc,
    uploaded_at desc
  )
  where import_status = 'valid';

create table if not exists public.crm_owner_assignments (
  phone_key text primary key,
  owner text not null,
  updated_by text,
  updated_at timestamptz not null default now()
);

create index if not exists idx_crm_owner_assignments_owner
  on public.crm_owner_assignments (owner);

create table if not exists public.crm_lead_followups (
  customer_key text primary key,
  customer_id text,
  customer_name text,
  phone_key text,
  phone1 text,
  phone2 text,
  product_group text,
  lead_status text,
  follow_up_status text,
  follow_up_date date,
  follow_up_note text,
  priority text,
  updated_by text,
  updated_at timestamptz not null default now(),
  created_at timestamptz not null default now()
);

create index if not exists idx_crm_lead_followups_phone_key
  on public.crm_lead_followups (phone_key);
create index if not exists idx_crm_lead_followups_updated_at
  on public.crm_lead_followups (updated_at desc);

create table if not exists public.crm_product_options (
  id bigserial primary key,
  sku text,
  product_group text not null,
  product_name text not null,
  sort_order integer not null default 0,
  is_active boolean not null default true,
  created_by text,
  updated_by text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (product_group, product_name)
);

create index if not exists idx_crm_product_options_active_sort
  on public.crm_product_options (is_active, sku, sort_order, product_group, product_name);
"""


CRM_COLUMNS = [
    "id",
    "import_batch_id",
    "source_file_name",
    "sheet_name",
    "row_number",
    "uploaded_by",
    "uploaded_at",
    "raw_data",
    "order_id",
    "url",
    "customer_name",
    "phone1",
    "phone2",
    "product_name",
    "sku",
    "order_date",
    "province",
    "city",
    "postal_code",
    "tracking_no",
    "carrier",
    "order_status",
    "total_amount",
    "owner",
    "import_status",
    "validation_error",
    "created_at",
    "updated_at",
]


def get_neon_database_url() -> str:
    value = ""
    try:
        value = str(st.secrets.get("NEON_DATABASE_URL", "")).strip()
    except Exception:
        value = ""
    return value or os.getenv("NEON_DATABASE_URL", "").strip()


def require_neon_config() -> None:
    if psycopg is None:
        st.error("ยังไม่ได้ติดตั้ง dependency `psycopg[binary]` สำหรับเชื่อม Neon PostgreSQL")
        st.stop()
    if not get_neon_database_url():
        st.error("ยังไม่ได้ตั้งค่า `NEON_DATABASE_URL` ใน Streamlit Secrets")
        st.stop()


@contextmanager
def neon_connection():
    require_neon_config()
    conn = psycopg.connect(get_neon_database_url(), row_factory=dict_row)
    try:
        yield conn
    finally:
        conn.close()


@st.cache_resource(show_spinner=False)
def ensure_crm_data_imports_schema() -> bool:
    with neon_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(CRM_DATA_IMPORTS_DDL)
        conn.commit()
    return True


def normalize_phone(value) -> str:
    return "".join(ch for ch in clean(value) if ch.isdigit())


def clean(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and pd.isna(value):
        return ""
    text = str(value).strip()
    return "" if text.upper() in {"NULL", "NONE", "NAN", "NAT"} else text


def parse_date(value) -> str | None:
    text = clean(value)
    if not text:
        return None
    parsed = pd.to_datetime(text, errors="coerce", dayfirst=True)
    if pd.isna(parsed):
        return None
    return parsed.date().isoformat()


def to_number(value):
    text = clean(value).replace(",", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def make_dedupe_key(order_id: str, phone1: str, phone2: str, tracking_no: str) -> str:
    text = "|".join([clean(order_id), normalize_phone(phone1), normalize_phone(phone2), clean(tracking_no)])
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def new_batch_id() -> str:
    return str(uuid4())


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_record_from_mapping(
    row: dict,
    mapping: dict[str, str],
    batch_id: str,
    filename: str,
    sheet_name: str,
    row_number: int,
    uploaded_by: str,
) -> dict:
    def pick(field: str) -> str:
        column = mapping.get(field, "")
        return clean(row.get(column)) if column else ""

    customer_name = pick("customer_name")
    phone1 = pick("phone1")
    phone2 = pick("phone2")
    tracking_no = pick("tracking_no")
    order_id = pick("order_id")
    errors = []
    if not customer_name:
        errors.append("customer_name ว่าง")
    if not normalize_phone(phone1) and not normalize_phone(phone2):
        errors.append("phone1/phone2 ว่าง")

    raw_data = {str(key): clean(value) for key, value in row.items()}
    return {
        "import_batch_id": batch_id,
        "source_file_name": filename,
        "sheet_name": sheet_name,
        "row_number": row_number,
        "uploaded_by": uploaded_by,
        "uploaded_at": now_iso(),
        "raw_data": raw_data,
        "order_id": order_id,
        "url": pick("url"),
        "customer_name": customer_name,
        "phone1": normalize_phone(phone1),
        "phone2": normalize_phone(phone2),
        "product_name": pick("product_name"),
        "sku": pick("sku"),
        "order_date": parse_date(pick("order_date")),
        "province": pick("province"),
        "city": pick("city"),
        "postal_code": pick("postal_code"),
        "tracking_no": tracking_no,
        "carrier": pick("carrier"),
        "order_status": pick("order_status"),
        "total_amount": to_number(pick("total_amount")),
        "owner": pick("owner"),
        "import_status": "invalid" if errors else "valid",
        "validation_error": "; ".join(errors),
        "dedupe_key": make_dedupe_key(order_id, phone1, phone2, tracking_no),
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }


def insert_import_records(records: list[dict], batch_size: int = 500) -> None:
    if not records:
        return
    ensure_crm_data_imports_schema()
    columns = [
        "import_batch_id",
        "source_file_name",
        "sheet_name",
        "row_number",
        "uploaded_by",
        "uploaded_at",
        "raw_data",
        "order_id",
        "url",
        "customer_name",
        "phone1",
        "phone2",
        "product_name",
        "sku",
        "order_date",
        "province",
        "city",
        "postal_code",
        "tracking_no",
        "carrier",
        "order_status",
        "total_amount",
        "owner",
        "import_status",
        "validation_error",
        "dedupe_key",
        "created_at",
        "updated_at",
    ]
    placeholders = ", ".join(["%s"] * len(columns))
    sql = f"insert into public.crm_data_imports ({', '.join(columns)}) values ({placeholders})"

    with neon_connection() as conn:
        try:
            with conn.cursor() as cur:
                insert_records = prepare_import_records(cur, records)
                for start in range(0, len(insert_records), batch_size):
                    chunk = insert_records[start : start + batch_size]
                    values = []
                    for record in chunk:
                        row_values = []
                        for column in columns:
                            value = record.get(column)
                            row_values.append(Jsonb(value) if column == "raw_data" else value)
                        values.append(tuple(row_values))
                    cur.executemany(sql, values)
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def analyze_import_records(records: list[dict]) -> dict:
    if not records:
        return {
            "insert_records": [],
            "skipped_records": [],
            "phone_duplicate_records": [],
            "summary": {"insert": 0, "skip": 0, "phone_duplicate": 0},
        }
    ensure_crm_data_imports_schema()
    with neon_connection() as conn:
        with conn.cursor() as cur:
            return build_import_plan(cur, records, mutate_records=False)


def prepare_import_records(cur, records: list[dict]) -> list[dict]:
    plan = build_import_plan(cur, records, mutate_records=True)
    return plan["insert_records"]


def build_import_plan(cur, records: list[dict], mutate_records: bool) -> dict:
    apply_owner_assignments(cur, records)
    existing_order_ids = fetch_existing_order_ids(cur, records)
    latest_by_phone = fetch_latest_customer_rows_by_phone(cur, records)
    seen_order_ids: set[str] = set()
    insert_records: list[dict] = []
    skipped_records: list[dict] = []
    phone_duplicate_records: list[dict] = []
    latest_updates: dict[str, dict] = {}

    for record in records:
        row_number = record.get("row_number")
        phone1 = normalize_phone(record.get("phone1"))
        phone2 = normalize_phone(record.get("phone2"))
        phones = [phone for phone in (phone1, phone2) if phone]
        order_id = clean(record.get("order_id"))

        if record.get("import_status") == "invalid" or not phones:
            skipped_records.append(skip_preview(record, "ไม่มีเบอร์โทร"))
            continue
        if order_id and order_id in existing_order_ids:
            skipped_records.append(skip_preview(record, "ซ้ำเลขออเดอร์ในฐานข้อมูล"))
            continue
        if order_id and order_id in seen_order_ids:
            skipped_records.append(skip_preview(record, "ซ้ำเลขออเดอร์ในไฟล์"))
            continue

        latest_matches = unique_latest_matches(latest_by_phone, phones)
        if latest_matches:
            phone_duplicate_records.append(
                {
                    "row_number": row_number,
                    "customer_name": clean(record.get("customer_name")),
                    "phone1": phone1,
                    "phone2": phone2,
                    "order_id": order_id,
                    "matched_rows": len(latest_matches),
                    "latest_customer_id": latest_matches[0]["id"],
                }
            )
            update = latest_updates.setdefault(
                latest_matches[0]["id"],
                {"id": latest_matches[0]["id"], "url": "", "owner": ""},
            )
            if clean(record.get("url")):
                update["url"] = clean(record.get("url"))
            if clean(record.get("owner")):
                update["owner"] = clean(record.get("owner"))

        insert_records.append(record)
        if order_id:
            seen_order_ids.add(order_id)

    if mutate_records:
        apply_latest_customer_updates(cur, latest_updates.values())

    return {
        "insert_records": insert_records,
        "skipped_records": skipped_records,
        "phone_duplicate_records": phone_duplicate_records,
        "summary": {
            "insert": len(insert_records),
            "skip": len(skipped_records),
            "phone_duplicate": len(phone_duplicate_records),
        },
    }


def fetch_existing_order_ids(cur, records: list[dict]) -> set[str]:
    order_ids = sorted({clean(record.get("order_id")) for record in records if clean(record.get("order_id"))})
    if not order_ids:
        return set()
    cur.execute(
        """
        select order_id
        from public.crm_data_imports
        where order_id = any(%s)
          and import_status = 'valid'
        """,
        [order_ids],
    )
    return {clean(row["order_id"]) for row in cur.fetchall()}


def fetch_latest_customer_rows_by_phone(cur, records: list[dict]) -> dict[str, list[dict]]:
    phones = sorted(
        {
            normalize_phone(record.get(name))
            for record in records
            for name in ("phone1", "phone2")
            if normalize_phone(record.get(name))
        }
    )
    if not phones:
        return {}
    cur.execute(
        """
        with matched as (
          select
            id,
            phone1,
            phone2,
            row_number() over (
              partition by matched_phone
              order by order_date desc nulls last, uploaded_at desc, id desc
            ) as rn,
            matched_phone
          from (
            select id, phone1, phone2, order_date, uploaded_at, phone1 as matched_phone
            from public.crm_data_imports
            where import_status = 'valid' and phone1 = any(%s)
            union all
            select id, phone1, phone2, order_date, uploaded_at, phone2 as matched_phone
            from public.crm_data_imports
            where import_status = 'valid' and phone2 = any(%s)
          ) src
        )
        select id::text, phone1, phone2, matched_phone
        from matched
        where rn = 1
        """,
        [phones, phones],
    )
    by_phone: dict[str, list[dict]] = {}
    for row in cur.fetchall():
        by_phone.setdefault(clean(row["matched_phone"]), []).append(row)
    return by_phone


def unique_latest_matches(latest_by_phone: dict[str, list[dict]], phones: list[str]) -> list[dict]:
    matches: list[dict] = []
    seen: set[str] = set()
    for phone in phones:
        for row in latest_by_phone.get(phone, []):
            row_id = clean(row.get("id"))
            if row_id and row_id not in seen:
                seen.add(row_id)
                matches.append(row)
    return matches


def apply_latest_customer_updates(cur, updates) -> None:
    for update in updates:
        row_id = clean(update.get("id"))
        url = clean(update.get("url"))
        owner = clean(update.get("owner"))
        if not row_id or (not url and not owner):
            continue
        cur.execute(
            """
            update public.crm_data_imports
            set url = coalesce(nullif(%s, ''), url),
                owner = coalesce(nullif(%s, ''), owner),
                updated_at = now()
            where id = %s
            """,
            [url, owner, row_id],
        )


def skip_preview(record: dict, reason: str) -> dict:
    return {
        "row_number": record.get("row_number"),
        "reason": reason,
        "customer_name": clean(record.get("customer_name")),
        "order_id": clean(record.get("order_id")),
        "phone1": clean(record.get("phone1")),
        "phone2": clean(record.get("phone2")),
        "tracking_no": clean(record.get("tracking_no")),
    }


def apply_owner_assignments(cur, records: list[dict]) -> None:
    phones = sorted(
        {
            normalize_phone(record.get(name))
            for record in records
            for name in ("phone1", "phone2")
            if normalize_phone(record.get(name))
        }
    )
    if not phones:
        return
    cur.execute(
        """
        select phone_key, owner
        from public.crm_owner_assignments
        where phone_key = any(%s)
        """,
        [phones],
    )
    owner_by_phone = {row["phone_key"]: clean(row["owner"]) for row in cur.fetchall()}
    for record in records:
        if clean(record.get("owner")):
            continue
        for name in ("phone1", "phone2"):
            owner = owner_by_phone.get(normalize_phone(record.get(name)))
            if owner:
                record["owner"] = owner
                break


def fetch_customer_page(filters: dict[str, str], page_size: int, page: int) -> tuple[list[dict], int]:
    ensure_crm_data_imports_schema()
    where, params = build_customer_where(filters)
    limit = int(page_size)
    offset = (max(int(page), 1) - 1) * limit
    select_cols = customer_select_columns()
    source_sql = f"""
      from (
        select
          *,
          case
            when nullif(phone1, '') is not null and nullif(phone2, '') is not null then least(phone1, phone2)
            else coalesce(nullif(phone1, ''), nullif(phone2, ''), id::text)
          end as phone_key
        from public.crm_data_imports
        {where}
      ) keyed
    """
    with neon_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(f"select count(distinct phone_key) as total {source_sql}", params)
            total = int(cur.fetchone()["total"] or 0)
            cur.execute(
                f"""
                with ranked as (
                  select
                    keyed.*,
                    row_number() over (
                      partition by phone_key
                      order by order_date desc nulls last, uploaded_at desc, id desc
                    ) as rn
                  {source_sql}
                )
                select {select_cols}
                from ranked
                where rn = 1
                order by order_date desc nulls last, uploaded_at desc, id desc
                limit %s offset %s
                """,
                params + [limit, offset],
            )
            return cur.fetchall(), total


def build_customer_where(filters: dict[str, str]) -> tuple[str, list]:
    clauses = ["import_status = 'valid'"]
    params: list = []
    staff = clean(filters.get("staff"))
    keyword = clean(filters.get("keyword"))
    if staff and staff != "ทั้งหมด":
        clauses.append("owner = %s")
        params.append(staff)
    if keyword:
        like = f"%{keyword}%"
        clauses.append(
            "("
            "customer_name ilike %s or phone1 ilike %s or phone2 ilike %s or "
            "postal_code ilike %s or tracking_no ilike %s or sku ilike %s or "
            "order_id ilike %s or raw_data->>'เลขคำสั่งซื้อ' ilike %s"
            ")"
        )
        params.extend([like, like, like, like, like, like, like, like])
    return "where " + " and ".join(clauses), params


def customer_select_columns() -> str:
    return """
      id::text as id,
      id::text as customer_id,
      customer_name as customer,
      owner as sales_staff,
      order_id,
      url as product_url,
      url as channel_url,
      product_name,
      phone1,
      phone2,
      sku,
      province,
      city,
      postal_code as postcode,
      tracking_no,
      carrier,
      order_status,
      total_amount,
      order_date,
      order_date::text as order_date_text,
      raw_data,
      updated_at
    """


def fetch_customer_by_id(customer_id: str) -> list[dict]:
    ensure_crm_data_imports_schema()
    with neon_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select
                  """ + customer_select_columns() + """
                from public.crm_data_imports
                where id = %s
                limit 1
                """,
                [customer_id],
            )
            return cur.fetchall()


def assign_owner_to_phones(phones: tuple[str, ...], owner: str, updated_by: str) -> int:
    clean_phones = sorted({normalize_phone(phone) for phone in phones if normalize_phone(phone)})
    owner = clean(owner)
    if not clean_phones or not owner:
        return 0
    ensure_crm_data_imports_schema()
    with neon_connection() as conn:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    update public.crm_data_imports
                    set owner = %s,
                        updated_at = now()
                    where phone1 = any(%s) or phone2 = any(%s)
                    """,
                    [owner, clean_phones, clean_phones],
                )
                updated = int(cur.rowcount or 0)
                cur.executemany(
                    """
                    insert into public.crm_owner_assignments (phone_key, owner, updated_by, updated_at)
                    values (%s, %s, %s, now())
                    on conflict (phone_key) do update
                    set owner = excluded.owner,
                        updated_by = excluded.updated_by,
                        updated_at = now()
                    """,
                    [(phone, owner, clean(updated_by)) for phone in clean_phones],
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    return updated


def fetch_filter_options() -> dict[str, list[str]]:
    ensure_crm_data_imports_schema()
    with neon_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select distinct owner
                from public.crm_data_imports
                where owner is not null and owner <> ''
                order by owner
                limit 1000
                """
            )
            return {"product_group": [], "sales_staff": [row["owner"] for row in cur.fetchall()]}


def search_terms(keyword: str) -> dict[str, tuple[str, ...]]:
    keyword = clean(keyword)
    if not keyword:
        return {"phones": (), "customers": ()}
    ensure_crm_data_imports_schema()
    like = f"%{keyword}%"
    with neon_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select customer_name, phone1, phone2
                from public.crm_data_imports
                where customer_name ilike %s
                   or phone1 ilike %s
                   or phone2 ilike %s
                   or postal_code ilike %s
                   or tracking_no ilike %s
                   or order_id ilike %s
                limit 80
                """,
                [like, like, like, like, like, like],
            )
            rows = cur.fetchall()
    phones: list[str] = []
    customers: list[str] = []
    for row in rows:
        for name in ("phone1", "phone2"):
            phone = normalize_phone(row.get(name))
            if phone and phone not in phones:
                phones.append(phone)
        customer = clean(row.get("customer_name"))
        if customer and customer not in customers:
            customers.append(customer)
    return {"phones": tuple(phones[:30]), "customers": tuple(customers[:20])}


def fetch_orders_by_phones(phones: tuple[str, ...], limit: int = 5000) -> list[dict]:
    clean_phones = [normalize_phone(phone) for phone in phones if normalize_phone(phone)]
    if not clean_phones:
        return []
    ensure_crm_data_imports_schema()
    clauses = []
    params: list = []
    for phone in clean_phones[:6]:
        clauses.append("(phone1 = %s or phone2 = %s)")
        params.extend([phone, phone])
    with neon_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                select
                  id::text as source_key,
                  order_id,
                  order_date::text as date_text,
                  order_date,
                  customer_name as customer,
                  phone1,
                  phone2,
                  raw_data->>'ที่อยู่จัดส่ง' as address,
                  raw_data->>'ตำบล' as subdistrict,
                  city as district,
                  province,
                  postal_code as postcode,
                  raw_data->>'ช่องทางขาย' as channel,
                  raw_data->>'พนักงานเปิดบิล' as sales_staff,
                  raw_data->>'พนักงานอัพเซลล์' as upsell_staff,
                  owner as care_staff,
                  total_amount as total_sales,
                  order_status,
                  raw_data->>'วิธีการชำระ' as payment_method,
                  carrier as shipping,
                  tracking_no,
                  url as channel_url,
                  sku,
                  product_name,
                  raw_data,
                  updated_at
                from public.crm_data_imports
                where import_status = 'valid'
                  and ({' or '.join(clauses)})
                order by order_date desc nulls last, uploaded_at desc, id desc
                limit %s
                """,
                params + [limit],
            )
            rows = cur.fetchall()
    for row in rows:
        row["products"] = [
            {
                "sku": clean(row.get("sku")),
                "name": clean(row.get("product_name")),
                "qty": clean((row.get("raw_data") or {}).get("จำนวน")),
                "price": clean(row.get("total_sales")),
            }
        ]
    return rows


def fetch_import_history(limit: int = 50) -> list[dict]:
    ensure_crm_data_imports_schema()
    with neon_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select
                  import_batch_id::text,
                  max(source_file_name) as source_file_name,
                  max(sheet_name) as sheet_name,
                  max(uploaded_by) as uploaded_by,
                  max(uploaded_at) as uploaded_at,
                  count(*) as total_rows,
                  count(*) filter (where import_status = 'valid') as valid_rows,
                  count(*) filter (where import_status = 'invalid') as invalid_rows
                from public.crm_data_imports
                group by import_batch_id
                order by max(uploaded_at) desc
                limit %s
                """,
                [limit],
            )
            return cur.fetchall()


def delete_import_batch(batch_id: str) -> int:
    ensure_crm_data_imports_schema()
    with neon_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("delete from public.crm_data_imports where import_batch_id = %s", [batch_id])
            deleted = cur.rowcount
        conn.commit()
    return int(deleted or 0)


def fetch_lead_followups(limit: int = 100000) -> list[dict]:
    ensure_crm_data_imports_schema()
    with neon_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select
                  customer_key,
                  customer_id,
                  customer_name,
                  phone_key,
                  phone1,
                  phone2,
                  product_group,
                  lead_status,
                  follow_up_status,
                  follow_up_date::text as follow_up_date,
                  follow_up_note,
                  priority,
                  updated_by,
                  updated_at,
                  created_at
                from public.crm_lead_followups
                order by updated_at desc
                limit %s
                """,
                [int(limit)],
            )
            return cur.fetchall()


def upsert_lead_followup(payload: dict) -> None:
    ensure_crm_data_imports_schema()
    columns = [
        "customer_key",
        "customer_id",
        "customer_name",
        "phone_key",
        "phone1",
        "phone2",
        "product_group",
        "lead_status",
        "follow_up_status",
        "follow_up_date",
        "follow_up_note",
        "priority",
        "updated_by",
        "updated_at",
    ]
    values = [payload.get(column) for column in columns]
    set_clause = ", ".join([f"{column} = excluded.{column}" for column in columns[1:]])
    with neon_connection() as conn:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    insert into public.crm_lead_followups ({', '.join(columns)})
                    values ({', '.join(['%s'] * len(columns))})
                    on conflict (customer_key) do update
                    set {set_clause}
                    """,
                    values,
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def fetch_product_options() -> list[dict]:
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
                    on conflict (product_group, product_name) do update
                    set sku = excluded.sku,
                        sort_order = excluded.sort_order,
                        is_active = excluded.is_active,
                        updated_by = excluded.updated_by,
                        updated_at = excluded.updated_at
                    """,
                    [tuple(record.get(column) for column in columns) for record in records],
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def update_product_option(option_id: str, payload: dict) -> None:
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
    ensure_crm_data_imports_schema()
    with neon_connection() as conn:
        try:
            with conn.cursor() as cur:
                cur.execute("delete from public.crm_product_options where id = %s", [option_id])
            conn.commit()
        except Exception:
            conn.rollback()
            raise
