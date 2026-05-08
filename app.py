import streamlit as st
import pandas as pd
import requests
from urllib.parse import quote

st.set_page_config(
    page_title="Sales Dashboard Pro",
    layout="wide"
)

# =====================================================
# CONFIG
# =====================================================

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_ANON_KEY"]

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
}

# =====================================================
# STYLE
# =====================================================

st.markdown("""
<style>

.main {
    background-color: #0e1117;
}

.block-container {
    padding-top: 1rem;
}

[data-testid="stMetric"] {
    background: #111827;
    padding: 15px;
    border-radius: 14px;
    border: 1px solid #1f2937;
}

.customer-card {
    background: #111827;
    border: 1px solid #1f2937;
    padding: 20px;
    border-radius: 18px;
    margin-bottom: 18px;
}

.order-card {
    background: #0f172a;
    border: 1px solid #1e293b;
    padding: 18px;
    border-radius: 14px;
    margin-bottom: 12px;
}

.green {
    color: #00e676;
    font-weight: 700;
}

.blue-badge {
    display:inline-block;
    background:#1d4ed8;
    padding:6px 12px;
    border-radius:999px;
    color:white;
    font-size:13px;
    font-weight:700;
}

.purple-badge {
    display:inline-block;
    background:#7c3aed;
    padding:6px 12px;
    border-radius:999px;
    color:white;
    font-size:13px;
    font-weight:700;
}

.phone-badge {
    display:inline-block;
    background:#2563eb;
    padding:6px 12px;
    border-radius:999px;
    color:white;
    font-size:13px;
    font-weight:700;
}

</style>
""", unsafe_allow_html=True)

# =====================================================
# HELPERS
# =====================================================

def safe_text(v):
    if v is None:
        return ""
    return str(v)

def to_number(series):
    return pd.to_numeric(series, errors="coerce").fillna(0)

# =====================================================
# LOAD FILTER OPTIONS
# =====================================================

@st.cache_data(ttl=120)
def get_filter_options():

    url = f"{SUPABASE_URL}/rest/v1/orders?select=year,province,channel,sales_staff&limit=50000"

    res = requests.get(url, headers=HEADERS)

    if res.status_code != 200:
        return {}

    df = pd.DataFrame(res.json())

    if df.empty:
        return {}

    return {
        "years": sorted(df["year"].dropna().astype(str).unique().tolist()) if "year" in df.columns else [],
        "provinces": sorted(df["province"].dropna().astype(str).unique().tolist()) if "province" in df.columns else [],
        "channels": sorted(df["channel"].dropna().astype(str).unique().tolist()) if "channel" in df.columns else [],
        "sales_staff": sorted(df["sales_staff"].dropna().astype(str).unique().tolist()) if "sales_staff" in df.columns else [],
    }

# =====================================================
# LOAD ORDERS
# =====================================================

@st.cache_data(ttl=60)
def load_orders(keyword, year, province, channel, sales_staff, limit, offset):

    params = ["select=*"]

    if year != "ทั้งหมด":
        params.append(f"year=eq.{quote(year)}")

    if province != "ทั้งหมด":
        params.append(f"province=eq.{quote(province)}")

    if channel != "ทั้งหมด":
        params.append(f"channel=eq.{quote(channel)}")

    if sales_staff != "ทั้งหมด":
        params.append(f"sales_staff=eq.{quote(sales_staff)}")

    if keyword:

        kw = quote(keyword.strip())

        params.append(
            f"or=(customer.ilike.*{kw}*,phone1.ilike.*{kw}*,phone2.ilike.*{kw}*,order_id.ilike.*{kw}*)"
        )

    params.append("order=date_text.desc")
    params.append(f"limit={limit}")
    params.append(f"offset={offset}")

    url = f"{SUPABASE_URL}/rest/v1/orders?" + "&".join(params)

    res = requests.get(url, headers=HEADERS)

    if res.status_code != 200:
        st.error(res.text)
        return pd.DataFrame()

    return pd.DataFrame(res.json())

# =====================================================
# PAGE TITLE
# =====================================================

st.title("📊 Sales Dashboard Pro")

# =====================================================
# SIDEBAR
# =====================================================

options = get_filter_options()

st.sidebar.header("🔎 ตัวกรอง")

keyword = st.sidebar.text_input(
    "ค้นหา ชื่อ / เบอร์ / เลขออเดอร์"
)

year = st.sidebar.selectbox(
    "ปี",
    ["ทั้งหมด"] + options.get("years", [])
)

province = st.sidebar.selectbox(
    "จังหวัด",
    ["ทั้งหมด"] + options.get("provinces", [])
)

channel = st.sidebar.selectbox(
    "ช่องทาง",
    ["ทั้งหมด"] + options.get("channels", [])
)

sales_staff = st.sidebar.selectbox(
    "พนักงานขาย",
    ["ทั้งหมด"] + options.get("sales_staff", [])
)

