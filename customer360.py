import html
import json
import os
from datetime import date, datetime
from urllib.parse import quote, urlencode

import pandas as pd
import requests
import streamlit as st
import streamlit.components.v1 as components


CUSTOMERS_TABLE = "crm_customers"
ORDERS_TABLE = "order_history"
LEAD_FOLLOWUPS_TABLE = "crm_lead_followups"
FETCH_LIMIT = 1000
ORDER_MAX_FETCH = 5000
CUSTOMER_MAX_FETCH = 100000
PAGE_SIZE_OPTIONS = [10, 25, 50, 100, 250, 500]
AUTO_REFRESH_SECONDS = 60
LEAD_STATUS_OPTIONS = {
    "new": "ลูกค้าใหม่",
    "contacted": "ติดต่อแล้ว",
    "interested": "สนใจ",
    "follow_up": "ต้องติดตาม",
    "won": "ปิดการขายแล้ว",
    "lost": "ไม่สนใจ/หลุด",
    "dormant": "ลูกค้าเงียบ",
}
FOLLOW_UP_STATUS_OPTIONS = {
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

PRODUCT_GROUP_ORDER = [
    "ยา/อาหารเสริม",
    "DKUB",
    "SMASH",
    "เด็ก/คุณแม่",
    "สัตว์เลี้ยง",
    "รถ/เครื่องมือช่าง",
    "สินค้าทั่วไป",
]


def get_secret(*names: str) -> str:
    for name in names:
        if name in st.secrets:
            return st.secrets[name]
        value = os.getenv(name, "")
        if value:
            return value
    return ""


SUPABASE_URL = get_secret("CRM_SUPABASE_URL", "SUPABASE_URL").rstrip("/")
SUPABASE_ANON_KEY = get_secret("CRM_SUPABASE_ANON_KEY", "SUPABASE_ANON_KEY")
SUPABASE_SERVICE_KEY = get_secret("CRM_SUPABASE_SERVICE_KEY", "SUPABASE_SERVICE_KEY")


def render_customer360() -> None:
    inject_css()
    sync_detail_key_from_query()
    sidebar_refresh_controls()

    customers = load_crm_customers()
    st.title("ข้อมูลลูกค้า")

    if customers.empty:
        render_setup_warning()
        st.stop()

    filtered = sidebar_filters(customers)
    if filtered.empty:
        st.warning("ไม่พบลูกค้าตามเงื่อนไขที่เลือก")
        st.stop()

    filtered = filtered.reset_index(drop=True)
    if st.session_state.get("customer360_detail_key"):
        render_customer_detail(filtered)
        return

    render_customer_list(filtered)


def inject_css() -> None:
    st.markdown(
        """
<style>
:root {
  --crm-bg:#fff8f1;
  --crm-panel:#ffffff;
  --crm-border:#fed7aa;
  --crm-soft-border:#ffedd5;
  --crm-text:#111827;
  --crm-muted:#64748b;
  --crm-accent:#f97316;
  --crm-accent-dark:#ea580c;
  --crm-accent-soft:#fff3e6;
  --crm-accent-softer:#fffaf5;
  --crm-green:#15803d;
  --crm-shadow:0 14px 34px rgba(234,88,12,.08);
}
.stApp { background:var(--crm-bg); color:var(--crm-text); }
.block-container { max-width:1500px; padding-top:2.2rem; padding-bottom:3rem; }
[data-testid="stSidebar"] {
  background:linear-gradient(180deg,#ffffff 0%,#fff7ed 100%);
  border-right:1px solid var(--crm-border);
}
[data-testid="stSidebar"] * { color:var(--crm-text) !important; }
[data-testid="stSidebar"] input,
[data-testid="stSidebar"] textarea,
[data-testid="stSidebar"] [data-baseweb="select"] > div,
[data-testid="stSidebar"] [data-baseweb="input"] > div {
  background:#ffffff !important;
  color:var(--crm-text) !important;
  border-color:var(--crm-accent) !important;
  border-radius:8px !important;
  box-shadow:0 1px 0 rgba(249,115,22,.08) !important;
}
[data-testid="stSidebar"] input::placeholder,
[data-testid="stSidebar"] textarea::placeholder {
  color:#9a3412 !important;
  opacity:.62 !important;
}
[data-testid="stSidebarNav"] a { color:var(--crm-text) !important; border-radius:6px; }
[data-testid="stSidebarNav"] a[aria-current="page"],
[data-testid="stSidebarNav"] a:hover {
  background:#ffedd5 !important;
  color:var(--crm-accent-dark) !important;
  font-weight:700;
}
[data-testid="stSidebarNav"] a[href$="/~/+/"],
[data-testid="stSidebarNav"] a[href$="/"],
[data-testid="stSidebarNav"] a[href*="/~/+/customers"],
[data-testid="stSidebarNav"] a[href*="/customers"],
[data-testid="stSidebarNav"] a[href*="/~/+/sync_status"],
[data-testid="stSidebarNav"] a[href*="/sync_status"] { font-size:0 !important; }
[data-testid="stSidebarNav"] a[href$="/~/+/"]::after,
[data-testid="stSidebarNav"] a[href$="/"]::after {
  content:"ข้อมูลลูกค้า";
  font-size:14px !important;
}
[data-testid="stSidebarNav"] a[href*="/~/+/sync_status"]::after,
[data-testid="stSidebarNav"] a[href*="/sync_status"]::after {
  content:"สถานะ Sync";
  font-size:14px !important;
}
h1 {
  color:var(--crm-text);
  letter-spacing:0;
  border-left:6px solid var(--crm-accent);
  padding-left:14px;
  margin-bottom:1rem;
}
h2, h3 { color:var(--crm-text); letter-spacing:0; }
p, label, [data-testid="stMarkdownContainer"] { color:var(--crm-text); }
[data-testid="stCaptionContainer"] { color:#7c2d12 !important; }
[data-testid="stMetric"] {
  background:linear-gradient(180deg,#ffffff 0%,#fffaf5 100%);
  border:1px solid var(--crm-border);
  border-radius:8px;
  padding:16px 18px;
  box-shadow:var(--crm-shadow);
}
[data-testid="stMetric"] label,
[data-testid="stMetric"] label *,
[data-testid="stMetricLabel"],
[data-testid="stMetricLabel"] * {
  color:#9a3412 !important;
  font-weight:700 !important;
  opacity:1 !important;
}
[data-testid="stMetricValue"] { color:var(--crm-accent-dark); font-weight:700; }
.stSelectbox label, .stNumberInput label, .stTextInput label {
  color:#9a3412 !important;
  font-weight:700 !important;
}
div[data-baseweb="select"] > div,
div[data-baseweb="input"] > div,
input {
  background:#ffffff !important;
  color:#111827 !important;
  border:1px solid #fb923c !important;
  border-radius:8px !important;
}
div[data-baseweb="select"] *,
div[data-baseweb="input"] *,
input,
textarea {
  color:#111827 !important;
}
div[data-baseweb="select"] svg,
button svg {
  color:#ea580c !important;
  fill:#ea580c !important;
}
[role="listbox"],
[data-baseweb="popover"] > div {
  background:#ffffff !important;
  color:#111827 !important;
  border:1px solid #fdba74 !important;
  box-shadow:0 18px 45px rgba(124,45,18,.14) !important;
}
[role="option"] {
  background:#ffffff !important;
  color:#111827 !important;
}
[role="option"]:hover,
[aria-selected="true"] {
  background:#ffedd5 !important;
  color:#7c2d12 !important;
}
.stNumberInput button {
  background:#fff7ed !important;
  border-color:#fb923c !important;
  color:#ea580c !important;
}
.crm-table-wrap {
  border:1px solid var(--crm-soft-border);
  border-radius:8px;
  overflow:auto;
  background:#ffffff;
  box-shadow:var(--crm-shadow);
  margin-top:12px;
}
.crm-table {
  width:100%;
  border-collapse:collapse;
  font-size:14px;
  color:var(--crm-text);
  background:#ffffff;
}
.crm-table thead th {
  background:linear-gradient(180deg,#fff3e6 0%,#ffedd5 100%);
  color:#7c2d12;
  font-weight:700;
  text-align:left;
  padding:11px 12px;
  border-bottom:1px solid #fdba74;
  white-space:nowrap;
}
.crm-table tbody td {
  padding:10px 12px;
  border-bottom:1px solid #f1f5f9;
  color:var(--crm-text);
  background:#ffffff;
  vertical-align:top;
  min-width:110px;
}
.crm-table tbody tr:nth-child(even) { background:#fffaf5; }
.crm-table tbody tr:nth-child(even) td { background:#fffaf5; }
.crm-table tbody tr:hover { background:#ffedd5; }
.crm-table tbody tr:hover td { background:#ffedd5; }
.crm-table .num {
  text-align:right;
  font-variant-numeric:tabular-nums;
  font-weight:700;
  color:var(--crm-accent-dark);
}
.history-link {
  display:inline-flex;
  align-items:center;
  justify-content:center;
  min-width:70px;
  min-height:30px;
  padding:4px 10px;
  border:1px solid #fb923c;
  border-radius:8px;
  background:#fff7ed;
  color:#9a3412 !important;
  font-weight:700;
  text-decoration:none !important;
  white-space:nowrap;
}
.history-link:hover {
  background:#ffedd5;
  color:#7c2d12 !important;
}
.crm-detail-grid {
  display:grid;
  grid-template-columns:repeat(2, minmax(0, 1fr));
  gap:12px;
  margin:14px 0 22px 0;
}
.crm-detail-item {
  border:1px solid var(--crm-border);
  border-radius:8px;
  background:linear-gradient(180deg,#ffffff 0%,#fffaf5 100%);
  padding:12px 14px;
  box-shadow:0 8px 22px rgba(234,88,12,.06);
}
.crm-detail-label { color:var(--crm-muted); font-size:13px; margin-bottom:4px; }
.crm-detail-value { color:var(--crm-text); font-weight:700; overflow-wrap:anywhere; }
.order-card {
  background:linear-gradient(180deg,#ffffff 0%,#fffaf5 100%);
  border:1px solid var(--crm-border);
  border-radius:8px;
  padding:16px;
  margin-bottom:12px;
  box-shadow:0 1px 2px rgba(15,23,42,.04);
}
.badge {
  display:inline-block;
  padding:4px 10px;
  border-radius:999px;
  background:#ffedd5;
  color:#7c2d12;
  font-size:12px;
  font-weight:700;
  margin:0 6px 6px 0;
}
.badge-green { background:#dcfce7; color:#166534; }
.badge-orange { background:#ffedd5; color:#9a3412; }
.badge-blue { background:#dbeafe; color:#1d4ed8; }
.badge-red { background:#fee2e2; color:#991b1b; }
.badge-gray { background:#f1f5f9; color:#334155; }
.green { color:var(--crm-green); font-weight:700; }
.muted { color:var(--crm-muted); }
.stButton > button {
  border-radius:8px;
  font-weight:700;
  background:#ffffff !important;
  color:#9a3412 !important;
  border:1px solid #fb923c !important;
}
[data-testid="stSidebar"] .stButton > button {
  background:linear-gradient(90deg,#ff7a00 0%,#fb923c 100%);
  color:#ffffff !important;
  border:none;
  min-height:42px;
}
.stButton > button:hover {
  background:#ffedd5 !important;
  color:#7c2d12 !important;
  border-color:#ea580c !important;
}
@media (max-width: 900px) {
  .crm-detail-grid { grid-template-columns:1fr; }
}
</style>
""",
        unsafe_allow_html=True,
    )


def require_config() -> None:
    missing = [
        name
        for name, value in {
            "CRM_SUPABASE_URL": SUPABASE_URL,
            "CRM_SUPABASE_ANON_KEY": SUPABASE_ANON_KEY,
        }.items()
        if not value
    ]
    if missing:
        st.error("ยังไม่ได้ตั้งค่า Streamlit secrets: " + ", ".join(missing))
        st.stop()


def request_headers(api_key: str | None = None, prefer: str = "count=exact") -> dict[str, str]:
    key = api_key or SUPABASE_ANON_KEY
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Prefer": prefer,
    }


