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
assert manual_ui.parse_required_price_input("")[0] is False
assert manual_ui.parse_required_price_input(None)[0] is False
zero_ok, zero_amount, zero_error = manual_ui.parse_required_price_input("0")
assert zero_ok is True
assert zero_amount == 0.0
assert zero_error == ""
invalid_ok, _invalid_amount, invalid_error = manual_ui.parse_required_price_input("abc")
assert invalid_ok is False
assert invalid_error

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
assert "add_manual_order_item(product, 1, None)" in manual_source
assert "add_product_submitted" not in manual_source
assert "selected_product_qty" not in manual_source
assert "selected_product_amount" not in manual_source
assert "parse_required_price_input" in manual_source
assert "amount_value = \"\" if amount in (None, \"\") else amount" in manual_source
assert "key=f\"manual_item_amount_{index}\"" in manual_source
assert "cols[3].text_input(" in manual_source
assert "price_ok, parsed_amount, _price_error = parse_required_price_input(item.get(\"amount\"))" in manual_source
assert "item[\"amount\"] = parsed_amount" in manual_source
assert "key=f\"manual_item_qty_{index}\"" in manual_source
assert "key=f\"manual_item_amount_{index}\"" in manual_source
assert "item[\"qty\"] = int(qty_value or 1)" in manual_source
assert "item[\"amount\"] = str(amount_value or \"\").strip()" in manual_source
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
assert "select_popup_product(row_key, product, clean_query)" in followup_source
assert "add_popup_order_item(row_key, product, 1, None)" in followup_source
assert "parse_required_price_input" in followup_source
assert "add_item = pc4.form_submit_button" not in followup_source
assert "selected_amount" not in followup_source
assert "selected_qty" not in followup_source
assert "amount_value = \"\" if amount in (None, \"\") else amount" in followup_source
assert "cols[3].text_input(" in followup_source
assert "price_ok, parsed_amount, _price_error = parse_required_price_input(item.get(\"amount\"))" in followup_source
assert "item[\"amount\"] = parsed_amount" in followup_source
assert "st.session_state[popup_product_picker_state_key(row_key, \"selected_product\")]" in followup_source
assert "st.session_state[popup_product_picker_state_key(row_key, \"selected_product_sku\")]" in followup_source
assert "st.session_state[popup_product_picker_state_key(row_key, \"hide_results\")]" in followup_source
assert "st.session_state[popup_product_picker_state_key(row_key, \"open\")] = False" in followup_source
assert "st.session_state[popup_product_picker_state_key(row_key, \"query\")] = \"\"" not in followup_source
assert "f\"{prefix}_product_select\"" not in followup_source
assert "pc1.selectbox(" not in followup_source
assert "product_action.form_submit_button" in followup_source
assert "open_product_selector" in followup_source
assert "render_popup_product_selector_panel(product_options, row_key)" in followup_source
assert "def render_popup_product_selector_panel" in followup_source
assert "st.container(border=True)" in followup_source
assert "@st.dialog(" not in followup_source.split("def render_popup_product_picker", 1)[1]
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
assert "key=f\"{prefix}_item_qty_{index}\"" in followup_source
assert "key=f\"{prefix}_item_amount_{index}\"" in followup_source
assert "item[\"qty\"] = int(qty_value or 1)" in followup_source
assert "item[\"amount\"] = str(amount_value or \"\").strip()" in followup_source
assert "upsert_manual_order_items(" in followup_source
assert "result = upsert_manual_order_items(" in followup_source
assert "items," in followup_source
assert "def followup_option_or_default(value: str, options: dict, default: str) -> str:" in followup_source
assert "st.session_state[f\"{prefix}_lead_status\"]" in followup_source
assert "st.session_state[f\"{prefix}_followup_status\"]" in followup_source
assert "st.session_state[f\"{prefix}_priority\"]" in followup_source
assert "st.session_state[f\"{prefix}_next_followup_date\"]" in followup_source
assert "row.get(\"lead_status\")" in followup_source
assert "row.get(\"followup_status\")" in followup_source
assert "row.get(\"priority\")" in followup_source
assert "row.get(\"next_followup_date\")" in followup_source
assert "list(LEAD_STATUS_OPTIONS.keys())" in followup_source
assert "list(FOLLOWUP_STATUS_OPTIONS.keys())" in followup_source
assert "list(PRIORITY_OPTIONS.keys())" in followup_source
assert "key=f\"{prefix}_lead_status\"" in followup_source
assert "key=f\"{prefix}_followup_status\"" in followup_source
assert "key=f\"{prefix}_priority\"" in followup_source
assert "date_input(" in followup_source
assert "key=f\"{prefix}_next_followup_date\"" in followup_source
assert neon.FOLLOWUP_PRIORITY_OPTIONS == ("Super VIP", "VIP", "Premium", "Economy", "NEW", "Dismiss")

order_dialog_source = followup_source.split("def _render_order_dialog", 1)[1].split(
    "def find_popup_order_owner_conflict",
    1,
)[0]
assert "def build_popup_followup_payload(row: dict, user: dict, prefix: str)" in followup_source
assert "def serialize_popup_followup_date(value)" in followup_source
assert "followup_payload, followup_update_errors = build_popup_followup_payload(row, user, prefix)" in order_dialog_source
assert "upsert_lead_followup(followup_payload)" in order_dialog_source
assert order_dialog_source.index("result = upsert_manual_order_items(") < order_dialog_source.index(
    "followup_payload, followup_update_errors = build_popup_followup_payload(row, user, prefix)"
)
assert order_dialog_source.index(
    "followup_payload, followup_update_errors = build_popup_followup_payload(row, user, prefix)"
) < order_dialog_source.index("upsert_lead_followup(followup_payload)")
assert order_dialog_source.index("upsert_lead_followup(followup_payload)") < order_dialog_source.index(
    "clear_popup_order_state(prefix, row)"
)
validate_fail_source = order_dialog_source.split("if errors:", 1)[1].split("if not can_manage_all(user):", 1)[0]
assert "upsert_lead_followup(" not in validate_fail_source
save_fail_source = order_dialog_source.split("except Exception as exc:", 1)[1].split(
    'duplicate_lock_warning = neon.clean(result.get("duplicate_lock_warning"))',
    1,
)[0]
assert "upsert_lead_followup(" not in save_fail_source
for field in (
    '"customer_name"',
    '"phone1"',
    '"phone2"',
    '"url"',
    '"lead_status"',
    '"followup_status"',
    '"follow_up_status"',
    '"next_followup_date"',
    '"follow_up_date"',
    '"priority"',
):
    assert field in followup_source
assert "lead_status not in LEAD_STATUS_OPTIONS" in followup_source
assert "followup_status not in FOLLOWUP_STATUS_OPTIONS" in followup_source
assert "priority not in FOLLOWUP_PRIORITY_OPTIONS" in followup_source
assert "if isinstance(value, date):" in followup_source
assert "return value.isoformat(), """ in followup_source
assert "clear_popup_order_state(prefix, row)" in order_dialog_source
assert "def upsert_manual_order_items" not in followup_source

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
