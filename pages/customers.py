from datetime import date, datetime, timedelta
import html
from io import BytesIO
from uuid import uuid4

import pandas as pd
import streamlit as st

from auth_utils import current_user, require_login
from crm_data.dashboard import (
    fetch_dashboard_kpis,
    fetch_sales_report,
    fetch_sales_report_owner_options,
    fetch_sales_report_rows,
)
from crm_data.team_sales import fetch_team_sales_summary, fetch_team_top_products
from crm_theme import badge, render_page_header
from nav_utils import render_sidebar_nav
import neon_utils as neon
import staff_identity
from neon_utils import (
    DEFAULT_FOLLOWUP_PRIORITY,
    assign_owner_to_order_record,
    assign_url_to_phones,
    fetch_customer_export_rows,
    fetch_customer_page,
    fetch_filter_options,
    fetch_followup_filter_options,
    fetch_orders_by_phones,
    fetch_owner_user_options,
    normalize_phone,
    upsert_lead_followup,
)
from permissions import (
    can_assign_customer_owner,
    can_export_customers,
    can_manage_all,
    can_manage_customer_records,
)
from ui.pagination import get_pagination_state, render_pagination


PAGE_SIZE_OPTIONS = [10, 25, 50, 100, 500, 1000]
CUSTOMER_HISTORY_DISPLAY_LIMIT = 100
OWNER_ASSIGNMENT_FOLLOWUP_FILTER_RESET_KEYS = (
    "followup_filter_priority",
    "followup_filter_lead_status",
    "followup_filter_followup_status",
)
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


def reset_owner_assignment_followup_filters() -> None:
    for key in OWNER_ASSIGNMENT_FOLLOWUP_FILTER_RESET_KEYS:
        st.session_state.pop(key, None)


def clear_customer_editor_action_caches() -> None:
    neon.clear_cached_data_functions(
        fetch_customer_page,
        fetch_customer_export_rows,
        fetch_filter_options,
        fetch_followup_filter_options,
        fetch_dashboard_kpis,
        fetch_sales_report,
        fetch_sales_report_rows,
        fetch_sales_report_owner_options,
        fetch_team_sales_summary,
        fetch_team_top_products,
    )


def main() -> None:
    render_sidebar_nav()
    require_login()
    user = current_user() or {}
    render_page_header("ลูกค้า", "ค้นหาและดูข้อมูลลูกค้าจาก Neon แบบ server-side")

    filters = render_filters(user)
    page_size, page = get_pagination_state(
        key_prefix="customers",
        page_size_options=PAGE_SIZE_OPTIONS,
    )

    with st.spinner("กำลังโหลดข้อมูลลูกค้า..."):
        rows, total = fetch_customer_page(filters, page_size, page, user, enforce_user_scope=False)

    page_size, page = render_pagination(
        total_rows=total,
        page_size=page_size,
        current_page=page,
        key_prefix="customers",
        page_size_options=PAGE_SIZE_OPTIONS,
    )
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
    if not can_export_customers(user):
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
    can_assign_owner = can_assign_customer_owner(user)
    staff_choices = []
    if can_assign_owner:
        try:
            staff_choices = staff_identity.build_staff_directory_choices(fetch_owner_user_options(active_only=True))
        except Exception:
            staff_choices = []
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
            render_customer_detail(row, staff_choices, user, can_assign_owner)


def select_customer_row(next_id: str) -> None:
    current_id = clean(st.session_state.get("customers_selected_id"))
    st.session_state.customers_selected_id = "" if current_id == next_id else next_id


def render_customer_detail(
    row: dict,
    staff_choices: list[tuple[str, str]],
    user: dict,
    can_assign_owner: bool,
) -> None:
    st.markdown('<div class="crm-detail-card">', unsafe_allow_html=True)
    top_left, top_right = st.columns([1.4, 1])
    with top_left:
        st.markdown(f"### {html.escape(clean(row.get('customer')) or '-')}")
        st.caption(f"เบอร์โทร: {clean(row.get('phone1')) or '-'} / เบอร์สำรอง: {clean(row.get('phone2')) or '-'}")
    with top_right:
        render_customer_actions(row, staff_choices, user, can_assign_owner)

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


