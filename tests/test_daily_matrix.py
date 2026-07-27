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
            scope_type="ALL",
            actor_email="editor@example.com",
            conn_or_none="not-a-real-connection-should-never-be-used",
        )
    except ValueError:
        pass
    else:
        raise AssertionError("invalid status must raise ValueError")


def test_save_day_status_rejects_invalid_scope_before_touching_db():
    try:
        daily_matrix.save_day_status(
            status_date=date(2026, 7, 6),
            status="HOLIDAY",
            scope_type="TEAM",
            conn_or_none="not-a-real-connection-should-never-be-used",
        )
    except ValueError:
        pass
    else:
        raise AssertionError("invalid scope_type must raise ValueError")


def test_save_day_status_staff_scope_requires_staff_code():
    try:
        daily_matrix.save_day_status(
            status_date=date(2026, 7, 6),
            status="HOLIDAY",
            scope_type="STAFF",
            staff_code="  ",
            conn_or_none="not-a-real-connection-should-never-be-used",
        )
    except ValueError:
        pass
    else:
        raise AssertionError("STAFF scope with blank staff_code must raise ValueError")


def test_save_day_status_all_scope_rejects_staff_code():
    try:
        daily_matrix.save_day_status(
            status_date=date(2026, 7, 6),
            status="HOLIDAY",
            scope_type="ALL",
            staff_code="KO",
            conn_or_none="not-a-real-connection-should-never-be-used",
        )
    except ValueError:
        pass
    else:
        raise AssertionError("ALL scope with a staff_code must raise ValueError")


def test_save_day_status_all_scope_upserts_and_commits():
    fake_conn = FakeConnection(
        fetchone_result={
            "status_date": date(2026, 7, 6),
            "scope_type": "ALL",
            "staff_code": None,
            "status": "HOLIDAY",
            "note": None,
        }
    )
    result = daily_matrix.save_day_status(
        status_date=date(2026, 7, 6),
        status="holiday",
        scope_type="all",
        note="  ",
        actor_email="  Editor@Example.com  ",
        conn_or_none=fake_conn,
    )
    assert result["scope_type"] == "ALL"
    assert result["staff_code"] is None
    assert fake_conn.committed is True
    assert fake_conn.rolled_back is False
    sql, params = fake_conn.cursor_instance.executed[0]
    assert "on conflict (status_date, scope_type, (coalesce(staff_code, '')))" in sql.lower()
    assert params[0] == date(2026, 7, 6)
    assert params[1] == "ALL"
    assert params[2] is None  # ALL scope never carries a staff_code
    assert params[3] == "HOLIDAY"
    assert params[4] is None  # blank note normalized to None
    assert params[5] == "editor@example.com"  # actor email normalized


def test_save_day_status_staff_scope_upserts_with_normalized_staff_code():
    fake_conn = FakeConnection(
        fetchone_result={
            "status_date": date(2026, 7, 6),
            "scope_type": "STAFF",
            "staff_code": "KO",
            "status": "LEAVE",
            "note": None,
        }
    )
    result = daily_matrix.save_day_status(
        status_date=date(2026, 7, 6),
        status="leave",
        scope_type="staff",
        staff_code="  KO  ",
        actor_email="editor@example.com",
        conn_or_none=fake_conn,
    )
    assert result["scope_type"] == "STAFF"
    assert result["staff_code"] == "KO"
    sql, params = fake_conn.cursor_instance.executed[0]
    assert params[1] == "STAFF"
    assert params[2] == "KO"  # normalized (trimmed)
    assert params[3] == "LEAVE"


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
            scope_type="ALL",
            actor_email="editor@example.com",
            conn_or_none=fake_conn,
        )
    except RuntimeError:
        pass
    else:
        raise AssertionError("underlying DB error must propagate")
    assert fake_conn.rolled_back is True
    assert fake_conn.committed is False


def test_clear_day_status_rejects_invalid_scope_before_touching_db():
    try:
        daily_matrix.clear_day_status(
            status_date=date(2026, 7, 6),
            scope_type="EVERYONE",
            conn_or_none="not-a-real-connection-should-never-be-used",
        )
    except ValueError:
        pass
    else:
        raise AssertionError("invalid scope_type must raise ValueError")


def test_clear_day_status_staff_scope_requires_staff_code():
    try:
        daily_matrix.clear_day_status(
            status_date=date(2026, 7, 6),
            scope_type="STAFF",
            conn_or_none="not-a-real-connection-should-never-be-used",
        )
    except ValueError:
        pass
    else:
        raise AssertionError("STAFF scope with no staff_code must raise ValueError")


