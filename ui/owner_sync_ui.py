"""Update customer owners from an edited copy of the customer export.

The file is the export this app produces: edit "พนักงานดูแล", upload it back,
and the matching customers change hands. It never adds or removes an order --
only the owner of rows that already exist is rewritten, and only on the CRM
side, so the Upsell side of a shared customer is left alone.

Rows are matched by phone number. A row is considered only when its "ทีม"
column says CRM Team; anything else in the file is ignored. An owner name the
app does not know, a blank one, or two different owners for the same phone is
skipped and reported rather than guessed at.
"""

from __future__ import annotations

from io import BytesIO
from uuid import uuid4

import pandas as pd
import streamlit as st

import neon_utils as neon
from neon_utils import (
    apply_owner_sync_updates,
    clean,
    fetch_crm_side_rows_by_phones,
    fetch_owner_user_options,
    normalize_phone,
)
from permissions import can_assign_customer_owner


PHONE_COLUMN = "เบอร์โทร"
OWNER_COLUMN = "พนักงานดูแล"
TEAM_COLUMN = "ทีม"
CRM_TEAM_LABEL = "CRM Team"
REQUIRED_COLUMNS = (PHONE_COLUMN, OWNER_COLUMN, TEAM_COLUMN)

SKIP_BLANK_OWNER = "ไม่ได้กรอกพนักงานดูแล"
SKIP_UNKNOWN_OWNER = "ไม่รู้จักชื่อพนักงานนี้ในระบบ"
SKIP_CONFLICT = "ไฟล์ระบุผู้ดูแลไม่ตรงกันสำหรับเบอร์เดียวกัน"
SKIP_NO_MATCH = "ไม่พบเบอร์นี้ในฝั่ง CRM ของระบบ"


def normalize_name(value) -> str:
    return " ".join(clean(value).split()).casefold()


def read_owner_sync_file(data: bytes) -> tuple[list[dict], str]:
    """Rows of the uploaded sheet, or an error message."""
    try:
        frame = pd.read_excel(BytesIO(data), dtype=str)
    except Exception as exc:  # pragma: no cover - surfaced in the UI
        return [], f"อ่านไฟล์ไม่สำเร็จ: {exc}"
    missing = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
    if missing:
        return [], f"ไฟล์ไม่มีคอลัมน์ที่ต้องใช้: {', '.join(missing)}"
    frame = frame.where(pd.notna(frame), None)
    return frame.to_dict("records"), ""


def plan_owner_sync(rows: list[dict], staff_code_by_name: dict[str, str], current_rows: list[dict]) -> dict:
    """Work out what would change, without touching anything.

    Returns the updates to apply plus a per-reason tally of what was skipped,
    so the person sees the whole picture before approving.
    """
    code_by_normalized_name = {normalize_name(name): code for name, code in staff_code_by_name.items()}
    canonical_name = {normalize_name(name): name for name in staff_code_by_name}

    wanted: dict[str, set] = {}
    crm_rows_seen = 0
    for row in rows or []:
        if clean(row.get(TEAM_COLUMN)) != CRM_TEAM_LABEL:
            continue
        crm_rows_seen += 1
        phone = normalize_phone(row.get(PHONE_COLUMN))
        if not phone:
            continue
        wanted.setdefault(phone, set()).add(normalize_name(row.get(OWNER_COLUMN)))

    skipped: dict[str, list[str]] = {}

    def skip(reason: str, phone: str) -> None:
        skipped.setdefault(reason, []).append(phone)

    rows_by_phone: dict[str, list[dict]] = {}
    for row in current_rows or []:
        for phone in (normalize_phone(row.get("phone1")), normalize_phone(row.get("phone2"))):
            if phone:
                rows_by_phone.setdefault(phone, []).append(row)

    updates: list[dict] = []
    unchanged = 0
    for phone, names in sorted(wanted.items()):
        if len(names) > 1:
            skip(SKIP_CONFLICT, phone)
            continue
        name = next(iter(names))
        if not name:
            skip(SKIP_BLANK_OWNER, phone)
            continue
        staff_code = code_by_normalized_name.get(name)
        if not staff_code:
            skip(SKIP_UNKNOWN_OWNER, phone)
            continue
        matched = rows_by_phone.get(phone) or []
        if not matched:
            skip(SKIP_NO_MATCH, phone)
            continue
        changing = [
            row
            for row in matched
            if clean(row.get("staff_code")).upper() != staff_code.upper()
            or normalize_name(row.get("owner")) != name
        ]
        if not changing:
            unchanged += 1
            continue
        updates.append(
            {
                "phone": phone,
                "owner": canonical_name[name],
                "staff_code": staff_code,
                "row_ids": [clean(row.get("id")) for row in changing],
                "previous": [
                    {"id": clean(row.get("id")), "owner": clean(row.get("owner")), "staff_code": clean(row.get("staff_code"))}
                    for row in changing
                ],
            }
        )
    return {
        "updates": updates,
        "unchanged_customers": unchanged,
        "crm_rows_in_file": crm_rows_seen,
        "phones_in_file": len(wanted),
        "skipped": skipped,
    }


