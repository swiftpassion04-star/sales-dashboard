import ast
import re
from datetime import date
from pathlib import Path


PAGE_PATH = Path("pages/team_sales.py")
DATA_PATH = Path("crm_data/team_sales.py")
page_source = PAGE_PATH.read_text(encoding="utf-8")
data_source = DATA_PATH.read_text(encoding="utf-8")
page_tree = ast.parse(page_source)
data_tree = ast.parse(data_source)


def function_node(tree: ast.Module, name: str) -> ast.FunctionDef:
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"missing function: {name}")


def function_source(source: str, tree: ast.Module, name: str) -> str:
    segment = ast.get_source_segment(source, function_node(tree, name))
    assert segment is not None
    return segment


def unconditional_reruns(tree: ast.Module) -> list[tuple[str, int]]:
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for statement in node.body:
            if not isinstance(statement, ast.Expr) or not isinstance(statement.value, ast.Call):
                continue
            call = statement.value
            if (
                isinstance(call.func, ast.Attribute)
                and isinstance(call.func.value, ast.Name)
                and call.func.value.id == "st"
                and call.func.attr == "rerun"
            ):
                found.append((node.name, statement.lineno))
    return found


summary_source = function_source(data_source, data_tree, "fetch_team_sales_summary")
top_products_source = function_source(data_source, data_tree, "fetch_team_top_products")
clear_source = function_source(data_source, data_tree, "clear_team_sales_caches")
fingerprint_source = function_source(data_source, data_tree, "fetch_team_sales_fingerprint")
visible_render_source = function_source(page_source, page_tree, "_render_team_sales_once")
poller_source = function_source(page_source, page_tree, "_poll_team_sales_changes")
main_source = function_source(page_source, page_tree, "main")

# Cached visible reads and one targeted invalidation helper.
assert "@st.cache_data(ttl=120, show_spinner=False)\ndef fetch_team_sales_summary" in data_source
assert "@st.cache_data(ttl=120, show_spinner=False)\ndef fetch_team_top_products" in data_source
assert clear_source.count("fetch_team_sales_summary.clear()") == 1
assert clear_source.count("fetch_team_top_products.clear()") == 1
assert "st.cache_data.clear()" not in data_source
assert "st.cache_data.clear()" not in page_source

# The fingerprint is uncached, read-only, and observes both source tables.
fingerprint_node = function_node(data_tree, "fetch_team_sales_fingerprint")
assert fingerprint_node.decorator_list == []
assert "public.crm_data_imports" in fingerprint_source
assert "count(*) as import_row_count" in fingerprint_source
assert "max(d.updated_at) as import_updated_at" in fingerprint_source
assert "public.crm_user_team_assignments" in fingerprint_source
assert "count(*) as assignment_row_count" in fingerprint_source
assert "max(updated_at) as assignment_updated_at" in fingerprint_source
assert "_date_bounds(start_date, end_date)" in fingerprint_source
assert "_sale_type_filter(sale_type_filter)" in fingerprint_source
assert "('NEW_ORDER', 'UPSELL', '⭐NEW_ORDER', '⭐UPSELL')" in fingerprint_source
assert "FOLLOW" not in fingerprint_source
assert not re.search(r"\b(insert|update|delete|alter|create|drop)\b", fingerprint_source, re.I)

# Existing aggregation business rules remain intact.
for aggregate_source in (summary_source, top_products_source):
    assert "_MANUAL_ROW_SQL" in aggregate_source
    assert "('NEW_ORDER', 'UPSELL', '⭐NEW_ORDER', '⭐UPSELL')" in aggregate_source
    assert "FOLLOW" not in aggregate_source
assert "count(distinct nullif(btrim(order_id), ''))" in summary_source
assert "coalesce(sum(amount), 0)" in summary_source
assert "sum({_EFFECTIVE_QUANTITY_SQL})" in top_products_source
assert "limit=10" in visible_render_source

# Only the hidden poller owns the timed fragment; visible cards render normally.
visible_render_node = function_node(page_tree, "_render_team_sales_once")
poller_node = function_node(page_tree, "_poll_team_sales_changes")
assert visible_render_node.decorator_list == []
assert "run_every" not in visible_render_source
assert "@st.fragment(run_every=AUTO_REFRESH_INTERVAL_SECONDS)" in page_source
assert "def _render_team_sales_auto_refresh" not in page_source
assert page_source.count("@st.fragment") == 1

