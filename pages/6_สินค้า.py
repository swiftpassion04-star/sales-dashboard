import os
from datetime import datetime, timezone
from urllib.parse import quote

import pandas as pd
import requests
import streamlit as st

from auth_utils import can_manage_all, require_login


PRODUCT_OPTIONS_TABLE = "crm_product_options"


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


st.set_page_config(page_title="สินค้า", layout="wide")


def inject_css() -> None:
    st.markdown(
        """
<style>
:root {
  --crm-bg:#fff8f1;
  --crm-border:#fed7aa;
  --crm-border-strong:#fb923c;
  --crm-text:#111827;
  --crm-accent:#f97316;
  --crm-accent-dark:#ea580c;
  --crm-shadow:0 18px 44px rgba(124,45,18,.08);
}
.stApp { background:var(--crm-bg); color:var(--crm-text); }
.block-container { max-width:1180px; padding-top:2.4rem; padding-bottom:3rem; }
section[data-testid="stSidebar"] {
  background:linear-gradient(180deg,#ffffff 0%,#fff7ed 100%) !important;
  border-right:1px solid var(--crm-border) !important;
}
section[data-testid="stSidebar"] * { color:var(--crm-text) !important; }
h1 {
  color:var(--crm-text) !important;
  border-left:6px solid var(--crm-accent);
  padding-left:14px;
  letter-spacing:0;
}
[data-testid="stForm"] {
  background:linear-gradient(180deg,#ffffff 0%,#fffaf5 100%) !important;
  border:1px solid var(--crm-border) !important;
  border-radius:14px !important;
  padding:22px !important;
  box-shadow:var(--crm-shadow);
}
label { color:#7c2d12 !important; font-weight:750 !important; }
div[data-baseweb="input"] > div,
div[data-baseweb="select"] > div,
input {
  background:#ffffff !important;
  color:var(--crm-text) !important;
  -webkit-text-fill-color:var(--crm-text) !important;
  border:1px solid var(--crm-border-strong) !important;
  border-radius:10px !important;
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
button[kind="formSubmit"] {
  background:linear-gradient(90deg,#f97316 0%,#ea580c 100%) !important;
  color:#ffffff !important;
}
[data-testid="stDataFrame"] {
  background:#ffffff !important;
  border:1px solid var(--crm-border) !important;
  border-radius:12px !important;
  box-shadow:var(--crm-shadow);
}
[data-testid="stAlert"] * { color:#111827 !important; }
</style>
""",
        unsafe_allow_html=True,
    )


def main() -> None:
    inject_css()
    st.title("สินค้า")
    st.caption("จัดการตัวเลือกกลุ่มสินค้าและสินค้า สำหรับใช้ในหน้าเพิ่มข้อมูลลูกค้า")
    auth_user = require_login()
    if not can_manage_all(auth_user):
        st.warning("หน้านี้จัดการได้เฉพาะตำแหน่ง EDITOR เท่านั้น")
        st.stop()
    require_config()
    render_product_options(auth_user)


def require_config() -> None:
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        st.error("ยังไม่ได้ตั้งค่า CRM_SUPABASE_URL หรือ CRM_SUPABASE_SERVICE_KEY")
        st.stop()


def headers(prefer: str = "return=minimal") -> dict[str, str]:
    return {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json",
        "Prefer": prefer,
    }


def api_request(method: str, table: str, params: str = "", payload=None, prefer: str = "return=minimal"):
    response = requests.request(
        method,
        f"{SUPABASE_URL}/rest/v1/{table}{params}",
        headers=headers(prefer),
        json=payload,
        timeout=60,
    )
    if response.status_code >= 300:
        raise RuntimeError(response.text)
    if not response.text:
        return []
    return response.json()


