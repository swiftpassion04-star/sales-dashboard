import json
import os
from typing import Any

import gspread
import requests
from google.oauth2.service_account import Credentials


SUPABASE_URL = os.environ.get("CRM_SUPABASE_URL") or os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.environ.get("CRM_SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_SERVICE_KEY")
GOOGLE_SERVICE_ACCOUNT_FILE = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "service_account.json")
SUPABASE_TABLE = "order_history"
BATCH_SIZE = 500

DATA_SOURCES = [
    {
        "year_file": "2022",
        "sheet_id": "1Q9CyZi5ezvthVABg-aw6LvrYtSp7qRHiEr4pVMGMKHg",
        "worksheet": "DATA_RAW",
    },
    {
        "year_file": "2023",
        "sheet_id": "1Up4Vnx5fjxQMl6oEgFEpaJV9D8s4_pnEpIi0OS4LD08",
        "worksheet": "DATA_RAW",
    },
    {
        "year_file": "2024",
        "sheet_id": "1U2CJ0HIcANRYNSlMSOun5_2RT4ElVFzoMaQMhZ4XD7s",
        "worksheet": "DATA_RAW",
    },
]


def require_config() -> None:
    missing = []
    if not SUPABASE_URL:
        missing.append("CRM_SUPABASE_URL")
    if not SUPABASE_SERVICE_KEY:
        missing.append("CRM_SUPABASE_SERVICE_KEY")
    if not os.path.exists(GOOGLE_SERVICE_ACCOUNT_FILE):
        missing.append(f"Google service account file: {GOOGLE_SERVICE_ACCOUNT_FILE}")
    if missing:
        raise RuntimeError("Missing config: " + ", ".join(missing))


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


def read_sheet_rows(client: gspread.Client, sheet_id: str, worksheet_name: str) -> list[dict[str, str]]:
    worksheet = client.open_by_key(sheet_id).worksheet(worksheet_name)
    values = worksheet.get_all_values()
    if not values:
        return []

    headers = [header.strip() if header.strip() else f"EMPTY_{index}" for index, header in enumerate(values[0])]
    rows = []
    for raw_row in values[1:]:
        rows.append({header: raw_row[index] if index < len(raw_row) else "" for index, header in enumerate(headers)})
    return rows


def build_record(row: dict[str, Any], source: dict[str, str]) -> dict[str, Any] | None:
    order_id = get(row, "เลขคำสั่งซื้อ")
    if not order_id:
        return None

    products = build_products(row)
    return {
        "source_key": f"{source['year_file']}_{order_id}",
        "order_id": order_id,
        "year": get(row, "ปี") or source["year_file"],
        "month": get(row, "เดือน"),
        "day": get(row, "วันที่"),
        "date_text": make_date_text(row),
        "customer": get(row, "ลูกค้า"),
        "phone1": get(row, "เบอร์โทร (1)"),
        "phone2": get(row, "เบอร์โทร (2)"),
        "address": get(row, "ที่อยู่จัดส่ง"),
        "subdistrict": get(row, "ตำบล"),
        "district": get(row, "อำเภอ"),
        "province": get(row, "จังหวัด"),
        "postcode": get(row, "รหัสไปรษณีย์"),
        "channel": get(row, "ช่องทางขาย"),
        "sales_staff": get(row, "พนักงานเปิดบิล", "พนักงานขาย"),
        "upsell_staff": get(row, "พนักงานอัพเซลล์", "พนักงาน Upsell"),
        "care_staff": get(row, "พนักงานดูแล"),
        "product_group": get(row, "หมวดสินค้า"),
        "total_sales": to_number(row.get("ยอดขายรวม")),
        "order_status": get(row, "สถานะคำสั่งซื้อ"),
        "payment_method": get(row, "วิธีการชำระเงิน"),
        "delivery_status": get(row, "สถานะจัดส่ง"),
        "shipping": get(row, "ขนส่ง"),
        "tracking_no": get(row, "หมายเลขพัสดุ"),
        "channel_url": get(row, "ช่องทาง URL"),
        "products": products,
        "note": get(row, "หมายเหตุ"),
        "source_spreadsheet_id": source["sheet_id"],
        "source_sheet": source["worksheet"],
        "year_file": source["year_file"],
    }


def supabase_upsert(records: list[dict[str, Any]]) -> None:
    if not records:
        return

    url = f"{SUPABASE_URL.rstrip('/')}/rest/v1/{SUPABASE_TABLE}?on_conflict=source_key"
    response = requests.post(
        url,
        headers={
            "apikey": SUPABASE_SERVICE_KEY,
            "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates",
        },
        data=json.dumps(records, ensure_ascii=False),
        timeout=120,
    )
    if response.status_code >= 300:
        raise RuntimeError(f"Supabase upsert failed: {response.status_code} {response.text}")


def main() -> None:
    require_config()
    scopes = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
    credentials = Credentials.from_service_account_file(GOOGLE_SERVICE_ACCOUNT_FILE, scopes=scopes)
    client = gspread.authorize(credentials)

    total_rows = 0
    total_records = 0
    for source in DATA_SOURCES:
        print(f"Loading {source['year_file']} {source['worksheet']}...")
        rows = read_sheet_rows(client, source["sheet_id"], source["worksheet"])
        total_rows += len(rows)
        print(f"Rows: {len(rows):,}")

        batch = []
        for row in rows:
            record = build_record(row, source)
            if not record:
                continue
            batch.append(record)
            if len(batch) >= BATCH_SIZE:
                supabase_upsert(batch)
                total_records += len(batch)
                print(f"Upserted {total_records:,} records...")
                batch = []

        if batch:
            supabase_upsert(batch)
            total_records += len(batch)
            print(f"Upserted {total_records:,} records...")

    print(f"Done. Read {total_rows:,} rows, upserted {total_records:,} records.")


if __name__ == "__main__":
    main()