def api_get(path: str, params: list[str], api_key: str | None = None) -> tuple[list[dict], str | None]:
    require_config()
    url = f"{SUPABASE_URL}/rest/v1/{path}?{'&'.join(params)}"
    response = requests.get(url, headers=request_headers(api_key=api_key), timeout=30)
    if response.status_code not in (200, 206):
        return [], response.text
    return response.json(), None


def api_upsert(path: str, payload: dict, conflict_key: str) -> tuple[list[dict], str | None]:
    require_config()
    if not SUPABASE_SERVICE_KEY:
        return [], "ยังไม่ได้ตั้งค่า CRM_SUPABASE_SERVICE_KEY สำหรับบันทึก Lead / Follow-up"
    url = f"{SUPABASE_URL}/rest/v1/{path}?on_conflict={quote(conflict_key)}"
    headers = request_headers(
        api_key=SUPABASE_SERVICE_KEY,
        prefer="resolution=merge-duplicates,return=representation",
    )
    headers["Content-Type"] = "application/json"
    response = requests.post(url, headers=headers, json=[payload], timeout=30)
    if response.status_code not in (200, 201):
        return [], response.text
    return response.json(), None


@st.cache_data(ttl=60, show_spinner="กำลังโหลดลูกค้า CRM...")
def load_crm_customers() -> pd.DataFrame:
    rows: list[dict] = []
    offset = 0
    while offset < CUSTOMER_MAX_FETCH:
        page, error = api_get(
            CUSTOMERS_TABLE,
            [
                "select=*",
                "order=updated_at.desc",
                f"limit={min(FETCH_LIMIT, CUSTOMER_MAX_FETCH - offset)}",
                f"offset={offset}",
            ],
        )
        if error:
            st.session_state.customer360_customer_error = error
            return pd.DataFrame()
        rows.extend(page)
        if len(page) < FETCH_LIMIT:
            break
        offset += FETCH_LIMIT
    st.session_state.customer360_customer_error = ""
    return pd.DataFrame(rows)


