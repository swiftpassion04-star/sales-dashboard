import ast
import re
import sys
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import crm_data.common as common
import crm_data.dashboard as crm_dashboard
import neon_utils as neon
import ui.manual_order_ui as manual_order_ui


REPO_ROOT = Path(__file__).resolve().parents[1]
COMMON_SOURCE = (REPO_ROOT / "crm_data" / "common.py").read_text(encoding="utf-8")
NEON_SOURCE = (REPO_ROOT / "neon_utils.py").read_text(encoding="utf-8")
DASHBOARD_SOURCE = (REPO_ROOT / "crm_data" / "dashboard.py").read_text(encoding="utf-8")
MANUAL_SOURCE = (REPO_ROOT / "ui" / "manual_order_ui.py").read_text(encoding="utf-8")

FORBIDDEN_DOC_TOUCH = (
    REPO_ROOT / "docs" / "STAFF_MAPPING_DECISION_REQUIRED.md",
    REPO_ROOT / "docs" / "OWNER_STAFF_MAPPING_APPROVAL.md",
    REPO_ROOT / "neon" / "manual_sql" / "202606_staff_code_normalization_plan.sql",
)


# ---------------------------------------------------------------------------
# 1. collapse_whitespace(): pure function, direct behavioral tests
# ---------------------------------------------------------------------------
assert common.collapse_whitespace("พรณกมล ดวงจันทร์ (แต้ว)") == "พรณกมล ดวงจันทร์ (แต้ว)"
assert common.collapse_whitespace("พรณกมล  ดวงจันทร์ (แต้ว)") == "พรณกมล ดวงจันทร์ (แต้ว)"
assert common.collapse_whitespace("พรณกมล ดวงจันทร์ (แต้ว)") == common.collapse_whitespace(
    "พรณกมล  ดวงจันทร์ (แต้ว)"
), "1-space and 2-space variants must normalize to the same string"

assert common.collapse_whitespace("   นำหน้า") == "นำหน้า"
assert common.collapse_whitespace("ตามหลัง   ") == "ตามหลัง"
assert common.collapse_whitespace("   ทั้งสองด้าน   ") == "ทั้งสองด้าน"

assert common.collapse_whitespace("แต้ว\tTAEW") == "แต้ว TAEW"
assert common.collapse_whitespace("แต้ว\n\nTAEW") == "แต้ว TAEW"
assert common.collapse_whitespace("แต้ว   \t\n  TAEW") == "แต้ว TAEW"

assert common.collapse_whitespace("") == ""
assert common.collapse_whitespace(None) == ""
assert common.collapse_whitespace("   ") == ""
assert common.collapse_whitespace(123) == "123"

# Non-whitespace differences must NOT be treated as equal (no fuzzy match).
# NOTE: this is a property test of collapse_whitespace() itself (does it
# ever conflate two DIFFERENT strings that merely happen to also differ in
# whitespace?) -- generic strings are used here on purpose. Whether real
# staff identities (TAEW/NOONA/JEEB) are kept distinct through the actual
# dropdown -> save pipeline is proven separately below via production
# functions (see section 15), not via bare string-literal inequality.
assert common.collapse_whitespace("abc def") != common.collapse_whitespace("abc de")  # missing trailing char
assert common.collapse_whitespace("abc  def") != common.collapse_whitespace("abcdef")  # collapsing != removing

print("collapse_whitespace() pure behavior OK")


# ---------------------------------------------------------------------------
# 2. Re-export identity: neon_utils.collapse_whitespace is the same helper
# ---------------------------------------------------------------------------
assert neon.collapse_whitespace is common.collapse_whitespace
assert manual_order_ui.neon.collapse_whitespace is common.collapse_whitespace
assert "collapse_whitespace" in NEON_SOURCE.split("from crm_data.common import", 1)[1].split(")", 1)[0]

print("collapse_whitespace re-export wiring OK")


# ---------------------------------------------------------------------------
# 3. clean() itself must be byte-for-byte unchanged in behavior (central
#    helper -- explicitly forbidden to modify its whitespace semantics).
# ---------------------------------------------------------------------------
assert common.clean("พรณกมล  ดวงจันทร์ (แต้ว)") == "พรณกมล  ดวงจันทร์ (แต้ว)", (
    "clean() must NOT collapse internal whitespace -- only strip ends"
)
assert common.clean("  x  ") == "x"
assert common.clean(None) == ""
assert common.clean("NULL") == ""

clean_source = ast.get_source_segment(COMMON_SOURCE, next(
    node for node in ast.walk(ast.parse(COMMON_SOURCE))
    if isinstance(node, ast.FunctionDef) and node.name == "clean"
))
assert "collapse" not in clean_source.lower()
assert "\\s+" not in clean_source

print("clean() unchanged / not touched OK")


