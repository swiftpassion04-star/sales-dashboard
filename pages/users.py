from datetime import datetime, timezone

import pandas as pd
import streamlit as st

from auth_utils import current_user, fetch_user_role, require_login
from crm_theme import render_page_header
from nav_utils import render_sidebar_nav
import neon_utils as neon
from neon_utils import (
    fetch_crm_owner_options,
    fetch_user_roles,
    set_user_role_active,
    test_user_role_visibility,
    upsert_user_role,
)
from permissions import can_edit_users


ROLE_OPTIONS = ["EDITOR", "ADMIN", "พนักงาน", "TELESELL", "STAFF", "USER", "ทั่วไป"]
OWNER_PLACEHOLDER = "ไม่เลือก owner mapping"


st.set_page_config(page_title="Users", layout="wide")


def clear_user_role_caches() -> None:
    neon.clear_cached_data_functions(
        fetch_user_role,
        neon.fetch_owner_user_options,
    )


def main() -> None:
    render_sidebar_nav()
    auth_user = require_login()
    user = current_user() or auth_user or {}
    can_manage = can_edit_users(user)
    render_page_header("User / Role", "จัดการสิทธิ์และ staff mapping จาก Neon")

    if not can_manage:
        st.info("หน้านี้ดูได้อย่างเดียว เฉพาะ ADMIN/EDITOR เท่านั้นที่แก้ User / Role ได้")

    try:
        owners = fetch_crm_owner_options()
        users = fetch_user_roles()
    except Exception as exc:
        st.error(f"โหลดข้อมูล User / Role ไม่สำเร็จ: {exc}")
        return

    render_mapping_notice()
    if can_manage:
        render_create_user(owners)
    render_mapping_tester(users, can_manage)
    render_user_table(users, owners, can_manage)


def render_mapping_notice() -> None:
    st.markdown(
        """
<div class="crm-card crm-muted">
ใช้ <strong>staff_code</strong> เป็นตัวจับคู่หลัก และ fallback เทียบ <strong>owner</strong> กับ
<strong>staff_name / owner_alias</strong> แบบ trim และลดช่องว่างซ้ำก่อนเทียบ exact match
</div>
""",
        unsafe_allow_html=True,
    )


def render_create_user(owners: list[str]) -> None:
    with st.expander("เพิ่ม user ใหม่", expanded=False):
        with st.form("create_user_role", clear_on_submit=True):
            c1, c2 = st.columns(2)
            email = c1.text_input("Email")
            role = c2.selectbox("Role", ROLE_OPTIONS, index=ROLE_OPTIONS.index("พนักงาน"))
            c3, c4 = st.columns(2)
            staff_code = c3.text_input("Staff code")
            staff_name = c4.text_input("Staff name")
            owner_alias = st.selectbox("Owner mapping จากข้อมูลจริง", [OWNER_PLACEHOLDER] + owners)
            is_active = st.checkbox("Active", value=True)
            submitted = st.form_submit_button("เพิ่ม / อัปเดต user", use_container_width=True)
        if submitted:
            if not clean(email):
                st.error("กรุณากรอก email")
                return
            upsert_user_role(
                {
                    "email": clean(email).lower(),
                    "role": role,
                    "staff_code": clean(staff_code),
                    "staff_name": clean(staff_name),
                    "owner_alias": "" if owner_alias == OWNER_PLACEHOLDER else owner_alias,
                    "is_active": bool(is_active),
                    "updated_at": now_iso(),
                }
            )
            st.success("บันทึก User / Role แล้ว")
            clear_user_role_caches()
            st.rerun()


