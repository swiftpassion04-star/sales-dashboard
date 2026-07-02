from datetime import datetime, timezone

import pandas as pd
import streamlit as st

import neon_utils as neon
from auth_utils import require_login
from crm_data.products import (
    PRODUCT_PAGE_SIZE,
    bulk_update_product_active,
    fetch_product_delete_readiness,
    fetch_product_page,
)
from crm_theme import render_page_header
from nav_utils import render_sidebar_nav
from permissions import can_edit_products
from ui.pagination import render_pagination


st.set_page_config(page_title="สินค้า", layout="wide")

PRODUCT_STATUS_OPTIONS = {
    "สินค้าที่เปิดใช้งาน": "active",
    "สินค้าที่ปิดใช้งาน": "inactive",
    "สินค้าทั้งหมด": "all",
}
PRODUCT_SORT_OPTIONS = {
    "SP น้อยไปมาก": "sku_asc",
    "SP มากไปน้อย": "sku_desc",
    "เพิ่มเก่าสุด": "created_asc",
    "เพิ่มล่าสุด": "created_desc",
}
PRODUCT_SELECTION_KEY = "selected_product_ids"
PRODUCT_SELECTION_CONTEXT_KEY = "product_master_selection_context"
PRODUCT_SELECTION_WIDGET_PREFIX = "product_master_select_"
PRODUCT_BULK_ACTION_KEY = "product_master_bulk_action"
PRODUCT_BULK_CONFIRM_KEY = "product_master_bulk_confirm"
PRODUCT_BULK_CLEAR_PENDING_KEY = "product_master_bulk_clear_pending"
PRODUCT_BULK_SUCCESS_KEY = "product_master_bulk_success"
PRODUCT_DELETE_READINESS_KEY = "product_master_delete_readiness"
PRODUCT_DELETE_READINESS_SELECTION_KEY = "product_master_delete_readiness_selection"


def clear_product_delete_readiness() -> None:
    st.session_state.pop(PRODUCT_DELETE_READINESS_KEY, None)
    st.session_state.pop(PRODUCT_DELETE_READINESS_SELECTION_KEY, None)


def clear_product_selection() -> None:
    st.session_state[PRODUCT_SELECTION_KEY] = set()
    st.session_state.pop(PRODUCT_BULK_CONFIRM_KEY, None)
    clear_product_delete_readiness()
    for key in list(st.session_state):
        if str(key).startswith(PRODUCT_SELECTION_WIDGET_PREFIX):
            del st.session_state[key]


def sync_product_selection_context(context: tuple) -> None:
    if st.session_state.get(PRODUCT_SELECTION_CONTEXT_KEY) == context:
        return
    clear_product_selection()
    st.session_state[PRODUCT_SELECTION_CONTEXT_KEY] = context


def select_current_product_page(product_ids: list[str]) -> None:
    clear_product_selection()
    selected_ids = {product_id for product_id in product_ids if product_id}
    st.session_state[PRODUCT_SELECTION_KEY] = selected_ids
    for product_id in selected_ids:
        st.session_state[f"{PRODUCT_SELECTION_WIDGET_PREFIX}{product_id}"] = True


def update_product_selection(product_id: str, widget_key: str) -> None:
    selected_ids = set(st.session_state.get(PRODUCT_SELECTION_KEY, set()))
    if st.session_state.get(widget_key):
        selected_ids.add(product_id)
    else:
        selected_ids.discard(product_id)
    st.session_state[PRODUCT_SELECTION_KEY] = selected_ids
    st.session_state.pop(PRODUCT_BULK_CONFIRM_KEY, None)
    clear_product_delete_readiness()


def reset_product_bulk_confirmation() -> None:
    st.session_state.pop(PRODUCT_BULK_CONFIRM_KEY, None)


def selected_product_ids_for_bulk(
    selected_ids: set[str],
    page_product_ids: list[str],
) -> list[int]:
    normalized_selected_ids = {clean(product_id) for product_id in selected_ids if clean(product_id)}
    current_page_ids = {clean(product_id) for product_id in page_product_ids if clean(product_id)}
    if not normalized_selected_ids:
        return []
    if not normalized_selected_ids.issubset(current_page_ids):
        raise ValueError("รายการที่เลือกไม่ตรงกับหน้าปัจจุบัน กรุณาเลือกสินค้าใหม่")

    parsed_ids = []
    for product_id in sorted(normalized_selected_ids):
        if not product_id.isdigit() or int(product_id) <= 0:
            raise ValueError("รหัสสินค้าที่เลือกไม่ถูกต้อง กรุณาเลือกสินค้าใหม่")
        parsed_ids.append(int(product_id))
    return parsed_ids


