import streamlit as st

from auth_utils import can_view_system_page, require_login
from crm_theme import render_page_header
from nav_utils import render_sidebar_nav


st.set_page_config(page_title="System Status", layout="wide")


def main() -> None:
    render_sidebar_nav()
    auth_user = require_login()
    if not can_view_system_page(auth_user):
        st.warning("หน้านี้เป็นระบบหลังบ้าน เฉพาะ EDITOR เท่านั้น")
        st.stop()
    render_page_header("Sync / System Status", "สถานะระบบ CRM หลังย้ายข้อมูลหลักไป Neon")
    if st.button("รีเฟรชข้อมูลตอนนี้", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    c1, c2, c3 = st.columns(3)
    c1.metric("Supabase Database Query", "0")
    c2.metric("CRM Database", "Neon")
    c3.metric("Auto Refresh", "Manual")
    st.markdown(
        """
<div class="crm-card">
  <b>สถานะปัจจุบัน</b><br>
  CRM data ใช้ Neon PostgreSQL เป็นหลัก, Supabase ใช้เฉพาะ Login/Auth และไม่มี legacy Google Sheet sync อัตโนมัติ
</div>
""",
        unsafe_allow_html=True,
    )


main()