def test_clear_day_status_all_scope_deletes_and_commits():
    fake_conn = FakeConnection(rowcount=1)
    result = daily_matrix.clear_day_status(
        status_date=date(2026, 7, 6),
        scope_type="ALL",
        actor_email="editor@example.com",
        conn_or_none=fake_conn,
    )
    assert result == {
        "status_date": date(2026, 7, 6),
        "scope_type": "ALL",
        "staff_code": None,
        "deleted": True,
    }
    assert fake_conn.committed is True
    sql, params = fake_conn.cursor_instance.executed[0]
    assert "delete from public.crm_daily_status" in sql.lower()
    assert "scope_type = %s" in sql.lower()
    assert "coalesce(staff_code, '') = coalesce(%s, '')" in sql.lower()
    assert params == [date(2026, 7, 6), "ALL", None]


def test_clear_day_status_staff_scope_deletes_only_that_staff_code():
    fake_conn = FakeConnection(rowcount=1)
    result = daily_matrix.clear_day_status(
        status_date=date(2026, 7, 6),
        scope_type="STAFF",
        staff_code="KO",
        conn_or_none=fake_conn,
    )
    assert result == {
        "status_date": date(2026, 7, 6),
        "scope_type": "STAFF",
        "staff_code": "KO",
        "deleted": True,
    }
    sql, params = fake_conn.cursor_instance.executed[0]
    assert params == [date(2026, 7, 6), "STAFF", "KO"]


def test_clear_day_status_reports_not_deleted_when_no_row_matched():
    fake_conn = FakeConnection(rowcount=0)
    result = daily_matrix.clear_day_status(
        status_date=date(2026, 7, 6), scope_type="ALL", conn_or_none=fake_conn
    )
    assert result["deleted"] is False


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


# ---------------------------------------------------------------------------
# format_staff_display_name -- compact header labels.
# ---------------------------------------------------------------------------


def test_format_staff_display_name_extracts_trailing_parens():
    assert daily_matrix.format_staff_display_name("พรนภา นันที (หนูนา)", "NOONA") == "หนูนา"


def test_format_staff_display_name_trims_whitespace_inside_parens():
    assert daily_matrix.format_staff_display_name("พรนภา นันที (  หนูนา  )", "NOONA") == "หนูนา"


def test_format_staff_display_name_no_parens_falls_back_to_full_name():
    assert daily_matrix.format_staff_display_name("พรนภา นันที", "NOONA") == "พรนภา นันที"


def test_format_staff_display_name_only_trailing_parens_count_not_middle():
    # A parenthesized aside in the middle of a name (not at the very end)
    # is left alone -- only the trailing group is a "nickname".
    assert daily_matrix.format_staff_display_name("A (mid) B", "CODE") == "A (mid) B"


def test_format_staff_display_name_empty_parens_falls_back_to_trimmed_name():
    assert daily_matrix.format_staff_display_name("  พรนภา นันที ()  ", "NOONA") == "พรนภา นันที ()"


def test_format_staff_display_name_whitespace_only_parens_falls_back_to_trimmed_name():
    assert daily_matrix.format_staff_display_name("พรนภา นันที (   )", "NOONA") == "พรนภา นันที (   )"


def test_format_staff_display_name_blank_name_falls_back_to_staff_code():
    assert daily_matrix.format_staff_display_name("", "NOONA") == "NOONA"
    assert daily_matrix.format_staff_display_name(None, "NOONA") == "NOONA"
    assert daily_matrix.format_staff_display_name("   ", "  noona  ") == "noona"


def test_format_staff_display_name_blank_name_and_blank_code_returns_empty_string():
    assert daily_matrix.format_staff_display_name(None, None) == ""
    assert daily_matrix.format_staff_display_name("", "") == ""


def test_page_uses_display_name_helper_only_in_column_header_cells():
    header_source = function_source(page_source, page_tree, "_column_header_cells")
    assert "format_staff_display_name(" in header_source
    # The helper must never leak into the per-staff data lookup -- that key
    # stays staff_code (raw), never the shortened display label.
    build_source = function_source(page_source, page_tree, "_build_matrix_html")
    assert "format_staff_display_name(" not in build_source
    assert build_source.count('.get(staff_code, 0.0)') == 3


# ---------------------------------------------------------------------------
# _build_matrix_from_rows -- pure, DB-free transform (roster + sales rows ->
# matrix dict). Exercises the actual bucketing/aggregation logic directly.
# ---------------------------------------------------------------------------


