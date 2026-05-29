import streamlit as st

from auth_utils import can_view_system_page, require_login
from nav_utils import render_placeholder_page


st.set_page_config(page_title="CRM Dashboard", layout="wide")
auth_user = require_login()
if not can_view_system_page(auth_user):
    st.warning("หน้านี้เป็น dashboard หลังบ้าน เฉพาะ CEO/EDITOR เท่านั้น")
    st.stop()
render_placeholder_page(
    "CRM Dashboard",
    "หน้านี้ปิดการโหลดข้อมูลจาก Supabase แล้ว เพื่อให้ข้อมูล CRM หลักทำงานผ่าน Neon และลด Egress",
)
