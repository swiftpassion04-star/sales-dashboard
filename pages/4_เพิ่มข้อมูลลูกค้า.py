import os
import uuid
from io import BytesIO
from datetime import datetime, timezone
from urllib.parse import quote

import pandas as pd
import requests
import streamlit as st

from auth_utils import can_manage_all, require_login


CUSTOMERS_V2_TABLE = "crm_customers_v2"
PRODUCT_OPTIONS_TABLE = "crm_product_options"
STAFF_OPTIONS_TABLE = "crm_staff_options"
ORDER_TABLE = "order_history"
IMPORT_BATCH_TABLE = "data_raw_import_batches"
BATCH_SIZE = 500
PREVIEW_ROWS = 100

CUSTOMER_COLUMNS = [
    "customer_id",
    "customer",
    "sales_staff",
    "product_url",
    "product_sku",
    "product_name",
    "phone1",
    "phone2",
    "product_group",
    "note",
]

ORDER_COLUMNS = [
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
    "note",
    "source_sheet",
    "year_file",
]

ORDER_SYNONYMS = {
    "order_id": ["เลขคำสั่งซื้อ", "เลขออเดอร์", "order_id"],
    "customer": ["ลูกค้า", "ชื่อลูกค้า", "customer"],
    "phone1": ["เบอร์โทร (1)", "เบอร์โทร", "เบอร์โทรติดต่อ", "phone1"],
    "phone2": ["เบอร์โทร (2)", "เบอร์โทรสำรอง", "phone2"],
    "tracking_no": ["หมายเลขพัสดุ", "เลขพัสดุ", "tracking_no"],
    "total_sales": ["ยอดขายรวม", "ยอดขาย", "total_sales"],
    "payment_method": ["วิธีการชำระเงิน", "วิธีชำระ", "payment_method"],
    "delivery_status": ["สถานะจัดส่ง", "delivery_status"],
    "channel_url": ["ช่องทาง URL", "URL", "url", "channel_url"],
    "product_group": ["หมวดสินค้า", "กลุ่มสินค้า", "product_group"],
}


def get_secret(*names: str) -> str:
    for name in names:
        if name in st.secrets:
            return str(st.secrets[name])
        value = os.getenv(name, "")
        if value:
            return value
    return ""


SUPABASE_URL = get_secret("CRM_SUPABASE_URL", "SUPABASE_URL").rstrip("/")
SUPABASE_SERVICE_KEY = get_secret("CRM_SUPABASE_SERVICE_KEY", "SUPABASE_SERVICE_KEY")


st.set_page_config(page_title="เพิ่มข้อมูลลูกค้า", layout="wide")


def main() -> None:
    inject_css()
    st.title("เพิ่มข้อมูลลูกค้า")
    st.caption("เพิ่มข้อมูลเข้า crm_customers_v2 ก่อน โดยยังไม่เปลี่ยน source หลักของรายงาน")

    auth_user = require_login()
    if not can_manage_all(auth_user):
        st.warning("หน้านี้จัดการได้เฉพาะตำแหน่ง EDITOR เท่านั้น")
        st.stop()
    require_config()

    render_create_customer_v2(auth_user)
    render_customer_import(auth_user)