def render_customer_actions(
    row: dict,
    staff_choices: list[tuple[str, str]],
    user: dict,
    can_assign_owner: bool,
) -> None:
    can_edit_follow = can_edit_customer_follow_action(row, user)
    can_manage_records = can_manage_customer_records(user)
    if not can_edit_follow and not can_assign_owner and not can_manage_records:
        st.caption("ไม่มีสิทธิ์แก้ไขรายการนี้")
        return

    current_owner = clean(row.get("sales_staff"))
    current_staff_code = clean(row.get("staff_code"))
    current_url = clean(row.get("product_url"))
    # Keyed by staff_code, never by display name -- two different staff_codes
    # that happen to render the same name must never collide or overwrite
    # each other here (see staff_identity.build_staff_directory_choices).
    staff_name_by_code = dict(staff_choices)
    codes = [code for code, _name in staff_choices]
    if current_staff_code and current_staff_code not in staff_name_by_code:
        staff_name_by_code[current_staff_code] = current_owner or current_staff_code
        codes = [current_staff_code] + codes

    record_id = clean(row.get("id"))
    order_id = clean(row.get("order_id"))
    form_key = f"customer_actions_{record_id}"
    with st.form(form_key):
        follow_submitted = False
        if can_edit_follow and can_assign_owner and codes:
            col1, col2, col3, col4 = st.columns([1, 1, 2, 1])
        elif can_edit_follow:
            col1, col2 = st.columns([1, 1])
            col3 = col4 = None
        elif can_assign_owner and codes:
            col3, col4 = st.columns([2, 1])
            col1 = col2 = None
        else:
            col1 = col2 = col3 = col4 = None
        marker_options = ["0", "1", "2", "3", "RESET"]
        current_marker = follow_marker_display(row.get("followup_status"))
        marker_index = marker_options.index(current_marker) if current_marker in marker_options else 0
        marker = current_marker
        if can_edit_follow and col1 is not None and col2 is not None:
            marker = col1.selectbox("ติดตาม", marker_options, index=marker_index, key=f"{form_key}_marker")
            follow_submitted = col2.form_submit_button("บันทึกติดตาม", use_container_width=True)
        owner_submitted = False
        selected_staff_code = current_staff_code
        if can_assign_owner and codes and col3 is not None and col4 is not None:
            default_index = codes.index(current_staff_code) if current_staff_code in codes else 0
            selected_staff_code = col3.selectbox(
                "มอบหมายผู้ดูแล",
                codes,
                index=default_index,
                format_func=lambda code: staff_name_by_code.get(code, code),
                key=f"{form_key}_owner",
            )
            owner_submitted = col4.form_submit_button("บันทึกผู้ดูแล", use_container_width=True)
        url_submitted = False
        new_url = current_url
        if can_assign_owner:
            url_cols = st.columns([3, 1])
            new_url = url_cols[0].text_input("อัพเดต URL", value=current_url, key=f"{form_key}_url")
            url_submitted = url_cols[1].form_submit_button("บันทึก URL", use_container_width=True)

    if follow_submitted:
        if not can_edit_customer_follow_action(row, user):
            st.error("ไม่มีสิทธิ์แก้ไขรายการนี้")
            return
        try:
            current_followup = neon.fetch_lead_followup_by_customer(
                customer_key=f"customer_id:{clean(row.get('customer_id')) or clean(row.get('id'))}",
                crm_data_import_id=clean(row.get("id")),
                phone1=row.get("phone1"),
                phone2=row.get("phone2"),
            )
        except Exception as exc:
            st.error(f"ไม่สามารถอ่านข้อมูลติดตามล่าสุดได้: {exc}")
            return
        try:
            payload = build_follow_marker_payload(row, marker, clean(user.get("email")), current_followup)
            upsert_lead_followup(payload)
            neon.clear_cached_data_functions(fetch_followup_filter_options)
            st.success("อัปเดตสถานะติดตามแล้ว")
            st.rerun()
        except Exception as exc:
            st.error(f"อัปเดตสถานะติดตามไม่สำเร็จ: {exc}")
    if owner_submitted:
        if not can_assign_owner:
            st.error("ไม่มีสิทธิ์มอบหมายผู้ดูแล")
            return
        selected_owner_name = clean(staff_name_by_code.get(selected_staff_code))
        if not selected_staff_code or not selected_owner_name:
            st.error("ไม่พบ staff_code ของผู้ดูแลที่เลือก")
            return
        try:
            updated = assign_owner_to_order_record(
                record_id,
                order_id,
                selected_owner_name,
                clean(user.get("email")),
                staff_code=selected_staff_code,
            )
            neon.clear_cached_data_functions(
                fetch_filter_options,
                fetch_followup_filter_options,
                getattr(neon, "fetch_sales_report_owner_options", None),
                getattr(neon, "fetch_crm_owner_options", None),
            )
            reset_owner_assignment_followup_filters()
            st.success(f"อัปเดตผู้ดูแลแล้ว {updated:,} แถว")
            st.rerun()
        except Exception as exc:
            st.error(f"อัปเดตผู้ดูแลไม่สำเร็จ: {exc}")
    if url_submitted:
        if not can_assign_owner:
            st.error("ไม่มีสิทธิ์อัปเดต URL")
            return
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


    if can_manage_records:
        render_customer_editor_record_actions(row, user)


