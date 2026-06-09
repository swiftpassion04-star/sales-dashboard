import html
from datetime import date, datetime

import streamlit as st

from auth_utils import current_user, require_login
from crm_theme import badge, render_page_header
from nav_utils import render_sidebar_nav
from neon_utils import (
    fetch_followup_filter_options,
    fetch_followup_page,
    fetch_product_options,
    upsert_lead_followup,
    upsert_manual_order_items,
)
from permissions import can_view_followup, can_view_followup_owner_filter


PAGE_SIZE_OPTIONS = [10, 25, 50, 100]
PRODUCT_PLACEHOLDER = "เลือกสินค้า"
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
    inject_followup_dialog_css()
    require_login()
    user = current_user() or {}
    if not can_view_followup(user):
        st.warning("หน้านี้ใช้ได้เฉพาะ EDITOR และพนักงานที่ดูแลลูกค้า")
        st.stop()

    render_page_header("ติดตามลูกค้า", "จัดการ Lead และ Follow-up จาก Neon เท่านั้น")
    render_followup_page_message()
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


def inject_followup_dialog_css() -> None:
    st.markdown(
        """
<style>
div[role="dialog"] {
  background:#FFF8F0 !important;
  border:8px solid #EA580C !important;
  border-radius:24px !important;
  color:#1F2937 !important;
  box-shadow:0 18px 45px rgba(124,45,18,.28) !important;
}
div[role="dialog"] [data-testid="stDialogContent"],
div[role="dialog"] [data-testid="stVerticalBlock"],
div[role="dialog"] [data-testid="stForm"] {
  background:#FFFFFF !important;
  color:#1F2937 !important;
}
div[role="dialog"] h1,
div[role="dialog"] h2,
div[role="dialog"] h3,
div[role="dialog"] p,
div[role="dialog"] label,
div[role="dialog"] span,
div[role="dialog"] div {
  color:#1F2937;
}
div[role="dialog"] [data-testid="stForm"] {
  border:1px solid #FDBA74 !important;
  border-radius:18px !important;
  padding:16px !important;
}
div[role="dialog"] input,
div[role="dialog"] textarea,
div[role="dialog"] div[data-baseweb="select"] > div,
div[role="dialog"] div[data-baseweb="input"] > div {
  background:#FFFFFF !important;
  color:#1F2937 !important;
  -webkit-text-fill-color:#1F2937 !important;
  border-color:#FDBA74 !important;
}
div[role="dialog"] button[aria-label="Close"] {
  color:#EA580C !important;
}
</style>
""",
        unsafe_allow_html=True,
    )


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
        if can_view_followup_owner_filter(user):
            owner = c5.selectbox("ผู้ดูแล", [ALL] + options.get("owners", []))
        keyword = st.text_input("ค้นหา", placeholder="เบอร์โทร / ชื่อลูกค้า / เลขคำสั่งซื้อ")
        submitted = st.form_submit_button("ค้นหา", use_container_width=True)
    if submitted:
        st.session_state.followup_page_v2 = 1
        close_followup_modal()
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
  <div class="crm-table-header" style="grid-template-columns:.85fr 1fr 1.35fr 1fr .8fr 1.2fr 1fr 1fr .9fr .8fr;">
    <div class="crm-table-cell">ติดตาม</div>
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
        detail_url = customer_detail_url(row)
        st.markdown(
            f"""
<div class="crm-table-row" style="grid-template-columns:.85fr 1fr 1.35fr 1fr .8fr 1.2fr 1fr 1fr .9fr .8fr;">
  <div class="crm-table-cell"><a class="crm-link crm-outline-link" href="{html.escape(detail_url, quote=True)}" target="_blank">ติดตาม</a></div>
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
        st.session_state.followup_page_success = "บันทึกสำเร็จแล้ว"
        close_followup_modal()
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


def customer_detail_url(row: dict) -> str:
    customer_id = clean(row.get("customer_id")) or clean(row.get("crm_data_import_id")) or row_key(row)
    return f"customer_detail?customer_id={html.escape(customer_id, quote=True)}"


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


def render_followup_table(rows: list[dict], user: dict) -> None:
    header = st.columns([0.8, 1.05, 1.0, 1.25, 1.0, 0.75, 1.2, 1.0, 1.0, 0.9, 0.8])
    labels = ["ติดตาม", "เพิ่มคำสั่งซื้อ", "วันนัด", "ชื่อลูกค้า", "เบอร์โทร", "SKU", "สินค้า", "สถานะลูกค้า", "สถานะติดตาม", "ความสำคัญ", "URL"]
    for col, label in zip(header, labels):
        col.markdown(f"**{label}**")

    for row in rows:
        key = row_key(row)
        url = clean(row.get("url"))
        cols = st.columns([0.8, 1.05, 1.0, 1.25, 1.0, 0.75, 1.2, 1.0, 1.0, 0.9, 0.8])
        if cols[0].button("ติดตาม", key=f"followup_popup_{key}", use_container_width=True):
            st.session_state.followup_modal_type = "followup"
            st.session_state.followup_modal_row = dict(row)
            st.rerun()
        if cols[1].button("เพิ่มคำสั่งซื้อ", key=f"order_popup_{key}", use_container_width=True):
            st.session_state.followup_modal_type = "order"
            st.session_state.followup_modal_row = dict(row)
            st.rerun()
        cols[2].write(clean(row.get("next_followup_date")) or "ว่าง")
        cols[3].write(clean(row.get("customer_name")) or "-")
        cols[4].write(clean(row.get("phone1")) or clean(row.get("phone2")) or "-")
        cols[5].write(clean(row.get("sku")) or "-")
        cols[6].write(clean(row.get("product_name")) or "-")
        cols[7].markdown(badge(lead_label(clean(row.get("lead_status")) or "new"), "blue"), unsafe_allow_html=True)
        cols[8].markdown(badge(followup_label(clean(row.get("followup_status")) or "none"), "gray"), unsafe_allow_html=True)
        cols[9].markdown(priority_badge(clean(row.get("priority")) or "normal"), unsafe_allow_html=True)
        if url:
            cols[10].markdown(f"[เปิดลิงก์]({url})")
        else:
            cols[10].write("-")

    modal_row = st.session_state.get("followup_modal_row")
    modal_type = clean(st.session_state.get("followup_modal_type"))
    if modal_row and modal_type == "followup":
        render_followup_dialog(dict(modal_row), user)
    elif modal_row and modal_type == "order":
        render_order_dialog(dict(modal_row), user)


def render_followup_page_message() -> None:
    message = clean(st.session_state.pop("followup_page_success", ""))
    if message:
        st.success(message)


def close_followup_modal() -> None:
    st.session_state.pop("followup_modal_type", None)
    st.session_state.pop("followup_modal_row", None)


@st.dialog("ติดตามลูกค้า", width="large")
def render_followup_dialog(row: dict, user: dict) -> None:
    render_popup_customer_summary(row)
    render_detail(row, user)


@st.dialog("เพิ่มคำสั่งซื้อ", width="large")
def render_order_dialog(row: dict, user: dict) -> None:
    key = row_key(row)
    prefix = f"followup_order_{key}"
    owner = clean(row.get("owner"))
    staff_code = clean(row.get("staff_code"))
    if not owner:
        st.error("รายการนี้ยังไม่มีผู้ดูแล จึงยังเพิ่มคำสั่งซื้อจาก popup นี้ไม่ได้")
        return
    prepare_popup_order_state(prefix, row)

    try:
        product_options = fetch_popup_product_options()
    except Exception as exc:
        product_options = []
        st.warning(f"โหลดรายการสินค้าไม่สำเร็จ: {exc}")

    with st.form(f"{prefix}_form", clear_on_submit=False):
        c1, c2 = st.columns(2)
        order_id = c1.text_input("หมายเลขคำสั่งซื้อ", key=f"{prefix}_order_id")
        customer_name = c2.text_input("ชื่อลูกค้า", key=f"{prefix}_customer_name")
        p1, p2 = st.columns(2)
        phone1 = p1.text_input("เบอร์โทร", key=f"{prefix}_phone1")
        phone2 = p2.text_input("เบอร์สำรอง", key=f"{prefix}_phone2")
        url = st.text_input("URL", key=f"{prefix}_url")
        address = st.text_area("ที่อยู่", key=f"{prefix}_address", height=90)
        sale_type = st.selectbox("ประเภทการขาย", ["NEW_ORDER", "UPSELL", "FOLLOW"], key=f"{prefix}_sale_type")
        st.text_input("ผู้ดูแล", value=owner, disabled=True, key=f"{prefix}_owner_locked")
        st.caption(f"วันที่สร้างคำสั่งซื้อ: {date.today().isoformat()}")

        st.markdown("#### รายการสินค้า")
        product_labels = [PRODUCT_PLACEHOLDER, *[popup_product_label(item) for item in product_options]]
        if st.session_state.pop(f"{prefix}_product_reset", False):
            st.session_state[f"{prefix}_product_select"] = PRODUCT_PLACEHOLDER
            st.session_state[f"{prefix}_product_qty"] = 1
            st.session_state[f"{prefix}_product_amount"] = 0.0
        if st.session_state.get(f"{prefix}_product_select") not in product_labels:
            st.session_state[f"{prefix}_product_select"] = PRODUCT_PLACEHOLDER
        pc1, pc2, pc3, pc4 = st.columns([2.2, 0.7, 0.8, 1.1])
        selected_label = pc1.selectbox("สินค้า", product_labels, key=f"{prefix}_product_select")
        selected_qty = pc2.number_input("จำนวน", min_value=1, value=1, step=1, key=f"{prefix}_product_qty")
        selected_amount = pc3.number_input("ราคา", min_value=0.0, value=0.0, step=1.0, key=f"{prefix}_product_amount")
        add_item = pc4.form_submit_button("เพิ่มสินค้าอีก 1 รายการ", use_container_width=True)
        delete_index = render_popup_order_items(prefix)
        submitted = st.form_submit_button("บันทึกคำสั่งซื้อ", use_container_width=True)

    if add_item:
        product = popup_product_from_label(product_options, selected_label)
        if not product:
            st.error("กรุณาเลือกสินค้า")
            return
        amount = 0.0 if sale_type == "FOLLOW" else float(selected_amount or 0)
        add_popup_order_item(prefix, product, int(selected_qty or 1), amount)
        st.session_state[f"{prefix}_product_reset"] = True
        st.rerun()
    if delete_index is not None:
        remove_popup_order_item(prefix, delete_index)
        st.rerun()
    if not submitted:
        return

    items = st.session_state.get(f"{prefix}_items", [])
    errors = []
    if not clean(order_id):
        errors.append("กรุณากรอกหมายเลขคำสั่งซื้อ")
    if not clean(customer_name):
        errors.append("กรุณากรอกชื่อลูกค้า")
    if not normalize_phone(phone1) and not normalize_phone(phone2):
        errors.append("กรุณากรอกเบอร์โทรหรือเบอร์สำรอง")
    if not items:
        errors.append("กรุณาเลือกสินค้าอย่างน้อย 1 รายการ")
    if errors:
        st.error(" / ".join(errors))
        return

    try:
        result = upsert_manual_order_items(
            {
                "order_id": order_id,
                "customer_name": customer_name,
                "phone1": phone1,
                "phone2": phone2,
                "url": url,
                "address": address,
                "sale_type": sale_type,
                "order_date": date.today().isoformat(),
                "owner": owner,
                "staff_code": staff_code,
                "force_owner_update": False,
                "uploaded_by": clean(user.get("email")),
                "updated_by": clean(user.get("email")),
            },
            items,
        )
    except Exception as exc:
        st.error(f"บันทึกคำสั่งซื้อไม่สำเร็จ: {exc}")
        return

    st.cache_data.clear()
    clear_popup_order_state(prefix, row)
    actions = result.get("actions") or {}
    st.session_state.followup_page_success = (
        "บันทึกสำเร็จแล้ว "
        f"สินค้า {result.get('item_count', 0)} รายการ "
        f"(เพิ่มใหม่ {actions.get('inserted', 0)}, อัปเดต {actions.get('updated', 0)})"
    )
    close_followup_modal()
    st.rerun()


def render_popup_customer_summary(row: dict) -> None:
    phone = clean(row.get("phone1")) or clean(row.get("phone2")) or "-"
    url = clean(row.get("url"))
    url_html = f'<a class="crm-link" href="{html.escape(url, quote=True)}" target="_blank">เปิดลิงก์</a>' if url else "-"
    st.markdown(
        f"""
<div class="crm-card">
  <div style="display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px;">
    <div><div class="crm-muted">ชื่อลูกค้า</div><b>{html.escape(clean(row.get("customer_name")) or "-")}</b></div>
    <div><div class="crm-muted">เบอร์โทร</div><b>{html.escape(phone)}</b></div>
    <div><div class="crm-muted">URL</div><b>{url_html}</b></div>
    <div><div class="crm-muted">สินค้า</div><b>{html.escape(clean(row.get("product_name")) or "-")}</b></div>
    <div><div class="crm-muted">SKU</div><b>{html.escape(clean(row.get("sku")) or "-")}</b></div>
    <div><div class="crm-muted">ผู้ดูแล</div><b>{html.escape(clean(row.get("owner")) or "-")}</b></div>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )


def prepare_popup_order_state(prefix: str, row: dict) -> None:
    if st.session_state.get(f"{prefix}_ready"):
        return
    st.session_state[f"{prefix}_order_id"] = ""
    st.session_state[f"{prefix}_customer_name"] = clean(row.get("customer_name"))
    st.session_state[f"{prefix}_phone1"] = clean(row.get("phone1"))
    st.session_state[f"{prefix}_phone2"] = clean(row.get("phone2"))
    st.session_state[f"{prefix}_url"] = clean(row.get("url"))
    st.session_state[f"{prefix}_address"] = clean(row.get("address"))
    st.session_state[f"{prefix}_sale_type"] = "NEW_ORDER"
    st.session_state[f"{prefix}_product_select"] = PRODUCT_PLACEHOLDER
    st.session_state[f"{prefix}_product_qty"] = 1
    st.session_state[f"{prefix}_product_amount"] = 0.0
    st.session_state[f"{prefix}_items"] = []
    st.session_state[f"{prefix}_ready"] = True


def clear_popup_order_state(prefix: str, row: dict) -> None:
    for key in list(st.session_state.keys()):
        if key.startswith(prefix):
            del st.session_state[key]
    prepare_popup_order_state(prefix, row)


def fetch_popup_product_options() -> list[dict]:
    return [
        {
            "sku": clean(row.get("sku")),
            "product_name": clean(row.get("product_name")),
        }
        for row in fetch_product_options()
        if clean(row.get("sku")) and clean(row.get("product_name")) and bool(row.get("is_active"))
    ]


