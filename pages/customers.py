import html

import streamlit as st

from auth_utils import can_manage_all, current_user, require_login
from crm_theme import badge, render_page_header
from nav_utils import render_sidebar_nav
from neon_utils import fetch_customer_page, fetch_filter_options


PAGE_SIZE_OPTIONS = [10, 25, 50, 100]
ALL = "ทั้งหมด"

st.set_page_config(page_title="Customers", layout="wide")


def main() -> None:
    render_sidebar_nav()
    require_login()
    user = current_user() or {}
    render_page_header("ลูกค้า", "ค้นหาและดูข้อมูลลูกค้าจาก Neon แบบ server-side")

    filters = render_filters(user)
    page_size = st.selectbox("จำนวนแถวต่อหน้า", PAGE_SIZE_OPTIONS, index=0, key="customers_page_size")
    page = int(st.number_input("หน้า", min_value=1, value=int(st.session_state.get("customers_page", 1)), step=1))
    st.session_state.customers_page = page

    with st.spinner("กำลังโหลดข้อมูลลูกค้า..."):
        rows, total = fetch_customer_page(filters, page_size, page, user)

    c1, c2, c3 = st.columns(3)
    c1.metric("ลูกค้าทั้งหมด", f"{total:,}")
    c2.metric("แถวที่แสดง", f"{len(rows):,}")
    c3.metric("หน้า", f"{page:,}")

    if not rows:
        st.info("ไม่พบข้อมูลตามเงื่อนไขที่ค้นหา")
        return
    render_customer_table(rows)


def render_filters(user: dict) -> dict[str, str]:
    try:
        options = fetch_filter_options()
    except Exception:
        options = {"owners": []}
    with st.form("customer_filters"):
        if can_manage_all(user):
            col1, col2 = st.columns([1, 2])
            staff = col1.selectbox("ผู้ดูแล", [ALL] + options.get("owners", []))
            keyword = col2.text_input("ค้นหา", placeholder="ชื่อ / เบอร์ / รหัสไปรษณีย์ / เลขคำสั่งซื้อ")
        else:
            staff = ALL
            keyword = st.text_input("ค้นหา", placeholder="ชื่อ / เบอร์ / รหัสไปรษณีย์ / เลขคำสั่งซื้อ")
        submitted = st.form_submit_button("ค้นหา", use_container_width=True)
    if submitted:
        st.session_state.customers_page = 1
    return {"staff": staff, "keyword": keyword}


def render_customer_table(rows: list[dict]) -> None:
    st.markdown(
        """
<div class="crm-table">
  <div class="crm-table-header" style="grid-template-columns:1.4fr 1fr 1.4fr 1fr 1fr .8fr;">
    <div class="crm-table-cell">ชื่อลูกค้า</div>
    <div class="crm-table-cell">เบอร์โทร</div>
    <div class="crm-table-cell">สินค้า</div>
    <div class="crm-table-cell">ผู้ดูแล</div>
    <div class="crm-table-cell">อัปเดต</div>
    <div class="crm-table-cell">URL</div>
  </div>
""",
        unsafe_allow_html=True,
    )
    for row in rows:
        url = clean(row.get("product_url"))
        url_html = f'<a class="crm-link" href="{html.escape(url, quote=True)}" target="_blank">เปิดลิงก์</a>' if url else "-"
        st.markdown(
            f"""
<div class="crm-table-row" style="grid-template-columns:1.4fr 1fr 1.4fr 1fr 1fr .8fr;">
  <div class="crm-table-cell">{html.escape(clean(row.get("customer")) or "-")}</div>
  <div class="crm-table-cell">{html.escape(clean(row.get("phone1")) or clean(row.get("phone2")) or "-")}</div>
  <div class="crm-table-cell">{html.escape(clean(row.get("product_name")) or "-")}</div>
  <div class="crm-table-cell">{html.escape(clean(row.get("sales_staff")) or "-")}</div>
  <div class="crm-table-cell">{html.escape(clean(row.get("updated_at"))[:10] or "-")}</div>
  <div class="crm-table-cell">{url_html}</div>
</div>
""",
            unsafe_allow_html=True,
        )
    st.markdown("</div>", unsafe_allow_html=True)


def clean(value) -> str:
    return str(value or "").strip()


main()
