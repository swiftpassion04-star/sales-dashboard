import gspread
from google.oauth2.service_account import Credentials
from supabase import create_client

# =========================
# SUPABASE
# =========================
SUPABASE_URL = "https://zctqbrlqtomopsblazwq.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InpjdHFicmxxdG9tb3BzYmxhendxIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3ODIzMjM5MywiZXhwIjoyMDkzODA4MzkzfQ.YK8p4mqBY-FDSyvVJUZqDJwFMYQqc1OOwjXKg7CYfJM"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# =========================
# CONFIG
# =========================
SHEET_ID = "1Q9CyZi5ezvthVABg-aw6LvrYtSp7qRHiEr4pVMGMKHg"
WORKSHEET_NAME = "DATA_RAW"
BATCH_SIZE = 500

# =========================
# HELPERS
# =========================
def clean_text(value):
    if value is None:
        return ""
    return str(value).strip()

def to_float(value):
    try:
        if value is None or value == "":
            return 0
        return float(str(value).replace(",", "").strip())
    except:
        return 0

def make_date_text(row):
    day = clean_text(row.get("วัน", ""))
    month = clean_text(row.get("เดือน", ""))
    year = clean_text(row.get("ปี", ""))

    if day and month and year:
        return f"{day}/{month}/{year}"
    return ""

# =========================
# GOOGLE SHEETS
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
sheet = client.open_by_key(SHEET_ID).worksheet(WORKSHEET_NAME)

values = sheet.get_all_values()

if not values:
    raise Exception("ไม่พบข้อมูลในชีท")

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

print(f"โหลดข้อมูล {len(rows)} รายการ")

# =========================
# INSERT
# =========================
for i in range(0, len(rows), BATCH_SIZE):

    batch = rows[i:i + BATCH_SIZE]
    records = []

    for row in batch:

        order_id = clean_text(row.get("เลขคำสั่งซื้อ", ""))

        # กันแถวว่าง / กัน order_id ว่าง
        if not order_id:
            continue

        record = {
            "order_id": order_id,
            "year": clean_text(row.get("ปี", "")),
            "month": clean_text(row.get("เดือน", "")),
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

            "source_sheet": WORKSHEET_NAME
        }

        records.append(record)

    if records:
        supabase.table("orders").upsert(records, on_conflict="order_id").execute()

    print(f"เพิ่มแล้ว {min(i + BATCH_SIZE, len(rows))} / {len(rows)} รายการ")

print("IMPORT เสร็จสมบูรณ์")