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
assert "render_manual_product_picker(product_options)" in manual_source
assert "if not clean_query:" in manual_source
assert "manual_product_query" in manual_source
assert "manual_selected_product" in manual_source
assert "manual_selected_product_sku" in manual_source
assert "filter_product_picker_options" in manual_source
assert "product_picker_search_text" in manual_source
assert "selected_product = selected_manual_product(product_options)" in manual_source
assert "add_manual_order_item(product, int(selected_product_qty or 1), item_amount)" in manual_source
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
assert "product_labels = [popup_product_label(item) for item in product_options]" in followup_source
assert "[PRODUCT_PLACEHOLDER," not in followup_source
assert "placeholder=\"\"" in followup_source
assert "if not label:" in followup_source
assert "render_popup_order_item_preview(cols[1], item)" in followup_source
assert "\"image_url\": image_url" in followup_source

helper_source = inspect.getsource(neon.fetch_order_product_options).lower()
assert "image_url," in helper_source
assert "fetch_product_options(" not in helper_source
assert "delete " not in helper_source
assert "insert " not in helper_source
assert "update " not in helper_source

print("product order options safety OK")
