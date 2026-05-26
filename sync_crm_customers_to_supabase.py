import json
import os
import sys
from datetime import datetime, timezone
from typing import Any

import gspread
import requests
from google.oauth2.service_account import Credentials


SUPABASE_URL = os.environ.get("CRM_SUPABASE_URL") or os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.environ.get("CRM_SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_SERVICE_KEY")
GOOGLE_SERVICE_ACCOUNT_FILE = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "service_account.json")
GOOGLE_SERVICE_ACCOUNT_JSON = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
CRM_MANAGER_SHEETS_JSON = os.environ.get("CRM_MANAGER_SHEETS_JSON", "")

CUSTOMERS_TABLE = "crm_customers"
BATCH_SIZE = int(os.environ.get("CRM_CUSTOMERS_BATCH_SIZE", "250"))
REQUEST_TIMEOUT = 120


def require_config() -> None:
    missing = []
    if not SUPABASE_URL:
        missing.append("CRM_SUPABASE_URL")
    if not SUPABASE_SERVICE_KEY:
        missing.append("CRM_SUPABASE_SERVICE_KEY")
    if not GOOGLE_SERVICE_ACCOUNT_JSON and not os.path.exists(GOOGLE_SERVICE_ACCOUNT_FILE):
        missing.append("GOOGLE_SERVICE_ACCOUNT_JSON or service_account.json")
    if not CRM_MANAGER_SHEETS_JSON:
        missing.append("CRM_MANAGER_SHEETS_JSON")
    if missing:
        raise RuntimeError("Missing config: " + ", ".join(missing))


def load_sources() -> list[dict[str, str]]:
    try:
        sources = json.loads(CRM_MANAGER_SHEETS_JSON)
    except json.JSONDecodeError as exc:
        raise RuntimeError("CRM_MANAGER_SHEETS_JSON is not valid JSON") from exc
    if not isinstance(sources, list) or not sources:
        raise RuntimeError("CRM_MANAGER_SHEETS_JSON must be a non-empty JSON array")

    normalized = []
    for index, source in enumerate(sources, start=1):
        if not isinstance(source, dict):
            raise RuntimeError(f"CRM manager sheet source #{index} must be an object")
        sheet_id = clean(source.get("sheet_id"))
        if not sheet_id:
            raise RuntimeError(f"CRM manager sheet source #{index} is missing sheet_id")
        normalized.append(
            {
                "label": clean(source.get("label")) or clean(source.get("product_group")) or f"source_{index}",
                "sheet_id": sheet_id,
                "worksheet": clean(source.get("worksheet")) or "CRM",
                "product_group": clean(source.get("product_group")),
            }
        )
    return normalized


def credentials_from_config() -> Credentials:
    scopes = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
    if GOOGLE_SERVICE_ACCOUNT_JSON:
        return Credentials.from_service_account_info(json.loads(GOOGLE_SERVICE_ACCOUNT_JSON), scopes=scopes)
    return Credentials.from_service_account_file(GOOGLE_SERVICE_ACCOUNT_FILE, scopes=scopes)


def service_headers(extra: dict[str, str] | None = None) -> dict[str, str]:
    headers = {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json",
    }
    if extra:
        headers.update(extra)
    return headers


def read_sheet_rows(client: gspread.Client, source: dict[str, str]) -> list[dict[str, Any]]:
    worksheet = client.open_by_key(source["sheet_id"]).worksheet(source["worksheet"])
    values = worksheet.get_all_values()
    if not values:
        return []

    headers = [clean(header) or f"EMPTY_{index}" for index, header in enumerate(values[0])]
    rows = []
    for row_number, raw_row in enumerate(values[1:], start=2):
        row = {
            "source_row_number": row_number,
            "_raw_values": raw_row,
        }
        for index, header in enumerate(headers):
            row[header] = raw_row[index] if index < len(raw_row) else ""
        rows.append(row)
    return rows