visible_poller_calls = []
for statement in poller_node.body:
    for node in ast.walk(statement):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "st"
            and node.func.attr != "rerun"
        ):
            visible_poller_calls.append((node.func.attr, node.lineno))
assert visible_poller_calls == []
assert unconditional_reruns(page_tree) == []

# Filter-specific state keys prevent baselines from leaking across views.
key_node = function_node(page_tree, "_team_sales_fingerprint_state_key")
runtime_module = ast.Module(body=[key_node, poller_node], type_ignores=[])
ast.fix_missing_locations(runtime_module)


class FakeStreamlit:
    def __init__(self) -> None:
        self.session_state = {}
        self.rerun_calls = 0

    def fragment(self, function=None, *, run_every=None):
        del run_every
        if function is not None:
            return function

        def decorator(inner):
            return inner

        return decorator

    def rerun(self) -> None:
        self.rerun_calls += 1


fake_st = FakeStreamlit()
clear_calls = []
fingerprints = [(10, "2026-07-20T10:00:00", 2, "2026-07-20T09:00:00")]


def fake_fetch_fingerprint(*args, **kwargs):
    del args, kwargs
    return fingerprints[-1]


def fake_clear_caches() -> None:
    clear_calls.append("clear")


runtime = {
    "AUTO_REFRESH_INTERVAL_SECONDS": 15,
    "TEAM_SALES_FINGERPRINT_PREFIX": "team_sales_fingerprint::",
    "clear_team_sales_caches": fake_clear_caches,
    "date": date,
    "fetch_team_sales_fingerprint": fake_fetch_fingerprint,
    "st": fake_st,
}
exec(compile(runtime_module, str(PAGE_PATH), "exec"), runtime)
state_key = runtime["_team_sales_fingerprint_state_key"]
poll_changes = runtime["_poll_team_sales_changes"]

start = date(2026, 7, 1)
end = date(2026, 7, 31)
base_key = state_key(start, end, None, None)
assert base_key == "team_sales_fingerprint::2026-07-01::2026-07-31::ALL::ALL"
assert state_key(start, end, "UPSELL", None) != base_key
assert state_key(start, end, None, "CRM_TEAM") != base_key

# First observation stores a baseline without clearing or rerunning.
poll_changes(start, end, None, None)
assert fake_st.session_state[base_key] == fingerprints[-1]
assert clear_calls == []
assert fake_st.rerun_calls == 0

# An unchanged observation is a no-op.
poll_changes(start, end, None, None)
assert clear_calls == []
assert fake_st.rerun_calls == 0

# A changed observation clears visible caches once and requests one full rerun.
fingerprints.append((11, "2026-07-20T10:01:00", 2, "2026-07-20T09:00:00"))
poll_changes(start, end, None, None)
assert clear_calls == ["clear"]
assert fake_st.rerun_calls == 1
assert fake_st.session_state[base_key] == fingerprints[-1]

# Poll errors are silent and cannot clear or rerun.
def failing_fetch(*args, **kwargs):
    del args, kwargs
    raise RuntimeError("temporary polling failure")


runtime["fetch_team_sales_fingerprint"] = failing_fetch
poll_changes(start, end, None, None)
assert clear_calls == ["clear"]
assert fake_st.rerun_calls == 1

# Auto refresh gates the poller; manual refresh uses only targeted clears.
parents = {}
for parent in ast.walk(function_node(page_tree, "main")):
    for child in ast.iter_child_nodes(parent):
        parents[child] = parent
poll_calls = [
    node
    for node in ast.walk(function_node(page_tree, "main"))
    if isinstance(node, ast.Call)
    and isinstance(node.func, ast.Name)
    and node.func.id == "_poll_team_sales_changes"
]
assert len(poll_calls) == 1
ancestor = parents[poll_calls[0]]
while ancestor is not None and not isinstance(ancestor, ast.If):
    ancestor = parents.get(ancestor)
assert isinstance(ancestor, ast.If)
assert isinstance(ancestor.test, ast.Name) and ancestor.test.id == "auto_refresh"
assert "if manual_refresh:" in main_source
manual_refresh_source = main_source.split("if manual_refresh:", 1)[1].split(
    "_render_team_sales_once(", 1
)[0]
assert "clear_team_sales_caches()" in manual_refresh_source
assert "_clear_team_sales_fingerprint_state()" in manual_refresh_source
assert manual_refresh_source.count("st.rerun()") == 1
assert "st.cache_data.clear()" not in manual_refresh_source

print("team sales change-aware refresh safety OK")