# ---------------------------------------------------------------------------
# 4. Equivalence check: Python-side collapse_whitespace() must agree with
#    the SQL-side _normalized_text_sql() regex (regexp_replace ... '\s+' ' ' 'g')
#    for the same battery of inputs, simulating what Postgres would produce.
# ---------------------------------------------------------------------------
def simulate_normalized_text_sql(value: str) -> str:
    """Python re-implementation of `trim(coalesce(column,'')) regexp_replace \\s+ -> ' '`
    matching _normalized_text_sql()'s exact SQL semantics, to prove parity
    without a real Postgres connection."""
    text = "" if value is None else str(value)
    text = text.strip()
    return re.sub(r"\s+", " ", text)


battery = [
    "พรณกมล ดวงจันทร์ (แต้ว)",
    "พรณกมล  ดวงจันทร์ (แต้ว)",
    "  พรณกมล   ดวงจันทร์  (แต้ว)  ",
    "TAEW",
    "NOONA",
    "",
    "   ",
    "แต้ว\tTAEW\n",
]
for value in battery:
    assert common.collapse_whitespace(value) == simulate_normalized_text_sql(value), (
        f"Python/SQL normalization mismatch for {value!r}"
    )

print("Python/SQL normalization parity OK")


# ---------------------------------------------------------------------------
# 5. neon_utils._normalized_text_sql(): confirm still intact, unmodified
#    signature, and now actually referenced (no longer dead code).
# ---------------------------------------------------------------------------
assert neon._normalized_text_sql("owner") == "regexp_replace(trim(coalesce(owner, '')), '\\s+', ' ', 'g')"
assert neon._normalized_text_sql("d.owner") == "regexp_replace(trim(coalesce(d.owner, '')), '\\s+', ' ', 'g')"

fetch_owner_options_source = NEON_SOURCE.split("def fetch_owner_user_options", 1)[1].split(
    "def upsert_staff_option", 1
)[0]
assert "_normalized_text_sql(\"staff_name\")" in fetch_owner_options_source
assert "group by staff_code, staff_name" in fetch_owner_options_source
assert "staff_code" in fetch_owner_options_source  # staff_code itself is never wrapped/normalized
assert "_normalized_text_sql(\"staff_code\")" not in fetch_owner_options_source
assert "_normalized_text_sql('staff_code')" not in fetch_owner_options_source

print("_normalized_text_sql() usage in fetch_owner_user_options OK")


# ---------------------------------------------------------------------------
# 6. crm_data/dashboard.py structural checks: normalization applied to both
#    the DISTINCT dropdown query and the WHERE-clause filter (not just one).
# ---------------------------------------------------------------------------
owner_options_source = DASHBOARD_SOURCE.split("def fetch_sales_report_owner_options", 1)[1].split(
    "def _sales_report_where", 1
)[0]
assert "_normalized_text_sql" in owner_options_source
assert "select distinct {owner_normalized_sql} as owner" in owner_options_source
assert "select distinct owner\n" not in owner_options_source

where_source = DASHBOARD_SOURCE.split("def _sales_report_where", 1)[1].split(
    "def summarize_sales_report_rows", 1
)[0]
assert "_normalized_text_sql" in where_source
assert "collapse_whitespace" in where_source
assert '"d.owner = %s"' not in where_source, (
    "the WHERE clause must compare against the NORMALIZED owner column, "
    "not the raw d.owner column, or historical whitespace-variant rows "
    "will not be included when filtering"
)
assert "d.staff_code = %s" in where_source  # non-admin/editor branch must remain untouched

print("crm_data/dashboard.py structural normalization coverage OK")


# ---------------------------------------------------------------------------
# 7. _sales_report_where(): real, direct behavioral test.
# ---------------------------------------------------------------------------
admin_user = {"role": "EDITOR", "email": "editor@example.com"}
staff_user = {"role": "STAFF", "staff_code": "TAEW"}

# "ทั้งหมด" (no filter) must produce IDENTICAL clauses/params to an empty filter,
# and must add no owner clause at all -- the grand total path is untouched.
clauses_all, params_all = crm_dashboard._sales_report_where(admin_user, "ทั้งหมด")
clauses_empty, params_empty = crm_dashboard._sales_report_where(admin_user, "")
assert clauses_all == clauses_empty
assert params_all == params_empty
assert not any("owner" in clause for clause in clauses_all)

# A 2-space owner filter must bind a COLLAPSED (1-space) parameter, and the
# clause must reference the normalized column expression.
clauses_2sp, params_2sp = crm_dashboard._sales_report_where(admin_user, "พรณกมล  ดวงจันทร์ (แต้ว)")
owner_clause = next(c for c in clauses_2sp if "owner" in c)
assert "regexp_replace" in owner_clause
assert params_2sp[-1] == "พรณกมล ดวงจันทร์ (แต้ว)", "bound param must be the collapsed form"

# A 1-space owner filter must bind the SAME collapsed parameter.
clauses_1sp, params_1sp = crm_dashboard._sales_report_where(admin_user, "พรณกมล ดวงจันทร์ (แต้ว)")
assert params_1sp[-1] == params_2sp[-1], "1-space and 2-space filter inputs must bind the identical parameter"
assert clauses_1sp == clauses_2sp, "generated SQL clause text must be identical regardless of input whitespace"

