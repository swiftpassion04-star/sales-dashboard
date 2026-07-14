from datetime import date
from math import isfinite

import streamlit as st

import neon_utils as neon
from ui.perf import perf_trace


PRODUCT_PLACEHOLDER = None
PRODUCT_PICKER_LIMIT = 10
PRODUCT_SELECTOR_PAGE_SIZE_OPTIONS = [10, 25, 50]


def parse_price_input(value: str) -> tuple[bool, float, str]:
    text = str(value or "").strip().replace(",", "")
    if not text:
        return True, 0.0, ""
    try:
        amount = float(text)
    except ValueError:
        return False, 0.0, "กรุณากรอกราคาเป็นตัวเลข เช่น 159, 159.50 หรือ 1,590"
    if not isfinite(amount) or amount < 0:
        return False, 0.0, "ราคาต้องเป็นตัวเลขตั้งแต่ 0 ขึ้นไป"
    return True, amount, ""


def render_manual_order_form(user: dict, is_editor: bool) -> None:
    with perf_trace("manual_order.render_form", role=user.get("role")):
        _render_manual_order_form(user, is_editor)


def _render_manual_order_form(user: dict, is_editor: bool) -> None:
    st.subheader("เพิ่มคำสั่งซื้อ")
    st.markdown(
        '<div class="crm-manual-meta">พนักงานเพิ่มคำสั่งซื้อได้ทีละรายการ ส่วนการนำเข้า Excel ใช้ได้เฉพาะ EDITOR</div>',
        unsafe_allow_html=True,
    )
    success_message = st.session_state.pop("manual_order_success_message", "")
    if success_message:
        st.success(success_message)
    if st.session_state.pop("manual_order_clear_requested", False):
        clear_manual_order_form_state()
    staff_options = []
    if is_editor:
        try:
            with perf_trace("manual_order.load_owner_options", role=user.get("role")):
                staff_options = neon.fetch_owner_user_options(active_only=True)
        except Exception as exc:
            st.warning(f"โหลดรายชื่อพนักงานไม่สำเร็จ: {exc}")
    try:
        with perf_trace("manual_order.load_product_options", role=user.get("role")):
            product_options = fetch_manual_product_options()
    except Exception as exc:
        product_options = []
        st.warning(f"โหลดรายการสินค้าไม่สำเร็จ: {exc}")

    with st.container(border=True):
        with st.form("manual_order_form", clear_on_submit=False, border=False):
            col1, col2 = st.columns(2)
            order_id = col1.text_input("หมายเลขคำสั่งซื้อ", key="manual_order_id")
            customer_name = col2.text_input("ชื่อลูกค้า", key="manual_customer_name")
            phone_col1, phone_col2 = st.columns(2)
            phone1 = phone_col1.text_input("เบอร์โทร", key="manual_phone1")
            phone2 = phone_col2.text_input("เบอร์สำรอง", key="manual_phone2")
            url = st.text_input("URL", key="manual_url")
            address = st.text_area("ที่อยู่", key="manual_address", height=90)
            sale_type = st.selectbox("ประเภทการขาย", ["NEW_ORDER", "UPSELL", "FOLLOW"], key="manual_sale_type")
            order_date = date.today().isoformat()
            st.caption(f"วันที่สร้างคำสั่งซื้อ: {order_date}")

            product_heading, product_action = st.columns([3.0, 1.0], vertical_alignment="center")
            product_heading.markdown("#### \u0e23\u0e32\u0e22\u0e01\u0e32\u0e23\u0e2a\u0e34\u0e19\u0e04\u0e49\u0e32")
            open_product_selector_submitted = product_action.form_submit_button(
                "+ \u0e40\u0e1e\u0e34\u0e48\u0e21\u0e2a\u0e34\u0e19\u0e04\u0e49\u0e32",
                use_container_width=True,
            )
            if st.session_state.pop("manual_product_reset_requested", False):
                st.session_state["manual_product_qty"] = 1
                st.session_state["manual_product_amount"] = ""
            selected_product = selected_manual_product(product_options)
            pc1, pc2, pc3, pc4 = st.columns([2.2, 0.6, 0.8, 1.1])
            with pc1:
                render_manual_selected_product(selected_product)
            selected_product_qty = pc2.number_input("\u0e08\u0e33\u0e19\u0e27\u0e19", min_value=1, value=1, step=1, key="manual_product_qty")
            selected_product_amount = pc3.text_input("\u0e23\u0e32\u0e04\u0e32", placeholder="\u0e01\u0e23\u0e2d\u0e01\u0e23\u0e32\u0e04\u0e32", key="manual_product_amount")
            add_product_submitted = pc4.form_submit_button("\u0e40\u0e1e\u0e34\u0e48\u0e21\u0e2a\u0e34\u0e19\u0e04\u0e49\u0e32\u0e2d\u0e35\u0e01 1 \u0e23\u0e32\u0e22\u0e01\u0e32\u0e23", use_container_width=True)
            delete_item_index = render_manual_order_items()

            owner = neon.clean(user.get("staff_name"))
            staff_code = neon.clean(user.get("staff_code"))
            if is_editor:
                staff_choices = build_staff_choices(staff_options)
                if staff_choices:
                    labels = ["เลือกผู้ดูแล", *[label for label, _row in staff_choices]]
                    selected_label = st.selectbox("ผู้ดูแล", labels, index=0, key="manual_owner_select")
                    if selected_label == "เลือกผู้ดูแล":
                        owner = ""
                        staff_code = ""
                    else:
                        selected_index = labels.index(selected_label) - 1
                        selected_staff = dict(staff_choices[selected_index][1])
                        owner = display_staff_name(selected_staff)
                        staff_code = normalize_staff_code(neon.clean(selected_staff.get("staff_code")))
                else:
                    owner = st.text_input("ผู้ดูแล", key="manual_owner_text")
                    staff_code = ""
            else:
                staff_code = normalize_staff_code(staff_code)
                owner = strip_duplicate_staff_suffix(owner or staff_code, staff_code)
                st.text_input("ผู้ดูแล", value=owner or "-", disabled=True, key="manual_owner_disabled")

            submitted = st.form_submit_button("บันทึกคำสั่งซื้อ", use_container_width=True)

    if open_product_selector_submitted:
        st.session_state["manual_product_selector_open"] = True
        st.rerun()

    render_manual_product_picker(product_options)

    if add_product_submitted:
        with perf_trace("manual_order.add_item", action="add_item", sale_type=sale_type):
            product = selected_manual_product(product_options)
            if not product:
                st.error("กรุณาเลือกสินค้า")
                return
            price_ok, parsed_amount, price_error = parse_price_input(selected_product_amount)
            if not price_ok:
                st.error(price_error)
                return
            item_amount = 0.0 if sale_type == "FOLLOW" else parsed_amount
            add_manual_order_item(product, int(selected_product_qty or 1), item_amount)
            st.session_state["manual_product_reset_requested"] = True
            with perf_trace("manual_order.rerun", action="add_item"):
                st.rerun()

    if delete_item_index is not None:
        remove_manual_order_item(delete_item_index)
        st.rerun()

    if not submitted:
        return

    errors = []
    if not neon.clean(order_id):
        errors.append("กรุณากรอกหมายเลขคำสั่งซื้อ")
    if not neon.clean(customer_name):
        errors.append("กรุณากรอกชื่อลูกค้า")
    errors.extend(neon.validate_phone_pair(phone1, phone2))
    manual_items = st.session_state.get("manual_order_items", [])
    if not manual_items:
        errors.append("กรุณาเลือกสินค้าอย่างน้อย 1 รายการ")
    if any(int(item.get("qty") or 0) <= 0 for item in manual_items):
        errors.append("จำนวนสินค้าต้องมากกว่า 0")
    if not owner:
        errors.append("กรุณาระบุผู้ดูแล")
    if not staff_code:
        errors.append("กรุณาระบุ staff_code ของผู้ดูแล")
    if errors:
        st.error(" / ".join(errors))
        return

    if not is_editor:
        owner_conflict = find_manual_order_owner_conflict(phone1, phone2, user, owner, staff_code)
        if owner_conflict:
            conflict_owner = neon.clean(owner_conflict.get("owner")) or neon.clean(owner_conflict.get("staff_code")) or "-"
            st.error(f"มีผู้ดูแลแล้ว: {conflict_owner}")
            return

    try:
        with perf_trace(
            "manual_order.save_order",
            action="save",
            count=len(manual_items),
            role=user.get("role"),
            sale_type=sale_type,
        ):
            result = neon.upsert_manual_order_items(
                {
                    "order_id": order_id,
                    "customer_name": customer_name,
                    "phone1": phone1,
                    "phone2": phone2,
                    "url": url,
                    "address": address,
                    "sale_type": sale_type,
                    "order_date": order_date,
                    "owner": owner,
                    "staff_code": staff_code,
                    "force_owner_update": bool(is_editor),
                    "uploaded_by": neon.clean(user.get("email")),
                    "updated_by": neon.clean(user.get("email")),
                },
                manual_items,
            )
    except Exception as exc:
        st.error(f"บันทึกคำสั่งซื้อไม่สำเร็จ: {exc}")
        return

    duplicate_lock_warning = neon.clean(result.get("duplicate_lock_warning"))
    if duplicate_lock_warning:
        st.warning(duplicate_lock_warning)
    actions = result.get("actions") or {}
    action_text = f"สินค้า {result.get('item_count', 0)} รายการ (เพิ่มใหม่ {actions.get('inserted', 0)}, อัปเดต {actions.get('updated', 0)})"
    with perf_trace("manual_order.clear_caches", action="save"):
        neon.clear_cached_data_functions(
            neon.fetch_followup_filter_options,
            neon.fetch_filter_options,
            neon.fetch_sales_report_owner_options,
            neon.fetch_crm_owner_options,
        )
    st.session_state.manual_order_success_message = f"บันทึกสำเร็จ: {action_text}"
    st.session_state.manual_order_clear_requested = True
    with perf_trace("manual_order.rerun", action="save"):
        st.rerun()


