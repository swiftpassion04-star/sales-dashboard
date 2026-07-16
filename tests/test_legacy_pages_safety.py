from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

LEGACY_PAGES = [
    "pages/1_รายงาน.py",
    "pages/2_KPI.py",
    "pages/3_sync_status.py",
    "pages/4_เพิ่มข้อมูลลูกค้า.py",
    "pages/5_ฐานข้อมูลลูกค้า.py",
    "pages/6_สินค้า.py",
    "pages/7_พนักงาน.py",
    "pages/8_ประวัติการซื้อ.py",
    "pages/9_ติดตามลูกค้า.py",
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

# Keep this list explicit so Phase 7B handles risky direct-URL legacy pages
# intentionally instead of letting old write/cache-clear paths drift.
HIGH_RISK_LEGACY_PAGES = [
    "pages/3_sync_status.py",
    "pages/4_เพิ่มข้อมูลลูกค้า.py",
    "pages/6_สินค้า.py",
    "pages/7_พนักงาน.py",
    "pages/9_ติดตามลูกค้า.py",
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

assert set(HIGH_RISK_LEGACY_PAGES).issubset(set(LEGACY_PAGES))

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

print("legacy pages safety inventory OK")
