import inspect
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from crm_data.products import (
    fetch_product_options,
    fetch_product_page,
    insert_product_options,
    normalize_product_image_url,
    update_product_option,
    upsert_product_options,
)


assert normalize_product_image_url(None) is None
assert normalize_product_image_url("") is None
assert normalize_product_image_url("   ") is None
assert normalize_product_image_url(" https://example.com/p.jpg ") == "https://example.com/p.jpg"
assert normalize_product_image_url("http://example.com/p.jpg") == "http://example.com/p.jpg"

options_source = inspect.getsource(fetch_product_options).lower()
page_source = inspect.getsource(fetch_product_page).lower()
upsert_source = inspect.getsource(upsert_product_options).lower()
insert_source = inspect.getsource(insert_product_options).lower()
update_source = inspect.getsource(update_product_option).lower()

assert "image_url," in options_source
assert "image_url," in page_source
assert '"image_url"' in upsert_source
assert '"image_url"' in insert_source
assert '"image_url"' in update_source
assert "normalize_product_image_url" in upsert_source
assert "normalize_product_image_url" in update_source or "_product_record_value" in update_source

products_page = Path("pages/products.py").read_text(encoding="utf-8")
assert "validate_product_image_url" in products_page
assert "normalize_product_image_url" in products_page
assert "product_image_status_label" in products_page
assert "sync_product_image_widget_value" in products_page
assert "product_master_create_image_url" in products_page
assert "pm_image_" in products_page
assert "_row_value" in products_page
assert "cols[4].caption(product_image_status_label(normalized_image_url))" in products_page
assert "placeholder=\"https://...\"" in products_page
assert "http://" in products_page and "https://" in products_page
assert "st.image" in products_page or "container.image" in products_page
assert "requests." not in products_page
assert "urlopen" not in products_page
assert "httpx." not in products_page
assert "fetch_order_product_options" not in products_page

print("product image URL safety OK")
