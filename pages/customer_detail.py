import html
from datetime import date, datetime

import streamlit as st

from auth_utils import current_user, require_login
from crm_theme import badge, render_page_header
from nav_utils import render_sidebar_nav
from neon_utils import (
    clean,
    fetch_customer_360_base,
    fetch_customer_360_orders,
    fetch_customer_360_products,
    neon_connection,
    normalize_phone,
    upsert_lead_followup,
)
from permissions import can_manage_all


LEAD_STATUS_OPTIONS = {
    "new": "ลูกค้าใหม่",
    "contacted": "ติดต่อแล้ว",
    "interested": "สนใจ",
    "follow_up": "ต้องติดตาม",
    "won": "ปิดการขายแล้ว",
    "lost": "ไม่สนใจ/หลุด",
    "dormant": "ลูกค้าเงียบ",
}
FOLLOWUP_STATUS_OPTIONS = {
    "none": "ยังไม่ตั้งติดตาม",
    "scheduled": "นัดติดตาม",
    "done": "ติดตามแล้ว",
    "missed": "เลยกำหนด",
}
PRIORITY_OPTIONS = {
    "urgent": "ด่วนมาก",
    "high": "สูง",
    "normal": "ปกติ",
    "low": "ต่ำ",
}


st.set_page_config(page_title="Customer 360", layout="wide")


def main() -> None:
    render_sidebar_nav()
    require_login()
    user = current_user() or {}
    customer_id = get_customer_id()
    if not customer_id:
        render_page_header("Customer 360", "ไม่พบ customer_id ใน URL")
        st.warning("กรุณาเปิดหน้านี้จากปุ่มติดตามหรือดูประวัติในระบบ CRM")
        return

    customer = load_customer(customer_id)
    if not customer:
        render_page_header("Customer 360", f"ไม่พบข้อมูล customer_id: {customer_id}")
        st.warning("ไม่พบข้อมูลลูกค้าใน Neon")
        return

    if not can_view_customer_detail(user, customer):
        render_page_header("Customer 360", "ไม่มีสิทธิ์เข้าถึง")
        st.error("ไม่มีสิทธิ์เข้าถึงข้อมูลนี้")
        return

    followup = fetch_customer_followup(customer)
    orders = fetch_customer_360_orders(customer.get("phone1"), customer.get("phone2"), limit=20)
    products = fetch_customer_360_products(customer.get("phone1"), customer.get("phone2"), limit=50)
    render_page_header(
        clean(customer.get("customer")) or "Customer 360",
        "ข้อมูลลูกค้า, ออเดอร์ล่าสุด, Follow-up, ประวัติสั่งซื้อ และสินค้าที่เคยซื้อ",
    )
    render_customer_360(customer, followup, orders, products, user)


def get_customer_id() -> str:
    try:
        value = st.query_params.get("customer_id", "")
    except Exception:
        value = ""
    if isinstance(value, list):
        value = value[0] if value else ""
    return clean(value)


def load_customer(customer_id: str) -> dict:
    rows = fetch_customer_360_base(customer_id)
    return dict(rows[0]) if rows else {}


def can_view_customer_detail(user: dict, customer: dict) -> bool:
    if can_manage_all(user):
        return True
    user_staff_code = clean(user.get("staff_code"))
    customer_staff_code = clean(customer.get("staff_code"))
    return bool(user_staff_code and customer_staff_code and user_staff_code == customer_staff_code)


def fetch_customer_followup(customer: dict) -> dict:
    customer_id = clean(customer.get("id")) or clean(customer.get("customer_id"))
    phone1 = normalize_phone(customer.get("phone1"))
    phone2 = normalize_phone(customer.get("phone2"))
    clauses = ["customer_key = %s"]
    params = [f"customer_id:{customer_id}"]
    if customer_id and customer_id.isdigit():
        clauses.append("crm_data_import_id = %s")
        params.append(int(customer_id))
    if phone1:
        clauses.append("(phone1 = %s or phone2 = %s)")
        params.extend([phone1, phone1])
    if phone2:
        clauses.append("(phone1 = %s or phone2 = %s)")
        params.extend([phone2, phone2])
    with neon_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                select
                  id::text,
                  customer_key,
                  crm_data_import_id::text,
                  order_id,
                  customer_name,
                  phone1,
                  phone2,
                  product_name,
                  sku,
                  staff_code,
                  owner,
                  coalesce(lead_status, 'new') as lead_status,
                  coalesce(followup_status, follow_up_status, 'none') as followup_status,
                  coalesce(priority, 'normal') as priority,
                  coalesce(next_followup_date, follow_up_date)::text as next_followup_date,
                  coalesce(followup_note, follow_up_note, '') as followup_note,
                  updated_by,
                  updated_at
                from public.crm_lead_followups
                where {" or ".join(clauses)}
                order by updated_at desc nulls last, created_at desc nulls last
                limit 1
                """,
                params,
            )
            row = cur.fetchone()
            return dict(row) if row else {}


def render_customer_360(
    customer: dict,
    followup: dict,
    orders: list[dict],
    products: list[dict],
    user: dict,
) -> None:
    render_customer_profile(customer, followup)
    render_latest_order(orders[0] if orders else {})
    render_url_owner(customer)
    render_followup_form(customer, followup, user)
    render_customer_order_history(orders)
    render_products_bought(products)


def render_customer_profile(customer: dict, followup: dict) -> None:
    phone = clean(customer.get("phone1")) or clean(customer.get("phone2")) or "-"
    st.markdown(
        f"""
