"""DB-free tests for crm_data/daily_matrix.py, permissions, and page wiring.

No pytest in this environment -- discovered via the repo's stdlib test_*
runner. FakeConnection/FakeCursor pattern mirrors tests/test_product_archive_repository.py.
"""

import ast
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from crm_data import daily_matrix
from permissions import ROLE_ADMIN, ROLE_EDITOR, ROLE_STAFF, can_manage_daily_status


DATA_PATH = Path("crm_data/daily_matrix.py")
PAGE_PATH = Path("pages/daily_matrix.py")
data_source = DATA_PATH.read_text(encoding="utf-8")
page_source = PAGE_PATH.read_text(encoding="utf-8")
data_tree = ast.parse(data_source)
page_tree = ast.parse(page_source)


def function_node(tree: ast.Module, name: str) -> ast.FunctionDef:
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"missing function: {name}")


def function_source(source: str, tree: ast.Module, name: str) -> str:
    segment = ast.get_source_segment(source, function_node(tree, name))
    assert segment is not None
    return segment


class FakeCursor:
    def __init__(self, fetchone_result=None, rowcount=1):
        self.executed = []
        self._fetchone_result = fetchone_result
        self._fetchall_result = None
        self.rowcount = rowcount

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def execute(self, sql, params):
        self.executed.append((sql, params))

    def fetchone(self):
        return self._fetchone_result

    def fetchall(self):
        return self._fetchall_result or []


class FakeConnection:
    def __init__(self, fetchone_result=None, rowcount=1, fetchall_result=None):
        self.cursor_instance = FakeCursor(fetchone_result, rowcount)
        self.cursor_instance._fetchall_result = fetchall_result
        self.committed = False
        self.rolled_back = False

    def cursor(self):
        return self.cursor_instance

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True


# ---------------------------------------------------------------------------
# Pure tone-classification boundary tests -- "เกิน" is strictly greater-than.
# ---------------------------------------------------------------------------


def test_upsell_cell_tone_boundaries():
    assert daily_matrix.classify_upsell_cell_tone(3000) == "normal"
    assert daily_matrix.classify_upsell_cell_tone(3000.01) == "yellow"
    assert daily_matrix.classify_upsell_cell_tone(4500) == "yellow"
    assert daily_matrix.classify_upsell_cell_tone(4500.01) == "blue"
    assert daily_matrix.classify_upsell_cell_tone(0) == "normal"
    assert daily_matrix.classify_upsell_cell_tone(None) == "normal"


def test_upsell_cell_tone_blue_wins_over_yellow_far_above_both():
    assert daily_matrix.classify_upsell_cell_tone(100000) == "blue"


def test_crm_cell_tone_boundaries():
    assert daily_matrix.classify_crm_cell_tone(11000) == "normal"
    assert daily_matrix.classify_crm_cell_tone(11000.01) == "green"
    assert daily_matrix.classify_crm_cell_tone(None) == "normal"


def test_team_total_tone_boundaries():
    assert daily_matrix.classify_team_total_tone(11000, daily_matrix.UPSELL_TEAM_TOTAL_THRESHOLD) == "normal"
    assert daily_matrix.classify_team_total_tone(11000.01, daily_matrix.UPSELL_TEAM_TOTAL_THRESHOLD) == "green"
    assert daily_matrix.classify_team_total_tone(40000, daily_matrix.CRM_TEAM_TOTAL_THRESHOLD) == "normal"
    assert daily_matrix.classify_team_total_tone(40000.01, daily_matrix.CRM_TEAM_TOTAL_THRESHOLD) == "green"


def test_threshold_constants_match_specification():
    assert daily_matrix.UPSELL_YELLOW_THRESHOLD == 3000
    assert daily_matrix.UPSELL_BLUE_THRESHOLD == 4500
    assert daily_matrix.UPSELL_TEAM_TOTAL_THRESHOLD == 11000
    assert daily_matrix.CRM_INDIVIDUAL_THRESHOLD == 11000
    assert daily_matrix.CRM_TEAM_TOTAL_THRESHOLD == 40000