def test_aggregation_key_stays_staff_code_not_display_name():
    roster_rows = [
        {"team_code": "UPSELL_TEAM", "staff_code_norm": "NOONA", "staff_name": "พรนภา นันที (หนูนา)"}
    ]
    matrix = daily_matrix._build_matrix_from_rows(roster_rows, [], date(2026, 7, 1), date(2026, 8, 1))
    col = matrix["teams"]["UPSELL_TEAM"]["columns"][0]
    # Raw, untransformed -- format_staff_display_name is applied only at
    # render time in pages/daily_matrix.py, never inside the data layer.
    assert col["staff_code"] == "NOONA"
    assert col["staff_name"] == "พรนภา นันที (หนูนา)"


def test_unassigned_team_name_is_thai_label():
    assert daily_matrix.UNASSIGNED_TEAM_NAME == "ไม่มีทีม"
    matrix = daily_matrix._build_matrix_from_rows([], [], date(2026, 7, 1), date(2026, 8, 1))
    assert matrix["teams"][daily_matrix.UNASSIGNED_TEAM_CODE]["team_name"] == "ไม่มีทีม"


def test_staff_with_no_team_appear_as_columns_in_unassigned_block():
    sales_rows = [
        {
            "staff_code_norm": "GHOST",
            "order_date": date(2026, 7, 6),
            "day_amount": 500.0,
            "staff_name": "Ghost Person",
            "team_code": None,
            "is_ambiguous": False,
        },
    ]
    matrix = daily_matrix._build_matrix_from_rows([], sales_rows, date(2026, 7, 1), date(2026, 8, 1))
    unassigned_cols = {c["staff_code"] for c in matrix["teams"][daily_matrix.UNASSIGNED_TEAM_CODE]["columns"]}
    assert unassigned_cols == {"GHOST"}
    # Sales must not disappear: this is the core bug being fixed.
    assert matrix["teams"][daily_matrix.UNASSIGNED_TEAM_CODE]["days"][date(2026, 7, 6)]["per_staff"]["GHOST"] == 500.0


def test_unassigned_daily_and_team_totals_are_correct():
    sales_rows = [
        {"staff_code_norm": "A", "order_date": date(2026, 7, 6), "day_amount": 100.0, "staff_name": "A Name", "team_code": None, "is_ambiguous": False},
        {"staff_code_norm": "B", "order_date": date(2026, 7, 6), "day_amount": 250.0, "staff_name": "B Name", "team_code": None, "is_ambiguous": False},
        {"staff_code_norm": "A", "order_date": date(2026, 7, 7), "day_amount": 50.0, "staff_name": "A Name", "team_code": None, "is_ambiguous": False},
    ]
    matrix = daily_matrix._build_matrix_from_rows([], sales_rows, date(2026, 7, 1), date(2026, 8, 1))
    unassigned = matrix["teams"][daily_matrix.UNASSIGNED_TEAM_CODE]

    day6 = unassigned["days"][date(2026, 7, 6)]
    assert day6["per_staff"]["A"] == 100.0
    assert day6["per_staff"]["B"] == 250.0
    assert day6["team_total"] == 350.0

    day7 = unassigned["days"][date(2026, 7, 7)]
    assert day7["per_staff"]["A"] == 50.0
    assert day7["team_total"] == 50.0

    assert matrix["unassigned"]["total"] == 400.0


def test_team_staff_and_unassigned_staff_never_mix():
    roster_rows = [
        {"team_code": "UPSELL_TEAM", "staff_code_norm": "KO", "staff_name": "สุมนตรา ทัศน์ศรี (โก้)"},
    ]
    sales_rows = [
        {"staff_code_norm": "KO", "order_date": date(2026, 7, 6), "day_amount": 1000.0, "staff_name": "สุมนตรา ทัศน์ศรี (โก้)", "team_code": "UPSELL_TEAM", "is_ambiguous": False},
        {"staff_code_norm": "GHOST", "order_date": date(2026, 7, 6), "day_amount": 500.0, "staff_name": None, "team_code": None, "is_ambiguous": False},
    ]
    matrix = daily_matrix._build_matrix_from_rows(roster_rows, sales_rows, date(2026, 7, 1), date(2026, 8, 1))

    upsell_codes = {c["staff_code"] for c in matrix["teams"]["UPSELL_TEAM"]["columns"]}
    unassigned_codes = {c["staff_code"] for c in matrix["teams"][daily_matrix.UNASSIGNED_TEAM_CODE]["columns"]}
    crm_codes = {c["staff_code"] for c in matrix["teams"]["CRM_TEAM"]["columns"]}

    assert upsell_codes == {"KO"}
    assert unassigned_codes == {"GHOST"}
    assert crm_codes == set()
    assert "GHOST" not in upsell_codes
    assert "KO" not in unassigned_codes
    # Sales figures for each stay in their own bucket too, not just columns.
    assert matrix["teams"]["UPSELL_TEAM"]["days"][date(2026, 7, 6)]["per_staff"] == {"KO": 1000.0}
    assert matrix["teams"][daily_matrix.UNASSIGNED_TEAM_CODE]["days"][date(2026, 7, 6)]["per_staff"] == {"GHOST": 500.0}


