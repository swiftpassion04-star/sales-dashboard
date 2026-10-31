"""Updating customer owners from an edited copy of the customer export.

The planner decides what would change; nothing is written until the person
approves the preview. These tests pin the rules that keep the upload safe:
CRM-team rows only, matched by phone, never inventing an owner, and never
touching the open (Upsell / no team) side.

No pytest in this environment -- discovered via the repo's stdlib test_*
runner, same as every other tests/test_*.py file here.
"""

import inspect
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import neon_utils as neon
from ui.owner_sync_ui import (
    CRM_TEAM_LABEL,
    OWNER_COLUMN,
    PHONE_COLUMN,
    SKIP_BLANK_OWNER,
    SKIP_CONFLICT,
    SKIP_NO_MATCH,
    SKIP_UNKNOWN_OWNER,
    TEAM_COLUMN,
    plan_owner_sync,
    read_owner_sync_file,
    summarize_moves,
)


STAFF = {
    "สายฝน ราวิชัย (สายฝน)": "SAIFON",
    "พรณกมล ดวงจันทร์ (แต้ว)": "TAEW",
    "พรนภา นันที (หนูนา)": "NOONA",
}


def file_row(phone, owner, team=CRM_TEAM_LABEL, **extra):
    row = {PHONE_COLUMN: phone, OWNER_COLUMN: owner, TEAM_COLUMN: team}
    row.update(extra)
    return row


def db_row(row_id, phone, owner, staff_code, phone2=""):
    return {"id": str(row_id), "phone1": phone, "phone2": phone2, "owner": owner, "staff_code": staff_code}


# --- what gets updated ----------------------------------------------------------

def test_a_changed_owner_updates_every_order_of_that_phone():
    plan = plan_owner_sync(
        [file_row("0811111111", "พรณกมล ดวงจันทร์ (แต้ว)")],
        STAFF,
        [
            db_row(1, "0811111111", "สายฝน ราวิชัย (สายฝน)", "SAIFON"),
            db_row(2, "0811111111", "สายฝน ราวิชัย (สายฝน)", "SAIFON"),
        ],
    )
    assert len(plan["updates"]) == 1
    update = plan["updates"][0]
    assert update["staff_code"] == "TAEW"
    assert update["owner"] == "พรณกมล ดวงจันทร์ (แต้ว)"
    assert sorted(update["row_ids"]) == ["1", "2"]
    assert update["previous"][0]["staff_code"] == "SAIFON"  # kept for the audit log


def test_the_phone_matches_on_either_column():
    plan = plan_owner_sync(
        [file_row("0822222222", "พรนภา นันที (หนูนา)")],
        STAFF,
        [db_row(9, "0899999999", "สายฝน ราวิชัย (สายฝน)", "SAIFON", phone2="0822222222")],
    )
    assert plan["updates"][0]["row_ids"] == ["9"]


def test_an_unchanged_owner_produces_no_update():
    plan = plan_owner_sync(
        [file_row("0811111111", "สายฝน ราวิชัย (สายฝน)")],
        STAFF,
        [db_row(1, "0811111111", "สายฝน ราวิชัย (สายฝน)", "SAIFON")],
    )
    assert plan["updates"] == []
    assert plan["unchanged_customers"] == 1


def test_a_renamed_owner_on_the_same_staff_code_is_rewritten():
    # same person, display name edited in the file -> the row is realigned
    plan = plan_owner_sync(
        [file_row("0811111111", "สายฝน ราวิชัย (สายฝน)")],
        STAFF,
        [db_row(1, "0811111111", "สายฝน  ราวิชัย", "SAIFON")],
    )
    assert plan["updates"][0]["owner"] == "สายฝน ราวิชัย (สายฝน)"


def test_owner_name_matching_ignores_case_and_extra_spaces():
    plan = plan_owner_sync(
        [file_row("0811111111", "  พรนภา   นันที (หนูนา) ")],
        STAFF,
        [db_row(1, "0811111111", "สายฝน ราวิชัย (สายฝน)", "SAIFON")],
    )
    assert plan["updates"][0]["staff_code"] == "NOONA"


# --- what is skipped -------------------------------------------------------------

def test_rows_of_other_teams_are_ignored_entirely():
    rows = [
        file_row("0833333333", "พรณกมล ดวงจันทร์ (แต้ว)", team="Upsell Team"),
        file_row("0844444444", "พรณกมล ดวงจันทร์ (แต้ว)", team="ยังไม่เลือกทีม"),
    ]
    db = [db_row(1, "0833333333", "สายฝน ราวิชัย (สายฝน)", "SAIFON"),
          db_row(2, "0844444444", "สายฝน ราวิชัย (สายฝน)", "SAIFON")]
    plan = plan_owner_sync(rows, STAFF, db)
    assert plan["updates"] == []
    assert plan["crm_rows_in_file"] == 0
    assert plan["skipped"] == {}


def test_a_blank_owner_is_skipped_not_cleared():
    plan = plan_owner_sync(
        [file_row("0811111111", "")],
        STAFF,
        [db_row(1, "0811111111", "สายฝน ราวิชัย (สายฝน)", "SAIFON")],
    )
    assert plan["updates"] == []
    assert plan["skipped"][SKIP_BLANK_OWNER] == ["0811111111"]


def test_an_unknown_owner_name_is_skipped():
    plan = plan_owner_sync(
        [file_row("0811111111", "ใครก็ไม่รู้")],
        STAFF,
        [db_row(1, "0811111111", "สายฝน ราวิชัย (สายฝน)", "SAIFON")],
    )
    assert plan["updates"] == []
    assert plan["skipped"][SKIP_UNKNOWN_OWNER] == ["0811111111"]