def finalize_pending_product_bulk_action() -> None:
    if st.session_state.pop(PRODUCT_BULK_CLEAR_PENDING_KEY, False):
        clear_product_selection()
    success_message = st.session_state.pop(PRODUCT_BULK_SUCCESS_KEY, "")
    if success_message:
        st.success(success_message)


def reset_product_page() -> None:
    st.session_state.product_master_page = 1
    clear_product_selection()


def main() -> None:
    render_sidebar_nav()
    auth_user = require_login()
    is_editor = can_edit_products(auth_user)
    render_page_header("สินค้า", "Product Master สำหรับเลือกสินค้าในคำสั่งซื้อ")

    filter_col, sort_col = st.columns(2)
    status_label = filter_col.selectbox(
        "สถานะสินค้า",
        list(PRODUCT_STATUS_OPTIONS),
        key="product_master_status_filter",
        on_change=reset_product_page,
    )
    sort_label = sort_col.selectbox(
        "เรียงตาม",
        list(PRODUCT_SORT_OPTIONS),
        key="product_master_sort_mode",
        on_change=reset_product_page,
    )
    query = st.text_input(
        "ค้นหา SKU หรือชื่อสินค้า",
        key="product_master_search",
        on_change=reset_product_page,
    )
    page = max(int(st.session_state.get("product_master_page", 1)), 1)
    rows, total = fetch_product_page(
        status_filter=PRODUCT_STATUS_OPTIONS[status_label],
        sort_mode=PRODUCT_SORT_OPTIONS[sort_label],
        page=page,
        page_size=PRODUCT_PAGE_SIZE,
        search=query,
    )

    if is_editor:
        all_product_options = neon.fetch_product_options()
        render_create_product_form(auth_user)
        render_product_import(auth_user, all_product_options)
    else:
        st.info("บัญชีนี้ดูรายการสินค้าได้ แต่เพิ่ม/แก้ไข/ปิดใช้งานได้เฉพาะ EDITOR")

    _, page = render_pagination(
        total_rows=total,
        page_size=PRODUCT_PAGE_SIZE,
        current_page=page,
        key_prefix="product_master",
        page_size_options=[PRODUCT_PAGE_SIZE],
    )
    sync_product_selection_context(
        (
            page,
            PRODUCT_STATUS_OPTIONS[status_label],
            PRODUCT_SORT_OPTIONS[sort_label],
            clean(query).casefold(),
        )
    )
    finalize_pending_product_bulk_action()
    render_product_table(rows, auth_user, is_editor)


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
                st.warning("ถ้าเป็นกรณี SKU ใหม่แต่ชื่อสินค้า/กลุ่มสินค้าเดิม ให้รัน migration unique rule ใหม่ใน Neon ก่อน")
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
    page_product_ids = [clean(row.get("id")) for row in rows if clean(row.get("id"))]
    selected_ids = set(st.session_state.get(PRODUCT_SELECTION_KEY, set()))
    selected_on_page = selected_ids.intersection(page_product_ids)
    select_col, clear_col, summary_col = st.columns([1.4, 1.2, 3.4])
    select_col.button(
        "เลือกทั้งหมดในหน้านี้",
        key="product_master_select_current_page",
        on_click=select_current_product_page,
        args=(page_product_ids,),
        disabled=not page_product_ids,
        use_container_width=True,
    )
    clear_col.button(
        "ล้างรายการที่เลือก",
        key="product_master_clear_selection",
        on_click=clear_product_selection,
        disabled=not selected_ids,
        use_container_width=True,
    )
    summary_col.caption(f"เลือกแล้ว {len(selected_on_page):,} รายการในหน้านี้")
    render_product_bulk_actions(selected_ids, page_product_ids, auth_user, is_editor)
    render_product_delete_readiness(selected_ids, page_product_ids, is_editor)

    header = st.columns([0.55, 0.9, 2.5, 1.4, 0.7, 0.9, 0.9])
    header[0].markdown("**เลือก**")
    header[1].markdown("**SKU**")
    header[2].markdown("**ชื่อสินค้า**")
    header[3].markdown("**กลุ่มสินค้า**")
    header[4].markdown("**Active**")
    header[5].markdown("**บันทึก**")
    header[6].markdown("**ปิดใช้งาน**")

    for row in rows:
        render_product_row(row, auth_user, is_editor)


