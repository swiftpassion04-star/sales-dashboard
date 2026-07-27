from datetime import date, timedelta
from html import escape

import streamlit as st

from auth_utils import current_user, require_login
from crm_data.daily_matrix import (
    CRM_TEAM_TOTAL_THRESHOLD,
    UPSELL_TEAM_TOTAL_THRESHOLD,
    classify_crm_cell_tone,
    classify_team_total_tone,
    classify_upsell_cell_tone,
    clear_day_status,
    clear_daily_matrix_caches,
    fetch_daily_matrix,
    fetch_day_statuses,
    save_day_status,
)
from crm_theme import render_page_header
from nav_utils import render_sidebar_nav
from permissions import can_manage_daily_status
from ui.daily_matrix_design import inject_daily_matrix_design


st.set_page_config(page_title="ยอดขายรายวัน", layout="wide")

_THAI_WEEKDAYS = [
    "วันจันทร์",
    "วันอังคาร",
    "วันพุธ",
    "วันพฤหัสบดี",
    "วันศุกร์",
    "วันเสาร์",
    "วันอาทิตย์",
]

_LEGEND_HTML = """
<div class="dm-legend">
  <span><span class="dm-legend-swatch" style="background:#FFF3CC;"></span>UPSELL รายบุคคล เกิน 3,000 บาท</span>
  <span><span class="dm-legend-swatch" style="background:#D6EAFF;"></span>UPSELL รายบุคคล เกิน 4,500 บาท</span>
  <span><span class="dm-legend-swatch" style="background:#E9F8EF;"></span>CRM รายบุคคล เกิน 11,000 บาท / ยอดรวมทีมถึงเป้า</span>
  <span><span class="dm-legend-swatch" style="background:#FDE4E4;"></span>วันหยุด / วันลา</span>
</div>
"""


def _thai_weekday(value: date) -> str:
    return _THAI_WEEKDAYS[value.weekday()]


def _thai_date_short(value: date) -> str:
    buddhist_year = value.year + 543
    return f"{value.day}/{value.month}/{buddhist_year % 100:02d}"


def _format_amount(value) -> str:
    return f"{float(value or 0):,.0f}"


def _month_all_dates(month_start: date, month_end_exclusive: date) -> list[date]:
    days = (month_end_exclusive - month_start).days
    return [month_start + timedelta(days=i) for i in range(days)]


