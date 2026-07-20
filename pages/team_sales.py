from datetime import date, datetime
from html import escape

import streamlit as st

from auth_utils import current_user, require_login
from crm_data.team_sales import (
    clear_team_sales_caches,
    clear_user_team_assignment,
    fetch_team_assignment_users,
    fetch_team_sales_fingerprint,
    fetch_team_sales_summary,
    fetch_team_top_products,
    save_user_team_assignment,
)
from crm_data.common import BANGKOK_TZ
from crm_theme import render_page_header
from nav_utils import render_sidebar_nav
from permissions import ROLE_EDITOR, user_role
from ui.design_system import inject_crm_design_system


TEAM_OPTIONS = {
    "ทั้งหมด": None,
    "CRM Team": "CRM_TEAM",
    "Upsell Team": "UPSELL_TEAM",
}
SALE_TYPE_OPTIONS = {
    "ทั้งหมด": None,
    "NEW_ORDER": "NEW_ORDER",
    "UPSELL": "UPSELL",
}
ASSIGNMENT_OPTIONS = {
    "ยังไม่เลือกทีม": None,
    "CRM Team": "CRM_TEAM",
    "Upsell Team": "UPSELL_TEAM",
}
AUTO_REFRESH_INTERVAL_SECONDS = 15
TEAM_SALES_FINGERPRINT_PREFIX = "team_sales_fingerprint::"


st.set_page_config(page_title="ยอดขายทีม", layout="wide")


def _format_money(value) -> str:
    return f"฿{float(value or 0):,.2f}"


def _team_rows_by_code(summary: dict) -> dict[str, dict]:
    return {
        str(item.get("team_code") or ""): item
        for item in summary.get("teams", [])
    }


def _team_sales_fingerprint_state_key(
    start_date: date,
    end_date: date,
    sale_type_filter: str | None,
    team_code_filter: str | None,
) -> str:
    sale_key = str(sale_type_filter or "ALL")
    team_key = str(team_code_filter or "ALL")
    return (
        f"{TEAM_SALES_FINGERPRINT_PREFIX}{start_date.isoformat()}::"
        f"{end_date.isoformat()}::{sale_key}::{team_key}"
    )


def _clear_team_sales_fingerprint_state() -> None:
    for key in list(st.session_state):
        if str(key).startswith(TEAM_SALES_FINGERPRINT_PREFIX):
            del st.session_state[key]


def _render_team_card(team: dict, card_key: str) -> None:
    team_code = card_key.lower()
    with st.container(border=True, key=f"team_sales_team_card_{team_code}"):
        st.subheader(str(team.get("team_name") or "-"))
        metrics = st.columns([0.9, 1.65, 0.9])
        metrics[0].metric("จำนวนออเดอร์", f"{int(team.get('order_count') or 0):,}")
        metrics[1].metric("ยอดขายรวม", _format_money(team.get("sales_amount")))
        metrics[2].metric("จำนวนรายการ", f"{int(team.get('row_count') or 0):,}")


def _render_top_products(rows: list[dict]) -> None:
    st.subheader("Top 10 สินค้าขายดี")
    st.caption("เรียงตามจำนวนสินค้าที่ขายได้")
    if not rows:
        st.info("ยังไม่มีข้อมูลสินค้าขายดีในทีม เพราะยังไม่ได้จัด User เข้าทีม")
        return

    table_rows = []
    for rank, row in enumerate(rows, start=1):
        table_rows.append(
            "<tr>"
            f'<td class="crm-table-number">{rank}</td>'
            f'<td class="crm-table-sku">{escape(str(row.get("sku") or "-"))}</td>'
            f'<td class="crm-table-product">{escape(str(row.get("product_name") or "-"))}</td>'
            f'<td class="crm-table-number">{float(row.get("total_quantity") or 0):,.2f}</td>'
            f'<td class="crm-table-number">{int(row.get("order_count") or 0):,}</td>'
            "</tr>"
        )
    st.markdown(
        """
<div class="crm-top-products-table-wrap">
  <table class="crm-top-products-table">
    <colgroup>
      <col class="crm-col-rank">
      <col class="crm-col-sku">
      <col class="crm-col-product">
      <col class="crm-col-quantity">
      <col class="crm-col-orders">
    </colgroup>
    <thead>
      <tr>
        <th class="crm-table-number">อันดับ</th>
        <th class="crm-table-sku">SKU</th>
        <th class="crm-table-product">สินค้า</th>
        <th class="crm-table-number">จำนวนขาย</th>
        <th class="crm-table-number">ออเดอร์</th>
      </tr>
    </thead>
    <tbody>
"""
        + "".join(table_rows)
        + """
    </tbody>
  </table>
</div>
""",
        unsafe_allow_html=True,
    )