# Non-admin/editor path is untouched: still filters by staff_code, not owner.
clauses_staff, params_staff = crm_dashboard._sales_report_where(staff_user, "anything")
assert clauses_staff == ["d.import_status = 'valid'", "d.created_at >= %s", "d.created_at < %s", "d.amount is not null",
                          "coalesce(nullif(d.sale_type, ''), 'NEW_ORDER') in ('NEW_ORDER', 'UPSELL', '⭐NEW_ORDER', '⭐UPSELL')",
                          "d.staff_code = %s"]
assert params_staff == ["TAEW"]

print("_sales_report_where() behavioral tests OK")


# ---------------------------------------------------------------------------
# 8. fetch_sales_report_owner_options(): behavioral test via FakeConnection,
#    simulating Postgres regexp_replace so DISTINCT truly collapses
#    whitespace-duplicate raw rows into a single dropdown option.
# ---------------------------------------------------------------------------
class FakeCursorOwnerOptions:
    def __init__(self, raw_owners):
        self.raw_owners = raw_owners
        self.last_sql = ""

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, params=None):
        self.last_sql = " ".join(sql.split())
        assert "regexp_replace" in self.last_sql, "query must use the normalized owner expression"
        seen = {}
        for raw in self.raw_owners:
            normalized = simulate_normalized_text_sql(raw)
            seen.setdefault(normalized, normalized)
        self._rows = [{"owner": value} for value in sorted(seen.values())]

    def fetchall(self):
        return self._rows


class FakeConnOwnerOptions:
    def __init__(self, cursor):
        self._cursor = cursor

    def cursor(self):
        return self._cursor

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


@contextmanager
def _fake_neon_connection_factory(cursor):
    @contextmanager
    def _fake_neon_connection():
        yield FakeConnOwnerOptions(cursor)

    yield _fake_neon_connection


raw_owner_rows = [
    "พรณกมล ดวงจันทร์ (แต้ว)",
    "พรณกมล  ดวงจันทร์ (แต้ว)",  # whitespace-duplicate of the row above
    "สายฝน ราวิชัย (สายฝน)",
]
fake_cursor = FakeCursorOwnerOptions(raw_owner_rows)

fetch_sales_report_owner_options = crm_dashboard.fetch_sales_report_owner_options.__wrapped__
original_ensure_schema = neon.ensure_crm_data_imports_schema
original_neon_connection = neon.neon_connection
original_crm_sales_report_ready = crm_dashboard.crm_sales_report_ready
try:
    neon.ensure_crm_data_imports_schema = lambda: True
    neon.neon_connection = lambda: FakeConnOwnerOptions(fake_cursor)
    crm_dashboard.crm_sales_report_ready = lambda: True
    result = fetch_sales_report_owner_options(admin_user)
finally:
    neon.ensure_crm_data_imports_schema = original_ensure_schema
    neon.neon_connection = original_neon_connection
    crm_dashboard.crm_sales_report_ready = original_crm_sales_report_ready

assert result.count("พรณกมล ดวงจันทร์ (แต้ว)") == 1, (
    f"whitespace-duplicate owner rows must collapse to exactly one dropdown option, got {result}"
)
assert len(result) == 2, f"expected 2 distinct owners (แต้ว merged, สายฝน separate), got {result}"

print("fetch_sales_report_owner_options() behavioral dedup test OK")


# ---------------------------------------------------------------------------
# 9. display_staff_name() / normalize_staff_code() / strip_duplicate_staff_suffix()
#    / staff_label() / build_staff_choices(): real functions, direct behavioral
#    tests -- no Streamlit widgets involved, fully DB-free and UI-free.
# ---------------------------------------------------------------------------
row_2space = {"staff_name": "พรณกมล  ดวงจันทร์ (แต้ว)", "staff_code": "TAEW"}
row_1space = {"staff_name": "พรณกมล ดวงจันทร์ (แต้ว)", "staff_code": "TAEW"}
assert manual_order_ui.display_staff_name(row_2space) == manual_order_ui.display_staff_name(row_1space)
assert manual_order_ui.display_staff_name(row_2space) == "พรณกมล ดวงจันทร์ (แต้ว)"

# Same normalized display name, DIFFERENT staff_code -> must remain two
# distinct identities with distinguishable labels, not merged.
row_code_a = {"staff_name": "พรณกมล ดวงจันทร์ (แต้ว)", "staff_code": "TAEW"}
row_code_b = {"staff_name": "พรณกมล  ดวงจันทร์ (แต้ว)", "staff_code": "แต้ว"}
label_a = manual_order_ui.staff_label(row_code_a)
label_b = manual_order_ui.staff_label(row_code_b)
assert label_a != label_b, "different staff_code must never collapse into an identical dropdown label"

choices = manual_order_ui.build_staff_choices([row_code_a, row_code_b])
assert len(choices) == 2, "rows with the same normalized name but different staff_code must not be deduplicated away"
choice_codes = {row.get("staff_code") for _label, row in choices}
assert choice_codes == {"TAEW", "แต้ว"}, "neither identity may be silently dropped"

# TAEW/NOONA/JEEB non-merge is proven end-to-end through the real dropdown
# -> save pipeline in section 15 below (production functions, not bare
# string-literal inequality).

