import streamlit as st
import pandas as pd
import requests
import json
from urllib.parse import quote

st.set_page_config(
    page_title="Sales Dashboard Pro Ultra",
    page_icon="📊",
    layout="wide"
)

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_ANON_KEY"]

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Prefer": "count=exact"
}

PAGE_LIMIT_OPTIONS = [50, 100, 200, 500]
SUMMARY_PAGE_SIZE = 1000
SUMMARY_MAX_ROWS = 500000


# =========================
# ULTRA THEME CSS
# =========================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

.stApp {
    background:
        radial-gradient(circle at top left, rgba(255,122,0,0.13), transparent 30%),
        linear-gradient(135deg, #FFF7ED 0%, #F8FAFC 42%, #FFFFFF 100%);
    color: #111827;
}

section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #FFFFFF 0%, #FFF7ED 100%);
    border-right: 1px solid #FED7AA;
    box-shadow: 8px 0 30px rgba(251,146,60,0.08);
}

section[data-testid="stSidebar"] * {
    color: #111827 !important;
}

.block-container {
    padding-top: 2rem;
    padding-bottom: 3rem;
}

[data-testid="stMetric"] {
    background: rgba(255,255,255,0.92);
    border: 1px solid #FED7AA;
    border-radius: 22px;
    padding: 20px;
    box-shadow: 0 10px 30px rgba(255,122,0,0.10);
}

[data-testid="stMetricLabel"] {
    color: #92400E !important;
    font-weight: 700;
}

[data-testid="stMetricValue"] {
    color: #111827 !important;
    font-size: 34px !important;
    font-weight: 800 !important;
}

