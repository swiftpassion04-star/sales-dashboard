import html
from datetime import date, datetime

import streamlit as st

from auth_utils import current_user, require_login
from crm_theme import badge, render_page_header
from nav_utils import render_sidebar_nav
import neon_utils as neon
from neon_utils import (
    FOLLOWUP_PRIORITY_OPTIONS,
    fetch_followup_filter_options,
    fetch_followup_page,
    fetch_existing_owner_rows_by_phones,
    fetch_order_product_options,
    normalize_followup_priority,
    upsert_lead_followup,
    upsert_manual_order_items,
    validate_phone_pair,
)
from permissions import can_manage_all, can_view_followup, can_view_followup_owner_filter
from ui.manual_order_ui import parse_price_input, parse_required_price_input
from ui.pagination import get_pagination_state, render_pagination
from ui.perf import perf_trace


PAGE_SIZE_OPTIONS = [10, 25, 50, 100, 500, 1000]
FOLLOWUP_TABLE_COLUMNS = [0.8, 1.0, 1.05, 2.05, 1.25, 0.8, 1.4, 1.5, 1.6, 0.85, 0.8]
PRODUCT_PLACEHOLDER = None
POPUP_PRODUCT_SELECTOR_PAGE_SIZE_OPTIONS = [10, 25, 50]
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
    "round_1": "ติดตามรอบ 1",
    "round_2": "ติดตามรอบ 2",
    "round_3": "ติดตามรอบ 3",
    "round_4": "ติดตามรอบ 4",
    "done": "ติดตามแล้ว",
    "missed": "เลยกำหนด",
}
PRIORITY_OPTIONS = {priority: priority for priority in FOLLOWUP_PRIORITY_OPTIONS}
FOLLOWUP_PRIORITY_TAB_OPTIONS = tuple(FOLLOWUP_PRIORITY_OPTIONS)

DATE_FILTER_OPTIONS = {
    "all": ALL,
    "today": "วันนี้",
    "single": "เลือกวัน",
    "range": "เลือกช่วงระหว่างวัน",
}
FOLLOWUP_FILTER_DEFAULTS = {
    "followup_filter_lead_status": ALL,
    "followup_filter_followup_status": ALL,
    "followup_filter_priority": ALL,
    "followup_filter_product": ALL,
    "followup_filter_owner": ALL,
    "followup_filter_keyword": "",
    "followup_filter_date_mode": "all",
}

st.set_page_config(page_title="Follow-up", layout="wide")


def main() -> None:
    with perf_trace("followup.page_render"):
        _render_followup_page()


