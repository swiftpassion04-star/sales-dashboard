from __future__ import annotations

from datetime import date, datetime, timedelta
from io import BytesIO

import pandas as pd
import streamlit as st

from neon_utils import fetch_customer_export_rows
from permissions import can_export_customers


EXPORT_PERIOD_OPTIONS = ["ทั้งหมด", "รายวัน", "รายเดือน", "กำหนดช่วงวันที่"]
CRM_EXPORT_HEADERS = [
    "วันที่สั่งซื้อ",
    "เลขคำสั่งซื้อ",
    "ช่องทางขาย",
    "SKU",
    "สินค้า",
    "จำนวน",
    "ราคา",
    "วิธีการชำระ",
    "ขนส่ง",
    "หมายเลขพัสดุ",
    "URL",
    "ชื่อลูกค้า",
    "เบอร์โทร",
    "เบอร์สำรอง",
    "ที่อยู่จัดส่ง",
    "ตำบล",
    "อำเภอ",
    "จังหวัด",
    "รหัสไปรษณีย์",
    "พนักงานเปิดบิล",
    "พนักงานอัพเซลล์",
    "พนักงานดูแล",
]


def render_customer_export_panel(
    filters: dict[str, str] | None,
    user: dict | None,
    *,
    form_key: str = "customer_xlsx_export",
    state_prefix: str = "customers_export",
) -> None:
    if not can_export_customers(user):
        return

    st.markdown("#### ดาวน์โหลดข้อมูลลูกค้า (.xlsx)")
    with st.form(form_key):
        period_col, date_col = st.columns([1, 2])
        period = period_col.selectbox("ช่วงข้อมูล", EXPORT_PERIOD_OPTIONS, key=f"{state_prefix}_period")
        start_date, end_date = resolve_export_dates(period, date_col, state_prefix)
        prepared = st.form_submit_button("เตรียมไฟล์ดาวน์โหลด", use_container_width=True)

    if prepared:
        try:
            rows = fetch_customer_export_rows(filters or {}, user, start_date=start_date, end_date=end_date)
            st.session_state[f"{state_prefix}_xlsx"] = build_customer_export_xlsx(rows)
            st.session_state[f"{state_prefix}_count"] = len(rows)
            st.session_state[f"{state_prefix}_name"] = build_export_filename(start_date, end_date)
        except Exception as exc:
            st.error(f"เตรียมไฟล์ดาวน์โหลดไม่สำเร็จ: {exc}")
            return

    xlsx_data = st.session_state.get(f"{state_prefix}_xlsx")
    if xlsx_data:
        count = int(st.session_state.get(f"{state_prefix}_count") or 0)
        file_name = clean(st.session_state.get(f"{state_prefix}_name")) or "crm_customers_export.xlsx"
        st.success(f"เตรียมไฟล์แล้ว {count:,} แถว")
        st.download_button(
            "ดาวน์โหลด .xlsx",
            data=xlsx_data,
            file_name=file_name,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            key=f"{state_prefix}_download_button",
        )


def resolve_export_dates(period: str, container, state_prefix: str) -> tuple[date | None, date | None]:
    today = date.today()
    if period == "ทั้งหมด":
        container.info("ดาวน์โหลดข้อมูลทั้งหมดตามตัวกรองปัจจุบัน")
        return None, None
    if period == "รายวัน":
        selected = container.date_input("เลือกวันที่สร้าง", value=today, key=f"{state_prefix}_day")
        return selected, selected
    if period == "รายเดือน":
        selected = container.date_input("เลือกเดือน", value=today.replace(day=1), key=f"{state_prefix}_month")
        start = selected.replace(day=1)
        next_month = start.replace(year=start.year + 1, month=1) if start.month == 12 else start.replace(month=start.month + 1)
        return start, next_month - timedelta(days=1)

    selected_range = container.date_input(
        "เลือกช่วงวันที่สร้าง",
        value=(today, today),
        key=f"{state_prefix}_range",
    )
    if isinstance(selected_range, tuple) and len(selected_range) == 2:
        start, end = selected_range
        return start, end
    return today, today


def build_export_filename(start_date: date | None, end_date: date | None) -> str:
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    if start_date and end_date:
        return f"crm_customers_{start_date:%Y%m%d}_{end_date:%Y%m%d}_{stamp}.xlsx"
    return f"crm_customers_all_{stamp}.xlsx"


def build_customer_export_xlsx(rows: list[dict]) -> bytes:
    table = [customer_export_row(row) for row in rows]
    df = pd.DataFrame(table, columns=CRM_EXPORT_HEADERS)
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="customers")
    return buffer.getvalue()


def customer_export_row(row: dict) -> dict:
    raw = row.get("raw_data") or {}
    if not isinstance(raw, dict):
        raw = {}

    def pick(field: str, *raw_keys: str) -> str:
        value = clean(row.get(field))
        if value:
            return value
        for key in raw_keys:
            value = clean(raw.get(key))
            if value:
                return value
        return ""

    price = pick("amount", "ราคา", "ยอดขาย", "ยอดขายรวม")
    if not price:
        price = pick("total_amount", "ราคา", "ยอดขาย", "ยอดขายรวม")

    return {
        "วันที่สั่งซื้อ": pick("order_date", "วันที่สั่งซื้อ", "วันที่"),
        "เลขคำสั่งซื้อ": pick("order_id", "เลขคำสั่งซื้อ", "เลขออเดอร์"),
        "ช่องทางขาย": pick("sales_channel", "ช่องทางขาย", "ช่องทาง"),
        "SKU": pick("sku", "SKU"),
        "สินค้า": pick("product_name", "สินค้า", "ชื่อสินค้า"),
        "จำนวน": pick("quantity", "จำนวน", "qty"),
        "ราคา": price,
        "วิธีการชำระ": pick("payment_method", "วิธีการชำระ", "วิธีชำระ"),
        "ขนส่ง": pick("carrier", "ขนส่ง", "บริษัทขนส่ง"),
        "หมายเลขพัสดุ": pick("tracking_no", "หมายเลขพัสดุ", "เลขพัสดุ"),
        "URL": pick("url", "URL", "ลิงก์"),
        "ชื่อลูกค้า": pick("customer_name", "ชื่อลูกค้า", "ลูกค้า"),
        "เบอร์โทร": pick("phone1", "เบอร์โทร", "เบอร์โทรติดต่อ"),
        "เบอร์สำรอง": pick("phone2", "เบอร์สำรอง", "เบอร์โทรสำรอง"),
        "ที่อยู่จัดส่ง": pick("address", "ที่อยู่จัดส่ง", "ที่อยู่"),
        "ตำบล": pick("subdistrict", "ตำบล", "แขวง"),
        "อำเภอ": pick("city", "อำเภอ", "เขต", "เมือง"),
        "จังหวัด": pick("province", "จังหวัด"),
        "รหัสไปรษณีย์": pick("postal_code", "รหัสไปรษณีย์", "postcode"),
        "พนักงานเปิดบิล": pick("billing_staff", "พนักงานเปิดบิล", "ผู้ขาย"),
        "พนักงานอัพเซลล์": pick("upsell_staff", "พนักงานอัพเซลล์", "พนักงาน UPSELL"),
        "พนักงานดูแล": pick("owner", "พนักงานดูแล", "ผู้ดูแล"),
    }


def clean(value) -> str:
    return str(value or "").strip()