def inject_css() -> None:
    st.markdown(
        """
<style>
:root {
  --crm-bg:#fff8f1;
  --crm-panel:#ffffff;
  --crm-panel-soft:#fffaf5;
  --crm-border:#fed7aa;
  --crm-border-strong:#fb923c;
  --crm-text:#111827;
  --crm-muted:#64748b;
  --crm-accent:#f97316;
  --crm-accent-dark:#ea580c;
  --crm-shadow:0 18px 44px rgba(124,45,18,.08);
}
.stApp {
  background:var(--crm-bg);
  color:var(--crm-text);
}
.block-container {
  max-width:1180px;
  padding-top:2.4rem;
  padding-bottom:3rem;
}
section[data-testid="stSidebar"] {
  background:linear-gradient(180deg,#ffffff 0%,#fff7ed 100%) !important;
  border-right:1px solid var(--crm-border) !important;
}
section[data-testid="stSidebar"] * {
  color:var(--crm-text) !important;
}
section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a {
  border-radius:8px !important;
  color:var(--crm-text) !important;
  font-weight:650 !important;
}
section[data-testid="stSidebar"] [aria-current="page"],
section[data-testid="stSidebar"] a:hover {
  background:#ffedd5 !important;
  color:var(--crm-accent-dark) !important;
}
.crm-auth-card {
  background:#fffaf5 !important;
  border:1px solid var(--crm-border) !important;
  border-radius:8px !important;
  box-shadow:0 10px 24px rgba(234,88,12,.06);
}
h1 {
  color:var(--crm-text) !important;
  border-left:6px solid var(--crm-accent);
  padding-left:14px;
  margin-bottom:1.2rem;
  letter-spacing:0;
}
h2, h3 {
  color:var(--crm-text) !important;
  letter-spacing:0;
}
p, label, span, div[data-testid="stMarkdownContainer"] {
  color:var(--crm-text);
}
[data-testid="stCaptionContainer"] {
  color:var(--crm-muted) !important;
}
.stTabs [data-baseweb="tab-list"] {
  gap:8px;
  border-bottom:1px solid var(--crm-border);
}
.stTabs [data-baseweb="tab"] {
  color:#9a3412 !important;
  background:#fffaf5 !important;
  border:1px solid var(--crm-border) !important;
  border-bottom:0 !important;
  border-radius:10px 10px 0 0 !important;
  padding:8px 14px !important;
}
.stTabs [aria-selected="true"] {
  color:var(--crm-accent-dark) !important;
  background:#ffffff !important;
  font-weight:800 !important;
}
[data-testid="stForm"] {
  background:linear-gradient(180deg,#ffffff 0%,#fffaf5 100%) !important;
  border:1px solid var(--crm-border) !important;
  border-radius:14px !important;
  padding:22px 22px 18px !important;
  box-shadow:var(--crm-shadow);
  margin:12px 0 28px !important;
}
[data-testid="stForm"] label,
.stTextInput label,
.stTextArea label,
.stSelectbox label,
.stNumberInput label,
.stFileUploader label,
.stCheckbox label {
  color:#7c2d12 !important;
  font-weight:750 !important;
  font-size:14px !important;
  background:transparent !important;
}
div[data-baseweb="input"] > div,
div[data-baseweb="select"] > div,
textarea,
input,
[data-baseweb="textarea"] textarea {
  background:#ffffff !important;
  color:var(--crm-text) !important;
  -webkit-text-fill-color:var(--crm-text) !important;
  border:1px solid var(--crm-border-strong) !important;
  border-radius:10px !important;
  box-shadow:none !important;
}
div[data-baseweb="input"] > div:focus-within,
div[data-baseweb="select"] > div:focus-within,
textarea:focus,
input:focus {
  border-color:var(--crm-accent-dark) !important;
  box-shadow:0 0 0 3px rgba(249,115,22,.16) !important;
  outline:none !important;
}
input::placeholder,
textarea::placeholder {
  color:#c2410c !important;
  opacity:.55 !important;
}
div[data-baseweb="input"] *,
div[data-baseweb="select"] *,
[role="listbox"] *,
[data-baseweb="popover"] * {
  color:var(--crm-text) !important;
}
[role="listbox"],
[data-baseweb="popover"] > div {
  background:#ffffff !important;
  border:1px solid var(--crm-border) !important;
  box-shadow:0 18px 44px rgba(124,45,18,.14) !important;
}
[role="option"] {
  background:#ffffff !important;
  color:var(--crm-text) !important;
}
[role="option"]:hover,
[aria-selected="true"] {
  background:#ffedd5 !important;
  color:#7c2d12 !important;
}
.stButton > button,
button[kind="formSubmit"] {
  min-height:42px !important;
  border-radius:10px !important;
  border:1px solid var(--crm-accent) !important;
  color:#9a3412 !important;
  background:#ffffff !important;
  font-weight:800 !important;
}
.stButton > button:hover {
  background:#fff7ed !important;
  border-color:var(--crm-accent-dark) !important;
}
button[kind="formSubmit"] {
  background:linear-gradient(90deg,#f97316 0%,#ea580c 100%) !important;
  color:#ffffff !important;
}
button[kind="formSubmit"]:hover {
  filter:brightness(.98);
}
[data-testid="stAlert"] {
  border-radius:10px !important;
}
[data-testid="stAlert"] * {
  color:#111827 !important;
}
[data-testid="stDataFrame"],
[data-testid="stTable"] {
  background:#ffffff !important;
  border:1px solid var(--crm-border) !important;
  border-radius:12px !important;
  box-shadow:var(--crm-shadow);
}
[data-testid="stDataFrame"] * {
  color:#111827 !important;
}
[data-testid="stExpander"] {
  background:#ffffff !important;
  border:1px solid var(--crm-border) !important;
  border-radius:14px !important;
  box-shadow:var(--crm-shadow);
  overflow:hidden;
}
[data-testid="stExpander"] details,
[data-testid="stExpander"] summary {
  background:#ffffff !important;
  color:var(--crm-text) !important;
}
[data-testid="stExpander"] summary {
  border-bottom:1px solid #ffedd5 !important;
  font-weight:800 !important;
}
[data-testid="stExpander"] summary *,
[data-testid="stFileUploader"] *,
[data-testid="stDownloadButton"] * {
  color:var(--crm-text) !important;
}
[data-testid="stFileUploader"] {
  background:#ffffff !important;
  border:1px dashed var(--crm-border-strong) !important;
  border-radius:14px !important;
  padding:14px !important;
}
[data-testid="stFileUploader"] section {
  background:#fffaf5 !important;
  border:1px dashed #fdba74 !important;
  border-radius:12px !important;
}
[data-testid="stFileUploader"] button,
[data-testid="stDownloadButton"] button {
  background:#ffffff !important;
  color:#9a3412 !important;
  border:1px solid var(--crm-accent) !important;
  border-radius:10px !important;
  font-weight:800 !important;
}
.stButton > button[kind="primary"],
[data-testid="stFormSubmitButton"] button {
  background:linear-gradient(90deg,#f97316 0%,#ea580c 100%) !important;
  color:#ffffff !important;
  border:1px solid var(--crm-accent-dark) !important;
}
[data-testid="stFileUploaderDropzone"] {
  background:#fffaf5 !important;
  color:var(--crm-text) !important;
}
[data-testid="stFileUploaderDropzone"] * {
  color:var(--crm-text) !important;
}
hr {
  border-color:var(--crm-border) !important;
}
@media (max-width: 900px) {
  .block-container {
    max-width:100%;
    padding-left:1rem;
    padding-right:1rem;
  }
}
</style>
""",
        unsafe_allow_html=True,
    )