def customer_editor_action_key(name: str, anchor_id: str) -> str:
    return f"{name}_{clean(anchor_id)}"


def render_customer_editor_record_actions(row: dict, user: dict) -> None:
    anchor_id = clean(row.get("id"))
    if not anchor_id:
        return
    st.divider()
    st.caption("EDITOR actions")
    edit_col, delete_col = st.columns(2)
    edit_key = customer_editor_action_key("edit_phone", anchor_id)
    delete_key = customer_editor_action_key("delete_order", anchor_id)
    if edit_col.button("แก้ไขเบอร์ลูกค้า", key=f"{edit_key}_open_button", use_container_width=True):
        st.session_state[edit_key] = True
        st.session_state.setdefault(f"{edit_key}_request_id", str(uuid4()))
    if delete_col.button("ลบออเดอร์ถาวร", key=f"{delete_key}_open_button", use_container_width=True):
        st.session_state[delete_key] = True
        st.session_state.setdefault(f"{delete_key}_request_id", str(uuid4()))

    if st.session_state.get(edit_key):
        render_customer_phone_editor_panel(row, user, edit_key)
    if st.session_state.get(delete_key):
        render_customer_order_delete_panel(row, user, delete_key)


def render_customer_order_delete_panel(row: dict, user: dict, state_key: str) -> None:
    anchor_id = clean(row.get("id"))
    with st.container(border=True):
        st.markdown("##### ยืนยันการลบออเดอร์")
        st.warning("การลบนี้จะลบเฉพาะแถวสินค้าในออเดอร์เดียวกัน และจะไม่ลบ Follow-up")
        preview_key = f"{state_key}_preview"
        request_key = f"{state_key}_request_id"
        in_progress_key = f"{state_key}_in_progress"
        col1, col2 = st.columns(2)
        if col1.button("ตรวจสอบก่อนลบ", key=f"{state_key}_preview_button", use_container_width=True):
            try:
                st.session_state[preview_key] = neon.preview_customer_order_delete(anchor_id, user)
            except Exception as exc:
                st.session_state.pop(preview_key, None)
                st.error(f"ตรวจสอบรายการลบไม่สำเร็จ: {exc}")
        if col2.button("ปิด", key=f"{state_key}_close_button", use_container_width=True):
            st.session_state.pop(state_key, None)
            st.session_state.pop(preview_key, None)
            st.session_state.pop(request_key, None)
            st.session_state.pop(in_progress_key, None)
            st.rerun()
        preview = st.session_state.get(preview_key) or {}
        if preview:
            st.write(f"จำนวนแถวสินค้าที่จะลบ: {int(preview.get('row_count') or 0):,}")
            st.write(f"จำนวน Follow-up ที่เกี่ยวข้อง (ไม่ลบ): {int(preview.get('followup_count') or 0):,}")
            st.caption(f"Grouping: {clean(preview.get('group_strategy')) or '-'}")
            confirmed = st.checkbox("ยืนยันว่าต้องการลบออเดอร์นี้ถาวร", key=f"{state_key}_confirm_checkbox")
            if st.button(
                "ลบออเดอร์ถาวร",
                key=f"{state_key}_confirm_button",
                use_container_width=True,
                disabled=not confirmed or bool(st.session_state.get(in_progress_key)),
            ):
                st.session_state[in_progress_key] = True
                try:
                    result = neon.delete_customer_order_records(
                        anchor_id,
                        user,
                        st.session_state.setdefault(request_key, str(uuid4())),
                    )
                    clear_customer_editor_action_caches()
                    if result.get("duplicate_request"):
                        st.info("คำขอนี้ถูกดำเนินการไปแล้ว")
                    else:
                        st.success(f"ลบออเดอร์แล้ว {int(result.get('deleted') or 0):,} แถว")
                    st.session_state.pop(state_key, None)
                    st.session_state.pop(preview_key, None)
                    st.session_state.pop(request_key, None)
                    st.session_state.pop(in_progress_key, None)
                    st.rerun()
                except Exception as exc:
                    st.session_state[in_progress_key] = False
                    st.error(f"ลบออเดอร์ไม่สำเร็จ: {exc}")


