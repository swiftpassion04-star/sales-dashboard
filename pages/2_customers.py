"""
pages/2_customers.py
หน้าข้อมูลลูกค้า — ค้นหาก่อน แล้วค่อยแสดง (ไม่โหลดทั้งหมดตอนเปิดหน้า)
"""

import streamlit as st
import pandas as pd
import requests
from urllib.parse import quote

st.set_page_config(page_title="ข้อมูลลูกค้า", layout="wide")

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_ANON_KEY"]

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Prefer": "count=exact"
}

FETCH_LIMIT = 1000
PAGE_SIZE   = 50

# ── STYLE ────────────────────────────────────────────────────
st.markdown("""
<style>
.stApp { background-color:#F8FAFC; color:#111827; }
section[data-testid="stSidebar"] {
    background:linear-gradient(180deg,#FFFFFF 0%,#FFF7ED 100%);
    border-right:1px solid #FED7AA;
}
section[data-testid="stSidebar"] * { color:#111827 !important; }
[data-testid="stMetric"] {
    background:white; border:1px solid #FED7AA;
    border-radius:18px; padding:18px;
    box-shadow:0 4px 12px rgba(255,122,0,.08);
}
.customer-card {
    background:white; border:1px solid #FED7AA;
    border-radius:18px; padding:18px; margin-bottom:12px;
    box-shadow:0 4px 12px rgba(255,122,0,.06);
}
.order-card {
    background:#FFF7ED; border:1px solid #FDBA74;
    border-radius:14px; padding:14px; margin-bottom:10px;
}
.badge {
    display:inline-block; padding:4px 12px; border-radius:999px;
    background:#FF7A00; color:white; font-size:12px; font-weight:700;
}
.badge-green {
    display:inline-block; padding:4px 12px; border-radius:999px;
    background:#16A34A; color:white; font-size:12px; font-weight:700;
}
.badge-blue {
    display:inline-block; padding:4px 12px; border-radius:999px;
    background:#2563EB; color:white; font-size:12px; font-weight:700;
}
.green  { color:#16A34A; font-weight:700; }
.search-hint {
    text-align:center; padding:60px 20px; color:#9CA3AF;
}
.search-hint .icon { font-size:56px; margin-bottom:16px; }
.search-hint h2 { color:#EA580C !important; font-size:22px; }
.search-hint p  { font-size:15px; margin-top:8px; }
h1,h2,h3 { color:#EA580C !important; }
hr { border-color:#FED7AA; }
.stButton > button {
    background:linear-gradient(90deg,#FF7A00 0%,#FB923C 100%);
    color:white; border:none; border-radius:12px;
    padding:10px 18px; font-weight:700; transition:.2s;
}
.stButton > button:hover {
    transform:translateY(-2px);
    box-shadow:0 6px 14px rgba(255,122,0,.25);
}
div[data-baseweb="select"] > div {
    background:white !important; border:1px solid #FDBA74 !important;
    border-radius:12px !important;
}
input {
    background:white !important; border:1px solid #FDBA74 !important;
    border-radius:12px !important;
}
</style>
""", unsafe_allow_html=True)


# ── API ───────────────────────────────────────────────────────
def api_get(path, params):
    url = f"{SUPABASE_URL}/rest/v1/{path}?{'&'.join(params)}"
    res = requests.get(url, headers=HEADERS)
    if res.status_code not in [200, 206]:
        st.error(f"API Error: {res.text}")
        return [], 0
    total = 0
    cr = res.headers.get("Content-Range", "")
    if "/" in cr:
        try: total = int(cr.split("/")[-1])
        except: pass
    return res.json(), total


# ── LOAD (เฉพาะเมื่อค้นหา) ───────────────────────────────────
@st.cache_data(ttl=120, show_spinner="🔍 กำลังค้นหา...")
def search_orders(keyword: str, year: str) -> pd.DataFrame:
    """ดึงเฉพาะออเดอร์ที่ match keyword — ไม่โหลดทั้งหมด"""
    all_rows = []
    offset   = 0

    base = ["select=order_id,year,date_text,customer,phone1,phone2,province,channel,sales_staff,total_sales,products,synced_at"]

    if year != "ทั้งหมด":
        base.append(f"year=eq.{quote(year)}")

    kw = keyword.strip()
    if kw:
        q = quote(kw)
        base.append(
            f"or=(customer.ilike.*{q}*,phone1.ilike.*{q}*,phone2.ilike.*{q}*,order_id.ilike.*{q}*)"
        )

    # จำกัดสูงสุด 5000 แถว ถ้าค้นหาแบบ keyword (เร็วพอ)
    # ถ้าไม่มี keyword จะไม่โหลดเลย (handled ด้านนอก)
    max_fetch = 5000
    while offset < max_fetch:
        params = base + [
            f"limit={min(FETCH_LIMIT, max_fetch - offset)}",
            f"offset={offset}",
            "order=synced_at.desc"
        ]
        rows, _ = api_get("orders", params)
        if not rows: break
        all_rows.extend(rows)
        if len(rows) < FETCH_LIMIT: break
        offset += FETCH_LIMIT

    return pd.DataFrame(all_rows)


