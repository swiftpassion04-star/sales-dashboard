from datetime import date, datetime

import streamlit as st

from auth_utils import ROLE_EDITOR, ROLE_TELESELL_ALIASES, current_user, require_login
from nav_utils import render_sidebar_nav
from neon_utils import fetch_followup_filter_options, fetch_followup_page, upsert_lead_followup


PAGE_SIZE_OPTIONS = [10, 25, 50, 100, 250]
ALL = "ทั้งหมด"
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
    "normal": "ปกติ",
    "high": "สำคัญ",
    "urgent": "ด่วน",
}


st.set_page_config(page_title="ติดตามลูกค้า", layout="wide")


def inject_css() -> None:
    st.markdown(
        """
<style>
.stApp { background:#fff8f1; color:#111827; }
.block-container { max-width:1280px; padding-top:2.2rem; }
h1 { color:#111827 !important; border-left:6px solid #f97316; padding-left:14px; }
[data-testid="stForm"], [data-testid="stExpander"] {
  background:#ffffff !important;
  border:1px solid #fed7aa !important;
  border-radius:14px !important;
  box-shadow:0 16px 36px rgba(124,45,18,.07);
}
label { color:#7c2d12 !important; font-weight:750 !important; }
div[data-baseweb="input"] > div,
div[data-baseweb="select"] > div,
textarea {
  background:#ffffff !important;
  color:#111827 !important;
  -webkit-text-fill-color:#111827 !important;
  border:1px solid #fb923c !important;
  border-radius:10px !important;
}
.stButton > button, button[kind="formSubmit"] {
  min-height:40px !important;
  border-radius:10px !important;
  border:1px solid #f97316 !important;
  font-weight:800 !important;
}
button[kind="formSubmit"], .stButton > button[kind="primary"] {
  background:#f97316 !important;
  color:#ffffff !important;
}
.crm-chip {
  display:inline-block;
  padding:5px 10px;
  border-radius:999px;
  background:#ffedd5;
  color:#9a3412;
  font-weight:800;
  margin-right:6px;
  margin-bottom:6px;
}
.crm-note { color:#6b7280; font-size:14px; }
</style>
""",
        unsafe_allow_html=True,
    )


def main() -> None:
    inject_css()
    render_sidebar_nav()
    auth_user = require_login()
    user = current_user() or auth_user
    role = clean(user.get("role"))
    if role != ROLE_EDITOR and role not in ROLE_TELESELL_ALIASES:
        st.warning("หน้านี้ใช้ได้เฉพาะ EDITOR และ TELESELL เท่านั้น")
        st.stop()

    st.title("ติดตามลูกค้า")
    st.caption("จัดการ Lead / Follow-up จาก Neon เท่านั้น ไม่เรียก Supabase Database")

    filters = render_filters(user)
    page_size = st.selectbox("จำนวนแถวต่อหน้า", PAGE_SIZE_OPTIONS, index=0, key="followup_page_size")
    page = int(st.number_input("หน้า", min_value=1, value=int(st.session_state.get("followup_page", 1)), step=1))
    st.session_state.followup_page = page

    try:
        rows, total = fetch_followup_page(filters, user, page_size, page)
    except Exception as exc:
        st.error(f"โหลดข้อมูลติดตามลูกค้าไม่สำเร็จ: {exc}")
        return

    render_summary(rows, total, page_size, page)
    if not rows:
        st.info("ยังไม่มีรายการติดตามลูกค้าตามตัวกรองนี้")
        return
    for row in rows:
        render_followup_row(row, user)


def render_filters(user: dict) -> dict[str, str]:
    try:
        options = fetch_followup_filter_options(user)
    except Exception:
        options = {"owners": [], "products": []}
    with st.form("followup_filters"):
        col1, col2, col3 = st.columns(3)
        lead_status = col1.selectbox("Lead Status", [ALL] + list(LEAD_STATUS_OPTIONS.keys()), format_func=lead_label)
        followup_status = col2.selectbox("Follow-up Status", [ALL] + list(FOLLOWUP_STATUS_OPTIONS.keys()), format_func=followup_label)
        priority = col3.selectbox("Priority", [ALL] + list(PRIORITY_OPTIONS.keys()), format_func=priority_label)
        col4, col5 = st.columns(2)
        product = col4.selectbox("Product / SKU", [ALL] + options.get("products", []))
        owner = ALL
        if clean(user.get("role")) == ROLE_EDITOR:
            owner = col5.selectbox("Owner", [ALL] + options.get("owners", []))
        submitted = st.form_submit_button("ค้นหา", use_container_width=True)
    if submitted:
        st.session_state.followup_page = 1
    return {
        "lead_status": lead_status,
        "followup_status": followup_status,
        "priority": priority,
        "product": product,
        "owner": owner,
    }