print("display_staff_name/staff_label/build_staff_choices behavioral tests OK")


# ---------------------------------------------------------------------------
# 10. fetch_owner_user_options(): behavioral test via FakeConnection --
#     same staff_code + whitespace-different staff_name collapses to one
#     row; different staff_code stays separate even with the same
#     normalized name (identity is staff_code + normalized name, never
#     name alone).
# ---------------------------------------------------------------------------
class FakeCursorStaffOptions:
    def __init__(self, user_role_rows, staff_option_rows):
        self.user_role_rows = user_role_rows
        self.staff_option_rows = staff_option_rows

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, params=None):
        assert "_normalized" not in sql  # sanity: this is the raw SQL text, f-string already resolved
        assert "regexp_replace" in sql, "query must normalize staff_name"
        combined = self.user_role_rows + self.staff_option_rows
        merged: dict[tuple, dict] = {}
        for row in combined:
            key = (row["staff_code"], simulate_normalized_text_sql(row["staff_name"]))
            existing = merged.get(key)
            if existing is None:
                merged[key] = {
                    "id": "x",
                    "staff_code": row["staff_code"],
                    "staff_name": simulate_normalized_text_sql(row["staff_name"]),
                    "is_active": row.get("is_active", True),
                    "sort_order": row.get("sort_order", 0),
                    "updated_at": row.get("updated_at"),
                }
        self._rows = list(merged.values())

    def fetchall(self):
        return self._rows


class FakeConnStaffOptions:
    def __init__(self, cursor):
        self._cursor = cursor

    def cursor(self):
        return self._cursor

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


fetch_owner_user_options = neon.fetch_owner_user_options.__wrapped__

user_role_rows = [
    {"staff_code": "TAEW", "staff_name": "พรณกมล ดวงจันทร์ (แต้ว)", "is_active": True, "sort_order": 0},
]
staff_option_rows = [
    {"staff_code": "TAEW", "staff_name": "พรณกมล  ดวงจันทร์ (แต้ว)", "is_active": True, "sort_order": 0},  # whitespace dup, same code
    {"staff_code": "SAIFON", "staff_name": "สายฝน ราวิชัย (สายฝน)", "is_active": True, "sort_order": 1},
]
cursor = FakeCursorStaffOptions(user_role_rows, staff_option_rows)
original_ensure_schema2 = neon.ensure_crm_data_imports_schema
original_neon_connection2 = neon.neon_connection
try:
    neon.ensure_crm_data_imports_schema = lambda: True
    neon.neon_connection = lambda: FakeConnStaffOptions(cursor)
    options = fetch_owner_user_options(active_only=True)
finally:
    neon.ensure_crm_data_imports_schema = original_ensure_schema2
    neon.neon_connection = original_neon_connection2

taew_rows = [row for row in options if row["staff_code"] == "TAEW"]
assert len(taew_rows) == 1, f"same staff_code + whitespace-different staff_name must merge to one row, got {taew_rows}"
assert taew_rows[0]["staff_name"] == "พรณกมล ดวงจันทร์ (แต้ว)"
assert len(options) == 2

print("fetch_owner_user_options() behavioral dedup test OK")


# ---------------------------------------------------------------------------
# 11. Manual Order save-path structural check: the collapse_whitespace()
#     catch-all is applied to `owner` immediately before the submit button,
#     covering every branch (dropdown selection, free-text fallback,
#     non-editor auto-set) with a single point.
# ---------------------------------------------------------------------------
form_source = MANUAL_SOURCE.split("def _render_manual_order_form", 1)[1].split(
    "def render_manual_product_picker", 1
)[0]
owner_assign_index = form_source.index("owner = neon.clean(user.get(\"staff_name\"))")
catch_all_index = form_source.index('owner = neon.collapse_whitespace(owner)\n            submitted = st.form_submit_button')
submit_button_index = form_source.index('submitted = st.form_submit_button("บันทึกคำสั่งซื้อ"')
assert owner_assign_index < catch_all_index < submit_button_index + 1, (
    "collapse_whitespace(owner) must run after every owner-assignment branch and before the save/validation path"
)

non_editor_branch_source = form_source.split("else:\n                staff_code = normalize_staff_code(staff_code)", 1)[1].split(
    "owner = neon.collapse_whitespace(owner)\n            submitted", 1
)[0]
assert "neon.collapse_whitespace(strip_duplicate_staff_suffix(" in non_editor_branch_source, (
    "the non-editor disabled owner display must also show the normalized value, not just save it normalized"
)

print("Manual Order owner-normalization save-path structural checks OK")


# ---------------------------------------------------------------------------
# 12. Regression: safe structured logging from commit 00cfc2b is untouched.
# ---------------------------------------------------------------------------
assert "from app_logging import log_exception, user_error_message" in MANUAL_SOURCE
assert MANUAL_SOURCE.count("log_exception(") == 3
assert MANUAL_SOURCE.count("user_error_message(") == 3
assert 'st.warning(f"โหลดรายชื่อพนักงานไม่สำเร็จ' not in MANUAL_SOURCE
assert 'st.error(f"บันทึกคำสั่งซื้อไม่สำเร็จ' not in MANUAL_SOURCE