@st.cache_data(ttl=120, show_spinner="กำลังจับคู่ประวัติคำสั่งซื้อ...")
def search_orders_by_phones(phones: tuple[str, ...], year: str) -> pd.DataFrame:
    clean_phones = tuple(phone for phone in phones if phone)
    if not clean_phones:
        return pd.DataFrame()

    select_cols = ",".join(
        [
            "source_key",
            "order_id",
            "year",
            "month",
            "day",
            "date_text",
            "customer",
            "phone1",
            "phone2",
            "address",
            "subdistrict",
            "district",
            "province",
            "postcode",
            "channel",
            "sales_staff",
            "upsell_staff",
            "care_staff",
            "product_group",
            "total_sales",
            "order_status",
            "payment_method",
            "delivery_status",
            "shipping",
            "tracking_no",
            "channel_url",
            "products",
            "note",
            "source_sheet",
            "year_file",
            "synced_at",
        ]
    )
    phone_filters = []
    for phone in clean_phones[:6]:
        q = quote(phone)
        phone_filters.extend([f"phone1.ilike.*{q}*", f"phone2.ilike.*{q}*"])

    rows: list[dict] = []
    offset = 0
    base = [f"select={select_cols}", f"or=({','.join(phone_filters)})"]
    if year != "ทั้งหมด":
        base.append(f"year_file=eq.{quote(year)}")

    while offset < ORDER_MAX_FETCH:
        page, error = api_get(
            ORDERS_TABLE,
            base
            + [
                f"limit={min(FETCH_LIMIT, ORDER_MAX_FETCH - offset)}",
                f"offset={offset}",
                "order=synced_at.desc",
            ],
        )
        if error or not page:
            break
        rows.extend(page)
        if len(page) < FETCH_LIMIT:
            break
        offset += FETCH_LIMIT

    df = pd.DataFrame(rows)
    if df.empty:
        return df
    target_phones = set(clean_phones)

    def exact_phone_match(row: pd.Series) -> bool:
        return bool({normalize_phone(row.get("phone1")), normalize_phone(row.get("phone2"))} & target_phones)

    return df[df.apply(exact_phone_match, axis=1)].copy()


@st.cache_data(ttl=30, show_spinner="กำลังโหลดสถานะ Lead / Follow-up...")
def load_lead_followups() -> dict[str, dict]:
    if not SUPABASE_SERVICE_KEY:
        st.session_state.customer360_lead_error = "missing_service_key"
        return {}

    rows: list[dict] = []
    offset = 0
    while offset < CUSTOMER_MAX_FETCH:
        page, error = api_get(
            LEAD_FOLLOWUPS_TABLE,
            [
                "select=*",
                "order=updated_at.desc",
                f"limit={min(FETCH_LIMIT, CUSTOMER_MAX_FETCH - offset)}",
                f"offset={offset}",
            ],
            api_key=SUPABASE_SERVICE_KEY,
        )
        if error:
            st.session_state.customer360_lead_error = error
            return {}
        rows.extend(page)
        if len(page) < FETCH_LIMIT:
            break
        offset += FETCH_LIMIT

    st.session_state.customer360_lead_error = ""
    return {clean(row.get("customer_key")): row for row in rows if clean(row.get("customer_key"))}


