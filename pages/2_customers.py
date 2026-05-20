import html
import json
from urllib.parse import quote

import pandas as pd
import requests
import streamlit as st


st.set_page_config(page_title="ข้อมูลลูกค้า", layout="wide")

SUPABASE_URL = st.secrets.get("CRM_SUPABASE_URL", st.secrets.get("SUPABASE_URL", ""))
SUPABASE_KEY = st.secrets.get("CRM_SUPABASE_ANON_KEY", st.secrets.get("SUPABASE_ANON_KEY", ""))
ORDERS_TABLE = "order_history"
FETCH_LIMIT = 1000
MAX_FETCH = 5000
PAGE_SIZE = 50

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Prefer": "count=exact",
}


st.markdown(
    """
<style>
.stApp { background:#F8FAFC; color:#111827; }
section[data-testid="stSidebar"] {
    background:linear-gradient(180deg,#FFFFFF 0%,#FFF7ED 100%);
    border-right:1px solid #FED7AA;
}
section[data-testid="stSidebar"] * { color:#111827 !important; }
section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a[href="/"],
section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a[href="/customers"],
section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a[href="/sync_status"] {
    font-size:0 !important;
}
section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a[href="/"]::after {
    content:"ค้นหาลูกค้า CRM";
    font-size:14px !important;
}
section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a[href="/customers"]::after {
    content:"ข้อมูลลูกค้า";
    font-size:14px !important;
}
section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a[href="/sync_status"]::after {
    content:"สถานะ Sync";
    font-size:14px !important;
}
[data-testid="stMetric"] {
    background:white; border:1px solid #FED7AA;
    border-radius:16px; padding:16px;
    box-shadow:0 4px 12px rgba(255,122,0,.08);
}
.customer-card, .order-card {
    background:white; border:1px solid #FED7AA;
    border-radius:14px; padding:16px; margin-bottom:12px;
    box-shadow:0 4px 12px rgba(255,122,0,.06);
}
.order-card { background:#FFF7ED; }
.badge {
    display:inline-block; padding:4px 12px; border-radius:999px;
    background:#FF7A00; color:white; font-size:12px; font-weight:700;
    margin-right:6px; margin-bottom:6px;
}
.badge-green { background:#16A34A; }
.badge-blue { background:#2563EB; }
.muted { color:#6B7280; }
.green { color:#16A34A; font-weight:700; }
.search-hint { text-align:center; padding:60px 20px; color:#6B7280; }
.search-hint .icon { font-size:54px; margin-bottom:16px; }
.search-hint h2, h1, h2, h3 { color:#EA580C !important; }
.data-table {
    width:100%; border-collapse:collapse; overflow:hidden;
    border:1px solid #E5E7EB; border-radius:12px;
}
.data-table th, .data-table td {
    border:1px solid #E5E7EB; padding:9px 10px; vertical-align:top;
}
.data-table th { background:#FFF7ED; color:#7C2D12; text-align:left; width:34%; }
.stButton > button {
    background:linear-gradient(90deg,#FF7A00 0%,#FB923C 100%);
    color:white; border:none; border-radius:12px;
    padding:10px 18px; font-weight:700;
}
div[data-baseweb="select"] > div, input {
    background:white !important; border:1px solid #FDBA74 !important;
    border-radius:12px !important;
}
</style>
""",
    unsafe_allow_html=True,
)


def require_config() -> None:
    if not SUPABASE_URL or not SUPABASE_KEY:
        st.error("ยังไม่ได้ตั้งค่า Streamlit secrets สำหรับ Supabase")
        st.stop()


def api_get(path: str, params: list[str]) -> list[dict]:
    url = f"{SUPABASE_URL}/rest/v1/{path}?{'&'.join(params)}"
    response = requests.get(url, headers=HEADERS, timeout=30)
    if response.status_code not in (200, 206):
        st.error(f"API Error: {response.text}")
        return []
    return response.json()


