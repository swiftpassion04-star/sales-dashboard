import ast
import py_compile
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st

import neon_utils as neon


REPO_ROOT = Path(__file__).resolve().parents[1]

# ---------------------------------------------------------------------------
# 0. Compile checks (checklist item: pages/followup.py, ui/manual_order_ui.py,
#    and the canonical Manual Order page must all still compile).
# ---------------------------------------------------------------------------
for relative_path in ("pages/followup.py", "ui/manual_order_ui.py", "pages/import_excel.py"):
    py_compile.compile(str(REPO_ROOT / relative_path), doraise=True)

followup_source = (REPO_ROOT / "pages/followup.py").read_text(encoding="utf-8")
manual_source = (REPO_ROOT / "ui/manual_order_ui.py").read_text(encoding="utf-8")
import_excel_source = (REPO_ROOT / "pages/import_excel.py").read_text(encoding="utf-8")

order_dialog_source = followup_source.split("def _render_order_dialog", 1)[1].split(
    "def find_popup_order_owner_conflict",
    1,
)[0]


def string_constants(source: str) -> str:
    """All string-literal *values* in a module, already Unicode-decoded.

    This file mixes raw UTF-8 Thai text and \\uXXXX-escaped literals for
    different strings (both are valid, equivalent Python source -- just an
    inconsistent authoring style already present in the repo). A plain
    ``.read_text()`` substring search for a literal Thai label can miss a
    match that is spelled with \\uXXXX escapes on disk. Parsing and reading
    back the *decoded* constant values sidesteps that, since Python's parser
    normalizes both forms to the same string.
    """
    parts = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            parts.append(node.value)
    return "\n".join(parts)


def strings_in_function(source: str, function_name: str) -> str:
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == function_name:
            return "\n".join(
                n.value
                for n in ast.walk(node)
                if isinstance(n, ast.Constant) and isinstance(n.value, str)
            )
    raise AssertionError(f"function {function_name} not found in source")


followup_strings = string_constants(followup_source)
manual_strings = string_constants(manual_source)
order_dialog_strings = strings_in_function(followup_source, "_render_order_dialog")

print("compile checks OK")

# ---------------------------------------------------------------------------
# 1. Follow-up order popup: "โน้ตติดตาม" field wiring (structural checks)
# ---------------------------------------------------------------------------
assert 'key=f"{prefix}_followup_note"' in followup_source
assert "โน้ตติดตาม" in order_dialog_strings  # โน้ตติดตาม
assert "st.text_area(" in order_dialog_source

# Initial value must come from the row's existing follow-up note.
assert (
    'st.session_state[f"{prefix}_followup_note"] = clean(row.get("followup_note"))'
    in followup_source
)

# The payload sent to upsert_lead_followup must carry the note through on
# both the canonical column and its legacy mirror, matching the dual-write
# pattern already used by the main Follow-up dialog's own save path.
assert 'followup_note = clean(st.session_state.get(f"{prefix}_followup_note"))' in followup_source
assert '"followup_note": followup_note,' in followup_source
assert '"follow_up_note": followup_note,' in followup_source

# Regression guard: the fields that already existed in the popup must still
# be there (this task is additive only).
for existing_field in (
    'key=f"{prefix}_lead_status"',
    'key=f"{prefix}_followup_status"',
    'key=f"{prefix}_priority"',
    'key=f"{prefix}_next_followup_date"',
):
    assert existing_field in order_dialog_source

print("follow-up note field wiring OK")

# ---------------------------------------------------------------------------
# 2. Follow-up order popup: save ordering / failure safety (structural,
#    mirrors the ordering checks already enforced by
#    tests/test_product_order_options.py, re-asserted here for this task).
# ---------------------------------------------------------------------------
assert order_dialog_source.index("result = upsert_manual_order_items(") < order_dialog_source.index(
    "followup_payload, followup_update_errors = build_popup_followup_payload(row, user, prefix)"
)
assert order_dialog_source.index(
    "followup_payload, followup_update_errors = build_popup_followup_payload(row, user, prefix)"
) < order_dialog_source.index("upsert_lead_followup(followup_payload)")
assert order_dialog_source.index("upsert_lead_followup(followup_payload)") < order_dialog_source.index(
    "clear_popup_order_state(prefix, row)"
)

