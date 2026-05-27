import hashlib
import html
import json
import os
import uuid
from datetime import datetime, timezone
from urllib.parse import quote

import pandas as pd
import requests
import streamlit as st


UPLOAD_BATCH_SIZE = 500
IMPORT_BATCHES_TABLE = "import_batches"
IMPORT_STAGING_TABLE = "import_staging"
IMPORT_LOGS_TABLE = "import_logs"
IMPORT_BACKUPS_TABLE = "import_backups"

TARGETS = {
    "order_history": {
        "label": "ประวัติคำสั่งซื้อ (order_history)",
        "key": "source_key",
        "required": ["source_key", "order_id"],
        "fields": [
            "source_key",
            "order_id",
            "year",
            "month",
            "day",
            "date_text",
            "customer",
            "phone1",
            "phone2",
            "address",
            "subdistrict",
            "district",
            "province",
            "postcode",
            "channel",
            "sales_staff",
            "upsell_staff",
            "care_staff",
            "product_group",
            "total_sales",
            "order_status",
            "payment_method",
            "delivery_status",
            "shipping",
            "tracking_no",
            "channel_url",
            "note",
            "source_sheet",
            "year_file",
        ],
        "synonyms": {
            "order_id": ["เลขคำสั่งซื้อ", "เลขออเดอร์", "order_id"],
            "customer": ["ลูกค้า", "ชื่อลูกค้า", "customer"],
            "phone1": ["เบอร์โทร (1)", "เบอร์โทร", "เบอร์โทรติดต่อ", "phone1"],
            "phone2": ["เบอร์โทร (2)", "เบอร์โทรสำรอง", "phone2"],
            "product_group": ["หมวดสินค้า", "กลุ่มสินค้า", "product_group"],
            "total_sales": ["ยอดขายรวม", "ยอดขาย", "total_sales"],
            "date_text": ["วันที่", "date_text"],
        },
    },
    "crm_customers": {
        "label": "ลูกค้า CRM (crm_customers)",
        "key": "customer_id",
        "required": ["customer_id", "customer", "product_group"],
        "fields": [
            "customer_id",
            "customer",
            "sales_staff",
            "product_url",
            "product_name",
            "phone1",
            "phone2",
            "product_group",
            "call_1",
            "call_2",
            "call_3",
            "note",
            "source_spreadsheet_id",
            "source_sheet",
            "row_hash",
        ],
        "synonyms": {
            "customer": ["ชื่อลูกค้า", "ลูกค้า", "customer"],
            "sales_staff": ["ผู้ดูแล", "พนักงานดูแล", "sales_staff", "owner"],
            "product_url": ["URL", "url", "ลิงก์", "product_url"],
            "product_name": ["สินค้า", "product_name", "product"],
            "phone1": ["เบอร์โทรติดต่อ", "เบอร์โทร (1)", "เบอร์โทร", "phone1"],
            "phone2": ["เบอร์โทรสำรอง", "เบอร์โทร (2)", "phone2"],
            "product_group": ["กลุ่มสินค้า", "หมวดสินค้า", "product_group"],
            "note": ["โน๊ต", "โน้ต", "หมายเหตุ", "note"],
        },
    },
}


def get_secret(*names: str) -> str:
    for name in names:
        if name in st.secrets:
            return st.secrets[name]
        value = os.getenv(name, "")
        if value:
            return value
    return ""


SUPABASE_URL = get_secret("CRM_SUPABASE_URL", "SUPABASE_URL").rstrip("/")
SUPABASE_SERVICE_KEY = get_secret("CRM_SUPABASE_SERVICE_KEY", "SUPABASE_SERVICE_KEY")
UPLOAD_ADMIN_PASSWORD = get_secret("CRM_UPLOAD_ADMIN_PASSWORD", "CRM_SYNC_ADMIN_PASSWORD")


st.set_page_config(page_title="Upload Excel", layout="wide")