# ── DEDUP ─────────────────────────────────────────────────────
def build_customer_list(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()

    df = df.copy()
    df["total_sales"] = pd.to_numeric(df["total_sales"], errors="coerce").fillna(0)
    df["phone1"] = df["phone1"].fillna("").astype(str).str.strip()
    df["phone2"] = df["phone2"].fillna("").astype(str).str.strip()

    # Union-Find
    parent = {}

    def find(x):
        if x not in parent: parent[x] = x
        if parent[x] != x: parent[x] = find(parent[x])
        return parent[x]

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb: parent[ra] = rb

    for _, row in df.iterrows():
        p1, p2 = row["phone1"], row["phone2"]
        if p1: find(p1)
        if p2: find(p2)
        if p1 and p2: union(p1, p2)

    def canonical(row):
        p1, p2 = row["phone1"], row["phone2"]
        if p1: return find(p1)
        if p2: return find(p2)
        return f"__nophone_{row.name}"

    df["canonical_phone"] = df.apply(canonical, axis=1)

    records = []
    for canon, grp in df.groupby("canonical_phone"):
        grp_sorted = grp.sort_values("date_text", ascending=False)
        latest     = grp_sorted.iloc[0]

        phones = set()
        for _, r in grp.iterrows():
            if r["phone1"]: phones.add(r["phone1"])
            if r["phone2"]: phones.add(r["phone2"])
        phones.discard("")

        records.append({
            "canonical_phone" : canon,
            "customer"        : latest["customer"] or "",
            "phones"          : " / ".join(sorted(phones)),
            "province"        : latest.get("province", ""),
            "channel"         : latest.get("channel", ""),
            "total_sales"     : grp["total_sales"].sum(),
            "order_count"     : grp["order_id"].nunique(),
            "latest_date"     : latest["date_text"],
            "_orders"         : grp.to_dict("records")
        })

    return pd.DataFrame(records).sort_values("latest_date", ascending=False)


def product_text(products):
    if not isinstance(products, list): return ""
    return "\n".join(
        f"• {p.get('name','')} × {p.get('qty','')}"
        for p in products if isinstance(p, dict) and p.get("name")
    )


# ── SESSION STATE ─────────────────────────────────────────────
for k, v in {"cust_page": 1, "detail_idx": None, "searched": False,
             "last_keyword": "", "last_year": "ทั้งหมด"}.items():
    if k not in st.session_state:
        st.session_state[k] = v


# ── SIDEBAR ───────────────────────────────────────────────────
st.sidebar.header("🔎 ค้นหาลูกค้า")

keyword  = st.sidebar.text_input(
    "ชื่อ / เบอร์โทร / เลขออเดอร์",
    placeholder="พิมพ์แล้วกดปุ่มค้นหา..."
)
year_sel = st.sidebar.selectbox("ปี", ["ทั้งหมด", "2565", "2566"])

do_search = st.sidebar.button("🔍 ค้นหา", use_container_width=True)

if st.sidebar.button("🔄 ล้าง / Refresh", use_container_width=True):
    st.cache_data.clear()
    st.session_state.searched   = False
    st.session_state.cust_page  = 1
    st.session_state.detail_idx = None
    st.rerun()

# ── TRIGGER SEARCH ────────────────────────────────────────────
if do_search:
    if not keyword.strip():
        st.sidebar.warning("กรุณาพิมพ์คำค้นหาก่อนครับ")
    else:
        st.session_state.searched    = True
        st.session_state.cust_page   = 1
        st.session_state.detail_idx  = None
        st.session_state.last_keyword = keyword
        st.session_state.last_year    = year_sel


# ── MAIN TITLE ────────────────────────────────────────────────
st.title("👥 ข้อมูลลูกค้า")

# ── ยังไม่ได้ค้นหา → แสดงหน้า Welcome ──────────────────────
if not st.session_state.searched:
    st.markdown("""
    <div class="search-hint">
        <div class="icon">🔍</div>
        <h2>ค้นหาลูกค้าก่อนเลยครับ</h2>
        <p>พิมพ์ <b>ชื่อ</b> หรือ <b>เบอร์โทร</b> หรือ <b>เลขออเดอร์</b><br>
        ในช่องด้านซ้าย แล้วกด <b>🔍 ค้นหา</b></p>
    </div>
    """, unsafe_allow_html=True)
    st.stop()


# ── โหลดข้อมูล (เฉพาะเมื่อค้นหาแล้ว) ───────────────────────
raw_df = search_orders(st.session_state.last_keyword, st.session_state.last_year)

if raw_df.empty:
    st.warning(f"❌ ไม่พบลูกค้าที่ค้นหา: **{st.session_state.last_keyword}**")
    st.stop()

customer_df = build_customer_list(raw_df)


# ── DETAIL PAGE ───────────────────────────────────────────────
if st.session_state.detail_idx is not None:
    idx = st.session_state.detail_idx

    if idx >= len(customer_df):
        st.session_state.detail_idx = None
        st.rerun()

    c = customer_df.iloc[idx]

    if st.button("← กลับรายชื่อลูกค้า"):
        st.session_state.detail_idx = None
        st.rerun()

    st.title(f"👤 {c['customer'] or '(ไม่ระบุชื่อ)'}")
    st.markdown(f"""
    <span class="badge">📞 {c['phones']}</span>
    &nbsp;
    <span class="badge-green">📦 {int(c['order_count'])} ออเดอร์</span>
    &nbsp;
    <span class="badge-blue">📍 {c['province'] or '-'}</span>
    <br><br>
    <b>💰 ยอดซื้อรวม: <span class="green">{c['total_sales']:,.0f} บาท</span></b>
    """, unsafe_allow_html=True)

    st.divider()
    st.subheader("📜 ประวัติการสั่งซื้อ")

    orders = sorted(c["_orders"], key=lambda x: x.get("date_text",""), reverse=True)
    for o in orders:
        ptxt = product_text(o.get("products", []))
        st.markdown(f"""
        <div class="order-card">
            <b>🚀 ออเดอร์:</b> {o.get('order_id','')}
            &nbsp;&nbsp; <b>📅</b> {o.get('date_text','')}
            &nbsp;&nbsp; <b>💰</b> <span class="green">{float(o.get('total_sales',0)):,.0f} บาท</span>
            &nbsp;&nbsp; <b>📡</b> {o.get('channel','')}
            <br><br>
            <b>📦 สินค้า:</b><br>
            <pre style="margin:6px 0 0 0;font-size:13px">{ptxt or '-'}</pre>
        </div>
        """, unsafe_allow_html=True)

    st.stop()


# ── LIST PAGE ─────────────────────────────────────────────────
total_customers = len(customer_df)
total_pages     = max(1, (total_customers + PAGE_SIZE - 1) // PAGE_SIZE)

# KPI
k1, k2, k3 = st.columns(3)
k1.metric("👥 พบลูกค้า (ไม่นับซ้ำ)", f"{total_customers:,}")
k2.metric("💰 ยอดขายรวม",             f"{customer_df['total_sales'].sum():,.0f}")
k3.metric("📦 ออเดอร์รวม",            f"{customer_df['order_count'].sum():,.0f}")

st.caption(f"🔍 ผลการค้นหา: **{st.session_state.last_keyword}**")
st.divider()

# Pagination top
col_info, col_prev, col_next = st.columns([4, 1, 1])
col_info.markdown(
    f"**หน้า {st.session_state.cust_page} / {total_pages}** &nbsp;|&nbsp; {total_customers:,} ราย",
    unsafe_allow_html=True
)
if col_prev.button("⬅️ ก่อนหน้า") and st.session_state.cust_page > 1:
    st.session_state.cust_page -= 1
    st.rerun()
if col_next.button("ถัดไป ➡️") and st.session_state.cust_page < total_pages:
    st.session_state.cust_page += 1
    st.rerun()

# Slice
start = (st.session_state.cust_page - 1) * PAGE_SIZE
end   = start + PAGE_SIZE
page_customers = customer_df.iloc[start:end].reset_index(drop=True)

# Cards
for i, c in page_customers.iterrows():
    abs_idx = start + i
    st.markdown(f"""
    <div class="customer-card">
        <h3>👤 {c['customer'] or '(ไม่ระบุชื่อ)'}</h3>
        <span class="badge">📞 {c['phones']}</span>
        &nbsp;
        <span class="badge-green">📦 {int(c['order_count'])} ออเดอร์</span>
        &nbsp;
        <span class="badge-blue">📍 {c['province'] or '-'}</span>
        <br><br>
        📅 ล่าสุด: <b>{c['latest_date']}</b>
        &nbsp;&nbsp;
        💰 ยอดรวม: <span class="green">{c['total_sales']:,.0f} บาท</span>
        &nbsp;&nbsp;
        📡 {c['channel'] or '-'}
    </div>
    """, unsafe_allow_html=True)

    if st.button("📋 ดูประวัติการซื้อ", key=f"detail_{abs_idx}"):
        st.session_state.detail_idx = abs_idx
        st.rerun()

    st.markdown("---")

# Pagination bottom
bc1, bc2, bc3 = st.columns([4, 1, 1])
bc1.caption(f"แสดง {start+1:,}–{min(end, total_customers):,} จาก {total_customers:,} รายการ")
if bc2.button("⬅️ ก่อนหน้า ", key="bot_prev") and st.session_state.cust_page > 1:
    st.session_state.cust_page -= 1
    st.rerun()
if bc3.button("ถัดไป ➡️ ", key="bot_next") and st.session_state.cust_page < total_pages:
    st.session_state.cust_page += 1
    st.rerun()
