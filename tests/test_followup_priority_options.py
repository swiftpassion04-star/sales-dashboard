import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import neon_utils as neon


TRANSFER_PRIORITY = "\u0e42\u0e2d\u0e19\u0e0a\u0e33\u0e23\u0e30"
LEGACY_UPSELL_TRANSFER_PRIORITY = "Upsell \u0e42\u0e2d\u0e19\u0e0a\u0e33\u0e23\u0e30"
EXPECTED_PRIORITIES = ["Super VIP", "VIP", "Premium", "Economy", "NEW", "Upsell", TRANSFER_PRIORITY, "Dismiss"]
LEGACY_VALUES = ["urgent", "high", "normal", "low", "\u0e14\u0e48\u0e27\u0e19\u0e21\u0e32\u0e01", "\u0e2a\u0e39\u0e07", "\u0e1b\u0e01\u0e15\u0e34", "\u0e15\u0e48\u0e33"]


assert list(neon.FOLLOWUP_PRIORITY_OPTIONS) == EXPECTED_PRIORITIES
assert neon.DEFAULT_FOLLOWUP_PRIORITY == "NEW"

filter_options = ["\u0e17\u0e31\u0e49\u0e07\u0e2b\u0e21\u0e14", *neon.FOLLOWUP_PRIORITY_OPTIONS]
assert filter_options == ["\u0e17\u0e31\u0e49\u0e07\u0e2b\u0e21\u0e14", *EXPECTED_PRIORITIES]

assert neon.normalize_followup_priority("urgent") == "Super VIP"
assert neon.normalize_followup_priority("\u0e14\u0e48\u0e27\u0e19\u0e21\u0e32\u0e01") == "Super VIP"
assert neon.normalize_followup_priority("high") == "VIP"
assert neon.normalize_followup_priority("\u0e2a\u0e39\u0e07") == "VIP"
assert neon.normalize_followup_priority("normal") == "NEW"
assert neon.normalize_followup_priority("\u0e1b\u0e01\u0e15\u0e34") == "NEW"
assert neon.normalize_followup_priority("low") == "Economy"
assert neon.normalize_followup_priority("\u0e15\u0e48\u0e33") == "Economy"

for priority in EXPECTED_PRIORITIES:
    assert neon.normalize_followup_priority(priority) == priority

assert neon.normalize_followup_priority(LEGACY_UPSELL_TRANSFER_PRIORITY) == TRANSFER_PRIORITY
assert neon.normalize_followup_priority(None) == "NEW"
assert neon.normalize_followup_priority("") == "NEW"
assert neon.normalize_followup_priority("unknown") == "NEW"

for legacy_value in LEGACY_VALUES:
    assert legacy_value not in neon.FOLLOWUP_PRIORITY_OPTIONS

assert set(neon.followup_priority_filter_values("Super VIP")) == {
    "Super VIP",
    "urgent",
    "\u0e14\u0e48\u0e27\u0e19\u0e21\u0e32\u0e01",
}
assert set(neon.followup_priority_filter_values("NEW")) == {"NEW", "normal", "\u0e1b\u0e01\u0e15\u0e34"}
assert neon.followup_priority_filter_values("Upsell") == ["Upsell"]
assert set(neon.followup_priority_filter_values(TRANSFER_PRIORITY)) == {
    TRANSFER_PRIORITY,
    LEGACY_UPSELL_TRANSFER_PRIORITY,
}

root = Path(__file__).resolve().parents[1]
followup_page = (root / "pages" / "followup.py").read_text(encoding="utf-8", errors="replace")
customer_detail_page = (root / "pages" / "customer_detail.py").read_text(encoding="utf-8", errors="replace")
customers_page = (root / "pages" / "customers.py").read_text(encoding="utf-8", errors="replace")

assert "PRIORITY_OPTIONS = {priority: priority for priority in FOLLOWUP_PRIORITY_OPTIONS}" in followup_page
assert "PRIORITY_OPTIONS = {priority: priority for priority in FOLLOWUP_PRIORITY_OPTIONS}" in customer_detail_page
assert 'priority = clean(current_followup.get("priority")) or DEFAULT_FOLLOWUP_PRIORITY' in customers_page
assert '"priority": priority' in customers_page
assert "normalize_followup_priority" in followup_page
assert "normalize_followup_priority" in customer_detail_page

for removed_followup_status in ("round_1", "round_2", "round_3", "round_4"):
    assert removed_followup_status not in followup_page
    assert removed_followup_status not in customer_detail_page

print("followup priority options safety OK")
