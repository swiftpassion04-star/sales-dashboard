from datetime import date, timedelta
from html import escape

import streamlit as st

from auth_utils import current_user, require_login
from crm_data.daily_matrix import (
    CRM_TEAM_TOTAL_THRESHOLD,
    UNASSIGNED_TEAM_CODE,
    UPSELL_TEAM_TOTAL_THRESHOLD,
    classify_crm_cell_tone,
    classify_team_total_tone,
    classify_upsell_cell_tone,
    clear_day_status,
    clear_daily_matrix_caches,
    fetch_daily_matrix,
    fetch_day_statuses,
    format_staff_display_name,
    resolve_cell_status_highlight,
    save_day_status,
)
from crm_theme import render_page_header
from nav_utils import render_sidebar_nav
from permissions import can_manage_daily_status
from ui.daily_matrix_design import inject_daily_matrix_design


st.set_page_config(page_title="ยอดขายรายวัน", layout="wide")

_THAI_WEEKDAYS = ["จ.", "อ.", "พ.", "พฤ.", "ศ.", "ส.", "อา."]

_LEGEND_HTML = """
<div class="dm-legend">
  <span><span class="dm-legend-swatch" style="background:#FFF3CC;"></span>UPSELL รายบุคคล เกิน 3,000 บาท</span>
  <span><span class="dm-legend-swatch" style="background:#D6EAFF;"></span>UPSELL รายบุคคล เกิน 4,500 บาท</span>
  <span><span class="dm-legend-swatch" style="background:#E9F8EF;"></span>CRM รายบุคคล เกิน 11,000 บาท / ยอดรวมทีมถึงเป้า</span>
  <span><span class="dm-legend-swatch" style="background:#FDE4E4;"></span>วันหยุด / วันลา (ทุกคน หรือ รายคน)</span>
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


def _column_header_cells(columns: list[dict]) -> str:
    return "".join(
        f'<th class="dm-col-staff" title="{escape(col["staff_name"] or col["staff_code"])}">'
        f"{escape(format_staff_display_name(col['staff_name'], col['staff_code']))}</th>"
        for col in columns
    )


def _day_bucket(team: dict, current: date) -> dict:
    return team["days"].get(current, {"per_staff": {}, "team_total": 0.0})


def _collect_staff_options(matrix: dict) -> list[dict]:
    """Union of every staff_code appearing as a column in any of the three
    blocks this month, deduped by staff_code, sorted by display name. Used
    to populate the STAFF-scope picker in the day-status manager."""
    seen: dict[str, dict] = {}
    for team_code in ("UPSELL_TEAM", "CRM_TEAM", UNASSIGNED_TEAM_CODE):
        for col in matrix["teams"][team_code]["columns"]:
            seen.setdefault(col["staff_code"], col)
    return sorted(
        seen.values(),
        key=lambda col: format_staff_display_name(col["staff_name"], col["staff_code"]),
    )


def _staff_cell_html(amount, tone: str, all_status, staff_statuses: dict, staff_code: str) -> str:
    extra_class = ""
    title_attr = ""
    personal_status = resolve_cell_status_highlight(all_status, staff_statuses, staff_code)
    if personal_status:
        extra_class = " dm-cell-personal-off"
        label = "วันหยุด" if personal_status["status"] == "HOLIDAY" else "วันลา"
        note = personal_status.get("note")
        title_text = label if not note else f"{label} · {note}"
        title_attr = f' title="{escape(title_text)}"'
    return f'<td class="dm-cell-{tone} dm-col-staff{extra_class}"{title_attr}>{_format_amount(amount)}</td>'


def _build_matrix_html(matrix: dict, day_statuses: dict) -> str:
    month_start = matrix["month_start"]
    month_end = matrix["month_end_exclusive"]
    upsell = matrix["teams"]["UPSELL_TEAM"]
    crm = matrix["teams"]["CRM_TEAM"]
    unassigned = matrix["teams"][UNASSIGNED_TEAM_CODE]
    upsell_cols = upsell["columns"]
    crm_cols = crm["columns"]
    unassigned_cols = unassigned["columns"]

    total_data_cols = len(upsell_cols) + 1 + len(crm_cols) + 1 + len(unassigned_cols) + 1 + 1

    header_group = (
        "<tr>"
        '<th rowspan="2" class="dm-col-date">วันที่</th>'
        f'<th colspan="{len(upsell_cols) + 1}" class="dm-group-upsell">ยอดขาย ทีมเสนอขาย UPSELL</th>'
        f'<th colspan="{len(crm_cols) + 1}" class="dm-group-crm">ยอดขายยา อาหารเสริม CRM</th>'
        f'<th colspan="{len(unassigned_cols) + 1}" class="dm-group-unassigned">{unassigned["team_name"]}</th>'
        '<th rowspan="2">ยอดรวมทั้งหมด</th>'
        "</tr>"
    )
    header_names = (
        "<tr>"
        + _column_header_cells(upsell_cols)
        + '<th class="dm-col-total">ยอดรวมทีม</th>'
        + _column_header_cells(crm_cols)
        + '<th class="dm-col-total">ยอดรวมทีม</th>'
        + _column_header_cells(unassigned_cols)
        + '<th class="dm-col-total">ยอดรวม</th>'
        + "</tr>"
    )

    body_rows: list[str] = []
    footer_totals = [0.0] * total_data_cols

    for current in _month_all_dates(month_start, month_end):
        day_info = day_statuses.get(current) or {}
        all_status = day_info.get("all")
        staff_statuses = day_info.get("staff") or {}
        row_class = "dm-row-holiday" if all_status else ""
        upsell_day = _day_bucket(upsell, current)
        crm_day = _day_bucket(crm, current)
        unassigned_day = _day_bucket(unassigned, current)

        cells: list[str] = []
        col_index = 0
        for col in upsell_cols:
            staff_code = col["staff_code"]
            amount = upsell_day["per_staff"].get(staff_code, 0.0)
            tone = "normal" if all_status else classify_upsell_cell_tone(amount)
            cells.append(_staff_cell_html(amount, tone, all_status, staff_statuses, staff_code))
            footer_totals[col_index] += amount
            col_index += 1

        upsell_total = upsell_day["team_total"]
        upsell_total_tone = (
            "normal"
            if all_status
            else classify_team_total_tone(upsell_total, UPSELL_TEAM_TOTAL_THRESHOLD)
        )
        cells.append(
            f'<td class="dm-col-total dm-cell-{upsell_total_tone}">{_format_amount(upsell_total)}</td>'
        )
        footer_totals[col_index] += upsell_total
        col_index += 1

        for col in crm_cols:
            staff_code = col["staff_code"]
            amount = crm_day["per_staff"].get(staff_code, 0.0)
            tone = "normal" if all_status else classify_crm_cell_tone(amount)
            cells.append(_staff_cell_html(amount, tone, all_status, staff_statuses, staff_code))
            footer_totals[col_index] += amount
            col_index += 1

        crm_total = crm_day["team_total"]
        crm_total_tone = (
            "normal"
            if all_status
            else classify_team_total_tone(crm_total, CRM_TEAM_TOTAL_THRESHOLD)
        )
        cells.append(
            f'<td class="dm-col-total dm-cell-{crm_total_tone}">{_format_amount(crm_total)}</td>'
        )
        footer_totals[col_index] += crm_total
        col_index += 1

        # No thresholds were specified for the unassigned block -- it's
        # informational (so attribution can be audited), never colored by
        # amount. It still supports the same ALL/STAFF status highlighting.
        for col in unassigned_cols:
            staff_code = col["staff_code"]
            amount = unassigned_day["per_staff"].get(staff_code, 0.0)
            cells.append(_staff_cell_html(amount, "normal", all_status, staff_statuses, staff_code))
            footer_totals[col_index] += amount
            col_index += 1

        unassigned_total = unassigned_day["team_total"]
        cells.append(
            f'<td class="dm-col-total dm-cell-normal">{_format_amount(unassigned_total)}</td>'
        )
        footer_totals[col_index] += unassigned_total
        col_index += 1

        grand_total = upsell_total + crm_total + unassigned_total
        cells.append(f'<td class="dm-col-total">{_format_amount(grand_total)}</td>')
        footer_totals[col_index] += grand_total
        col_index += 1

        # Only an ALL-scope status lengthens the date label (matches the
        # previous behavior exactly). A STAFF-scope status never does --
        # it's surfaced via the cell highlight + tooltip built above
        # instead, so the date column never grows unbounded with a list of
        # names.
        date_label = f"{_thai_weekday(current)} {_thai_date_short(current)}"
        if all_status:
            status_label = "วันหยุด" if all_status["status"] == "HOLIDAY" else "วันลา"
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
    staff_options: list[dict],
    actor_email: str,
) -> None:
    with st.expander("จัดการวันหยุด / วันลา (EDITOR)", expanded=False):
        all_dates = _month_all_dates(month_start, month_end_exclusive)
        date_options = {
            f"{_thai_weekday(value)} {_thai_date_short(value)}": value for value in all_dates
        }
        # "ชื่อย่อ (staff_code)" -- the short nickname alone isn't guaranteed
        # unique across staff, so the code disambiguates the picker.
        staff_label_options = {
            f"{format_staff_display_name(opt['staff_name'], opt['staff_code'])} ({opt['staff_code']})": opt[
                "staff_code"
            ]
            for opt in staff_options
        }
        staff_display_lookup = {
            opt["staff_code"]: format_staff_display_name(opt["staff_name"], opt["staff_code"])
            for opt in staff_options
        }

        with st.form("daily_matrix_mark_status_form"):
            row1 = st.columns([2, 1.2, 1])
            selected_date_labels = row1[0].multiselect("เลือกวันที่", list(date_options))
            scope_label = row1[1].selectbox("ขอบเขต", ["ทุกคน", "รายคน"])
            status_label = row1[2].selectbox("สถานะ", ["วันหยุด", "วันลา"])
            row2 = st.columns([2.3, 2])
            selected_staff_labels = row2[0].multiselect(
                "เลือกพนักงาน (ใช้เฉพาะขอบเขต 'รายคน')", list(staff_label_options)
            )
            note = row2[1].text_input("หมายเหตุ (ถ้ามี)", value="")
            submitted = st.form_submit_button("บันทึก", use_container_width=True)

        if submitted:
            if not selected_date_labels:
                st.warning("กรุณาเลือกวันที่อย่างน้อย 1 วัน")
            elif scope_label == "ทุกคน" and selected_staff_labels:
                st.warning(
                    "ขอบเขต 'ทุกคน' ไม่ต้องเลือกพนักงาน กรุณาล้างรายชื่อพนักงานหรือเปลี่ยนขอบเขตเป็น 'รายคน'"
                )
            elif scope_label == "รายคน" and not selected_staff_labels:
                st.warning("กรุณาเลือกพนักงานอย่างน้อย 1 คนสำหรับขอบเขต 'รายคน'")
            else:
                status_value = "HOLIDAY" if status_label == "วันหยุด" else "LEAVE"
                scope_value = "ALL" if scope_label == "ทุกคน" else "STAFF"
                saved_count = 0
                try:
                    for date_label in selected_date_labels:
                        status_date = date_options[date_label]
                        if scope_value == "ALL":
                            save_day_status(
                                status_date=status_date,
                                status=status_value,
                                scope_type="ALL",
                                note=note,
                                actor_email=actor_email,
                            )
                            saved_count += 1
                        else:
                            for staff_label in selected_staff_labels:
                                save_day_status(
                                    status_date=status_date,
                                    status=status_value,
                                    scope_type="STAFF",
                                    staff_code=staff_label_options[staff_label],
                                    note=note,
                                    actor_email=actor_email,
                                )
                                saved_count += 1
                except Exception:
                    st.error("บันทึกสถานะไม่สำเร็จ กรุณาลองใหม่อีกครั้ง")
                else:
                    clear_daily_matrix_caches()
                    st.session_state.daily_matrix_notice = f"บันทึกสถานะ {saved_count} รายการแล้ว"
                    st.rerun()

        has_any_status = any(info.get("all") or info.get("staff") for info in day_statuses.values())
        if not has_any_status:
            st.caption("ยังไม่มีวันที่ตั้งค่าเป็นวันหยุด/วันลาในเดือนนี้")
            return

        st.caption("วันที่ตั้งค่าแล้วในเดือนนี้")
        for status_date in sorted(day_statuses):
            info = day_statuses[status_date]

            if info.get("all"):
                all_info = info["all"]
                label = "วันหยุด" if all_info["status"] == "HOLIDAY" else "วันลา"
                note_text = f" · {all_info['note']}" if all_info.get("note") else ""
                with st.form(f"daily_matrix_unmark_all_{status_date.isoformat()}"):
                    row_cols = st.columns([3, 1])
                    row_cols[0].markdown(
                        f"**{_thai_weekday(status_date)} {_thai_date_short(status_date)}** "
                        f"— ทุกคน — {label}{note_text}"
                    )
                    unmark_submitted = row_cols[1].form_submit_button(
                        "ยกเลิก", use_container_width=True, key=f"unmark_all_btn_{status_date.isoformat()}"
                    )
                if unmark_submitted:
                    try:
                        clear_day_status(status_date=status_date, scope_type="ALL", actor_email=actor_email)
                    except Exception:
                        st.error("ยกเลิกสถานะไม่สำเร็จ กรุณาลองใหม่อีกครั้ง")
                    else:
                        clear_daily_matrix_caches()
                        st.rerun()

            for staff_code, staff_info in sorted(info.get("staff", {}).items()):
                label = "วันหยุด" if staff_info["status"] == "HOLIDAY" else "วันลา"
                note_text = f" · {staff_info['note']}" if staff_info.get("note") else ""
                display_name = staff_display_lookup.get(staff_code, staff_code)
                with st.form(f"daily_matrix_unmark_staff_{status_date.isoformat()}_{staff_code}"):
                    row_cols = st.columns([3, 1])
                    row_cols[0].markdown(
                        f"**{_thai_weekday(status_date)} {_thai_date_short(status_date)}** "
                        f"— {escape(display_name)} — {label}{note_text}"
                    )
                    unmark_submitted = row_cols[1].form_submit_button(
                        "ยกเลิก",
                        use_container_width=True,
                        key=f"unmark_staff_btn_{status_date.isoformat()}_{staff_code}",
                    )
                if unmark_submitted:
                    try:
                        clear_day_status(
                            status_date=status_date,
                            scope_type="STAFF",
                            staff_code=staff_code,
                            actor_email=actor_email,
                        )
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
            _collect_staff_options(matrix),
            str(user.get("email") or ""),
        )


main()
