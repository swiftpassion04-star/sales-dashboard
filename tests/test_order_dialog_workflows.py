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

for tracking_widget_key in (
    'key=f"{prefix}_lead_status"',
    'key=f"{prefix}_followup_status"',
    'key=f"{prefix}_priority"',
    'key=f"{prefix}_next_followup_date"',
    'key=f"{prefix}_followup_note"',
):
    assert tracking_widget_key in order_dialog_source

for order_widget_key in (
    'key=f"{prefix}_order_id"',
    'key=f"{prefix}_customer_name"',
    'key=f"{prefix}_phone1"',
    'key=f"{prefix}_phone2"',
    'key=f"{prefix}_url"',
    'key=f"{prefix}_address"',
    'key=f"{prefix}_sale_type"',
):
    assert order_widget_key in order_dialog_source

assert "st.form(" not in order_dialog_source
assert "form_submit_button" not in order_dialog_source
assert "product_action.button(" in order_dialog_source
assert "submitted = st.button(" in order_dialog_source
assert 'key=f"{prefix}_open_product_picker"' in order_dialog_source
assert 'key=f"{prefix}_submit_order"' in order_dialog_source
assert "@st.dialog(" not in order_dialog_source
assert "st.fragment" not in order_dialog_source
assert "st.cache_data.clear()" not in order_dialog_source

print("follow-up note field wiring OK")