def main() -> None:
    inject_css()
    st.title("Upload Excel → Supabase")
    st.caption("นำเข้าไฟล์เข้า import_staging ก่อนตรวจและยืนยันอัปเดตลง Database")

    if not require_config():
        st.stop()
    if not require_upload_access():
        st.stop()

    tab_upload, tab_batches, tab_cleanup = st.tabs(["Upload", "ตรวจ/ยืนยัน", "Cleanup"])
    with tab_upload:
        render_upload_tab()
    with tab_batches:
        render_batches_tab()
    with tab_cleanup:
        render_cleanup_tab()


def inject_css() -> None:
    st.markdown(
        """
<style>
.stApp { background:#fff8f1; color:#111827; }
.block-container { max-width:1500px; padding-top:2rem; }
h1, h2, h3 { color:#111827; }
h1 { border-left:6px solid #f97316; padding-left:14px; }
[data-testid="stMetric"] {
  background:#fff;
  border:1px solid #fed7aa;
  border-radius:8px;
  padding:14px;
}
.upload-card {
  background:#fff;
  border:1px solid #fed7aa;
  border-radius:8px;
  padding:16px;
  margin:12px 0;
}
.badge {
  display:inline-block;
  padding:4px 10px;
  border-radius:999px;
  background:#ffedd5;
  color:#7c2d12;
  font-size:12px;
  font-weight:700;
  margin:0 6px 6px 0;
}
.badge-green { background:#dcfce7; color:#166534; }
.badge-red { background:#fee2e2; color:#991b1b; }
.badge-blue { background:#dbeafe; color:#1d4ed8; }
</style>
""",
        unsafe_allow_html=True,
    )


def require_config() -> bool:
    missing = []
    if not SUPABASE_URL:
        missing.append("CRM_SUPABASE_URL")
    if not SUPABASE_SERVICE_KEY:
        missing.append("CRM_SUPABASE_SERVICE_KEY")
    if missing:
        st.error("ยังไม่ได้ตั้งค่า Streamlit secrets: " + ", ".join(missing))
        return False
    return True


def require_upload_access() -> bool:
    if not UPLOAD_ADMIN_PASSWORD:
        st.error("ยังไม่ได้ตั้งค่า CRM_UPLOAD_ADMIN_PASSWORD หรือ CRM_SYNC_ADMIN_PASSWORD สำหรับป้องกันหน้า Upload")
        return False
    if st.session_state.get("upload_excel_authenticated"):
        return True
    password = st.text_input("รหัสสำหรับ Upload/Admin", type="password")
    if st.button("เข้าสู่หน้า Upload", use_container_width=True):
        if password == UPLOAD_ADMIN_PASSWORD:
            st.session_state.upload_excel_authenticated = True
            st.rerun()
        st.error("รหัสไม่ถูกต้อง")
    return False


def service_headers(prefer: str = "return=representation") -> dict[str, str]:
    return {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json",
        "Prefer": prefer,
    }


def api_request(method: str, table: str, payload=None, params: str = "", prefer: str = "return=representation"):
    url = f"{SUPABASE_URL}/rest/v1/{table}{params}"
    response = requests.request(
        method,
        url,
        headers=service_headers(prefer),
        data=json.dumps(payload, ensure_ascii=False) if payload is not None else None,
        timeout=120,
    )
    if response.status_code >= 300:
        raise RuntimeError(f"{method} {table} failed: {response.status_code} {response.text}")
    if not response.text:
        return []
    return response.json()