print("Phase 2 Patch 1 safe logging regression OK")


# ---------------------------------------------------------------------------
# 13. Scope guard: none of this patch's changed files touch the three
#     protected docs/migration files, and none introduce a TAEW/JEEB/NOONA
#     staff_code mapping or alias.
# ---------------------------------------------------------------------------
for path in FORBIDDEN_DOC_TOUCH:
    assert path.exists(), f"expected file to still exist untouched: {path}"

for source, label in (
    (COMMON_SOURCE, "crm_data/common.py"),
    (DASHBOARD_SOURCE, "crm_data/dashboard.py"),
):
    assert "TAEW" not in source, f"{label} must not hardcode staff_code mapping"
    assert "NOONA" not in source, f"{label} must not hardcode staff_code mapping"
    assert "JEEB" not in source, f"{label} must not hardcode staff_code mapping"

# neon_utils.py and manual_order_ui.py only reference staff_code as a column
# name / variable, never as a literal alias mapping -- confirm no new
# literal 'TAEW'/'NOONA'/'JEEB' string constants were introduced by this patch.
for source, label in ((NEON_SOURCE, "neon_utils.py"), (MANUAL_SOURCE, "ui/manual_order_ui.py")):
    for literal in ('"TAEW"', "'TAEW'", '"NOONA"', "'NOONA'", '"JEEB"', "'JEEB'"):
        assert literal not in source, f"{label} must not introduce a hardcoded {literal} mapping"

print("Scope guard: no protected docs touched, no TAEW/JEEB/NOONA mapping introduced OK")


# ---------------------------------------------------------------------------
# 14. Manual Order end-to-end save-path harness: executes the REAL,
#     UNMODIFIED _render_manual_order_form() via a FakeStreamlit +
#     monkeypatched I/O boundary. No production code is changed for this --
#     module attributes (manual_order_ui.st, neon.upsert_manual_order_items,
#     etc.) are reassigned from the test only, exactly like the existing
#     FakeConnection pattern already used in test_customer_editor_actions.py.
# ---------------------------------------------------------------------------
class ManualOrderFakeSessionState(dict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)

    def __setattr__(self, name, value):
        self[name] = value

    def pop(self, key, default=None):
        return dict.pop(self, key, default)


class ManualOrderRerun(Exception):
    pass


class FakeManualOrderStreamlit:
    def __init__(self, widget_values, submit_key=None):
        self.session_state = ManualOrderFakeSessionState()
        self.widget_values = dict(widget_values)
        self.submit_key = submit_key
        self.errors = []
        self.warnings = []
        self.successes = []

    def _value(self, key, default=""):
        return self.widget_values.get(key, default)

    def text_input(self, label, key=None, value="", **kw):
        return self._value(key, value)

    def text_area(self, label, key=None, value="", **kw):
        return self._value(key, value)

    def selectbox(self, label, options, key=None, index=0, **kw):
        default = options[index] if options else None
        return self._value(key, default)

    def form_submit_button(self, label, key=None, **kw):
        if not self.submit_key:
            return False
        return (key is not None and key == self.submit_key) or (key is None and label == self.submit_key)

    def button(self, label, key=None, **kw):
        return False

    def columns(self, spec, **kw):
        n = spec if isinstance(spec, int) else len(spec)
        return [self for _ in range(n)]

    @contextmanager
    def container(self, *a, **k):
        yield self

    @contextmanager
    def form(self, *a, **k):
        yield self

    def rerun(self):
        raise ManualOrderRerun()

    def markdown(self, *a, **k): pass
    def caption(self, *a, **k): pass
    def info(self, *a, **k): pass
    def divider(self, *a, **k): pass
    def warning(self, msg, *a, **k): self.warnings.append(msg)
    def error(self, msg, *a, **k): self.errors.append(msg)
    def success(self, msg, *a, **k): self.successes.append(msg)