def staff_label(row: dict) -> str:
    name = display_staff_name(row)
    code = normalize_staff_code(neon.clean(row.get("staff_code")))
    if code and name.endswith(f"({code})"):
        return name
    return f"{name} ({code})" if code and code != name else name


def find_manual_order_owner_conflict(phone1: str, phone2: str, user: dict, owner: str, staff_code: str) -> dict:
    rows = neon.fetch_existing_owner_rows_by_phones(phone1, phone2)
    if not rows:
        return {}

    allowed_codes = {
        normalize_staff_code(neon.clean(value)).casefold()
        for value in [staff_code, user.get("staff_code")]
        if normalize_staff_code(neon.clean(value))
    }
    for row in rows:
        existing_code = normalize_staff_code(neon.clean(row.get("staff_code"))).casefold()
        if existing_code and existing_code in allowed_codes:
            continue
        return dict(row)
    return {}


def normalize_compare_text(value) -> str:
    return " ".join(neon.clean(value).split()).casefold()


def clear_manual_order_form_state() -> None:
    for key in (
        "manual_order_id",
        "manual_customer_name",
        "manual_phone1",
        "manual_phone2",
        "manual_product_name",
        "manual_url",
        "manual_address",
        "manual_owner_text",
    ):
        st.session_state[key] = ""
    st.session_state["manual_owner_select"] = "เลือกผู้ดูแล"
    st.session_state["manual_product_select"] = PRODUCT_PLACEHOLDER
    st.session_state["manual_selected_product"] = {}
    st.session_state["manual_selected_product_sku"] = ""
    st.session_state["manual_product_selector_open"] = False
    st.session_state["manual_product_selector_query"] = ""
    st.session_state["manual_product_selector_page"] = 1
    st.session_state["manual_product_selector_page_size"] = 10
    st.session_state["manual_product_selector_selected_product"] = {}
    st.session_state["manual_product_selector_selected_product_sku"] = ""
    st.session_state["manual_product_qty"] = 1
    st.session_state["manual_product_amount"] = ""
    st.session_state["manual_sale_type"] = "NEW_ORDER"
    st.session_state["manual_order_items"] = []
    st.session_state.pop("manual_owner_disabled", None)