def render_upload_tab() -> None:
    uploaded = st.file_uploader("เลือกไฟล์ Excel หรือ CSV", type=["xlsx", "csv"])
    if not uploaded:
        st.info("เลือกไฟล์ก่อน ระบบจะ preview และให้ mapping column ก่อนนำเข้า staging")
        return

    target_table = st.selectbox(
        "ปลายทางหลังยืนยัน",
        list(TARGETS.keys()),
        format_func=lambda key: TARGETS[key]["label"],
    )
    worksheet = ""
    df = read_uploaded_dataframe(uploaded)
    if isinstance(df, dict):
        worksheets = list(df.keys())
        worksheet = st.selectbox("Worksheet", worksheets)
        df = df[worksheet]

    if df.empty:
        st.warning("ไฟล์นี้ไม่มีข้อมูล")
        return

    df = normalize_dataframe(df)
    st.subheader("1. Mapping Columns")
    mapping = render_mapping_controls(df, target_table)
    mapped = build_mapped_rows(df, target_table, mapping, uploaded.name, worksheet)
    duplicate_keys = find_duplicate_keys([row["unique_key"] for row in mapped])
    existing_keys = fetch_existing_keys(target_table, [row["unique_key"] for row in mapped if row["unique_key"]])
    validated = validate_rows(mapped, target_table, duplicate_keys, existing_keys)

    st.subheader("2. Preview ก่อน import")
    render_validation_summary(validated)
    preview_df = pd.DataFrame([row["mapped_record"] | {"_errors": ", ".join(row["validation_errors"])} for row in validated])
    edited = st.data_editor(preview_df.head(200), use_container_width=True, num_rows="fixed")
    st.caption("แสดง/แก้ preview ได้สูงสุด 200 แถวแรก ก่อนนำเข้า staging")

    confirm_stage = st.checkbox("ยืนยันว่า mapping ถูกต้อง และต้องการนำเข้า import_staging")
    created_by = st.text_input("ชื่อผู้ทำรายการ", value="")
    if st.button("นำเข้า import_staging", disabled=not confirm_stage, use_container_width=True):
        if not created_by.strip():
            st.error("กรุณาระบุชื่อผู้ทำรายการก่อน")
            return
        edited_validated = apply_preview_edits(validated, edited)
        batch_id = create_staging_batch(
            target_table=target_table,
            filename=uploaded.name,
            worksheet=worksheet,
            rows=edited_validated,
            created_by=created_by.strip(),
        )
        st.success(f"นำเข้า staging แล้ว: {batch_id}")
        st.session_state.last_upload_batch_id = batch_id


def read_uploaded_dataframe(uploaded):
    name = uploaded.name.lower()
    uploaded.seek(0)
    if name.endswith(".csv"):
        return pd.read_csv(uploaded, dtype=str).fillna("")
    excel = pd.ExcelFile(uploaded)
    sheets = {}
    for sheet in excel.sheet_names:
        sheets[sheet] = pd.read_excel(excel, sheet_name=sheet, dtype=str).fillna("")
    return sheets


def normalize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [clean(col) or f"EMPTY_{index}" for index, col in enumerate(df.columns)]
    return df.fillna("").astype(str)


def render_mapping_controls(df: pd.DataFrame, target_table: str) -> dict[str, str]:
    target = TARGETS[target_table]
    source_options = ["ไม่ใช้"] + list(df.columns)
    mapping = {}
    cols = st.columns(3)
    for index, field in enumerate(target["fields"]):
        default = auto_match_column(field, df.columns, target["synonyms"])
        mapping[field] = cols[index % 3].selectbox(
            field,
            source_options,
            index=source_options.index(default) if default in source_options else 0,
            key=f"map_{target_table}_{field}",
        )
    return mapping


def auto_match_column(field: str, columns, synonyms: dict[str, list[str]]) -> str:
    candidates = [field] + synonyms.get(field, [])
    lowered = {clean(col).lower(): col for col in columns}
    for candidate in candidates:
        if candidate.lower() in lowered:
            return lowered[candidate.lower()]
    return "ไม่ใช้"


def build_mapped_rows(df: pd.DataFrame, target_table: str, mapping: dict[str, str], filename: str, worksheet: str) -> list[dict]:
    rows = []
    for index, row in df.iterrows():
        record = {}
        for field, source_col in mapping.items():
            record[field] = clean(row.get(source_col)) if source_col != "ไม่ใช้" else ""
        enrich_record(record, target_table, filename, worksheet, index + 2)
        unique_key = clean(record.get(TARGETS[target_table]["key"]))
        rows.append(
            {
                "row_number": index + 2,
                "raw_record": {str(key): clean(value) for key, value in row.to_dict().items()},
                "mapped_record": record,
                "unique_key": unique_key,
                "row_hash": row_hash(record),
            }
        )
    return rows