def test_unassigned_staff_missing_from_roster_still_gets_a_display_name():
    sales_rows = [
        {"staff_code_norm": "GHOST", "order_date": date(2026, 7, 6), "day_amount": 10.0, "staff_name": None, "team_code": None, "is_ambiguous": False},
    ]
    matrix = daily_matrix._build_matrix_from_rows([], sales_rows, date(2026, 7, 1), date(2026, 8, 1))
    col = matrix["teams"][daily_matrix.UNASSIGNED_TEAM_CODE]["columns"][0]
    assert col["staff_code"] == "GHOST"
    assert col["staff_name"] == "GHOST"  # falls back to staff_code when roster has no name


def test_ambiguous_staff_warning_still_works_with_unassigned_bucket():
    sales_rows = [
        {"staff_code_norm": "DUP", "order_date": date(2026, 7, 6), "day_amount": 100.0, "staff_name": "Dup Name", "team_code": "CRM_TEAM", "is_ambiguous": True},
        {"staff_code_norm": "GHOST", "order_date": date(2026, 7, 6), "day_amount": 50.0, "staff_name": None, "team_code": None, "is_ambiguous": False},
    ]
    matrix = daily_matrix._build_matrix_from_rows([], sales_rows, date(2026, 7, 1), date(2026, 8, 1))
    assert matrix["ambiguous_staff_codes"] == ["DUP"]


def test_zero_sales_team_member_and_unassigned_do_not_interact():
    # Regression guard: a team member seeded with zero sales (via roster)
    # must not accidentally show up in, or block, the unassigned bucket.
    roster_rows = [
        {"team_code": "CRM_TEAM", "staff_code_norm": "ZERO", "staff_name": "Zero Sales Person"},
    ]
    sales_rows = [
        {"staff_code_norm": "GHOST", "order_date": date(2026, 7, 6), "day_amount": 20.0, "staff_name": "Ghost", "team_code": None, "is_ambiguous": False},
    ]
    matrix = daily_matrix._build_matrix_from_rows(roster_rows, sales_rows, date(2026, 7, 1), date(2026, 8, 1))
    crm_codes = {c["staff_code"] for c in matrix["teams"]["CRM_TEAM"]["columns"]}
    unassigned_codes = {c["staff_code"] for c in matrix["teams"][daily_matrix.UNASSIGNED_TEAM_CODE]["columns"]}
    assert crm_codes == {"ZERO"}
    assert unassigned_codes == {"GHOST"}
    assert matrix["teams"]["CRM_TEAM"]["days"] == {}  # zero sales -> no day entries, cells default to 0 at render time


# ---------------------------------------------------------------------------
# pages/daily_matrix.py -- unassigned block rendering (source-level).
# ---------------------------------------------------------------------------


def test_build_matrix_html_includes_unassigned_block():
    build_source = function_source(page_source, page_tree, "_build_matrix_html")
    assert "UNASSIGNED_TEAM_CODE" in build_source
    assert "dm-group-unassigned" in build_source
    assert build_source.count('.get(staff_code, 0.0)') == 3


def test_build_matrix_html_never_colors_unassigned_cells():
    build_source = function_source(page_source, page_tree, "_build_matrix_html")
    assert "unassigned_cols" in build_source
    # No thresholds were specified for the unassigned block -- its cells
    # must always be built with the literal "normal" tone, never a
    # classify_* call, unlike the upsell/crm loops right above it.
    assert '_staff_cell_html(amount, "normal", all_status, staff_statuses, staff_code)' in build_source


def test_grand_total_includes_unassigned():
    build_source = function_source(page_source, page_tree, "_build_matrix_html")
    assert "grand_total = upsell_total + crm_total + unassigned_total" in build_source


