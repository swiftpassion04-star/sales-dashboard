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
        return []


class FakeConnection:
    def __init__(self, fetchone_result=None, rowcount=1):
        self.cursor_instance = FakeCursor(fetchone_result, rowcount)
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
    matrix_source = function_source(data_source, data_tree, "fetch_daily_matrix")
    # matrix_source is raw source TEXT (via ast.get_source_segment), so the
    # needle must be a raw string too -- the .py file literally contains two
    # backslash characters before "s+" (it evaluates to one at runtime).
    assert matrix_source.count(r"regexp_replace(trim(coalesce(staff_code, '')), '\\s+', ' ', 'g')") == 1
    assert matrix_source.count(r"regexp_replace(trim(coalesce(d.staff_code, '')), '\\s+', ' ', 'g')") == 1


def test_fetch_daily_matrix_handles_ambiguous_staff_code_without_dropping_rows():
    matrix_source = function_source(data_source, data_tree, "fetch_daily_matrix")
    assert "distinct on (staff_code_norm)" in matrix_source
    assert "left join" in matrix_source.lower()
    assert "ambiguous_staff_codes" in data_source


def test_fetch_daily_matrix_is_cached():
    assert "@st.cache_data(ttl=120, show_spinner=False)\ndef fetch_daily_matrix" in data_source


def test_clear_daily_matrix_caches_clears_both_fetchers():
    clear_source = function_source(data_source, data_tree, "clear_daily_matrix_caches")
    assert "fetch_daily_matrix.clear()" in clear_source
    assert "fetch_day_statuses.clear()" in clear_source


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