.hero-card {
    background: linear-gradient(135deg, #FF7A00 0%, #FB923C 48%, #FDBA74 100%);
    border-radius: 28px;
    padding: 34px;
    margin-bottom: 26px;
    color: white;
    box-shadow: 0 20px 45px rgba(255,122,0,0.28);
}

.hero-title {
    font-size: 42px;
    font-weight: 900;
    margin-bottom: 6px;
}

.hero-subtitle {
    font-size: 16px;
    opacity: 0.95;
}

.glass-card {
    background: rgba(255,255,255,0.90);
    border: 1px solid #FED7AA;
    border-radius: 24px;
    padding: 22px;
    box-shadow: 0 12px 28px rgba(17,24,39,0.06);
    margin-bottom: 18px;
}

.customer-card {
    background: rgba(255,255,255,0.96);
    border: 1px solid #FED7AA;
    border-left: 8px solid #FF7A00;
    border-radius: 22px;
    padding: 20px;
    margin-bottom: 16px;
    box-shadow: 0 10px 24px rgba(255,122,0,0.08);
}

.order-card {
    background: #FFF7ED;
    border: 1px solid #FDBA74;
    border-radius: 18px;
    padding: 16px;
    margin-bottom: 12px;
}

.green {
    color: #16A34A;
    font-weight: 800;
}

.badge {
    display:inline-block;
    padding:7px 13px;
    border-radius:999px;
    background:#FF7A00;
    color:white;
    font-size:13px;
    font-weight:800;
}

.stButton > button {
    background: linear-gradient(90deg, #FF7A00 0%, #FB923C 100%);
    color: white !important;
    border: none;
    border-radius: 14px;
    padding: 10px 18px;
    font-weight: 800;
    transition: all 0.2s ease;
    box-shadow: 0 8px 18px rgba(255,122,0,0.18);
}

.stButton > button:hover {
    transform: translateY(-2px);
    box-shadow: 0 12px 24px rgba(255,122,0,0.28);
}

div[data-baseweb="select"] > div {
    background: white !important;
    border: 1px solid #FDBA74 !important;
    border-radius: 14px !important;
}

input {
    background: white !important;
    border: 1px solid #FDBA74 !important;
    border-radius: 14px !important;
}

[data-testid="stDataFrame"] {
    border: 1px solid #FED7AA;
    border-radius: 20px;
    overflow: hidden;
    box-shadow: 0 10px 24px rgba(17,24,39,0.05);
}

h1, h2, h3 {
    color: #EA580C !important;
    font-weight: 900 !important;
}

hr {
    border-color: #FED7AA;
}

div[data-testid="stExpander"] {
    background: white;
    border: 1px solid #FED7AA;
    border-radius: 16px;
}

#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}
</style>
""", unsafe_allow_html=True)


# =========================
# API
# =========================
def api_get(path, params):
    url = f"{SUPABASE_URL}/rest/v1/{path}?{'&'.join(params)}"
    res = requests.get(url, headers=HEADERS)

    if res.status_code not in [200, 206]:
        st.error(res.text)
        return [], 0

    total = 0
    content_range = res.headers.get("Content-Range", "")

    if "/" in content_range:
        try:
            total = int(content_range.split("/")[-1])
        except:
            total = 0

    return res.json(), total


def build_filter_params(keyword, year, province, channel, sales_staff, source_sheet):
    params = []

    if year != "ทั้งหมด":
        params.append(f"year=eq.{quote(year)}")

    if province != "ทั้งหมด":
        params.append(f"province=eq.{quote(province)}")

    if channel != "ทั้งหมด":
        params.append(f"channel=eq.{quote(channel)}")

    if sales_staff != "ทั้งหมด":
        params.append(f"sales_staff=eq.{quote(sales_staff)}")

    if source_sheet != "ทั้งหมด":
        params.append(f"source_sheet=eq.{quote(source_sheet)}")

    if keyword:
        kw = quote(keyword.strip())
        params.append(
            f"or=(customer.ilike.*{kw}*,phone1.ilike.*{kw}*,phone2.ilike.*{kw}*,order_id.ilike.*{kw}*)"
        )

    return params


# =========================
# DATA LOADERS
# =========================
@st.cache_data(ttl=180)
def get_filter_options():
    rows, _ = api_get(
        "orders",
        ["select=year,province,channel,sales_staff,source_sheet", "limit=50000"]
    )

    df = pd.DataFrame(rows)

    if df.empty:
        return {
            "years": [],
            "provinces": [],
            "channels": [],
            "sales_staff": [],
            "source_sheets": [],
        }

    def unique_col(col):
        if col not in df.columns:
            return []
        return sorted(df[col].dropna().astype(str).unique().tolist())

    return {
        "years": unique_col("year"),
        "provinces": unique_col("province"),
        "channels": unique_col("channel"),
        "sales_staff": unique_col("sales_staff"),
        "source_sheets": unique_col("source_sheet"),
    }


@st.cache_data(ttl=90)
def load_summary(keyword, year, province, channel, sales_staff, source_sheet):
    base_filters = build_filter_params(keyword, year, province, channel, sales_staff, source_sheet)
    all_rows = []
    offset = 0

    while offset < SUMMARY_MAX_ROWS:
        params = ["select=*"] + base_filters + [
            "order=synced_at.desc",
            f"limit={SUMMARY_PAGE_SIZE}",
            f"offset={offset}"
        ]

        rows, _ = api_get("orders", params)

        if not rows:
            break

        all_rows.extend(rows)

        if len(rows) < SUMMARY_PAGE_SIZE:
            break

        offset += SUMMARY_PAGE_SIZE

    return pd.DataFrame(all_rows)


@st.cache_data(ttl=90)
def load_page(keyword, year, province, channel, sales_staff, source_sheet, limit, offset):
    base_filters = build_filter_params(keyword, year, province, channel, sales_staff, source_sheet)

    params = ["select=*"] + base_filters + [
        "order=synced_at.desc",
        f"limit={limit}",
        f"offset={offset}"
    ]

    rows, total = api_get("orders", params)
    return pd.DataFrame(rows), total


# =========================
# HELPERS
# =========================
def to_number(s):
    return pd.to_numeric(s, errors="coerce").fillna(0)


def product_text(products):
    if isinstance(products, str):
        try:
            products = json.loads(products)
        except:
            return products

    if not isinstance(products, list):
        return ""

    out = []
    for p in products:
        if isinstance(p, dict):
            name = p.get("name", "")
            qty = p.get("qty", "")
            if name:
                out.append(f"• {name} x {qty}")
    return "\n".join(out)


def safe_group_sum(df, group_col, value_col="total_sales", top=None):
    if group_col not in df.columns or value_col not in df.columns:
        return pd.Series(dtype=float)

    s = df.groupby(group_col)[value_col].sum().sort_values(ascending=False)

    if top:
        return s.head(top)

    return s


def safe_group_count(df, group_col, count_col="order_id", top=None):
    if group_col not in df.columns or count_col not in df.columns:
        return pd.Series(dtype=float)

    s = df.groupby(group_col)[count_col].nunique().sort_values(ascending=False)

    if top:
        return s.head(top)

    return s


# =========================
# SIDEBAR
# =========================
options = get_filter_options()

st.sidebar.markdown("## 🔎 ตัวกรอง")
st.sidebar.caption("กรองข้อมูลยอดขาย ลูกค้า และแหล่งข้อมูล")

keyword = st.sidebar.text_input("ค้นหา ชื่อ / เบอร์ / เลขออเดอร์")

year = st.sidebar.selectbox("ปี", ["ทั้งหมด"] + options["years"])
source_sheet = st.sidebar.selectbox("แหล่งข้อมูล", ["ทั้งหมด"] + options["source_sheets"])
province = st.sidebar.selectbox("จังหวัด", ["ทั้งหมด"] + options["provinces"])
channel = st.sidebar.selectbox("ช่องทาง", ["ทั้งหมด"] + options["channels"])
sales_staff = st.sidebar.selectbox("พนักงานขาย", ["ทั้งหมด"] + options["sales_staff"])

limit = st.sidebar.selectbox("จำนวนแสดงต่อหน้า", PAGE_LIMIT_OPTIONS, index=0)

if "page" not in st.session_state:
    st.session_state.page = 1

col_prev, col_next = st.sidebar.columns(2)

if col_prev.button("⬅️ ย้อนกลับ") and st.session_state.page > 1:
    st.session_state.page -= 1

if col_next.button("ถัดไป ➡️"):
    st.session_state.page += 1

if st.sidebar.button("🔄 ล้าง Cache / Refresh"):
    st.cache_data.clear()
    st.rerun()


# =========================
# HERO
# =========================
st.markdown("""
<div class="hero-card">
    <div class="hero-title">📊 Sales Dashboard Pro Ultra</div>
    <div class="hero-subtitle">
        ระบบวิเคราะห์ยอดขาย ลูกค้า ช่องทาง พนักงาน และแหล่งข้อมูลแบบรวมศูนย์
    </div>
</div>
""", unsafe_allow_html=True)


# =========================
# LOAD DATA
# =========================
page = st.session_state.page
offset = (page - 1) * limit

with st.spinner("กำลังโหลดข้อมูล Dashboard..."):
    summary_df = load_summary(keyword, year, province, channel, sales_staff, source_sheet)
    page_df, total_count = load_page(keyword, year, province, channel, sales_staff, source_sheet, limit, offset)

if summary_df.empty:
    st.warning("❌ ไม่พบข้อมูลตามตัวกรอง")
    st.stop()

summary_df["total_sales"] = to_number(summary_df["total_sales"])

if not page_df.empty and "total_sales" in page_df.columns:
    page_df["total_sales"] = to_number(page_df["total_sales"])

total_pages = max(1, (total_count + limit - 1) // limit)


# =========================
# KPI
# =========================
k1, k2, k3, k4 = st.columns(4)

k1.metric("💰 ยอดขายรวม", f"{summary_df['total_sales'].sum():,.0f}")
k2.metric("📦 ออเดอร์ทั้งหมด", f"{summary_df['order_id'].nunique():,}")
k3.metric("👤 ลูกค้าทั้งหมด", f"{summary_df['phone1'].nunique():,}")
k4.metric("📄 หน้า", f"{page:,} / {total_pages:,}")

st.divider()


# =========================
# CUSTOMER SEARCH
# =========================
if keyword and not page_df.empty:
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.subheader("👥 ผลการค้นหาลูกค้า")

    customer_df = (
        summary_df.groupby(["customer", "phone1"], dropna=False)
        .agg(
            total_sales=("total_sales", "sum"),
            total_orders=("order_id", "count"),
            latest_date=("date_text", "max")
        )
        .reset_index()
        .sort_values("total_sales", ascending=False)
    )

    for _, c in customer_df.iterrows():
        st.markdown(f"""
        <div class="customer-card">
            <h3>👤 {c['customer']}</h3>
            <span class="badge">📞 {c['phone1']}</span>
            &nbsp;
            <span class="green">📦 ซื้อ {int(c['total_orders'])} ครั้ง</span>
            <br><br>
            📅 ล่าสุด: <b>{c['latest_date']}</b><br>
            💰 ยอดรวม: <span class="green">{c['total_sales']:,.0f}</span>
        </div>
        """, unsafe_allow_html=True)

        history = summary_df[summary_df["phone1"] == c["phone1"]].sort_values("date_text", ascending=False)

        with st.expander("📜 ดูประวัติการซื้อทั้งหมด"):
            for _, h in history.iterrows():
                st.markdown(f"""
                <div class="order-card">
                    🚀 <b>{h.get('order_id','')}</b>
                    &nbsp;&nbsp; 📅 {h.get('date_text','')}
                    &nbsp;&nbsp; 💰 <span class="green">{h.get('total_sales',0):,.0f}</span>
                    <br><br>
                    📦 สินค้า<br>
                    <pre>{product_text(h.get('products'))}</pre>
                </div>
                """, unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)


# =========================
# DASHBOARD
# =========================
st.subheader("📈 Dashboard รวมตามตัวกรอง")

c1, c2 = st.columns(2)

with c1:
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.markdown("### 📈 ยอดขายตามช่องทาง")
    channel_sales = safe_group_sum(summary_df, "channel")
    if not channel_sales.empty:
        st.bar_chart(channel_sales)
    st.markdown('</div>', unsafe_allow_html=True)

with c2:
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.markdown("### 🏆 จังหวัดยอดขายสูงสุด")
    province_sales = safe_group_sum(summary_df, "province", top=10)
    if not province_sales.empty:
        st.bar_chart(province_sales)
    st.markdown('</div>', unsafe_allow_html=True)

c3, c4 = st.columns(2)

with c3:
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.markdown("### 👨‍💼 ยอดขายตามพนักงานขาย")
    staff_sales = safe_group_sum(summary_df, "sales_staff", top=10)
    if not staff_sales.empty:
        st.bar_chart(staff_sales)
    st.markdown('</div>', unsafe_allow_html=True)

with c4:
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.markdown("### 📦 จำนวนออเดอร์ตามแหล่งข้อมูล")
    source_orders = safe_group_count(summary_df, "source_sheet")
    if not source_orders.empty:
        st.bar_chart(source_orders)
    st.markdown('</div>', unsafe_allow_html=True)


st.divider()


# =========================
# DATA TABLE
# =========================
st.subheader("📋 รายการข้อมูล")

if page_df.empty:
    st.warning("หน้านี้ไม่มีข้อมูล")
else:
    show_cols = [
        "order_id",
        "year",
        "source_sheet",
        "date_text",
        "customer",
        "phone1",
        "address",
        "subdistrict",
        "district",
        "province",
        "shipping",
        "tracking_no",
        "channel",
        "sales_staff",
        "upsell_staff",
        "total_sales"
    ]

    show_cols = [c for c in show_cols if c in page_df.columns]
    show_cols = list(dict.fromkeys(show_cols))

    display_df = page_df[show_cols].copy()

    for col in display_df.columns:
        if display_df[col].dtype == "object":
            display_df[col] = display_df[col].fillna("").astype(str)

    st.dataframe(
        display_df,
        use_container_width=True,
        height=540
    )


st.caption(
    f"แสดงหน้า {page:,} จากทั้งหมด {total_pages:,} หน้า | รวม {total_count:,} รายการตามตัวกรอง"
)