import ast
import inspect
import sys
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import neon_utils as neon
import ui.manual_order_ui as manual_ui


rows = [
    {
        "sku": "SP001",
        "product_group": "Group A",
        "product_name": "Active Product",
        "is_active": True,
        "archived_at": None,
        "image_url": "https://example.com/active.jpg",
    },
    {
        "sku": "SP002",
        "product_group": "Group A",
        "product_name": "Archived Product",
        "is_active": True,
        "archived_at": "2026-07-01T00:00:00+00:00",
        "image_url": "https://example.com/archived.jpg",
    },
    {
        "sku": "SP003",
        "product_group": "Group B",
        "product_name": "Inactive Product",
        "is_active": False,
        "archived_at": None,
        "image_url": "https://example.com/inactive.jpg",
    },
    {
        "sku": "SP004",
        "product_group": "Group B",
        "product_name": "Inactive Archived Product",
        "is_active": False,
        "archived_at": "2026-07-01T00:00:00+00:00",
        "image_url": "https://example.com/inactive-archived.jpg",
    },
    {
        "sku": "SP005",
        "product_group": "Group C",
        "product_name": "No Image Product",
        "is_active": True,
        "archived_at": None,
        "image_url": None,
    },
]

assert neon._order_product_options_from_rows(rows) == [
    {
        "sku": "SP001",
        "product_name": "Active Product",
        "product_group": "Group A",
        "image_url": "https://example.com/active.jpg",
    },
    {
        "sku": "SP005",
        "product_name": "No Image Product",
        "product_group": "Group C",
        "image_url": "",
    }
]

assert neon.product_image_preview_url({"image_url": "https://example.com/p.jpg"}) == "https://example.com/p.jpg"
assert neon.product_image_preview_url({"image_url": "http://example.com/p.jpg"}) == "http://example.com/p.jpg"
assert neon.product_image_preview_url({"image_url": ""}) == ""
assert neon.product_image_preview_url({"image_url": None}) == ""
assert neon.product_image_preview_url({"image_url": "ftp://example.com/p.jpg"}) == ""
assert neon.product_image_preview_url(None) == ""
assert neon.product_image_preview_url("https://example.com/p.jpg") == ""


class FakeCursor:
    def __init__(self):
        self.statement = ""

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def execute(self, statement):
        self.statement = " ".join(statement.split()).lower()

    def fetchall(self):
        return rows


class FakeConnection:
    def __init__(self):
        self.cursor_instance = FakeCursor()

    def cursor(self):
        return self.cursor_instance


fake_connection = FakeConnection()


@contextmanager
def fake_neon_connection():
    yield fake_connection


original_ensure_schema = neon.ensure_crm_data_imports_schema
original_neon_connection = neon.neon_connection
try:
    neon.ensure_crm_data_imports_schema = lambda: True
    neon.neon_connection = fake_neon_connection
    assert neon.fetch_order_product_options() == [
        {
            "sku": "SP001",
            "product_name": "Active Product",
            "product_group": "Group A",
            "image_url": "https://example.com/active.jpg",
        },
        {
            "sku": "SP005",
            "product_name": "No Image Product",
            "product_group": "Group C",
            "image_url": "",
        }
    ]
finally:
    neon.ensure_crm_data_imports_schema = original_ensure_schema
    neon.neon_connection = original_neon_connection

assert "where is_active = true and archived_at is null" in fake_connection.cursor_instance.statement


picker_products = [
    {
        "sku": "SP680",
        "product_name": "Coffee Premium",
        "product_group": "Drink",
        "image_url": "https://example.com/sp680.jpg",
    },
    {
        "sku": "SP681",
        "product_name": "Tea Economy",
        "product_group": "Drink",
        "image_url": "",
    },
    {
        "sku": "AB100",
        "product_name": "Snack Box",
        "product_group": "Food",
        "image_url": "ftp://example.com/not-used.jpg",
    },
]