def require_config() -> None:
    missing = []
    if not SUPABASE_URL:
        missing.append("CRM_SUPABASE_URL")
    if not SUPABASE_SERVICE_KEY:
        missing.append("CRM_SUPABASE_SERVICE_KEY")
    if missing:
        st.error("ยังไม่ได้ตั้งค่า Streamlit secrets: " + ", ".join(missing))
        st.stop()


def headers(prefer: str = "return=minimal") -> dict[str, str]:
    return {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json",
        "Prefer": prefer,
    }


def api_request(method: str, table: str, params: str = "", payload=None, prefer: str = "return=minimal"):
    url = f"{SUPABASE_URL}/rest/v1/{table}{params}"
    response = requests.request(method, url, headers=headers(prefer), json=payload, timeout=120)
    if response.status_code >= 300:
        raise RuntimeError(f"{method} {table} failed: {response.status_code} {response.text}")
    if not response.text:
        return []
    return response.json()


@st.cache_data(ttl=300, show_spinner=False)
def load_product_options() -> list[dict]:
    try:
        rows = api_request(
            "GET",
            PRODUCT_OPTIONS_TABLE,
            params="?select=id,sku,product_group,product_name,is_active,sort_order&is_active=eq.true&order=sku.asc,sort_order.asc,product_group.asc,product_name.asc",
            prefer="return=representation",
        )
    except Exception:
        return []
    return rows if isinstance(rows, list) else []


@st.cache_data(ttl=300, show_spinner=False)
def load_staff_options() -> list[dict]:
    try:
        rows = api_request(
            "GET",
            STAFF_OPTIONS_TABLE,
            params="?select=id,staff_name,is_active,sort_order&is_active=eq.true&order=sort_order.asc,staff_name.asc",
            prefer="return=representation",
        )
    except Exception:
        return []
    return rows if isinstance(rows, list) else []


def select_or_manual(container, label: str, options: list[str], key: str) -> str:
    cleaned_options = [clean(option) for option in options if clean(option)]
    choices = ["เลือกจากรายการ"] + cleaned_options + ["พิมพ์เอง"]
    choice = container.selectbox(label, choices, key=f"{key}_choice")
    if choice == "พิมพ์เอง":
        return container.text_input(f"{label} (พิมพ์เอง)", key=f"{key}_manual")
    if choice == "เลือกจากรายการ":
        return ""
    return choice


