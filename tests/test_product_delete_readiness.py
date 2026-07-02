import inspect
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from crm_data.products import (
    _PRODUCT_DELETE_READINESS_SQL,
    build_product_delete_readiness,
    fetch_product_delete_readiness,
)


def product_row(product_id, sku="SP001", product_name="Product", **counts):
    return {
        "product_id": product_id,
        "sku": sku,
        "product_name": product_name,
        "imports_sku_count": 0,
        "imports_name_count": 0,
        "imports_raw_sku_count": 0,
        "order_items_sku_count": 0,
        "order_items_name_count": 0,
        **counts,
    }


used_import = build_product_delete_readiness(
    [1],
    [product_row(1, imports_sku_count=2)],
)[1]
assert used_import["status"] == "blocked_used"
assert used_import["usage_sources"] == ["crm_data_imports.sku"]

used_order_item = build_product_delete_readiness(
    [2],
    [product_row(2, order_items_name_count=1)],
)[2]
assert used_order_item["status"] == "blocked_used"
assert used_order_item["usage_sources"] == ["crm_order_items.product_name"]

tentative = build_product_delete_readiness([3], [product_row(3)])[3]
assert tentative["status"] == "tentative_no_usage"
assert tentative["reason"] == "no_usage_found_in_text_checks"

missing = build_product_delete_readiness([4], [])[4]
assert missing["status"] == "unsafe_unknown"
assert missing["reason"] == "product_not_found"

blank = build_product_delete_readiness(
    [5],
    [product_row(5, sku="", product_name="")],
)[5]
assert blank["status"] == "unsafe_unknown"
assert blank["reason"] == "blank_sku_and_product_name"

check_error = build_product_delete_readiness(
    [6],
    [],
    check_error="ConnectionTimeout",
)[6]
assert check_error["status"] == "unsafe_unknown"
assert check_error["reason"] == "usage_check_error:ConnectionTimeout"

normalized_sql = " ".join(_PRODUCT_DELETE_READINESS_SQL.lower().split())
for forbidden_statement in ("delete ", "update ", "insert ", "alter ", "drop ", "truncate "):
    assert forbidden_statement not in normalized_sql
assert normalized_sql.startswith("select ")

readiness_source = inspect.getsource(fetch_product_delete_readiness).lower()
assert "ensure_crm_data_imports_schema" not in readiness_source

print("product delete readiness safety OK")