def fetch_manual_product_options() -> list[dict]:
    return neon.fetch_order_product_options()


def manual_product_label(row: dict) -> str:
    return f"{neon.clean(row.get('sku'))} - {neon.clean(row.get('product_name'))}"


def manual_product_from_label(options: list[dict], label: str) -> dict:
    if not label:
        return {}
    for row in options:
        if manual_product_label(row) == label:
            return row
    return {}


def product_picker_search_text(product: dict) -> str:
    return " ".join(
        part
        for part in (
            neon.clean(product.get("sku")),
            neon.clean(product.get("product_name")),
            neon.clean(product.get("product_group")),
        )
        if part
    ).casefold()


def selected_product_key(product: dict) -> str:
    if not isinstance(product, dict):
        return ""
    sku = neon.clean(product.get("sku"))
    product_name = neon.clean(product.get("product_name"))
    return f"{sku}::{product_name}" if sku or product_name else ""


def filter_product_picker_options(products: list[dict], query: str, limit: int = PRODUCT_PICKER_LIMIT) -> list[dict]:
    limit = max(1, int(limit or PRODUCT_PICKER_LIMIT))
    tokens = [token.casefold() for token in neon.clean(query).split() if token]
    if not tokens:
        return []
    matches = []
    for product in products:
        if not selected_product_key(product):
            continue
        search_text = product_picker_search_text(product)
        if tokens and not all(token in search_text for token in tokens):
            continue
        matches.append(product)
        if len(matches) >= limit:
            break
    return matches