def _render_assignment_users(users: list[dict], actor_email: str) -> None:
    st.subheader("ตั้งค่าทีม User")
    if not users:
        st.info("ยังไม่พบ User ที่เปิดใช้งาน")
        return

    st.caption("เลือกทีมแล้วบันทึกทีละ User การเปลี่ยนทีมจะเริ่มมีผลตั้งแต่เวลาที่บันทึก")
    option_labels = list(ASSIGNMENT_OPTIONS)
    for row in users:
        email = str(row.get("email") or "").strip().lower()
        if not email:
            continue
        current_team_code = row.get("current_team_code")
        current_label = next(
            (
                label
                for label, code in ASSIGNMENT_OPTIONS.items()
                if code == current_team_code
            ),
            "ยังไม่เลือกทีม",
        )
        with st.form(f"team_assignment_{email}"):
            info_col, role_col, team_col, action_col = st.columns([2.2, 1, 1.4, 1])
            info_col.markdown(f"**{row.get('staff_name') or '-'}**")
            info_col.caption(email)
            role_col.markdown("**Role**")
            role_col.caption(str(row.get("role") or "-"))
            selected_label = team_col.selectbox(
                "ทีม",
                option_labels,
                index=option_labels.index(current_label),
                key=f"team_assignment_select_{email}",
            )
            submitted = action_col.form_submit_button(
                "บันทึก",
                use_container_width=True,
            )

        if not submitted:
            continue
        try:
            selected_team_code = ASSIGNMENT_OPTIONS[selected_label]
            if selected_team_code is None:
                result = clear_user_team_assignment(
                    user_email=email,
                    actor_email=actor_email,
                )
            else:
                result = save_user_team_assignment(
                    user_email=email,
                    team_code=selected_team_code,
                    actor_email=actor_email,
                )
        except Exception:
            st.error(f"บันทึกทีมของ {email} ไม่สำเร็จ กรุณาลองใหม่อีกครั้ง")
            continue

        if result.get("changed"):
            st.session_state.team_assignment_notice = f"บันทึกทีมของ {email} แล้ว"
            clear_team_sales_caches()
            _clear_team_sales_fingerprint_state()
        else:
            st.session_state.team_assignment_notice = f"ทีมของ {email} ไม่มีการเปลี่ยนแปลง"
        st.rerun()


def _render_team_sales_once(
    start_date: date,
    end_date: date,
    sale_type_filter: str | None,
    team_code_filter: str | None,
    *,
    auto_refresh: bool,
) -> None:
    try:
        with st.spinner("กำลังโหลดยอดขายทีมจาก Neon..."):
            summary = fetch_team_sales_summary(
                start_date,
                end_date,
                sale_type_filter=sale_type_filter,
            )
            top_products = fetch_team_top_products(
                start_date,
                end_date,
                team_code=team_code_filter,
                sale_type_filter=sale_type_filter,
                limit=10,
            )
    except Exception:
        st.error("โหลดข้อมูลยอดขายทีมไม่สำเร็จ กรุณาลองใหม่อีกครั้ง")
        return

    refresh_label = (
        f"อัปเดตอัตโนมัติทุก {AUTO_REFRESH_INTERVAL_SECONDS} วินาที"
        if auto_refresh
        else "ปิดการอัปเดตอัตโนมัติ"
    )
    updated_at = datetime.now(BANGKOK_TZ).strftime("%H:%M:%S")
    st.caption(f"{refresh_label} · อัปเดตล่าสุด: {updated_at}")

    summary_col, products_col = st.columns([1.12, 1], gap="large")
    with summary_col:
        with st.container(key="team_sales_summary_panel"):
            st.subheader("ยอดรวมระดับทีม")
            teams_by_code = _team_rows_by_code(summary)
            visible_codes = [team_code_filter] if team_code_filter else list(TEAM_OPTIONS.values())[1:]
            for team_code in visible_codes:
                _render_team_card(teams_by_code.get(team_code, {}), team_code)

            unassigned = summary.get("unassigned") or {}
            if int(unassigned.get("row_count") or 0) > 0:
                st.warning(
                    "ยังมีรายการที่ยังไม่ถูกจัดทีม: "
                    f"{int(unassigned.get('row_count') or 0):,} รายการ / "
                    f"{int(unassigned.get('order_count') or 0):,} ออเดอร์"
                )

    with products_col:
        with st.container(key="team_sales_top_products"):
            _render_top_products(top_products)


