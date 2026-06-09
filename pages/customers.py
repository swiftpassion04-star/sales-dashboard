from datetime import date, datetime, timedelta
import html
from io import BytesIO

import pandas as pd
import streamlit as st

from auth_utils import ROLE_EDITOR, current_user, require_login
from crm_theme import badge, render_page_header
from nav_utils import render_sidebar_nav
from neon_utils import (
    assign_owner_to_order_record,
    assign_url_to_phones,
    fetch_customer_export_rows,
    fetch_customer_page,
    fetch_filter_options,
    fetch_orders_by_phones,
    fetch_owner_user_options,
    normalize_phone,
    upsert_lead_followup,
)


PAGE_SIZE_OPTIONS = [10, 25, 50, 100]
ALL = "ทั้งหมด"
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

st.set_page_config(page_title="Customers", layout="wide")


def main() -> None:
    render_sidebar_nav()
    require_login()
    user = current_user() or {}
    render_page_header("ลูกค้า", "ค้นหาและดูข้อมูลลูกค้าจาก Neon แบบ server-side")

    filters = render_filters(user)
    render_export_panel(filters, user)
    page_size = st.selectbox("จำนวนแถวต่อหน้า", PAGE_SIZE_OPTIONS, index=0, key="customers_page_size")
    page = int(st.number_input("หน้า", min_value=1, value=int(st.session_state.get("customers_page", 1)), step=1))
    st.session_state.customers_page = page

    with st.spinner("กำลังโหลดข้อมูลลูกค้า..."):
        rows, total = fetch_customer_page(filters, page_size, page, user, enforce_user_scope=False)

    c1, c2, c3 = st.columns(3)
    c1.metric("ลูกค้าทั้งหมด", f"{total:,}")
    c2.metric("แถวที่แสดง", f"{len(rows):,}")
    c3.metric("หน้า", f"{page:,}")

    if not rows:
        st.info("ไม่พบข้อมูลตามเงื่อนไขที่ค้นหา")
        return
    render_customer_table(rows, user)


def render_filters(user: dict) -> dict[str, str]:
    try:
        options = fetch_filter_options()
    except Exception:
        options = {"owners": []}
    with st.form("customer_filters"):
        col1, col2 = st.columns([1, 2])
        staff = col1.selectbox("ผู้ดูแล", [ALL] + options.get("owners", []))
        keyword = col2.text_input("ค้นหา", placeholder="ชื่อ / เบอร์ / รหัสไปรษณีย์ / เลขคำสั่งซื้อ")
        submitted = st.form_submit_button("ค้นหา", use_container_width=True)
    if submitted:
        st.session_state.customers_page = 1
    return {"staff": staff, "keyword": keyword}


def render_export_panel(filters: dict[str, str], user: dict) -> None:
    if clean(user.get("role")) != ROLE_EDITOR:
        return

    st.markdown("#### ดาวน์โหลดข้อมูลลูกค้า (.xlsx)")
    with st.form("customer_xlsx_export"):
        period_col, date_col = st.columns([1, 2])
        period = period_col.selectbox("ช่วงข้อมูล", EXPORT_PERIOD_OPTIONS, key="customers_export_period")
        start_date, end_date = resolve_export_dates(period, date_col)
        prepared = st.form_submit_button("เตรียมไฟล์ดาวน์โหลด", use_container_width=True)

    if prepared:
        try:
            rows = fetch_customer_export_rows(filters, user, start_date=start_date, end_date=end_date)
            st.session_state.customers_export_xlsx = build_customer_export_xlsx(rows)
            st.session_state.customers_export_count = len(rows)
            st.session_state.customers_export_name = build_export_filename(start_date, end_date)
        except Exception as exc:
            st.error(f"เตรียมไฟล์ดาวน์โหลดไม่สำเร็จ: {exc}")
            return

    xlsx_data = st.session_state.get("customers_export_xlsx")
    if xlsx_data:
        count = int(st.session_state.get("customers_export_count") or 0)
        file_name = clean(st.session_state.get("customers_export_name")) or "crm_customers_export.xlsx"
        st.success(f"เตรียมไฟล์แล้ว {count:,} แถว")
        st.download_button(
            "ดาวน์โหลด .xlsx",
            data=xlsx_data,
            file_name=file_name,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )


def resolve_export_dates(period: str, container) -> tuple[date | None, date | None]:
    today = date.today()
    if period == "ทั้งหมด":
        container.info("ดาวน์โหลดข้อมูลทั้งหมดตามตัวกรองปัจจุบัน")
        return None, None
    if period == "รายวัน":
        selected = container.date_input("เลือกวันที่สร้าง", value=today, key="customers_export_day")
        return selected, selected
    if period == "รายเดือน":
        selected = container.date_input("เลือกเดือน", value=today.replace(day=1), key="customers_export_month")
        start = selected.replace(day=1)
        next_month = start.replace(year=start.year + 1, month=1) if start.month == 12 else start.replace(month=start.month + 1)
        return start, next_month - timedelta(days=1)

    selected_range = container.date_input(
        "เลือกช่วงวันที่สร้าง",
        value=(today, today),
        key="customers_export_range",
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


def render_customer_table(rows: list[dict], user: dict) -> None:
    can_assign_owner = clean(user.get("role")) == ROLE_EDITOR
    owner_options = []
    if can_assign_owner:
        try:
            owner_options = unique_names(fetch_owner_user_options(active_only=True))
        except Exception:
            owner_options = []
    selected_id = clean(st.session_state.get("customers_selected_id"))
    st.markdown('<div class="crm-table-header-soft">', unsafe_allow_html=True)
    header_cols = st.columns([0.75, 1.35, 1, 1.35, 1, 1, 0.8])
    for col, label in zip(header_cols, ["ประวัติ", "ชื่อลูกค้า", "เบอร์โทร", "สินค้า", "ผู้ดูแล", "ติดตาม", "URL"]):
        col.markdown(f"**{label}**")
    st.markdown("</div>", unsafe_allow_html=True)
    for row in rows:
        record_id = clean(row.get("id"))
        url = clean(row.get("product_url"))
        cols = st.columns([0.75, 1.35, 1, 1.35, 1, 1, 0.8])
        cols[0].button(
            "ดูประวัติ",
            key=f"open_customer_history_{record_id}",
            use_container_width=False,
            on_click=select_customer_row,
            args=(record_id,),
        )
        cols[1].write(clean(row.get("customer")) or "-")
        cols[2].write(clean(row.get("phone1")) or clean(row.get("phone2")) or "-")
        cols[3].write(clean(row.get("product_name")) or "-")
        cols[4].write(clean(row.get("sales_staff")) or "-")
        cols[5].write(follow_marker_display(row.get("followup_status")))
        if url:
            cols[6].markdown(f"[เปิดลิงก์]({url})")
        else:
            cols[6].write("-")
        if selected_id == record_id:
            render_customer_detail(row, owner_options, user, can_assign_owner)


def select_customer_row(next_id: str) -> None:
    current_id = clean(st.session_state.get("customers_selected_id"))
    st.session_state.customers_selected_id = "" if current_id == next_id else next_id


def render_customer_detail(row: dict, owner_options: list[str], user: dict, can_assign_owner: bool) -> None:
    st.markdown('<div class="crm-detail-card">', unsafe_allow_html=True)
    top_left, top_right = st.columns([1.4, 1])
    with top_left:
        st.markdown(f"### {html.escape(clean(row.get('customer')) or '-')}")
        st.caption(f"เบอร์โทร: {clean(row.get('phone1')) or '-'} / เบอร์สำรอง: {clean(row.get('phone2')) or '-'}")
    with top_right:
        render_customer_actions(row, owner_options, user, can_assign_owner)

    info_cols = st.columns(3)
    info_cols[0].metric("สินค้า", clean(row.get("product_name")) or "-")
    info_cols[1].metric("SKU", clean(row.get("sku")) or "-")
    info_cols[2].metric("ผู้ดูแล", clean(row.get("sales_staff")) or "-")

    history_rows = unique_order_history(row)
    st.markdown("#### ประวัติสั่งซื้อเก่า")
    if not history_rows:
        st.info("ยังไม่มีเลขออเดอร์สำหรับแสดงประวัติสั่งซื้อเก่า")
    else:
        render_order_history(history_rows)
    st.markdown("</div>", unsafe_allow_html=True)


def render_customer_actions(row: dict, owner_options: list[str], user: dict, can_assign_owner: bool) -> None:
    current_owner = clean(row.get("sales_staff"))
    current_url = clean(row.get("product_url"))
    options = list(owner_options)
    if current_owner and current_owner not in options:
        options.insert(0, current_owner)

    record_id = clean(row.get("id"))
    order_id = clean(row.get("order_id"))
    form_key = f"customer_actions_{record_id}"
    with st.form(form_key):
        if can_assign_owner and options:
            col1, col2, col3, col4 = st.columns([1, 1, 2, 1])
        else:
            col1, col2 = st.columns([1, 1])
            col3 = col4 = None
        marker_options = ["0", "1", "2", "3", "RESET"]
        current_marker = follow_marker_display(row.get("followup_status"))
        marker_index = marker_options.index(current_marker) if current_marker in marker_options else 0
        marker = col1.selectbox("ติดตาม", marker_options, index=marker_index, key=f"{form_key}_marker")
        follow_submitted = col2.form_submit_button("บันทึกติดตาม", use_container_width=True)
        owner_submitted = False
        selected_owner = current_owner
        if can_assign_owner and options and col3 is not None and col4 is not None:
            default_index = options.index(current_owner) if current_owner in options else 0
            selected_owner = col3.selectbox("มอบหมายผู้ดูแล", options, index=default_index, key=f"{form_key}_owner")
            owner_submitted = col4.form_submit_button("บันทึกผู้ดูแล", use_container_width=True)
        url_submitted = False
        new_url = current_url
        if can_assign_owner:
            url_cols = st.columns([3, 1])
            new_url = url_cols[0].text_input("อัพเดต URL", value=current_url, key=f"{form_key}_url")
            url_submitted = url_cols[1].form_submit_button("บันทึก URL", use_container_width=True)

    if follow_submitted:
        try:
            payload = build_follow_marker_payload(row, marker, clean(user.get("email")))
            upsert_lead_followup(payload)
            st.success("อัปเดตสถานะติดตามแล้ว")
            st.rerun()
        except Exception as exc:
            st.error(f"อัปเดตสถานะติดตามไม่สำเร็จ: {exc}")
    if owner_submitted:
        try:
            updated = assign_owner_to_order_record(record_id, order_id, selected_owner, clean(user.get("email")))
            st.success(f"อัปเดตผู้ดูแลแล้ว {updated:,} แถว")
            st.rerun()
        except Exception as exc:
            st.error(f"อัปเดตผู้ดูแลไม่สำเร็จ: {exc}")
    if url_submitted:
        try:
            if not clean(new_url):
                st.error("กรุณากรอก URL ก่อนบันทึก")
                return
            phones = tuple(phone for phone in (clean(row.get("phone1")), clean(row.get("phone2"))) if phone)
            updated = assign_url_to_phones(phones, new_url, clean(user.get("email")))
            st.success(f"อัปเดต URL แล้ว {updated:,} แถว")
            st.rerun()
        except Exception as exc:
            st.error(f"อัปเดต URL ไม่สำเร็จ: {exc}")


def unique_names(rows: list[dict]) -> list[str]:
    names: list[str] = []
    for row in rows:
        name = clean(row.get("staff_name"))
        if name and name not in names:
            names.append(name)
    return names


def build_follow_marker_payload(row: dict, marker: str, updated_by: str) -> dict:
    phone1 = clean(row.get("phone1"))
    phone2 = clean(row.get("phone2"))
    phone_key = customer_phone_key(row)
    followup_status = clean(marker) or "0"
    if followup_status == "0":
        note = ""
    elif followup_status == "RESET":
        note = "RESET"
    else:
        note = f"ติดตามรอบที่ {followup_status}"
    return {
        "customer_key": phone_key or clean(row.get("id")),
        "crm_data_import_id": clean(row.get("id")) or None,
        "order_id": clean(row.get("order_id")),
        "customer_id": clean(row.get("customer_id")) or clean(row.get("id")),
        "customer_name": clean(row.get("customer")),
        "phone_key": phone_key,
        "phone1": phone1,
        "phone2": phone2,
        "product_group": "",
        "product_name": clean(row.get("product_name")),
        "sku": clean(row.get("sku")),
        "staff_code": clean(row.get("staff_code")),
        "owner": clean(row.get("sales_staff")),
        "lead_status": "new",
        "followup_status": followup_status,
        "next_followup_date": None,
        "followup_note": note,
        "follow_up_status": followup_status,
        "follow_up_date": None,
        "follow_up_note": note,
        "priority": "normal",
        "updated_by": updated_by,
        "updated_at": datetime.utcnow().isoformat() + "Z",
    }


def follow_marker_display(value: object) -> str:
    marker = clean(value)
    if not marker or marker.lower() == "none":
        return "0"
    return marker


def customer_phone_key(row: dict) -> str:
    phones = [normalize_phone(row.get("phone1")), normalize_phone(row.get("phone2"))]
    phones = [phone for phone in phones if phone]
    if not phones:
        return clean(row.get("id"))
    return min(phones)


def unique_order_history(row: dict) -> list[dict]:
    phones = tuple(phone for phone in (clean(row.get("phone1")), clean(row.get("phone2"))) if phone)
    if not phones:
        return []
    orders = fetch_orders_by_phones(phones, limit=500)
    seen: set[str] = set()
    history: list[dict] = []
    for order in orders:
        order_id = clean(order.get("order_id"))
        if not order_id or order_id in seen:
            continue
        seen.add(order_id)
        history.append(order)
    return history


def render_order_history(rows: list[dict]) -> None:
    st.markdown(
        """
<div class="crm-table">
  <div class="crm-table-header" style="grid-template-columns:1fr 1fr 1.4fr 1fr 1fr 1fr .8fr;">
    <div class="crm-table-cell">เลขออเดอร์</div>
    <div class="crm-table-cell">วันที่</div>
    <div class="crm-table-cell">สินค้า</div>
    <div class="crm-table-cell">ยอดขาย</div>
    <div class="crm-table-cell">ขนส่ง</div>
    <div class="crm-table-cell">เลขพัสดุ</div>
    <div class="crm-table-cell">URL</div>
  </div>
""",
        unsafe_allow_html=True,
    )
    for order in rows:
        url = clean(order.get("channel_url"))
        url_html = f'<a class="crm-link" href="{html.escape(url, quote=True)}" target="_blank">เปิดลิงก์</a>' if url else "-"
        st.markdown(
            f"""
<div class="crm-table-row" style="grid-template-columns:1fr 1fr 1.4fr 1fr 1fr 1fr .8fr;">
  <div class="crm-table-cell">{html.escape(clean(order.get("order_id")) or "-")}</div>
  <div class="crm-table-cell">{html.escape(clean(order.get("date_text")) or "-")}</div>
  <div class="crm-table-cell">{html.escape(clean(order.get("product_name")) or "-")}</div>
  <div class="crm-table-cell">{html.escape(clean(order.get("total_sales")) or "-")}</div>
  <div class="crm-table-cell">{html.escape(clean(order.get("shipping")) or "-")}</div>
  <div class="crm-table-cell">{html.escape(clean(order.get("tracking_no")) or "-")}</div>
  <div class="crm-table-cell">{url_html}</div>
</div>
""",
            unsafe_allow_html=True,
        )
    st.markdown("</div>", unsafe_allow_html=True)


def clean(value) -> str:
    return str(value or "").strip()


main()