def summarize_moves(updates: list[dict]) -> pd.DataFrame:
    moves: dict[tuple[str, str], int] = {}
    for update in updates:
        for previous in update["previous"]:
            key = (clean(previous.get("owner")) or "(ไม่มีผู้ดูแล)", update["owner"])
            moves[key] = moves.get(key, 0) + 1
    rows = [{"จากผู้ดูแล": a, "เป็นผู้ดูแล": b, "จำนวนออเดอร์": n} for (a, b), n in sorted(moves.items(), key=lambda i: -i[1])]
    return pd.DataFrame(rows)


def render_owner_sync_panel(user: dict | None, *, key_prefix: str = "owner_sync") -> None:
    if not can_assign_customer_owner(user):
        return

    st.markdown("#### อัปเดตผู้ดูแลจากไฟล์ (.xlsx)")
    st.caption(
        "อัปโหลดไฟล์ที่ดาวน์โหลดจากระบบแล้วแก้คอลัมน์ “พนักงานดูแล” "
        "ระบบจะอ่านเฉพาะแถวที่ทีมเป็น CRM Team จับคู่ด้วยเบอร์โทร และอัปเดตเฉพาะผู้ดูแลฝั่ง CRM "
        "ไม่มีการเพิ่มหรือลบคำสั่งซื้อ"
    )
    uploaded = st.file_uploader("เลือกไฟล์ .xlsx", type=["xlsx"], key=f"{key_prefix}_file")
    if not uploaded:
        st.session_state.pop(f"{key_prefix}_plan", None)
        return

    if st.button("ตรวจสอบไฟล์", key=f"{key_prefix}_preview", use_container_width=True):
        rows, error = read_owner_sync_file(uploaded.getvalue())
        if error:
            st.error(error)
            return
        try:
            _, staff_code_by_name = _owner_choices()
            phones = [row.get(PHONE_COLUMN) for row in rows if clean(row.get(TEAM_COLUMN)) == CRM_TEAM_LABEL]
            current_rows = fetch_crm_side_rows_by_phones(phones)
        except Exception as exc:
            st.error(f"ตรวจสอบไฟล์ไม่สำเร็จ: {exc}")
            return
        st.session_state[f"{key_prefix}_plan"] = plan_owner_sync(rows, staff_code_by_name, current_rows)
        st.session_state[f"{key_prefix}_request_id"] = str(uuid4())

    plan = st.session_state.get(f"{key_prefix}_plan")
    if not plan:
        return

    updates = plan["updates"]
    rows_to_change = sum(len(update["row_ids"]) for update in updates)
    cols = st.columns(4)
    cols[0].metric("แถว CRM ในไฟล์", f"{plan['crm_rows_in_file']:,}")
    cols[1].metric("ลูกค้าที่จะเปลี่ยนผู้ดูแล", f"{len(updates):,}")
    cols[2].metric("ออเดอร์ที่จะถูกแก้", f"{rows_to_change:,}")
    cols[3].metric("เหมือนเดิม ไม่ต้องแก้", f"{plan['unchanged_customers']:,}")

    if plan["skipped"]:
        st.warning("รายการที่ข้ามไป (ไม่ถูกแก้ไข)")
        st.dataframe(
            pd.DataFrame(
                [{"เหตุผล": reason, "จำนวนเบอร์": len(phones), "ตัวอย่างเบอร์": ", ".join(phones[:5])}
                 for reason, phones in sorted(plan["skipped"].items())]
            ),
            use_container_width=True,
            hide_index=True,
        )

    if not updates:
        st.info("ไม่มีอะไรต้องอัปเดตจากไฟล์นี้")
        return

    st.markdown("**สรุปการย้ายผู้ดูแล**")
    st.dataframe(summarize_moves(updates), use_container_width=True, hide_index=True)

    confirmed = st.checkbox(
        f"ยืนยันอัปเดตผู้ดูแลของลูกค้า {len(updates):,} ราย ({rows_to_change:,} ออเดอร์)",
        key=f"{key_prefix}_confirm",
    )
    if st.button("อัปเดตผู้ดูแลตามไฟล์", disabled=not confirmed, key=f"{key_prefix}_apply", use_container_width=True):
        try:
            result = apply_owner_sync_updates(
                updates,
                user,
                st.session_state.get(f"{key_prefix}_request_id") or str(uuid4()),
            )
        except Exception as exc:
            st.error(f"อัปเดตไม่สำเร็จ ไม่มีข้อมูลถูกเปลี่ยน: {exc}")
            return
        st.success(
            f"อัปเดตแล้ว {result['updated_customers']:,} ลูกค้า "
            f"({result['updated_rows']:,} ออเดอร์) · บันทึกประวัติ {result['audit_logged']:,} รายการ"
        )
        st.session_state.pop(f"{key_prefix}_plan", None)
        st.session_state.pop(f"{key_prefix}_confirm", None)


def _owner_choices() -> tuple[list[str], dict[str, str]]:
    names: list[str] = []
    staff_code_by_name: dict[str, str] = {}
    seen: set[str] = set()
    for row in fetch_owner_user_options(active_only=True):
        name = clean(row.get("staff_name"))
        staff_code = clean(row.get("staff_code"))
        if name and staff_code and staff_code not in seen:
            names.append(name)
            staff_code_by_name[name] = staff_code
            seen.add(staff_code)
    return names, staff_code_by_name
