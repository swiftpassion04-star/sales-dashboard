import streamlit as st


st.set_page_config(page_title="Legacy page", layout="wide")
st.warning("หน้านี้เลิกใช้แล้ว กรุณาใช้หน้าใหม่: สินค้า")
st.page_link("pages/products.py", label="ไปหน้าสินค้า")
st.switch_page("pages/products.py")
st.stop()

from io import BytesIO
from datetime import datetime, timezone

import pandas as pd
import streamlit as st

from auth_utils import can_manage_all, require_login
from nav_utils import render_sidebar_nav
from neon_utils import (
    delete_product_option,
    fetch_product_options,
    update_product_option,
    upsert_product_options,
)


st.set_page_config(page_title="สินค้า", layout="wide")


def inject_css() -> None:
    st.markdown(
        """
<style>
:root {
  --crm-bg:#FFF8F0;
  --crm-border:#F3E4D2;
  --crm-border-strong:#FDBA74;
  --crm-text:#1F2937;
  --crm-accent:#F97316;
  --crm-accent-dark:#EA580C;
  --crm-shadow:0 2px 8px rgba(31,41,55,.04);
}
.stApp { background:var(--crm-bg); color:var(--crm-text); }
.block-container { max-width:1180px; padding-top:2.4rem; padding-bottom:3rem; }
section[data-testid="stSidebar"] {
  background:#FFF3E8 !important;
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
  background:#ffffff !important;
  border:1px solid var(--crm-border) !important;
  border-radius:18px !important;
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
  border-radius:12px !important;
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
  background:var(--crm-accent) !important;
  color:#ffffff !important;
}
[data-testid="stDataFrame"] {
  background:#ffffff !important;
  border:1px solid var(--crm-border) !important;
  border-radius:16px !important;
  box-shadow:var(--crm-shadow);
}
[data-testid="stExpander"] {
  background:#ffffff !important;
  border:1px solid var(--crm-border) !important;
  border-radius:16px !important;
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
[data-testid="stFileUploader"] section,
[data-testid="stFileUploaderDropzone"] {
  background:#FFFDF9 !important;
  border:1px dashed #fdba74 !important;
  border-radius:12px !important;
  color:var(--crm-text) !important;
}
[data-testid="stFileUploaderDropzone"] * {
  color:var(--crm-text) !important;
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
  background:var(--crm-accent) !important;
  color:#ffffff !important;
  border:1px solid var(--crm-accent-dark) !important;
}
[data-testid="stAlert"] * { color:#1F2937 !important; }
</style>
""",
        unsafe_allow_html=True,
    )


def main() -> None:
    inject_css()
    render_sidebar_nav()
    st.title("สินค้า")
    st.caption("จัดการตัวเลือกกลุ่มสินค้าและสินค้า สำหรับใช้ในหน้าเพิ่มข้อมูลลูกค้า")
    auth_user = require_login()
    if not can_manage_all(auth_user):
        st.warning("หน้านี้จัดการได้เฉพาะตำแหน่ง EDITOR เท่านั้น")
        st.stop()
    render_product_options(auth_user)


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
            upsert_product_options([payload])
            st.success("เพิ่ม/อัปเดตสินค้าแล้ว")
            st.cache_data.clear()
            st.rerun()

    render_product_import(auth_user)

    rows = fetch_product_options()
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
            upsert_product_options(records)
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
        update_product_option(
            row_id,
            {
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
        delete_product_option(row_id)
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