def _build_matrix_html(matrix: dict, day_statuses: dict) -> str:
    month_start = matrix["month_start"]
    month_end = matrix["month_end_exclusive"]
    upsell = matrix["teams"]["UPSELL_TEAM"]
    crm = matrix["teams"]["CRM_TEAM"]
    upsell_cols = upsell["columns"]
    crm_cols = crm["columns"]

    total_data_cols = len(upsell_cols) + 1 + len(crm_cols) + 1 + 1

    header_group = (
        "<tr>"
        '<th rowspan="2" class="dm-col-date">วันที่</th>'
        f'<th colspan="{len(upsell_cols) + 1}" class="dm-group-upsell">ยอดขาย ทีมเสนอขาย UPSELL</th>'
        f'<th colspan="{len(crm_cols) + 1}" class="dm-group-crm">ยอดขายยา อาหารเสริม CRM</th>'
        '<th rowspan="2">ยอดรวมทั้งหมด</th>'
        "</tr>"
    )
    header_names = (
        "<tr>"
        + "".join(f"<th>{escape(col['staff_name'])}</th>" for col in upsell_cols)
        + '<th class="dm-col-total">ยอดรวมทีม</th>'
        + "".join(f"<th>{escape(col['staff_name'])}</th>" for col in crm_cols)
        + '<th class="dm-col-total">ยอดรวมทีม</th>'
        + "</tr>"
    )

    body_rows: list[str] = []
    footer_totals = [0.0] * total_data_cols

    for current in _month_all_dates(month_start, month_end):
        status_info = day_statuses.get(current)
        row_class = "dm-row-holiday" if status_info else ""
        upsell_day = upsell["days"].get(current, {"per_staff": {}, "team_total": 0.0})
        crm_day = crm["days"].get(current, {"per_staff": {}, "team_total": 0.0})

        cells: list[str] = []
        col_index = 0
        for col in upsell_cols:
            amount = upsell_day["per_staff"].get(col["staff_code"], 0.0)
            tone = "normal" if status_info else classify_upsell_cell_tone(amount)
            cells.append(f'<td class="dm-cell-{tone}">{_format_amount(amount)}</td>')
            footer_totals[col_index] += amount
            col_index += 1

        upsell_total = upsell_day["team_total"]
        upsell_total_tone = (
            "normal"
            if status_info
            else classify_team_total_tone(upsell_total, UPSELL_TEAM_TOTAL_THRESHOLD)
        )
        cells.append(
            f'<td class="dm-col-total dm-cell-{upsell_total_tone}">{_format_amount(upsell_total)}</td>'
        )
        footer_totals[col_index] += upsell_total
        col_index += 1

        for col in crm_cols:
            amount = crm_day["per_staff"].get(col["staff_code"], 0.0)
            tone = "normal" if status_info else classify_crm_cell_tone(amount)
            cells.append(f'<td class="dm-cell-{tone}">{_format_amount(amount)}</td>')
            footer_totals[col_index] += amount
            col_index += 1

        crm_total = crm_day["team_total"]
        crm_total_tone = (
            "normal"
            if status_info
            else classify_team_total_tone(crm_total, CRM_TEAM_TOTAL_THRESHOLD)
        )
        cells.append(
            f'<td class="dm-col-total dm-cell-{crm_total_tone}">{_format_amount(crm_total)}</td>'
        )
        footer_totals[col_index] += crm_total
        col_index += 1

        grand_total = upsell_total + crm_total
        cells.append(f'<td class="dm-col-total">{_format_amount(grand_total)}</td>')
        footer_totals[col_index] += grand_total
        col_index += 1

        date_label = f"{_thai_weekday(current)} {_thai_date_short(current)}"
        if status_info:
            status_label = "วันหยุด" if status_info["status"] == "HOLIDAY" else "วันลา"
            date_label += f" ({status_label})"

        body_rows.append(
            f'<tr class="{row_class}"><td class="dm-col-date">{escape(date_label)}</td>'
            + "".join(cells)
            + "</tr>"
        )

    footer_cells = "".join(f"<td>{_format_amount(value)}</td>" for value in footer_totals)
    footer_row = f'<tr><td class="dm-col-date">รวมทั้งเดือน</td>{footer_cells}</tr>'

    return (
        '<div class="dm-table-wrap"><table class="dm-table">'
        f"<thead>{header_group}{header_names}</thead>"
        f'<tbody>{"".join(body_rows)}</tbody>'
        f"<tfoot>{footer_row}</tfoot>"
        "</table></div>"
    )