def product_option_label(row: dict) -> str:
    sku = normalize_sku(row.get("sku"))
    product_name = clean(row.get("product_name"))
    return f"{sku} {product_name}".strip() if sku else product_name


def render_create_customer_v2(auth_user: dict) -> None:
    product_options = load_product_options()
    staff_options = load_staff_options()
    product_groups = sorted({clean(row.get("product_group")) for row in product_options if clean(row.get("product_group"))})
    staff_names = [clean(row.get("staff_name")) for row in staff_options if clean(row.get("staff_name"))]
    option_col1, option_col2, option_col3 = st.columns(3)
    product_group = select_or_manual(option_col1, "กลุ่มสินค้า", product_groups, "customer_v2_product_group")
    available_products = [
        product_option_label(row)
        for row in product_options
        if clean(row.get("product_group")) == clean(product_group) and clean(row.get("product_name"))
    ]
    product_label = select_or_manual(option_col2, "สินค้า", available_products, "customer_v2_product_name")
    product_sku, product_name = split_product_label(product_label)
    sales_staff = select_or_manual(option_col3, "ผู้ดูแล", staff_names, "customer_v2_sales_staff")

    with st.form("customer_v2_create", clear_on_submit=True):
        col1, col2 = st.columns(2)
        customer = col1.text_input("ชื่อลูกค้า")
        phone1 = col1.text_input("เบอร์โทรติดต่อ")
        phone2 = col2.text_input("เบอร์โทรสำรอง")
        product_url = st.text_input("URL")
        note = st.text_area("โน๊ต", height=90)
        submitted = st.form_submit_button("สร้างข้อมูลลูกค้า", use_container_width=True)
    if not submitted:
        return
    if not clean(customer):
        st.error("กรุณากรอกชื่อลูกค้า")
        return
    payload = {
        "customer_id": "web:" + datetime.utcnow().strftime("%Y%m%d%H%M%S%f"),
        "customer": clean(customer),
        "product_group": clean(product_group),
        "product_sku": clean(product_sku),
        "product_name": clean(product_name),
        "sales_staff": clean(sales_staff),
        "phone1": clean(phone1),
        "phone2": clean(phone2),
        "product_url": clean(product_url),
        "note": clean(note),
        "source": "web",
        "created_by": clean(auth_user.get("email")),
        "updated_by": clean(auth_user.get("email")),
        "updated_at": now_iso(),
    }
    api_request("POST", CUSTOMERS_V2_TABLE, payload=payload)
    st.success("สร้างข้อมูลลูกค้า SQL v2 แล้ว")
    st.cache_data.clear()