def enrich_record(record: dict, target_table: str, filename: str, worksheet: str, row_number: int) -> None:
    now = now_iso()
    if target_table == "order_history":
        if not clean(record.get("source_key")):
            order_id = clean(record.get("order_id"))
            record["source_key"] = f"upload:{filename}:{worksheet}:{order_id or row_number}"
        if not clean(record.get("year_file")):
            record["year_file"] = clean(record.get("year"))
        record["source_sheet"] = clean(record.get("source_sheet")) or worksheet or filename
        record["synced_at"] = now
    else:
        if not clean(record.get("customer_id")):
            parts = [filename, worksheet, clean(record.get("phone1")), clean(record.get("customer")), clean(record.get("product_group")), str(row_number)]
            record["customer_id"] = "upload:" + hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()
        record["source_sheet"] = clean(record.get("source_sheet")) or worksheet or filename
        record["row_hash"] = clean(record.get("row_hash")) or row_hash(record)
        record["synced_at"] = now
        record["updated_at"] = now


def validate_rows(rows: list[dict], target_table: str, duplicate_keys: set[str], existing_keys: set[str]) -> list[dict]:
    required = TARGETS[target_table]["required"]
    for row in rows:
        errors = []
        record = row["mapped_record"]
        for field in required:
            if not clean(record.get(field)):
                errors.append(f"empty:{field}")
        if row["unique_key"] in duplicate_keys:
            errors.append("duplicate_in_file")
            row["duplicate_in_file"] = True
        else:
            row["duplicate_in_file"] = False
        row["duplicate_in_database"] = row["unique_key"] in existing_keys
        if row["duplicate_in_database"]:
            errors.append("duplicate_in_database")
        row["validation_errors"] = errors
        blocking_errors = [error for error in errors if error != "duplicate_in_database"]
        row["status"] = "invalid" if blocking_errors else "valid"
    return rows


def render_validation_summary(rows: list[dict]) -> None:
    total = len(rows)
    invalid = sum(1 for row in rows if row["status"] == "invalid")
    dup_file = sum(1 for row in rows if row.get("duplicate_in_file"))
    dup_db = sum(1 for row in rows if row.get("duplicate_in_database"))
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("ทั้งหมด", f"{total:,}")
    col2.metric("พร้อมเข้า staging", f"{total - invalid:,}")
    col3.metric("ซ้ำในไฟล์", f"{dup_file:,}")
    col4.metric("ซ้ำใน Database", f"{dup_db:,}")


def apply_preview_edits(rows: list[dict], edited: pd.DataFrame) -> list[dict]:
    updated = rows.copy()
    for pos, (_, edited_row) in enumerate(edited.iterrows()):
        if pos >= len(updated):
            break
        record = updated[pos]["mapped_record"].copy()
        for col, value in edited_row.to_dict().items():
            if not col.startswith("_"):
                record[col] = clean(value)
        updated[pos]["mapped_record"] = record
        updated[pos]["row_hash"] = row_hash(record)
    return updated


def create_staging_batch(target_table: str, filename: str, worksheet: str, rows: list[dict], created_by: str) -> str:
    batch_id = str(uuid.uuid4())
    valid = sum(1 for row in rows if row["status"] == "valid")
    invalid = len(rows) - valid
    duplicates = sum(1 for row in rows if row.get("duplicate_in_file") or row.get("duplicate_in_database"))
    api_request(
        "POST",
        IMPORT_BATCHES_TABLE,
        {
            "id": batch_id,
            "target_table": target_table,
            "original_filename": filename,
            "worksheet_name": worksheet,
            "total_rows": len(rows),
            "valid_rows": valid,
            "invalid_rows": invalid,
            "duplicate_rows": duplicates,
            "created_by": created_by,
        },
    )
    staging_rows = []
    for row in rows:
        staging_rows.append(
            {
                "batch_id": batch_id,
                "target_table": target_table,
                "row_number": row["row_number"],
                "raw_record": row["raw_record"],
                "mapped_record": row["mapped_record"],
                "unique_key": row["unique_key"],
                "row_hash": row["row_hash"],
                "validation_errors": row["validation_errors"],
                "duplicate_in_file": row.get("duplicate_in_file", False),
                "duplicate_in_database": row.get("duplicate_in_database", False),
                "status": row["status"],
            }
        )
    batch_insert(IMPORT_STAGING_TABLE, staging_rows, conflict_key=None)
    log_event(batch_id, "info", f"staged {len(rows):,} rows")
    return batch_id