def test_two_different_owners_for_one_phone_are_skipped():
    plan = plan_owner_sync(
        [file_row("0811111111", "พรณกมล ดวงจันทร์ (แต้ว)"), file_row("0811111111", "พรนภา นันที (หนูนา)")],
        STAFF,
        [db_row(1, "0811111111", "สายฝน ราวิชัย (สายฝน)", "SAIFON")],
    )
    assert plan["updates"] == []
    assert plan["skipped"][SKIP_CONFLICT] == ["0811111111"]


def test_a_phone_the_crm_side_does_not_have_is_skipped_never_created():
    plan = plan_owner_sync([file_row("0855555555", "พรณกมล ดวงจันทร์ (แต้ว)")], STAFF, [])
    assert plan["updates"] == []
    assert plan["skipped"][SKIP_NO_MATCH] == ["0855555555"]


def test_only_rows_handed_in_can_be_updated():
    # The planner never looks anything up itself: the caller passes the CRM-side
    # rows, so the open side can never end up in an update.
    plan = plan_owner_sync(
        [file_row("0811111111", "พรณกมล ดวงจันทร์ (แต้ว)")],
        STAFF,
        [db_row(1, "0811111111", "สายฝน ราวิชัย (สายฝน)", "SAIFON")],
    )
    assert [row_id for update in plan["updates"] for row_id in update["row_ids"]] == ["1"]


# --- file reading ------------------------------------------------------------------

def test_a_file_without_the_needed_columns_is_rejected():
    import pandas as pd
    from io import BytesIO

    buffer = BytesIO()
    pd.DataFrame([{"เบอร์โทร": "0811111111"}]).to_excel(buffer, index=False)
    rows, error = read_owner_sync_file(buffer.getvalue())
    assert rows == []
    assert "พนักงานดูแล" in error and "ทีม" in error


def test_a_real_export_file_is_read_back():
    import pandas as pd
    from io import BytesIO

    buffer = BytesIO()
    pd.DataFrame(
        [{PHONE_COLUMN: "0811111111", OWNER_COLUMN: "สายฝน ราวิชัย (สายฝน)", TEAM_COLUMN: CRM_TEAM_LABEL}]
    ).to_excel(buffer, index=False)
    rows, error = read_owner_sync_file(buffer.getvalue())
    assert error == ""
    assert rows[0][PHONE_COLUMN] == "0811111111"


def test_the_move_summary_counts_orders_per_pair():
    plan = plan_owner_sync(
        [file_row("0811111111", "พรณกมล ดวงจันทร์ (แต้ว)"), file_row("0822222222", "พรณกมล ดวงจันทร์ (แต้ว)")],
        STAFF,
        [
            db_row(1, "0811111111", "สายฝน ราวิชัย (สายฝน)", "SAIFON"),
            db_row(2, "0811111111", "สายฝน ราวิชัย (สายฝน)", "SAIFON"),
            db_row(3, "0822222222", "พรนภา นันที (หนูนา)", "NOONA"),
        ],
    )
    frame = summarize_moves(plan["updates"])
    assert set(frame["จำนวนออเดอร์"]) == {2, 1}
    assert set(frame["เป็นผู้ดูแล"]) == {"พรณกมล ดวงจันทร์ (แต้ว)"}


# --- the write path ------------------------------------------------------------------

APPLY_SOURCE = " ".join(inspect.getsource(neon.apply_owner_sync_updates).split())
READ_SOURCE = " ".join(inspect.getsource(neon.fetch_crm_side_rows_by_phones).split())


def test_the_write_only_ever_updates_existing_valid_rows():
    assert "update public.crm_data_imports" in APPLY_SOURCE
    assert "where id::text = any(%s) and import_status = 'valid'" in APPLY_SOURCE
    for forbidden in ("insert into public.crm_data_imports", "delete from public.crm_data_imports"):
        assert forbidden not in APPLY_SOURCE


def test_the_write_is_editor_only_transactional_and_audited():
    assert "_assert_editor_customer_record_action(user)" in APPLY_SOURCE
    assert "conn.rollback()" in APPLY_SOURCE and "conn.commit()" in APPLY_SOURCE
    assert 'action_type="OWNER_SYNC_FROM_FILE"' in APPLY_SOURCE
    assert APPLY_SOURCE.index("_assert_editor_customer_record_action") < APPLY_SOURCE.index("update public.crm_data_imports")


def test_the_read_side_is_crm_only():
    assert "{_ORDER_TEAM_SIDE_SQL} = %s" in READ_SOURCE
    assert "OWNERSHIP_SIDE_CRM" in READ_SOURCE
    assert "import_status = 'valid'" in READ_SOURCE


def test_applying_an_empty_plan_writes_nothing():
    assert neon.apply_owner_sync_updates([], {"role": "EDITOR"}, "req-1") == {
        "updated_rows": 0,
        "updated_customers": 0,
        "audit_logged": 0,
    }


def test_the_page_offers_the_panel_to_editors_only():
    page = (Path(__file__).resolve().parents[1] / "pages" / "import_excel.py").read_text(encoding="utf-8")
    assert "render_owner_sync_panel(user)" in page
    ui = (Path(__file__).resolve().parents[1] / "ui" / "owner_sync_ui.py").read_text(encoding="utf-8")
    assert "if not can_assign_customer_owner(user):" in ui
    assert "disabled=not confirmed" in ui  # the apply button needs the tick
