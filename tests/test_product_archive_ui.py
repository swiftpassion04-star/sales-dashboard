import ast
from pathlib import Path


PAGE_PATH = Path(__file__).resolve().parents[1] / "pages" / "products.py"
SOURCE = PAGE_PATH.read_text(encoding="utf-8")
LOWER_SOURCE = SOURCE.lower()
TREE = ast.parse(SOURCE)


def function_source(name):
    node = next(
        item
        for item in TREE.body
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == name
    )
    return ast.get_source_segment(SOURCE, node)


assert '"สินค้าที่เก็บถาวร": "archived"' in SOURCE
assert "status_filter=PRODUCT_STATUS_OPTIONS[status_label]" in SOURCE
assert "archive_products" in SOURCE
assert "restore_archived_products" in SOURCE

archive_actions = function_source("render_product_archive_actions")
assert 'status_filter == "archived"' in archive_actions
assert "selected_product_ids_for_bulk(selected_ids, page_product_ids)" in archive_actions
assert "PRODUCT_ARCHIVE_CONFIRM_KEY" in archive_actions
assert "PRODUCT_RESTORE_CONFIRM_KEY" in archive_actions
assert 'clean(reason) or "Archived from Product Master"' in archive_actions
assert "clear_product_selection()" in archive_actions
assert "PRODUCT_BULK_SUCCESS_KEY" in archive_actions
assert "archive_products(" in archive_actions
assert "restore_archived_products(" in archive_actions

clear_selection = function_source("clear_product_selection")
assert "clear_product_archive_action_state()" in clear_selection
assert "clear_product_delete_readiness()" in clear_selection
assert "PRODUCT_SELECTION_KEY" in clear_selection

render_table = function_source("render_product_table")
assert 'if status_filter != "archived"' in render_table
assert "render_product_archive_actions(" in render_table

render_row = function_source("render_product_row")
assert 'is_archived = bool(row.get("archived_at"))' in render_row
assert "if is_editor and not is_archived" in render_row
assert 'cols[4].write("เก็บถาวร")' in render_row

assert "delete from" not in LOWER_SOURCE
assert "delete_product_option(" not in LOWER_SOURCE

print("product archive UI safety OK")
