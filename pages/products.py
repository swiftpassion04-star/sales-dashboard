from datetime import datetime, timezone

import pandas as pd
import streamlit as st

import neon_utils as neon
from auth_utils import can_manage_all, require_login
from crm_theme import render_page_header
from nav_utils import render_sidebar_nav


st.set_page_config(page_title="สินค้า", layout="wide")


def main() -> None:
    render_sidebar_nav()
    auth_user = require_login()
    is_editor = can_manage_all(auth_user)
    render_page_header("สินค้า", "Product Master สำหรับเลือกสินค้าในคำสั่งซื้อ")

    rows = neon.fetch_product_options()
    query = st.text_input("ค้นหา SKU หรือชื่อสินค้า", key="product_master_search")
    filtered_rows = filter_products(rows, query)

    if is_editor:
        render_create_product_form(auth_user)
        render_product_import(auth_user, rows)
    else:
        st.info("บัญชีนี้ดูรายการสินค้าได้ แต่เพิ่ม/แก้ไข/ปิดใช้งานได้เฉพาะ EDITOR")

    render_product_table(filtered_rows, auth_user, is_editor)


def render_create_product_form(auth_user: dict) -> None:
    with st.form("product_master_create", clear_on_submit=True):
        c1, c2, c3 = st.columns([0.7, 1.8, 1.2])
        sku = c1.text_input("SKU")
        product_name = c2.text_input("ชื่อสินค้า")
        product_group = c3.text_input("กลุ่มสินค้า", value="ทั่วไป")
        submitted = st.form_submit_button("เพิ่มสินค้า", use_container_width=True)
    if not submitted:
        return
    if not clean(sku) or not clean(product_name):
        st.error("กรุณากรอก SKU และชื่อสินค้า")
        return
    neon.upsert_product_options(
        [
            {
                "sku": normalize_sku(sku),
                "product_group": clean(product_group) or "ทั่วไป",
                "product_name": clean(product_name),
                "sort_order": sku_sort_value(sku),
                "is_active": True,
                "created_by": clean(auth_user.get("email")),
                "updated_by": clean(auth_user.get("email")),
                "updated_at": now_iso(),
            }
        ]
    )
    st.cache_data.clear()
    st.success("เพิ่มสินค้าแล้ว")
    st.rerun()


def render_product_import(auth_user: dict, existing_rows: list[dict]) -> None:
    st.markdown('<div class="crm-section-title">นำเข้าสินค้าจาก Excel</div>', unsafe_allow_html=True)
    with st.container(border=True):
        st.caption("รองรับไฟล์ .xlsx โดยใช้คอลัมน์ A=SKU, B=ชื่อสินค้า, C=กลุ่มสินค้า")
        uploaded = st.file_uploader(
            "อัปโหลดไฟล์สินค้า .xlsx",
            type=["xlsx"],
            key="product_master_import_file",
        )
        if uploaded is None:
            st.info("อัปโหลดไฟล์เพื่อดู Preview ก่อนนำเข้า")
            return

        try:
            preview_rows, import_rows, summary = build_product_import_preview(uploaded, existing_rows, auth_user)
        except Exception as exc:
            st.error(f"อ่านไฟล์ไม่สำเร็จ: {exc}")
            return

        c1, c2, c3 = st.columns(3)
        c1.metric("ใหม่", f"{summary['new']:,}")
        c2.metric("ซ้ำ", f"{summary['duplicate']:,}")
        c3.metric("ข้อมูลไม่ครบ", f"{summary['invalid']:,}")

        st.dataframe(
            pd.DataFrame(preview_rows),
            hide_index=True,
            use_container_width=True,
        )

        disabled = summary["new"] <= 0
        if st.button("ยืนยันนำเข้าสินค้า", type="primary", use_container_width=True, disabled=disabled):
            try:
                neon.insert_product_options(import_rows)
            except Exception as exc:
                st.error(f"นำเข้าไม่สำเร็จ: {exc}")
                st.warning("ถ้าเป็นกรณี SKU ใหม่แต่ชื่อสินค้า/กลุ่มสินค้าเดิม อาจติด unique constraint เดิมของตารางสินค้า")
                return
            st.cache_data.clear()
            st.success(f"นำเข้าสินค้าใหม่ {len(import_rows):,} รายการแล้ว")
            st.rerun()