def render_product_bulk_actions(
    selected_ids: set[str],
    page_product_ids: list[str],
    auth_user: dict,
    is_editor: bool,
) -> None:
    if not is_editor or not selected_ids:
        return

    with st.container(border=True):
        st.markdown(f"**จัดการสินค้าที่เลือก {len(selected_ids):,} รายการ**")
        action = st.radio(
            "การดำเนินการ",
            options=["activate", "deactivate"],
            format_func=lambda value: "เปิดใช้งาน" if value == "activate" else "ปิดใช้งาน",
            horizontal=True,
            key=PRODUCT_BULK_ACTION_KEY,
            on_change=reset_product_bulk_confirmation,
        )
        is_activating = action == "activate"
        if not is_activating:
            st.warning(
                "สินค้าที่ปิดใช้งานจะไม่แสดงใน dropdown เพิ่มคำสั่งซื้อ / Follow-up popup"
            )

        action_label = "เปิดใช้งาน" if is_activating else "ปิดใช้งาน"
        confirmed = st.checkbox(
            f"ยืนยันการ{action_label}รายการที่เลือก {len(selected_ids):,} รายการ",
            key=PRODUCT_BULK_CONFIRM_KEY,
        )
        if not st.button(
            f"{action_label}รายการที่เลือก",
            key="product_master_bulk_submit",
            type="primary",
            disabled=not confirmed,
        ):
            return

        try:
            product_ids = selected_product_ids_for_bulk(selected_ids, page_product_ids)
            if not product_ids:
                st.error("กรุณาเลือกสินค้าอย่างน้อย 1 รายการ")
                return
            updated_count = bulk_update_product_active(
                product_ids,
                is_activating,
                clean(auth_user.get("email")) or None,
            )
        except ValueError as exc:
            st.error(str(exc))
            return
        except Exception as exc:
            st.error(f"อัปเดตสถานะสินค้าไม่สำเร็จ: {exc}")
            return

        st.session_state[PRODUCT_BULK_CLEAR_PENDING_KEY] = True
        st.session_state[PRODUCT_BULK_SUCCESS_KEY] = (
            f"{action_label}สินค้า {updated_count:,} รายการแล้ว"
        )
        st.rerun()


