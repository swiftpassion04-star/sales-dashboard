import json
import gspread
from google.oauth2.service_account import Credentials
from supabase import create_client

# =========================
# SUPABASE
# ใช้ service_role key เฉพาะไฟล์ sync นี้เท่านั้น
# ห้ามเอา key นี้ไปใส่ app.py
# =========================
SUPABASE_URL = "https://zctqbrlqtomopsblazwq.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InpjdHFicmxxdG9tb3BzYmxhendxIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3ODIzMjM5MywiZXhwIjoyMDkzODA4MzkzfQ.YK8p4mqBY-FDSyvVJUZqDJwFMYQqc1OOwjXKg7CYfJM"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# =========================
# CONFIG หลายไฟล์ / หลายปี
# =========================
DATA_SOURCES = [
    {
        "year_file": "2022",
        "sheet_id": "1Q9CyZi5ezvthVABg-aw6LvrYtSp7qRHiEr4pVMGMKHg",
        "worksheet": "DATA_RAW"
    },

    {
        "year_file": "2023",
        "sheet_id": "1Up4Vnx5fjxQMl6oEgFEpaJV9D8s4_pnEpIi0OS4LD08",
        "worksheet": "DATA_RAW"
    },

    {
        "year_file": "2024",
        "sheet_id": "1U2CJ0HIcANRYNSlMSOun5_2RT4ElVFzoMaQMhZ4XD7s",
        "worksheet": "DATA_RAW"
    }
]

BATCH_SIZE = 500

# =========================
# HELPERS
# =========================
def clean_text(value):
    if value is None:
        return ""
    text = str(value).strip()
    if text.upper() in ["NULL", "NONE", "NAN"]:
        return ""
    return text


def to_float(value):
    try:
        text = clean_text(value).replace(",", "")
        if text == "":
            return 0
        return float(text)
    except:
        return 0


def make_date_text(row):
    day = clean_text(row.get("วัน", ""))
    month = clean_text(row.get("เดือน", ""))
    year = clean_text(row.get("ปี", ""))

    if day and month and year:
        return f"{day}/{month}/{year}"
    return ""


def build_products(row):
    products = []
    total_sales = to_float(row.get("ยอดขายรวม", 0))

    for i in range(1, 7):
        product_name = clean_text(row.get(f"สินค้า ({i})", ""))
        qty = to_float(row.get(f"จำนวน ({i})", 0))

        if product_name:
            products.append({
                "name": product_name,
                "qty": int(qty) if qty == int(qty) else qty,
                "sales": total_sales if i == 1 else 0
            })

    return products


def read_sheet_rows(client, sheet_id, worksheet_name):
    sheet = client.open_by_key(sheet_id).worksheet(worksheet_name)
    values = sheet.get_all_values()

    if not values:
        return []

    headers = [
        h.strip() if h.strip() else f"EMPTY_{i}"
        for i, h in enumerate(values[0])
    ]

    rows = []

    for row in values[1:]:
        row_dict = {}
        for i, h in enumerate(headers):
            row_dict[h] = row[i] if i < len(row) else ""
        rows.append(row_dict)

    return rows


# =========================
# GOOGLE SHEETS AUTH
# =========================
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

creds = Credentials.from_service_account_file(
    "service_account.json",
    scopes=scope
)

client = gspread.authorize(creds)

# =========================
# SYNC
# =========================
def get_existing_order_ids():
    existing = set()
    limit = 1000
    offset = 0

    while True:
        res = (
            supabase.table("orders")
            .select("order_id")
            .range(offset, offset + limit - 1)
            .execute()
        )

        data = res.data or []
        if not data:
            break

        for item in data:
            oid = clean_text(item.get("order_id", ""))
            if oid:
                existing.add(oid)

        if len(data) < limit:
            break

        offset += limit

    return existing
print("กำลังโหลดเลขออเดอร์เดิมจาก Supabase...")
existing_order_ids = get_existing_order_ids()
print(f"พบออเดอร์เดิมในฐานข้อมูล {len(existing_order_ids)} รายการ")
grand_total = 0
grand_success = 0
grand_skip = 0

for source in DATA_SOURCES:

    year_file = source["year_file"]
    sheet_id = source["sheet_id"]
    worksheet_name = source["worksheet"]

    if "ใส่ SHEET ID" in sheet_id:
        print(f"ข้ามปี {year_file}: ยังไม่ได้ใส่ SHEET ID")
        continue

    print("=" * 50)
    print(f"เริ่ม Sync ปี {year_file} | Sheet: {worksheet_name}")

    rows = read_sheet_rows(client, sheet_id, worksheet_name)

    print(f"โหลดข้อมูล {len(rows)} รายการ")

    grand_total += len(rows)

    for i in range(0, len(rows), BATCH_SIZE):

        batch = rows[i:i + BATCH_SIZE]
        records = []

        batch_order_ids = set()
        for row in batch:

            order_id = clean_text(row.get("เลขคำสั่งซื้อ", ""))

            if not order_id:
                grand_skip += 1
                continue

            if order_id in existing_order_ids:
                grand_skip += 1
                continue

            if order_id in batch_order_ids:
                grand_skip += 1
                continue

            batch_order_ids.add(order_id)

            # ป้องกัน order_id ซ้ำข้ามปี โดยใส่ year_file นำหน้าใน source_key
            # แต่ยังเก็บ order_id เดิมไว้ให้เว็บใช้
            source_key = f"{year_file}_{order_id}"

            products = build_products(row)

            record = {
                "source_key": source_key,
                "order_id": order_id,

                "year": clean_text(row.get("ปี", "")) or year_file,
                "month": clean_text(row.get("เดือน", "")),
                "day": clean_text(row.get("วัน", "")),
                "date_text": make_date_text(row),

                "customer": clean_text(row.get("ลูกค้า", "")),
                "phone1": clean_text(row.get("เบอร์โทร (1)", "")),
                "phone2": clean_text(row.get("เบอร์โทร (2)", "")),

                "address": clean_text(row.get("ที่อยู่จัดส่ง", "")),
                "subdistrict": clean_text(row.get("ตำบล", "")),
                "district": clean_text(row.get("อำเภอ", "")),
                "province": clean_text(row.get("จังหวัด", "")),
                "postcode": clean_text(row.get("รหัสไปรษณีย์", "")),

                "shipping": clean_text(row.get("ขนส่ง", "")),
                "tracking_no": clean_text(row.get("หมายเลขพัสดุ", "")),

                "channel": clean_text(row.get("ช่องทางขาย", "")) or clean_text(row.get("ช่องทาง", "")),

                "sales_staff": clean_text(row.get("พนักงานเปิดบิล", "")) or clean_text(row.get("พนักงานขาย", "")),
                "upsell_staff": clean_text(row.get("พนักงาน Upsell", "")),

                "total_sales": to_float(row.get("ยอดขายรวม", 0)),

                "products": json.dumps(products, ensure_ascii=False),

                "source_sheet": worksheet_name,
                "year_file": year_file
            }

            records.append(record)

        if records:
            supabase.table("orders").insert(records).execute()

            for r in records:
                existing_order_ids.add(r["order_id"])

            grand_success += len(records)

        print(f"ปี {year_file}: Sync แล้ว {min(i + BATCH_SIZE, len(rows))} / {len(rows)} รายการ")

print("=" * 50)
print("IMPORT เสร็จสมบูรณ์")
print(f"โหลดรวม: {grand_total} รายการ")
print(f"เพิ่มสำเร็จ: {grand_success} รายการ")
print(f"ข้ามแถวว่าง: {grand_skip} รายการ")