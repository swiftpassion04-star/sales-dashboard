import html

import streamlit as st


def inject_saas_theme() -> None:
    st.markdown(
        """
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700;800&family=Plus+Jakarta+Sans:wght@500;600;700;800&family=Noto+Sans+Thai:wght@400;500;600;700;800&display=swap');
:root {
  --crm-primary:#FF8C42;
  --crm-primary-soft:#FFDBB5;
  --crm-primary-pale:#FFF4EB;
  --crm-bg:#FFF9F5;
  --crm-surface:#FFFFFF;
  --crm-border:#FFE0C2;
  --crm-text:#2D1F0E;
  --crm-muted:#8A6A52;
  --crm-soft:#FFF4EB;
  --crm-success:#16A34A;
  --crm-warning:#F59E0B;
  --crm-danger:#DC2626;
  --crm-radius:8px;
  --crm-shadow:0 1px 1px rgba(45,31,14,.03);
}
html, body, [class*="css"], .stApp {
  font-family:"DM Sans","Noto Sans Thai",system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif !important;
  font-size:15px;
}
.stApp {
  background:var(--crm-bg) !important;
  color:var(--crm-text) !important;
}
.block-container {
  max-width:1440px;
  padding:28px 36px 60px;
}
[data-testid="stSidebar"] {
  width:240px !important;
  min-width:240px !important;
  background:var(--crm-primary-pale) !important;
  border-right:1px solid var(--crm-border) !important;
}
[data-testid="stSidebar"] > div:first-child {
  width:240px !important;
}
[data-testid="stSidebar"] * {
  color:var(--crm-text) !important;
}
[data-testid="stSidebarNav"] {
  display:none !important;
}
.crm-shell-header {
  display:flex;
  justify-content:space-between;
  gap:16px;
  align-items:flex-start;
  margin:2px 0 22px;
}
.crm-eyebrow {
  color:var(--crm-muted);
  font-size:12px;
  font-weight:700;
  letter-spacing:.03em;
  margin-bottom:6px;
}
.crm-title,
h1 {
  font-family:"Plus Jakarta Sans","Noto Sans Thai",system-ui,sans-serif !important;
  color:var(--crm-text) !important;
  font-size:28px !important;
  line-height:1.22 !important;
  font-weight:800 !important;
  letter-spacing:0 !important;
  margin:0 !important;
}
h2 {
  font-family:"Plus Jakarta Sans","Noto Sans Thai",system-ui,sans-serif !important;
  color:var(--crm-text) !important;
  font-size:22px !important;
  line-height:1.3 !important;
  font-weight:750 !important;
}
h3 {
  font-family:"Plus Jakarta Sans","Noto Sans Thai",system-ui,sans-serif !important;
  color:var(--crm-text) !important;
  font-size:17px !important;
  line-height:1.35 !important;
  font-weight:750 !important;
}
.crm-subtitle {
  color:var(--crm-muted);
  font-size:15px;
  margin-top:8px;
}
.crm-card {
  background:var(--crm-surface);
  border:1px solid var(--crm-border);
  border-radius:var(--crm-radius);
  box-shadow:var(--crm-shadow);
  padding:20px;
}
.crm-section-title {
  color:var(--crm-text);
  font-family:"Plus Jakarta Sans","Noto Sans Thai",system-ui,sans-serif;
  font-size:17px;
  font-weight:800;
  margin:20px 0 12px;
}
.crm-nav-brand {
  padding:10px 10px 18px;
  margin:0 0 12px;
  border-bottom:1px solid var(--crm-border);
}
.crm-nav-brand-title {
  font-family:"Plus Jakarta Sans","Noto Sans Thai",system-ui,sans-serif;
  font-size:17px;
  font-weight:800;
  color:var(--crm-text);
}
.crm-nav-brand-subtitle {
  font-size:12px;
  color:var(--crm-muted) !important;
  margin-top:3px;
}
.crm-nav-title {
  margin:18px 10px 6px;
  color:var(--crm-muted) !important;
  font-size:12px;
  font-weight:800;
  text-transform:uppercase;
  letter-spacing:.04em;
}
.crm-nav-spacer {
  height:8px;
}
[data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"] {
  min-height:38px !important;
  border-radius:8px !important;
  padding:8px 10px 8px 12px !important;
  border-left:3px solid transparent !important;
  font-weight:650 !important;
}
[data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"]:hover {
  background:#FFEAD6 !important;
  border-left-color:var(--crm-primary-soft) !important;
}
[data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"][aria-current="page"] {
  background:var(--crm-primary-soft) !important;
  border-left-color:var(--crm-primary) !important;
  color:var(--crm-text) !important;
}
p, label, span, small, div[data-testid="stMarkdownContainer"] {
  color:var(--crm-text);
  letter-spacing:0;
}
[data-testid="stCaptionContainer"] {
  color:var(--crm-muted) !important;
}
[data-testid="stForm"],
[data-testid="stExpander"],
[data-testid="stDataFrame"],
[data-testid="stMetric"],
[data-testid="stFileUploader"] {
  background:var(--crm-surface) !important;
  border:1px solid var(--crm-border) !important;
  border-radius:8px !important;
  box-shadow:var(--crm-shadow) !important;
}
[data-testid="stForm"] {
  padding:18px !important;
}
[data-testid="stMetric"] {
  padding:18px !important;
}
[data-testid="stMetric"] label,
[data-testid="stMetric"] label *,
[data-testid="stMetricLabel"],
[data-testid="stMetricLabel"] * {
  color:var(--crm-muted) !important;
  font-size:13px !important;
  font-weight:700 !important;
}
[data-testid="stMetricValue"] {
  color:var(--crm-text) !important;
  font-family:"Plus Jakarta Sans","Noto Sans Thai",system-ui,sans-serif !important;
  font-weight:800 !important;
}
div[data-baseweb="input"] > div,
div[data-baseweb="select"] > div,
div[data-baseweb="base-input"],
div[data-baseweb="textarea"],
textarea,
input {
  background:var(--crm-surface) !important;
  color:var(--crm-text) !important;
  -webkit-text-fill-color:var(--crm-text) !important;
  border:1px solid var(--crm-border) !important;
  border-radius:8px !important;
  box-shadow:none !important;
  font-size:15px !important;
}
div[data-baseweb="input"] > div:focus-within,
div[data-baseweb="select"] > div:focus-within,
textarea:focus,
input:focus {
  border-color:var(--crm-primary) !important;
  box-shadow:0 0 0 3px rgba(255,140,66,.14) !important;
  outline:none !important;
}
input::placeholder,
textarea::placeholder {
  color:#B5967E !important;
}
div[data-baseweb="select"] svg,
div[data-baseweb="input"] svg {
  color:var(--crm-muted) !important;
  fill:var(--crm-muted) !important;
}
div[data-baseweb="popover"],
div[data-baseweb="menu"],
ul[role="listbox"] {
  background:var(--crm-surface) !important;
  border-color:var(--crm-border) !important;
  color:var(--crm-text) !important;
}
div[role="option"] {
  color:var(--crm-text) !important;
}
div[role="option"]:hover {
  background:var(--crm-primary-pale) !important;
}
.stButton > button,
button[kind="formSubmit"],
div.stDownloadButton > button {
  min-height:40px !important;
  border-radius:8px !important;
  border:1px solid var(--crm-border) !important;
  background:var(--crm-surface) !important;
  color:var(--crm-text) !important;
  font-weight:750 !important;
  box-shadow:none !important;
}
.stButton > button:hover,
div.stDownloadButton > button:hover {
  border-color:var(--crm-primary) !important;
  color:var(--crm-text) !important;
  background:var(--crm-primary-pale) !important;
}
button[kind="formSubmit"],
.stButton > button[kind="primary"] {
  background:var(--crm-primary) !important;
  color:#FFFFFF !important;
  border-color:var(--crm-primary) !important;
}
button[kind="formSubmit"]:hover,
.stButton > button[kind="primary"]:hover {
  background:#F47C2C !important;
  color:#FFFFFF !important;
  border-color:#F47C2C !important;
}
[data-testid="stExpander"] details,
[data-testid="stExpander"] details summary,
[data-testid="stExpander"] details summary *,
[data-testid="stFileUploader"] section,
[data-testid="stFileUploader"] section * {
  background:var(--crm-surface) !important;
  color:var(--crm-text) !important;
}
[data-testid="stFileUploader"] section {
  border-color:var(--crm-border) !important;
}
[data-testid="stAlert"] {
  border-radius:8px !important;
  border-color:var(--crm-border) !important;
  color:var(--crm-text) !important;
}
[data-testid="stAlert"] * {
  color:var(--crm-text) !important;
}
.crm-badge {
  display:inline-flex;
  align-items:center;
  min-height:24px;
  padding:2px 9px;
  border-radius:999px;
  background:var(--crm-soft);
  color:var(--crm-text);
  font-weight:750;
  font-size:12px;
}
.crm-badge-blue { background:#FFEAD6; color:#9A4B12; }
.crm-badge-green { background:#E9F8EF; color:#166534; }
.crm-badge-yellow { background:#FFF3CC; color:#8A5A00; }
.crm-badge-orange { background:#FFDBB5; color:#8F3D08; }
.crm-badge-red { background:#FDE4E4; color:#B91C1C; }
.crm-badge-gray { background:#F6EEE8; color:#7B5C44; }
.crm-table {
  width:100%;
  border-collapse:separate;
  border-spacing:0;
  overflow:hidden;
  border:1px solid var(--crm-border);
  border-radius:8px;
  background:var(--crm-surface);
}
.crm-table-header,
.crm-table-row {
  display:grid;
  gap:0;
  align-items:center;
}
.crm-table-header {
  min-height:48px;
  background:var(--crm-primary-pale);
  border-bottom:1px solid var(--crm-border);
  color:var(--crm-muted);
  font-size:13px;
  font-weight:800;
}
.crm-table-row {
  min-height:52px;
  border-bottom:1px solid #FFF0E2;
}
.crm-table-row:nth-child(even) {
  background:#FFFCFA;
}
.crm-table-row:hover {
  background:#FFF4EB;
}
.crm-table-row:last-child {
  border-bottom:0;
}
.crm-table-cell {
  padding:11px 12px;
  color:var(--crm-text);
  font-size:15px;
  overflow-wrap:anywhere;
}
.crm-inline-detail-title {
  margin:10px 0 8px;
  padding:10px 14px;
  background:var(--crm-primary-pale);
  border:1px solid var(--crm-border);
  border-radius:8px;
  color:var(--crm-text);
  font-size:15px;
  font-weight:800;
}
.crm-muted {
  color:var(--crm-muted) !important;
}
a.crm-link {
  color:#C45A1B !important;
  font-weight:750;
  text-decoration:none;
}
a.crm-link:hover {
  color:#9A4B12 !important;
  text-decoration:underline;
}
@media (max-width: 900px) {
  .block-container {
    padding:18px 16px 48px;
  }
  .crm-shell-header {
    display:block;
  }
}
</style>
""",
        unsafe_allow_html=True,
    )


def render_page_header(title: str, subtitle: str = "", eyebrow: str = "CRM Core") -> None:
    st.markdown(
        f"""
<div class="crm-shell-header">
  <div>
    <div class="crm-eyebrow">{html.escape(eyebrow)}</div>
    <h1 class="crm-title">{html.escape(title)}</h1>
    <div class="crm-subtitle">{html.escape(subtitle)}</div>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )


def badge(text: str, tone: str = "gray") -> str:
    safe = html.escape(str(text or "-"))
    return f'<span class="crm-badge crm-badge-{tone}">{safe}</span>'