def _render_followup_page() -> None:
    render_sidebar_nav()
    inject_followup_dialog_css()
    require_login()
    user = current_user() or {}
    if not can_view_followup(user):
        st.warning("หน้านี้ใช้ได้เฉพาะ EDITOR และพนักงานที่ดูแลลูกค้า")
        st.stop()

    render_page_header("ติดตามลูกค้า", "จัดการ Lead และ Follow-up จาก Neon เท่านั้น")
    render_followup_page_message()
    render_priority_tabs()
    filters = render_filters(user)
    page_size, page = get_pagination_state(
        key_prefix="followup",
        page_size_options=PAGE_SIZE_OPTIONS,
        page_key="followup_page_v2",
        page_size_key="followup_page_size_v2",
    )

    with st.spinner("กำลังโหลดรายการติดตาม..."):
        with perf_trace(
            "followup.fetch_page",
            page=page,
            page_size=page_size,
            role=user.get("role"),
        ):
            rows, total = fetch_followup_page(filters, user, page_size, page)

    page_size, page = render_pagination(
        total_rows=total,
        page_size=page_size,
        current_page=page,
        key_prefix="followup",
        page_size_options=PAGE_SIZE_OPTIONS,
        page_key="followup_page_v2",
        page_size_key="followup_page_size_v2",
    )
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
.st-key-followup_table_header_v2 [data-testid="stHorizontalBlock"] {
  background:#FFE8D2;
  border:2px solid #F97316;
  border-bottom:1px solid #F97316;
  border-radius:16px 16px 0 0;
  overflow:hidden;
  box-shadow:0 10px 22px rgba(249, 115, 22, 0.16);
  min-height:58px;
}
.st-key-followup_table_header_v2,
[class*="st-key-followup_table_row_"] {
  width:min(1620px, calc(100vw - 310px));
  max-width:none;
  margin-left:50%;
  transform:translateX(-50%);
}
.st-key-followup_table_header_v2 {
  position:sticky;
  top:58px;
  z-index:80;
  background:#FFF8F0;
  padding-top:12px;
  margin-top:14px;
}
.st-key-followup_table_header_v2::before {
  content:"";
  position:absolute;
  inset:-18px 0 auto 0;
  height:18px;
  background:#FFF8F0;
}
.st-key-followup_table_header_v2 [data-testid="column"],
[class*="st-key-followup_table_row_"] [data-testid="column"] {
  min-height:62px;
  padding:10px 12px;
  display:flex;
  align-items:center;
}
.st-key-followup_table_header_v2 p,
[class*="st-key-followup_table_row_"] p {
  margin:0;
  line-height:1.45;
  width:100%;
}
.st-key-followup_table_header_v2 p {
  color:#7C2D12 !important;
  font-weight:800 !important;
  white-space:normal;
  text-align:center;
}
/* วันนัด / เบอร์โทร / SKU: keep on one line and centered for quick scanning */
.st-key-followup_table_header_v2 [data-testid="column"]:nth-child(3),
.st-key-followup_table_header_v2 [data-testid="column"]:nth-child(5),
.st-key-followup_table_header_v2 [data-testid="column"]:nth-child(6),
[class*="st-key-followup_table_row_"] [data-testid="column"]:nth-child(3),
[class*="st-key-followup_table_row_"] [data-testid="column"]:nth-child(5),
[class*="st-key-followup_table_row_"] [data-testid="column"]:nth-child(6) {
  justify-content:center;
}
[class*="st-key-followup_table_row_"] [data-testid="column"]:nth-child(3) p,
[class*="st-key-followup_table_row_"] [data-testid="column"]:nth-child(5) p,
[class*="st-key-followup_table_row_"] [data-testid="column"]:nth-child(6) p {
  white-space:nowrap;
  text-align:center;
  font-variant-numeric:tabular-nums;
}
[class*="st-key-followup_table_row_"] [data-testid="stHorizontalBlock"] {
  border-left:1px solid #FB923C;
  border-right:1px solid #FB923C;
  border-bottom:1px solid #FB923C;
  overflow:hidden;
}
[class*="st-key-followup_table_row_even_"] [data-testid="stHorizontalBlock"] {
  background:#FFFFFF;
}
[class*="st-key-followup_table_row_odd_"] [data-testid="stHorizontalBlock"] {
  background:#FFF6EC;
}
[class*="st-key-followup_table_row_"] [data-testid="stHorizontalBlock"]:hover {
  background:#FFF0DD;
}
[class*="st-key-followup_table_row_"] .stButton > button {
  min-height:38px;
  white-space:nowrap;
}
</style>
""",
        unsafe_allow_html=True,
    )


def reset_followup_filter_state() -> None:
    for key, value in FOLLOWUP_FILTER_DEFAULTS.items():
        st.session_state[key] = value
    today = date.today()
    st.session_state['followup_filter_single_date'] = today
    st.session_state['followup_filter_date_range'] = (today, today)


def render_priority_tabs() -> None:
    st.markdown("#### ความสำคัญ")
    cols = st.columns(len(FOLLOWUP_PRIORITY_TAB_OPTIONS))
    current_priority = clean(st.session_state.get("followup_filter_priority"))
    if current_priority and current_priority != ALL:
        current_priority = normalize_followup_priority(current_priority)
    for col, priority in zip(cols, FOLLOWUP_PRIORITY_TAB_OPTIONS):
        button_type = "primary" if current_priority == priority else "secondary"
        if col.button(
            priority,
            key=f"followup_priority_tab_{priority.lower().replace(' ', '_')}",
            type=button_type,
            use_container_width=True,
        ):
            set_followup_priority_filter_from_tab(priority)
            st.rerun()


def set_followup_priority_filter_from_tab(priority: str) -> None:
    st.session_state["followup_filter_priority"] = normalize_followup_priority(priority)
    st.session_state.followup_page_v2 = 1
    close_followup_modal()


def date_filter_label(value: str) -> str:
    return DATE_FILTER_OPTIONS.get(value, value)


def resolve_followup_date_filter(date_mode: str) -> tuple[str, str]:
    today = date.today()
    if date_mode == 'today':
        return today.isoformat(), today.isoformat()
    if date_mode == 'single':
        selected = st.session_state.get('followup_filter_single_date') or today
        return selected.isoformat(), selected.isoformat()
    if date_mode == 'range':
        selected_range = st.session_state.get('followup_filter_date_range') or (today, today)
        if isinstance(selected_range, tuple):
            dates = [selected for selected in selected_range if selected]
        else:
            dates = [selected_range] if selected_range else []
        if not dates:
            return '', ''
        if len(dates) == 1:
            start_date = end_date = dates[0]
        else:
            start_date, end_date = sorted(dates[:2])
        return start_date.isoformat(), end_date.isoformat()
    return '', ''


def render_filters(user: dict) -> dict[str, str]:
    if st.session_state.pop('followup_filter_reset_requested', False):
        reset_followup_filter_state()
    current_priority = st.session_state.get("followup_filter_priority")
    if current_priority and current_priority != ALL:
        st.session_state["followup_filter_priority"] = normalize_followup_priority(current_priority)
    try:
        with perf_trace("followup.fetch_filter_options", role=user.get("role")):
            options = fetch_followup_filter_options(user)
    except Exception:
        options = {'owners': [], 'products': []}
    with st.form('followup_filters_v2'):
        c1, c2, c3 = st.columns(3)
        lead_status = c1.selectbox('สถานะลูกค้า', [ALL] + list(LEAD_STATUS_OPTIONS.keys()), format_func=lead_label, key='followup_filter_lead_status')
        followup_status = c2.selectbox('สถานะติดตาม', [ALL] + list(FOLLOWUP_STATUS_OPTIONS.keys()), format_func=followup_label, key='followup_filter_followup_status')
        priority = c3.selectbox('ความสำคัญ', [ALL] + list(PRIORITY_OPTIONS.keys()), format_func=priority_label, key='followup_filter_priority')
        c4, c5 = st.columns(2)
        product = c4.selectbox('สินค้า / SKU', [ALL] + options.get('products', []), key='followup_filter_product')
        owner = ALL
        if can_view_followup_owner_filter(user):
            owner = c5.selectbox('ผู้ดูแล', [ALL] + options.get('owners', []), key='followup_filter_owner')
        else:
            st.session_state['followup_filter_owner'] = ALL

        date_mode = st.selectbox('วันที่นัด', list(DATE_FILTER_OPTIONS.keys()), format_func=date_filter_label, key='followup_filter_date_mode')
        if date_mode == 'single':
            st.date_input('เลือกวันที่นัด', key='followup_filter_single_date')
        elif date_mode == 'range':
            st.date_input('เลือกช่วงวันที่นัด', key='followup_filter_date_range')

        keyword = st.text_input('ค้นหา', placeholder='เบอร์โทร / ชื่อลูกค้า / เลขคำสั่งซื้อ', key='followup_filter_keyword')
        search_col, reset_col = st.columns([3, 1])
        submitted = search_col.form_submit_button('ค้นหา', use_container_width=True)
        reset_submitted = reset_col.form_submit_button('รีเฟรช / ล้างตัวกรอง', use_container_width=True)
    if reset_submitted:
        st.session_state.followup_page_v2 = 1
        st.session_state['followup_filter_reset_requested'] = True
        close_followup_modal()
        st.rerun()
    if submitted:
        st.session_state.followup_page_v2 = 1
        close_followup_modal()
    date_start, date_end = resolve_followup_date_filter(date_mode)
    return {
        'lead_status': lead_status,
        'followup_status': followup_status,
        'priority': priority,
        'product': product,
        'owner': owner,
        'phone': normalize_phone(keyword),
        'keyword': keyword,
        'date_mode': date_mode,
        'date_start': date_start,
        'date_end': date_end,
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
        with perf_trace(
            "followup.save_followup",
            action="save",
            role=user.get("role"),
        ):
            upsert_lead_followup(payload)
        st.session_state.setdefault("followup_drafts_v2", {}).pop(key, None)
        with perf_trace("followup.clear_caches", action="save_followup"):
            clear_cached_functions_safely(fetch_followup_filter_options)
        st.session_state.followup_page_success = "บันทึกสำเร็จแล้ว"
        close_followup_modal()
        with perf_trace("followup.rerun", action="save_followup"):
            st.rerun()


def prepare_followup_form_state(key: str, row: dict) -> None:
    draft = st.session_state.setdefault("followup_drafts_v2", {}).get(key, {})
    defaults = {
        f"followup_lead_status_{key}": draft.get("lead_status", clean(row.get("lead_status")) or "new"),
        f"followup_status_{key}": draft.get("followup_status", clean(row.get("followup_status")) or "none"),
        f"followup_priority_{key}": normalize_followup_priority(draft.get("priority", clean(row.get("priority")))),
        f"followup_next_date_{key}": draft.get("next_followup_date", parse_date(row.get("next_followup_date"))),
        f"followup_clear_date_{key}": draft.get("clear_date", False),
        f"followup_note_{key}": draft.get("followup_note", clean(row.get("followup_note"))),
    }
    for state_key, value in defaults.items():
        if state_key not in st.session_state:
            st.session_state[state_key] = value


def priority_badge(value: str) -> str:
    priority = normalize_followup_priority(value)
    tones = {
        "Super VIP": "red",
        "VIP": "orange",
        "Premium": "blue",
        "Economy": "gray",
        "NEW": "yellow",
        "Dismiss": "gray",
    }
    return badge(priority_label(priority), tones.get(priority, "gray"))


def lead_label(value: str) -> str:
    return ALL if value == ALL else LEAD_STATUS_OPTIONS.get(value, value)


def followup_label(value: str) -> str:
    return ALL if value == ALL else FOLLOWUP_STATUS_OPTIONS.get(value, value)


def priority_label(value: str) -> str:
    return ALL if value == ALL else normalize_followup_priority(value)


def followup_option_or_default(value: str, options: dict, default: str) -> str:
    text = clean(value)
    return text if text in options else default


def serialize_popup_followup_date(value) -> tuple[str | None, str]:
    if value in (None, ""):
        return None, ""
    if isinstance(value, date):
        return value.isoformat(), ""
    parsed = parse_date(value)
    if parsed:
        return parsed.isoformat(), ""
    return None, "\u0e27\u0e31\u0e19\u0e17\u0e35\u0e48\u0e19\u0e31\u0e14\u0e44\u0e21\u0e48\u0e16\u0e39\u0e01\u0e15\u0e49\u0e2d\u0e07"


def build_popup_followup_payload(row: dict, user: dict, prefix: str) -> tuple[dict, list[str]]:
    lead_status = clean(st.session_state.get(f"{prefix}_lead_status"))
    followup_status = clean(st.session_state.get(f"{prefix}_followup_status"))
    priority = clean(st.session_state.get(f"{prefix}_priority"))
    followup_note = clean(st.session_state.get(f"{prefix}_followup_note"))
    next_followup_date, date_error = serialize_popup_followup_date(
        st.session_state.get(f"{prefix}_next_followup_date")
    )
    errors = []
    if lead_status not in LEAD_STATUS_OPTIONS:
        errors.append("\u0e2a\u0e16\u0e32\u0e19\u0e30\u0e25\u0e39\u0e01\u0e04\u0e49\u0e32\u0e44\u0e21\u0e48\u0e16\u0e39\u0e01\u0e15\u0e49\u0e2d\u0e07")
    if followup_status not in FOLLOWUP_STATUS_OPTIONS:
        errors.append("\u0e2a\u0e16\u0e32\u0e19\u0e30\u0e15\u0e34\u0e14\u0e15\u0e32\u0e21\u0e44\u0e21\u0e48\u0e16\u0e39\u0e01\u0e15\u0e49\u0e2d\u0e07")
    if priority not in FOLLOWUP_PRIORITY_OPTIONS:
        errors.append("\u0e04\u0e27\u0e32\u0e21\u0e2a\u0e33\u0e04\u0e31\u0e0d\u0e44\u0e21\u0e48\u0e16\u0e39\u0e01\u0e15\u0e49\u0e2d\u0e07")
    if date_error:
        errors.append(date_error)
    phone1 = clean(st.session_state.get(f"{prefix}_phone1"))
    phone2 = clean(st.session_state.get(f"{prefix}_phone2"))
    payload = {
        "customer_key": clean(row.get("customer_key")),
        "crm_data_import_id": clean(row.get("crm_data_import_id")),
        "order_id": clean(row.get("order_id")),
        "customer_id": clean(row.get("crm_data_import_id")),
        "customer_name": clean(st.session_state.get(f"{prefix}_customer_name")),
        "phone_key": phone1 or phone2,
        "phone1": phone1,
        "phone2": phone2,
        "product_name": clean(row.get("product_name")),
        "sku": clean(row.get("sku")),
        "url": clean(st.session_state.get(f"{prefix}_url")),
        "staff_code": clean(row.get("staff_code")),
        "owner": clean(row.get("owner")),
        "lead_status": lead_status,
        "followup_status": followup_status,
        "next_followup_date": next_followup_date,
        "followup_note": followup_note,
        "follow_up_status": followup_status,
        "follow_up_date": next_followup_date,
        "follow_up_note": followup_note,
        "priority": priority,
        "updated_by": clean(user.get("email")),
        "updated_at": datetime.utcnow().isoformat() + "Z",
    }
    return payload, errors


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


def format_followup_date_display(value) -> str:
    parsed = parse_date(value)
    if not parsed:
        return "ว่าง"
    return parsed.strftime("%d/%m/%Y")


def clean(value) -> str:
    return str(value or "").strip()


def normalize_phone(value) -> str:
    return "".join(ch for ch in clean(value) if ch.isdigit())


def render_followup_table(rows: list[dict], user: dict) -> None:
    with st.container(key="followup_table_header_v2"):
        header = st.columns(FOLLOWUP_TABLE_COLUMNS)
    labels = ["ติดตาม", "เพิ่มคำสั่งซื้อ", "วันนัด", "ชื่อลูกค้า", "เบอร์โทร", "SKU", "สินค้า", "สถานะลูกค้า", "สถานะติดตาม", "ความสำคัญ", "URL"]
    for col, label in zip(header, labels):
        col.markdown(f"**{label}**")

    for index, row in enumerate(rows):
        key = row_key(row)
        url = clean(row.get("url"))
        safe_key = "".join(ch if ch.isalnum() else "_" for ch in key)[:60] or str(index)
        row_tone = "even" if index % 2 == 0 else "odd"
        with st.container(key=f"followup_table_row_{row_tone}_{index}_{safe_key}"):
            cols = st.columns(FOLLOWUP_TABLE_COLUMNS)
        if cols[0].button("ติดตาม", key=f"followup_popup_{key}", use_container_width=True):
            with perf_trace("followup.open_popup", action="followup", role=user.get("role")):
                st.session_state.followup_modal_type = "followup"
                st.session_state.followup_modal_row = dict(row)
                st.rerun()
        if cols[1].button("เพิ่มคำสั่งซื้อ", key=f"order_popup_{key}", use_container_width=True):
            with perf_trace("followup.open_popup", action="order", role=user.get("role")):
                st.session_state.followup_modal_type = "order"
                st.session_state.followup_modal_row = dict(row)
                st.rerun()
        cols[2].write(format_followup_date_display(row.get("next_followup_date")))
        cols[3].write(clean(row.get("customer_name")) or "-")
        cols[4].write(clean(row.get("phone1")) or clean(row.get("phone2")) or "-")
        cols[5].write(clean(row.get("sku")) or "-")
        cols[6].write(clean(row.get("product_name")) or "-")
        cols[7].markdown(badge(lead_label(clean(row.get("lead_status")) or "new"), "blue"), unsafe_allow_html=True)
        cols[8].markdown(badge(followup_label(clean(row.get("followup_status")) or "none"), "gray"), unsafe_allow_html=True)
        cols[9].markdown(priority_badge(row.get("priority")), unsafe_allow_html=True)
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


def clear_cached_functions_safely(*functions) -> None:
    clear_many = getattr(neon, "clear_cached_data_functions", None)
    if callable(clear_many):
        clear_many(*functions)
        return
    for function in functions:
        clear = getattr(function, "clear", None)
        if callable(clear):
            clear()


@st.dialog("ติดตามลูกค้า", width="large")
def render_followup_dialog(row: dict, user: dict) -> None:
    with perf_trace("followup.dialog_render", action="followup", role=user.get("role")):
        _render_followup_dialog(row, user)


def _render_followup_dialog(row: dict, user: dict) -> None:
    render_popup_customer_summary(row)
    render_detail(row, user)


@st.dialog("เพิ่มคำสั่งซื้อ", width="large")
def render_order_dialog(row: dict, user: dict) -> None:
    with perf_trace("followup.dialog_render", action="order", role=user.get("role")):
        _render_order_dialog(row, user)


def _render_order_dialog(row: dict, user: dict) -> None:
    key = row_key(row)
    prefix = f"followup_order_{key}"
    owner = clean(row.get("owner"))
    staff_code = clean(row.get("staff_code"))
    if not owner:
        st.error("รายการนี้ยังไม่มีผู้ดูแล จึงยังเพิ่มคำสั่งซื้อจาก popup นี้ไม่ได้")
        return
    prepare_popup_order_state(prefix, row)

    try:
        with perf_trace("followup.load_product_options", action="order"):
            product_options = fetch_popup_product_options()
    except Exception as exc:
        product_options = []
        st.warning(f"โหลดรายการสินค้าไม่สำเร็จ: {exc}")

    st.markdown("#### \u0e02\u0e49\u0e2d\u0e21\u0e39\u0e25\u0e15\u0e34\u0e14\u0e15\u0e32\u0e21\u0e25\u0e39\u0e01\u0e04\u0e49\u0e32")
    followup_status_cols = st.columns(2)
    followup_status_cols[0].selectbox(
        "\u0e2a\u0e16\u0e32\u0e19\u0e30\u0e25\u0e39\u0e01\u0e04\u0e49\u0e32",
        list(LEAD_STATUS_OPTIONS.keys()),
        format_func=lead_label,
        key=f"{prefix}_lead_status",
    )
    followup_status_cols[1].selectbox(
        "\u0e2a\u0e16\u0e32\u0e19\u0e30\u0e15\u0e34\u0e14\u0e15\u0e32\u0e21",
        list(FOLLOWUP_STATUS_OPTIONS.keys()),
        format_func=followup_label,
        key=f"{prefix}_followup_status",
    )
    followup_meta_cols = st.columns(2)
    followup_meta_cols[0].selectbox(
        "\u0e04\u0e27\u0e32\u0e21\u0e2a\u0e33\u0e04\u0e31\u0e0d",
        list(PRIORITY_OPTIONS.keys()),
        format_func=priority_label,
        key=f"{prefix}_priority",
    )
    followup_meta_cols[1].date_input("\u0e27\u0e31\u0e19\u0e17\u0e35\u0e48\u0e19\u0e31\u0e14", key=f"{prefix}_next_followup_date")
    st.text_area(
        "\u0e42\u0e19\u0e49\u0e15\u0e15\u0e34\u0e14\u0e15\u0e32\u0e21",
        key=f"{prefix}_followup_note",
        height=100,
    )
    st.caption(
        "\u0e2b\u0e32\u0e01\u0e41\u0e01\u0e49\u0e44\u0e02\u0e02\u0e49\u0e2d\u0e21\u0e39\u0e25\u0e43\u0e19\u0e2a\u0e48\u0e27\u0e19\u0e19\u0e35\u0e49 \u0e23\u0e30\u0e1a\u0e1a\u0e08\u0e30\u0e43\u0e0a\u0e49\u0e2a\u0e33\u0e2b\u0e23\u0e31\u0e1a\u0e2d\u0e31\u0e1b\u0e40\u0e14\u0e15\u0e02\u0e49\u0e2d\u0e21\u0e39\u0e25\u0e15\u0e34\u0e14\u0e15\u0e32\u0e21\u0e2b\u0e25\u0e31\u0e07\u0e1a\u0e31\u0e19\u0e17\u0e36\u0e01\u0e04\u0e33\u0e2a\u0e31\u0e48\u0e07\u0e0b\u0e37\u0e49\u0e2d\u0e43\u0e19\u0e40\u0e1f\u0e2a\u0e16\u0e31\u0e14\u0e44\u0e1b"
    )

    c1, c2 = st.columns(2)
    order_id = c1.text_input("หมายเลขคำสั่งซื้อ", key=f"{prefix}_order_id")
    customer_name = c2.text_input("ชื่อลูกค้า", key=f"{prefix}_customer_name")
    p1, p2 = st.columns(2)
    phone1 = p1.text_input("เบอร์โทร", key=f"{prefix}_phone1")
    phone2 = p2.text_input("เบอร์สำรอง", key=f"{prefix}_phone2")
    url = st.text_input("URL", key=f"{prefix}_url")
    address = st.text_area("ที่อยู่", key=f"{prefix}_address", height=90)
    sale_type = st.selectbox("ประเภทการขาย", ["NEW_ORDER", "UPSELL", "FOLLOW", "⭐NEW_ORDER", "⭐UPSELL"], key=f"{prefix}_sale_type")
    st.text_input("ผู้ดูแล", value=owner, disabled=True, key=f"{prefix}_owner_locked")
    st.caption(f"วันที่สร้างคำสั่งซื้อ: {date.today().isoformat()}")

    product_heading, product_action = st.columns([3.0, 1.0], vertical_alignment="center")
    product_heading.markdown("#### \u0e23\u0e32\u0e22\u0e01\u0e32\u0e23\u0e2a\u0e34\u0e19\u0e04\u0e49\u0e32")
    open_product_selector = product_action.button(
        "+ \u0e40\u0e1e\u0e34\u0e48\u0e21\u0e2a\u0e34\u0e19\u0e04\u0e49\u0e32",
        key=f"{prefix}_open_product_picker",
        use_container_width=True,
    )
    delete_index = render_popup_order_items(prefix)
    submitted = st.button(
        "บันทึกคำสั่งซื้อ",
        key=f"{prefix}_submit_order",
        use_container_width=True,
    )

    if open_product_selector:
        st.session_state[popup_product_picker_state_key(prefix, "open")] = True
        st.rerun()

    render_popup_product_picker(product_options, prefix)

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
    errors.extend(validate_phone_pair(phone1, phone2))
    if not items:
        errors.append("กรุณาเลือกสินค้าอย่างน้อย 1 รายการ")
    price_error = False
    for item in items:
        price_ok, parsed_amount, _price_error = parse_required_price_input(item.get("amount"))
        if not price_ok:
            price_error = True
            break
        item["amount"] = parsed_amount
    if price_error:
        errors.append("\u0e01\u0e23\u0e38\u0e13\u0e32\u0e01\u0e23\u0e2d\u0e01\u0e23\u0e32\u0e04\u0e32\u0e2a\u0e34\u0e19\u0e04\u0e49\u0e32\u0e43\u0e2b\u0e49\u0e04\u0e23\u0e1a\u0e17\u0e38\u0e01\u0e23\u0e32\u0e22\u0e01\u0e32\u0e23")
    if errors:
        st.error(" / ".join(errors))
        return

    if not can_manage_all(user):
        owner_conflict = find_popup_order_owner_conflict(phone1, phone2, user, staff_code)
        if owner_conflict:
            conflict_owner = clean(owner_conflict.get("owner")) or clean(owner_conflict.get("staff_code")) or "-"
            st.error(f"มีผู้ดูแลแล้ว: {conflict_owner}")
            return

    try:
        with perf_trace(
            "followup.save_order",
            action="save",
            count=len(items),
            role=user.get("role"),
            sale_type=sale_type,
        ):
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

    duplicate_lock_warning = neon.clean(result.get("duplicate_lock_warning"))
    if duplicate_lock_warning:
        st.warning(duplicate_lock_warning)

    followup_payload, followup_update_errors = build_popup_followup_payload(row, user, prefix)
    if followup_update_errors:
        st.error(
            "\u0e1a\u0e31\u0e19\u0e17\u0e36\u0e01\u0e04\u0e33\u0e2a\u0e31\u0e48\u0e07\u0e0b\u0e37\u0e49\u0e2d\u0e41\u0e25\u0e49\u0e27 \u0e41\u0e15\u0e48\u0e02\u0e49\u0e2d\u0e21\u0e39\u0e25\u0e15\u0e34\u0e14\u0e15\u0e32\u0e21\u0e44\u0e21\u0e48\u0e16\u0e39\u0e01\u0e2d\u0e31\u0e1b\u0e40\u0e14\u0e15: "
            + " / ".join(followup_update_errors)
        )
        return
    try:
        with perf_trace("followup.update_after_order", action="save_order"):
            upsert_lead_followup(followup_payload)
    except Exception as exc:
        st.error(f"\u0e1a\u0e31\u0e19\u0e17\u0e36\u0e01\u0e04\u0e33\u0e2a\u0e31\u0e48\u0e07\u0e0b\u0e37\u0e49\u0e2d\u0e41\u0e25\u0e49\u0e27 \u0e41\u0e15\u0e48\u0e2d\u0e31\u0e1b\u0e40\u0e14\u0e15\u0e02\u0e49\u0e2d\u0e21\u0e39\u0e25\u0e15\u0e34\u0e14\u0e15\u0e32\u0e21\u0e44\u0e21\u0e48\u0e2a\u0e33\u0e40\u0e23\u0e47\u0e08: {exc}")
        return

    with perf_trace("followup.clear_caches", action="save_order"):
        clear_cached_functions_safely(
            fetch_followup_filter_options,
            getattr(neon, "fetch_filter_options", None),
            getattr(neon, "fetch_sales_report_owner_options", None),
            getattr(neon, "fetch_crm_owner_options", None),
        )
    clear_popup_order_state(prefix, row)
    actions = result.get("actions") or {}
    st.session_state.followup_page_success = (
        "บันทึกสำเร็จแล้ว "
        f"สินค้า {result.get('item_count', 0)} รายการ "
        f"(เพิ่มใหม่ {actions.get('inserted', 0)}, อัปเดต {actions.get('updated', 0)})"
    )
    close_followup_modal()
    with perf_trace("followup.rerun", action="save_order"):
        st.rerun()


def find_popup_order_owner_conflict(phone1: str, phone2: str, user: dict, staff_code: str) -> dict:
    rows = fetch_existing_owner_rows_by_phones(phone1, phone2)
    if not rows:
        return {}

    allowed_codes = {
        clean(value).casefold()
        for value in [staff_code, (user or {}).get("staff_code")]
        if clean(value)
    }
    for row in rows:
        existing_code = clean(row.get("staff_code")).casefold()
        if existing_code and existing_code in allowed_codes:
            continue
        return dict(row)
    return {}


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
    st.session_state[f"{prefix}_lead_status"] = followup_option_or_default(
        row.get("lead_status"),
        LEAD_STATUS_OPTIONS,
        "new",
    )
    st.session_state[f"{prefix}_followup_status"] = followup_option_or_default(
        row.get("followup_status"),
        FOLLOWUP_STATUS_OPTIONS,
        "none",
    )
    st.session_state[f"{prefix}_priority"] = normalize_followup_priority(row.get("priority"))
    st.session_state[f"{prefix}_next_followup_date"] = parse_date(row.get("next_followup_date"))
    st.session_state[f"{prefix}_followup_note"] = clean(row.get("followup_note"))
    st.session_state[popup_product_picker_state_key(prefix, "selected_product")] = {}
    st.session_state[popup_product_picker_state_key(prefix, "selected_product_sku")] = ""
    st.session_state[f"{prefix}_product_qty"] = 1
    st.session_state[f"{prefix}_product_amount"] = ""
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
            "product_group": clean(row.get("product_group")),
            "image_url": clean(row.get("image_url")),
        }
        for row in fetch_order_product_options()
        if clean(row.get("sku")) and clean(row.get("product_name"))
    ]


def popup_product_label(row: dict) -> str:
    return f"{clean(row.get('sku'))} - {clean(row.get('product_name'))}"


def popup_product_from_label(options: list[dict], label: str) -> dict:
    if not label:
        return {}
    for row in options:
        if popup_product_label(row) == label:
            return row
    return {}


def popup_product_picker_state_key(row_key: str, name: str) -> str:
    return f"{row_key}_product_picker_{name}"


def popup_product_picker_search_text(product: dict) -> str:
    return " ".join(
        clean(value)
        for value in [
            product.get("sku"),
            product.get("product_name"),
            product.get("product_group"),
        ]
        if clean(value)
    ).casefold()


def popup_selected_product_key(product: dict) -> str:
    return f"{clean(product.get('sku'))}::{clean(product.get('product_name'))}"


def filter_popup_product_picker_options(products: list[dict], query: str) -> list[dict]:
    tokens = [token for token in clean(query).casefold().split() if token]
    if not tokens:
        return []
    matches = []
    for product in products:
        haystack = popup_product_picker_search_text(product)
        if all(token in haystack for token in tokens):
            matches.append(product)
    return matches


def normalize_popup_product_selector_page_size(value) -> int:
    try:
        page_size = int(value)
    except (TypeError, ValueError):
        page_size = POPUP_PRODUCT_SELECTOR_PAGE_SIZE_OPTIONS[0]
    if page_size not in POPUP_PRODUCT_SELECTOR_PAGE_SIZE_OPTIONS:
        return POPUP_PRODUCT_SELECTOR_PAGE_SIZE_OPTIONS[0]
    return page_size


def paginate_popup_product_selector_options(products: list[dict], page: int, page_size: int) -> tuple[list[dict], int, int]:
    page_size = normalize_popup_product_selector_page_size(page_size)
    total_pages = max(1, (len(products) + page_size - 1) // page_size)
    page = min(max(1, int(page or 1)), total_pages)
    start = (page - 1) * page_size
    return products[start : start + page_size], page, total_pages


def popup_product_from_key(options: list[dict], product_key: str) -> dict:
    if not product_key:
        return {}
    for product in options:
        if popup_selected_product_key(product) == product_key:
            return product
    return {}


def select_popup_product(row_key: str, product: dict, query: str = "") -> None:
    selected_product = dict(product or {})
    st.session_state[popup_product_picker_state_key(row_key, "selected_product")] = selected_product
    st.session_state[popup_product_picker_state_key(row_key, "selected_product_sku")] = clean(
        selected_product.get("sku")
    )
    st.session_state[popup_product_picker_state_key(row_key, "hide_results")] = True
    st.session_state[popup_product_picker_state_key(row_key, "hide_query")] = clean(query)


def selected_popup_product(product_options: list[dict], row_key: str) -> dict:
    selected = st.session_state.get(popup_product_picker_state_key(row_key, "selected_product"))
    product_key = popup_selected_product_key(selected) if isinstance(selected, dict) else ""
    product = popup_product_from_key(product_options, product_key)
    if product:
        return product
    st.session_state[popup_product_picker_state_key(row_key, "selected_product")] = {}
    st.session_state[popup_product_picker_state_key(row_key, "selected_product_sku")] = ""
    return {}


def render_popup_picker_thumbnail(container, product: dict, width: int = 48) -> None:
    image_url = selected_product_image_preview_url(product)
    if image_url:
        container.image(image_url, width=width)
    else:
        container.caption("ไม่มีรูป")


def render_popup_product_picker(product_options: list[dict], row_key: str) -> None:
    if not st.session_state.get(popup_product_picker_state_key(row_key, "open")):
        return
    render_popup_product_selector_panel(product_options, row_key)


def render_popup_product_selector_panel(product_options: list[dict], row_key: str) -> None:
    with st.container(border=True):
        header_col, close_col = st.columns([3.0, 1.0], vertical_alignment="center")
        header_col.markdown("#### \u0e40\u0e25\u0e37\u0e2d\u0e01\u0e2a\u0e34\u0e19\u0e04\u0e49\u0e32")
        if close_col.button("\u0e1b\u0e34\u0e14", key=popup_product_picker_state_key(row_key, "close_top"), use_container_width=True):
            st.session_state[popup_product_picker_state_key(row_key, "open")] = False
            st.rerun()
        st.caption("\u0e04\u0e49\u0e19\u0e2b\u0e32 SKU \u0e2b\u0e23\u0e37\u0e2d\u0e0a\u0e37\u0e48\u0e2d\u0e2a\u0e34\u0e19\u0e04\u0e49\u0e32 \u0e41\u0e25\u0e49\u0e27\u0e40\u0e25\u0e37\u0e2d\u0e01\u0e08\u0e32\u0e01\u0e15\u0e32\u0e23\u0e32\u0e07\u0e14\u0e49\u0e32\u0e19\u0e25\u0e48\u0e32\u0e07")
        render_popup_product_selector_panel_body(product_options, row_key)


def render_popup_product_selector_panel_body(product_options: list[dict], row_key: str) -> None:
    query_key = popup_product_picker_state_key(row_key, "query")
    query = st.text_input("\u0e04\u0e49\u0e19\u0e2b\u0e32 SKU / \u0e0a\u0e37\u0e48\u0e2d\u0e2a\u0e34\u0e19\u0e04\u0e49\u0e32", key=query_key)
    clean_query = clean(query)
    previous_query_key = popup_product_picker_state_key(row_key, "previous_query")
    previous_query = st.session_state.get(previous_query_key, "")
    if clean_query != previous_query:
        st.session_state[popup_product_picker_state_key(row_key, "page")] = 1
        st.session_state[previous_query_key] = clean_query

    page_size = st.selectbox(
        "\u0e08\u0e33\u0e19\u0e27\u0e19\u0e23\u0e32\u0e22\u0e01\u0e32\u0e23\u0e15\u0e48\u0e2d\u0e2b\u0e19\u0e49\u0e32",
        POPUP_PRODUCT_SELECTOR_PAGE_SIZE_OPTIONS,
        key=popup_product_picker_state_key(row_key, "page_size"),
    )
    page_size = normalize_popup_product_selector_page_size(page_size)

    if not clean_query:
        st.caption("\u0e1e\u0e34\u0e21\u0e1e\u0e4c SKU \u0e2b\u0e23\u0e37\u0e2d\u0e0a\u0e37\u0e48\u0e2d\u0e2a\u0e34\u0e19\u0e04\u0e49\u0e32\u0e40\u0e1e\u0e37\u0e48\u0e2d\u0e04\u0e49\u0e19\u0e2b\u0e32")
        if st.button("\u0e1b\u0e34\u0e14", key=popup_product_picker_state_key(row_key, "close_empty")):
            st.session_state[popup_product_picker_state_key(row_key, "open")] = False
            st.rerun()
        return

    matches = filter_popup_product_picker_options(product_options, clean_query)
    if not matches:
        st.info("\u0e44\u0e21\u0e48\u0e1e\u0e1a\u0e2a\u0e34\u0e19\u0e04\u0e49\u0e32")
        if st.button("\u0e1b\u0e34\u0e14", key=popup_product_picker_state_key(row_key, "close_no_result")):
            st.session_state[popup_product_picker_state_key(row_key, "open")] = False
            st.rerun()
        return

    current_page = st.session_state.get(popup_product_picker_state_key(row_key, "page"), 1)
    page_items, page, total_pages = paginate_popup_product_selector_options(matches, current_page, page_size)
    st.session_state[popup_product_picker_state_key(row_key, "page")] = page
    st.caption(f"\u0e1e\u0e1a {len(matches):,} \u0e23\u0e32\u0e22\u0e01\u0e32\u0e23")

    header = st.columns([0.45, 0.75, 1.8, 1.0, 0.6])
    for col, label in zip(header, ["\u0e23\u0e39\u0e1b", "SKU", "\u0e2a\u0e34\u0e19\u0e04\u0e49\u0e32", "\u0e01\u0e25\u0e38\u0e48\u0e21", ""]):
        col.markdown(f"**{label}**")
    current_product = selected_popup_product(product_options, row_key)
    current_key = popup_selected_product_key(current_product)
    for index, product in enumerate(page_items):
        product_key = popup_selected_product_key(product)
        cols = st.columns([0.45, 0.75, 1.8, 1.0, 0.6])
        render_popup_picker_thumbnail(cols[0], product, width=48)
        cols[1].write(clean(product.get("sku")) or "-")
        cols[2].write(clean(product.get("product_name")) or "-")
        cols[3].write(clean(product.get("product_group")) or "-")
        if cols[4].button(
            "\u0e40\u0e25\u0e37\u0e2d\u0e01",
            key=f"{row_key}_product_selector_pick_{page}_{index}_{product_key}",
            use_container_width=True,
        ):
            select_popup_product(row_key, product, clean_query)
            add_popup_order_item(row_key, product, 1, None)
            st.rerun()

    nav_prev, nav_status, nav_next, nav_close = st.columns([0.9, 1.4, 0.9, 0.9])
    if nav_prev.button("\u0e01\u0e48\u0e2d\u0e19\u0e2b\u0e19\u0e49\u0e32", key=popup_product_picker_state_key(row_key, "prev"), disabled=page <= 1, use_container_width=True):
        st.session_state[popup_product_picker_state_key(row_key, "page")] = max(1, page - 1)
        st.rerun()
    nav_status.caption(f"\u0e2b\u0e19\u0e49\u0e32 {page} / {total_pages}")
    if nav_next.button("\u0e16\u0e31\u0e14\u0e44\u0e1b", key=popup_product_picker_state_key(row_key, "next"), disabled=page >= total_pages, use_container_width=True):
        st.session_state[popup_product_picker_state_key(row_key, "page")] = min(total_pages, page + 1)
        st.rerun()
    if nav_close.button("\u0e1b\u0e34\u0e14", key=popup_product_picker_state_key(row_key, "close"), use_container_width=True):
        st.session_state[popup_product_picker_state_key(row_key, "open")] = False
        st.rerun()


def render_popup_selected_product(product: dict) -> None:
    if not product:
        st.info("ยังไม่ได้เลือกสินค้า")
        return
    st.markdown(f"**{clean(product.get('sku')) or '-'} - {clean(product.get('product_name')) or '-'}**")
    product_group = clean(product.get("product_group"))
    if product_group:
        st.caption(product_group)
    render_popup_product_preview(product)


def render_popup_product_preview(product: dict) -> None:
    image_url = selected_product_image_preview_url(product)
    if image_url:
        st.image(image_url, width=120)


def selected_product_image_preview_url(product: dict) -> str:
    preview_url = getattr(neon, "product_image_preview_url", None)
    if callable(preview_url):
        return preview_url(product)
    if not isinstance(product, dict):
        return ""
    image_url = clean(product.get("image_url"))
    if image_url.lower().startswith(("http://", "https://")):
        return image_url
    return ""


def add_popup_order_item(prefix: str, product: dict, qty: int, amount=None) -> None:
    items = list(st.session_state.get(f"{prefix}_items", []))
    sku = clean(product.get("sku"))
    product_name = clean(product.get("product_name"))
    product_group = clean(product.get("product_group"))
    qty = max(1, int(qty or 1))
    amount_value = "" if amount in (None, "") else amount
    image_url = clean(product.get("image_url"))
    for item in items:
        if clean(item.get("sku")) == sku and clean(item.get("product_name")) == product_name:
            item["qty"] = int(item.get("qty") or 0) + qty
            if amount_value != "":
                current_amount = item.get("amount")
                item["amount"] = float(current_amount or 0) + float(amount_value or 0)
            if product_group and not clean(item.get("product_group")):
                item["product_group"] = product_group
            if image_url and not clean(item.get("image_url")):
                item["image_url"] = image_url
            st.session_state[f"{prefix}_items"] = items
            return
    items.append({
        "sku": sku,
        "product_name": product_name,
        "product_group": product_group,
        "qty": qty,
        "amount": amount_value,
        "image_url": image_url,
    })
    st.session_state[f"{prefix}_items"] = items


def remove_popup_order_item(prefix: str, index: int) -> None:
    items = list(st.session_state.get(f"{prefix}_items", []))
    if 0 <= index < len(items):
        items.pop(index)
    st.session_state[f"{prefix}_items"] = items


def render_popup_order_item_preview(container, item: dict) -> None:
    image_url = selected_product_image_preview_url(item)
    if image_url:
        container.image(image_url, width=120)


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
        render_popup_order_item_preview(cols[1], item)
        qty_value = cols[2].number_input(
            "\u0e08\u0e33\u0e19\u0e27\u0e19",
            min_value=1,
            value=max(1, int(item.get("qty") or 1)),
            step=1,
            key=f"{prefix}_item_qty_{index}",
            label_visibility="collapsed",
        )
        amount_text = "" if item.get("amount") in (None, "") else str(item.get("amount"))
        amount_value = cols[3].text_input(
            "\u0e23\u0e32\u0e04\u0e32",
            value=amount_text,
            key=f"{prefix}_item_amount_{index}",
            label_visibility="collapsed",
        )
        item["qty"] = int(qty_value or 1)
        item["amount"] = str(amount_value or "").strip()
        if cols[4].button("ลบ", key=f"{prefix}_delete_{index}", use_container_width=True):
            delete_index = index
    return delete_index


main()
