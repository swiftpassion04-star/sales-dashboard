import streamlit as st

from auth_utils import current_user, require_login
from crm_theme import render_page_header
from nav_utils import render_sidebar_nav
from neon_utils import fetch_dashboard_kpis


st.set_page_config(page_title="Dashboard", layout="wide")


def main() -> None:
    render_sidebar_nav()
    require_login()
    user = current_user() or {}
    render_page_header("Dashboard", "ภาพรวมงาน CRM รายวันสำหรับทีม Telesales")
    with st.spinner("กำลังโหลด KPI จาก Neon..."):
        kpis = fetch_dashboard_kpis(user)

    cols = st.columns(6)
    cols[0].metric("ลูกค้าทั้งหมด", f"{kpis['total_customers']:,}")
    cols[1].metric("ต้องติดตามวันนี้", f"{kpis['due_today']:,}")
    cols[2].metric("ค้างติดตาม", f"{kpis['overdue']:,}")
    cols[3].metric("Lead สนใจ", f"{kpis['interested']:,}")
    cols[4].metric("ปิดการขายแล้ว", f"{kpis['won']:,}")
    cols[5].metric("อัปเดตล่าสุด", kpis["latest_update"][:10] if kpis["latest_update"] else "-")

    st.markdown('<div class="crm-section-title">สถานะระบบ</div>', unsafe_allow_html=True)
    st.markdown(
        """
<div class="crm-card">
  ข้อมูล CRM หลักอ่าน/เขียนจาก Neon PostgreSQL และ Supabase ใช้เฉพาะ Login/Auth เท่านั้น
</div>
""",
        unsafe_allow_html=True,
    )


main()