limit = st.sidebar.selectbox(
    "จำนวนแสดงต่อหน้า",
    [50, 100, 200],
    index=0
)

page = st.sidebar.number_input(
    "หน้า",
    min_value=1,
    value=1
)

offset = (page - 1) * limit

if st.sidebar.button("🔄 ล้าง Cache / Refresh"):
    st.cache_data.clear()
    st.rerun()

# =====================================================
# LOAD DATA
# =====================================================

df = load_orders(
    keyword,
    year,
    province,
    channel,
    sales_staff,
    limit,
    offset
)

if df.empty:
    st.warning("❌ ไม่พบข้อมูล")
    st.stop()

df["total_sales"] = to_number(df["total_sales"])

# =====================================================
# KPI
# =====================================================

k1, k2, k3, k4 = st.columns(4)

k1.metric(
    "💰 ยอดขาย",
    f"{df['total_sales'].sum():,.0f}"
)

k2.metric(
    "📦 ออเดอร์",
    f"{df['order_id'].nunique():,}"
)

k3.metric(
    "👤 ลูกค้า",
    f"{df['phone1'].nunique():,}"
)

k4.metric(
    "📄 หน้า",
    f"{page:,}"
)

st.divider()

# =====================================================
# CUSTOMER MODE
# =====================================================

if keyword:

    st.subheader("👥 ลูกค้า")

    customer_df = (
        df.groupby(["customer", "phone1"], dropna=False)
        .agg(
            latest_date=("date_text", "max"),
            latest_sales=("total_sales", "max"),
            total_sales=("total_sales", "sum"),
            total_orders=("order_id", "count")
        )
        .reset_index()
    )

    for _, row in customer_df.iterrows():

        customer_name = safe_text(row["customer"])
        phone = safe_text(row["phone1"])

        latest_date = safe_text(row["latest_date"])

        latest_sales = row["latest_sales"]
        total_sales = row["total_sales"]
        total_orders = row["total_orders"]

        st.markdown(f"""
        <div class="customer-card">

        <h2>👤 {customer_name}</h2>

        <span class="phone-badge">📞 {phone}</span>

        &nbsp;

        <span class="green">
        🛒 ซื้อ {total_orders} ครั้ง
        </span>

        <br><br>

        <b>📅 ล่าสุด:</b> {latest_date}

        <br>

        <b>💰 ยอดล่าสุด:</b>
        <span class="green">
        {latest_sales:,.0f}
        </span>

        <br>

        <b>💎 ยอดรวม:</b>
        <span class="green">
        {total_sales:,.0f}
        </span>

        </div>
        """, unsafe_allow_html=True)

        history = df[
            (df["phone1"] == phone)
        ].sort_values(
            by="date_text",
            ascending=False
        )

        st.markdown("### 📜 ประวัติการสั่งซื้อ")

        for _, h in history.iterrows():

            order_id = safe_text(h.get("order_id"))
            order_date = safe_text(h.get("date_text"))
            amount = h.get("total_sales", 0)

            products = ""

            if "products" in h and h["products"] is not None:

                if isinstance(h["products"], list):

                    p_list = []

                    for p in h["products"]:

                        if isinstance(p, dict):

                            pname = safe_text(p.get("name"))
                            qty = safe_text(p.get("qty"))

                            if pname:
                                p_list.append(f"• {pname} x {qty}")

                    products = "<br>".join(p_list)

            st.markdown(f"""
            <div class="order-card">

            <div style="font-size:20px;font-weight:700;">
            🚀 {order_id}
            </div>

            <br>

            📅 {order_date}

            &nbsp;&nbsp;&nbsp;

            <span class="green">
            💰 {amount:,.0f}
            </span>

            <br><br>

            📦 สินค้า

            <br>

            {products}

            </div>
            """, unsafe_allow_html=True)

        st.divider()

# =====================================================
# CHARTS
# =====================================================

c1, c2 = st.columns(2)

with c1:

    st.subheader("📈 ยอดขายตามช่องทาง")

    chart_df = (
        df.groupby("channel")["total_sales"]
        .sum()
        .sort_values(ascending=False)
    )

    st.bar_chart(chart_df)

with c2:

    st.subheader("🏆 จังหวัดยอดขายสูงสุด")

    chart_df = (
        df.groupby("province")["total_sales"]
        .sum()
        .sort_values(ascending=False)
        .head(10)
    )

    st.bar_chart(chart_df)

st.divider()

# =====================================================
# TABLE
# =====================================================

st.subheader("📋 รายการข้อมูล")

show_cols = [
    "order_id",
    "date_text",
    "customer",
    "phone1",
    "province",
    "district",
    "channel",
    "sales_staff",
    "total_sales"
]

show_cols = [c for c in show_cols if c in df.columns]

st.dataframe(
    df[show_cols],
    use_container_width=True,
    height=500
)

st.caption("CRM Dashboard Pro 🚀")