# ---------------------------------------------------------------------------
# 2. Follow-up order popup: save ordering / failure safety (structural,
#    mirrors the ordering checks already enforced by
#    tests/test_product_order_options.py, re-asserted here for this task).
# ---------------------------------------------------------------------------
assert order_dialog_source.index("result = upsert_manual_order_items(") < order_dialog_source.index(
    "followup_row = popup_followup_row_for_saved_order(row, result, st.session_state.get(f\"{prefix}_items\") or [])"
)
assert order_dialog_source.index(
    "followup_row = popup_followup_row_for_saved_order(row, result, st.session_state.get(f\"{prefix}_items\") or [])"
) < order_dialog_source.index(
    "followup_payload, followup_update_errors = build_popup_followup_payload(followup_row, user, prefix)"
)
assert order_dialog_source.index(
    "followup_payload, followup_update_errors = build_popup_followup_payload(followup_row, user, prefix)"
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
    "popup_followup_row_for_saved_order",
    "select_popup_product",
    "add_popup_order_item",
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

# 3g. Scenario A: edit appointment date, open the product picker, select a
#     product, then save. The new date must survive the picker rerun and be
#     written to both canonical and legacy date fields.
st.session_state.clear()
followup_ns["prepare_popup_order_state"](prefix, sample_row)
new_date = date(2026, 8, 2)
st.session_state[f"{prefix}_next_followup_date"] = new_date
st.session_state[followup_ns["popup_product_picker_state_key"](prefix, "open")] = True
product = {
    "sku": "SP680",
    "product_name": "Coffee Premium",
    "product_group": "Drink",
    "image_url": "https://example.test/sp680.jpg",
}
followup_ns["select_popup_product"](prefix, product, "680")
followup_ns["add_popup_order_item"](prefix, product, 1, None)
followup_ns["prepare_popup_order_state"](prefix, sample_row)
payload, errors = followup_ns["build_popup_followup_payload"](sample_row, {"email": "tester@example.com"}, prefix)
assert errors == []
assert st.session_state[f"{prefix}_next_followup_date"] == new_date
assert payload["next_followup_date"] == "2026-08-02"
assert payload["follow_up_date"] == "2026-08-02"
assert st.session_state[f"{prefix}_items"][0]["image_url"] == product["image_url"]
assert st.session_state[f"{prefix}_items"][0]["qty"] == 1
assert st.session_state[f"{prefix}_items"][0]["amount"] == ""

# 3h. Scenario B: picker already open -> edit date -> click product pick
#     immediately. The selected product rerun must not restore the old date.
st.session_state.clear()
followup_ns["prepare_popup_order_state"](prefix, sample_row)
st.session_state[followup_ns["popup_product_picker_state_key"](prefix, "open")] = True
immediate_date = date(2026, 8, 3)
st.session_state[f"{prefix}_next_followup_date"] = immediate_date
followup_ns["select_popup_product"](prefix, product, "680")
followup_ns["add_popup_order_item"](prefix, product, 1, None)
followup_ns["prepare_popup_order_state"](prefix, sample_row)
payload, errors = followup_ns["build_popup_followup_payload"](sample_row, {"email": "tester@example.com"}, prefix)
assert errors == []
assert st.session_state[f"{prefix}_next_followup_date"] == immediate_date
assert payload["next_followup_date"] == "2026-08-03"
assert payload["follow_up_date"] == "2026-08-03"

# 3i. Scenario C: an originally blank appointment date must not come back as
#     None after choosing a date and selecting a product.
blank_date_row = dict(sample_row)
blank_date_row["next_followup_date"] = None
st.session_state.clear()
followup_ns["prepare_popup_order_state"](prefix, blank_date_row)
assert st.session_state[f"{prefix}_next_followup_date"] is None
selected_date = date(2026, 8, 4)
st.session_state[f"{prefix}_next_followup_date"] = selected_date
followup_ns["select_popup_product"](prefix, product, "680")
followup_ns["add_popup_order_item"](prefix, product, 1, None)
followup_ns["prepare_popup_order_state"](prefix, blank_date_row)
payload, errors = followup_ns["build_popup_followup_payload"](blank_date_row, {"email": "tester@example.com"}, prefix)
assert errors == []
assert st.session_state[f"{prefix}_next_followup_date"] == selected_date
assert payload["next_followup_date"] == "2026-08-04"
assert payload["follow_up_date"] == "2026-08-04"

# 3j. Scenario D / reverse interaction: order fields already in session_state
#     must survive a rerun caused by outside-form follow-up widgets.
st.session_state.clear()
followup_ns["prepare_popup_order_state"](prefix, sample_row)
st.session_state[f"{prefix}_order_id"] = "ORDER-123"
st.session_state[f"{prefix}_customer_name"] = "Customer Draft"
st.session_state[f"{prefix}_phone1"] = "0899999999"
st.session_state[f"{prefix}_url"] = "https://example.test/order"
st.session_state[f"{prefix}_address"] = "Draft address"
st.session_state[f"{prefix}_sale_type"] = "UPSELL"
st.session_state[f"{prefix}_next_followup_date"] = date(2026, 8, 5)
followup_ns["prepare_popup_order_state"](prefix, sample_row)
assert st.session_state[f"{prefix}_order_id"] == "ORDER-123"
assert st.session_state[f"{prefix}_customer_name"] == "Customer Draft"
assert st.session_state[f"{prefix}_phone1"] == "0899999999"
assert st.session_state[f"{prefix}_url"] == "https://example.test/order"
assert st.session_state[f"{prefix}_address"] == "Draft address"
assert st.session_state[f"{prefix}_sale_type"] == "UPSELL"
payload, errors = followup_ns["build_popup_followup_payload"](sample_row, {"email": "tester@example.com"}, prefix)
assert errors == []
assert payload["next_followup_date"] == "2026-08-05"

# 3k. Behavioral render harness: after removing st.form, every dialog widget
#     should commit immediately to session_state, and real save calls should
#     receive the preserved order/follow-up data.
dialog_needed_defs = {
    "clean",
    "parse_date",
    "followup_option_or_default",
    "popup_product_picker_state_key",
    "serialize_popup_followup_date",
    "prepare_popup_order_state",
    "build_popup_followup_payload",
    "clear_popup_order_state",
    "popup_followup_row_for_saved_order",
    "select_popup_product",
    "add_popup_order_item",
    "_render_order_dialog",
    "render_popup_order_items",
    "render_popup_order_item_preview",
    "selected_product_image_preview_url",
}
dialog_needed_assigns = {"LEAD_STATUS_OPTIONS", "FOLLOWUP_STATUS_OPTIONS"}
dialog_nodes = []
for node in followup_tree.body:
    if isinstance(node, ast.FunctionDef) and node.name in dialog_needed_defs:
        dialog_nodes.append(node)
    elif isinstance(node, ast.Assign) and any(
        isinstance(target, ast.Name) and target.id in dialog_needed_assigns for target in node.targets
    ):
        dialog_nodes.append(node)

assert {node.name for node in dialog_nodes if isinstance(node, ast.FunctionDef)} == dialog_needed_defs


class _FakeRerun(Exception):
    pass


class _NoopContext:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeSessionState(dict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def __setattr__(self, name, value):
        self[name] = value


class _FakeStreamlit:
    def __init__(self, state, values=None, clicks=None, harness=None):
        self.session_state = state
        self.values = values or {}
        self.clicks = set(clicks or [])
        self.harness = harness

    def columns(self, spec, **_kwargs):
        count = spec if isinstance(spec, int) else len(spec)
        return [self for _ in range(count)]

    def text_input(self, _label, value="", key=None, **_kwargs):
        if key in self.values:
            self.session_state[key] = self.values[key]
        elif key and key not in self.session_state:
            self.session_state[key] = value
        return self.session_state.get(key, value)

    def text_area(self, _label, value="", key=None, **_kwargs):
        return self.text_input(_label, value=value, key=key)

    def selectbox(self, _label, options, key=None, **_kwargs):
        default = options[0] if options else None
        if key in self.values:
            self.session_state[key] = self.values[key]
        elif key and key not in self.session_state:
            self.session_state[key] = default
        return self.session_state.get(key, default)

    def date_input(self, _label, value=None, key=None, **_kwargs):
        if key in self.values:
            self.session_state[key] = self.values[key]
        elif key and key not in self.session_state:
            self.session_state[key] = value
        return self.session_state.get(key, value)

    def number_input(self, _label, value=0, key=None, **_kwargs):
        if key in self.values:
            self.session_state[key] = self.values[key]
        elif key and key not in self.session_state:
            self.session_state[key] = value
        return self.session_state.get(key, value)

    def button(self, label, key=None, **_kwargs):
        button_id = key or label
        return button_id in self.clicks or label in self.clicks

    def form_submit_button(self, *_args, **_kwargs):
        raise AssertionError("Follow-up order dialog must not use st.form_submit_button")

    def form(self, *_args, **_kwargs):
        raise AssertionError("Follow-up order dialog must not use st.form")

    def rerun(self):
        if self.harness:
            self.harness.reruns += 1
        raise _FakeRerun()

    def error(self, message):
        if self.harness:
            self.harness.errors.append(str(message))

    def warning(self, _message):
        pass

    def caption(self, _message):
        pass

    def markdown(self, _message, **_kwargs):
        pass

    def info(self, _message):
        pass

    def write(self, _message):
        pass

    def image(self, *_args, **_kwargs):
        pass


class _DialogHarness:
    def __init__(self, row):
        self.row = dict(row)
        self.state = _FakeSessionState()
        self.order_writes = []
        self.followup_writes = []
        self.cache_clears = 0
        self.closes = 0
        self.reruns = 0
        self.errors = []
        self.order_fail = False
        self.followup_fail = False
        self.saved_record_ids = []
        self.product = {
            "sku": "SP680",
            "product_name": "Coffee Premium",
            "product_group": "Drink",
            "image_url": "https://example.test/sp680.jpg",
        }

    @property
    def prefix(self):
        return "followup_order_customer_id_42"

    def render(self, values=None, clicks=None, picker_select=False):
        fake = _FakeStreamlit(self.state, values=values, clicks=clicks, harness=self)
        dialog_ns["st"] = fake
        dialog_ns["_active_harness"] = self
        dialog_ns["_picker_select"] = picker_select
        try:
            dialog_ns["_render_order_dialog"](self.row, {"email": "tester@example.com", "role": "admin"})
            return "ok"
        except _FakeRerun:
            return "rerun"


def _fake_render_popup_product_picker(_product_options, row_key):
    harness = dialog_ns["_active_harness"]
    if not dialog_ns.get("_picker_select"):
        return
    dialog_ns["select_popup_product"](row_key, harness.product, "680")
    dialog_ns["add_popup_order_item"](row_key, harness.product, 1, None)
    dialog_ns["st"].rerun()


def _fake_upsert_manual_order_items(order_payload, items):
    harness = dialog_ns["_active_harness"]
    if harness.order_fail:
        raise RuntimeError("order write failed")
    captured_items = [dict(item) for item in items]
    harness.order_writes.append((dict(order_payload), captured_items))
    return {
        "item_count": len(captured_items),
        "actions": {"inserted": len(captured_items), "updated": 0},
        "ids": list(harness.saved_record_ids),
    }


def _fake_upsert_lead_followup(payload):
    harness = dialog_ns["_active_harness"]
    harness.followup_writes.append(dict(payload))
    if harness.followup_fail:
        raise RuntimeError("follow-up write failed")


def _fake_clear_cached_functions_safely(*_functions):
    dialog_ns["_active_harness"].cache_clears += 1


def _fake_close_followup_modal():
    dialog_ns["_active_harness"].closes += 1


def _fake_parse_required_price_input(value):
    text = str(value or "").strip()
    if text == "":
        return False, None, "required"
    try:
        return True, float(text), ""
    except ValueError:
        return False, None, "invalid"


dialog_module = ast.Module(body=dialog_nodes, type_ignores=[])
ast.fix_missing_locations(dialog_module)
dialog_ns = {
    "st": None,
    "date": date,
    "datetime": datetime,
    "neon": neon,
    "row_key": lambda _row: "customer_id_42",
    "perf_trace": lambda *_args, **_kwargs: _NoopContext(),
    "fetch_popup_product_options": lambda: [],
    "render_popup_product_picker": _fake_render_popup_product_picker,
    "parse_required_price_input": _fake_parse_required_price_input,
    "validate_phone_pair": lambda *_args: [],
    "can_manage_all": lambda _user: True,
    "find_popup_order_owner_conflict": lambda *_args: {},
    "upsert_manual_order_items": _fake_upsert_manual_order_items,
    "build_popup_followup_payload": followup_ns["build_popup_followup_payload"],
    "upsert_lead_followup": _fake_upsert_lead_followup,
    "clear_cached_functions_safely": _fake_clear_cached_functions_safely,
    "fetch_followup_filter_options": lambda: None,
    "close_followup_modal": _fake_close_followup_modal,
    "FOLLOWUP_PRIORITY_OPTIONS": neon.FOLLOWUP_PRIORITY_OPTIONS,
    "PRIORITY_OPTIONS": {priority: priority for priority in neon.FOLLOWUP_PRIORITY_OPTIONS},
    "normalize_followup_priority": neon.normalize_followup_priority,
    "lead_label": lambda value: value,
    "followup_label": lambda value: value,
    "priority_label": lambda value: value,
}
dialog_ns.update({
    "render_popup_product_picker": _fake_render_popup_product_picker,
    "remove_popup_order_item": lambda prefix_arg, index: dialog_ns["st"].session_state[f"{prefix_arg}_items"].pop(index),
    "upsert_manual_order_items": _fake_upsert_manual_order_items,
    "upsert_lead_followup": _fake_upsert_lead_followup,
    "clear_cached_functions_safely": _fake_clear_cached_functions_safely,
    "close_followup_modal": _fake_close_followup_modal,
})
exec(compile(dialog_module, "<followup_order_dialog_render>", "exec"), dialog_ns)


def _valid_order_values(prefix_value, order_id="ORDER-123", amount="120"):
    return {
        f"{prefix_value}_order_id": order_id,
        f"{prefix_value}_customer_name": "Customer Draft",
        f"{prefix_value}_phone1": "0899999999",
        f"{prefix_value}_phone2": "",
        f"{prefix_value}_url": "https://example.test/order",
        f"{prefix_value}_address": "Draft address",
        f"{prefix_value}_sale_type": "UPSELL",
        f"{prefix_value}_item_qty_0": 2,
        f"{prefix_value}_item_amount_0": amount,
    }


def _submit_click(prefix_value):
    return {f"{prefix_value}_submit_order"}


# Scenario A: edit date, open picker, select product, save.
harness_a = _DialogHarness(sample_row)
prefix_a = harness_a.prefix
assert harness_a.render(values={f"{prefix_a}_next_followup_date": date(2026, 8, 6)}, clicks={f"{prefix_a}_open_product_picker"}) == "rerun"
assert harness_a.state[f"{prefix_a}_next_followup_date"] == date(2026, 8, 6)
assert harness_a.render(picker_select=True) == "rerun"
assert harness_a.render(values=_valid_order_values(prefix_a), clicks=_submit_click(prefix_a)) == "rerun"
assert harness_a.followup_writes[0]["next_followup_date"] == "2026-08-06"
assert harness_a.followup_writes[0]["follow_up_date"] == "2026-08-06"

# Scenario B: picker is open, edit date, pick immediately, save.
harness_b = _DialogHarness(sample_row)
prefix_b = harness_b.prefix
harness_b.state[followup_ns["popup_product_picker_state_key"](prefix_b, "open")] = True
assert harness_b.render(values={f"{prefix_b}_next_followup_date": date(2026, 8, 7)}, picker_select=True) == "rerun"
assert harness_b.state[f"{prefix_b}_next_followup_date"] == date(2026, 8, 7)
assert harness_b.render(values=_valid_order_values(prefix_b), clicks=_submit_click(prefix_b)) == "rerun"
assert harness_b.followup_writes[0]["next_followup_date"] == "2026-08-07"

# Scenario C: original date None, choose date, select product, rerun.
row_without_date = dict(sample_row)
row_without_date["next_followup_date"] = None
harness_c = _DialogHarness(row_without_date)
prefix_c = harness_c.prefix
assert harness_c.render(values={f"{prefix_c}_next_followup_date": date(2026, 8, 8)}, picker_select=True) == "rerun"
assert harness_c.state[f"{prefix_c}_next_followup_date"] == date(2026, 8, 8)
assert harness_c.render(values=_valid_order_values(prefix_c), clicks=_submit_click(prefix_c)) == "rerun"
assert harness_c.followup_writes[0]["next_followup_date"] == "2026-08-08"

# Scenario D: order fields before metadata rerun remain in captured order payload.
harness_d = _DialogHarness(sample_row)
prefix_d = harness_d.prefix
first_values_d = _valid_order_values(prefix_d, order_id="ORDER-D")
harness_d.render(values=first_values_d)
harness_d.state[f"{prefix_d}_items"] = [dict(harness_d.product, qty=1, amount="120")]
harness_d.render(values={f"{prefix_d}_item_qty_0": 2, f"{prefix_d}_item_amount_0": "120"})
harness_d.render(values={
    f"{prefix_d}_next_followup_date": date(2026, 8, 9),
    f"{prefix_d}_lead_status": "interested",
    f"{prefix_d}_priority": "VIP",
    f"{prefix_d}_followup_note": "Updated note",
})
result_d = harness_d.render(clicks=_submit_click(prefix_d))
assert result_d == "rerun", (result_d, harness_d.errors, harness_d.order_writes, harness_d.followup_writes)
order_payload_d, order_items_d = harness_d.order_writes[0]
assert order_payload_d["order_id"] == "ORDER-D"
assert order_payload_d["customer_name"] == "Customer Draft"
assert order_payload_d["phone1"] == "0899999999"
assert order_items_d[0]["qty"] == 2
assert order_items_d[0]["amount"] == 120.0
assert harness_d.followup_writes[0]["next_followup_date"] == "2026-08-09"

# Scenario D2: after saving a new order row, follow-up metadata must attach
# to the crm_data_imports record returned by the order save result. The
# follow-up table joins on customer_id:<id>, so keeping the old row key makes
# the selected date appear to disappear after the table reloads.
harness_d2 = _DialogHarness(sample_row)
harness_d2.saved_record_ids = ["901", "902"]
prefix_d2 = harness_d2.prefix
harness_d2.render()
harness_d2.state[f"{prefix_d2}_items"] = [
    dict(harness_d2.product, qty=1, amount="120"),
    {
        "sku": "SP681",
        "product_name": "Tea Economy",
        "product_group": "Drink",
        "image_url": "",
        "qty": 1,
        "amount": "80",
    },
]
result_d2 = harness_d2.render(
    values={
        **_valid_order_values(prefix_d2, order_id="ORDER-D2"),
        f"{prefix_d2}_next_followup_date": date(2026, 8, 10),
    },
    clicks=_submit_click(prefix_d2),
)
assert result_d2 == "rerun", (result_d2, harness_d2.errors, harness_d2.followup_writes)
assert harness_d2.followup_writes[0]["crm_data_import_id"] == "902"
assert harness_d2.followup_writes[0]["customer_id"] == "902"
assert harness_d2.followup_writes[0]["customer_key"] == "customer_id:902"
assert harness_d2.followup_writes[0]["order_id"] == "ORDER-D2"
assert harness_d2.followup_writes[0]["sku"] == "SP681"
assert harness_d2.followup_writes[0]["product_name"] == "Tea Economy"
assert harness_d2.followup_writes[0]["next_followup_date"] == "2026-08-10"

# Scenario E: order fields before product selection remain in captured order payload.
harness_e = _DialogHarness(sample_row)
prefix_e = harness_e.prefix
harness_e.render(values=_valid_order_values(prefix_e, order_id="ORDER-E"))
assert harness_e.render(clicks={f"{prefix_e}_open_product_picker"}) == "rerun"
assert harness_e.render(picker_select=True) == "rerun"
assert harness_e.render(values={f"{prefix_e}_item_qty_0": 2, f"{prefix_e}_item_amount_0": "130"}, clicks=_submit_click(prefix_e)) == "rerun"
order_payload_e, order_items_e = harness_e.order_writes[0]
assert order_payload_e["order_id"] == "ORDER-E"
assert order_payload_e["customer_name"] == "Customer Draft"
assert order_items_e[0]["sku"] == "SP680"
assert order_items_e[0]["amount"] == 130.0

# Scenario F: order save failure never writes follow-up data.
harness_f = _DialogHarness(sample_row)
prefix_f = harness_f.prefix
harness_f.order_fail = True
harness_f.render()
harness_f.state[f"{prefix_f}_items"] = [dict(harness_f.product, qty=1, amount="120")]
assert harness_f.render(values=_valid_order_values(prefix_f), clicks=_submit_click(prefix_f)) == "ok"
assert len(harness_f.order_writes) == 0
assert len(harness_f.followup_writes) == 0

# Scenario G: follow-up failure leaves state open and does not clear/close/rerun success.
harness_g = _DialogHarness(sample_row)
prefix_g = harness_g.prefix
harness_g.followup_fail = True
harness_g.render()
harness_g.state[f"{prefix_g}_items"] = [dict(harness_g.product, qty=1, amount="120")]
assert harness_g.render(values=_valid_order_values(prefix_g), clicks=_submit_click(prefix_g)) == "ok"
assert len(harness_g.order_writes) == 1
assert len(harness_g.followup_writes) == 1
assert harness_g.cache_clears == 0
assert harness_g.closes == 0
assert harness_g.reruns == 0
assert harness_g.state.get(f"{prefix_g}_ready") is True

# Scenario H: full success writes once each, clears once, closes once, reruns once.
harness_h = _DialogHarness(sample_row)
prefix_h = harness_h.prefix
harness_h.render()
harness_h.state[f"{prefix_h}_items"] = [dict(harness_h.product, qty=1, amount="0")]
assert harness_h.render(values=_valid_order_values(prefix_h, amount="0"), clicks=_submit_click(prefix_h)) == "rerun"
assert len(harness_h.order_writes) == 1
assert len(harness_h.followup_writes) == 1
assert harness_h.cache_clears == 1
assert harness_h.closes == 1
assert harness_h.reruns == 1

st.session_state.clear()
print("follow-up note/date/product picker behavioral checks OK")

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

# ---------------------------------------------------------------------------
# 11. Regression: no unconditional st.rerun() in ui/manual_order_ui.py.
#
# A bare st.rerun() sitting directly in a function's top-level body (not
# nested inside any if/for/while) fires on EVERY render of that function.
# For render_manual_product_selector_dialog -- called on every script rerun
# whenever the picker is open -- that is a self-triggering rerun loop: it
# reruns, which renders the function again, which reruns again, forever.
#
# This shipped once: the "ปิด" (close) button's st.rerun() was left at the
# same indentation as its guarding `if`, instead of inside it, so it fired
# unconditionally right after the conditional one, on every single render.
# Symptom in production: typing in the product search box felt laggy, and
# under an added @st.fragment (since reverted) the picker hung outright.
# ---------------------------------------------------------------------------
def unconditional_reruns(source: str) -> list[tuple[str, int]]:
    """Function name + line number of any st.rerun() sitting directly in a
    function's top-level body, i.e. not guarded by any if/for/while."""
    tree = ast.parse(source)
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            for stmt in node.body:
                is_rerun_call = (
                    isinstance(stmt, ast.Expr)
                    and isinstance(stmt.value, ast.Call)
                    and isinstance(stmt.value.func, ast.Attribute)
                    and stmt.value.func.attr == "rerun"
                )
                if is_rerun_call:
                    found.append((node.name, stmt.lineno))
    return found


manual_unconditional_reruns = unconditional_reruns(manual_source)
assert manual_unconditional_reruns == [], (
    "unconditional st.rerun() found in ui/manual_order_ui.py -- fires on "
    f"every render of its function, causing a rerun loop: {manual_unconditional_reruns}"
)

followup_unconditional_reruns = unconditional_reruns(followup_source)
assert followup_unconditional_reruns == [], (
    "unconditional st.rerun() found in pages/followup.py -- fires on "
    f"every render of its function, causing a rerun loop: {followup_unconditional_reruns}"
)

print("no unconditional st.rerun() in ui/manual_order_ui.py or pages/followup.py OK")

print("order dialog workflows safety OK")