assert manual_ui.product_picker_search_text(picker_products[0]) == "sp680 coffee premium drink"
assert manual_ui.filter_product_picker_options(picker_products, "SP680") == [picker_products[0]]
assert manual_ui.filter_product_picker_options(picker_products, "coffee") == [picker_products[0]]
assert manual_ui.filter_product_picker_options(picker_products, "drink", limit=10) == picker_products[:2]
assert manual_ui.filter_product_picker_options(picker_products, "missing") == []
assert manual_ui.filter_product_picker_options(picker_products, "", limit=2) == []
assert manual_ui.filter_product_picker_options(picker_products, "", limit=20) == []
selector_products = [
    {
        "sku": "SP999",
        "product_name": f"Variant {index:02d}",
        "product_group": "Bundle",
        "image_url": "https://example.com/variant.jpg" if index == 0 else "",
    }
    for index in range(30)
]
selector_matches = manual_ui.filter_product_selector_options(selector_products, "SP999")
assert len(selector_matches) == 30
assert manual_ui.filter_product_selector_options(selector_products, "") == []
assert manual_ui.filter_product_selector_options(selector_products, "variant 05") == [selector_products[5]]
assert manual_ui.normalize_product_selector_page_size(10) == 10
assert manual_ui.normalize_product_selector_page_size(25) == 25
assert manual_ui.normalize_product_selector_page_size(50) == 50
assert manual_ui.normalize_product_selector_page_size(99) == 10
page_items, page, total_pages = manual_ui.paginate_product_selector_options(selector_matches, 1, 10)
assert page_items == selector_products[:10]
assert page == 1
assert total_pages == 3
page_items, page, total_pages = manual_ui.paginate_product_selector_options(selector_matches, 2, 25)
assert page_items == selector_products[25:30]
assert page == 2
assert total_pages == 2
page_items, page, total_pages = manual_ui.paginate_product_selector_options(selector_matches, 99, 50)
assert page_items == selector_products
assert page == 1
assert total_pages == 1
assert manual_ui.selected_product_key(picker_products[0]) == "SP680::Coffee Premium"
assert manual_ui.product_from_key(picker_products, "SP680::Coffee Premium") == picker_products[0]
assert manual_ui.product_from_key(picker_products, "missing") == {}
assert manual_ui.selected_product_image_preview_url(picker_products[0]) == "https://example.com/sp680.jpg"
assert manual_ui.selected_product_image_preview_url(picker_products[1]) == ""
assert manual_ui.selected_product_image_preview_url(picker_products[2]) == ""

manual_source = Path("ui/manual_order_ui.py").read_text(encoding="utf-8")
followup_source = Path("pages/followup.py").read_text(encoding="utf-8")
assert "neon.fetch_order_product_options()" in manual_source
assert "PRODUCT_PICKER_LIMIT = 10" in manual_source
assert "PRODUCT_SELECTOR_PAGE_SIZE_OPTIONS = [10, 25, 50]" in manual_source
assert "render_manual_product_picker(product_options)" in manual_source
assert "render_manual_product_selector_dialog(product_options)" in manual_source
assert "@st.dialog(" in manual_source
assert "manual_product_selector_open" in manual_source
assert "manual_product_selector_query" in manual_source
assert "manual_product_selector_page" in manual_source
assert "manual_product_selector_page_size" in manual_source
assert "manual_product_selector_selected_product" in manual_source
assert "manual_product_selector_selected_product_sku" in manual_source
assert "filter_product_selector_options" in manual_source
assert "paginate_product_selector_options" in manual_source
assert "PRODUCT_SELECTOR_PAGE_SIZE_OPTIONS" in manual_source
assert "page_items, page, total_pages = paginate_product_selector_options" in manual_source
assert "manual_product_query" not in manual_source
assert "st.session_state[\"manual_product_query\"] = \"\"" not in manual_source
assert "manual_product_selector_query" not in inspect.getsource(manual_ui.select_manual_product)
assert "manual_product_picker_hide_results" in manual_source
assert "manual_selected_product" in manual_source
assert "manual_selected_product_sku" in manual_source
assert "filter_product_picker_options" in manual_source
assert "product_picker_search_text" in manual_source
assert "selected_product = selected_manual_product(product_options)" in manual_source
assert "add_manual_order_item(product, int(selected_product_qty or 1), item_amount)" in manual_source
assert "neon.upsert_manual_order_items(" in manual_source
assert "render_manual_product_preview" in manual_source
assert "selected_product_image_preview_url" in manual_source
assert "getattr(neon, \"product_image_preview_url\", None)" in manual_source
assert "st.image(image_url, width=120)" in manual_source
assert "render_manual_order_item_preview(cols[1], item)" in manual_source
assert "\"image_url\": image_url" in manual_source
assert "fetch_order_product_options" in followup_source
assert "for row in fetch_order_product_options()" in followup_source
assert "\"image_url\": clean(row.get(\"image_url\"))" in followup_source
assert "render_popup_product_preview" in followup_source
assert "selected_product_image_preview_url" in followup_source
assert "getattr(neon, \"product_image_preview_url\", None)" in followup_source
assert "POPUP_PRODUCT_SELECTOR_PAGE_SIZE_OPTIONS = [10, 25, 50]" in followup_source
assert "def popup_product_picker_state_key(row_key: str, name: str) -> str:" in followup_source
assert "return f\"{row_key}_product_picker_{name}\"" in followup_source
assert "def filter_popup_product_picker_options(" in followup_source
assert "if not tokens:" in followup_source
assert "return []" in followup_source
assert "def paginate_popup_product_selector_options(" in followup_source
assert "render_popup_product_picker(product_options, prefix)" in followup_source
assert "selected_product = selected_popup_product(product_options, prefix)" in followup_source
assert "product = selected_popup_product(product_options, prefix)" in followup_source
assert "select_popup_product(row_key, product, clean_query)" in followup_source
assert "st.session_state[popup_product_picker_state_key(row_key, \"selected_product\")]" in followup_source
assert "st.session_state[popup_product_picker_state_key(row_key, \"selected_product_sku\")]" in followup_source
assert "st.session_state[popup_product_picker_state_key(row_key, \"hide_results\")]" in followup_source
assert "st.session_state[popup_product_picker_state_key(row_key, \"open\")] = False" in followup_source
assert "st.session_state[popup_product_picker_state_key(row_key, \"query\")] = \"\"" not in followup_source
assert "f\"{prefix}_product_select\"" not in followup_source
assert "pc1.selectbox(" not in followup_source
assert "product_action.form_submit_button" in followup_source
assert "open_product_selector" in followup_source
assert "render_popup_product_selector_dialog(product_options, row_key)" in followup_source
assert "@st.dialog(" in followup_source
assert "popup_product_picker_state_key(prefix, \"open\")" in followup_source
assert "popup_product_picker_state_key(row_key, \"query\")" in followup_source
assert "popup_product_picker_state_key(row_key, \"page\")" in followup_source
assert "popup_product_picker_state_key(row_key, \"page_size\")" in followup_source
assert "popup_product_picker_state_key(row_key, \"previous_query\")" in followup_source
assert "page_items, page, total_pages = paginate_popup_product_selector_options" in followup_source
assert "POPUP_PRODUCT_SELECTOR_PAGE_SIZE_OPTIONS" in followup_source
assert "\"product_group\": clean(row.get(\"product_group\"))" in followup_source
assert "render_popup_order_item_preview(cols[1], item)" in followup_source
assert "\"image_url\": image_url" in followup_source
assert "upsert_manual_order_items(" in followup_source
assert "result = upsert_manual_order_items(" in followup_source
assert "items," in followup_source