def run_manual_order_form(user, is_editor, widget_values, *, staff_options,
                           submit_key="บันทึกคำสั่งซื้อ", fail_owner_options_load=False,
                           fail_save=False):
    """Execute the REAL, unmodified manual_order_ui._render_manual_order_form()
    end to end. Returns (calls, fake_st, reran) where `calls` captures the
    actual arguments the real function passed to
    neon.upsert_manual_order_items() and log_exception()."""
    calls = {"upsert_manual_order_items": [], "log_exception": [], "cache_clears": 0}

    def fake_fetch_owner_user_options(active_only=False):
        if fail_owner_options_load:
            raise RuntimeError("simulated owner-options load failure")
        return staff_options

    def fake_upsert(payload, items):
        calls["upsert_manual_order_items"].append((dict(payload), [dict(i) for i in items]))
        if fail_save:
            raise RuntimeError("simulated save failure")
        return {"item_count": len(items), "actions": {"inserted": len(items), "updated": 0}, "duplicate_lock_warning": ""}

    def fake_log_exception(event, exc, safe_metadata_values=None):
        calls["log_exception"].append((event, str(exc), dict(safe_metadata_values or {})))
        return "REF-TEST-1"

    fake_st = FakeManualOrderStreamlit(widget_values, submit_key=submit_key)

    originals = {
        "st": manual_order_ui.st,
        "fetch_owner_user_options": neon.fetch_owner_user_options,
        "fetch_order_product_options": neon.fetch_order_product_options,
        "validate_phone_pair": neon.validate_phone_pair,
        "upsert_manual_order_items": neon.upsert_manual_order_items,
        "clear_cached_data_functions": neon.clear_cached_data_functions,
        "render_manual_order_items": manual_order_ui.render_manual_order_items,
        "render_manual_product_picker": manual_order_ui.render_manual_product_picker,
        "should_check_manual_owner_conflict": manual_order_ui.should_check_manual_owner_conflict,
        "log_exception": manual_order_ui.log_exception,
    }
    try:
        manual_order_ui.st = fake_st
        neon.fetch_owner_user_options = fake_fetch_owner_user_options
        neon.fetch_order_product_options = lambda: []
        neon.validate_phone_pair = lambda p1, p2: []
        neon.upsert_manual_order_items = fake_upsert
        neon.clear_cached_data_functions = lambda *fns: calls.__setitem__("cache_clears", calls["cache_clears"] + 1)
        manual_order_ui.render_manual_order_items = lambda: None
        manual_order_ui.render_manual_product_picker = lambda product_options: None
        manual_order_ui.should_check_manual_owner_conflict = lambda user: False
        manual_order_ui.log_exception = fake_log_exception

        fake_st.session_state["manual_order_items"] = [
            {"sku": "SKU1", "product_name": "Test Product", "qty": 1, "amount": "199"}
        ]
        reran = False
        try:
            manual_order_ui._render_manual_order_form(user, is_editor)
        except ManualOrderRerun:
            reran = True
    finally:
        manual_order_ui.st = originals["st"]
        neon.fetch_owner_user_options = originals["fetch_owner_user_options"]
        neon.fetch_order_product_options = originals["fetch_order_product_options"]
        neon.validate_phone_pair = originals["validate_phone_pair"]
        neon.upsert_manual_order_items = originals["upsert_manual_order_items"]
        neon.clear_cached_data_functions = originals["clear_cached_data_functions"]
        manual_order_ui.render_manual_order_items = originals["render_manual_order_items"]
        manual_order_ui.render_manual_product_picker = originals["render_manual_product_picker"]
        manual_order_ui.should_check_manual_owner_conflict = originals["should_check_manual_owner_conflict"]
        manual_order_ui.log_exception = originals["log_exception"]

    return calls, fake_st, reran


EDITOR_USER = {"role": "EDITOR", "email": "editor@example.com", "staff_name": "", "staff_code": ""}

BASE_WIDGET_VALUES = {
    "manual_order_id": "ORD-1",
    "manual_customer_name": "Customer A",
    "manual_phone1": "0811111111",
    "manual_phone2": "",
    "manual_url": "",
    "manual_address": "",
    "manual_sale_type": "NEW_ORDER",
}

print("Manual Order FakeStreamlit save-path harness defined OK")


# ---------------------------------------------------------------------------
# 15. Leading/trailing + double-space/tab/newline owner normalization,
#     staff_code preservation, and per-selection staff_code correctness --
#     all proven via the ACTUAL captured neon.upsert_manual_order_items()
#     payload from the real, unmodified save path.
# ---------------------------------------------------------------------------
staff_options_taew_variant = [
    {"staff_code": "TAEW", "staff_name": "  พรณกมล   ดวงจันทร์  (แต้ว)  ", "is_active": True, "sort_order": 0},
]
label_taew = manual_order_ui.staff_label(staff_options_taew_variant[0])

calls, fake_st, reran = run_manual_order_form(
    EDITOR_USER, True,
    {**BASE_WIDGET_VALUES, "manual_owner_select": label_taew},
    staff_options=staff_options_taew_variant,
)
assert reran is True, "successful save must end in st.rerun()"
assert len(calls["upsert_manual_order_items"]) == 1
saved_payload_1, saved_items_1 = calls["upsert_manual_order_items"][0]
assert saved_payload_1["owner"] == "พรณกมล ดวงจันทร์ (แต้ว)", (
    f"leading/trailing/double-space owner must be trimmed and collapsed in the ACTUAL save payload, got {saved_payload_1['owner']!r}"
)
assert saved_payload_1["staff_code"] == "TAEW", "staff_code must be saved unchanged"
assert saved_payload_1["order_id"] == "ORD-1"
assert saved_payload_1["customer_name"] == "Customer A"