def render_customer_import(auth_user: dict) -> None:
    with st.expander("นำเข้าลูกค้าจาก Excel", expanded=False):
        headers = ["ชื่อลูกค้า", "พนักงานดูแล", "URL", "SKU", "สินค้า", "เบอร์โทรติดต่อ", "เบอร์โทรสำรอง", "กลุ่มสินค้า"]
        st.download_button(
            "ดาวน์โหลดฟอร์มเพิ่มข้อมูลลูกค้า (.xlsx)",
            data=build_xlsx_template(headers, "เพิ่มข้อมูลลูกค้า"),
            file_name="crm_customer_import_template.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
        uploaded = st.file_uploader("อัปโหลดไฟล์ลูกค้า .xlsx", type=["xlsx"], key="customer_v2_upload")
        if not uploaded:
            st.info("ใช้หัวตาราง: " + " / ".join(headers))
            return
        try:
            df = pd.read_excel(uploaded, dtype=str).fillna("")
        except Exception as exc:
            st.error(f"อ่านไฟล์ไม่สำเร็จ: {exc}")
            return
        missing = [column for column in headers if column not in df.columns]
        if missing:
            st.error("หัวตารางไม่ครบ: " + ", ".join(missing))
            return
        import_df = df[headers].copy()
        for column in headers:
            import_df[column] = import_df[column].map(clean)
        import_df["SKU"] = import_df["SKU"].map(normalize_sku)
        import_df = import_df[import_df["ชื่อลูกค้า"] != ""]
        st.dataframe(import_df.head(100), use_container_width=True)
        st.caption(f"พร้อมนำเข้า {len(import_df):,} แถว")
        confirm = st.checkbox("ยืนยันนำเข้าลูกค้า", key="confirm_customer_v2_import")
        if st.button("นำเข้าลูกค้า", disabled=not confirm or import_df.empty, use_container_width=True):
            created = 0
            updated = 0
            for _, row in import_df.iterrows():
                result = merge_customer_import_row(row.to_dict(), auth_user)
                if result == "created":
                    created += 1
                elif result == "updated":
                    updated += 1
            st.success(f"นำเข้าเสร็จ: เพิ่มใหม่ {created:,} แถว / merge {updated:,} แถว")
            st.cache_data.clear()
            st.rerun()


def merge_customer_import_row(row: dict, auth_user: dict) -> str:
    customer = clean(row.get("ชื่อลูกค้า"))
    staff = clean(row.get("พนักงานดูแล"))
    url = clean(row.get("URL"))
    sku = normalize_sku(row.get("SKU"))
    product = clean(row.get("สินค้า"))
    phone1 = clean(row.get("เบอร์โทรติดต่อ"))
    phone2 = clean(row.get("เบอร์โทรสำรอง"))
    group = clean(row.get("กลุ่มสินค้า"))
    existing = find_existing_customer_v2(customer, phone1, phone2)
    product_name = format_product_name(sku, product)
    if existing:
        payload = {
            "customer": customer or clean(existing.get("customer")),
            "sales_staff": staff or clean(existing.get("sales_staff")),
            "product_url": url or clean(existing.get("product_url")),
            "product_sku": merge_csv_values(clean(existing.get("product_sku")), sku),
            "product_name": merge_csv_values(clean(existing.get("product_name")), product_name),
            "phone1": phone1 or clean(existing.get("phone1")),
            "phone2": phone2 or clean(existing.get("phone2")),
            "product_group": group or clean(existing.get("product_group")),
            "updated_by": clean(auth_user.get("email")),
            "updated_at": now_iso(),
        }
        api_request("PATCH", CUSTOMERS_V2_TABLE, params=f"?id=eq.{quote(clean(existing.get('id')))}", payload=payload)
        return "updated"
    payload = {
        "customer_id": "web:" + datetime.utcnow().strftime("%Y%m%d%H%M%S%f"),
        "customer": customer,
        "sales_staff": staff,
        "product_url": url,
        "product_sku": sku,
        "product_name": product_name,
        "phone1": phone1,
        "phone2": phone2,
        "product_group": group,
        "source": "excel",
        "created_by": clean(auth_user.get("email")),
        "updated_by": clean(auth_user.get("email")),
        "updated_at": now_iso(),
    }
    api_request("POST", CUSTOMERS_V2_TABLE, payload=payload)
    return "created"


def find_existing_customer_v2(customer: str, phone1: str, phone2: str) -> dict | None:
    select = "select=id,customer,phone1,phone2,sales_staff,product_url,product_sku,product_name,product_group"
    filters = []
    if phone1:
        q = quote(phone1)
        filters.extend([f"phone1.eq.{q}", f"phone2.eq.{q}"])
    if phone2:
        q = quote(phone2)
        filters.extend([f"phone1.eq.{q}", f"phone2.eq.{q}"])
    if filters:
        rows = api_request("GET", CUSTOMERS_V2_TABLE, params=f"?{select}&or=({','.join(filters)})&limit=1", prefer="return=representation")
        if rows:
            return rows[0]
    if customer:
        rows = api_request("GET", CUSTOMERS_V2_TABLE, params=f"?{select}&customer=eq.{quote(customer)}&limit=1", prefer="return=representation")
        if rows:
            return rows[0]
    return None


def merge_csv_values(existing: str, new_value: str) -> str:
    values = [clean(value) for value in existing.split(",") if clean(value)]
    if clean(new_value) and clean(new_value) not in values:
        values.append(clean(new_value))
    return ", ".join(values)


def format_product_name(sku: str, product: str) -> str:
    sku = normalize_sku(sku)
    product = clean(product)
    return f"{sku} {product}".strip() if sku else product


def split_product_label(label: str) -> tuple[str, str]:
    label = clean(label)
    if not label:
        return "", ""
    first, _, rest = label.partition(" ")
    if first.isdigit():
        return normalize_sku(first), clean(rest)
    return "", label


def render_customers_v2(auth_user: dict) -> None:
    st.subheader("เพิ่มข้อมูลลูกค้า")
    with st.form("customer_v2_create", clear_on_submit=True):
        col1, col2 = st.columns(2)
        customer = col1.text_input("ชื่อลูกค้า")
        product_group = col2.text_input("กลุ่มสินค้า")
        product_name = col1.text_input("สินค้า")
        sales_staff = col2.text_input("ผู้ดูแล")
        phone1 = col1.text_input("เบอร์โทรติดต่อ")
        phone2 = col2.text_input("เบอร์โทรสำรอง")
        product_url = st.text_input("URL")
        note = st.text_area("โน๊ต", height=90)
        submitted = st.form_submit_button("สร้างข้อมูลลูกค้า", use_container_width=True)
    if submitted:
        if not clean(customer):
            st.error("กรุณากรอกชื่อลูกค้า")
        else:
            payload = {
                "customer_id": "web:" + datetime.utcnow().strftime("%Y%m%d%H%M%S%f"),
                "customer": clean(customer),
                "product_group": clean(product_group),
                "product_name": clean(product_name),
                "sales_staff": clean(sales_staff),
                "phone1": clean(phone1),
                "phone2": clean(phone2),
                "product_url": clean(product_url),
                "note": clean(note),
                "source": "web",
                "created_by": clean(auth_user.get("email")),
                "updated_by": clean(auth_user.get("email")),
                "updated_at": now_iso(),
            }
            api_request("POST", CUSTOMERS_V2_TABLE, payload=payload)
            st.success("สร้างข้อมูลลูกค้า SQL v2 แล้ว")
            st.cache_data.clear()

    st.subheader("รายการลูกค้า SQL v2")
    keyword = st.text_input("ค้นหา v2", placeholder="ชื่อลูกค้า / เบอร์ / ผู้ดูแล")
    params = [
        "select=id,customer_id,customer,sales_staff,phone1,phone2,product_group,product_name,product_url,note,deleted_at,created_at,updated_at",
        "order=updated_at.desc",
        "limit=50",
    ]
    if clean(keyword):
        q = quote(clean(keyword))
        params.append(f"or=(customer.ilike.*{q}*,phone1.ilike.*{q}*,phone2.ilike.*{q}*,sales_staff.ilike.*{q}*)")
    rows = api_request("GET", CUSTOMERS_V2_TABLE, params="?" + "&".join(params), prefer="return=representation")
    df = pd.DataFrame(rows)
    if df.empty:
        st.info("ยังไม่มีข้อมูลลูกค้า v2")
        return
    st.dataframe(df.drop(columns=["id"], errors="ignore"), use_container_width=True)

    selected = st.selectbox("เลือกลูกค้าที่ต้องการแก้ไข/ลบ", df["customer_id"].tolist())
    row = df[df["customer_id"] == selected].iloc[0].to_dict()
    with st.form("customer_v2_edit"):
        col1, col2 = st.columns(2)
        edit_customer = col1.text_input("ชื่อลูกค้า", value=clean(row.get("customer")))
        edit_group = col2.text_input("กลุ่มสินค้า", value=clean(row.get("product_group")))
        edit_product = col1.text_input("สินค้า", value=clean(row.get("product_name")))
        edit_staff = col2.text_input("ผู้ดูแล", value=clean(row.get("sales_staff")))
        edit_phone1 = col1.text_input("เบอร์โทรติดต่อ", value=clean(row.get("phone1")))
        edit_phone2 = col2.text_input("เบอร์โทรสำรอง", value=clean(row.get("phone2")))
        edit_url = st.text_input("URL", value=clean(row.get("product_url")))
        edit_note = st.text_area("โน๊ต", value=clean(row.get("note")), height=90)
        confirm_hard_delete = st.checkbox("ยืนยันลบจริงจาก SQL ถาวร", key="customer_v2_confirm_hard_delete")
        save_col, soft_col, hard_col = st.columns(3)
        save = save_col.form_submit_button("บันทึกแก้ไข", use_container_width=True)
        soft_delete = soft_col.form_submit_button("ลบแบบซ่อน", use_container_width=True)
        hard_delete = hard_col.form_submit_button("ลบจริงจาก SQL", use_container_width=True)
    if save:
        payload = {
            "customer": clean(edit_customer),
            "product_group": clean(edit_group),
            "product_name": clean(edit_product),
            "sales_staff": clean(edit_staff),
            "phone1": clean(edit_phone1),
            "phone2": clean(edit_phone2),
            "product_url": clean(edit_url),
            "note": clean(edit_note),
            "updated_by": clean(auth_user.get("email")),
            "updated_at": now_iso(),
        }
        api_request("PATCH", CUSTOMERS_V2_TABLE, params=f"?id=eq.{quote(row['id'])}", payload=payload)
        st.success("บันทึกแล้ว")
        st.rerun()
    if soft_delete:
        payload = {"deleted_at": now_iso(), "deleted_by": clean(auth_user.get("email")), "updated_at": now_iso()}
        api_request("PATCH", CUSTOMERS_V2_TABLE, params=f"?id=eq.{quote(row['id'])}", payload=payload)
        st.success("ลบแบบซ่อนแล้ว")
        st.rerun()
    if hard_delete and not confirm_hard_delete:
        st.error("กรุณาติ๊กยืนยันก่อนลบจริงจาก SQL")
    if hard_delete and confirm_hard_delete:
        st.warning("ลบจริงจาก SQL แล้วจะย้อนกลับไม่ได้")
        api_request("DELETE", CUSTOMERS_V2_TABLE, params=f"?id=eq.{quote(row['id'])}")
        st.success("ลบจริงจาก SQL แล้ว")
        st.rerun()


def render_data_raw_upload(auth_user: dict) -> None:
    st.subheader("นำเข้า DATA_RAW")
    uploaded = st.file_uploader("เลือกไฟล์ xlsx/csv", type=["xlsx", "csv"])
    if not uploaded:
        st.info("เลือกไฟล์ก่อน ระบบจะให้เลือก header row และ mapping columns ก่อน import")
        return

    sheets = read_upload(uploaded)
    sheet_name = ""
    if isinstance(sheets, dict):
        sheet_name = st.selectbox("Worksheet", list(sheets.keys()))
        raw_df = sheets[sheet_name]
    else:
        raw_df = sheets

    header_row = st.number_input("แถว header ที่ต้องการนำเข้า", min_value=1, max_value=max(len(raw_df), 1), value=1, step=1)
    df = dataframe_from_header(raw_df, int(header_row) - 1)
    if df.empty:
        st.warning("ไม่พบข้อมูลหลัง header row ที่เลือก")
        return

    st.caption(f"พบข้อมูล {len(df):,} แถวหลังตัดแถวว่าง")
    mapping = render_order_mapping(df)
    records = build_order_records(df, mapping, uploaded.name, sheet_name)
    preview = pd.DataFrame(records).head(PREVIEW_ROWS)
    st.dataframe(preview, use_container_width=True)

    valid_records = [record for record in records if clean(record.get("order_id"))]
    st.caption(f"พร้อม import {len(valid_records):,} / {len(records):,} แถว (ต้องมีเลขออเดอร์)")
    confirm = st.checkbox("ยืนยัน mapping และต้องการ import เข้า order_history")
    if st.button("Import DATA_RAW เข้า SQL", disabled=not confirm, use_container_width=True):
        batch_id = create_import_batch(uploaded.name, sheet_name, int(header_row), len(records), auth_user)
        progress = st.progress(0)
        imported = 0
        for start in range(0, len(valid_records), BATCH_SIZE):
            chunk = valid_records[start : start + BATCH_SIZE]
            for record in chunk:
                record["import_batch_id"] = batch_id
                record["imported_at"] = now_iso()
            api_request(
                "POST",
                ORDER_TABLE,
                params="?on_conflict=source_key",
                payload=chunk,
                prefer="resolution=merge-duplicates,return=minimal",
            )
            imported += len(chunk)
            progress.progress(min(imported / max(len(valid_records), 1), 1.0))
        skipped = len(records) - imported
        api_request(
            "PATCH",
            IMPORT_BATCH_TABLE,
            params=f"?id=eq.{quote(batch_id)}",
            payload={"status": "success", "imported_rows": imported, "skipped_rows": skipped, "completed_at": now_iso()},
        )
        st.success(f"import สำเร็จ {imported:,} แถว, ข้าม {skipped:,} แถว")


def render_order_mapping(df: pd.DataFrame) -> dict[str, str]:
    options = ["ไม่ใช้"] + list(df.columns)
    mapping = {}
    cols = st.columns(3)
    for index, field in enumerate(ORDER_COLUMNS):
        default = auto_match(field, df.columns)
        mapping[field] = cols[index % 3].selectbox(
            field,
            options,
            index=options.index(default) if default in options else 0,
            key=f"raw_map_{field}",
        )
    return mapping


def auto_match(field: str, columns) -> str:
    candidates = [field] + ORDER_SYNONYMS.get(field, [])
    lower_map = {clean(column).lower(): column for column in columns}
    for candidate in candidates:
        if candidate.lower() in lower_map:
            return lower_map[candidate.lower()]
    return "ไม่ใช้"


def build_order_records(df: pd.DataFrame, mapping: dict[str, str], filename: str, sheet_name: str) -> list[dict]:
    records = []
    for idx, row in df.iterrows():
        record = {}
        for field, source_col in mapping.items():
            record[field] = clean(row.get(source_col)) if source_col != "ไม่ใช้" else ""
        order_id = clean(record.get("order_id"))
        year_file = clean(record.get("year_file")) or clean(record.get("year"))
        record["source_key"] = f"{year_file or 'upload'}_{order_id}" if order_id else f"upload:{filename}:{sheet_name}:{idx}"
        record["source_sheet"] = clean(record.get("source_sheet")) or sheet_name or filename
        record["year_file"] = year_file
        record["total_sales"] = to_number(record.get("total_sales"))
        record["products"] = build_products_from_row(row)
        record["synced_at"] = now_iso()
        records.append(record)
    return records


def build_products_from_row(row: pd.Series) -> list[dict]:
    products = []
    for index in range(1, 11):
        sku = clean(pick_value(row, f"SKU ({index})", f"SKU{index}", f"sku_{index}", f"sku{index}"))
        product = clean(
            pick_value(
                row,
                f"สินค้า ({index})",
                f"สินค้า{index}",
                f"product_{index}",
                f"product{index}",
                f"item_{index}",
            )
        )
        quantity = to_number(pick_value(row, f"จำนวน ({index})", f"จำนวน{index}", f"qty_{index}", f"quantity_{index}"))
        price = to_number(pick_value(row, f"ราคา ({index})", f"ราคา{index}", f"price_{index}", f"unit_price_{index}"))
        if not any([sku, product, quantity, price]):
            continue
        products.append({"sku": sku, "product": product, "quantity": quantity, "price": price})
    if products:
        return products
    single_product = clean(pick_value(row, "สินค้า", "product", "product_name"))
    single_sku = clean(pick_value(row, "SKU", "sku"))
    if single_product or single_sku:
        return [{"sku": single_sku, "product": single_product, "quantity": None, "price": None}]
    return []


def pick_value(row: pd.Series, *names: str) -> object:
    lower_map = {clean(column).lower(): column for column in row.index}
    for name in names:
        column = lower_map.get(clean(name).lower())
        if column is not None:
            return row.get(column)
    return ""


def read_upload(uploaded):
    uploaded.seek(0)
    if uploaded.name.lower().endswith(".csv"):
        return pd.read_csv(uploaded, header=None, dtype=str).fillna("")
    excel = pd.ExcelFile(uploaded)
    return {sheet: pd.read_excel(excel, sheet_name=sheet, header=None, dtype=str).fillna("") for sheet in excel.sheet_names}


def dataframe_from_header(raw_df: pd.DataFrame, header_index: int) -> pd.DataFrame:
    headers = [clean(value) or f"EMPTY_{idx}" for idx, value in enumerate(raw_df.iloc[header_index].tolist())]
    df = raw_df.iloc[header_index + 1 :].copy()
    df.columns = headers
    df = df.fillna("").astype(str)
    df = df[df.apply(lambda row: any(clean(value) for value in row), axis=1)]
    return df.reset_index(drop=True)


def create_import_batch(filename: str, worksheet: str, header_row: int, total_rows: int, auth_user: dict) -> str:
    batch_id = str(uuid.uuid4())
    api_request(
        "POST",
        IMPORT_BATCH_TABLE,
        payload={
            "id": batch_id,
            "original_filename": filename,
            "worksheet_name": worksheet,
            "header_row": header_row,
            "total_rows": total_rows,
            "status": "importing",
            "created_by": clean(auth_user.get("email")),
        },
    )
    return batch_id


def clean(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and pd.isna(value):
        return ""
    text = str(value).strip()
    return "" if text.upper() in {"NULL", "NONE", "NAN"} else text


def normalize_sku(value) -> str:
    text = clean(value)
    if not text:
        return ""
    if text.endswith(".0") and text[:-2].isdigit():
        text = text[:-2]
    return text.zfill(3) if text.isdigit() and len(text) <= 3 else text


def build_xlsx_template(headers: list[str], sheet_name: str) -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        pd.DataFrame(columns=headers).to_excel(writer, index=False, sheet_name=sheet_name)
    return output.getvalue()


def to_number(value) -> float:
    text = clean(value).replace(",", "")
    if not text:
        return 0
    try:
        return float(text)
    except ValueError:
        return 0


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


if __name__ == "__main__":
    main()
