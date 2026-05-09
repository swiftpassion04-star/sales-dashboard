import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from supabase import create_client
import streamlit as st

# =========================
# SUPABASE
# =========================
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# =========================
# GOOGLE SHEETS
# =========================
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

creds = ServiceAccountCredentials.from_json_keyfile_name(
    "service_account.json",
    scope
)

client = gspread.authorize(creds)

# =========================
# GOOGLE SHEET ID
# =========================
SHEET_ID = "1Q9CyZi5ezvthVABg-aw6LvrYtSp7qRHiEr4pVMGMKHg"

sheet = client.open_by_key(SHEET_ID).worksheet("DATA_RAW")

rows = sheet.get_all_records()

print(f"โหลดข้อมูล {len(rows)} รายการ")

# =========================
# CLEAR OLD DATA
# =========================
supabase.table("orders").delete().neq("id", 0).execute()

# =========================
# INSERT
# =========================
batch_size = 500

for i in range(0, len(rows), batch_size):

    batch = rows[i:i+batch_size]

    records = []

    for row in batch:

        record = {

            "date_text": f"{row.get('วัน', '')}/{row.get('เดือน', '')}/{row.get('ปี', '')}",

            "customer": row.get("ลูกค้า", ""),

            "phone1": row.get("เบอร์โทร (1)", ""),
            "phone2": row.get("เบอร์โทร (2)", ""),

            "address": row.get("ที่อยู่จัดส่ง", ""),

            "subdistrict": row.get("ตำบล", ""),
            "district": row.get("อำเภอ", ""),
            "province": row.get("จังหวัด", ""),
            "postcode": row.get("รหัสไปรษณีย์", ""),

            "shipping": row.get("ขนส่ง", ""),
            "tracking_no": row.get("หมายเลขพัสดุ", ""),

            "channel": row.get("ช่องทาง", ""),

            "sales_staff": row.get("พนักงานเปิดบิล", ""),
            "upsell_staff": row.get("พนักงาน Upsell", ""),

            "total_sales": row.get("ยอดขายรวม", 0),

            "source_sheet": "DATA_RAW"
        }

        records.append(record)

    supabase.table("orders").insert(records).execute()

    print(f"เพิ่มแล้ว {i + len(batch)} รายการ")

print("IMPORT เสร็จสมบูรณ์")