followup_tree = ast.parse(followup_source)
needed_followup_defs = {
    "clean",
    "popup_product_picker_state_key",
    "popup_product_picker_search_text",
    "filter_popup_product_picker_options",
    "normalize_popup_product_selector_page_size",
    "paginate_popup_product_selector_options",
    "popup_selected_product_key",
}
followup_subset = [
    node for node in followup_tree.body
    if isinstance(node, ast.FunctionDef) and node.name in needed_followup_defs
]
followup_module = ast.Module(
    body=[ast.Assign(targets=[ast.Name(id="POPUP_PRODUCT_SELECTOR_PAGE_SIZE_OPTIONS", ctx=ast.Store())], value=ast.List(elts=[ast.Constant(10), ast.Constant(25), ast.Constant(50)], ctx=ast.Load())), *followup_subset],
    type_ignores=[],
)
ast.fix_missing_locations(followup_module)
followup_helpers = {}
exec(compile(followup_module, "<followup_helpers>", "exec"), followup_helpers)

assert followup_helpers["popup_product_picker_state_key"]("row_a", "query") == "row_a_product_picker_query"
assert followup_helpers["popup_product_picker_state_key"]("row_b", "query") == "row_b_product_picker_query"
assert followup_helpers["popup_product_picker_search_text"](picker_products[0]) == "sp680 coffee premium drink"
assert followup_helpers["filter_popup_product_picker_options"](picker_products, "SP680") == [picker_products[0]]
assert followup_helpers["filter_popup_product_picker_options"](picker_products, "coffee") == [picker_products[0]]
assert followup_helpers["filter_popup_product_picker_options"](picker_products, "drink") == picker_products[:2]
assert followup_helpers["filter_popup_product_picker_options"](picker_products, "missing") == []
assert followup_helpers["filter_popup_product_picker_options"](picker_products, "") == []
followup_selector_matches = followup_helpers["filter_popup_product_picker_options"](selector_products, "SP999")
assert len(followup_selector_matches) == 30
assert followup_helpers["normalize_popup_product_selector_page_size"](10) == 10
assert followup_helpers["normalize_popup_product_selector_page_size"](25) == 25
assert followup_helpers["normalize_popup_product_selector_page_size"](50) == 50
assert followup_helpers["normalize_popup_product_selector_page_size"](99) == 10
page_items, page, total_pages = followup_helpers["paginate_popup_product_selector_options"](followup_selector_matches, 1, 10)
assert page_items == selector_products[:10]
assert page == 1
assert total_pages == 3
page_items, page, total_pages = followup_helpers["paginate_popup_product_selector_options"](followup_selector_matches, 2, 25)
assert page_items == selector_products[25:30]
assert page == 2
assert total_pages == 2
page_items, page, total_pages = followup_helpers["paginate_popup_product_selector_options"](followup_selector_matches, 99, 50)
assert page_items == selector_products
assert page == 1
assert total_pages == 1
assert followup_helpers["popup_selected_product_key"](picker_products[0]) == "SP680::Coffee Premium"

helper_source = inspect.getsource(neon.fetch_order_product_options).lower()
assert "image_url," in helper_source
assert "fetch_product_options(" not in helper_source
assert "delete " not in helper_source
assert "insert " not in helper_source
assert "update " not in helper_source

print("product order options safety OK")