def build_product_import_preview(uploaded, existing_rows: list[dict], auth_user: dict) -> tuple[list[dict], list[dict], dict]:
    frame = pd.read_excel(uploaded, sheet_name=0, dtype=str, header=None)
    if frame.shape[1] < 3:
        raise ValueError("ไฟล์ต้องมีอย่างน้อย 3 คอลัมน์: SKU / ชื่อสินค้า / กลุ่มสินค้า")

    data = frame.iloc[:, :3].copy()
    data.columns = ["sku", "product_name", "product_group"]
    data["_excel_row_no"] = data.index + 1
    if not data.empty and is_product_header_row(data.iloc[0]):
        data = data.iloc[1:].reset_index(drop=True)

    existing_exact = {
        product_key(row.get("sku"), row.get("product_name"), row.get("product_group"))
        for row in existing_rows
    }
    existing_group_name = {
        (clean(row.get("product_group")).casefold(), clean(row.get("product_name")).casefold()): normalize_sku(row.get("sku"))
        for row in existing_rows
    }

    seen_in_file: set[tuple[str, str, str]] = set()
    preview_rows: list[dict] = []
    import_rows: list[dict] = []
    summary = {"new": 0, "duplicate": 0, "invalid": 0}

    for index, row in data.iterrows():
        sku = normalize_sku(row.get("sku"))
        product_name = clean(row.get("product_name"))
        product_group = clean(row.get("product_group"))
        row_no = int(row.get("_excel_row_no") or index + 1)
        key = product_key(sku, product_name, product_group)
        group_name_key = (product_group.casefold(), product_name.casefold())

        status = "ใหม่"
        reason = ""
        if not sku or not product_name or not product_group:
            status = "ข้อมูลไม่ครบ"
            reason = "ต้องมี SKU, ชื่อสินค้า, กลุ่มสินค้า"
            summary["invalid"] += 1
        elif key in existing_exact or key in seen_in_file:
            status = "ซ้ำ"
            reason = "SKU + ชื่อสินค้า + กลุ่มสินค้าตรงกันทั้งหมด"
            summary["duplicate"] += 1
        elif group_name_key in existing_group_name and existing_group_name[group_name_key] != sku:
            status = "ข้อมูลไม่ครบ"
            reason = "ชื่อสินค้า+กลุ่มสินค้านี้มีอยู่แล้ว แต่ SKU ต่างกัน; schema เดิมยังไม่รองรับ"
            summary["invalid"] += 1
        else:
            summary["new"] += 1
            import_rows.append(
                {
                    "sku": sku,
                    "product_group": product_group,
                    "product_name": product_name,
                    "sort_order": sku_sort_value(sku),
                    "is_active": True,
                    "created_by": clean(auth_user.get("email")),
                    "updated_by": clean(auth_user.get("email")),
                    "updated_at": now_iso(),
                }
            )

        if sku and product_name and product_group:
            seen_in_file.add(key)

        preview_rows.append(
            {
                "แถว": row_no,
                "SKU": sku or "-",
                "ชื่อสินค้า": product_name or "-",
                "กลุ่มสินค้า": product_group or "-",
                "สถานะ": status,
                "หมายเหตุ": reason or "-",
            }
        )

    return preview_rows, import_rows, summary


def render_product_table(rows: list[dict], auth_user: dict, is_editor: bool) -> None:
    if not rows:
        st.info("ยังไม่มีรายการสินค้า")
        return

    st.markdown('<div class="crm-section-title">รายการสินค้า</div>', unsafe_allow_html=True)
    header = st.columns([0.9, 2.5, 1.4, 0.7, 0.9, 0.9])
    header[0].markdown("**SKU**")
    header[1].markdown("**ชื่อสินค้า**")
    header[2].markdown("**กลุ่มสินค้า**")
    header[3].markdown("**Active**")
    header[4].markdown("**บันทึก**")
    header[5].markdown("**ปิดใช้งาน**")

    for row in rows:
        render_product_row(row, auth_user, is_editor)


