import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from typing import Any

import gspread
import requests
from google.oauth2.service_account import Credentials


SUPABASE_URL = os.environ.get("CRM_SUPABASE_URL") or os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.environ.get("CRM_SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_SERVICE_KEY")
GOOGLE_SERVICE_ACCOUNT_FILE = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "service_account.json")
GOOGLE_SERVICE_ACCOUNT_JSON = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
TRIGGER_TYPE = os.environ.get("SYNC_TRIGGER_TYPE", "manual")

ORDER_TABLE = "order_history"
CONTROL_TABLE = "sync_control"
RUN_TABLE = "sync_runs"
SYNC_NAME = "data_raw"
SYNC_CONTROL_COLUMNS = ",".join(
    [
        "sync_name",
        "is_paused",
        "stop_requested",
        "current_run_id",
        "last_status",
        "last_message",
        "last_started_at",
        "last_finished_at",
        "last_source",
        "last_rows_read",
        "last_records_upserted",
        "updated_at",
    ]
)
BATCH_SIZE = int(os.environ.get("DATA_RAW_BATCH_SIZE", "250"))
MIN_BATCH_SIZE = int(os.environ.get("DATA_RAW_MIN_BATCH_SIZE", "25"))
MAX_UPSERT_RETRIES = int(os.environ.get("DATA_RAW_MAX_UPSERT_RETRIES", "3"))
RETRY_SLEEP_SECONDS = float(os.environ.get("DATA_RAW_RETRY_SLEEP_SECONDS", "2"))
REQUEST_TIMEOUT = 120
TRANSIENT_STATUS_CODES = {408, 425, 429, 500, 502, 503, 504}

DATA_SOURCES = [
    {"year_file": "2565", "sheet_id": "1Q9CyZi5ezvthVABg-aw6LvrYtSp7qRHiEr4pVMGMKHg", "worksheet": "DATA_RAW"},
    {"year_file": "2566", "sheet_id": "1Up4Vnx5fjxQMl6oEgFEpaJV9D8s4_pnEpIi0OS4LD08", "worksheet": "DATA_RAW"},
    {"year_file": "2567", "sheet_id": "1U2CJ0HIcANRYNSlMSOun5_2RT4ElVFzoMaQMhZ4XD7s", "worksheet": "DATA_RAW"},
    {"year_file": "2568", "sheet_id": "1FdHmaZ3eesHbF5WO5dZEDKSq9AmlNqKPD056Fa-yfuI", "worksheet": "DATA_RAW"},
    {"year_file": "2569", "sheet_id": "1LewCpziyieVJ_hnV2KYzXW7ZE43Nj5Yg7Lp2lsIF5o4", "worksheet": "DATA_RAW"},
]


class SyncStopped(RuntimeError):
    pass


class SupabaseUpsertError(RuntimeError):
    def __init__(self, status_code: int, text: str) -> None:
        self.status_code = status_code
        self.text = text
        super().__init__(f"Supabase upsert failed: {status_code} {text}")


def is_timeout_error(text: str) -> bool:
    lowered = text.lower()
    return "timeout" in lowered or "57014" in lowered or "statement timeout" in lowered


def is_transient_error(exc: Exception) -> bool:
    if isinstance(exc, SupabaseUpsertError):
        return exc.status_code in TRANSIENT_STATUS_CODES or is_timeout_error(exc.text)
    return isinstance(exc, (requests.Timeout, requests.ConnectionError))


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def require_config() -> None:
    missing = []
    if not SUPABASE_URL:
        missing.append("CRM_SUPABASE_URL")
    if not SUPABASE_SERVICE_KEY:
        missing.append("CRM_SUPABASE_SERVICE_KEY")
    if not GOOGLE_SERVICE_ACCOUNT_JSON and not os.path.exists(GOOGLE_SERVICE_ACCOUNT_FILE):
        missing.append("GOOGLE_SERVICE_ACCOUNT_JSON or service_account.json")
    if missing:
        raise RuntimeError("Missing config: " + ", ".join(missing))