def render_product_delete_readiness(
    selected_ids: set[str],
    page_product_ids: list[str],
    is_editor: bool,
) -> None:
    if not is_editor or not selected_ids:
        return

    selection_signature = tuple(sorted(selected_ids))
    with st.container(border=True):
        st.markdown("**ตรวจสอบความพร้อมในการลบ**")
        st.caption(
            "ลบได้เฉพาะสินค้าที่ไม่เคยถูกใช้งานเท่านั้น "
            "สินค้าที่เคยถูกใช้ในออเดอร์/ข้อมูลขายจะไม่ถูกลบ ให้ปิดใช้งานแทน"
        )
        if st.button(
            "ตรวจสอบความพร้อมในการลบ",
            key="product_master_check_delete_readiness",
        ):
            try:
                product_ids = selected_product_ids_for_bulk(selected_ids, page_product_ids)
                readiness = fetch_product_delete_readiness(product_ids)
            except ValueError as exc:
                st.error(str(exc))
                clear_product_delete_readiness()
            else:
                st.session_state[PRODUCT_DELETE_READINESS_KEY] = readiness
                st.session_state[PRODUCT_DELETE_READINESS_SELECTION_KEY] = selection_signature

        readiness = st.session_state.get(PRODUCT_DELETE_READINESS_KEY, {})
        readiness_selection = st.session_state.get(PRODUCT_DELETE_READINESS_SELECTION_KEY)
        if not readiness or readiness_selection != selection_signature:
            st.info("กดตรวจสอบเพื่อดูผลการใช้งานของสินค้าที่เลือก")
            return

        status_labels = {
            "blocked_used": "ห้ามลบ: พบการใช้งาน",
            "tentative_no_usage": "ไม่พบการใช้งานเบื้องต้น: ยังไม่เปิดให้ลบจริง",
            "unsafe_unknown": "ห้ามลบ: ตรวจสอบไม่ครบ/ไม่ปลอดภัย",
        }
        reason_labels = {
            "usage_found": "พบการอ้างอิงในข้อมูลขายหรือออเดอร์",
            "no_usage_found_in_text_checks": "ไม่พบจาก text-based checks ที่ตรวจได้",
            "product_not_found": "ไม่พบสินค้าใน Product Master",
            "blank_sku_and_product_name": "SKU และชื่อสินค้าว่าง จึงตรวจสอบไม่ครบ",
        }
        display_rows = []
        for product_id in sorted(readiness):
            result = readiness[product_id]
            reason = str(result.get("reason") or "")
            if reason.startswith("usage_check_error:"):
                reason = "ตรวจสอบไม่สำเร็จ: " + reason.split(":", 1)[1]
            else:
                reason = reason_labels.get(reason, reason or "-")
            display_rows.append(
                {
                    "ID": result.get("product_id"),
                    "SKU": result.get("sku") or "-",
                    "สินค้า": result.get("product_name") or "-",
                    "สถานะ": status_labels.get(result.get("status"), "ห้ามลบ: ไม่ทราบสถานะ"),
                    "จำนวนการใช้งาน": int(result.get("usage_count") or 0),
                    "แหล่งการใช้งาน": ", ".join(result.get("usage_sources") or []) or "-",
                    "เหตุผล": reason,
                }
            )

        blocked_count = sum(
            result.get("status") == "blocked_used" for result in readiness.values()
        )
        tentative_count = sum(
            result.get("status") == "tentative_no_usage" for result in readiness.values()
        )
        unknown_count = sum(
            result.get("status") == "unsafe_unknown" for result in readiness.values()
        )
        summary_cols = st.columns(3)
        summary_cols[0].metric("พบการใช้งาน", blocked_count)
        summary_cols[1].metric("ไม่พบเบื้องต้น", tentative_count)
        summary_cols[2].metric("ตรวจสอบไม่ครบ", unknown_count)
        st.dataframe(pd.DataFrame(display_rows), hide_index=True, use_container_width=True)
        st.warning(
            "เพื่อความปลอดภัย ระบบยังไม่เปิดลบถาวร "
            "จนกว่าจะมี stable product reference/FK หรือ usage audit ครบถ้วน"
        )


def render_product_row(row: dict, auth_user: dict, is_editor: bool) -> None:
    row_id = clean(row.get("id"))
    cols = st.columns([0.55, 0.9, 2.5, 1.4, 0.7, 0.9, 0.9])
    if row_id:
        selection_widget_key = f"{PRODUCT_SELECTION_WIDGET_PREFIX}{row_id}"
        if selection_widget_key not in st.session_state:
            selected_ids = set(st.session_state.get(PRODUCT_SELECTION_KEY, set()))
            st.session_state[selection_widget_key] = row_id in selected_ids
        cols[0].checkbox(
            "เลือก",
            key=selection_widget_key,
            label_visibility="collapsed",
            on_change=update_product_selection,
            args=(row_id, selection_widget_key),
        )
    else:
        cols[0].write("-")
    if is_editor:
        sku = cols[1].text_input("SKU", value=clean(row.get("sku")), key=f"pm_sku_{row_id}", label_visibility="collapsed")
        product_name = cols[2].text_input(
            "ชื่อสินค้า",
            value=clean(row.get("product_name")),
            key=f"pm_name_{row_id}",
            label_visibility="collapsed",
        )
        product_group = cols[3].text_input(
            "กลุ่มสินค้า",
            value=clean(row.get("product_group")) or "ทั่วไป",
            key=f"pm_group_{row_id}",
            label_visibility="collapsed",
        )
        is_active = cols[4].checkbox(
            "Active",
            value=bool(row.get("is_active")),
            key=f"pm_active_{row_id}",
            label_visibility="collapsed",
        )
        if cols[5].button("บันทึก", key=f"pm_save_{row_id}", use_container_width=True):
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
        if cols[6].button("ปิดใช้งาน", key=f"pm_disable_{row_id}", disabled=not bool(row.get("is_active")), use_container_width=True):
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
        cols[1].write(clean(row.get("sku")) or "-")
        cols[2].write(clean(row.get("product_name")) or "-")
        cols[3].write(clean(row.get("product_group")) or "-")
        cols[4].write("เปิด" if row.get("is_active") else "ปิด")
        cols[5].write("-")
        cols[6].write("-")


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