def save_lead_followup(customer: pd.Series, values: dict) -> str | None:
    customer_key = customer_detail_key(customer)
    payload = {
        "customer_key": customer_key,
        "customer_id": first_value(customer, "customer_id", "id"),
        "customer_name": first_value(customer, "customer", "customer_name"),
        "phone_key": customer_group_key(customer),
        "phone1": first_value(customer, "phone1"),
        "phone2": first_value(customer, "phone2"),
        "product_group": first_value(customer, "product_group"),
        "lead_status": values["lead_status"],
        "follow_up_status": values["follow_up_status"],
        "follow_up_date": values["follow_up_date"].isoformat() if values.get("follow_up_date") else None,
        "follow_up_note": values.get("follow_up_note", ""),
        "priority": values["priority"],
        "updated_by": values.get("updated_by", ""),
        "updated_at": datetime.utcnow().isoformat() + "Z",
    }
    _, error = api_upsert(LEAD_FOLLOWUPS_TABLE, payload, "customer_key")
    if not error:
        load_lead_followups.clear()
    return error


def sidebar_refresh_controls() -> None:
    st.sidebar.header("อัปเดตข้อมูล")
    auto_refresh = st.sidebar.toggle(
        f"รีเฟรชอัตโนมัติทุก {AUTO_REFRESH_SECONDS} วินาที",
        value=False,
    )
    if st.sidebar.button("รีเฟรชข้อมูลตอนนี้", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    if auto_refresh:
        components.html(
            f"""
            <script>
              window.setTimeout(function() {{
                window.parent.location.reload();
              }}, {AUTO_REFRESH_SECONDS * 1000});
            </script>
            """,
            height=0,
            width=0,
        )


def sidebar_filters(df: pd.DataFrame) -> pd.DataFrame:
    st.sidebar.header("ตัวกรอง")
    init_filter_state()
    product_options = [group for group in PRODUCT_GROUP_ORDER if group in set(df.get("product_group", []))]
    extras = sorted(set(df.get("product_group", pd.Series(dtype=str)).dropna().astype(str)) - set(product_options))
    staff_options = sorted(df.get("sales_staff", pd.Series(dtype=str)).dropna().astype(str).unique().tolist())

    product_group_options = ["ทั้งหมด"] + product_options + extras
    staff_filter_options = ["ทั้งหมด"] + staff_options
    year_options = ["ทั้งหมด", "2565", "2566", "2567", "2568", "2569"]

    st.sidebar.selectbox(
        "กลุ่มสินค้า",
        product_group_options,
        index=safe_index(product_group_options, st.session_state.customer360_pending_product_group),
        key="customer360_pending_product_group",
    )
    st.sidebar.selectbox(
        "ผู้ดูแล",
        staff_filter_options,
        index=safe_index(staff_filter_options, st.session_state.customer360_pending_staff),
        key="customer360_pending_staff",
    )
    st.sidebar.selectbox(
        "ประวัติปี",
        year_options,
        index=safe_index(year_options, st.session_state.customer360_pending_year),
        key="customer360_pending_year",
    )
    st.sidebar.text_input(
        "ค้นหา",
        placeholder="ชื่อลูกค้า / เบอร์ / สินค้า / โน๊ต / URL",
        key="customer360_pending_keyword",
        on_change=apply_pending_filters,
    )

    if st.sidebar.button("ค้นหา", use_container_width=True):
        apply_pending_filters()

    if st.sidebar.button("ล้างตัวกรอง", use_container_width=True):
        reset_filters()
        st.rerun()

    active = st.session_state.customer360_filters
    product_group = active["product_group"]
    staff = active["staff"]
    keyword = active["keyword"]
    st.session_state.customer360_year = active["year"]

    filtered = df.copy()
    if product_group != "ทั้งหมด" and "product_group" in filtered:
        filtered = filtered[filtered["product_group"].fillna("").astype(str) == product_group]
    if staff != "ทั้งหมด" and "sales_staff" in filtered:
        filtered = filtered[filtered["sales_staff"].fillna("").astype(str) == staff]
    if keyword:
        text_cols = ["customer", "product_group", "product_name", "phone1", "phone2", "note", "sales_staff", "product_url"]
        available = [col for col in text_cols if col in filtered.columns]
        if available:
            haystack = filtered[available].fillna("").astype(str).agg(" ".join, axis=1)
            filtered = filtered[haystack.str.contains(keyword.strip(), case=False, na=False)]

    return filtered


def init_filter_state() -> None:
    defaults = {
        "product_group": "ทั้งหมด",
        "staff": "ทั้งหมด",
        "keyword": "",
        "year": "ทั้งหมด",
    }
    if "customer360_filters" not in st.session_state:
        st.session_state.customer360_filters = defaults.copy()
    st.session_state.setdefault("customer360_pending_product_group", st.session_state.customer360_filters["product_group"])
    st.session_state.setdefault("customer360_pending_staff", st.session_state.customer360_filters["staff"])
    st.session_state.setdefault("customer360_pending_keyword", st.session_state.customer360_filters["keyword"])
    st.session_state.setdefault("customer360_pending_year", st.session_state.customer360_filters["year"])


def sync_detail_key_from_query() -> None:
    detail_key = st.query_params.get("customer_key", "")
    if detail_key:
        st.session_state.customer360_detail_key = detail_key


def apply_pending_filters() -> None:
    st.session_state.customer360_filters = {
        "product_group": st.session_state.get("customer360_pending_product_group", "ทั้งหมด"),
        "staff": st.session_state.get("customer360_pending_staff", "ทั้งหมด"),
        "keyword": st.session_state.get("customer360_pending_keyword", "").strip(),
        "year": st.session_state.get("customer360_pending_year", "ทั้งหมด"),
    }
    st.session_state.customer360_detail_key = None
    st.query_params.clear()


def reset_filters() -> None:
    defaults = {
        "product_group": "ทั้งหมด",
        "staff": "ทั้งหมด",
        "keyword": "",
        "year": "ทั้งหมด",
    }
    st.session_state.customer360_filters = defaults.copy()
    st.session_state.customer360_pending_product_group = "ทั้งหมด"
    st.session_state.customer360_pending_staff = "ทั้งหมด"
    st.session_state.customer360_pending_keyword = ""
    st.session_state.customer360_pending_year = "ทั้งหมด"
    st.session_state.customer360_detail_key = None
    st.query_params.clear()


def safe_index(options: list[str], value: str) -> int:
    return options.index(value) if value in options else 0


def render_customer_list(df: pd.DataFrame) -> None:
    display_df = display_customers(df)
    lead_map = load_lead_followups()
    lead_error = st.session_state.get("customer360_lead_error")
    total_customers = unique_customer_count(df)
    total_rows = len(display_df)
    with_phone = sum(1 for _, row in df.iterrows() if customer_phones(row))

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("ลูกค้าปัจจุบัน", f"{total_customers:,}")
    col2.metric("แถวที่แสดง", f"{total_rows:,}")
    col3.metric("กลุ่มสินค้า", f"{df.get('product_group', pd.Series(dtype=str)).nunique():,}")
    col4.metric("มีเบอร์โทร", f"{with_phone:,}")

    st.caption("รวมลูกค้าปัจจุบันจากชีทหัวหน้า ซ่อนแถวผู้ดูแลว่างเมื่อเบอร์เดียวกันมีผู้ดูแลแล้ว และกดดูประวัติสั่งซื้อเก่าจากเบอร์โทร")
    if lead_error == "missing_service_key":
        st.warning("Lead / Follow-up ยังเป็นโหมดอ่านอย่างเดียว เพราะยังไม่ได้ตั้งค่า CRM_SUPABASE_SERVICE_KEY")
    elif lead_error:
        st.warning("ยังโหลด Lead / Follow-up ไม่ได้ อาจต้องรัน migration crm_lead_followups ก่อน")

    page_size = st.selectbox("จำนวนแถวต่อหน้า", PAGE_SIZE_OPTIONS, index=0, key="customer360_page_size")
    total_pages = max((len(display_df) - 1) // page_size + 1, 1)
    page = st.number_input("หน้า", min_value=1, max_value=total_pages, value=1, step=1, key="customer360_page")
    start = (page - 1) * page_size
    end = start + page_size

    page_df = display_df.iloc[start:end].reset_index(drop=True)
    render_html_table(customer360_table(page_df, lead_map))

    st.caption(f"แสดง {start + 1 if len(display_df) else 0}-{min(end, len(display_df))} จาก {len(display_df):,} แถว")


def render_customer_detail(df: pd.DataFrame) -> None:
    detail_key = st.session_state.get("customer360_detail_key")
    selected = df[df.apply(customer_detail_key, axis=1) == detail_key]
    if selected.empty:
        st.session_state.customer360_detail_key = None
        st.rerun()

    customer = selected.iloc[0]
    phones = customer_phones(customer)
    year = st.session_state.get("customer360_year", "ทั้งหมด")
    order_df = search_orders_by_phones(phones, year)
    orders = order_df.to_dict("records") if not order_df.empty else []
    latest = sort_orders(orders)[0] if orders else {}

    if st.button("กลับหน้า Customer 360"):
        st.session_state.customer360_detail_key = None
        st.query_params.clear()
        st.rerun()

    name = first_value(customer, "customer", "customer_name") or "(ไม่ระบุชื่อลูกค้า)"
    st.subheader(name)
    st.markdown(
        f"""
        <span class="badge">โทร {html_escape(first_value(customer, "phone1")) or "-"}</span>
        <span class="badge">สำรอง {html_escape(first_value(customer, "phone2")) or "-"}</span>
        <span class="badge badge-green">{len(orders)} ออเดอร์เก่า</span>
        <span class="badge">{html_escape(first_value(customer, "sales_staff", "owner")) or "ไม่ระบุผู้ดูแล"}</span>
        """,
        unsafe_allow_html=True,
    )

    render_detail_grid(
        [
            ("ชื่อลูกค้า", name),
            ("กลุ่มสินค้า", first_value(customer, "product_group")),
            ("สินค้า", first_value(customer, "product_name", "product")),
            ("เบอร์โทรติดต่อ", first_value(customer, "phone1")),
            ("เบอร์โทรสำรอง", first_value(customer, "phone2")),
            ("โน๊ต", first_value(customer, "note")),
            ("ผู้ดูแล", first_value(customer, "sales_staff", "owner")),
            ("อัพเดต", count_checked_update_days(customer)),
            ("URL", first_value(customer, "product_url", "url", "channel_url")),
        ]
    )
    render_lead_followup_panel(customer)

    if not orders:
        st.info("ยังไม่พบประวัติคำสั่งซื้อจาก DATA_RAW ที่ตรงกับเบอร์โทรติดต่อหรือเบอร์โทรสำรอง")
        return

    st.subheader("ออเดอร์ล่าสุด")
    latest_products = parse_products(latest.get("products"))
    render_detail_grid(
        [
            ("เลขออเดอร์", latest.get("order_id")),
            ("วันที่", latest.get("date_text")),
            ("วิธีการชำระ", payment_badge(latest.get("payment_method"))),
            ("สถานะจัดส่ง", delivery_badge(latest.get("delivery_status"))),
            ("ผู้ขายเดิม", latest.get("sales_staff")),
            ("พนักงาน UPSELL", latest.get("upsell_staff")),
            ("พนักงานดูแล", latest.get("care_staff")),
            ("ยอดขาย", f"{float(latest.get('total_sales') or 0):,.0f} บาท"),
            ("สถานะคำสั่งซื้อ", latest.get("order_status")),
            ("ที่อยู่จัดส่ง", full_address(latest)),
            ("URL ออเดอร์", latest.get("channel_url")),
        ]
    )

    st.subheader("รายการสินค้าในออเดอร์ล่าสุด")
    st.markdown(product_table(latest_products), unsafe_allow_html=True)
    render_order_history(orders)


def render_lead_followup_panel(customer: pd.Series) -> None:
    lead = load_lead_followups().get(customer_detail_key(customer), {})
    lead_status = clean(lead.get("lead_status")) or "new"
    follow_up_status = clean(lead.get("follow_up_status")) or "none"
    priority = clean(lead.get("priority")) or "normal"

    st.subheader("Lead / Follow-up Status")
    if st.session_state.get("customer360_lead_error") == "missing_service_key":
        st.warning("ยังไม่ได้ตั้งค่า CRM_SUPABASE_SERVICE_KEY จึงยังบันทึกสถานะจากหน้าเว็บไม่ได้")
    elif st.session_state.get("customer360_lead_error"):
        st.warning("ยังอ่านตาราง crm_lead_followups ไม่ได้ อาจต้องรัน migration ก่อนใช้งานจริง")

    render_detail_grid(
        [
            ("Lead", lead_status_badge(lead_status)),
            ("Follow-up", follow_up_badge(lead)),
            ("นัดติดตาม", lead.get("follow_up_date")),
            ("ความสำคัญ", PRIORITY_OPTIONS.get(priority, priority)),
            ("ผู้แก้ไขล่าสุด", lead.get("updated_by")),
            ("อัปเดตล่าสุด", lead.get("updated_at")),
        ]
    )

    with st.form("lead_followup_form"):
        st.caption("ช่วงแรกยังไม่มีระบบล็อกอิน ให้ใส่ชื่อผู้แก้ไขไว้ก่อน รุ่นถัดไปค่อยผูกสิทธิ์ admin/หัวหน้า/พนักงาน")
        col1, col2, col3 = st.columns(3)
        selected_lead = col1.selectbox(
            "Lead Status",
            list(LEAD_STATUS_OPTIONS.keys()),
            format_func=lambda key: LEAD_STATUS_OPTIONS[key],
            index=safe_index(list(LEAD_STATUS_OPTIONS.keys()), lead_status),
        )
        selected_follow = col2.selectbox(
            "Follow-up Status",
            list(FOLLOW_UP_STATUS_OPTIONS.keys()),
            format_func=lambda key: FOLLOW_UP_STATUS_OPTIONS[key],
            index=safe_index(list(FOLLOW_UP_STATUS_OPTIONS.keys()), follow_up_status),
        )
        selected_priority = col3.selectbox(
            "Priority",
            list(PRIORITY_OPTIONS.keys()),
            format_func=lambda key: PRIORITY_OPTIONS[key],
            index=safe_index(list(PRIORITY_OPTIONS.keys()), priority),
        )
        date_value = parse_date(lead.get("follow_up_date"))
        selected_date = st.date_input("วันที่ต้องติดตาม", value=date_value)
        note = st.text_area("โน๊ตติดตาม", value=clean(lead.get("follow_up_note")), height=110)
        updated_by = st.text_input("ชื่อผู้แก้ไข", value=clean(lead.get("updated_by")))
        submitted = st.form_submit_button("บันทึก Lead / Follow-up", use_container_width=True)

    if submitted:
        error = save_lead_followup(
            customer,
            {
                "lead_status": selected_lead,
                "follow_up_status": selected_follow,
                "follow_up_date": selected_date,
                "follow_up_note": note,
                "priority": selected_priority,
                "updated_by": updated_by,
            },
        )
        if error:
            st.error("บันทึกไม่สำเร็จ: " + error)
        else:
            st.success("บันทึก Lead / Follow-up แล้ว")
            st.rerun()


def customer360_table(df: pd.DataFrame, lead_map: dict[str, dict]) -> pd.DataFrame:
    rows = []
    for _, row in df.iterrows():
        lead = lead_map.get(customer_detail_key(row), {})
        rows.append(
            {
                "ประวัติ": history_link(row),
                "Lead": lead_status_badge(lead.get("lead_status")),
                "Follow-up": follow_up_badge(lead),
                "ชื่อลูกค้า": first_value(row, "customer", "customer_name"),
                "กลุ่มสินค้า": first_value(row, "product_group"),
                "สินค้า": first_value(row, "product_name", "product"),
                "เบอร์โทรติดต่อ": first_value(row, "phone1"),
                "เบอร์โทรสำรอง": first_value(row, "phone2"),
                "โน๊ต": first_value(row, "note"),
                "ผู้ดูแล": first_value(row, "sales_staff", "owner"),
                "อัพเดต": count_checked_update_days(row),
                "URL": first_value(row, "product_url", "url", "channel_url"),
            }
        )
    return pd.DataFrame(rows)


def history_link(row: pd.Series) -> str:
    detail_key = customer_detail_key(row)
    href = "?" + urlencode({"customer_key": detail_key})
    return f'<a class="history-link" href="{html_escape(href)}">ดูประวัติ</a>'


def display_customers(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    rows_to_show = []
    working = df.copy()
    working["_source_index"] = working.index
    working["_phone_key"] = working.apply(customer_group_key, axis=1)
    working["_has_staff"] = working.apply(has_sales_staff, axis=1)

    for _, group in working.groupby("_phone_key", sort=False):
        with_staff = group[group["_has_staff"]]
        if not with_staff.empty:
            rows_to_show.append(with_staff)
            continue
        rows_to_show.append(group.head(1))

    display = pd.concat(rows_to_show, ignore_index=True) if rows_to_show else working.head(0)
    return display.drop(columns=["_phone_key", "_has_staff"], errors="ignore")


def customer_group_key(row: pd.Series) -> str:
    phones = customer_phones(row)
    if phones:
        return phones[0]
    customer = first_value(row, "customer", "customer_name")
    product_group = first_value(row, "product_group")
    if customer:
        return f"name:{customer}:{product_group}"
    return f"row:{row.name}"


def customer_detail_key(row: pd.Series) -> str:
    for name in ["customer_id", "id"]:
        value = first_value(row, name)
        if value:
            return f"{name}:{value}"
    phones = "|".join(customer_phones(row))
    parts = [
        phones,
        first_value(row, "customer", "customer_name"),
        first_value(row, "product_group"),
        first_value(row, "product_name", "product"),
        first_value(row, "sales_staff", "owner"),
        first_value(row, "product_url", "url", "channel_url"),
        first_value(row, "note"),
    ]
    return "fallback:" + "|".join(parts)


def has_sales_staff(row: pd.Series) -> bool:
    return bool(first_value(row, "sales_staff", "owner"))


def lead_status_badge(value: object) -> str:
    status = clean(value) or "new"
    label = LEAD_STATUS_OPTIONS.get(status, status)
    klass = {
        "new": "badge-blue",
        "contacted": "badge-gray",
        "interested": "badge-green",
        "follow_up": "badge-orange",
        "won": "badge-green",
        "lost": "badge-red",
        "dormant": "badge-gray",
    }.get(status, "badge-gray")
    return f'<span class="badge {klass}">{html_escape(label)}</span>'


def follow_up_badge(lead: dict | None) -> str:
    lead = lead or {}
    status = clean(lead.get("follow_up_status")) or "none"
    follow_date = parse_date(lead.get("follow_up_date"))
    if follow_date and status not in {"done", "missed"}:
        status = "missed" if follow_date < date.today() else "scheduled"
    label = FOLLOW_UP_STATUS_OPTIONS.get(status, status)
    if follow_date:
        label = f"{label} {follow_date.strftime('%d/%m/%Y')}"
    klass = {
        "none": "badge-gray",
        "scheduled": "badge-blue",
        "done": "badge-green",
        "missed": "badge-red",
    }.get(status, "badge-gray")
    return f'<span class="badge {klass}">{html_escape(label)}</span>'


def render_html_table(df: pd.DataFrame, numeric_cols: list[str] | None = None) -> None:
    numeric_cols = numeric_cols or []
    display = df.copy().fillna("")
    html_rows = ['<div class="crm-table-wrap"><table class="crm-table"><thead><tr>']
    for col in display.columns:
        html_rows.append(f"<th>{html_escape(col)}</th>")
    html_rows.append("</tr></thead><tbody>")

    for _, row in display.iterrows():
        html_rows.append("<tr>")
        for col in display.columns:
            klass = ' class="num"' if col in numeric_cols else ""
            html_rows.append(f"<td{klass}>{render_table_cell(col, row[col])}</td>")
        html_rows.append("</tr>")
    html_rows.append("</tbody></table></div>")
    st.markdown("".join(html_rows), unsafe_allow_html=True)


def render_detail_grid(rows: list[tuple[str, object]]) -> None:
    cells = ['<div class="crm-detail-grid">']
    for label, value in rows:
        text = clean(value) or "-"
        if is_url_label(label):
            rendered = render_url(text)
        elif is_safe_html(text):
            rendered = text
        else:
            rendered = html_escape(text)
        cells.append(
            '<div class="crm-detail-item">'
            f'<div class="crm-detail-label">{html_escape(label)}</div>'
            f'<div class="crm-detail-value">{rendered}</div>'
            "</div>"
        )
    cells.append("</div>")
    st.markdown("".join(cells), unsafe_allow_html=True)


def is_url_label(label: str) -> bool:
    return label in {"URL", "URL ออเดอร์"} or label.lower() in {"url", "product_url", "channel_url"}


def is_safe_html(value: str) -> bool:
    return value.startswith('<span class="badge')


def render_order_history(orders: list[dict]) -> None:
    st.subheader("ประวัติการสั่งซื้อเก่าทั้งหมด")
    for order in sort_orders(orders):
        products = parse_products(order.get("products"))
        html_card = (
            '<div class="order-card">'
            f'<span class="badge">ออเดอร์ {html_escape(order.get("order_id"))}</span>'
            f'<span class="badge">{html_escape(order.get("date_text")) or "-"}</span>'
            f'<span class="badge badge-green">{float(order.get("total_sales") or 0):,.0f} บาท</span>'
            f'{payment_badge(order.get("payment_method"))}'
            f'{delivery_badge(order.get("delivery_status"))}'
            "<div><b>สินค้า:</b></div>"
            f"{compact_product_list(products)}"
            f'<div><b>ที่อยู่:</b> {html_escape(full_address(order)) or "-"}</div>'
            f'<div><b>ผู้ขายเดิม:</b> {html_escape(order.get("sales_staff")) or "-"}</div>'
            f'<div><b>ขนส่ง:</b> {html_escape(order.get("shipping")) or "-"} / {html_escape(order.get("tracking_no")) or "-"}</div>'
            "</div>"
        )
        st.markdown(html_card, unsafe_allow_html=True)


def compact_product_list(products: list[dict]) -> str:
    if not products:
        return '<div class="muted">ไม่มีรายการสินค้า</div>'
    items = []
    for item in products:
        name = html_escape(item.get("name")) or "-"
        sku = html_escape(item.get("sku"))
        qty = html_escape(item.get("qty"))
        sku_text = f" ({sku})" if sku else ""
        qty_text = f" x {qty}" if qty else ""
        items.append(f"<div>{name}{sku_text}{qty_text}</div>")
    return "".join(items)


def product_table(products: list[dict]) -> str:
    if not products:
        return '<div class="muted">ไม่มีรายการสินค้า</div>'
    rows = []
    for item in products:
        rows.append(
            "<tr>"
            f"<td>{html_escape(item.get('sku')) or '-'}</td>"
            f"<td>{html_escape(item.get('name')) or '-'}</td>"
            f"<td>{html_escape(item.get('qty')) or '-'}</td>"
            f"<td>{html_escape(item.get('price')) or '0'}</td>"
            "</tr>"
        )
    return (
        '<div class="crm-table-wrap"><table class="crm-table"><thead><tr>'
        "<th>SKU</th><th>สินค้า</th><th>จำนวน</th><th>ราคา</th>"
        f"</tr></thead><tbody>{''.join(rows)}</tbody></table></div>"
    )


def payment_badge(value: object) -> str:
    text = clean(value)
    if not text:
        return '<span class="badge badge-gray">วิธีชำระ: -</span>'
    lowered = text.lower()
    if "cod" in lowered or "ปลายทาง" in text:
        label = "COD"
        klass = "badge-orange"
    elif "โอน" in text or "transfer" in lowered or "bank" in lowered:
        label = "โอน"
        klass = "badge-blue"
    else:
        label = text
        klass = "badge-gray"
    return f'<span class="badge {klass}">ชำระ: {html_escape(label)}</span>'


def delivery_badge(value: object) -> str:
    text = clean(value)
    if not text:
        return '<span class="badge badge-gray">จัดส่ง: -</span>'
    lowered = text.lower()
    if "สำเร็จ" in text or "delivered" in lowered or "success" in lowered:
        label = "ส่งสำเร็จ"
        klass = "badge-green"
    elif "ตีกลับ" in text or "return" in lowered:
        label = "ตีกลับ"
        klass = "badge-red"
    elif "ยกเลิก" in text or "cancel" in lowered:
        label = "ยกเลิก"
        klass = "badge-gray"
    else:
        label = text
        klass = "badge-orange"
    return f'<span class="badge {klass}">จัดส่ง: {html_escape(label)}</span>'


def render_setup_warning() -> None:
    error = st.session_state.get("customer360_customer_error", "")
    if error:
        st.error("ยังอ่านตาราง crm_customers ไม่ได้จาก Supabase")
        st.code(error, language="json")
    else:
        st.warning("ยังไม่มีข้อมูลลูกค้าใน crm_customers")
    st.info("ให้ตรวจ Supabase project ของ Streamlit secrets และรัน migration สำหรับสร้าง/เปิดสิทธิ์ตาราง crm_customers ก่อน deploy ใช้งานจริง")


def unique_customer_count(df: pd.DataFrame) -> int:
    if "customer_id" in df.columns:
        return int(df["customer_id"].nunique())
    phone_keys = df.apply(lambda row: customer_phones(row)[0] if customer_phones(row) else f"row-{row.name}", axis=1)
    return int(phone_keys.nunique())


def sort_orders(orders: list[dict]) -> list[dict]:
    def key(order: dict) -> tuple[int, int, int, str]:
        return (
            to_int(order.get("year_file") or order.get("year")),
            to_int(order.get("month")),
            to_int(order.get("day")),
            clean(order.get("source_key")),
        )

    return sorted(orders, key=key, reverse=True)


def customer_phones(row: pd.Series) -> tuple[str, ...]:
    phones = []
    for name in ["phone1", "phone2"]:
        phone = normalize_phone(row.get(name))
        if phone and phone not in phones:
            phones.append(phone)
    return tuple(phones)


def normalize_phone(value: object) -> str:
    phone = "".join(ch for ch in clean(value) if ch.isdigit())
    return phone if len(phone) >= 7 else ""


def count_checked_update_days(row: pd.Series) -> str:
    checkbox_names = [
        "call_1",
        "call_2",
        "call_3",
        "check_h",
        "check_j",
        "check_l",
        "update_check_1",
        "update_check_2",
        "update_check_3",
        "call_check_1",
        "call_check_2",
        "call_check_3",
        "checkbox_1",
        "checkbox_2",
        "checkbox_3",
        "h",
        "j",
        "l",
        "H",
        "J",
        "L",
    ]
    values = [row[name] for name in checkbox_names if name in row.index]
    if not values:
        values = [row.iloc[index] for index in [7, 9, 11] if index < len(row)]
    return f"{sum(1 for value in values if is_checked(value))} วัน"


def is_checked(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and not pd.isna(value):
        return value == 1
    text = str(value).strip().lower()
    return text in {"true", "yes", "y", "1", "checked", "ติ๊ก", "ติ้ก", "ถูก"}


def first_value(row: pd.Series, *names: str) -> str:
    for name in names:
        if name in row.index:
            value = clean(row.get(name))
            if value:
                return value
    return ""


def full_address(order: dict) -> str:
    parts = [
        clean(order.get("address")),
        clean(order.get("subdistrict")),
        clean(order.get("district")),
        clean(order.get("province")),
        clean(order.get("postcode")),
    ]
    return " ".join(part for part in parts if part)


def parse_products(value: object) -> list[dict]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else []
        except json.JSONDecodeError:
            return []
    return []


def product_summary(products: list[dict]) -> str:
    names = []
    for item in products:
        name = clean(item.get("name"))
        qty = clean(item.get("qty"))
        if name:
            names.append(f"{name} x {qty}" if qty else name)
    return " | ".join(names)


def render_table_cell(column: str, value: object) -> str:
    text = clean(value)
    if column == "ประวัติ":
        return text
    if column == "URL":
        return render_url(text)
    if is_safe_html(text):
        return text
    return html_escape(text)


def render_url(value: str) -> str:
    if value.startswith(("http://", "https://")):
        safe_url = html_escape(value)
        return f'<a href="{safe_url}" target="_blank" rel="noopener noreferrer">เปิดลิงก์</a>'
    return html_escape(value) or "-"


def clean(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and pd.isna(value):
        return ""
    return str(value).strip()


def parse_date(value: object) -> date | None:
    text = clean(value)
    if not text:
        return None
    try:
        return datetime.fromisoformat(text[:10]).date()
    except ValueError:
        return None


def to_int(value: object) -> int:
    try:
        return int(float(clean(value)))
    except ValueError:
        return 0


def html_escape(value: object) -> str:
    return html.escape(clean(value), quote=True)