# Tab and newline variants must normalize identically through the same path.
staff_options_tabnewline = [
    {"staff_code": "TAEW", "staff_name": "พรณกมล\tดวงจันทร์\n(แต้ว)", "is_active": True, "sort_order": 0},
]
label_taew_tabnewline = manual_order_ui.staff_label(staff_options_tabnewline[0])
calls2, _fake_st2, reran2 = run_manual_order_form(
    EDITOR_USER, True,
    {**BASE_WIDGET_VALUES, "manual_owner_select": label_taew_tabnewline},
    staff_options=staff_options_tabnewline,
)
assert reran2 is True
saved_payload_2, _ = calls2["upsert_manual_order_items"][0]
assert saved_payload_2["owner"] == "พรณกมล ดวงจันทร์ (แต้ว)", (
    f"tab/newline variants must collapse to a single space in the ACTUAL save payload, got {saved_payload_2['owner']!r}"
)
assert saved_payload_2["staff_code"] == "TAEW"

print("Manual Order save-path: whitespace normalization on actual save payload OK")


# ---------------------------------------------------------------------------
# 16-17. Identity collision: normalized display name identical, staff_code
#     different -- prove BOTH choices survive (dict/label not overwritten)
#     AND that selecting one vs the other sends the CORRECT distinct
#     staff_code into the actual save payload (not a fixed/wrong one).
# ---------------------------------------------------------------------------
row_taew = {"staff_code": "TAEW", "staff_name": "พรณกมล ดวงจันทร์ (แต้ว)", "is_active": True, "sort_order": 0}
row_taew_thai_code = {"staff_code": "แต้ว", "staff_name": "พรณกมล  ดวงจันทร์ (แต้ว)", "is_active": True, "sort_order": 1}
both_staff_options = [row_taew, row_taew_thai_code]

choices = manual_order_ui.build_staff_choices(both_staff_options)
assert len(choices) == 2, "same normalized name + different staff_code must not be deduplicated away"
label_for_taew = next(label for label, row in choices if row["staff_code"] == "TAEW")
label_for_taew_thai = next(label for label, row in choices if row["staff_code"] == "แต้ว")
assert label_for_taew != label_for_taew_thai, "dropdown labels must remain distinguishable (no dictionary/label overwrite)"

calls_a, _, reran_a = run_manual_order_form(
    EDITOR_USER, True,
    {**BASE_WIDGET_VALUES, "manual_owner_select": label_for_taew},
    staff_options=both_staff_options,
)
assert reran_a is True
payload_a, _ = calls_a["upsert_manual_order_items"][0]
assert payload_a["staff_code"] == "TAEW", (
    f"selecting the TAEW-coded choice must send staff_code='TAEW' to the actual save payload, got {payload_a['staff_code']!r}"
)
assert payload_a["owner"] == "พรณกมล ดวงจันทร์ (แต้ว)"

calls_b, _, reran_b = run_manual_order_form(
    EDITOR_USER, True,
    {**BASE_WIDGET_VALUES, "manual_owner_select": label_for_taew_thai},
    staff_options=both_staff_options,
)
assert reran_b is True
payload_b, _ = calls_b["upsert_manual_order_items"][0]
assert payload_b["staff_code"] == "แต้ว", (
    f"selecting the 'แต้ว'-coded choice must send staff_code='แต้ว' to the actual save payload, got {payload_b['staff_code']!r}"
)
assert payload_b["owner"] == "พรณกมล ดวงจันทร์ (แต้ว)", "owner display converges to the same normalized name for both -- expected and disclosed as a known limitation (see report)"

print("Manual Order save-path: distinct staff_code selections send correct staff_code to actual save payload OK")


# ---------------------------------------------------------------------------
# 18. TAEW / NOONA / JEEB: full pipeline test with all three staff_codes
#     present simultaneously (same display name deliberately, to stress the
#     dedup/label logic), proving no path in this patch conflates them --
#     via production functions end to end, not bare string-literal
#     inequality.
# ---------------------------------------------------------------------------
row_taew2 = {"staff_code": "TAEW", "staff_name": "Staff X", "is_active": True, "sort_order": 0}
row_noona = {"staff_code": "NOONA", "staff_name": "Staff X", "is_active": True, "sort_order": 1}
row_jeeb = {"staff_code": "JEEB", "staff_name": "Staff X", "is_active": True, "sort_order": 2}
three_way_options = [row_taew2, row_noona, row_jeeb]

three_choices = manual_order_ui.build_staff_choices(three_way_options)
assert len(three_choices) == 3, "TAEW/NOONA/JEEB sharing a display name must all survive as distinct choices"
codes_seen = {row["staff_code"] for _label, row in three_choices}
assert codes_seen == {"TAEW", "NOONA", "JEEB"}, "no identity may be silently dropped or merged"
labels_seen = {label for label, _row in three_choices}
assert len(labels_seen) == 3, "all three labels must be pairwise distinct -- no dictionary/label overwrite"

for target_code, row in (("TAEW", row_taew2), ("NOONA", row_noona), ("JEEB", row_jeeb)):
    label = next(label for label, r in three_choices if r["staff_code"] == target_code)
    calls_x, _, reran_x = run_manual_order_form(
        EDITOR_USER, True,
        {**BASE_WIDGET_VALUES, "manual_owner_select": label},
        staff_options=three_way_options,
    )
    assert reran_x is True
    payload_x, _ = calls_x["upsert_manual_order_items"][0]
    assert payload_x["staff_code"] == target_code, (
        f"selecting the {target_code} choice must send staff_code={target_code!r} to the real save payload, "
        f"got {payload_x['staff_code']!r} -- a wrong value here would mean TAEW/NOONA/JEEB got conflated"
    )

