import streamlit as st

from auth_utils import can_view_system_page, require_login
from nav_utils import render_sidebar_nav


st.set_page_config(page_title="Sync Status", layout="wide")
render_sidebar_nav()
auth_user = require_login()
if not can_view_system_page(auth_user):
    st.warning("หน้านี้เป็นระบบหลังบ้าน เฉพาะ CEO/EDITOR เท่านั้น")
    st.stop()

st.title("Sync Status")
st.info("ระบบ Sync จาก Google Sheet ไป Supabase ถูกปิดแล้ว ข้อมูล CRM หลักให้ใช้การนำเข้า Excel เข้า Neon แทน")

if st.button("รีเฟรชข้อมูลตอนนี้", use_container_width=True):
    st.cache_data.clear()
    st.rerun()

st.markdown(
    """
### สถานะปัจจุบัน
- ไม่มี auto refresh
- ไม่มี query ไปที่ `sync_control` หรือ `sync_runs` ใน Supabase
- Workflow legacy sync ถูกตั้งเป็น disabled/manual echo เท่านั้น
- ข้อมูล CRM หลักอยู่ที่ Neon table `crm_data_imports`
"""
)
