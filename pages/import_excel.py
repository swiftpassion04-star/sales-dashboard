import streamlit as st

import neon_utils as neon
from auth_utils import current_user, require_login
from crm_theme import render_page_header
from nav_utils import render_sidebar_nav
from permissions import can_add_manual_order, can_import_excel
from ui.import_excel_ui import render_excel_import, render_import_history
from ui.manual_order_ui import render_manual_order_form


st.set_page_config(page_title="Import Excel", layout="wide")


def main() -> None:
    render_sidebar_nav()
    auth_user = require_login()
    user = current_user() or auth_user
    is_editor = can_import_excel(user)
    if not can_add_manual_order(user):
        st.warning("หน้านี้ใช้ได้เฉพาะ EDITOR และพนักงานที่มีสิทธิเพิ่มคำสั่งซื้อ")
        st.stop()

    render_page_header("นำเข้าข้อมูลลูกค้า", "เพิ่มคำสั่งซื้อทีละรายการ หรือ Import Excel แบบมีขั้นตอนตรวจสอบ")
    neon.require_neon_config()
    neon.ensure_crm_data_imports_schema()

    st.markdown('<div class="crm-section-title">เพิ่มคำสั่งซื้อ</div>', unsafe_allow_html=True)
    render_manual_order_form(user, is_editor)
    if not is_editor:
        st.info("บัญชีพนักงานเพิ่มคำสั่งซื้อได้ แต่ไม่มีสิทธินำเข้า Excel หรือจัดการ import history")
        return

    tabs = st.tabs(["1 Upload", "2 Preview / Validate / Confirm", "3 Import Batch History"])
    with tabs[0]:
        st.markdown('<div class="crm-card">อัปโหลดไฟล์ .xlsx ในขั้นตอนถัดไป ระบบจะให้เลือก worksheet, mapping column และ preview ก่อน import จริง</div>', unsafe_allow_html=True)
    with tabs[1]:
        render_excel_import(user)
    with tabs[2]:
        render_import_history()


main()
