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


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


main()
