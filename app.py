import streamlit as st
import pandas as pd
import requests
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

st.markdown("""
<style>
.stApp {
    background: linear-gradient(135deg, #FFF7ED 0%, #F8FAFC 45%, #FFFFFF 100%);
    color: #111827;
}
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #FFFFFF 0%, #FFF7ED 100%);
    border-right: 1px solid #FED7AA;
}
section[data-testid="stSidebar"] * { color: #111827 !important; }
.hero-card {
    background: linear-gradient(135deg, #FF7A00 0%, #FB923C 55%, #FDBA74 100%);
    border-radius: 28px;
    padding: 34px;
    margin-bottom: 24px;
    color: white;
    box-shadow: 0 20px 45px rgba(255,122,0,0.25);
}
.hero-title {
    font-size: 42px;
    font-weight: 900;
}
.hero-subtitle {
    font-size: 16px;
    opacity: .95;
}
[data-testid="stMetric"] {
    background: white;
    border: 1px solid #FED7AA;
    border-radius: 22px;
    padding: 20px;
    box-shadow: 0 10px 28px rgba(255,122,0,0.08);
}
.glass-card {
    background: white;
    border: 1px solid #FED7AA;
    border-radius: 24px;
    padding: 22px;
    box-shadow: 0 12px 28px rgba(17,24,39,0.05);
    margin-bottom: 18px;
}
h1, h2, h3 {
    color: #EA580C !important;
    font-weight: 900 !important;
}
.stButton > button {
    background: linear-gradient(90deg, #FF7A00 0%, #FB923C 100%);
    color: white !important;
    border: none;
    border-radius: 14px;
    font-weight: 800;
}
div[data-baseweb="select"] > div,
input {
    background: white !important;
    border: 1px solid #FDBA74 !important;
    border-radius: 14px !important;
}
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}
</style>
""", unsafe_allow_html=True)


def api_get(path, params):
    url = f"{SUPABASE_URL}/rest/v1/{path}?{'&'.join(params)}"
    res = requests.get(url, headers=HEADERS)

    if res.status_code not in [200, 206]:
        st.error(res.text)
        return []

    return res.json()


def build_filter_params(year, month, province, channel, sales_staff, source_sheet):
    params = []

    if year != "ทั้งหมด":
        params.append(f"year=eq.{quote(str(year))}")

    if month != "ทั้งหมด":
        params.append(f"month=eq.{quote(str(month))}")

    if province != "ทั้งหมด":
        params.append(f"province=eq.{quote(str(province))}")

    if channel != "ทั้งหมด":
        params.append(f"channel=eq.{quote(str(channel))}")

    if sales_staff != "ทั้งหมด":
        params.append(f"sales_staff=eq.{quote(str(sales_staff))}")

    if source_sheet != "ทั้งหมด":
        params.append(f"source_sheet=eq.{quote(str(source_sheet))}")

    return params


def sort_months(values):
    normal = []
    others = []

    for v in values:
        try:
            normal.append(int(v))
        except:
            others.append(v)

    normal = [str(v) for v in sorted(normal)]
    return normal + sorted(others)


@st.cache_data(ttl=300)
def load_summary_all():
    rows = api_get(
        "v_dashboard_summary",
        [
            "select=year,month,province,channel,sales_staff,source_sheet,total_sales,total_orders,total_customers",
            "limit=50000"
        ]
    )
    df = pd.DataFrame(rows)

    if df.empty:
        return df

    df["total_sales"] = pd.to_numeric(df["total_sales"], errors="coerce").fillna(0)
    df["total_orders"] = pd.to_numeric(df["total_orders"], errors="coerce").fillna(0)
    df["total_customers"] = pd.to_numeric(df["total_customers"], errors="coerce").fillna(0)

    return df


@st.cache_data(ttl=180)
def load_summary_filtered(year, month, province, channel, sales_staff, source_sheet):
    filters = build_filter_params(year, month, province, channel, sales_staff, source_sheet)

    rows = api_get(
        "v_dashboard_summary",
        [
            "select=year,month,province,channel,sales_staff,source_sheet,total_sales,total_orders,total_customers"
        ] + filters + [
            "limit=50000"
        ]
    )

    df = pd.DataFrame(rows)

    if df.empty:
        return df

    df["total_sales"] = pd.to_numeric(df["total_sales"], errors="coerce").fillna(0)
    df["total_orders"] = pd.to_numeric(df["total_orders"], errors="coerce").fillna(0)
    df["total_customers"] = pd.to_numeric(df["total_customers"], errors="coerce").fillna(0)

    return df