def render_batches_tab() -> None:
    batches = api_request(
        "GET",
        IMPORT_BATCHES_TABLE,
        params="?select=*&order=created_at.desc&limit=20",
    )
    if not batches:
        st.info("ยังไม่มี batch ใน import_staging")
        return
    labels = [batch_label(batch) for batch in batches]
    default_index = 0
    last_id = st.session_state.get("last_upload_batch_id")
    if last_id:
        for idx, batch in enumerate(batches):
            if batch["id"] == last_id:
                default_index = idx
                break
    selected_label = st.selectbox("เลือก batch", labels, index=default_index)
    batch = batches[labels.index(selected_label)]
    render_batch_detail(batch)


def render_batch_detail(batch: dict) -> None:
    st.markdown(
        f"""
<div class="upload-card">
<span class="badge badge-blue">{html_escape(batch.get("target_table"))}</span>
<span class="badge">{html_escape(batch.get("status"))}</span>
<span class="badge badge-green">valid {batch.get("valid_rows", 0):,}</span>
<span class="badge badge-red">invalid {batch.get("invalid_rows", 0):,}</span>
</div>
""",
        unsafe_allow_html=True,
    )
    rows = api_request(
        "GET",
        IMPORT_STAGING_TABLE,
        params=f"?batch_id=eq.{quote(batch['id'])}&select=row_number,unique_key,status,validation_errors,duplicate_in_database,mapped_record&order=row_number.asc&limit=200",
    )
    if rows:
        preview = []
        for row in rows:
            preview.append(
                {
                    "row": row["row_number"],
                    "key": row["unique_key"],
                    "status": row["status"],
                    "errors": ", ".join(row.get("validation_errors") or []),
                    **(row.get("mapped_record") or {}),
                }
            )
        st.dataframe(pd.DataFrame(preview), use_container_width=True)

    overwrite = st.checkbox("ยืนยันให้ overwrite ข้อมูลเดิมได้ ถ้า key ซ้ำ", value=False)
    clean_old = st.checkbox("หลัง import สำเร็จ ให้ลบ staging rows ของ batch นี้เพื่อลดขยะ", value=True)
    if st.button("อัปเดตไฟล์ลง Database", use_container_width=True):
        promote_batch(batch["id"], batch["target_table"], overwrite, clean_old)


