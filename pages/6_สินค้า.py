import os
from io import BytesIO
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
        col1, col2, col3, col4 = st.columns([0.45, 1, 1, 0.45])
        sku = col1.text_input("SKU")
        product_name = col2.text_input("สินค้า")
        product_group = col3.text_input("กลุ่มสินค้า")
        sort_order = col4.number_input("ลำดับ", min_value=0, value=0, step=1)
        submitted = st.form_submit_button("เพิ่มสินค้า", use_container_width=True)
    if submitted:
        if not clean(product_group) or not clean(product_name):
            st.error("กรุณากรอกกลุ่มสินค้าและสินค้า")
        else:
            payload = {
                "sku": normalize_sku(sku),
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

    render_product_import(auth_user)

    rows = api_request(
        "GET",
        PRODUCT_OPTIONS_TABLE,
        params="?select=id,sku,product_group,product_name,is_active,sort_order,updated_at&order=sku.asc,sort_order.asc,product_group.asc,product_name.asc",
        prefer="return=representation",
    )
    df = pd.DataFrame(rows)
    if df.empty:
        st.info("ยังไม่มีรายการสินค้า")
        return
    st.markdown("### รายการสินค้า")
    header = st.columns([0.45, 1.2, 1.5, 0.42, 0.5, 0.7, 0.9])
    header[0].markdown("**SKU**")
    header[1].markdown("**กลุ่มสินค้า**")
    header[2].markdown("**สินค้า**")
    header[3].markdown("**ลำดับ**")
    header[4].markdown("**สถานะ**")
    header[5].markdown("**แก้ไข**")
    header[6].markdown("**ลบถาวร**")
    for _, row in df.iterrows():
        render_product_row(row.to_dict(), auth_user)


def render_product_import(auth_user: dict) -> None:
    with st.expander("นำเข้าสินค้าจาก Excel", expanded=False):
        st.download_button(
            "ดาวน์โหลดฟอร์มสินค้า (.xlsx)",
            data=build_xlsx_template(["SKU", "สินค้า", "กลุ่มสินค้า"], "สินค้า"),
            file_name="crm_product_import_template.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
        uploaded = st.file_uploader("อัปโหลดไฟล์สินค้า .xlsx", type=["xlsx"], key="product_option_upload")
        if not uploaded:
            st.info("ใช้หัวตาราง: SKU / สินค้า / กลุ่มสินค้า")
            return
        try:
            df = pd.read_excel(uploaded, dtype=str).fillna("")
        except Exception as exc:
            st.error(f"อ่านไฟล์ไม่สำเร็จ: {exc}")
            return
        required = ["SKU", "สินค้า", "กลุ่มสินค้า"]
        missing = [column for column in required if column not in df.columns]
        if missing:
            st.error("หัวตารางไม่ครบ: " + ", ".join(missing))
            return
        import_df = df[required].copy()
        import_df["SKU"] = import_df["SKU"].map(normalize_sku)
        import_df["สินค้า"] = import_df["สินค้า"].map(clean)
        import_df["กลุ่มสินค้า"] = import_df["กลุ่มสินค้า"].map(clean)
        import_df = import_df[(import_df["สินค้า"] != "") & (import_df["กลุ่มสินค้า"] != "")]
        import_df = import_df.sort_values("SKU", kind="stable")
        st.dataframe(import_df.head(100), use_container_width=True)
        st.caption(f"พร้อมนำเข้า {len(import_df):,} แถว")
        confirm = st.checkbox("ยืนยันนำเข้าสินค้า", key="confirm_product_import")
        if st.button("นำเข้าสินค้า", disabled=not confirm or import_df.empty, use_container_width=True):
            records = []
            for _, row in import_df.iterrows():
                records.append(
                    {
                        "sku": clean(row["SKU"]),
                        "product_name": clean(row["สินค้า"]),
                        "product_group": clean(row["กลุ่มสินค้า"]),
                        "sort_order": int(sku_sort_value(row["SKU"])),
                        "is_active": True,
                        "created_by": clean(auth_user.get("email")),
                        "updated_by": clean(auth_user.get("email")),
                        "updated_at": now_iso(),
                    }
                )
            api_request(
                "POST",
                PRODUCT_OPTIONS_TABLE,
                params="?on_conflict=product_group,product_name",
                payload=records,
                prefer="resolution=merge-duplicates,return=minimal",
            )
            st.success(f"นำเข้าสินค้าแล้ว {len(records):,} แถว")
            st.cache_data.clear()
            st.rerun()


def render_product_row(row: dict, auth_user: dict) -> None:
    row_id = clean(row.get("id"))
    label = f"{clean(row.get('sku'))} {clean(row.get('product_name'))}".strip()
    cols = st.columns([0.45, 1.2, 1.5, 0.42, 0.5, 0.7, 0.9])
    sku = cols[0].text_input("SKU", value=clean(row.get("sku")), key=f"product_sku_{row_id}", label_visibility="collapsed")
    group = cols[1].text_input("กลุ่มสินค้า", value=clean(row.get("product_group")), key=f"product_group_{row_id}", label_visibility="collapsed")
    product = cols[2].text_input("สินค้า", value=clean(row.get("product_name")), key=f"product_name_{row_id}", label_visibility="collapsed")
    sort_order = cols[3].number_input(
        "ลำดับ",
        min_value=0,
        value=int(row.get("sort_order") or 0),
        step=1,
        key=f"product_sort_{row_id}",
        label_visibility="collapsed",
    )
    is_active = cols[4].checkbox("เปิด", value=bool(row.get("is_active")), key=f"product_active_{row_id}", label_visibility="collapsed")
    if cols[5].button("บันทึก", key=f"product_save_{row_id}", use_container_width=True):
        if not clean(group) or not clean(product):
            st.error("กรุณากรอกกลุ่มสินค้าและสินค้า")
            return
        api_request(
            "PATCH",
            PRODUCT_OPTIONS_TABLE,
            params=f"?id=eq.{quote(row_id)}",
            payload={
                "sku": normalize_sku(sku),
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
    confirm = cols[6].text_input(
        "พิมพ์ ลบ",
        key=f"product_delete_confirm_{row_id}",
        placeholder="พิมพ์ ลบ",
        label_visibility="collapsed",
    )
    if cols[6].button("ลบ", key=f"product_delete_{row_id}", use_container_width=True):
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


def normalize_sku(value) -> str:
    text = clean(value)
    if not text:
        return ""
    if text.endswith(".0") and text[:-2].isdigit():
        text = text[:-2]
    return text.zfill(3) if text.isdigit() and len(text) <= 3 else text


def sku_sort_value(value) -> int:
    text = normalize_sku(value)
    return int(text) if text.isdigit() else 999999


def build_xlsx_template(headers: list[str], sheet_name: str) -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        pd.DataFrame(columns=headers).to_excel(writer, index=False, sheet_name=sheet_name)
    return output.getvalue()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


main()