all_df = load_summary_all()

if all_df.empty:
    st.warning("ไม่พบข้อมูลใน v_dashboard_summary")
    st.stop()

years = sorted(all_df["year"].dropna().astype(str).unique().tolist())
months = sort_months(all_df["month"].dropna().astype(str).unique().tolist())
provinces = sorted(all_df["province"].dropna().astype(str).unique().tolist())
channels = sorted(all_df["channel"].dropna().astype(str).unique().tolist())
sales_staffs = sorted(all_df["sales_staff"].dropna().astype(str).unique().tolist())
source_sheets = sorted(all_df["source_sheet"].dropna().astype(str).unique().tolist())

st.sidebar.markdown("## 🔎 ตัวกรอง")
year = st.sidebar.selectbox("ปี", ["ทั้งหมด"] + years)
month = st.sidebar.selectbox("เดือน", ["ทั้งหมด"] + months)
source_sheet = st.sidebar.selectbox("แหล่งข้อมูล", ["ทั้งหมด"] + source_sheets)
province = st.sidebar.selectbox("จังหวัด", ["ทั้งหมด"] + provinces)
channel = st.sidebar.selectbox("ช่องทาง", ["ทั้งหมด"] + channels)
sales_staff = st.sidebar.selectbox("พนักงานขาย", ["ทั้งหมด"] + sales_staffs)

if st.sidebar.button("🔄 ล้าง Cache / Refresh"):
    st.cache_data.clear()
    st.rerun()

st.markdown("""
<div class="hero-card">
    <div class="hero-title">📊 Sales Dashboard Pro Ultra</div>
    <div class="hero-subtitle">
        Dashboard สรุปจากตาราง v_dashboard_summary — โหลดเร็ว ไม่ดึงข้อมูลดิบทั้งหมด
    </div>
</div>
""", unsafe_allow_html=True)

with st.spinner("กำลังโหลดข้อมูลสรุป..."):
    df = load_summary_filtered(year, month, province, channel, sales_staff, source_sheet)

if df.empty:
    st.warning("ไม่พบข้อมูลตามตัวกรอง")
    st.stop()

k1, k2, k3 = st.columns(3)
k1.metric("💰 ยอดขายรวม", f"{df['total_sales'].sum():,.0f}")
k2.metric("📦 จำนวนออเดอร์", f"{df['total_orders'].sum():,.0f}")
k3.metric("👤 จำนวนลูกค้า", f"{df['total_customers'].sum():,.0f}")

st.divider()

c1, c2 = st.columns(2)

with c1:
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.markdown("### 📅 ยอดขายแต่ละเดือน / ปี")
    monthly = (
        df.groupby(["year", "month"], as_index=False)["total_sales"]
        .sum()
    )

    monthly["month_sort"] = pd.to_numeric(monthly["month"], errors="coerce").fillna(99)
    monthly = monthly.sort_values(["year", "month_sort"])
    monthly["period"] = monthly["year"].astype(str) + "/" + monthly["month"].astype(str)

    st.bar_chart(monthly.set_index("period")["total_sales"])
    st.markdown('</div>', unsafe_allow_html=True)

with c2:
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.markdown("### 🏆 ยอดขายตามจังหวัด Top 10")
    province_sales = (
        df.groupby("province")["total_sales"]
        .sum()
        .sort_values(ascending=False)
        .head(10)
    )
    st.bar_chart(province_sales)
    st.markdown('</div>', unsafe_allow_html=True)

c3, c4 = st.columns(2)

with c3:
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.markdown("### 👨‍💼 ยอดขายตามพนักงานขาย Top 10")
    staff_sales = (
        df.groupby("sales_staff")["total_sales"]
        .sum()
        .sort_values(ascending=False)
        .head(10)
    )
    st.bar_chart(staff_sales)
    st.markdown('</div>', unsafe_allow_html=True)

with c4:
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.markdown("### 🛒 ยอดขายตามช่องทาง")
    channel_sales = (
        df.groupby("channel")["total_sales"]
        .sum()
        .sort_values(ascending=False)
    )
    st.bar_chart(channel_sales)
    st.markdown('</div>', unsafe_allow_html=True)

st.divider()
st.caption(f"โหลดจากตารางสรุป: {len(df):,} แถว | ไม่โหลดรายการข้อมูลดิบจาก orders")