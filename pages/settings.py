import streamlit as st

from auth_utils import can_view_system_page, require_login
from crm_theme import render_page_header
from nav_utils import render_sidebar_nav
from ui.glass_theme import inject_liquid_glass


st.set_page_config(page_title="Settings", layout="wide")


def main() -> None:
    render_sidebar_nav()
    inject_liquid_glass("crm-settings-glass")
    auth_user = require_login()
    if not can_view_system_page(auth_user):
        st.warning("หน้านี้เป็นระบบหลังบ้าน เฉพาะ EDITOR เท่านั้น")
        st.stop()
    render_page_header("Settings", "พื้นที่ตั้งค่าระบบ CRM")
    st.markdown(
        """
<div class="crm-card">
  ยังไม่มีการตั้งค่าเพิ่มเติมในหน้านี้ ระบบยังคงใช้ Supabase Auth และ Neon PostgreSQL ตาม architecture ปัจจุบัน
</div>
""",
        unsafe_allow_html=True,
    )


main()