def promote_batch(batch_id: str, target_table: str, overwrite: bool, clean_old: bool) -> None:
    rows = api_request(
        "GET",
        IMPORT_STAGING_TABLE,
        params=f"?batch_id=eq.{quote(batch_id)}&status=eq.valid&select=*&order=row_number.asc",
    )
    if not rows:
        st.warning("ไม่มี rows ที่ valid สำหรับ import")
        return

    api_request("PATCH", IMPORT_BATCHES_TABLE, {"status": "importing", "overwrite_confirmed": overwrite}, f"?id=eq.{quote(batch_id)}")
    progress = st.progress(0)
    imported = 0
    skipped = 0
    inserted_keys = []
    target_key = TARGETS[target_table]["key"]

    try:
        existing_keys = fetch_existing_keys(target_table, [row["unique_key"] for row in rows])
        if overwrite:
            backup_existing_records(batch_id, target_table, target_key, existing_keys)

        importable = []
        for row in rows:
            if row["unique_key"] in existing_keys and not overwrite:
                skipped += 1
                mark_staging(row["id"], "skipped", "duplicate exists; overwrite not confirmed")
                continue
            record = row["mapped_record"] or {}
            record["import_batch_id"] = batch_id
            record["imported_at"] = now_iso()
            importable.append((row, record))

        for start in range(0, len(importable), UPLOAD_BATCH_SIZE):
            chunk = importable[start : start + UPLOAD_BATCH_SIZE]
            records = [record for _, record in chunk]
            prefer = "resolution=merge-duplicates,return=representation" if overwrite else "resolution=ignore-duplicates,return=representation"
            batch_insert(target_table, records, conflict_key=target_key, prefer=prefer)
            for staging_row, record in chunk:
                inserted_keys.append(clean(record.get(target_key)))
                mark_staging(staging_row["id"], "imported", "")
            imported += len(chunk)
            progress.progress(min((start + len(chunk)) / max(len(importable), 1), 1.0))

        api_request(
            "PATCH",
            IMPORT_BATCHES_TABLE,
            {
                "status": "success",
                "imported_rows": imported,
                "skipped_rows": skipped,
                "completed_at": now_iso(),
                "updated_at": now_iso(),
            },
            f"?id=eq.{quote(batch_id)}",
        )
        log_event(batch_id, "info", f"imported {imported:,} rows, skipped {skipped:,}")
        if clean_old:
            api_request("DELETE", IMPORT_STAGING_TABLE, params=f"?batch_id=eq.{quote(batch_id)}", prefer="return=minimal")
            log_event(batch_id, "info", "cleaned staging rows after successful import")
        st.success(f"Import สำเร็จ {imported:,} rows, skip {skipped:,} rows")
    except Exception as exc:
        rollback_import(batch_id, target_table, target_key)
        api_request(
            "PATCH",
            IMPORT_BATCHES_TABLE,
            {"status": "failed", "updated_at": now_iso()},
            f"?id=eq.{quote(batch_id)}",
        )
        log_event(batch_id, "error", "import failed and rollback attempted", {"error": str(exc), "keys": inserted_keys[:50]})
        st.error("Import fail และพยายาม rollback แล้ว: " + str(exc))


def backup_existing_records(batch_id: str, target_table: str, target_key: str, keys: set[str]) -> None:
    if not keys:
        return
    existing = fetch_existing_records(target_table, target_key, keys)
    backups = [
        {
            "batch_id": batch_id,
            "target_table": target_table,
            "unique_key": clean(row.get(target_key)),
            "previous_record": row,
        }
        for row in existing
    ]
    batch_insert(IMPORT_BACKUPS_TABLE, backups, conflict_key="batch_id,target_table,unique_key")


def rollback_import(batch_id: str, target_table: str, target_key: str) -> None:
    api_request("DELETE", target_table, params=f"?import_batch_id=eq.{quote(batch_id)}", prefer="return=minimal")
    backups = api_request("GET", IMPORT_BACKUPS_TABLE, params=f"?batch_id=eq.{quote(batch_id)}&target_table=eq.{target_table}&select=previous_record")
    records = [row["previous_record"] for row in backups if row.get("previous_record")]
    if records:
        batch_insert(target_table, records, conflict_key=target_key, prefer="resolution=merge-duplicates,return=minimal")
    api_request("PATCH", IMPORT_BATCHES_TABLE, {"status": "rolled_back", "updated_at": now_iso()}, f"?id=eq.{quote(batch_id)}")


