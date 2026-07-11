from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CUSTOMERS_SOURCE = (ROOT / "pages" / "customers.py").read_text(encoding="utf-8", errors="replace")

EXPECTED_RESET_KEYS = [
    "followup_filter_priority",
    "followup_filter_lead_status",
    "followup_filter_followup_status",
]

PRESERVED_KEYS = [
    "followup_filter_keyword",
    "followup_filter_date_mode",
    "followup_filter_single_date",
    "followup_filter_date_range",
    "followup_filter_owner",
    "customers_page",
]


assert "OWNER_ASSIGNMENT_FOLLOWUP_FILTER_RESET_KEYS" in CUSTOMERS_SOURCE
assert "def reset_owner_assignment_followup_filters() -> None:" in CUSTOMERS_SOURCE
assert "reset_owner_assignment_followup_filters()" in CUSTOMERS_SOURCE

for key in EXPECTED_RESET_KEYS:
    assert f'"{key}"' in CUSTOMERS_SOURCE

reset_block = CUSTOMERS_SOURCE.split("OWNER_ASSIGNMENT_FOLLOWUP_FILTER_RESET_KEYS", 1)[1].split("EXPORT_PERIOD_OPTIONS", 1)[0]
assert "followup_filter_priority" in reset_block
assert "followup_filter_lead_status" in reset_block
assert "followup_filter_followup_status" in reset_block

helper_block = CUSTOMERS_SOURCE.split("def reset_owner_assignment_followup_filters() -> None:", 1)[1].split("def main() -> None:", 1)[0]
assert "st.session_state.pop(key, None)" in helper_block

for key in PRESERVED_KEYS:
    assert f'"{key}"' not in reset_block
    assert f'"{key}"' not in helper_block

print("customer owner assignment filter reset safety OK")