# Order save failure must never reach the note-carrying follow-up update.
save_fail_source = order_dialog_source.split("except Exception as exc:", 1)[1].split(
    'duplicate_lock_warning = neon.clean(result.get("duplicate_lock_warning"))',
    1,
)[0]
assert "upsert_lead_followup(" not in save_fail_source
assert "build_popup_followup_payload(" not in save_fail_source

# Follow-up update failure must not clear/close the popup (data stays put).
followup_update_fail_source = order_dialog_source.split("upsert_lead_followup(followup_payload)", 1)[1].split(
    "with perf_trace(\"followup.clear_caches\"",
    1,
)[0]
assert "except Exception as exc:" in followup_update_fail_source
assert "clear_popup_order_state(" not in followup_update_fail_source
assert "close_followup_modal(" not in followup_update_fail_source

print("follow-up note save-order/failure safety OK")

# ---------------------------------------------------------------------------
# 3. Follow-up order popup: behavioral check via direct call of the pure,
#    DB-free session-state helpers (same ast-extract-and-exec technique
#    tests/test_product_order_options.py already uses for this module, since
#    importing pages/followup.py directly would execute main() and hit Neon).
# ---------------------------------------------------------------------------
followup_tree = ast.parse(followup_source)
needed_defs = {
    "clean",
    "parse_date",
    "followup_option_or_default",
    "popup_product_picker_state_key",
    "serialize_popup_followup_date",
    "prepare_popup_order_state",
    "build_popup_followup_payload",
    "clear_popup_order_state",
}
needed_assigns = {"LEAD_STATUS_OPTIONS", "FOLLOWUP_STATUS_OPTIONS"}

extracted_nodes = []
for node in followup_tree.body:
    if isinstance(node, ast.FunctionDef) and node.name in needed_defs:
        extracted_nodes.append(node)
    elif isinstance(node, ast.Assign) and any(
        isinstance(target, ast.Name) and target.id in needed_assigns for target in node.targets
    ):
        extracted_nodes.append(node)

found_def_names = {node.name for node in extracted_nodes if isinstance(node, ast.FunctionDef)}
assert found_def_names == needed_defs, f"missing function defs: {needed_defs - found_def_names}"

followup_module = ast.Module(body=extracted_nodes, type_ignores=[])
ast.fix_missing_locations(followup_module)
followup_ns = {
    "st": st,
    "date": date,
    "datetime": datetime,
    "FOLLOWUP_PRIORITY_OPTIONS": neon.FOLLOWUP_PRIORITY_OPTIONS,
    "normalize_followup_priority": neon.normalize_followup_priority,
}
exec(compile(followup_module, "<followup_note_helpers>", "exec"), followup_ns)

st.session_state.clear()

sample_row = {
    "customer_key": "customer_id:42",
    "crm_data_import_id": "42",
    "order_id": "",
    "customer_name": "ทดสอบ ลูกค้า",
    "phone1": "0812345678",
    "phone2": "",
    "product_name": "GKK24",
    "sku": "SP674",
    "url": "",
    "staff_code": "ST01",
    "owner": "สายตาม",
    "lead_status": "new",
    "followup_status": "scheduled",
    "priority": "VIP",
    "next_followup_date": "2026-07-25",
    "followup_note": "โทรหาเวลาเย็น",  # โทรหาเวลาเย็น
}
prefix = "followup_order_customer_id_42"

# 3a. Popup opens -> initial note value must come from the row's existing note.
followup_ns["prepare_popup_order_state"](prefix, sample_row)
assert st.session_state[f"{prefix}_followup_note"] == sample_row["followup_note"]

# 3b. Re-priming an already-"ready" popup must NOT clobber a note the user is
#     mid-edit on (matches existing behavior for the other fields).
st.session_state[f"{prefix}_followup_note"] = "แก้ไขอยู่"  # แก้ไขอยู่
followup_ns["prepare_popup_order_state"](prefix, sample_row)
assert st.session_state[f"{prefix}_followup_note"] == "แก้ไขอยู่"

# 3c. Untouched note -> build_popup_followup_payload preserves the original
#     value (requirement: "ถ้าไม่ได้เปลี่ยนโน้ตติดตามในป๊อปอัพ ต้องคงค่าเดิมไว้").
st.session_state.clear()
followup_ns["prepare_popup_order_state"](prefix, sample_row)
payload, errors = followup_ns["build_popup_followup_payload"](sample_row, {"email": "tester@example.com"}, prefix)
assert errors == []
assert payload["followup_note"] == sample_row["followup_note"]
assert payload["follow_up_note"] == sample_row["followup_note"]