def build_record(row: dict[str, Any], source: dict[str, str]) -> dict[str, Any] | None:
    raw_values = row.get("_raw_values") or []
    row_number = int(row.get("source_row_number") or 0)
    customer = get(row, "ชื่อลูกค้า", "ลูกค้า", "customer", "customer_name")
    phone1 = get(row, "เบอร์โทรติดต่อ", "เบอร์โทร (1)", "เบอร์โทร", "phone1")
    phone2 = get(row, "เบอร์โทรสำรอง", "เบอร์โทร (2)", "phone2")
    product_name = get(row, "สินค้า", "product_name", "product")
    product_group = source["product_group"] or get(row, "กลุ่มสินค้า", "หมวดสินค้า", "product_group")

    if not any([customer, phone1, phone2, product_name]):
        return None

    customer_id = f"{source['label']}:{source['sheet_id']}:{source['worksheet']}:{row_number}"
    return {
        "customer_id": customer_id,
        "source_spreadsheet_id": source["sheet_id"],
        "source_sheet": source["worksheet"],
        "customer": customer,
        "product_group": product_group or source["label"],
        "product_name": product_name,
        "phone1": phone1,
        "phone2": phone2,
        "note": get(row, "โน๊ต", "โน้ต", "หมายเหตุ", "note"),
        "sales_staff": get(row, "ผู้ดูแล", "พนักงานดูแล", "sales_staff", "owner"),
        "product_url": get(row, "URL", "url", "ลิงก์", "link", "product_url"),
        "call_1": get_by_header_or_index(row, raw_values, ["H", "call_1", "check_h"], 7),
        "call_2": get_by_header_or_index(row, raw_values, ["J", "call_2", "check_j"], 9),
        "call_3": get_by_header_or_index(row, raw_values, ["L", "call_3", "check_l"], 11),
        "row_hash": make_row_hash(row),
        "synced_at": now_iso(),
        "updated_at": now_iso(),
    }


def upsert_records(records: list[dict[str, Any]]) -> None:
    if not records:
        return
    url = f"{SUPABASE_URL.rstrip('/')}/rest/v1/{CUSTOMERS_TABLE}?on_conflict=customer_id"
    response = requests.post(
        url,
        headers=service_headers({"Prefer": "resolution=merge-duplicates"}),
        data=json.dumps(records, ensure_ascii=False),
        timeout=REQUEST_TIMEOUT,
    )
    if response.status_code >= 300:
        raise RuntimeError(f"Supabase upsert failed: {response.status_code} {response.text}")


def sync_source(client: gspread.Client, source: dict[str, str]) -> tuple[int, int]:
    rows = read_sheet_rows(client, source)
    built = []
    for row in rows:
        record = build_record(row, source)
        if record:
            built.append(record)

    for index in range(0, len(built), BATCH_SIZE):
        upsert_records(built[index : index + BATCH_SIZE])
    return len(rows), len(built)


def get(row: dict[str, Any], *names: str) -> str:
    for name in names:
        value = clean(row.get(name))
        if value:
            return value
    return ""


def get_by_header_or_index(row: dict[str, Any], raw_values: list[str], names: list[str], zero_based_index: int) -> str:
    for name in names:
        value = clean(row.get(name))
        if value:
            return value
    if zero_based_index < len(raw_values):
        return clean(raw_values[zero_based_index])
    return ""


def is_checked(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value == 1
    text = clean(value).lower()
    return text in {"true", "yes", "y", "1", "checked", "ติ๊ก", "ติ้ก", "ถูก"}


def make_row_hash(row: dict[str, Any]) -> str:
    raw_values = row.get("_raw_values") or []
    return json.dumps(raw_values, ensure_ascii=False, separators=(",", ":"))


def clean(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.upper() in {"NULL", "NONE", "NAN"} else text


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def main() -> int:
    require_config()
    sources = load_sources()
    client = gspread.authorize(credentials_from_config())

    total_rows = 0
    total_records = 0
    for source in sources:
        rows_read, records_built = sync_source(client, source)
        total_rows += rows_read
        total_records += records_built
        print(f"{source['label']}: read {rows_read:,} rows, upserted {records_built:,} records")

    print(f"CRM customers sync complete: read {total_rows:,} rows, upserted {total_records:,} records")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
