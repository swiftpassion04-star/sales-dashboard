import streamlit as st

from app_revision import REVISION_SOURCE_UNAVAILABLE, resolve_app_revision
from auth_utils import can_view_system_page, require_login
from crm_theme import render_page_header
from nav_utils import render_sidebar_nav


st.set_page_config(page_title="System Status", layout="wide")


def _render_app_revision_section() -> None:
    try:
        revision = resolve_app_revision()
    except Exception:
        revision = {"source": REVISION_SOURCE_UNAVAILABLE}

    st.markdown("#### Application Revision")

    if not revision.get("commit_sha") and not revision.get("app_version"):
        st.info(
            "Revision unavailable — runtime นี้ไม่มี deployment metadata ที่ตรวจสอบได้ "
            "(ไม่พบ environment variable, git metadata หรือ package metadata ที่ใช้ยืนยันได้)"
        )
        return

    if revision.get("app_version"):
        st.write(f"**Version:** {revision['app_version']}")
    if revision.get("branch"):
        st.write(f"**Branch:** {revision['branch']}")
    st.write(f"**Revision source:** {revision.get('source', REVISION_SOURCE_UNAVAILABLE)}")
    if revision.get("build_timestamp"):
        st.write(f"**Build time:** {revision['build_timestamp']}")
    if revision.get("commit_sha"):
        st.write(f"**Commit ({revision.get('short_sha')}):**")
        st.code(revision["commit_sha"], language=None)


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
    _render_app_revision_section()


main()