# 3d. Edited note -> build_popup_followup_payload carries the edited value on
#     both the canonical and legacy-mirror columns.
st.session_state[f"{prefix}_followup_note"] = "นัดโทรอีกครั้งพรุ่งนี้"  # นัดโทรอีกครั้งพรุ่งนี้
payload, errors = followup_ns["build_popup_followup_payload"](sample_row, {"email": "tester@example.com"}, prefix)
assert errors == []
assert payload["followup_note"] == "นัดโทรอีกครั้งพรุ่งนี้"
assert payload["follow_up_note"] == "นัดโทรอีกครั้งพรุ่งนี้"

# 3e. Blank/whitespace-only note must clear cleanly (not error, not None-crash).
st.session_state[f"{prefix}_followup_note"] = "   "
payload, errors = followup_ns["build_popup_followup_payload"](sample_row, {"email": "tester@example.com"}, prefix)
assert errors == []
assert payload["followup_note"] == ""
assert payload["follow_up_note"] == ""

# 3f. clear_popup_order_state wipes the note along with the rest of this
#     popup's state, then re-primes from the row (same behavior as every
#     other field in this popup -- no special-casing needed for the note).
st.session_state[f"{prefix}_followup_note"] = "จะถูกล้าง"  # จะถูกล้าง
followup_ns["clear_popup_order_state"](prefix, sample_row)
assert st.session_state[f"{prefix}_followup_note"] == sample_row["followup_note"]

st.session_state.clear()
print("follow-up note behavioral checks OK")

# ---------------------------------------------------------------------------
# 4. Manual Order: page shows a clean entry with a "+ เพิ่มคำสั่งซื้อ" button
#    that opens a dialog (structural checks).
# ---------------------------------------------------------------------------
assert "def render_manual_order_entry(user: dict, is_editor: bool) -> None:" in manual_source
assert "def _render_manual_order_entry(user: dict, is_editor: bool) -> None:" in manual_source
entry_source = manual_source.split("def _render_manual_order_entry", 1)[1].split(
    "@st.dialog(\"เพิ่มคำสั่งซื้อ\", width=\"large\")",
    1,
)[0]
assert '"+ เพิ่มคำสั่งซื้อ"' in entry_source  # + เพิ่มคำสั่งซื้อ
assert 'st.button(' in entry_source
assert 'st.session_state["manual_order_dialog_open"] = True' in entry_source
assert "st.rerun()" in entry_source
assert 'if st.session_state.get("manual_order_dialog_open"):' in entry_source
assert "render_manual_order_dialog(user, is_editor)" in entry_source

assert '@st.dialog("เพิ่มคำสั่งซื้อ", width="large")' in manual_source
assert "def render_manual_order_dialog(user: dict, is_editor: bool) -> None:" in manual_source
assert "render_manual_order_form(user, is_editor)" in manual_source

print("manual order entry/dialog wiring OK")

# ---------------------------------------------------------------------------
# 5. Manual Order dialog must NOT contain follow-up tracking fields.
# ---------------------------------------------------------------------------
for tracking_label in (
    "สถานะลูกค้า",   # สถานะลูกค้า
    "สถานะติดตาม",   # สถานะติดตาม
    "ความสำคัญ",               # ความสำคัญ
    "วันที่นัด",               # วันที่นัด
    "โน้ตติดตาม",         # โน้ตติดตาม
):
    assert tracking_label not in manual_source
assert "LEAD_STATUS_OPTIONS" not in manual_source
assert "FOLLOWUP_STATUS_OPTIONS" not in manual_source
assert "followup_note" not in manual_source

print("manual order excludes follow-up tracking fields OK")

# ---------------------------------------------------------------------------
# 6. Manual Order dialog still has the required customer/order fields.
# ---------------------------------------------------------------------------
for required_label in (
    "หมายเลขคำสั่งซื้อ",  # หมายเลขคำสั่งซื้อ
    "ชื่อลูกค้า",                                          # ชื่อลูกค้า
    "เบอร์โทร",                                                      # เบอร์โทร
    "เบอร์สำรอง",                                          # เบอร์สำรอง
    "URL",
    "ที่อยู่",                                                            # ที่อยู่
    "ประเภทการขาย",                              # ประเภทการขาย
    "ผู้ดูแล",                                                            # ผู้ดูแล
    "วันที่สร้างคำสั่งซื้อ",  # วันที่สร้างคำสั่งซื้อ
    "บันทึกคำสั่งซื้อ",       # บันทึกคำสั่งซื้อ
):
    assert required_label in manual_source