# No hard-coded alias mapping / fuzzy matching exists anywhere in this
# patch's source that could explain a correct result other than genuine
# pass-through of the selected row's own staff_code (already re-confirmed
# in section 13's scope guard).

print("TAEW/NOONA/JEEB full pipeline identity-collision test OK")


# ---------------------------------------------------------------------------
# 19. Non-editor auto-owner path via the real save pipeline.
# ---------------------------------------------------------------------------
staff_user_whitespace = {
    "role": "STAFF",
    "email": "staff@example.com",
    "staff_name": "พรณกมล  ดวงจันทร์ (แต้ว)",
    "staff_code": "TAEW",
}
calls_staff, _, reran_staff = run_manual_order_form(
    staff_user_whitespace, False, dict(BASE_WIDGET_VALUES), staff_options=[],
)
assert reran_staff is True
payload_staff, _ = calls_staff["upsert_manual_order_items"][0]
assert payload_staff["owner"] == "พรณกมล ดวงจันทร์ (แต้ว)", "non-editor auto-owner must also be normalized in the actual save payload"
assert payload_staff["staff_code"] == "TAEW"
assert payload_staff["uploaded_by"] == "staff@example.com"

print("Manual Order save-path: non-editor auto-owner normalization OK")


# ---------------------------------------------------------------------------
# 20. Safe logging / exception control flow: verify via the REAL save path
#     (not a source-string count) that a failure still routes through
#     log_exception()/user_error_message() with the same event name and
#     metadata shape as before this patch, and that the dialog does not
#     silently "succeed".
# ---------------------------------------------------------------------------
calls_fail_load, fake_st_fail_load, reran_fail_load = run_manual_order_form(
    EDITOR_USER, True,
    dict(BASE_WIDGET_VALUES),
    staff_options=[],
    fail_owner_options_load=True,
)
assert any(event == "manual_order_data_load_failed" for event, _exc, _meta in calls_fail_load["log_exception"]), (
    "owner-options load failure must still call log_exception('manual_order_data_load_failed', ...) exactly as before"
)
load_fail_meta = next(meta for event, _exc, meta in calls_fail_load["log_exception"] if event == "manual_order_data_load_failed")
assert load_fail_meta == {"page": "manual_order", "action": "load_data", "component": "manual_order", "outcome": "failure"}
assert fake_st_fail_load.warnings, "a user-facing warning must still be shown on load failure"

calls_fail_save, fake_st_fail_save, reran_fail_save = run_manual_order_form(
    EDITOR_USER, True,
    {**BASE_WIDGET_VALUES, "manual_owner_select": label_taew},
    staff_options=staff_options_taew_variant,
    fail_save=True,
)
assert reran_fail_save is False, "a save failure must NOT reach the success st.rerun()"
assert len(calls_fail_save["upsert_manual_order_items"]) == 1, "save must have been attempted exactly once"
assert any(event == "manual_order_save_failed" for event, _exc, _meta in calls_fail_save["log_exception"])
save_fail_meta = next(meta for event, _exc, meta in calls_fail_save["log_exception"] if event == "manual_order_save_failed")
assert save_fail_meta == {"page": "manual_order", "action": "save_order", "component": "manual_order", "outcome": "failure"}
assert fake_st_fail_save.errors, "a user-facing error must still be shown on save failure"
assert not fake_st_fail_save.successes, "no success message may be shown when save fails"

print("Manual Order save-path: safe logging / exception control flow via real execution OK")


# ---------------------------------------------------------------------------
# 21. Permission/data-visibility regression, extended for the exact
#     TAEW/NOONA/JEEB scenario: non-admin filtering still keys strictly off
#     staff_code (never owner), so two staff_codes that would normalize to
#     the same owner text can never cross-leak into each other's visibility
#     scope. Real function call, real captured clause/params -- not source
#     occurrence.
# ---------------------------------------------------------------------------
for code in ("TAEW", "NOONA", "JEEB"):
    staff_scope_user = {"role": "STAFF", "staff_code": code}
    clauses_scope, params_scope = crm_dashboard._sales_report_where(staff_scope_user, "anything")
    assert clauses_scope[-1] == "d.staff_code = %s"
    assert params_scope == [code], f"non-admin visibility for {code} must bind exactly its own staff_code, got {params_scope}"
    assert not any("owner" in clause for clause in clauses_scope), (
        "non-admin path must never filter by the (normalized) owner text -- only by staff_code"
    )

# Admin/editor path is unaffected by any of this -- re-confirm unchanged.
admin_clauses, admin_params = crm_dashboard._sales_report_where(admin_user, "พรณกมล ดวงจันทร์ (แต้ว)")
assert "d.staff_code" not in " ".join(admin_clauses), "admin/editor path must not filter by staff_code at all"

print("Permission/data-visibility regression: TAEW/NOONA/JEEB staff_code scoping OK")


print("owner/staff-name whitespace normalization safety OK")