def popup_product_label(row: dict) -> str:
    return f"{clean(row.get('sku'))} - {clean(row.get('product_name'))}"


def popup_product_from_label(options: list[dict], label: str) -> dict:
    if label == PRODUCT_PLACEHOLDER:
        return {}
    for row in options:
        if popup_product_label(row) == label:
            return row
    return {}


def add_popup_order_item(prefix: str, product: dict, qty: int, amount: float) -> None:
    items = list(st.session_state.get(f"{prefix}_items", []))
    sku = clean(product.get("sku"))
    product_name = clean(product.get("product_name"))
    qty = max(1, int(qty or 1))
    amount = max(0.0, float(amount or 0))
    for item in items:
        if clean(item.get("sku")) == sku and clean(item.get("product_name")) == product_name:
            item["qty"] = int(item.get("qty") or 0) + qty
            item["amount"] = float(item.get("amount") or 0) + amount
            st.session_state[f"{prefix}_items"] = items
            return
    items.append({"sku": sku, "product_name": product_name, "qty": qty, "amount": amount})
    st.session_state[f"{prefix}_items"] = items


def remove_popup_order_item(prefix: str, index: int) -> None:
    items = list(st.session_state.get(f"{prefix}_items", []))
    if 0 <= index < len(items):
        items.pop(index)
    st.session_state[f"{prefix}_items"] = items


def render_popup_order_items(prefix: str) -> int | None:
    items = st.session_state.setdefault(f"{prefix}_items", [])
    if not items:
        st.info("ยังไม่มีรายการสินค้าในคำสั่งซื้อนี้")
        return None
    header = st.columns([0.8, 2.2, 0.6, 0.8, 0.6])
    for col, label in zip(header, ["SKU", "สินค้า", "จำนวน", "ราคา", "ลบ"]):
        col.markdown(f"**{label}**")
    delete_index = None
    for index, item in enumerate(items):
        cols = st.columns([0.8, 2.2, 0.6, 0.8, 0.6])
        cols[0].write(clean(item.get("sku")) or "-")
        cols[1].write(clean(item.get("product_name")) or "-")
        cols[2].write(int(item.get("qty") or 0))
        cols[3].write(f"{float(item.get('amount') or 0):,.2f}")
        if cols[4].form_submit_button("ลบ", key=f"{prefix}_delete_{index}", use_container_width=True):
            delete_index = index
    return delete_index


main()