def service_headers(extra: dict[str, str] | None = None) -> dict[str, str]:
    headers = {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json",
    }
    if extra:
        headers.update(extra)
    return headers


def supabase_request(
    method: str,
    path: str,
    payload: Any | None = None,
    params: str = "",
    prefer: str = "return=minimal",
) -> Any:
    url = f"{SUPABASE_URL.rstrip('/')}/rest/v1/{path}{params}"
    response = requests.request(
        method,
        url,
        headers=service_headers({"Prefer": prefer}),
        data=json.dumps(payload, ensure_ascii=False) if payload is not None else None,
        timeout=REQUEST_TIMEOUT,
    )
    if response.status_code >= 300:
        raise RuntimeError(f"Supabase {method} {path} failed: {response.status_code} {response.text}")
    if not response.text:
        return None
    return response.json()


def update_control(**fields: Any) -> None:
    fields["updated_at"] = now_iso()
    supabase_request("PATCH", CONTROL_TABLE, fields, f"?sync_name=eq.{SYNC_NAME}")


def create_run() -> str:
    run_id = str(uuid.uuid4())
    supabase_request(
        "POST",
        RUN_TABLE,
        {
            "id": run_id,
            "sync_name": SYNC_NAME,
            "status": "running",
            "trigger_type": TRIGGER_TYPE,
            "started_at": now_iso(),
        },
        prefer="return=minimal",
    )
    update_control(
        is_paused=False,
        stop_requested=False,
        current_run_id=run_id,
        last_status="running",
        last_message="เริ่มซิงก์ DATA_RAW",
        last_started_at=now_iso(),
        last_finished_at=None,
        last_rows_read=0,
        last_records_upserted=0,
    )
    return run_id


def update_run(run_id: str, **fields: Any) -> None:
    supabase_request("PATCH", RUN_TABLE, fields, f"?id=eq.{run_id}")


def get_control() -> dict[str, Any]:
    rows = supabase_request("GET", CONTROL_TABLE, params=f"?sync_name=eq.{SYNC_NAME}&select={SYNC_CONTROL_COLUMNS}")
    return rows[0] if rows else {}


def check_stop(run_id: str) -> None:
    control = get_control()
    if control.get("stop_requested") or control.get("is_paused"):
        message = "หยุดซิงก์ตามคำสั่งจากหน้าเว็บ"
        update_run(run_id, status="stopped", finished_at=now_iso(), error_message=message)
        update_control(
            current_run_id=None,
            last_status="stopped",
            last_message=message,
            last_finished_at=now_iso(),
        )
        raise SyncStopped(message)


