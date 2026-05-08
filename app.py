import streamlit as st
import pandas as pd
import requests
from urllib.parse import quote

st.set_page_config(page_title="Sales Dashboard Pro", layout="wide")

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_ANON_KEY"]

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
}

st.title("📊 Sales Dashboard Pro")

# -----------------------------
# Helpers
# -----------------------------
def safe_text(value):
    return "" if value is None else str(value).strip()

def to_number(series):
    return pd.to_numeric(series, errors="coerce").fillna(0)

@st.cache_data(ttl=120)
def get_filter_options():
    url = f"{SUPABASE_URL}/rest/v1/orders?select=year,province,channel,sales_staff&limit=50000"
    res = requests.get(url, headers=HEADERS)

    if res.status_code != 200:
        return {
            "years": [],
            "provinces": [],
            "channels": [],
            "sales_staff": [],
        }

    df = pd.DataFrame(res.json())

    if df.empty:
        return {
            "years": [],
            "provinces": [],
            "channels": [],
            "sales_staff": [],
        }

    return {
        "years": sorted(df.get("year", pd.Series()).dropna().astype(str).unique().tolist()),
        "provinces": sorted(df.get("province", pd.Series()).dropna().astype(str).unique().tolist()),
        "channels": sorted(df.get("channel", pd.Series()).dropna().astype(str).unique().tolist()),
        "sales_staff": sorted(df.get("sales_staff", pd.Series()).dropna().astype(str).unique().tolist()),
    }

@st.cache_data(ttl=60)
def load_orders(keyword, year, province, channel, sales_staff, min_sales, limit, offset):
    params = ["select=*"]

    if year != "ทั้งหมด":
        params.append(f"year=eq.{quote(year)}")

    if province != "ทั้งหมด":
        params.append(f"province=eq.{quote(province)}")

    if channel != "ทั้งหมด":
        params.append(f"channel=eq.{quote(channel)}")

    if sales_staff != "ทั้งหมด":
        params.append(f"sales_staff=eq.{quote(sales_staff)}")

    if min_sales > 0:
        params.append(f"total_sales=gte.{min_sales}")

    if keyword:
        kw = quote(keyword.strip())
        params.append(
            f"or=(customer.ilike.*{kw}*,phone1.ilike.*{kw}*,phone2.ilike.*{kw}*,order_id.ilike.*{kw}*)"
        )

    params.append("order=synced_at.desc")
    params.append(f"limit={limit}")
    params.append(f"offset={offset}")

    url = f"{SUPABASE_URL}/rest/v1/orders?" + "&".join(params)
    res = requests.get(url, headers=HEADERS)

    if res.status_code != 200:
        st.error(res.text)
        return pd.DataFrame()

    return pd.DataFrame(res.json())

# -----------------------------
# Sidebar
# -----------------------------
options = get_filter_options()

st.sidebar.header("🔎 ตัวกรอง")

keyword = st.sidebar.text_input("ค้นหา ชื่อ / เบอร์ / เลขออเดอร์")

year = st.sidebar.selectbox(
    "ปี",
    ["ทั้งหมด"] + options["years"],
)

province = st.sidebar.selectbox(
    "จังหวัด",
    ["ทั้งหมด"] + options["provinces"],
)

channel = st.sidebar.selectbox(
    "ช่องทาง",
    ["ทั้งหมด"] + options["channels"],
)

sales_staff = st.sidebar.selectbox(
    "พนักงานขาย",
    ["ทั้งหมด"] + options["sales_staff"],
)

min_sales = st.sidebar.number_input("ยอดขายขั้นต่ำ", min_value=0, value=0, step=100)

limit = st.sidebar.selectbox("จำนวนแสดงต่อหน้า", [50, 100, 200, 500], index=0)
page = st.sidebar.number_input("หน้า", min_value=1, value=1, step=1)

offset = (page - 1) * limit

if st.sidebar.button("🔄 ล้าง Cache / Refresh"):
    st.cache_data.clear()
    st.rerun()

# -----------------------------
# Load Data
# -----------------------------
df = load_orders(keyword, year, province, channel, sales_staff, min_sales, limit, offset)

if df.empty:
    st.warning("ไม่พบข้อมูลตามเงื่อนไข")
    st.stop()

df["total_sales"] = to_number(df["total_sales"])

# -----------------------------
# KPI
# -----------------------------
k1, k2, k3, k4 = st.columns(4)

k1.metric("💰 ยอดขายหน้านี้", f"{df['total_sales'].sum():,.0f}")
k2.metric("📦 ออเดอร์หน้านี้", f"{df['order_id'].nunique():,}")
k3.metric("👤 ลูกค้าหน้านี้", f"{df['phone1'].nunique():,}")
k4.metric("📄 หน้า", f"{page:,}")

st.divider()

# -----------------------------
# Charts
# -----------------------------
c1, c2 = st.columns(2)

with c1:
    st.subheader("ยอดขายตามช่องทาง")
    if "channel" in df.columns and not df.empty:
        chart_df = df.groupby("channel")["total_sales"].sum().sort_values(ascending=False)
        st.bar_chart(chart_df)

with c2:
    st.subheader("ยอดขายตามจังหวัด Top 10")
    if "province" in df.columns and not df.empty:
        chart_df = df.groupby("province")["total_sales"].sum().sort_values(ascending=False).head(10)
        st.bar_chart(chart_df)

c3, c4 = st.columns(2)

with c3:
    st.subheader("ยอดขายตามพนักงานขาย Top 10")
    if "sales_staff" in df.columns and not df.empty:
        chart_df = df.groupby("sales_staff")["total_sales"].sum().sort_values(ascending=False).head(10)
        st.bar_chart(chart_df)

with c4:
    st.subheader("จำนวนออเดอร์ตามช่องทาง")
    if "channel" in df.columns and not df.empty:
        chart_df = df.groupby("channel")["order_id"].nunique().sort_values(ascending=False)
        st.bar_chart(chart_df)

st.divider()

# -----------------------------
# Data Table
# -----------------------------
st.subheader("📋 รายการข้อมูล")

show_cols = [
    "order_id",
    "year",
    "month",
    "day",
    "date_text",
    "channel",
    "total_sales",
    "customer",
    "phone1",
    "phone2",
    "province",
    "district",
    "sales_staff",
    "upsell_staff",
    "synced_at",
]

show_cols = [col for col in show_cols if col in df.columns]

st.dataframe(
    df[show_cols],
    use_container_width=True,
    height=520,
)

st.caption("หมายเหตุ: KPI และ Chart คำนวณจากข้อมูลในหน้าปัจจุบันตาม Pagination ครับ")