def render_customer_phone_editor_panel(row: dict, user: dict, state_key: str) -> None:
    anchor_id = clean(row.get("id"))
    request_key = f"{state_key}_request_id"
    preview_key = f"{state_key}_preview"
    in_progress_key = f"{state_key}_in_progress"
    with st.container(border=True):
        st.markdown("##### แก้ไขเบอร์ลูกค้า")
        phone1 = st.text_input("เบอร์โทร", value=clean(row.get("phone1")), key=f"{state_key}_phone1")
        phone2 = st.text_input("เบอร์สำรอง", value=clean(row.get("phone2")), key=f"{state_key}_phone2")
        check_col, close_col = st.columns(2)
        if check_col.button("ตรวจสอบก่อนบันทึก", key=f"{state_key}_preview_button", use_container_width=True):
            try:
                st.session_state[preview_key] = neon.preview_customer_phone_update(anchor_id, phone1, phone2, user)
                st.session_state.setdefault(request_key, str(uuid4()))
            except Exception as exc:
                st.session_state.pop(preview_key, None)
                st.error(f"ตรวจสอบเบอร์ไม่สำเร็จ: {exc}")
        if close_col.button("ปิด", key=f"{state_key}_close_button", use_container_width=True):
            st.session_state.pop(state_key, None)
            st.session_state.pop(preview_key, None)
            st.session_state.pop(request_key, None)
            st.session_state.pop(in_progress_key, None)
            st.rerun()
        preview = st.session_state.get(preview_key) or {}
        if not preview:
            return
        st.write(f"ออเดอร์ฝั่งปัจจุบันที่จะอัปเดต: {int(preview.get('source_row_count') or 0):,}")
        st.write(f"Follow-up ฝั่งปัจจุบันที่จะอัปเดต: {int(preview.get('source_followup_count') or 0):,}")
        if preview.get("collision"):
            render_customer_phone_merge_panel(row, user, state_key, preview)
            return
        confirmed = st.checkbox("ยืนยันบันทึกเบอร์ใหม่", key=f"{state_key}_confirm_checkbox")
        if st.button(
            "บันทึกเบอร์ใหม่",
            key=f"{state_key}_save_button",
            use_container_width=True,
            disabled=not confirmed or bool(st.session_state.get(in_progress_key)),
        ):
            st.session_state[in_progress_key] = True
            try:
                result = neon.update_customer_phones(
                    anchor_id,
                    preview.get("new_phone1"),
                    preview.get("new_phone2"),
                    user,
                    st.session_state.setdefault(request_key, str(uuid4())),
                )
                clear_customer_editor_action_caches()
                if result.get("duplicate_request"):
                    st.info("คำขอนี้ถูกดำเนินการไปแล้ว")
                else:
                    st.success(
                        "อัปเดตเบอร์แล้ว "
                        f"{int(result.get('updated_orders') or 0):,} ออเดอร์ / "
                        f"{int(result.get('updated_followups') or 0):,} Follow-up"
                    )
                st.session_state.pop(state_key, None)
                st.session_state.pop(preview_key, None)
                st.session_state.pop(request_key, None)
                st.session_state.pop(in_progress_key, None)
                st.rerun()
            except Exception as exc:
                st.session_state[in_progress_key] = False
                st.error(f"อัปเดตเบอร์ไม่สำเร็จ: {exc}")


