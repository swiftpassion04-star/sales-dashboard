import streamlit as st

from crm_theme import inject_saas_theme, render_page_header


PRODUCTS_PAGE = "pages/products.py"


# Canonical CRM routes. Legacy Thai-named pages remain in the repo for
# compatibility, but the sidebar must only point to these English route files.
NAV_GROUPS = [
    ("ภาพรวม", [("📊Dashboard", "pages/dashboard.py")]),
    (
        "ลูกค้า",
        [
            ("🔍ค้นหาลูกค้า", "pages/customers.py"),
            ("🔔ติดตามลูกค้า", "pages/followup.py"),
            ("🛒เพิ่มคำสั่งซื้อ", "pages/import_excel.py"),
        ],
    ),
    (
        "ข้อมูล",
        [
            ("📦สินค้า", PRODUCTS_PAGE),
        ],
    ),
    (
        "ระบบ",
        [
            ("🔄Sync / System Status", "pages/system_status.py"),
            ("👥User / Role", "pages/users.py"),
            ("⚙️Settings", "pages/settings.py"),
        ],
    ),
]


def render_sidebar_nav() -> None:
    inject_saas_theme()
    st.sidebar.markdown(
        """
<div class="crm-nav-brand">
  <div class="crm-nav-brand-title">Sales CRM</div>
  <div class="crm-nav-brand-subtitle">Telesales workspace</div>
</div>
""",
        unsafe_allow_html=True,
    )
    for group, links in NAV_GROUPS:
        st.sidebar.markdown(f'<div class="crm-nav-title">{group}</div>', unsafe_allow_html=True)
        for label, page in links:
            st.sidebar.page_link(page, label=label)
        st.sidebar.markdown('<div class="crm-nav-spacer"></div>', unsafe_allow_html=True)


def render_placeholder_page(title: str, description: str = "เตรียมพื้นที่สำหรับพัฒนาต่อ") -> None:
    render_sidebar_nav()
    render_page_header(title, description)
    st.markdown(f'<div class="crm-card crm-muted">{description}</div>', unsafe_allow_html=True)