def test_narrow_staff_columns_css_class_applied_via_shared_cell_helper():
    # dm-col-staff is now applied once, inside the shared _staff_cell_html
    # helper, and that helper is called once per per-staff loop (upsell,
    # crm, unassigned) rather than each loop building its own <td> markup.
    cell_helper_source = function_source(page_source, page_tree, "_staff_cell_html")
    assert "dm-col-staff" in cell_helper_source
    build_source = function_source(page_source, page_tree, "_build_matrix_html")
    assert build_source.count("_staff_cell_html(") == 3
    header_source = function_source(page_source, page_tree, "_column_header_cells")
    assert "dm-col-staff" in header_source


def test_css_defines_narrow_staff_column_and_unassigned_group_color():
    design_source = Path("ui/daily_matrix_design.py").read_text(encoding="utf-8")
    assert "dm-col-staff" in design_source
    assert "dm-group-unassigned" in design_source


# ---------------------------------------------------------------------------
# Weekday short labels (จ./อ./พ./พฤ./ศ./ส./อา.)
# ---------------------------------------------------------------------------


def test_weekday_short_labels_all_seven_days():
    expected = {
        0: "จ.",
        1: "อ.",
        2: "พ.",
        3: "พฤ.",
        4: "ศ.",
        5: "ส.",
        6: "อา.",
    }
    weekdays_source = page_source
    # Sourced directly from the page module's constant via ast, not by
    # importing pages/daily_matrix.py (which executes st.set_page_config +
    # main() at import time -- unsafe outside a real Streamlit run).
    module = ast.parse(weekdays_source)
    assign = next(
        node
        for node in module.body
        if isinstance(node, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "_THAI_WEEKDAYS" for t in node.targets)
    )
    values = [elt.value for elt in assign.value.elts]
    assert len(values) == 7
    for index, label in expected.items():
        assert values[index] == label


def test_date_label_uses_short_weekday_format():
    build_source = function_source(page_source, page_tree, "_build_matrix_html")
    assert '_thai_weekday(current)} {_thai_date_short(current)}' in build_source


# ---------------------------------------------------------------------------
# resolve_cell_status_highlight -- ALL vs STAFF scope highlight decision.
# ---------------------------------------------------------------------------


def test_resolve_cell_status_highlight_all_scope_suppresses_per_cell_highlight():
    # A whole-row ALL status is rendered at the row level (dm-row-holiday);
    # no individual cell needs its own highlight on top of that.
    all_status = {"status": "HOLIDAY", "note": None}
    result = daily_matrix.resolve_cell_status_highlight(all_status, {"KO": {"status": "LEAVE"}}, "KO")
    assert result is None


def test_resolve_cell_status_highlight_staff_scope_highlights_only_that_cell():
    staff_statuses = {"KO": {"status": "LEAVE", "note": None}}
    assert daily_matrix.resolve_cell_status_highlight(None, staff_statuses, "KO") == {
        "status": "LEAVE",
        "note": None,
    }
    # A different staff_code on the same day is untouched.
    assert daily_matrix.resolve_cell_status_highlight(None, staff_statuses, "NOONA") is None


def test_resolve_cell_status_highlight_no_status_at_all():
    assert daily_matrix.resolve_cell_status_highlight(None, {}, "KO") is None


def test_staff_status_never_affects_other_staff_same_day():
    # Two people on the same day: only the one with a STAFF-scope entry
    # resolves to a highlight; the other's cell is completely unaffected.
    staff_statuses = {"A": {"status": "LEAVE", "note": None}}
    assert daily_matrix.resolve_cell_status_highlight(None, staff_statuses, "A") is not None
    assert daily_matrix.resolve_cell_status_highlight(None, staff_statuses, "B") is None


def test_row_highlight_driven_by_all_status_only():
    build_source = function_source(page_source, page_tree, "_build_matrix_html")
    assert 'row_class = "dm-row-holiday" if all_status else ""' in build_source


def test_staff_status_supported_in_all_three_blocks():
    # _staff_cell_html (which calls resolve_cell_status_highlight) is
    # invoked once per per-staff loop -- upsell, crm, and unassigned --
    # so a STAFF-scope status highlights correctly regardless of which
    # block that staff_code's column lives in.
    build_source = function_source(page_source, page_tree, "_build_matrix_html")
    assert build_source.count("_staff_cell_html(") == 3


# ---------------------------------------------------------------------------
# fetch_day_statuses / _build_day_statuses_from_rows -- ALL vs STAFF shape.
# ---------------------------------------------------------------------------