def render_product_row(row: dict, auth_user: dict, is_editor: bool) -> None:
    row_id = clean(row.get("id"))
    cols = st.columns([0.9, 2.5, 1.4, 0.7, 0.9, 0.9])
    if is_editor:
        sku = cols[0].text_input("SKU", value=clean(row.get("sku")), key=f"pm_sku_{row_id}", label_visibility="collapsed")
        product_name = cols[1].text_input(
            "ชื่อสินค้า",
            value=clean(row.get("product_name")),
            key=f"pm_name_{row_id}",
            label_visibility="collapsed",
        )
        product_group = cols[2].text_input(
            "กลุ่มสินค้า",
            value=clean(row.get("product_group")) or "ทั่วไป",
            key=f"pm_group_{row_id}",
            label_visibility="collapsed",
        )
        is_active = cols[3].checkbox(
            "Active",
            value=bool(row.get("is_active")),
            key=f"pm_active_{row_id}",
            label_visibility="collapsed",
        )
        if cols[4].button("บันทึก", key=f"pm_save_{row_id}", use_container_width=True):
            if not clean(sku) or not clean(product_name):
                st.error("กรุณากรอก SKU และชื่อสินค้า")
                return
            neon.update_product_option(
                row_id,
                {
                    "sku": normalize_sku(sku),
                    "product_group": clean(product_group) or "ทั่วไป",
                    "product_name": clean(product_name),
                    "sort_order": sku_sort_value(sku),
                    "is_active": bool(is_active),
                    "updated_by": clean(auth_user.get("email")),
                    "updated_at": now_iso(),
                },
            )
            st.cache_data.clear()
            st.success("บันทึกสินค้าแล้ว")
            st.rerun()
        if cols[5].button("ปิดใช้งาน", key=f"pm_disable_{row_id}", disabled=not bool(row.get("is_active")), use_container_width=True):
            neon.update_product_option(
                row_id,
                {
                    "sku": normalize_sku(row.get("sku")),
                    "product_group": clean(row.get("product_group")) or "ทั่วไป",
                    "product_name": clean(row.get("product_name")),
                    "sort_order": int(row.get("sort_order") or 0),
                    "is_active": False,
                    "updated_by": clean(auth_user.get("email")),
                    "updated_at": now_iso(),
                },
            )
            st.cache_data.clear()
            st.success("ปิดใช้งานสินค้าแล้ว")
            st.rerun()
    else:
        cols[0].write(clean(row.get("sku")) or "-")
        cols[1].write(clean(row.get("product_name")) or "-")
        cols[2].write(clean(row.get("product_group")) or "-")
        cols[3].write("เปิด" if row.get("is_active") else "ปิด")
        cols[4].write("-")
        cols[5].write("-")


def filter_products(rows: list[dict], query: str) -> list[dict]:
    text = clean(query).casefold()
    if not text:
        return rows
    return [
        row
        for row in rows
        if text in clean(row.get("sku")).casefold()
        or text in clean(row.get("product_name")).casefold()
    ]


def clean(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and pd.isna(value):
        return ""
    return str(value).strip()


def normalize_sku(value) -> str:
    text = clean(value)
    if text.endswith(".0") and text[:-2].isdigit():
        text = text[:-2]
    return text.zfill(3) if text.isdigit() and len(text) <= 3 else text


def sku_sort_value(value) -> int:
    text = normalize_sku(value)
    return int(text) if text.isdigit() else 999999


def product_key(sku, product_name, product_group) -> tuple[str, str, str]:
    return (
        normalize_sku(sku).casefold(),
        clean(product_name).casefold(),
        clean(product_group).casefold(),
    )


def is_product_header_row(row) -> bool:
    values = [clean(row.get(column)).casefold() for column in ["sku", "product_name", "product_group"]]
    return values == ["sku", "ชื่อสินค้า", "กลุ่มสินค้า"]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


main()
