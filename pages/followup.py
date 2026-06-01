import html
from datetime import date, datetime

import streamlit as st

from auth_utils import ROLE_EDITOR, ROLE_TELESELL_ALIASES, current_user, require_login
from crm_theme import badge, render_page_header
from nav_utils import render_sidebar_nav
from neon_utils import fetch_followup_filter_options, fetch_followup_page, upsert_lead_followup


PAGE_SIZE_OPTIONS = [10, 25, 50, 100]
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
    "urgent": "ด่วนมาก",
    "high": "สูง",
    "normal": "ปกติ",
    "low": "ต่ำ",
}

st.set_page_config(page_title="Follow-up", layout="wide")


def main() -> None:
    render_sidebar_nav()
    require_login()
    user = current_user() or {}
    role = clean(user.get("role"))
    if role != ROLE_EDITOR and role not in ROLE_TELESELL_ALIASES:
        st.warning("หน้านี้ใช้ได้เฉพาะ EDITOR และพนักงานที่ดูแลลูกค้า")
        st.stop()

    render_page_header("ติดตามลูกค้า", "จัดการ Lead และ Follow-up จาก Neon เท่านั้น")
    filters = render_filters(user)
    page_size = st.selectbox("จำนวนแถวต่อหน้า", PAGE_SIZE_OPTIONS, index=0, key="followup_page_size_v2")
    page = int(st.number_input("หน้า", min_value=1, value=int(st.session_state.get("followup_page_v2", 1)), step=1))
    st.session_state.followup_page_v2 = page

    with st.spinner("กำลังโหลดรายการติดตาม..."):
        rows, total = fetch_followup_page(filters, user, page_size, page)
    render_summary(rows, total, page_size, page)
    render_followup_sections(rows)
    if not rows:
        st.info("ไม่พบข้อมูลตามตัวกรอง")
        return
    render_followup_table(rows, user)


def render_filters(user: dict) -> dict[str, str]:
    try:
        options = fetch_followup_filter_options(user)
    except Exception:
        options = {"owners": [], "products": []}
    with st.form("followup_filters_v2"):
        c1, c2, c3 = st.columns(3)
        lead_status = c1.selectbox("สถานะลูกค้า", [ALL] + list(LEAD_STATUS_OPTIONS.keys()), format_func=lead_label)
        followup_status = c2.selectbox("สถานะติดตาม", [ALL] + list(FOLLOWUP_STATUS_OPTIONS.keys()), format_func=followup_label)
        priority = c3.selectbox("ความสำคัญ", [ALL] + list(PRIORITY_OPTIONS.keys()), format_func=priority_label)
        c4, c5 = st.columns(2)
        product = c4.selectbox("สินค้า / SKU", [ALL] + options.get("products", []))
        owner = ALL
        if clean(user.get("role")) == ROLE_EDITOR:
            owner = c5.selectbox("ผู้ดูแล", [ALL] + options.get("owners", []))
        keyword = st.text_input("ค้นหา", placeholder="เบอร์โทร / ชื่อลูกค้า / เลขคำสั่งซื้อ")
        submitted = st.form_submit_button("ค้นหา", use_container_width=True)
    if submitted:
        st.session_state.followup_page_v2 = 1
    return {
        "lead_status": lead_status,
        "followup_status": followup_status,
        "priority": priority,
        "product": product,
        "owner": owner,
        "phone": normalize_phone(keyword),
        "keyword": keyword,
    }