@st.cache_data(ttl=120, show_spinner="กำลังค้นหาประวัติลูกค้า...")
def search_orders(keyword: str, year: str) -> pd.DataFrame:
    require_config()
    keyword = keyword.strip()
    if not keyword:
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

    q = quote(keyword)
    base = [
        f"select={select_cols}",
        f"or=(customer.ilike.*{q}*,phone1.ilike.*{q}*,phone2.ilike.*{q}*,order_id.ilike.*{q}*)",
    ]
    if year != "ทั้งหมด":
        base.append(f"year_file=eq.{quote(year)}")

    rows: list[dict] = []
    offset = 0
    while offset < MAX_FETCH:
        params = base + [
            f"limit={min(FETCH_LIMIT, MAX_FETCH - offset)}",
            f"offset={offset}",
            "order=synced_at.desc",
        ]
        page = api_get(ORDERS_TABLE, params)
        if not page:
            break
        rows.extend(page)
        if len(page) < FETCH_LIMIT:
            break
        offset += FETCH_LIMIT

    return pd.DataFrame(rows)


def clean(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and pd.isna(value):
        return ""
    return str(value).strip()


def normalize_phone(value: object) -> str:
    phone = "".join(ch for ch in clean(value) if ch.isdigit())
    return phone if len(phone) >= 7 else ""


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


def build_customer_list(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()

    df = df.copy()
    df["total_sales"] = pd.to_numeric(df["total_sales"], errors="coerce").fillna(0)
    df["phone1"] = df["phone1"].fillna("").astype(str).str.strip()
    df["phone2"] = df["phone2"].fillna("").astype(str).str.strip()

    def canonical(row: pd.Series) -> str:
        return normalize_phone(row["phone1"]) or normalize_phone(row["phone2"]) or f"__nophone_{row.name}"

    df["canonical_phone"] = df.apply(canonical, axis=1)
    records = []

    for canon, group in df.groupby("canonical_phone"):
        group_sorted = group.sort_values(["year_file", "month", "day", "synced_at"], ascending=False)
        latest = group_sorted.iloc[0]
        phones = sorted(
            {
                phone
                for _, row in group.iterrows()
                for phone in [clean(row.get("phone1")), clean(row.get("phone2"))]
                if phone
            }
        )
        records.append(
            {
                "canonical_phone": canon,
                "customer": clean(latest.get("customer")),
                "phones": " / ".join(phones),
                "province": clean(latest.get("province")),
                "channel": clean(latest.get("channel")),
                "sales_staff": clean(latest.get("sales_staff")),
                "total_sales": group["total_sales"].sum(),
                "order_count": group["order_id"].nunique(),
                "latest_date": clean(latest.get("date_text")),
                "_orders": group.to_dict("records"),
            }
        )

    return pd.DataFrame(records).sort_values("latest_date", ascending=False)


def html_escape(value: object) -> str:
    return html.escape(clean(value), quote=True)


def info_table(rows: list[tuple[str, object]]) -> str:
    html_rows = "".join(
        f"<tr><th>{html_escape(label)}</th><td>{html_escape(value) or '-'}</td></tr>"
        for label, value in rows
    )
    return f'<table class="data-table"><tbody>{html_rows}</tbody></table>'


def product_table(products: list[dict]) -> str:
    if not products:
        return '<div class="muted">ไม่มีรายการสินค้า</div>'
    rows = ""
    for item in products:
        rows += (
            "<tr>"
            f"<td>{html_escape(item.get('sku')) or '-'}</td>"
            f"<td>{html_escape(item.get('name')) or '-'}</td>"
            f"<td>{html_escape(item.get('qty')) or '-'}</td>"
            f"<td>{html_escape(item.get('price')) or '0'}</td>"
            "</tr>"
        )
    return (
        '<table class="data-table"><thead><tr>'
        "<th>SKU</th><th>สินค้า</th><th>จำนวน</th><th>ราคา</th>"
        f"</tr></thead><tbody>{rows}</tbody></table>"
    )


def render_order_history(orders: list[dict]) -> None:
    st.subheader("ประวัติการสั่งซื้อทั้งหมดของลูกค้าคนนี้")
    sorted_orders = sorted(orders, key=lambda item: clean(item.get("source_key")), reverse=True)
    for order in sorted_orders:
        products = parse_products(order.get("products"))
        summary = product_summary(products) or "-"
        st.markdown(
            f"""
            <div class="order-card">
              <div><span class="badge">ออเดอร์ {html_escape(order.get('order_id'))}</span></div>
              <br>
              <div><b>วันที่:</b> {html_escape(order.get('date_text')) or '-'}</div>
              <div><b>ยอดขาย:</b> <span class="green">{float(order.get('total_sales') or 0):,.0f} บาท</span></div>
              <div><b>สินค้า:</b> {html_escape(summary)}</div>
              <div><b>ที่อยู่:</b> {html_escape(full_address(order)) or '-'}</div>
              <div><b>ผู้ขาย:</b> {html_escape(order.get('sales_staff')) or '-'}</div>
              <div><b>ขนส่ง:</b> {html_escape(order.get('shipping')) or '-'} / {html_escape(order.get('tracking_no')) or '-'}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


for key, value in {
    "cust_page": 1,
    "detail_idx": None,
    "searched": False,
    "last_keyword": "",
    "last_year": "ทั้งหมด",
}.items():
    if key not in st.session_state:
        st.session_state[key] = value


st.sidebar.header("ค้นหาลูกค้า")
keyword = st.sidebar.text_input("ชื่อ / เบอร์โทร / เลขออเดอร์", placeholder="พิมพ์แล้วกดค้นหา...")
year_sel = st.sidebar.selectbox("ปี", ["ทั้งหมด", "2565", "2566", "2567", "2568", "2569"])

if st.sidebar.button("ค้นหา", use_container_width=True):
    if not keyword.strip():
        st.sidebar.warning("กรุณาพิมพ์คำค้นหาก่อน")
    else:
        st.session_state.searched = True
        st.session_state.cust_page = 1
        st.session_state.detail_idx = None
        st.session_state.last_keyword = keyword
        st.session_state.last_year = year_sel

if st.sidebar.button("ล้าง / Refresh", use_container_width=True):
    st.cache_data.clear()
    st.session_state.searched = False
    st.session_state.cust_page = 1
    st.session_state.detail_idx = None
    st.rerun()


st.title("ข้อมูลลูกค้า")

if not st.session_state.searched:
    st.markdown(
        """
        <div class="search-hint">
            <div class="icon">🔎</div>
            <h2>ค้นหาลูกค้าก่อนเลยครับ</h2>
            <p>พิมพ์ชื่อ เบอร์โทร หรือเลขออเดอร์ เพื่อดูประวัติจาก DATA_RAW</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.stop()


raw_df = search_orders(st.session_state.last_keyword, st.session_state.last_year)
if raw_df.empty:
    st.warning(f"ไม่พบลูกค้าที่ค้นหา: {st.session_state.last_keyword}")
    st.stop()

customer_df = build_customer_list(raw_df)
if customer_df.empty:
    st.warning("พบข้อมูลดิบ แต่ยังจัดกลุ่มลูกค้าไม่ได้")
    st.stop()


if st.session_state.detail_idx is not None:
    idx = st.session_state.detail_idx
    if idx >= len(customer_df):
        st.session_state.detail_idx = None
        st.rerun()

    customer = customer_df.iloc[idx]
    orders = customer["_orders"]
    latest = sorted(orders, key=lambda item: clean(item.get("source_key")), reverse=True)[0]
    latest_products = parse_products(latest.get("products"))

    if st.button("กลับรายชื่อลูกค้า"):
        st.session_state.detail_idx = None
        st.rerun()

    st.title(customer["customer"] or "(ไม่ระบุชื่อลูกค้า)")
    st.markdown(
        f"""
        <span class="badge">โทร {html_escape(customer['phones'])}</span>
        <span class="badge badge-green">{int(customer['order_count'])} ออเดอร์</span>
        <span class="badge badge-blue">{html_escape(customer['province']) or '-'}</span>
        <br><br>
        <b>ยอดซื้อรวม: <span class="green">{customer['total_sales']:,.0f} บาท</span></b>
        """,
        unsafe_allow_html=True,
    )

    st.subheader("รายละเอียดออเดอร์ล่าสุด")
    st.markdown(
        info_table(
            [
                ("เลขออเดอร์", latest.get("order_id")),
                ("วันที่", latest.get("date_text")),
                ("ช่องทางขาย", latest.get("channel")),
                ("สถานะคำสั่งซื้อ", latest.get("order_status")),
                ("วิธีชำระเงิน", latest.get("payment_method")),
                ("ขนส่ง", latest.get("shipping")),
                ("หมายเลขพัสดุ", latest.get("tracking_no")),
                ("พนักงานปิดการขาย", latest.get("sales_staff")),
                ("พนักงาน UPSELL", latest.get("upsell_staff")),
                ("พนักงานดูแล", latest.get("care_staff")),
                ("ที่อยู่จัดส่ง", full_address(latest)),
                ("หมายเหตุ", latest.get("note")),
            ]
        ),
        unsafe_allow_html=True,
    )

    st.subheader("รายการสินค้าในออเดอร์ล่าสุด")
    st.markdown(product_table(latest_products), unsafe_allow_html=True)
    render_order_history(orders)
    st.stop()


total_customers = len(customer_df)
total_pages = max(1, (total_customers + PAGE_SIZE - 1) // PAGE_SIZE)

k1, k2, k3 = st.columns(3)
k1.metric("พบลูกค้า", f"{total_customers:,}")
k2.metric("ยอดขายรวม", f"{customer_df['total_sales'].sum():,.0f}")
k3.metric("ออเดอร์รวม", f"{customer_df['order_count'].sum():,.0f}")

st.caption(f"ผลการค้นหา: {st.session_state.last_keyword}")
st.divider()

col_info, col_prev, col_next = st.columns([4, 1, 1])
col_info.markdown(f"**หน้า {st.session_state.cust_page} / {total_pages}** | {total_customers:,} ราย")
if col_prev.button("ก่อนหน้า") and st.session_state.cust_page > 1:
    st.session_state.cust_page -= 1
    st.rerun()
if col_next.button("ถัดไป") and st.session_state.cust_page < total_pages:
    st.session_state.cust_page += 1
    st.rerun()

start = (st.session_state.cust_page - 1) * PAGE_SIZE
end = start + PAGE_SIZE
page_customers = customer_df.iloc[start:end].reset_index(drop=True)

for i, customer in page_customers.iterrows():
    abs_idx = start + i
    st.markdown(
        f"""
        <div class="customer-card">
            <h3>{html_escape(customer['customer']) or '(ไม่ระบุชื่อ)'}</h3>
            <span class="badge">โทร {html_escape(customer['phones'])}</span>
            <span class="badge badge-green">{int(customer['order_count'])} ออเดอร์</span>
            <span class="badge badge-blue">{html_escape(customer['province']) or '-'}</span>
            <br><br>
            ล่าสุด: <b>{html_escape(customer['latest_date'])}</b>
            &nbsp;&nbsp; ยอดรวม: <span class="green">{customer['total_sales']:,.0f} บาท</span>
            &nbsp;&nbsp; ช่องทาง: {html_escape(customer['channel']) or '-'}
            &nbsp;&nbsp; ผู้ขายล่าสุด: {html_escape(customer['sales_staff']) or '-'}
        </div>
        """,
        unsafe_allow_html=True,
    )

    if st.button("ดูประวัติการซื้อ", key=f"detail_{abs_idx}"):
        st.session_state.detail_idx = abs_idx
        st.rerun()

    st.markdown("---")

st.caption(f"แสดง {start + 1:,}-{min(end, total_customers):,} จาก {total_customers:,} รายการ")
