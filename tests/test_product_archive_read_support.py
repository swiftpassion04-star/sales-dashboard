import inspect
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from crm_data.products import (
    PRODUCT_STATUS_FILTERS,
    _PRODUCT_STATUS_CLAUSES,
    fetch_product_options,
    fetch_product_page,
)


assert PRODUCT_STATUS_FILTERS == {"all", "active", "inactive", "archived"}
assert _PRODUCT_STATUS_CLAUSES == {
    "active": ("is_active = true", "archived_at is null"),
    "inactive": ("is_active = false", "archived_at is null"),
    "all": ("archived_at is null",),
    "archived": ("archived_at is not null",),
}

signature = inspect.signature(fetch_product_page)
assert signature.parameters["status_filter"].default == "active"
assert signature.parameters["sort_mode"].default == "sku_asc"

page_source = inspect.getsource(fetch_product_page).lower()
assert "delete " not in page_source
assert "archived_at," in page_source
assert "archived_by," in page_source
assert "archive_reason," in page_source
assert page_source.count("{where_sql}") == 2
assert "(sku ilike %s or product_name ilike %s)" in page_source
assert "limit %s offset %s" in page_source
assert "sku_number asc nulls last" in page_source
assert "sku_number desc nulls last" in page_source

options_source = inspect.getsource(fetch_product_options).lower()
assert "archived_at" not in options_source
assert "archived_by" not in options_source
assert "archive_reason" not in options_source

print("product archive read support safety OK")
