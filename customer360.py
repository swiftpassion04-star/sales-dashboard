import html
import json
import os
from datetime import datetime
from urllib.parse import quote

import pandas as pd
import requests
import streamlit as st
import streamlit.components.v1 as components


CUSTOMERS_TABLE = "crm_customers"
ORDERS_TABLE = "order_history"
FETCH_LIMIT = 1000
ORDER_MAX_FETCH = 5000
CUSTOMER_MAX_FETCH = 100000
PAGE_SIZE_OPTIONS = [10, 25, 50, 100]
AUTO_REFRESH_SECONDS = 60

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


def render_customer360() -> None:
    inject_css()
    sidebar_refresh_controls()

    customers = load_crm_customers()
    st.title("Customer 360")

    if customers.empty:
        render_setup_warning()
        st.stop()

    filtered = sidebar_filters(customers)
    if filtered.empty:
        st.warning("ไม่พบลูกค้าตามเงื่อนไขที่เลือก")
        st.stop()

    filtered = filtered.reset_index(drop=True)
    if "customer360_detail_idx" in st.session_state and st.session_state.customer360_detail_idx is not None:
        render_customer_detail(filtered)
        return

    render_customer_list(filtered)


def inject_css() -> None:
    st.markdown(
        """
<style>
:root {
  --crm-bg:#fff7ed;
  --crm-panel:#ffffff;
  --crm-border:#fed7aa;
  --crm-soft-border:#e5e7eb;
  --crm-text:#111827;
  --crm-muted:#475569;
  --crm-accent:#f97316;
  --crm-accent-dark:#ea580c;
  --crm-green:#15803d;
}
.stApp { background:var(--crm-bg); color:var(--crm-text); }
.block-container { max-width:1500px; padding-top:2.2rem; padding-bottom:3rem; }
[data-testid="stSidebar"] {
  background:#fffaf5;
  border-right:1px solid var(--crm-border);
}
[data-testid="stSidebar"] * { color:var(--crm-text) !important; }
[data-testid="stSidebar"] input,
[data-testid="stSidebar"] textarea,
[data-testid="stSidebar"] [data-baseweb="select"] > div {
  background:#ffffff !important;
  color:var(--crm-text) !important;
  border-color:var(--crm-accent) !important;
  border-radius:8px !important;
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
[data-testid="stSidebarNav"] a[href$="/"]::after,
[data-testid="stSidebarNav"] a[href*="/~/+/customers"]::after,
[data-testid="stSidebarNav"] a[href*="/customers"]::after {
  content:"Customer 360";
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
}
h2, h3 { color:var(--crm-text); letter-spacing:0; }
[data-testid="stMetric"] {
  background:var(--crm-panel);
  border:1px solid var(--crm-border);
  border-radius:8px;
  padding:16px 18px;
  box-shadow:0 1px 2px rgba(15,23,42,.04);
}
[data-testid="stMetricValue"] { color:var(--crm-accent-dark); font-weight:700; }
.crm-table-wrap {
  border:1px solid var(--crm-soft-border);
  border-radius:8px;
  overflow:auto;
  background:#ffffff;
  box-shadow:0 1px 2px rgba(15,23,42,.05);
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
  background:#ffedd5;
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
  vertical-align:top;
  min-width:110px;
}
.crm-table tbody tr:nth-child(even) { background:#fffaf5; }
.crm-table tbody tr:hover { background:#ffedd5; }
.crm-table .num {
  text-align:right;
  font-variant-numeric:tabular-nums;
  font-weight:700;
  color:var(--crm-accent-dark);
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
  background:#ffffff;
  padding:12px 14px;
}
.crm-detail-label { color:var(--crm-muted); font-size:13px; margin-bottom:4px; }
.crm-detail-value { color:var(--crm-text); font-weight:700; overflow-wrap:anywhere; }
.order-card {
  background:#ffffff;
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
.green { color:var(--crm-green); font-weight:700; }
.muted { color:var(--crm-muted); }
.stButton > button {
  border-radius:8px;
  font-weight:700;
}
[data-testid="stSidebar"] .stButton > button {
  background:linear-gradient(90deg,#ff7a00 0%,#fb923c 100%);
  color:#ffffff !important;
  border:none;
  min-height:42px;
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


def request_headers() -> dict[str, str]:
    return {
        "apikey": SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
        "Prefer": "count=exact",
    }


def api_get(path: str, params: list[str]) -> tuple[list[dict], str | None]:
    require_config()
    url = f"{SUPABASE_URL}/rest/v1/{path}?{'&'.join(params)}"
    response = requests.get(url, headers=request_headers(), timeout=30)
    if response.status_code not in (200, 206):
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
    product_options = [group for group in PRODUCT_GROUP_ORDER if group in set(df.get("product_group", []))]
    extras = sorted(set(df.get("product_group", pd.Series(dtype=str)).dropna().astype(str)) - set(product_options))
    staff_options = sorted(df.get("sales_staff", pd.Series(dtype=str)).dropna().astype(str).unique().tolist())

    product_group = st.sidebar.selectbox("กลุ่มสินค้า", ["ทั้งหมด"] + product_options + extras)
    staff = st.sidebar.selectbox("ผู้ดูแล", ["ทั้งหมด"] + staff_options)
    keyword = st.sidebar.text_input("ค้นหา", placeholder="ชื่อลูกค้า / เบอร์ / สินค้า / โน๊ต / URL")
    year = st.sidebar.selectbox("ประวัติปี", ["ทั้งหมด", "2565", "2566", "2567", "2568", "2569"])
    st.session_state.customer360_year = year

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

    if st.sidebar.button("ล้างตัวกรอง", use_container_width=True):
        st.session_state.customer360_detail_idx = None
        st.rerun()

    return filtered


def render_customer_list(df: pd.DataFrame) -> None:
    total_customers = unique_customer_count(df)
    total_rows = len(df)
    with_phone = sum(1 for _, row in df.iterrows() if customer_phones(row))

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("ลูกค้าปัจจุบัน", f"{total_customers:,}")
    col2.metric("จำนวนแถว", f"{total_rows:,}")
    col3.metric("กลุ่มสินค้า", f"{df.get('product_group', pd.Series(dtype=str)).nunique():,}")
    col4.metric("มีเบอร์โทร", f"{with_phone:,}")

    st.caption("รวมลูกค้าปัจจุบันจากชีทหัวหน้า และกดดูประวัติสั่งซื้อเก่าที่จับคู่ด้วยเบอร์โทรติดต่อ/เบอร์โทรสำรอง")

    page_size = st.selectbox("จำนวนแถวต่อหน้า", PAGE_SIZE_OPTIONS, index=1, key="customer360_page_size")
    total_pages = max((len(df) - 1) // page_size + 1, 1)
    page = st.number_input("หน้า", min_value=1, max_value=total_pages, value=1, step=1, key="customer360_page")
    start = (page - 1) * page_size
    end = start + page_size

    page_df = df.iloc[start:end].reset_index(drop=True)
    render_html_table(customer360_table(page_df))

    st.caption(f"แสดง {start + 1 if len(df) else 0}-{min(end, len(df))} จาก {len(df):,} แถว")
    st.divider()

    for i, customer in page_df.iterrows():
        abs_idx = start + i
        name = first_value(customer, "customer", "customer_name") or f"ลูกค้าแถวที่ {abs_idx + 1}"
        if st.button(f"ดูประวัติสั่งซื้อเก่า: {name}", key=f"customer360_detail_{abs_idx}"):
            st.session_state.customer360_detail_idx = abs_idx
            st.rerun()


def render_customer_detail(df: pd.DataFrame) -> None:
    idx = st.session_state.customer360_detail_idx
    if idx >= len(df):
        st.session_state.customer360_detail_idx = None
        st.rerun()

    customer = df.iloc[idx]
    phones = customer_phones(customer)
    year = st.session_state.get("customer360_year", "ทั้งหมด")
    order_df = search_orders_by_phones(phones, year)
    orders = order_df.to_dict("records") if not order_df.empty else []
    latest = sort_orders(orders)[0] if orders else {}

    if st.button("กลับหน้า Customer 360"):
        st.session_state.customer360_detail_idx = None
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

    if not orders:
        st.info("ยังไม่พบประวัติคำสั่งซื้อจาก DATA_RAW ที่ตรงกับเบอร์โทรติดต่อหรือเบอร์โทรสำรอง")
        return

    st.subheader("ออเดอร์ล่าสุด")
    latest_products = parse_products(latest.get("products"))
    render_detail_grid(
        [
            ("เลขออเดอร์", latest.get("order_id")),
            ("วันที่", latest.get("date_text")),
            ("ผู้ขายเดิม", latest.get("sales_staff")),
            ("พนักงาน UPSELL", latest.get("upsell_staff")),
            ("พนักงานดูแล", latest.get("care_staff")),
            ("ยอดขาย", f"{float(latest.get('total_sales') or 0):,.0f} บาท"),
            ("สถานะคำสั่งซื้อ", latest.get("order_status")),
            ("ที่อยู่จัดส่ง", full_address(latest)),
            ("URL ออเดอร์", latest.get("channel_url")),
        ]
    )

    st.subheader("สินค้าที่เคยซื้อ")
    st.markdown(product_table(latest_products), unsafe_allow_html=True)
    render_order_history(orders)


def customer360_table(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, row in df.iterrows():
        rows.append(
            {
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
        if label == "URL" or label.endswith("URL") or label == "URL ออเดอร์":
            rendered = render_url(text)
        else:
            rendered = html_escape(text)
        cells.append(
            f"""
            <div class="crm-detail-item">
              <div class="crm-detail-label">{html_escape(label)}</div>
              <div class="crm-detail-value">{rendered}</div>
            </div>
            """
        )
    cells.append("</div>")
    st.markdown("".join(cells), unsafe_allow_html=True)


def render_order_history(orders: list[dict]) -> None:
    st.subheader("ประวัติการสั่งซื้อเก่าทั้งหมด")
    for order in sort_orders(orders):
        products = parse_products(order.get("products"))
        summary = product_summary(products) or "-"
        st.markdown(
            f"""
            <div class="order-card">
              <span class="badge">ออเดอร์ {html_escape(order.get("order_id"))}</span>
              <span class="badge">{html_escape(order.get("date_text")) or "-"}</span>
              <span class="badge badge-green">{float(order.get("total_sales") or 0):,.0f} บาท</span>
              <div><b>สินค้า:</b> {html_escape(summary)}</div>
              <div><b>ที่อยู่:</b> {html_escape(full_address(order)) or "-"}</div>
              <div><b>ผู้ขายเดิม:</b> {html_escape(order.get("sales_staff")) or "-"}</div>
              <div><b>ขนส่ง:</b> {html_escape(order.get("shipping")) or "-"} / {html_escape(order.get("tracking_no")) or "-"}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


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
    if column == "URL":
        return render_url(text)
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


def to_int(value: object) -> int:
    try:
        return int(float(clean(value)))
    except ValueError:
        return 0


def html_escape(value: object) -> str:
    return html.escape(clean(value), quote=True)