def render_customer_phone_merge_panel(row: dict, user: dict, state_key: str, preview: dict) -> None:
    source_anchor_id = clean(row.get("id"))
    target_anchor_id = clean(preview.get("target_anchor_id"))
    merge_key = f"phone_merge_{source_anchor_id}_{target_anchor_id}"
    st.warning("พบเบอร์นี้อยู่ในลูกค้าคนอื่น ต้องยืนยันการรวมข้อมูลก่อน")
    st.write(f"ออเดอร์ฝั่ง Target: {int(preview.get('target_row_count') or 0):,}")
    st.write(f"Follow-up ฝั่ง Target: {int(preview.get('target_followup_count') or 0):,}")
    survivor = st.radio("Survivor", ["target", "source"], index=0, key=f"{merge_key}_survivor", horizontal=True)
    owner_source = st.radio("Owner", ["target", "source"], index=0, key=f"{merge_key}_owner_source", horizontal=True)
    url_source = st.radio("URL", ["target", "source"], index=0, key=f"{merge_key}_url_source", horizontal=True)
    st.session_state[merge_key] = True
    confirmed = st.checkbox("ยืนยันรวมข้อมูลลูกค้า", key=f"{merge_key}_confirm_checkbox")
    if st.button(
        "รวมข้อมูลลูกค้า",
        key=f"{merge_key}_confirm_button",
        use_container_width=True,
        disabled=not confirmed or bool(st.session_state.get(f"{merge_key}_in_progress")),
    ):
        st.session_state[f"{merge_key}_in_progress"] = True
        try:
            result = neon.merge_customer_phone_collision(
                source_anchor_id,
                target_anchor_id,
                preview.get("new_phone1"),
                preview.get("new_phone2"),
                user,
                st.session_state.setdefault(f"{merge_key}_request_id", str(uuid4())),
                survivor=survivor,
                owner_source=owner_source,
                url_source=url_source,
            )
            clear_customer_editor_action_caches()
            if result.get("duplicate_request"):
                st.info("คำขอนี้ถูกดำเนินการไปแล้ว")
            else:
                st.success(
                    "รวมข้อมูลแล้ว "
                    f"{int(result.get('updated_orders') or 0):,} ออเดอร์ / "
                    f"{int(result.get('updated_followups') or 0):,} Follow-up"
                )
            for suffix in ("", "_request_id", "_in_progress", "_confirm_checkbox"):
                st.session_state.pop(f"{merge_key}{suffix}", None)
            st.session_state.pop(state_key, None)
            st.session_state.pop(f"{state_key}_preview", None)
            st.session_state.pop(f"{state_key}_request_id", None)
            st.session_state.pop(f"{state_key}_in_progress", None)
            st.rerun()
        except Exception as exc:
            st.session_state[f"{merge_key}_in_progress"] = False
            st.error(f"รวมข้อมูลไม่สำเร็จ: {exc}")


def can_edit_customer_follow_action(row: dict, user: dict) -> bool:
    if can_manage_all(user):
        return True
    user_staff_code = clean(user.get("staff_code"))
    row_staff_code = clean(row.get("staff_code"))
    return bool(user_staff_code and row_staff_code and user_staff_code == row_staff_code)