def clean(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.upper() in {"NULL", "NONE", "NAN"} else text


def to_number(value: Any) -> float:
    text = clean(value).replace(",", "")
    if not text:
        return 0
    try:
        return float(text)
    except ValueError:
        return 0


def get(row: dict[str, Any], *names: str) -> str:
    for name in names:
        value = clean(row.get(name))
        if value:
            return value
    return ""


def make_date_text(row: dict[str, Any]) -> str:
    day = get(row, "วันที่")
    month = get(row, "เดือน")
    year = get(row, "ปี")
    return f"{day}/{month}/{year}" if day and month and year else ""


def build_products(row: dict[str, Any]) -> list[dict[str, Any]]:
    products = []
    for index in range(1, 7):
        sku = get(row, f"SKU ({index})")
        name = get(row, f"สินค้า ({index})")
        qty = to_number(row.get(f"จำนวน ({index})"))
        price = to_number(row.get(f"ราคา ({index})"))
        if not sku and not name:
            continue
        products.append(
            {
                "sku": sku,
                "name": name,
                "qty": int(qty) if qty == int(qty) else qty,
                "price": price,
            }
        )
    return products


def build_record(row: dict[str, Any], source: dict[str, str]) -> dict[str, Any] | None:
    order_id = get(row, "เลขคำสั่งซื้อ")
    if not order_id:
        return None

    return {
        "source_key": f"{source['year_file']}_{order_id}",
        "order_id": order_id,
        "year": get(row, "ปี") or source["year_file"],
        "month": get(row, "เดือน"),
        "day": get(row, "วันที่"),
        "date_text": make_date_text(row),
        "customer": get(row, "ลูกค้า"),
        "phone1": get(row, "เบอร์โทร (1)", "เบอร์โทร"),
        "phone2": get(row, "เบอร์โทร (2)", "เบอร์โทรสำรอง"),
        "address": get(row, "ที่อยู่จัดส่ง", "ที่อยู่"),
        "subdistrict": get(row, "ตำบล"),
        "district": get(row, "อำเภอ"),
        "province": get(row, "จังหวัด"),
        "postcode": get(row, "รหัสไปรษณีย์"),
        "channel": get(row, "ช่องทางขาย"),
        "sales_staff": get(row, "พนักงานเปิดบิล", "พนักงานขาย"),
        "upsell_staff": get(row, "พนักงานอัพเซลล์", "พนักงาน UPSELL", "พนักงาน Upsell"),
        "care_staff": get(row, "พนักงานดูแล"),
        "product_group": get(row, "หมวดสินค้า"),
        "total_sales": to_number(row.get("ยอดขายรวม")),
        "order_status": get(row, "สถานะคำสั่งซื้อ"),
        "payment_method": get(row, "วิธีการชำระเงิน"),
        "delivery_status": get(row, "สถานะจัดส่ง"),
        "shipping": get(row, "ขนส่ง"),
        "tracking_no": get(row, "หมายเลขพัสดุ"),
        "channel_url": get(row, "ช่องทาง URL", "URL"),
        "products": build_products(row),
        "note": get(row, "หมายเหตุ", "โน๊ต", "โน้ต"),
        "source_spreadsheet_id": source["sheet_id"],
        "source_sheet": source["worksheet"],
        "year_file": source["year_file"],
        "synced_at": now_iso(),
    }


def credentials_from_config() -> Credentials:
    scopes = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
    if GOOGLE_SERVICE_ACCOUNT_JSON:
        return Credentials.from_service_account_info(json.loads(GOOGLE_SERVICE_ACCOUNT_JSON), scopes=scopes)
    return Credentials.from_service_account_file(GOOGLE_SERVICE_ACCOUNT_FILE, scopes=scopes)


def read_sheet_rows(client: gspread.Client, source: dict[str, str]) -> list[dict[str, str]]:
    worksheet = client.open_by_key(source["sheet_id"]).worksheet(source["worksheet"])
    values = worksheet.get_all_values()
    if not values:
        return []

    headers = [clean(header) or f"EMPTY_{index}" for index, header in enumerate(values[0])]
    rows = []
    for raw_row in values[1:]:
        rows.append({header: raw_row[index] if index < len(raw_row) else "" for index, header in enumerate(headers)})
    return rows


def upsert_orders(records: list[dict[str, Any]]) -> None:
    if not records:
        return
    upsert_orders_chunk(records)


def upsert_orders_chunk(records: list[dict[str, Any]], attempt: int = 1) -> None:
    url = f"{SUPABASE_URL.rstrip('/')}/rest/v1/{ORDER_TABLE}?on_conflict=source_key"
    try:
        response = requests.post(
            url,
            headers=service_headers({"Prefer": "resolution=merge-duplicates"}),
            data=json.dumps(records, ensure_ascii=False),
            timeout=REQUEST_TIMEOUT,
        )
        if response.status_code < 300:
            return
        raise SupabaseUpsertError(response.status_code, response.text)
    except Exception as exc:
        if should_split_batch(records, exc):
            midpoint = len(records) // 2
            print(f"Upsert batch of {len(records):,} failed; splitting into {midpoint:,} + {len(records) - midpoint:,}")
            upsert_orders_chunk(records[:midpoint])
            upsert_orders_chunk(records[midpoint:])
            return

        if attempt < MAX_UPSERT_RETRIES and is_transient_error(exc):
            sleep_for = RETRY_SLEEP_SECONDS * attempt
            print(f"Transient upsert error on {len(records):,} records; retry {attempt + 1}/{MAX_UPSERT_RETRIES} in {sleep_for:.1f}s")
            time.sleep(sleep_for)
            upsert_orders_chunk(records, attempt + 1)
            return

        raise exc


def should_split_batch(records: list[dict[str, Any]], exc: Exception) -> bool:
    return len(records) > MIN_BATCH_SIZE and is_transient_error(exc)


def sync_source(
    run_id: str,
    client: gspread.Client,
    source: dict[str, str],
    counters: dict[str, int],
    detail: dict[str, Any],
) -> None:
    label = f"DATA {source['year_file']}"
    print(f"Loading {label}...")
    update_run(run_id, current_source=label)
    update_control(last_source=label, last_message=f"กำลังอ่าน {label}")
    check_stop(run_id)

    rows = read_sheet_rows(client, source)
    counters["rows_read"] += len(rows)
    source_detail = {"rows_read": len(rows), "records_built": 0, "records_upserted": 0, "skipped_rows": 0}
    print(f"{label}: {len(rows):,} rows")

    batch: list[dict[str, Any]] = []
    for row in rows:
        record = build_record(row, source)
        if not record:
            counters["skipped_rows"] += 1
            source_detail["skipped_rows"] += 1
            continue

        batch.append(record)
        counters["records_built"] += 1
        source_detail["records_built"] += 1

        if len(batch) >= BATCH_SIZE:
            check_stop(run_id)
            upsert_orders(batch)
            counters["records_upserted"] += len(batch)
            source_detail["records_upserted"] += len(batch)
            batch = []
            update_progress(run_id, counters, detail | {label: source_detail}, label)

    if batch:
        check_stop(run_id)
        upsert_orders(batch)
        counters["records_upserted"] += len(batch)
        source_detail["records_upserted"] += len(batch)

    detail[label] = source_detail
    update_progress(run_id, counters, detail, label)


def update_progress(run_id: str, counters: dict[str, int], detail: dict[str, Any], label: str) -> None:
    update_run(
        run_id,
        current_source=label,
        rows_read=counters["rows_read"],
        records_built=counters["records_built"],
        records_upserted=counters["records_upserted"],
        skipped_rows=counters["skipped_rows"],
        detail=detail,
    )
    update_control(
        last_source=label,
        last_rows_read=counters["rows_read"],
        last_records_upserted=counters["records_upserted"],
        last_message=f"ซิงก์แล้ว {counters['records_upserted']:,} รายการ",
    )


def main() -> int:
    require_config()
    existing_control = get_control()
    if existing_control.get("is_paused") or existing_control.get("stop_requested"):
        print("Sync is paused/stopped from dashboard.")
        return 0

    run_id = create_run()
    counters = {"rows_read": 0, "records_built": 0, "records_upserted": 0, "skipped_rows": 0}
    detail: dict[str, Any] = {}

    try:
        credentials = credentials_from_config()
        client = gspread.authorize(credentials)

        for source in DATA_SOURCES:
            sync_source(run_id, client, source, counters, detail)
            time.sleep(1)

        message = f"ซิงก์สำเร็จ {counters['records_upserted']:,} รายการ จาก {counters['rows_read']:,} แถว"
        update_run(run_id, status="success", finished_at=now_iso(), detail=detail, **counters)
        update_control(
            current_run_id=None,
            last_status="success",
            last_message=message,
            last_finished_at=now_iso(),
            last_rows_read=counters["rows_read"],
            last_records_upserted=counters["records_upserted"],
        )
        print(message)
        return 0
    except SyncStopped as exc:
        print(str(exc))
        return 0
    except Exception as exc:
        message = str(exc)
        update_run(run_id, status="failed", finished_at=now_iso(), error_message=message, detail=detail, **counters)
        update_control(
            current_run_id=None,
            last_status="failed",
            last_message=message[:500],
            last_finished_at=now_iso(),
            last_rows_read=counters["rows_read"],
            last_records_upserted=counters["records_upserted"],
        )
        print(message, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