# ---------------------------------------------------------------------------
# _month_bounds
# ---------------------------------------------------------------------------


def test_month_bounds_normal_month():
    start, end = daily_matrix._month_bounds(2026, 7)
    assert start == date(2026, 7, 1)
    assert end == date(2026, 8, 1)


def test_month_bounds_december_wraps_to_next_year():
    start, end = daily_matrix._month_bounds(2026, 12)
    assert start == date(2026, 12, 1)
    assert end == date(2027, 1, 1)


def test_month_bounds_rejects_invalid_month():
    for bad_month in (0, 13, -1):
        try:
            daily_matrix._month_bounds(2026, bad_month)
        except ValueError:
            pass
        else:
            raise AssertionError(f"month={bad_month} must raise ValueError")


# ---------------------------------------------------------------------------
# save_day_status / clear_day_status
# ---------------------------------------------------------------------------


def test_save_day_status_rejects_invalid_status_before_touching_db():
    try:
        daily_matrix.save_day_status(
            status_date=date(2026, 7, 6),
            status="SICK_DAY",
            actor_email="editor@example.com",
            conn_or_none="not-a-real-connection-should-never-be-used",
        )
    except ValueError:
        pass
    else:
        raise AssertionError("invalid status must raise ValueError")


def test_save_day_status_upserts_and_commits():
    fake_conn = FakeConnection(
        fetchone_result={"status_date": date(2026, 7, 6), "status": "HOLIDAY", "note": None}
    )
    result = daily_matrix.save_day_status(
        status_date=date(2026, 7, 6),
        status="holiday",
        note="  ",
        actor_email="  Editor@Example.com  ",
        conn_or_none=fake_conn,
    )
    assert result == {"status_date": date(2026, 7, 6), "status": "HOLIDAY", "note": None}
    assert fake_conn.committed is True
    assert fake_conn.rolled_back is False
    sql, params = fake_conn.cursor_instance.executed[0]
    assert "on conflict (status_date) do update" in sql.lower()
    assert params[0] == date(2026, 7, 6)
    assert params[1] == "HOLIDAY"
    assert params[2] is None  # blank note normalized to None
    assert params[3] == "editor@example.com"  # actor email normalized


def test_save_day_status_rolls_back_on_error():
    class ExplodingCursor(FakeCursor):
        def execute(self, sql, params):
            raise RuntimeError("boom")

    class ExplodingConnection(FakeConnection):
        def cursor(self):
            return ExplodingCursor()

    fake_conn = ExplodingConnection()
    try:
        daily_matrix.save_day_status(
            status_date=date(2026, 7, 6),
            status="HOLIDAY",
            actor_email="editor@example.com",
            conn_or_none=fake_conn,
        )
    except RuntimeError:
        pass
    else:
        raise AssertionError("underlying DB error must propagate")
    assert fake_conn.rolled_back is True
    assert fake_conn.committed is False


def test_clear_day_status_deletes_and_commits():
    fake_conn = FakeConnection(rowcount=1)
    result = daily_matrix.clear_day_status(
        status_date=date(2026, 7, 6),
        actor_email="editor@example.com",
        conn_or_none=fake_conn,
    )
    assert result == {"status_date": date(2026, 7, 6), "deleted": True}
    assert fake_conn.committed is True
    sql, params = fake_conn.cursor_instance.executed[0]
    assert "delete from public.crm_daily_status" in sql.lower()
    assert params == [date(2026, 7, 6)]


def test_clear_day_status_reports_not_deleted_when_no_row_matched():
    fake_conn = FakeConnection(rowcount=0)
    result = daily_matrix.clear_day_status(status_date=date(2026, 7, 6), conn_or_none=fake_conn)
    assert result == {"status_date": date(2026, 7, 6), "deleted": False}


# ---------------------------------------------------------------------------
# fetch_daily_matrix SQL shape (source-level, matches tests/test_team_sales_refresh.py style)
# ---------------------------------------------------------------------------