def test_build_day_statuses_from_rows_separates_all_and_staff():
    rows = [
        {"status_date": date(2026, 7, 6), "scope_type": "ALL", "staff_code": None, "status": "HOLIDAY", "note": None},
        {"status_date": date(2026, 7, 6), "scope_type": "STAFF", "staff_code": "KO", "status": "LEAVE", "note": "ลาป่วย"},
        {"status_date": date(2026, 7, 6), "scope_type": "STAFF", "staff_code": "NOONA", "status": "LEAVE", "note": None},
        {"status_date": date(2026, 7, 7), "scope_type": "STAFF", "staff_code": "KO", "status": "HOLIDAY", "note": None},
    ]
    result = daily_matrix._build_day_statuses_from_rows(rows)

    day6 = result[date(2026, 7, 6)]
    assert day6["all"] == {"status": "HOLIDAY", "note": None}
    assert day6["staff"]["KO"] == {"status": "LEAVE", "note": "ลาป่วย"}
    assert day6["staff"]["NOONA"] == {"status": "LEAVE", "note": None}
    assert set(day6["staff"]) == {"KO", "NOONA"}  # multiple staff, same day, same date

    day7 = result[date(2026, 7, 7)]
    assert day7["all"] is None
    assert day7["staff"]["KO"] == {"status": "HOLIDAY", "note": None}


def test_build_day_statuses_from_rows_date_with_only_staff_entries_has_no_all():
    rows = [
        {"status_date": date(2026, 7, 6), "scope_type": "STAFF", "staff_code": "KO", "status": "LEAVE", "note": None},
    ]
    result = daily_matrix._build_day_statuses_from_rows(rows)
    assert result[date(2026, 7, 6)]["all"] is None


def test_fetch_day_statuses_selects_scope_and_staff_code_columns():
    fetch_source = function_source(data_source, data_tree, "fetch_day_statuses")
    assert "scope_type" in fetch_source
    assert "staff_code" in fetch_source
    assert "_build_day_statuses_from_rows(rows)" in fetch_source


# ---------------------------------------------------------------------------
# Migration: ALL/STAFF scope constraints (offline, source-level only -- this
# migration has never been run against any database).
# ---------------------------------------------------------------------------


def test_migration_adds_scope_type_and_staff_code_columns():
    migration_source = Path(
        "neon/migrations/202607270001_create_crm_daily_status.sql"
    ).read_text(encoding="utf-8")
    lowered = migration_source.lower()
    assert "scope_type text not null check (scope_type in ('all', 'staff'))" in lowered
    assert "staff_code text" in lowered


def test_migration_check_constraint_enforces_scope_staff_code_pairing():
    migration_source = Path(
        "neon/migrations/202607270001_create_crm_daily_status.sql"
    ).read_text(encoding="utf-8")
    lowered = migration_source.lower()
    assert "scope_type = 'all' and staff_code is null" in lowered
    assert "scope_type = 'staff' and staff_code is not null" in lowered


def test_migration_unique_index_distinguishes_all_and_staff_rows():
    migration_source = Path(
        "neon/migrations/202607270001_create_crm_daily_status.sql"
    ).read_text(encoding="utf-8")
    lowered = migration_source.lower()
    assert "create unique index" in lowered
    assert "(status_date, scope_type, (coalesce(staff_code, '')))" in lowered


def test_migration_does_not_drop_or_alter_destructively():
    migration_source = Path(
        "neon/migrations/202607270001_create_crm_daily_status.sql"
    ).read_text(encoding="utf-8")
    lowered = migration_source.lower()
    assert "drop table" not in lowered
    assert "drop column" not in lowered
    assert "create table if not exists" in lowered


def test_rollback_still_matches_the_paired_migration_table():
    rollback_source = Path(
        "neon/migrations/202607270001_drop_crm_daily_status.rollback.sql"
    ).read_text(encoding="utf-8")
    assert "drop table if exists public.crm_daily_status" in rollback_source.lower()


# ---------------------------------------------------------------------------
# Privacy: the day-status manager UI must never render an email address.
# ---------------------------------------------------------------------------


def test_day_status_manager_never_renders_email():
    manager_source = function_source(page_source, page_tree, "_render_day_status_manager")
    # actor_email is only ever passed through to save/clear calls (used
    # internally for created_by/updated_by), never interpolated into any
    # st.markdown/st.write/label text.
    assert "actor_email}" not in manager_source
    assert '{actor_email' not in manager_source


print("daily sales matrix safety OK")
