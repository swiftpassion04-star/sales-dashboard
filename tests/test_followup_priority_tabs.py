from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FOLLOWUP_SOURCE = (ROOT / "pages" / "followup.py").read_text(encoding="utf-8", errors="replace")
NEON_SOURCE = (ROOT / "neon_utils.py").read_text(encoding="utf-8", errors="replace")

EXPECTED_PRIORITIES = ["Super VIP", "VIP", "Premium", "Economy", "NEW", "Dismiss"]
LEGACY_PRIORITIES = ["urgent", "high", "normal", "low", "ด่วนมาก", "สูง", "ปกติ", "ต่ำ"]


assert "FOLLOWUP_PRIORITY_TAB_OPTIONS = tuple(FOLLOWUP_PRIORITY_OPTIONS)" in FOLLOWUP_SOURCE
assert "def render_priority_tabs() -> None:" in FOLLOWUP_SOURCE
assert "render_priority_tabs()" in FOLLOWUP_SOURCE
assert "def set_followup_priority_filter_from_tab(priority: str) -> None:" in FOLLOWUP_SOURCE
assert 'st.session_state["followup_filter_priority"] = normalize_followup_priority(priority)' in FOLLOWUP_SOURCE
assert "st.session_state.followup_page_v2 = 1" in FOLLOWUP_SOURCE

for priority in EXPECTED_PRIORITIES:
    assert priority in NEON_SOURCE
    assert priority in FOLLOWUP_SOURCE

tab_options_line = "FOLLOWUP_PRIORITY_TAB_OPTIONS = tuple(FOLLOWUP_PRIORITY_OPTIONS)"
for legacy_priority in LEGACY_PRIORITIES:
    assert legacy_priority not in tab_options_line

assert "fetch_followup_page(filters, user, page_size, page)" in FOLLOWUP_SOURCE
assert '_followup_staff_scope(user, "d")' in NEON_SOURCE

print("followup priority tabs safety OK")
