import os
import html
from datetime import date, datetime

import pandas as pd
import requests
import streamlit as st
import streamlit.components.v1 as components


st.set_page_config(page_title="Project CRM Dashboard", layout="wide")

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


st.markdown(
    """
    <style>
    :root {
      --crm-bg: #fff7ed;
      --crm-panel: #ffffff;
      --crm-border: #fed7aa;
      --crm-soft-border: #e5e7eb;
      --crm-text: #111827;
      --crm-muted: #475569;
      --crm-accent: #f97316;
      --crm-accent-dark: #ea580c;
      --crm-dark: #111827;
    }
    .stApp {
      background: var(--crm-bg);
      color: var(--crm-text);
    }
    [data-testid="stSidebar"] {
      background: #fffaf5;
      border-right: 1px solid var(--crm-border);
    }
    [data-testid="stSidebar"] * {
      color: var(--crm-text) !important;
    }
    [data-testid="stSidebar"] input,
    [data-testid="stSidebar"] textarea,
    [data-testid="stSidebar"] [data-baseweb="select"] > div {
      background: #ffffff !important;
      color: var(--crm-text) !important;
      border-color: var(--crm-accent) !important;
      border-radius: 8px !important;
    }
    [data-testid="stSidebar"] input::placeholder {
      color: #94a3b8 !important;
      opacity: 1 !important;
    }
    [data-testid="stSidebarNav"] a {
      color: var(--crm-text) !important;
      border-radius: 6px;
    }
    [data-testid="stSidebarNav"] a[aria-current="page"],
    [data-testid="stSidebarNav"] a:hover {
      background: #ffedd5 !important;
      color: var(--crm-accent-dark) !important;
      font-weight: 700;
    }
    [data-testid="stMetric"] {
      background: var(--crm-panel);
      border: 1px solid var(--crm-border);
      border-radius: 8px;
      padding: 16px 18px;
      box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
    }
    [data-testid="stMetricLabel"] p {
      color: var(--crm-muted);
      font-size: 0.9rem;
    }
    [data-testid="stMetricValue"] {
      color: var(--crm-accent-dark);
      font-weight: 700;
    }
    h1 {
      color: var(--crm-text);
      letter-spacing: 0;
      border-left: 6px solid var(--crm-accent);
      padding-left: 14px;
    }
    .block-container {
      padding-top: 2rem;
      padding-bottom: 3rem;
    }
    .crm-table-wrap {
      border: 1px solid var(--crm-soft-border);
      border-radius: 8px;
      overflow: hidden;
      background: #ffffff;
      box-shadow: 0 1px 2px rgba(15, 23, 42, 0.05);
      margin-top: 12px;
    }
    .crm-table {
      width: 100%;
      border-collapse: collapse;
      font-size: 14px;
      color: var(--crm-text);
      background: #ffffff;
    }
    .crm-table thead th {
      background: #ffedd5;
      color: #7c2d12;
      font-weight: 700;
      text-align: left;
      padding: 11px 12px;
      border-bottom: 1px solid #fdba74;
      white-space: nowrap;
    }
    .crm-table tbody td {
      padding: 10px 12px;
      border-bottom: 1px solid #f1f5f9;
      color: var(--crm-text);
      vertical-align: top;
    }
    .crm-table tbody tr:nth-child(even) {
      background: #fffaf5;
    }
    .crm-table tbody tr:hover {
      background: #ffedd5;
    }
    .crm-table .num {
      text-align: right;
      font-variant-numeric: tabular-nums;
      font-weight: 700;
      color: var(--crm-accent-dark);
    }
    .crm-table-caption {
      color: var(--crm-muted);
      font-size: 13px;
      margin-top: 6px;
    }
    .stTabs [data-baseweb="tab-list"] {
      gap: 8px;
      border-bottom: 1px solid var(--crm-border);
    }
    .stTabs [data-baseweb="tab"] {
      padding: 10px 12px;
      color: var(--crm-muted);
    }
    .stTabs [aria-selected="true"] {
      color: var(--crm-accent-dark);
      border-bottom-color: var(--crm-accent);
      font-weight: 700;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


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


@st.cache_data(ttl=30, show_spinner=False)
def load_customers() -> pd.DataFrame:
    require_config()
    endpoint = f"{SUPABASE_URL}/rest/v1/crm_customers"
    headers = {
        "apikey": SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
    }
    params = {
        "select": "*",
        "order": "updated_at.desc",
        "limit": "50000",
    }
    response = requests.get(endpoint, headers=headers, params=params, timeout=30)
    if response.status_code >= 300:
        st.error(response.text)
        st.stop()
    return pd.DataFrame(response.json())


def normalize_dates(df: pd.DataFrame) -> pd.DataFrame:
    for col in ["updated_at", "synced_at", "call_date_1", "call_date_2", "call_date_3"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")
    return df


def sidebar_filters(df: pd.DataFrame) -> pd.DataFrame:
    st.sidebar.header("ตัวกรอง")

    product_options = [g for g in PRODUCT_GROUP_ORDER if g in set(df.get("product_group", []))]
    extra_groups = sorted(set(df.get("product_group", pd.Series(dtype=str)).dropna()) - set(product_options))
    product_group = st.sidebar.selectbox("กลุ่มสินค้า", ["ทั้งหมด"] + product_options + extra_groups)

    staff_options = sorted(df.get("sales_staff", pd.Series(dtype=str)).dropna().unique().tolist())
    staff = st.sidebar.selectbox("ผู้ดูแล", ["ทั้งหมด"] + staff_options)

    keyword = st.sidebar.text_input("ค้นหา", placeholder="ชื่อลูกค้า เบอร์ สินค้า หรือโน๊ต")

    min_date = df["updated_at"].min().date() if "updated_at" in df and df["updated_at"].notna().any() else date.today()
    max_date = df["updated_at"].max().date() if "updated_at" in df and df["updated_at"].notna().any() else date.today()
    date_range = st.sidebar.date_input("ช่วงวันที่อัพเดต", value=(min_date, max_date))

    filtered = df.copy()
    if product_group != "ทั้งหมด":
        filtered = filtered[filtered["product_group"] == product_group]
    if staff != "ทั้งหมด":
        filtered = filtered[filtered["sales_staff"] == staff]
    if keyword:
        text_cols = ["customer", "phone1", "phone2", "product_url", "product_name", "note"]
        available = [col for col in text_cols if col in filtered.columns]
        haystack = filtered[available].fillna("").astype(str).agg(" ".join, axis=1)
        filtered = filtered[haystack.str.contains(keyword, case=False, na=False)]
    if isinstance(date_range, tuple) and len(date_range) == 2 and "updated_at" in filtered:
        start, end = date_range
        filtered = filtered[
            (filtered["updated_at"].dt.date >= start)
            & (filtered["updated_at"].dt.date <= end)
        ]
    return filtered


def sidebar_refresh_controls() -> None:
    st.sidebar.header("อัปเดตข้อมูล")
    auto_refresh = st.sidebar.toggle(
        f"รีเฟรชอัตโนมัติทุก {AUTO_REFRESH_SECONDS} วินาที",
        value=True,
    )
    if st.sidebar.button("รีเฟรชข้อมูลตอนนี้", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    if auto_refresh:
        schedule_auto_refresh(AUTO_REFRESH_SECONDS)


def schedule_auto_refresh(seconds: int) -> None:
    components.html(
        f"""
        <script>
          window.setTimeout(function() {{
            window.parent.location.reload();
          }}, {seconds * 1000});
        </script>
        """,
        height=0,
        width=0,
    )


def customer_table(df: pd.DataFrame) -> pd.DataFrame:
    display_cols = [
        "customer",
        "sales_staff",
        "product_group",
        "product_name",
        "phone1",
        "phone2",
        "note",
        "updated_at",
        "synced_at",
    ]
    cols = [col for col in display_cols if col in df.columns]
    table_df = df[cols].copy()

    if "updated_at" in table_df:
        table_df["updated_at"] = table_df["updated_at"].dt.strftime("%Y-%m-%d %H:%M").fillna("")
    if "synced_at" in table_df:
        table_df["synced_at"] = "ซิงก์แล้ว"

    return table_df.rename(
        columns={
            "customer": "ชื่อลูกค้า",
            "sales_staff": "ผู้ดูแล",
            "product_group": "กลุ่มสินค้า",
            "product_name": "สินค้า",
            "phone1": "เบอร์โทรติดต่อ",
            "phone2": "เบอร์โทรสำรอง",
            "note": "โน๊ต",
            "updated_at": "อัพเดต",
            "synced_at": "สถานะ",
        }
    )


def count_summary(df: pd.DataFrame, group_col: str, label: str) -> pd.DataFrame:
    if group_col not in df or "customer_id" not in df:
        return pd.DataFrame(columns=[label, "จำนวนลูกค้า", "จำนวนแถว"])

    summary = (
        df.groupby(group_col, dropna=False)
        .agg(customer_count=("customer_id", "nunique"), row_count=("customer_id", "count"))
        .reset_index()
        .sort_values(["customer_count", "row_count"], ascending=False)
    )
    summary[group_col] = summary[group_col].fillna("ไม่ระบุ").replace("", "ไม่ระบุ")
    return summary.rename(
        columns={
            group_col: label,
            "customer_count": "จำนวนลูกค้า",
            "row_count": "จำนวนแถว",
        }
    )


def render_html_table(df: pd.DataFrame, numeric_cols: list[str] | None = None) -> None:
    numeric_cols = numeric_cols or []
    display = df.copy().fillna("")

    html = ['<div class="crm-table-wrap"><table class="crm-table">']
    html.append("<thead><tr>")
    for col in display.columns:
        html.append(f"<th>{html_escape_(col)}</th>")
    html.append("</tr></thead><tbody>")

    for _, row in display.iterrows():
        html.append("<tr>")
        for col in display.columns:
            klass = ' class="num"' if col in numeric_cols else ""
            html.append(f"<td{klass}>{html_escape_(row[col])}</td>")
        html.append("</tr>")

    html.append("</tbody></table></div>")
    st.markdown("".join(html), unsafe_allow_html=True)


def html_escape_(value: object) -> str:
    return html.escape(str(value), quote=True)


st.title("Project CRM Dashboard")
sidebar_refresh_controls()

df = normalize_dates(load_customers())
if df.empty:
    st.warning("ยังไม่มีข้อมูลใน Supabase")
    st.stop()

filtered = sidebar_filters(df)
st.caption("Dashboard โหลดข้อมูลล่าสุด: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

col1, col2, col3, col4 = st.columns(4)
col1.metric("ลูกค้าทั้งหมด", f"{filtered['customer_id'].nunique():,}")
col2.metric("จำนวนแถว", f"{len(filtered):,}")
col3.metric("กลุ่มสินค้า", f"{filtered['product_group'].nunique():,}")
col4.metric("ผู้ดูแล", f"{filtered['sales_staff'].nunique():,}")

tab_table, tab_group, tab_staff = st.tabs(["ข้อมูลลูกค้า", "ตามกลุ่มสินค้า", "ตามพนักงาน"])

with tab_table:
    table_df = customer_table(filtered)
    page_size = st.selectbox("จำนวนแถวต่อหน้า", [50, 100, 200], index=1, key="customer_page_size")
    total_pages = max((len(table_df) - 1) // page_size + 1, 1)
    page = st.number_input("หน้า", min_value=1, max_value=total_pages, value=1, step=1)
    start = (page - 1) * page_size
    end = start + page_size
    render_html_table(table_df.iloc[start:end])
    st.caption(f"แสดง {start + 1 if len(table_df) else 0}-{min(end, len(table_df))} จาก {len(table_df):,} แถว")

with tab_group:
    group_df = count_summary(filtered, "product_group", "กลุ่มสินค้า")
    render_html_table(group_df, numeric_cols=["จำนวนลูกค้า", "จำนวนแถว"])

with tab_staff:
    staff_df = count_summary(filtered, "sales_staff", "ผู้ดูแล")
    render_html_table(staff_df, numeric_cols=["จำนวนลูกค้า", "จำนวนแถว"])