def _render_day_status_manager(
    month_start: date,
    month_end_exclusive: date,
    day_statuses: dict,
    actor_email: str,
) -> None:
    with st.expander("จัดการวันหยุด / วันลา (EDITOR)", expanded=False):
        all_dates = _month_all_dates(month_start, month_end_exclusive)
        date_options = {
            f"{_thai_weekday(value)} {_thai_date_short(value)}": value for value in all_dates
        }

        with st.form("daily_matrix_mark_status_form"):
            form_cols = st.columns([2, 1, 1.4, 1])
            selected_labels = form_cols[0].multiselect("เลือกวันที่", list(date_options))
            status_label = form_cols[1].selectbox("สถานะ", ["วันหยุด", "วันลา"])
            note = form_cols[2].text_input("หมายเหตุ (ถ้ามี)", value="")
            submitted = form_cols[3].form_submit_button("บันทึก", use_container_width=True)

        if submitted:
            if not selected_labels:
                st.warning("กรุณาเลือกวันที่อย่างน้อย 1 วัน")
            else:
                status_value = "HOLIDAY" if status_label == "วันหยุด" else "LEAVE"
                try:
                    for label in selected_labels:
                        save_day_status(
                            status_date=date_options[label],
                            status=status_value,
                            note=note,
                            actor_email=actor_email,
                        )
                except Exception:
                    st.error("บันทึกสถานะวันที่ไม่สำเร็จ กรุณาลองใหม่อีกครั้ง")
                else:
                    clear_daily_matrix_caches()
                    st.session_state.daily_matrix_notice = f"บันทึกสถานะ {len(selected_labels)} วันแล้ว"
                    st.rerun()

        if not day_statuses:
            st.caption("ยังไม่มีวันที่ตั้งค่าเป็นวันหยุด/วันลาในเดือนนี้")
            return

        st.caption("วันที่ตั้งค่าแล้วในเดือนนี้")
        for status_date in sorted(day_statuses):
            info = day_statuses[status_date]
            label = "วันหยุด" if info["status"] == "HOLIDAY" else "วันลา"
            note_text = f" · {info['note']}" if info.get("note") else ""
            with st.form(f"daily_matrix_unmark_{status_date.isoformat()}"):
                row_cols = st.columns([3, 1])
                row_cols[0].markdown(
                    f"**{_thai_weekday(status_date)} {_thai_date_short(status_date)}** — {label}{note_text}"
                )
                unmark_submitted = row_cols[1].form_submit_button(
                    "ยกเลิก", use_container_width=True
                )

            if not unmark_submitted:
                continue
            try:
                clear_day_status(status_date=status_date, actor_email=actor_email)
            except Exception:
                st.error("ยกเลิกสถานะไม่สำเร็จ กรุณาลองใหม่อีกครั้ง")
            else:
                clear_daily_matrix_caches()
                st.rerun()


def main() -> None:
    render_sidebar_nav()
    auth_user = require_login()
    user = current_user() or auth_user or {}

    inject_daily_matrix_design()
    render_page_header(
        "📅ตารางยอดขายรายวัน",
        "ยอดขายรายวันต่อคน แยกทีม UPSELL และทีมยา อาหารเสริม CRM พร้อมไฮไลต์ตามเป้า",
    )

    notice = st.session_state.pop("daily_matrix_notice", "")
    if notice:
        st.success(notice)

    today = date.today()
    picked = st.date_input("เดือนที่ต้องการดู", value=today, key="daily_matrix_month_picker")
    year, month = picked.year, picked.month

    try:
        with st.spinner("กำลังโหลดยอดขายรายวัน..."):
            matrix = fetch_daily_matrix(year, month)
    except Exception:
        st.error("โหลดข้อมูลยอดขายรายวันไม่สำเร็จ กรุณาลองใหม่อีกครั้ง")
        return

    # Independent from the sales matrix on purpose: crm_daily_status is a
    # separate table that may not be migrated yet. A failure here must never
    # hide the (fully independent) sales figures above.
    try:
        day_statuses = fetch_day_statuses(year, month)
    except Exception:
        day_statuses = {}
        st.caption(
            "ยังไม่สามารถโหลดสถานะวันหยุด/วันลาได้ (อาจยังไม่ได้รัน migration "
            "crm_daily_status) — ตารางยอดขายด้านล่างยังแสดงผลได้ตามปกติ"
        )

    if matrix["ambiguous_staff_codes"]:
        st.warning(
            "พบ staff_code ที่ผูกกับผู้ใช้มากกว่า 1 บัญชี (เลือกบัญชีแรกตามลำดับตัวอักษรมาแสดงชั่วคราว "
            "กรุณาตรวจสอบข้อมูลผู้ใช้): " + ", ".join(matrix["ambiguous_staff_codes"])
        )
    unassigned_total = matrix["unassigned"]["total"]
    if unassigned_total > 0:
        st.info(
            f"มียอดขาย {unassigned_total:,.0f} บาท จาก staff_code ที่ยังไม่ถูกจัดทีม "
            "(ตั้งค่าทีมได้ที่หน้า ยอดขายทีม)"
        )

    st.markdown(_LEGEND_HTML, unsafe_allow_html=True)
    st.markdown(_build_matrix_html(matrix, day_statuses), unsafe_allow_html=True)

    if can_manage_daily_status(user):
        st.divider()
        _render_day_status_manager(
            matrix["month_start"],
            matrix["month_end_exclusive"],
            day_statuses,
            str(user.get("email") or ""),
        )


main()