def render_summary(rows: list[dict], total: int, page_size: int, page: int) -> None:
    total_pages = max((total - 1) // page_size + 1, 1)
    c1, c2, c3 = st.columns(3)
    c1.metric("รายการทั้งหมด", f"{total:,}")
    c2.metric("แถวที่แสดง", f"{len(rows):,}")
    c3.metric("หน้า", f"{page:,} / {total_pages:,}")


def render_followup_row(row: dict, user: dict) -> None:
    title = f"{clean(row.get('customer_name')) or '-'} | {clean(row.get('phone1')) or clean(row.get('phone2')) or '-'}"
    with st.expander(title):
        st.markdown(
            " ".join(
                [
                    chip(f"สินค้า {clean(row.get('sku'))} {clean(row.get('product_name'))}".strip()),
                    chip(f"ผู้ดูแล {clean(row.get('owner')) or '-'}"),
                    chip(f"นัด {clean(row.get('next_followup_date')) or '-'}"),
                ]
            ),
            unsafe_allow_html=True,
        )
        col1, col2 = st.columns(2)
        col1.write(f"เลขคำสั่งซื้อ: **{clean(row.get('order_id')) or '-'}**")
        col2.write(f"อัปเดตล่าสุด: **{clean(row.get('updated_at')) or '-'}**")
        with st.form(f"followup_save_{row.get('crm_data_import_id')}"):
            c1, c2, c3 = st.columns(3)
            lead_status = c1.selectbox(
                "Lead Status",
                list(LEAD_STATUS_OPTIONS.keys()),
                index=safe_index(list(LEAD_STATUS_OPTIONS.keys()), clean(row.get("lead_status")) or "new"),
                format_func=lead_label,
            )
            followup_status = c2.selectbox(
                "Follow-up Status",
                list(FOLLOWUP_STATUS_OPTIONS.keys()),
                index=safe_index(list(FOLLOWUP_STATUS_OPTIONS.keys()), clean(row.get("followup_status")) or "none"),
                format_func=followup_label,
            )
            priority = c3.selectbox(
                "Priority",
                list(PRIORITY_OPTIONS.keys()),
                index=safe_index(list(PRIORITY_OPTIONS.keys()), clean(row.get("priority")) or "normal"),
                format_func=priority_label,
            )
            default_date = parse_date(row.get("next_followup_date"))
            next_date = st.date_input("Next Follow-up Date", value=default_date)
            clear_date = st.checkbox("ล้างวันที่", value=False)
            note = st.text_area("Follow-up Note", value=clean(row.get("followup_note")), height=110)
            submitted = st.form_submit_button("บันทึก Follow-up", use_container_width=True)
        if submitted:
            payload = {
                "customer_key": clean(row.get("customer_key")),
                "crm_data_import_id": clean(row.get("crm_data_import_id")),
                "order_id": clean(row.get("order_id")),
                "customer_id": clean(row.get("crm_data_import_id")),
                "customer_name": clean(row.get("customer_name")),
                "phone_key": clean(row.get("phone1")) or clean(row.get("phone2")),
                "phone1": clean(row.get("phone1")),
                "phone2": clean(row.get("phone2")),
                "product_group": "",
                "product_name": clean(row.get("product_name")),
                "sku": clean(row.get("sku")),
                "staff_code": clean(row.get("staff_code")),
                "owner": clean(row.get("owner")),
                "lead_status": lead_status,
                "followup_status": followup_status,
                "next_followup_date": None if clear_date else next_date.isoformat(),
                "followup_note": note,
                "follow_up_status": followup_status,
                "follow_up_date": None if clear_date else next_date.isoformat(),
                "follow_up_note": note,
                "priority": priority,
                "updated_by": clean(user.get("email")),
                "updated_at": datetime.utcnow().isoformat() + "Z",
            }
            try:
                upsert_lead_followup(payload)
                st.cache_data.clear()
                st.success("บันทึก Follow-up แล้ว")
                st.rerun()
            except Exception as exc:
                st.error(f"บันทึกไม่สำเร็จ: {exc}")


def chip(text: str) -> str:
    return f'<span class="crm-chip">{text}</span>'


def lead_label(value: str) -> str:
    return ALL if value == ALL else LEAD_STATUS_OPTIONS.get(value, value)


def followup_label(value: str) -> str:
    return ALL if value == ALL else FOLLOWUP_STATUS_OPTIONS.get(value, value)


def priority_label(value: str) -> str:
    return ALL if value == ALL else PRIORITY_OPTIONS.get(value, value)


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


def clean(value) -> str:
    return str(value or "").strip()


main()