def render_mapping_tester(users: list[dict], can_manage: bool) -> None:
    if not users:
        return
    st.markdown("### ทดสอบ mapping")
    emails = [clean(row.get("email")) for row in users if clean(row.get("email"))]
    selected = st.selectbox("เลือก user เพื่อดูจำนวนลูกค้าที่จะเห็น", emails)
    if st.button("ทดสอบ mapping", use_container_width=True):
        result = test_user_role_visibility(selected, limit=10)
        user = result.get("user") or {}
        if not user:
            st.error("ไม่พบ user นี้ใน crm_user_roles")
            return
        total = int(result.get("total") or 0)
        st.success(f"{selected} จะเห็นข้อมูลลูกค้า {total:,} รายการ")
        st.caption(
            f"role={clean(user.get('role')) or '-'} | "
            f"staff_code={clean(user.get('staff_code')) or '-'} | "
            f"staff_name={clean(user.get('staff_name')) or '-'} | "
            f"owner_alias={clean(user.get('owner_alias')) or '-'}"
        )
        samples = result.get("samples") or []
        if samples:
            st.dataframe(pd.DataFrame(samples), use_container_width=True, hide_index=True)
        else:
            st.warning("mapping นี้ยังไม่เห็นข้อมูลลูกค้า")
            if can_manage:
                st.info("ให้ตั้ง staff_name หรือ owner_alias ให้ตรงกับ owner จริงใน crm_data_imports")


def render_user_table(users: list[dict], owners: list[str], can_manage: bool) -> None:
    st.markdown("### รายชื่อ User / Role")
    if not users:
        st.info("ยังไม่มี user ใน crm_user_roles")
        return

    for row in users:
        render_user_row(row, owners, can_manage)


def render_user_row(row: dict, owners: list[str], can_manage: bool) -> None:
    email = clean(row.get("email"))
    active_label = "active" if row.get("is_active") else "inactive"
    with st.expander(f"{email} | {clean(row.get('role')) or '-'} | {active_label}", expanded=False):
        with st.form(f"user_role_{email}"):
            c1, c2 = st.columns(2)
            next_email = c1.text_input("Email", value=email, disabled=not can_manage)
            role_value = clean(row.get("role")) or "ทั่วไป"
            role_index = ROLE_OPTIONS.index(role_value) if role_value in ROLE_OPTIONS else ROLE_OPTIONS.index("ทั่วไป")
            role = c2.selectbox("Role", ROLE_OPTIONS, index=role_index, disabled=not can_manage)
            c3, c4 = st.columns(2)
            staff_code = c3.text_input("Staff code", value=clean(row.get("staff_code")), disabled=not can_manage)
            staff_name = c4.text_input("Staff name", value=clean(row.get("staff_name")), disabled=not can_manage)
            owner_alias_value = clean(row.get("owner_alias"))
            owner_options = [OWNER_PLACEHOLDER] + owners
            owner_index = owner_options.index(owner_alias_value) if owner_alias_value in owner_options else 0
            owner_alias = st.selectbox("Owner mapping", owner_options, index=owner_index, disabled=not can_manage)
            is_active = st.checkbox("Active", value=bool(row.get("is_active")), disabled=not can_manage)
            saved = st.form_submit_button("บันทึก", use_container_width=True, disabled=not can_manage)
        if saved:
            if not clean(next_email):
                st.error("กรุณากรอก email")
                return
            upsert_user_role(
                {
                    "email": clean(next_email).lower(),
                    "role": role,
                    "staff_code": clean(staff_code),
                    "staff_name": clean(staff_name),
                    "owner_alias": "" if owner_alias == OWNER_PLACEHOLDER else owner_alias,
                    "is_active": bool(is_active),
                    "updated_at": now_iso(),
                }
            )
            if clean(next_email).lower() != email:
                set_user_role_active(email, False, now_iso())
            st.success("บันทึก User / Role แล้ว")
            clear_user_role_caches()
            st.rerun()

        if can_manage and row.get("is_active"):
            if st.button("ปิดใช้งาน user นี้", key=f"deactivate_{email}", use_container_width=True):
                set_user_role_active(email, False, now_iso())
                st.success("ปิดใช้งาน user แล้ว")
                clear_user_role_caches()
                st.rerun()


def clean(value) -> str:
    return str(value or "").strip()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


main()