def filter_product_selector_options(products: list[dict], query: str) -> list[dict]:
    tokens = [token.casefold() for token in neon.clean(query).split() if token]
    if not tokens:
        return []
    matches = []
    for product in products:
        if not selected_product_key(product):
            continue
        search_text = product_picker_search_text(product)
        if all(token in search_text for token in tokens):
            matches.append(product)
    return matches


def normalize_product_selector_page_size(value) -> int:
    try:
        page_size = int(value)
    except (TypeError, ValueError):
        page_size = PRODUCT_SELECTOR_PAGE_SIZE_OPTIONS[0]
    if page_size not in PRODUCT_SELECTOR_PAGE_SIZE_OPTIONS:
        return PRODUCT_SELECTOR_PAGE_SIZE_OPTIONS[0]
    return page_size


def paginate_product_selector_options(products: list[dict], page: int, page_size: int) -> tuple[list[dict], int, int]:
    page_size = normalize_product_selector_page_size(page_size)
    total_pages = max(1, (len(products) + page_size - 1) // page_size)
    page = min(max(1, int(page or 1)), total_pages)
    start = (page - 1) * page_size
    return products[start : start + page_size], page, total_pages


def product_from_key(options: list[dict], key: str) -> dict:
    if not key:
        return {}
    for product in options:
        if selected_product_key(product) == key:
            return dict(product)
    return {}


def select_manual_product(product: dict) -> None:
    selected = dict(product)
    st.session_state["manual_selected_product"] = selected
    st.session_state["manual_selected_product_sku"] = neon.clean(selected.get("sku"))
    st.session_state["manual_product_selector_selected_product"] = selected
    st.session_state["manual_product_selector_selected_product_sku"] = neon.clean(selected.get("sku"))
    st.session_state["manual_product_picker_hide_results"] = True


def selected_manual_product(product_options: list[dict]) -> dict:
    selected = st.session_state.get("manual_selected_product")
    selected_key = selected_product_key(selected) if isinstance(selected, dict) else ""
    product = product_from_key(product_options, selected_key)
    if product:
        return product
    if selected_key:
        st.session_state["manual_selected_product"] = {}
        st.session_state["manual_selected_product_sku"] = ""
    return {}


def render_product_picker_thumbnail(container, product: dict, width: int = 48) -> None:
    image_url = selected_product_image_preview_url(product)
    if image_url:
        container.image(image_url, width=width)
    else:
        container.caption("\u0e44\u0e21\u0e48\u0e21\u0e35\u0e23\u0e39\u0e1b")


def render_manual_product_picker(product_options: list[dict]) -> None:
    if st.session_state.get("manual_product_selector_open"):
        render_manual_product_selector_dialog(product_options)


@st.dialog("\u0e40\u0e25\u0e37\u0e2d\u0e01\u0e2a\u0e34\u0e19\u0e04\u0e49\u0e32", width="large")
def render_manual_product_selector_dialog(product_options: list[dict]) -> None:
    st.caption("\u0e04\u0e49\u0e19\u0e2b\u0e32 SKU \u0e2b\u0e23\u0e37\u0e2d\u0e0a\u0e37\u0e48\u0e2d\u0e2a\u0e34\u0e19\u0e04\u0e49\u0e32 \u0e41\u0e25\u0e49\u0e27\u0e40\u0e25\u0e37\u0e2d\u0e01\u0e08\u0e32\u0e01\u0e15\u0e32\u0e23\u0e32\u0e07\u0e14\u0e49\u0e32\u0e19\u0e25\u0e48\u0e32\u0e07")
    query = st.text_input("\u0e04\u0e49\u0e19\u0e2b\u0e32 SKU / \u0e0a\u0e37\u0e48\u0e2d\u0e2a\u0e34\u0e19\u0e04\u0e49\u0e32", key="manual_product_selector_query")
    clean_query = neon.clean(query)
    previous_query = st.session_state.get("manual_product_selector_previous_query", "")
    if clean_query != previous_query:
        st.session_state["manual_product_selector_page"] = 1
        st.session_state["manual_product_selector_previous_query"] = clean_query

    page_size = st.selectbox(
        "\u0e08\u0e33\u0e19\u0e27\u0e19\u0e23\u0e32\u0e22\u0e01\u0e32\u0e23\u0e15\u0e48\u0e2d\u0e2b\u0e19\u0e49\u0e32",
        PRODUCT_SELECTOR_PAGE_SIZE_OPTIONS,
        key="manual_product_selector_page_size",
    )
    page_size = normalize_product_selector_page_size(page_size)

    if not clean_query:
        st.caption("\u0e1e\u0e34\u0e21\u0e1e\u0e4c SKU \u0e2b\u0e23\u0e37\u0e2d\u0e0a\u0e37\u0e48\u0e2d\u0e2a\u0e34\u0e19\u0e04\u0e49\u0e32\u0e40\u0e1e\u0e37\u0e48\u0e2d\u0e04\u0e49\u0e19\u0e2b\u0e32")
        if st.button("\u0e1b\u0e34\u0e14", key="manual_product_selector_close_empty"):
            st.session_state["manual_product_selector_open"] = False
            st.rerun()
        return

    matches = filter_product_selector_options(product_options, clean_query)
    if not matches:
        st.info("\u0e44\u0e21\u0e48\u0e1e\u0e1a\u0e2a\u0e34\u0e19\u0e04\u0e49\u0e32")
        if st.button("\u0e1b\u0e34\u0e14", key="manual_product_selector_close_no_result"):
            st.session_state["manual_product_selector_open"] = False
            st.rerun()
        return

    current_page = st.session_state.get("manual_product_selector_page", 1)
    page_items, page, total_pages = paginate_product_selector_options(matches, current_page, page_size)
    st.session_state["manual_product_selector_page"] = page
    st.caption(f"\u0e1e\u0e1a {len(matches):,} \u0e23\u0e32\u0e22\u0e01\u0e32\u0e23")

    header = st.columns([0.45, 0.75, 1.8, 1.0, 0.6])
    for col, label in zip(header, ["\u0e23\u0e39\u0e1b", "SKU", "\u0e2a\u0e34\u0e19\u0e04\u0e49\u0e32", "\u0e01\u0e25\u0e38\u0e48\u0e21", ""]):
        col.markdown(f"**{label}**")

    current_key = selected_product_key(st.session_state.get("manual_selected_product") or {})
    for index, product in enumerate(page_items):
        product_key = selected_product_key(product)
        cols = st.columns([0.45, 0.75, 1.8, 1.0, 0.6])
        render_product_picker_thumbnail(cols[0], product)
        cols[1].write(neon.clean(product.get("sku")) or "-")
        cols[2].write(neon.clean(product.get("product_name")) or "-")
        cols[3].write(neon.clean(product.get("product_group")) or "-")
        selected = product_key == current_key
        if cols[4].button(
            "\u0e40\u0e25\u0e37\u0e2d\u0e01\u0e41\u0e25\u0e49\u0e27" if selected else "\u0e40\u0e25\u0e37\u0e2d\u0e01",
            key=f"manual_product_selector_pick_{page}_{index}_{product_key}",
            disabled=selected,
            use_container_width=True,
        ):
            select_manual_product(product)
            st.session_state["manual_product_selector_open"] = False
            st.rerun()

    nav_prev, nav_status, nav_next, nav_close = st.columns([0.9, 1.4, 0.9, 0.9])
    if nav_prev.button("\u0e01\u0e48\u0e2d\u0e19\u0e2b\u0e19\u0e49\u0e32", key="manual_product_selector_prev", disabled=page <= 1, use_container_width=True):
        st.session_state["manual_product_selector_page"] = max(1, page - 1)
        st.rerun()
    nav_status.caption(f"\u0e2b\u0e19\u0e49\u0e32 {page} / {total_pages}")
    if nav_next.button("\u0e16\u0e31\u0e14\u0e44\u0e1b", key="manual_product_selector_next", disabled=page >= total_pages, use_container_width=True):
        st.session_state["manual_product_selector_page"] = min(total_pages, page + 1)
        st.rerun()
    if nav_close.button("\u0e1b\u0e34\u0e14", key="manual_product_selector_close", use_container_width=True):
        st.session_state["manual_product_selector_open"] = False
        st.rerun()


def render_manual_selected_product(product: dict) -> None:
    if not product:
        st.info("\u0e22\u0e31\u0e07\u0e44\u0e21\u0e48\u0e44\u0e14\u0e49\u0e40\u0e25\u0e37\u0e2d\u0e01\u0e2a\u0e34\u0e19\u0e04\u0e49\u0e32")
        return
    st.write(f"{neon.clean(product.get('sku'))} - {neon.clean(product.get('product_name'))}")
    product_group = neon.clean(product.get("product_group"))
    if product_group:
        st.caption(product_group)
    render_manual_product_preview(product)


def render_manual_product_preview(product: dict) -> None:
    image_url = selected_product_image_preview_url(product)
    if image_url:
        st.image(image_url, width=120)


def selected_product_image_preview_url(product: dict) -> str:
    preview_url = getattr(neon, "product_image_preview_url", None)
    if callable(preview_url):
        return preview_url(product)
    if not isinstance(product, dict):
        return ""
    image_url = neon.clean(product.get("image_url"))
    if image_url.lower().startswith(("http://", "https://")):
        return image_url
    return ""


def add_manual_order_item(product: dict, qty: int, amount: float) -> None:
    items = list(st.session_state.get("manual_order_items", []))
    sku = neon.clean(product.get("sku"))
    product_name = neon.clean(product.get("product_name"))
    qty = max(1, int(qty or 1))
    amount = max(0.0, float(amount or 0))
    image_url = neon.clean(product.get("image_url"))
    for item in items:
        if neon.clean(item.get("sku")) == sku and neon.clean(item.get("product_name")) == product_name:
            item["qty"] = int(item.get("qty") or 0) + qty
            item["amount"] = float(item.get("amount") or 0) + amount
            if image_url and not neon.clean(item.get("image_url")):
                item["image_url"] = image_url
            st.session_state["manual_order_items"] = items
            return
    items.append({"sku": sku, "product_name": product_name, "qty": qty, "amount": amount, "image_url": image_url})
    st.session_state["manual_order_items"] = items


def remove_manual_order_item(index: int) -> None:
    items = list(st.session_state.get("manual_order_items", []))
    if 0 <= index < len(items):
        items.pop(index)
    st.session_state["manual_order_items"] = items


def render_manual_order_item_preview(container, item: dict) -> None:
    image_url = selected_product_image_preview_url(item)
    if image_url:
        container.image(image_url, width=120)


def render_manual_order_items() -> int | None:
    items = st.session_state.setdefault("manual_order_items", [])
    if not items:
        st.info("ยังไม่มีรายการสินค้าในคำสั่งซื้อนี้")
        return None
    st.markdown("##### สินค้าที่เลือก")
    header = st.columns([0.8, 2.3, 0.6, 0.8, 0.6])
    header[0].markdown("**SKU**")
    header[1].markdown("**สินค้า**")
    header[2].markdown("**จำนวน**")
    header[3].markdown("**ราคา**")
    header[4].markdown("**ลบ**")
    delete_index = None
    for index, item in enumerate(items):
        cols = st.columns([0.8, 2.3, 0.6, 0.8, 0.6])
        cols[0].write(neon.clean(item.get("sku")) or "-")
        cols[1].write(neon.clean(item.get("product_name")) or "-")
        render_manual_order_item_preview(cols[1], item)
        cols[2].write(int(item.get("qty") or 0))
        cols[3].write(f"{float(item.get('amount') or 0):,.2f}")
        if cols[4].form_submit_button("ลบ", key=f"manual_item_delete_{index}", use_container_width=True):
            delete_index = index
    return delete_index


def build_staff_choices(rows: list[dict]) -> list[tuple[str, dict]]:
    choices = []
    seen = set()
    for row in rows:
        if not normalize_staff_code(neon.clean(row.get("staff_code"))):
            continue
        label = staff_label(row)
        key = label.casefold()
        if not label or key in seen:
            continue
        seen.add(key)
        choices.append((label, row))
    return choices


def display_staff_name(row: dict) -> str:
    name = neon.clean(row.get("staff_name"))
    code = normalize_staff_code(neon.clean(row.get("staff_code")))
    return strip_duplicate_staff_suffix(name, code)


def normalize_staff_code(value: str) -> str:
    text = neon.clean(value)
    if text.startswith("(") and text.endswith(")") and len(text) > 2:
        return text[1:-1].strip()
    return text


def strip_duplicate_staff_suffix(name: str, code: str) -> str:
    cleaned = neon.clean(name)
    normalized_code = normalize_staff_code(code)
    if not cleaned or not normalized_code:
        return cleaned
    duplicate_suffix = f"({normalized_code}) ({normalized_code})"
    if cleaned.endswith(duplicate_suffix):
        return cleaned[: -len(f" ({normalized_code})")].strip()
    return cleaned