<div class="crm-card">
  <div style="display:flex;justify-content:space-between;gap:16px;align-items:flex-start;flex-wrap:wrap;">
    <div>
      <div class="crm-muted">เบอร์โทรหลัก</div>
      <div style="font-size:20px;font-weight:800;">{html.escape(phone)}</div>
    </div>
    <div style="display:flex;gap:8px;flex-wrap:wrap;">
      {badge(lead_label(clean(followup.get("lead_status")) or "new"), "blue")}
      {badge(followup_label(clean(followup.get("followup_status")) or "none"), "gray")}
      {priority_badge(clean(followup.get("priority")) or "normal")}
    </div>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )
    cols = st.columns(4)
    cols[0].metric("ลูกค้า", display_value(customer.get("customer")))
    cols[1].metric("เบอร์สำรอง", display_value(customer.get("phone2")))
    cols[2].metric("จังหวัด", display_value(customer.get("province")))
    cols[3].metric("รหัสไปรษณีย์", display_value(customer.get("postcode")))


def render_latest_order(order: dict) -> None:
    st.markdown('<div class="crm-section-title">Latest Order</div>', unsafe_allow_html=True)
    if not order:
        st.info("ยังไม่มีประวัติคำสั่งซื้อจากเบอร์โทรนี้")
        return
    cols = st.columns(4)
    cols[0].metric("เลขคำสั่งซื้อ", display_value(order.get("order_id")))
    cols[1].metric("วันที่", display_value(order.get("date_text")))
    cols[2].metric("ประเภทการขาย", display_value(order.get("sale_type")))
    cols[3].metric("ยอดขาย", display_value(order.get("amount") or order.get("total_sales")))
    cols = st.columns(4)
    cols[0].metric("SKU", display_value(order.get("sku")))
    cols[1].metric("สินค้า", display_value(order.get("product_name")))
    cols[2].metric("ขนส่ง", display_value(order.get("shipping")))
    cols[3].metric("เลขพัสดุ", display_value(order.get("tracking_no")))


def render_url_owner(customer: dict) -> None:
    st.markdown('<div class="crm-section-title">URL / Owner</div>', unsafe_allow_html=True)
    url = clean(customer.get("product_url")) or clean(customer.get("channel_url"))
    owner = clean(customer.get("sales_staff")) or clean(customer.get("owner"))
    cols = st.columns([1, 2])
    cols[0].metric("ผู้ดูแล", owner or "-")
    if url:
        cols[1].markdown(
            f"""
<div class="crm-card">
  <div class="crm-muted">URL</div>
  <a class="crm-link" href="{html.escape(url, quote=True)}" target="_blank">เปิดลิงก์</a>
</div>
""",
            unsafe_allow_html=True,
        )
    else:
        cols[1].metric("URL", "-")


def render_followup_form(customer: dict, followup: dict, user: dict) -> None:
    st.markdown('<div class="crm-section-title">รายละเอียด Follow-up</div>', unsafe_allow_html=True)
    with st.form("customer_detail_followup_form"):
        c1, c2, c3 = st.columns(3)
        lead_status = c1.selectbox(
            "สถานะลูกค้า",
            list(LEAD_STATUS_OPTIONS.keys()),
            format_func=lead_label,
            index=safe_index(list(LEAD_STATUS_OPTIONS.keys()), clean(followup.get("lead_status")) or "new"),
        )
        followup_status = c2.selectbox(
            "สถานะติดตาม",
            list(FOLLOWUP_STATUS_OPTIONS.keys()),
            format_func=followup_label,
            index=safe_index(list(FOLLOWUP_STATUS_OPTIONS.keys()), clean(followup.get("followup_status")) or "none"),
        )
        priority = c3.selectbox(
            "ความสำคัญ",
            list(PRIORITY_OPTIONS.keys()),
            format_func=priority_label,
            index=safe_index(list(PRIORITY_OPTIONS.keys()), clean(followup.get("priority")) or "normal"),
        )
        next_date = st.date_input("วันนัดติดตาม", value=parse_date(followup.get("next_followup_date")))
        clear_date = st.checkbox("ล้างวันที่")
        note = st.text_area("โน้ตติดตาม", value=clean(followup.get("followup_note")), height=120)
        submitted = st.form_submit_button("บันทึก Follow-up", use_container_width=True)

    if not submitted:
        return

    selected_date = None if clear_date or not next_date else next_date.isoformat()
    customer_id = clean(customer.get("id")) or clean(customer.get("customer_id"))
    payload = {
        "customer_key": f"customer_id:{customer_id}",
        "crm_data_import_id": customer_id or None,
        "order_id": clean(customer.get("order_id")),
        "customer_id": customer_id,
        "customer_name": clean(customer.get("customer")),
        "phone_key": normalize_phone(customer.get("phone1")) or normalize_phone(customer.get("phone2")),
        "phone1": normalize_phone(customer.get("phone1")),
        "phone2": normalize_phone(customer.get("phone2")),
        "product_name": clean(customer.get("product_name")),
        "sku": clean(customer.get("sku")),
        "url": clean(customer.get("product_url")) or clean(customer.get("channel_url")),
        "staff_code": clean(customer.get("staff_code")),
        "owner": clean(customer.get("sales_staff")),
        "lead_status": lead_status,
        "followup_status": followup_status,
        "next_followup_date": selected_date,
        "followup_note": note,
        "follow_up_status": followup_status,
        "follow_up_date": selected_date,
        "follow_up_note": note,
        "priority": priority,
        "updated_by": clean(user.get("email")),
        "updated_at": datetime.utcnow().isoformat() + "Z",
    }
    upsert_lead_followup(payload)
    st.cache_data.clear()
    st.success("บันทึก Follow-up แล้ว")
    st.rerun()