def render_product_options(auth_user: dict) -> None:
    with st.form("product_option_create", clear_on_submit=True):
        col1, col2, col3 = st.columns([1, 1, 0.5])
        product_group = col1.text_input("กลุ่มสินค้า")
        product_name = col2.text_input("สินค้า")
        sort_order = col3.number_input("ลำดับ", min_value=0, value=0, step=1)
        submitted = st.form_submit_button("เพิ่มสินค้า", use_container_width=True)
    if submitted:
        if not clean(product_group) or not clean(product_name):
            st.error("กรุณากรอกกลุ่มสินค้าและสินค้า")
        else:
            payload = {
                "product_group": clean(product_group),
                "product_name": clean(product_name),
                "sort_order": int(sort_order),
                "is_active": True,
                "created_by": clean(auth_user.get("email")),
                "updated_by": clean(auth_user.get("email")),
                "updated_at": now_iso(),
            }
            api_request(
                "POST",
                PRODUCT_OPTIONS_TABLE,
                params="?on_conflict=product_group,product_name",
                payload=payload,
                prefer="resolution=merge-duplicates,return=minimal",
            )
            st.success("เพิ่ม/อัปเดตสินค้าแล้ว")
            st.cache_data.clear()
            st.rerun()

    rows = api_request(
        "GET",
        PRODUCT_OPTIONS_TABLE,
        params="?select=id,product_group,product_name,is_active,sort_order,updated_at&order=sort_order.asc,product_group.asc,product_name.asc",
        prefer="return=representation",
    )
    df = pd.DataFrame(rows)
    if df.empty:
        st.info("ยังไม่มีรายการสินค้า")
        return
    st.markdown("### รายการสินค้า")
    header = st.columns([1.3, 1.6, 0.45, 0.55, 0.75, 0.95])
    header[0].markdown("**กลุ่มสินค้า**")
    header[1].markdown("**สินค้า**")
    header[2].markdown("**ลำดับ**")
    header[3].markdown("**สถานะ**")
    header[4].markdown("**แก้ไข**")
    header[5].markdown("**ลบถาวร**")
    for _, row in df.iterrows():
        render_product_row(row.to_dict(), auth_user)


def render_product_row(row: dict, auth_user: dict) -> None:
    row_id = clean(row.get("id"))
    label = f"{clean(row.get('product_group'))} / {clean(row.get('product_name'))}"
    cols = st.columns([1.3, 1.6, 0.45, 0.55, 0.75, 0.95])
    group = cols[0].text_input("กลุ่มสินค้า", value=clean(row.get("product_group")), key=f"product_group_{row_id}", label_visibility="collapsed")
    product = cols[1].text_input("สินค้า", value=clean(row.get("product_name")), key=f"product_name_{row_id}", label_visibility="collapsed")
    sort_order = cols[2].number_input(
        "ลำดับ",
        min_value=0,
        value=int(row.get("sort_order") or 0),
        step=1,
        key=f"product_sort_{row_id}",
        label_visibility="collapsed",
    )
    is_active = cols[3].checkbox("เปิด", value=bool(row.get("is_active")), key=f"product_active_{row_id}", label_visibility="collapsed")
    if cols[4].button("บันทึก", key=f"product_save_{row_id}", use_container_width=True):
        if not clean(group) or not clean(product):
            st.error("กรุณากรอกกลุ่มสินค้าและสินค้า")
            return
        api_request(
            "PATCH",
            PRODUCT_OPTIONS_TABLE,
            params=f"?id=eq.{quote(row_id)}",
            payload={
                "product_group": clean(group),
                "product_name": clean(product),
                "sort_order": int(sort_order),
                "is_active": bool(is_active),
                "updated_by": clean(auth_user.get("email")),
                "updated_at": now_iso(),
            },
        )
        st.success("บันทึกสินค้าแล้ว")
        st.cache_data.clear()
        st.rerun()
    confirm = cols[5].text_input(
        "พิมพ์ ลบ",
        key=f"product_delete_confirm_{row_id}",
        placeholder="พิมพ์ ลบ",
        label_visibility="collapsed",
    )
    if cols[5].button("ลบ", key=f"product_delete_{row_id}", use_container_width=True):
        if clean(confirm) != "ลบ":
            st.error(f"กรุณาพิมพ์คำว่า ลบ เพื่อยืนยันลบถาวร: {label}")
            return
        api_request("DELETE", PRODUCT_OPTIONS_TABLE, params=f"?id=eq.{quote(row_id)}")
        st.success(f"ลบถาวรแล้ว: {label}")
        st.cache_data.clear()
        st.rerun()


def clean(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


main()