def build_follow_marker_payload(
    row: dict,
    marker: str,
    updated_by: str,
    current_followup: dict | None = None,
) -> dict:
    phone1 = clean(row.get("phone1"))
    phone2 = clean(row.get("phone2"))
    phone_key = customer_phone_key(row)
    current_followup = current_followup or {}
    followup_status = clean(marker) or "0"
    if current_followup:
        note = clean(current_followup.get("followup_note")) or clean(current_followup.get("follow_up_note"))
    elif followup_status == "0":
        note = ""
    elif followup_status == "RESET":
        note = "RESET"
    else:
        note = f"ติดตามรอบที่ {followup_status}"
    next_followup_date = clean(current_followup.get("next_followup_date")) or clean(current_followup.get("follow_up_date"))
    customer_id = clean(row.get("customer_id")) or clean(row.get("id"))
    customer_key = clean(current_followup.get("customer_key")) or phone_key or clean(row.get("id"))
    crm_data_import_id = clean(current_followup.get("crm_data_import_id")) or clean(row.get("id")) or None
    owner = clean(current_followup.get("owner")) or clean(row.get("sales_staff"))
    staff_code = clean(current_followup.get("staff_code")) or clean(row.get("staff_code"))
    lead_status = clean(current_followup.get("lead_status")) or "new"
    priority = clean(current_followup.get("priority")) or DEFAULT_FOLLOWUP_PRIORITY
    return {
        "customer_key": customer_key,
        "crm_data_import_id": crm_data_import_id,
        "order_id": clean(current_followup.get("order_id")) or clean(row.get("order_id")),
        "customer_id": customer_id,
        "customer_name": clean(current_followup.get("customer_name")) or clean(row.get("customer")),
        "phone_key": clean(current_followup.get("phone_key")) or phone_key,
        "phone1": clean(current_followup.get("phone1")) or phone1,
        "phone2": clean(current_followup.get("phone2")) or phone2,
        "product_group": clean(current_followup.get("product_group")),
        "product_name": clean(current_followup.get("product_name")) or clean(row.get("product_name")),
        "sku": clean(current_followup.get("sku")) or clean(row.get("sku")),
        "staff_code": staff_code,
        "owner": owner,
        "lead_status": lead_status,
        "customer_status": clean(current_followup.get("customer_status")),
        "followup_status": followup_status,
        "next_followup_date": next_followup_date or None,
        "followup_note": note,
        "follow_up_status": followup_status,
        "follow_up_date": next_followup_date or None,
        "follow_up_note": note,
        "priority": priority,
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
        if not order_id:
            continue
        row_key = "|".join(
            [
                order_id,
                clean(order.get("sku")),
                clean(order.get("product_name")),
                clean(order.get("quantity")),
                order_sales_display(order),
            ]
        )
        if row_key in seen:
            continue
        seen.add(row_key)
        history.append(order)
    return history


def order_sales_display(order: dict) -> str:
    sale_type = clean(order.get("sale_type")).upper()
    if sale_type == "FOLLOW":
        return "-"
    if sale_type in {"NEW_ORDER", "UPSELL"}:
        return clean(order.get("amount")) or clean(order.get("total_sales")) or "-"
    return clean(order.get("total_sales")) or clean(order.get("amount")) or "-"


def render_order_history(rows: list[dict]) -> None:
    display_orders = rows[:CUSTOMER_HISTORY_DISPLAY_LIMIT]
    st.caption(f"แสดง {len(display_orders):,} จากทั้งหมด {len(rows):,} รายการล่าสุด")
    if len(rows) > len(display_orders):
        st.caption("หากต้องการดูมากกว่านี้ให้ใช้ Customer 360 หรือปรับในเฟสถัดไป")
    st.markdown(
        """
<div class="crm-table">
  <div class="crm-table-header" style="grid-template-columns:1fr 1fr 1.4fr .8fr 1fr 1fr 1fr .8fr;">
    <div class="crm-table-cell">เลขออเดอร์</div>
    <div class="crm-table-cell">วันที่</div>
    <div class="crm-table-cell">สินค้า</div>
    <div class="crm-table-cell">จำนวน</div>
    <div class="crm-table-cell">ยอดขาย</div>
    <div class="crm-table-cell">ขนส่ง</div>
    <div class="crm-table-cell">เลขพัสดุ</div>
    <div class="crm-table-cell">URL</div>
  </div>
""",
        unsafe_allow_html=True,
    )
    for order in display_orders:
        url = clean(order.get("channel_url"))
        url_html = f'<a class="crm-link" href="{html.escape(url, quote=True)}" target="_blank">เปิดลิงก์</a>' if url else "-"
        st.markdown(
            f"""
<div class="crm-table-row" style="grid-template-columns:1fr 1fr 1.4fr .8fr 1fr 1fr 1fr .8fr;">
  <div class="crm-table-cell">{html.escape(clean(order.get("order_id")) or "-")}</div>
  <div class="crm-table-cell">{html.escape(clean(order.get("date_text")) or "-")}</div>
  <div class="crm-table-cell">{html.escape(clean(order.get("product_name")) or "-")}</div>
  <div class="crm-table-cell">{html.escape(clean(order.get("quantity")) or "-")}</div>
  <div class="crm-table-cell">{html.escape(order_sales_display(order))}</div>
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