@st.fragment(run_every=AUTO_REFRESH_INTERVAL_SECONDS)
def _poll_team_sales_changes(
    start_date: date,
    end_date: date,
    sale_type_filter: str | None,
    team_code_filter: str | None,
) -> None:
    state_key = _team_sales_fingerprint_state_key(
        start_date,
        end_date,
        sale_type_filter,
        team_code_filter,
    )
    try:
        current_fingerprint = fetch_team_sales_fingerprint(
            start_date,
            end_date,
            sale_type_filter=sale_type_filter,
        )
    except Exception:
        return

    if state_key not in st.session_state:
        st.session_state[state_key] = current_fingerprint
        return
    if st.session_state[state_key] != current_fingerprint:
        st.session_state[state_key] = current_fingerprint
        clear_team_sales_caches()
        st.rerun()


def main() -> None:
    render_sidebar_nav()
    auth_user = require_login()
    user = current_user() or auth_user or {}
    if user_role(user) != ROLE_EDITOR:
        st.warning("คุณไม่มีสิทธิ์เข้าดูหน้ายอดขายทีม")
        st.stop()

    inject_crm_design_system()
    render_page_header(
        "🎖️ยอดขายทีม",
        "แสดงยอดรวมคำสั่งซื้อที่เพิ่ม แยกตามทีม",
    )
    assignment_notice = st.session_state.pop("team_assignment_notice", "")
    if assignment_notice:
        st.success(assignment_notice)

    today = date.today()
    month_start = today.replace(day=1)
    with st.container(key="team_sales_filter_panel"):
        filter_cols = st.columns([1, 1, 1, 1])
        start_date = filter_cols[0].date_input(
            "วันที่เริ่มต้น",
            value=month_start,
            key="team_sales_start_date",
        )
        end_date = filter_cols[1].date_input(
            "วันที่สิ้นสุด",
            value=today,
            key="team_sales_end_date",
        )
        sale_type_label = filter_cols[2].selectbox(
            "ประเภทออเดอร์",
            list(SALE_TYPE_OPTIONS),
            key="team_sales_sale_type",
        )
        team_label = filter_cols[3].selectbox(
            "ทีม",
            list(TEAM_OPTIONS),
            key="team_sales_team",
        )

    if start_date > end_date:
        st.warning("วันที่เริ่มต้นต้องไม่มากกว่าวันที่สิ้นสุด")
        return

    sale_type_filter = SALE_TYPE_OPTIONS[sale_type_label]
    team_code_filter = TEAM_OPTIONS[team_label]
    refresh_col, auto_refresh_col = st.columns([1, 3], vertical_alignment="center")
    manual_refresh = refresh_col.button(
        "รีเฟรชข้อมูล",
        key="team_sales_manual_refresh",
        use_container_width=True,
    )
    auto_refresh = auto_refresh_col.toggle(
        "เปิดอัปเดตอัตโนมัติ",
        value=True,
        key="team_sales_auto_refresh",
        help="ตรวจสอบการเปลี่ยนแปลงทุก 15 วินาที และอัปเดตเมื่อข้อมูลเปลี่ยน",
    )

    if manual_refresh:
        clear_team_sales_caches()
        _clear_team_sales_fingerprint_state()
        st.rerun()

    _render_team_sales_once(
        start_date,
        end_date,
        sale_type_filter,
        team_code_filter,
        auto_refresh=auto_refresh,
    )
    if auto_refresh:
        _poll_team_sales_changes(
            start_date,
            end_date,
            sale_type_filter,
            team_code_filter,
        )

    try:
        with st.spinner("กำลังโหลดรายชื่อ User..."):
            users = fetch_team_assignment_users()
    except Exception:
        st.error("โหลดข้อมูลยอดขายทีมไม่สำเร็จ กรุณาลองใหม่อีกครั้ง")
        return

    st.divider()
    with st.container(key="team_sales_assignment_panel"):
        _render_assignment_users(users, str(user.get("email") or ""))


main()
