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
    "Prefer": "count=exact"
}

PAGE_LIMIT_OPTIONS = [50, 100, 200]
SUMMARY_PAGE_SIZE = 1000
SUMMARY_MAX_ROWS = 500000

st.title("📊 Sales Dashboard Pro")

st.markdown("""
<style>
[data-testid="stMetric"] {
    background: #111827;
    padding: 16px;
    border-radius: 16px;
    border: 1px solid #1f2937;
}
.customer-card {
    background:#111827;
    border:1px solid #1f2937;
    border-radius:18px;
    padding:18px;
    margin-bottom:14px;
}
.order-card {
    background:#0f172a;
    border:1px solid #1e293b;
    border-radius:14px;
    padding:14px;
    margin-bottom:10px;
}
.green { color:#00e676; font-weight:700; }
.badge {
    display:inline-block;
    padding:5px 10px;
    border-radius:999px;
    background:#2563eb;
    color:white;
    font-size:13px;
    font-weight:700;
}
</style>
""", unsafe_allow_html=True)


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


@st.cache_data(ttl=120)
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


@st.cache_data(ttl=60)
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


@st.cache_data(ttl=60)
def load_page(keyword, year, province, channel, sales_staff, source_sheet, limit, offset):
    base_filters = build_filter_params(keyword, year, province, channel, sales_staff, source_sheet)

    params = ["select=*"] + base_filters + [
        "order=synced_at.desc",
        f"limit={limit}",
        f"offset={offset}"
    ]

    rows, total = api_get("orders", params)
    return pd.DataFrame(rows), total


def to_number(s):
    return pd.to_numeric(s, errors="coerce").fillna(0)


def product_text(products):
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


options = get_filter_options()

st.sidebar.header("🔎 ตัวกรอง")

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

page = st.session_state.page
offset = (page - 1) * limit

summary_df = load_summary(keyword, year, province, channel, sales_staff, source_sheet)
page_df, total_count = load_page(keyword, year, province, channel, sales_staff, source_sheet, limit, offset)

if summary_df.empty:
    st.warning("❌ ไม่พบข้อมูลตามตัวกรอง")
    st.stop()

summary_df["total_sales"] = to_number(summary_df["total_sales"])

if not page_df.empty:
    page_df["total_sales"] = to_number(page_df["total_sales"])

total_pages = max(1, (total_count + limit - 1) // limit)

k1, k2, k3, k4 = st.columns(4)
k1.metric("💰 ยอดขายรวม", f"{summary_df['total_sales'].sum():,.0f}")
k2.metric("📦 ออเดอร์ทั้งหมด", f"{summary_df['order_id'].nunique():,}")
k3.metric("👤 ลูกค้าทั้งหมด", f"{summary_df['phone1'].nunique():,}")
k4.metric("📄 หน้า", f"{page:,} / {total_pages:,}")

st.divider()

if keyword and not page_df.empty:
    st.subheader("👥 ผลการค้นหาลูกค้า")

    customer_df = (
        summary_df.groupby(["customer", "phone1"], dropna=False)
        .agg(
            total_sales=("total_sales", "sum"),
            total_orders=("order_id", "count"),
            latest_date=("date_text", "max")
        )
        .reset_index()
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

        with st.expander("📜 ดูประวัติการซื้อ"):
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

st.subheader("📈 Dashboard รวมตามตัวกรอง")

c1, c2 = st.columns(2)

with c1:
    st.markdown("### 📈 ยอดขายตามช่องทาง")
    if "channel" in summary_df.columns:
        st.bar_chart(summary_df.groupby("channel")["total_sales"].sum().sort_values(ascending=False))

with c2:
    st.markdown("### 🏆 จังหวัดยอดขายสูงสุด")
    if "province" in summary_df.columns:
        st.bar_chart(summary_df.groupby("province")["total_sales"].sum().sort_values(ascending=False).head(10))

c3, c4 = st.columns(2)

with c3:
    st.markdown("### 👨‍💼 ยอดขายตามพนักงานขาย")
    if "sales_staff" in summary_df.columns:
        st.bar_chart(summary_df.groupby("sales_staff")["total_sales"].sum().sort_values(ascending=False).head(10))

with c4:
    st.markdown("### 📦 จำนวนออเดอร์ตามแหล่งข้อมูล")
    if "source_sheet" in summary_df.columns:
        st.bar_chart(summary_df.groupby("source_sheet")["order_id"].nunique().sort_values(ascending=False))

st.divider()

st.subheader("📋 รายการข้อมูล")

if page_df.empty:
    st.warning("หน้านี้ไม่มีข้อมูล")
else:
    show_cols = [
        "order_id", "year", "source_sheet", "date_text", "customer",
        "phone1", "province", "district", "channel",
        "sales_staff", "upsell_staff", "total_sales"
    ]
    show_cols = [c for c in show_cols if c in page_df.columns]

    st.dataframe(
        page_df[show_cols],
        use_container_width=True,
        height=520
    )

st.caption(f"แสดงหน้า {page:,} จากทั้งหมด {total_pages:,} หน้า | รวม {total_count:,} รายการตามตัวกรองครับ")