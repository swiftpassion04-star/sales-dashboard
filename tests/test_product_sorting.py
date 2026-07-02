import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from crm_data.products import sku_sort_key


assert sku_sort_key("SP 001")[:2] == (0, 1)
assert sku_sort_key("SP001")[:2] == (0, 1)
assert sku_sort_key("SP604")[:2] == (0, 604)
assert sku_sort_key("SP566-1\u0e0a\u0e34\u0e49\u0e19")[:2] == (0, 566)
assert sku_sort_key("SP673-300W 12V")[:2] == (0, 673)

assert sku_sort_key("SKU-100")[0] == 1
assert sku_sort_key("")[0] == 1
assert sku_sort_key(None)[0] == 1

ordered = sorted(
    ["SKU-100", "SP673-300W 12V", "SP604", "SP 001", "SP566-1\u0e0a\u0e34\u0e49\u0e19"],
    key=sku_sort_key,
)
assert ordered == [
    "SP 001",
    "SP566-1\u0e0a\u0e34\u0e49\u0e19",
    "SP604",
    "SP673-300W 12V",
    "SKU-100",
]

print("product SKU sorting characterization OK")
