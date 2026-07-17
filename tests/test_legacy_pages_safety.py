from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PAGES_DIR = ROOT / "pages"


def one(pattern: str) -> Path:
    matches = sorted(PAGES_DIR.glob(pattern))
    assert len(matches) == 1, f"Expected one page for {pattern}, found {matches}"
    return matches[0]


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


LEGACY_PAGES = [
    rel(one("1_*.py")),
    "pages/2_KPI.py",
    "pages/3_sync_status.py",
    rel(one("4_*.py")),
    rel(one("5_*.py")),
    rel(one("6_*.py")),
    rel(one("7_*.py")),
    rel(one("8_*.py")),
    rel(one("9_*.py")),
    "pages/10_System_Settings.py",
]

CANONICAL_PAGES = [
    "pages/dashboard.py",
    "pages/customers.py",
    "pages/followup.py",
    "pages/import_excel.py",
    "pages/products.py",
    "pages/users.py",
    "pages/customer_detail.py",
    "pages/team_sales.py",
]

HIGH_RISK_LEGACY_TARGETS = {
    "pages/3_sync_status.py": "pages/system_status.py",
    rel(one("4_*.py")): "pages/import_excel.py",
    rel(one("6_*.py")): "pages/products.py",
    rel(one("7_*.py")): "pages/users.py",
    rel(one("9_*.py")): "pages/followup.py",
}

LEGACY_WRITE_TOKENS = [
    "upsert_manual_order_items",
    "insert_import_records",
    "delete_import_batch",
    "upsert_product_options",
    "update_product_option",
    "delete_product_option",
    "upsert_staff_option",
    "update_staff_option",
    "delete_staff_option",
    "upsert_lead_followup",
    "st.cache_data.clear()",
]


def read_source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def page_link_targets(source: str) -> list[str]:
    targets: list[str] = []
    for marker in ("st.sidebar.page_link(", "st.page_link("):
        offset = 0
        while True:
            index = source.find(marker, offset)
            if index == -1:
                break
            segment = source[index : index + 220]
            for quote in ('"', "'"):
                route_start = segment.find(f"{quote}pages/")
                if route_start != -1:
                    route_end = segment.find(quote, route_start + 1)
                    targets.append(segment[route_start + 1 : route_end])
                    break
            offset = index + len(marker)
    return targets


for page in LEGACY_PAGES:
    assert (ROOT / page).is_file(), f"Missing legacy page inventory item: {page}"

for page in CANONICAL_PAGES:
    assert (ROOT / page).is_file(), f"Missing canonical page inventory item: {page}"

assert set(HIGH_RISK_LEGACY_TARGETS).issubset(set(LEGACY_PAGES))
for target in HIGH_RISK_LEGACY_TARGETS.values():
    assert (ROOT / target).is_file(), f"Missing high-risk legacy redirect target: {target}"

nav_source = read_source("nav_utils.py")
app_source = read_source("app.py")
theme_source = read_source("crm_theme.py")

for page in CANONICAL_PAGES:
    if page != "pages/customer_detail.py":
        assert page in nav_source or page in app_source

for target in page_link_targets(nav_source) + page_link_targets(app_source):
    assert target not in LEGACY_PAGES, f"Custom navigation points to legacy page: {target}"

for legacy_page in LEGACY_PAGES:
    assert f'"{legacy_page}"' not in nav_source
    assert f"'{legacy_page}'" not in nav_source
    assert f'"{legacy_page}"' not in app_source
    assert f"'{legacy_page}'" not in app_source

assert '[data-testid="stSidebarNav"]' in theme_source
sidebar_nav_block = theme_source.split('[data-testid="stSidebarNav"]', 1)[1].split("}", 1)[0]
assert "display:none" in sidebar_nav_block.replace(" ", "")

for legacy_page, canonical_target in HIGH_RISK_LEGACY_TARGETS.items():
    source = read_source(legacy_page)
    assert "\u0e2b\u0e19\u0e49\u0e32\u0e40\u0e01\u0e48\u0e32" in source
    assert "st.stop()" in source
    assert "st.page_link(" in source
    assert canonical_target in source
    for token in LEGACY_WRITE_TOKENS:
        assert token not in source, f"{legacy_page} still contains risky legacy token: {token}"

print("legacy pages safety inventory OK")