def test_fetch_daily_matrix_uses_order_date_not_created_at():
    matrix_source = function_source(data_source, data_tree, "fetch_daily_matrix")
    assert "d.order_date" in matrix_source
    assert "d.created_at" not in matrix_source


def test_fetch_daily_matrix_reuses_team_sales_predicates():
    matrix_source = function_source(data_source, data_tree, "fetch_daily_matrix")
    assert "_MANUAL_ROW_SQL" in matrix_source
    assert "('NEW_ORDER', 'UPSELL', '⭐NEW_ORDER', '⭐UPSELL')" in matrix_source


def test_fetch_daily_matrix_normalizes_staff_code_both_sides():
    # The roster side (unprefixed staff_code) is normalized once in the
    # shared _ROSTER_CTE_SQL constant; the sales side (d.staff_code) is
    # normalized once in fetch_daily_matrix's own sales CTE.
    # matrix_source/data_source are raw source TEXT (via ast.get_source_segment
    # / file read), so the needle must be a raw string too -- the .py file
    # literally contains two backslash characters before "s+" (it evaluates
    # to one at runtime).
    assert data_source.count(r"regexp_replace(trim(coalesce(staff_code, '')), '\\s+', ' ', 'g')") == 1
    matrix_source = function_source(data_source, data_tree, "fetch_daily_matrix")
    assert matrix_source.count(r"regexp_replace(trim(coalesce(d.staff_code, '')), '\\s+', ' ', 'g')") == 1


def test_roster_cte_dedupes_ambiguous_staff_code_deterministically():
    assert "distinct on (staff_code_norm)" in daily_matrix._ROSTER_CTE_SQL
    assert "having count(*) > 1" in daily_matrix._ROSTER_CTE_SQL


def test_fetch_daily_matrix_handles_ambiguous_staff_code_without_dropping_rows():
    matrix_source = function_source(data_source, data_tree, "fetch_daily_matrix")
    assert "left join" in matrix_source.lower()
    assert "ambiguous_staff_codes" in data_source


def test_fetch_daily_matrix_is_cached():
    assert "@st.cache_data(ttl=120, show_spinner=False)\ndef fetch_daily_matrix" in data_source


def test_clear_daily_matrix_caches_clears_both_fetchers():
    clear_source = function_source(data_source, data_tree, "clear_daily_matrix_caches")
    assert "fetch_daily_matrix.clear()" in clear_source
    assert "fetch_day_statuses.clear()" in clear_source


# ---------------------------------------------------------------------------
# Regression coverage for the "zero-sales staff member disappears from their
# team's columns" bug: columns must be seeded from roster+assignments, not
# derived only from staff who happened to have a sale that month.
# ---------------------------------------------------------------------------


def test_team_columns_are_seeded_before_sales_rows_are_fetched():
    matrix_node = function_node(data_tree, "fetch_daily_matrix")
    call_names_in_order = []
    for statement in matrix_node.body:
        for node in ast.walk(statement):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                call_names_in_order.append(node.func.id)
    assert "_fetch_team_roster_columns" in call_names_in_order
    assert "_fetch_all" in call_names_in_order
    assert call_names_in_order.index("_fetch_team_roster_columns") < call_names_in_order.index("_fetch_all")


def test_team_roster_columns_query_is_not_driven_by_sales():
    roster_columns_source = function_source(data_source, data_tree, "_fetch_team_roster_columns")
    assert "crm_data_imports" not in roster_columns_source
    assert "public.crm_user_team_assignments" in roster_columns_source
    assert "join public.crm_user_team_assignments" in roster_columns_source  # inner join: must have a real assignment
    assert "select distinct" in roster_columns_source


def test_team_roster_columns_uses_month_level_overlap_not_per_day():
    roster_columns_source = function_source(data_source, data_tree, "_fetch_team_roster_columns")
    assert "_date_bounds(" in roster_columns_source
    assert "at time zone" not in roster_columns_source.lower()