def render_customer_order_history(orders: list[dict]) -> None:
    orders = unique_orders(orders)[:20]
    st.markdown('<div class="crm-section-title">Order History ล่าสุด 20 รายการ</div>', unsafe_allow_html=True)
    if not orders:
        st.info("ยังไม่มีเลขออเดอร์สำหรับแสดงประวัติสั่งซื้อเก่า")
        return
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
    for order in orders:
        url = clean(order.get("channel_url"))
        url_html = f'<a class="crm-link" href="{html.escape(url, quote=True)}" target="_blank">เปิดลิงก์</a>' if url else "-"
        st.markdown(
            f"""
<div class="crm-table-row" style="grid-template-columns:1fr 1fr 1.4fr 1fr 1fr 1fr .8fr;">
  <div class="crm-table-cell">{html.escape(display_value(order.get("order_id")))}</div>
  <div class="crm-table-cell">{html.escape(display_value(order.get("date_text")))}</div>
  <div class="crm-table-cell">{html.escape(display_value(order.get("product_name")))}</div>
  <div class="crm-table-cell">{html.escape(display_value(order.get("amount") or order.get("total_sales")))}</div>
  <div class="crm-table-cell">{html.escape(display_value(order.get("shipping")))}</div>
  <div class="crm-table-cell">{html.escape(display_value(order.get("tracking_no")))}</div>
  <div class="crm-table-cell">{url_html}</div>
</div>
""",
            unsafe_allow_html=True,
        )
    st.markdown("</div>", unsafe_allow_html=True)


def render_products_bought(products: list[dict]) -> None:
    st.markdown('<div class="crm-section-title">Products Bought</div>', unsafe_allow_html=True)
    if not products:
        st.info("ยังไม่มีรายการสินค้าที่เคยซื้อ")
        return
    st.markdown(
        """
<div class="crm-table">
  <div class="crm-table-header" style="grid-template-columns:1fr 2fr 1fr 1fr;">
    <div class="crm-table-cell">SKU</div>
    <div class="crm-table-cell">สินค้า</div>
    <div class="crm-table-cell">จำนวนครั้ง</div>
    <div class="crm-table-cell">ซื้อล่าสุด</div>
  </div>
""",
        unsafe_allow_html=True,
    )
    for product in products:
        st.markdown(
            f"""
<div class="crm-table-row" style="grid-template-columns:1fr 2fr 1fr 1fr;">
  <div class="crm-table-cell">{html.escape(display_value(product.get("sku")))}</div>
  <div class="crm-table-cell">{html.escape(display_value(product.get("product_name")))}</div>
  <div class="crm-table-cell">{html.escape(display_value(product.get("purchase_count")))}</div>
  <div class="crm-table-cell">{html.escape(display_value(product.get("latest_order_date")))}</div>
</div>
""",
            unsafe_allow_html=True,
        )
    st.markdown("</div>", unsafe_allow_html=True)


def unique_orders(orders: list[dict]) -> list[dict]:
    seen = set()
    result = []
    for order in orders:
        order_id = clean(order.get("order_id"))
        dedupe_key = order_id or clean(order.get("source_key"))
        if not dedupe_key or dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        result.append(order)
    return result


def priority_badge(value: str) -> str:
    tones = {"urgent": "red", "high": "orange", "normal": "yellow", "low": "gray"}
    return badge(priority_label(value), tones.get(value, "gray"))


def lead_label(value: str) -> str:
    return LEAD_STATUS_OPTIONS.get(value, value)


def followup_label(value: str) -> str:
    return FOLLOWUP_STATUS_OPTIONS.get(value, value)


def priority_label(value: str) -> str:
    return PRIORITY_OPTIONS.get(value, value)


def safe_index(options: list[str], value: str) -> int:
    return options.index(value) if value in options else 0


def parse_date(value):
    text = clean(value)
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def display_value(value) -> str:
    return clean(value) or "-"


main()
