import streamlit as st


NAV_GROUPS = [
    (
        "📊 Dashboard",
        [
            ("CRM Dashboard", "crm_dashboard.py"),
            ("รายงาน", "pages/1_รายงาน.py"),
            ("KPI", "pages/2_KPI.py"),
        ],
    ),
    (
        "👥 ลูกค้า",
        [
            ("สร้างคำสั่งซื้อ", "pages/4_เพิ่มข้อมูลลูกค้า.py"),
            ("ข้อมูลลูกค้า", "pages/5_ฐานข้อมูลลูกค้า.py"),
            ("ประวัติการซื้อ", "pages/8_ประวัติการซื้อ.py"),
            ("ติดตามลูกค้า", "pages/9_ติดตามลูกค้า.py"),
        ],
    ),
    (
        "📦 ข้อมูล",
        [
            ("สินค้า", "pages/6_สินค้า.py"),
        ],
    ),
    (
        "⚙️ ตั้งค่า",
        [
            ("พนักงาน", "pages/7_พนักงาน.py"),
            ("Sync Status", "pages/3_sync_status.py"),
            ("System Settings", "pages/10_System_Settings.py"),
        ],
    ),
]


def render_sidebar_nav() -> None:
    st.sidebar.markdown(
        """
<style>
[data-testid="stSidebarNav"] {
  display:none !important;
}
[data-testid="stSidebar"] {
  background:linear-gradient(180deg,#ffffff 0%,#fff7ed 100%) !important;
  border-right:1px solid #fed7aa !important;
}
[data-testid="stSidebar"] * {
  color:#111827 !important;
}
.crm-nav-title {
  margin:14px 0 6px;
  font-weight:900;
  color:#9a3412 !important;
  font-size:15px;
}
.crm-nav-spacer {
  height:8px;
}
[data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"] {
  border-radius:8px !important;
  min-height:34px !important;
  padding:6px 10px !important;
  font-weight:700 !important;
}
[data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"]:hover,
[data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"][aria-current="page"] {
  background:#ffedd5 !important;
  color:#ea580c !important;
}
</style>
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
    st.title(title)
    st.info(description)