print("manual order retains required customer/order fields OK")

# ---------------------------------------------------------------------------
# 7. Session-state safety: validation failure keeps the dialog open with
#    entered data intact (no clear, no close).
# ---------------------------------------------------------------------------
validate_fail_source = manual_source.split("if errors:", 1)[1].split(
    "if not is_editor and should_check_manual_owner_conflict(user):",
    1,
)[0]
assert 'st.session_state["manual_order_dialog_open"] = False' not in validate_fail_source
assert "clear_manual_order_form_state()" not in validate_fail_source
assert "manual_order_clear_requested = True" not in validate_fail_source

# Owner-conflict rejection must also leave the dialog open.
owner_conflict_source = manual_source.split(
    "if not is_editor and should_check_manual_owner_conflict(user):", 1
)[1].split("try:\n        with perf_trace(", 1)[0]
assert 'st.session_state["manual_order_dialog_open"] = False' not in owner_conflict_source
assert "clear_manual_order_form_state()" not in owner_conflict_source

# Order save exception must also leave the dialog open.
manual_save_fail_source = manual_source.split("except Exception as exc:", 1)[1].split(
    'duplicate_lock_warning = neon.clean(result.get("duplicate_lock_warning"))',
    1,
)[0]
assert 'st.session_state["manual_order_dialog_open"] = False' not in manual_save_fail_source
assert "clear_manual_order_form_state()" not in manual_save_fail_source

print("manual order failure paths keep dialog state intact OK")

# ---------------------------------------------------------------------------
# 8. Session-state safety: save success closes the dialog and schedules a
#    field clear (consumed the next time the dialog opens).
# ---------------------------------------------------------------------------
success_tail_source = manual_source.split(
    'duplicate_lock_warning = neon.clean(result.get("duplicate_lock_warning"))', 1
)[1]
assert 'st.session_state.manual_order_success_message = f"' in success_tail_source
assert "st.session_state.manual_order_clear_requested = True" in success_tail_source
assert 'st.session_state["manual_order_dialog_open"] = False' in success_tail_source
assert success_tail_source.index("st.session_state.manual_order_clear_requested = True") < success_tail_source.index(
    "st.rerun()"
)
assert success_tail_source.index('st.session_state["manual_order_dialog_open"] = False') < success_tail_source.index(
    "st.rerun()"
)

print("manual order save-success closes dialog OK")

# ---------------------------------------------------------------------------
# 9. Regression guards: product selector pattern, save call, and duplicate
#    phone/owner protection are all still exactly as before.
# ---------------------------------------------------------------------------
assert "render_manual_product_picker(product_options)" in manual_source
assert "render_manual_product_selector_dialog(product_options)" in manual_source
assert "filter_product_selector_options" in manual_source
assert "paginate_product_selector_options" in manual_source
assert "PRODUCT_SELECTOR_PAGE_SIZE_OPTIONS" in manual_source
assert "add_manual_order_item(product, 1, None)" in manual_source

assert "neon.upsert_manual_order_items(" in manual_source

assert "should_check_manual_owner_conflict(user)" in manual_source
assert "neon.fetch_current_user_team_code" in manual_source
assert "neon.should_enforce_duplicate_phone_lock(team_code)" in manual_source
assert "find_manual_order_owner_conflict(phone1, phone2, user, owner, staff_code)" in manual_source
assert "if not is_editor and should_check_manual_owner_conflict(user):" in manual_source

print("manual order product selector / save / duplicate-lock regressions OK")

# ---------------------------------------------------------------------------
# 10. Canonical page wiring: pages/import_excel.py now opens the Manual
#     Order flow through the new entry point, and the rest of that page
#     (Excel import tabs, customer export panel) is untouched.
# ---------------------------------------------------------------------------
assert "from ui.manual_order_ui import render_manual_order_entry" in import_excel_source
assert "render_manual_order_entry(user, is_editor)" in import_excel_source
assert "render_manual_order_form(user, is_editor)" not in import_excel_source
assert "render_customer_export_panel(" in import_excel_source
assert "render_excel_import(user)" in import_excel_source
assert "render_import_history()" in import_excel_source
assert "def upsert_manual_order_items" not in import_excel_source
assert "def insert_import_records" not in import_excel_source
assert "def delete_import_batch" not in import_excel_source

print("import_excel.py canonical wiring OK")

print("order dialog workflows safety OK")