def test_fetch_team_roster_columns_returns_zero_sales_staff():
    # _fetch_team_roster_columns is plain (uncached), safe to invoke
    # directly with a fake connection -- unlike fetch_daily_matrix, which is
    # @st.cache_data-decorated and would route a custom fake object through
    # Streamlit's argument-hashing machinery.
    fake_conn = FakeConnection(
        fetchall_result=[
            {"team_code": "UPSELL_TEAM", "staff_code_norm": "ZERO", "staff_name": "Zero Sales Person"}
        ]
    )
    rows = daily_matrix._fetch_team_roster_columns(
        date(2031, 3, 1), date(2031, 4, 1), conn_or_none=fake_conn
    )
    assert rows == [
        {"team_code": "UPSELL_TEAM", "staff_code_norm": "ZERO", "staff_name": "Zero Sales Person"}
    ]
    sql, params = fake_conn.cursor_instance.executed[0]
    assert "crm_data_imports" not in sql
    assert len(params) == 2


# ---------------------------------------------------------------------------
# Regression coverage for the "missing crm_daily_status table kills the
# whole page" bug: fetch_daily_matrix and fetch_day_statuses must be in
# separate try/except blocks so a day-status failure can never hide the
# (fully independent) sales matrix.
# ---------------------------------------------------------------------------


def _try_nodes_containing_call(tree_node, call_name: str) -> list[ast.Try]:
    matches = []
    for node in ast.walk(tree_node):
        if not isinstance(node, ast.Try):
            continue
        for inner in ast.walk(node):
            if (
                isinstance(inner, ast.Call)
                and isinstance(inner.func, ast.Name)
                and inner.func.id == call_name
            ):
                matches.append(node)
                break
    return matches


def test_matrix_and_day_status_fetches_are_in_separate_try_blocks():
    main_node = function_node(page_tree, "main")
    matrix_try_nodes = _try_nodes_containing_call(main_node, "fetch_daily_matrix")
    status_try_nodes = _try_nodes_containing_call(main_node, "fetch_day_statuses")
    assert len(matrix_try_nodes) == 1
    assert len(status_try_nodes) == 1
    assert matrix_try_nodes[0] is not status_try_nodes[0]


def test_day_status_fetch_failure_does_not_return_early():
    main_node = function_node(page_tree, "main")
    status_try_node = _try_nodes_containing_call(main_node, "fetch_day_statuses")[0]
    for handler in status_try_node.handlers:
        for statement in ast.walk(handler):
            assert not isinstance(statement, ast.Return), (
                "the day-status except handler must not return -- doing so "
                "would hide the sales matrix whenever crm_daily_status "
                "hasn't been migrated yet"
            )


def test_matrix_fetch_failure_still_returns_early():
    main_node = function_node(page_tree, "main")
    matrix_try_node = _try_nodes_containing_call(main_node, "fetch_daily_matrix")[0]
    has_return = any(
        isinstance(statement, ast.Return)
        for handler in matrix_try_node.handlers
        for statement in ast.walk(handler)
    )
    assert has_return


# ---------------------------------------------------------------------------
# Permission gate
# ---------------------------------------------------------------------------


def test_can_manage_daily_status_editor_only():
    assert can_manage_daily_status({"role": ROLE_EDITOR}) is True
    assert can_manage_daily_status({"role": ROLE_ADMIN}) is False
    assert can_manage_daily_status({"role": ROLE_STAFF}) is False
    assert can_manage_daily_status({}) is False
    assert can_manage_daily_status(None) is False


def test_page_gates_day_status_manager_behind_can_manage_daily_status():
    main_source = function_source(page_source, page_tree, "main")
    assert "if can_manage_daily_status(user):" in main_source
    guarded_section = main_source.split("if can_manage_daily_status(user):", 1)[1]
    assert "_render_day_status_manager(" in guarded_section


def test_page_does_not_gate_whole_page_to_editor():
    main_source = function_source(page_source, page_tree, "main")
    # The matrix itself (fetch/render) must run unconditionally for any
    # logged-in user -- only the day-status manager is EDITOR-only.
    assert "st.stop()" not in main_source


print("daily sales matrix safety OK")