def render_cleanup_tab() -> None:
    st.subheader("ลบข้อมูลที่ไม่ใช้")
    st.warning("ส่วนนี้ลบเฉพาะ staging/import logs หรือข้อมูล final ที่มาจาก upload batch เท่านั้น ไม่ลบข้อมูล sync เดิมแบบไม่ระบุ batch")
    days = st.number_input("ลบ staging/log ที่เก่ากว่ากี่วัน", min_value=1, max_value=365, value=30)
    confirm = st.checkbox("ยืนยัน cleanup")
    if st.button("ลบ staging/log เก่า", disabled=not confirm):
        cutoff = (datetime.now(timezone.utc) - pd.Timedelta(days=int(days))).isoformat()
        api_request("DELETE", IMPORT_BATCHES_TABLE, params=f"?created_at=lt.{quote(cutoff)}&status=in.(success,failed,rolled_back,cleaned)", prefer="return=minimal")
        st.success("cleanup staging/log เก่าแล้ว")

    batches = api_request("GET", IMPORT_BATCHES_TABLE, params="?select=id,target_table,status,original_filename,created_at&order=created_at.desc&limit=50")
    if batches:
        label = st.selectbox("เลือก upload batch ที่ต้องการลบข้อมูล final ออก", ["ไม่เลือก"] + [batch_label(batch) for batch in batches])
        confirm_final = st.checkbox("ยืนยันลบข้อมูล final ของ batch นี้")
        if label != "ไม่เลือก" and st.button("ลบข้อมูล final ของ batch นี้", disabled=not confirm_final):
            batch = batches[[batch_label(batch) for batch in batches].index(label)]
            api_request("DELETE", batch["target_table"], params=f"?import_batch_id=eq.{quote(batch['id'])}", prefer="return=minimal")
            api_request("PATCH", IMPORT_BATCHES_TABLE, {"status": "cleaned", "updated_at": now_iso()}, f"?id=eq.{quote(batch['id'])}")
            log_event(batch["id"], "warning", "final rows for upload batch were deleted by cleanup")
            st.success("ลบข้อมูล final ของ batch นี้แล้ว")


def fetch_existing_keys(target_table: str, keys: list[str]) -> set[str]:
    target_key = TARGETS[target_table]["key"]
    existing = fetch_existing_records(target_table, target_key, set(keys))
    return {clean(row.get(target_key)) for row in existing}


def fetch_existing_records(target_table: str, target_key: str, keys: set[str]) -> list[dict]:
    clean_keys = sorted({clean(key) for key in keys if clean(key)})
    found = []
    for start in range(0, len(clean_keys), 100):
        chunk = clean_keys[start : start + 100]
        values = ",".join(f'"{key.replace(chr(34), "")}"' for key in chunk)
        found.extend(api_request("GET", target_table, params=f"?{target_key}=in.({values})&select=*"))
    return found


def batch_insert(table: str, records: list[dict], conflict_key: str | None, prefer: str | None = None) -> None:
    if not records:
        return
    params = f"?on_conflict={quote(conflict_key, safe=',')}" if conflict_key else ""
    header_prefer = prefer or ("resolution=merge-duplicates,return=minimal" if conflict_key else "return=minimal")
    for start in range(0, len(records), UPLOAD_BATCH_SIZE):
        api_request("POST", table, records[start : start + UPLOAD_BATCH_SIZE], params=params, prefer=header_prefer)


def mark_staging(row_id: int, status: str, message: str) -> None:
    api_request(
        "PATCH",
        IMPORT_STAGING_TABLE,
        {"status": status, "error_message": message, "imported_at": now_iso() if status == "imported" else None},
        f"?id=eq.{row_id}",
        prefer="return=minimal",
    )


def log_event(batch_id: str, level: str, message: str, detail: dict | None = None) -> None:
    api_request("POST", IMPORT_LOGS_TABLE, {"batch_id": batch_id, "level": level, "message": message, "detail": detail or {}}, prefer="return=minimal")


def find_duplicate_keys(keys: list[str]) -> set[str]:
    seen = set()
    dupes = set()
    for key in keys:
        if not key:
            continue
        if key in seen:
            dupes.add(key)
        seen.add(key)
    return dupes


def batch_label(batch: dict) -> str:
    return f"{batch.get('created_at', '')} | {batch.get('target_table')} | {batch.get('original_filename', '')} | {batch.get('status')} | {batch.get('id')}"


def row_hash(record: dict) -> str:
    return hashlib.sha1(json.dumps(record, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def clean(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and pd.isna(value):
        return ""
    text = str(value).strip()
    return "" if text.upper() in {"NULL", "NONE", "NAN"} else text


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def html_escape(value) -> str:
    return html.escape(clean(value), quote=True)


if __name__ == "__main__":
    main()