def render_summary(rows: list[dict], total: int, page_size: int, page: int) -> None:
    total_pages = max((total - 1) // page_size + 1, 1)
    c1, c2, c3 = st.columns(3)
    c1.metric("รายการทั้งหมด", f"{total:,}")
    c2.metric("แถวที่แสดง", f"{len(rows):,}")
    c3.metric("หน้า", f"{page:,} / {total_pages:,}")


def render_followup_sections(rows: list[dict]) -> None:
    today = date.today().isoformat()
    due_today = sum(1 for row in rows if clean(row.get("next_followup_date"))[:10] == today and clean(row.get("followup_status")) != "done")
    overdue = sum(1 for row in rows if clean(row.get("next_followup_date")) and clean(row.get("next_followup_date"))[:10] < today and clean(row.get("followup_status")) != "done")
    done = sum(1 for row in rows if clean(row.get("followup_status")) == "done")
    week = max(len(rows) - due_today - overdue - done, 0)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("ต้องติดตามวันนี้", f"{due_today:,}")
    c2.metric("ค้างเกินกำหนด", f"{overdue:,}")
    c3.metric("สัปดาห์นี้", f"{week:,}")
    c4.metric("เสร็จแล้ว", f"{done:,}")


def render_followup_table(rows: list[dict], user: dict) -> None:
    st.markdown(
        """
<div class="crm-table">
  <div class="crm-table-header" style="grid-template-columns:1fr 1.35fr 1fr .8fr 1.2fr 1fr 1fr .9fr .8fr;">
    <div class="crm-table-cell">วันนัด</div>
    <div class="crm-table-cell">ชื่อลูกค้า</div>
    <div class="crm-table-cell">เบอร์โทร</div>
    <div class="crm-table-cell">SKU</div>
    <div class="crm-table-cell">สินค้า</div>
    <div class="crm-table-cell">สถานะลูกค้า</div>
    <div class="crm-table-cell">สถานะติดตาม</div>
    <div class="crm-table-cell">ความสำคัญ</div>
    <div class="crm-table-cell">URL</div>
  </div>
""",
        unsafe_allow_html=True,
    )
    selected_id = clean(st.session_state.get("followup_selected_id_v2"))
    for row in rows:
        key = row_key(row)
        url = clean(row.get("url"))
        url_html = f'<a class="crm-link" href="{html.escape(url, quote=True)}" target="_blank">เปิดลิงก์</a>' if url else "-"
        st.markdown(
            f"""
<div class="crm-table-row" style="grid-template-columns:1fr 1.35fr 1fr .8fr 1.2fr 1fr 1fr .9fr .8fr;">
  <div class="crm-table-cell">{html.escape(clean(row.get("next_followup_date")) or "ว่าง")}</div>
  <div class="crm-table-cell">{html.escape(clean(row.get("customer_name")) or "-")}</div>
  <div class="crm-table-cell">{html.escape(clean(row.get("phone1")) or clean(row.get("phone2")) or "-")}</div>
  <div class="crm-table-cell">{html.escape(clean(row.get("sku")) or "-")}</div>
  <div class="crm-table-cell">{html.escape(clean(row.get("product_name")) or "-")}</div>
  <div class="crm-table-cell">{badge(lead_label(clean(row.get("lead_status")) or "new"), "blue")}</div>
  <div class="crm-table-cell">{badge(followup_label(clean(row.get("followup_status")) or "none"), "gray")}</div>
  <div class="crm-table-cell">{priority_badge(clean(row.get("priority")) or "normal")}</div>
  <div class="crm-table-cell">{url_html}</div>
</div>
""",
            unsafe_allow_html=True,
        )
        is_selected = selected_id == key
        toggle_label = f"{'ปิด' if is_selected else 'เปิด'}รายละเอียด: {clean(row.get('customer_name')) or key}"
        st.button(
            toggle_label,
            key=f"open_followup_detail_{key}",
            use_container_width=True,
            on_click=select_followup_row,
            args=(key,),
        )
        if is_selected:
            render_detail(row, user)
    st.markdown("</div>", unsafe_allow_html=True)


def select_followup_row(next_id: str) -> None:
    current_id = clean(st.session_state.get("followup_selected_id_v2"))
    save_followup_draft(current_id)
    st.session_state.followup_selected_id_v2 = "" if current_id == next_id else next_id


def save_followup_draft(row_id: str) -> None:
    if not row_id:
        return
    drafts = st.session_state.setdefault("followup_drafts_v2", {})
    field_keys = {
        "lead_status": f"followup_lead_status_{row_id}",
        "followup_status": f"followup_status_{row_id}",
        "priority": f"followup_priority_{row_id}",
        "next_followup_date": f"followup_next_date_{row_id}",
        "clear_date": f"followup_clear_date_{row_id}",
        "followup_note": f"followup_note_{row_id}",
    }
    draft = {}
    for field, state_key in field_keys.items():
        if state_key in st.session_state:
            draft[field] = st.session_state[state_key]
    if draft:
        drafts[row_id] = draft


def render_detail(row: dict, user: dict) -> None:
    key = row_key(row)
    prepare_followup_form_state(key, row)
    st.markdown('<div class="crm-inline-detail-title">รายละเอียด Follow-up</div>', unsafe_allow_html=True)
    with st.form(f"followup_save_v2_{key}"):
        c1, c2, c3 = st.columns(3)
        lead_status = c1.selectbox("สถานะลูกค้า", list(LEAD_STATUS_OPTIONS.keys()), format_func=lead_label, key=f"followup_lead_status_{key}")
        followup_status = c2.selectbox("สถานะติดตาม", list(FOLLOWUP_STATUS_OPTIONS.keys()), format_func=followup_label, key=f"followup_status_{key}")
        priority = c3.selectbox("ความสำคัญ", list(PRIORITY_OPTIONS.keys()), format_func=priority_label, key=f"followup_priority_{key}")
        next_date = st.date_input("วันนัดติดตาม", key=f"followup_next_date_{key}")
        clear_date = st.checkbox("ล้างวันที่", key=f"followup_clear_date_{key}")
        note = st.text_area("โน้ตติดตาม", height=110, key=f"followup_note_{key}")
        submitted = st.form_submit_button("บันทึก Follow-up", use_container_width=True)
    if submitted:
        selected_date = None if clear_date or not next_date else next_date.isoformat()
        payload = {
            "customer_key": clean(row.get("customer_key")),
            "crm_data_import_id": clean(row.get("crm_data_import_id")),
            "order_id": clean(row.get("order_id")),
            "customer_id": clean(row.get("crm_data_import_id")),
            "customer_name": clean(row.get("customer_name")),
            "phone_key": clean(row.get("phone1")) or clean(row.get("phone2")),
            "phone1": clean(row.get("phone1")),
            "phone2": clean(row.get("phone2")),
            "product_name": clean(row.get("product_name")),
            "sku": clean(row.get("sku")),
            "url": clean(row.get("url")),
            "staff_code": clean(row.get("staff_code")),
            "owner": clean(row.get("owner")),
            "lead_status": lead_status,
            "followup_status": followup_status,
            "next_followup_date": selected_date,
            "followup_note": note,
            "follow_up_status": followup_status,
            "follow_up_date": selected_date,
            "follow_up_note": note,
            "priority": priority,
            "updated_by": clean(user.get("email")),
            "updated_at": datetime.utcnow().isoformat() + "Z",
        }
        upsert_lead_followup(payload)
        st.session_state.setdefault("followup_drafts_v2", {}).pop(key, None)
        st.cache_data.clear()
        st.success("บันทึก Follow-up แล้ว")
        st.rerun()


def prepare_followup_form_state(key: str, row: dict) -> None:
    draft = st.session_state.setdefault("followup_drafts_v2", {}).get(key, {})
    defaults = {
        f"followup_lead_status_{key}": draft.get("lead_status", clean(row.get("lead_status")) or "new"),
        f"followup_status_{key}": draft.get("followup_status", clean(row.get("followup_status")) or "none"),
        f"followup_priority_{key}": draft.get("priority", clean(row.get("priority")) or "normal"),
        f"followup_next_date_{key}": draft.get("next_followup_date", parse_date(row.get("next_followup_date"))),
        f"followup_clear_date_{key}": draft.get("clear_date", False),
        f"followup_note_{key}": draft.get("followup_note", clean(row.get("followup_note"))),
    }
    for state_key, value in defaults.items():
        if state_key not in st.session_state:
            st.session_state[state_key] = value


def priority_badge(value: str) -> str:
    tones = {"urgent": "red", "high": "orange", "normal": "yellow", "low": "gray"}
    return badge(priority_label(value), tones.get(value, "gray"))


def lead_label(value: str) -> str:
    return ALL if value == ALL else LEAD_STATUS_OPTIONS.get(value, value)


def followup_label(value: str) -> str:
    return ALL if value == ALL else FOLLOWUP_STATUS_OPTIONS.get(value, value)


def priority_label(value: str) -> str:
    return ALL if value == ALL else PRIORITY_OPTIONS.get(value, value)


def row_key(row: dict) -> str:
    return clean(row.get("crm_data_import_id")) or clean(row.get("customer_key")) or clean(row.get("order_id")) or clean(row.get("phone1")) or clean(row.get("phone2"))


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


def normalize_phone(value) -> str:
    return "".join(ch for ch in clean(value) if ch.isdigit())


main()
