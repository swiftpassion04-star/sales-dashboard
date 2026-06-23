import html

import streamlit as st


def inject_saas_theme() -> None:
    st.markdown(
        """
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+Thai:wght@400;500;600;700;800&display=swap');
:root {
  --crm-primary:#F97316;
  --crm-primary-hover:#EA580C;
  --crm-primary-press:#C2410C;
  --crm-primary-tint:#FDBA74;
  --crm-primary-soft:#FED7AA;
  --crm-primary-pale:#FFF2E2;
  --crm-bg:#FFF8F0;
  --crm-bg-soft:#FFF3E8;
  --crm-bg-lift:#FFFDF9;
  --crm-surface:#FFFFFF;
  --crm-border:#F3E4D2;
  --crm-text:#1F2937;
  --crm-muted:#6B7280;
  --crm-warm-muted:#8A6A52;
  --crm-soft:#FFF5EB;
  --crm-success:#16A34A;
  --crm-warning:#F59E0B;
  --crm-danger:#DC2626;
  --crm-radius:18px;
  --crm-radius-sm:14px;
  --crm-pill:999px;
  --crm-shadow:0 18px 42px rgba(124, 45, 18, .10);
  --crm-shadow-soft:0 4px 14px rgba(124, 45, 18, .045);
  --crm-shadow-focus:0 0 0 4px rgba(249,115,22,.14);
}
html, body, [class*="css"], .stApp {
  font-family:"Noto Sans Thai",system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif !important;
  font-size:15px;
}
.stApp {
  background:
    radial-gradient(circle at 14% 8%, rgba(255, 219, 181, .52), transparent 28%),
    radial-gradient(circle at 88% 0%, rgba(255, 242, 226, .72), transparent 32%),
    var(--crm-bg) !important;
  color:var(--crm-text) !important;
}
.block-container {
  max-width:1480px;
  padding:32px 40px 64px;
}
[data-testid="stSidebar"] {
  width:240px !important;
  min-width:240px !important;
  background:var(--crm-bg-soft) !important;
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
  margin:2px 0 24px;
}
.crm-eyebrow {
  color:#9A5A22;
  font-size:12px;
  font-weight:700;
  letter-spacing:0;
  margin-bottom:6px;
}
.crm-title,
h1 {
  font-family:"Noto Sans Thai",system-ui,sans-serif !important;
  color:var(--crm-text) !important;
  font-size:28px !important;
  line-height:1.22 !important;
  font-weight:800 !important;
  letter-spacing:0 !important;
  margin:0 !important;
}
h2 {
  font-family:"Noto Sans Thai",system-ui,sans-serif !important;
  color:var(--crm-text) !important;
  font-size:22px !important;
  line-height:1.3 !important;
  font-weight:750 !important;
}
h3 {
  font-family:"Noto Sans Thai",system-ui,sans-serif !important;
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
  box-shadow:var(--crm-shadow-soft);
  padding:24px;
}
.crm-section-title {
  color:var(--crm-text);
  font-family:"Noto Sans Thai",system-ui,sans-serif;
  font-size:17px;
  font-weight:800;
  margin:20px 0 12px;
}
.crm-nav-brand {
  padding:14px 12px 20px;
  margin:0 0 14px;
  border-bottom:1px solid var(--crm-border);
}
.crm-nav-brand-title {
  font-family:"Noto Sans Thai",system-ui,sans-serif;
  font-size:18px;
  font-weight:800;
  color:var(--crm-text);
}
.crm-nav-brand-subtitle {
  font-size:12px;
  color:var(--crm-muted) !important;
  margin-top:3px;
}
.crm-nav-title {
  margin:20px 12px 8px;
  color:var(--crm-muted) !important;
  font-size:12px;
  font-weight:800;
  text-transform:none;
  letter-spacing:0;
}
.crm-nav-spacer {
  height:8px;
}
[data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"] {
  min-height:42px !important;
  border-radius:var(--crm-pill) !important;
  padding:10px 14px 10px 16px !important;
  border-left:3px solid transparent !important;
  font-weight:650 !important;
  margin:3px 0 !important;
}
[data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"]:hover {
  background:var(--crm-bg) !important;
  border-left-color:var(--crm-primary-tint) !important;
}
[data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"][aria-current="page"] {
  background:#FFE6CC !important;
  border-left-color:var(--crm-primary) !important;
  color:var(--crm-text) !important;
}
.crm-nav-disabled {
  min-height:42px;
  display:flex;
  align-items:center;
  border-radius:var(--crm-pill);
  padding:10px 14px 10px 16px;
  border-left:3px solid transparent;
  margin:2px 0;
  color:#8A6A52 !important;
  font-weight:650;
  opacity:.72;
  cursor:not-allowed;
  user-select:none;
}
.crm-nav-disabled:hover {
  background:#FFF8F0;
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
  border-radius:var(--crm-radius) !important;
  box-shadow:var(--crm-shadow-soft) !important;
}
[data-testid="stForm"] {
  padding:20px !important;
}
[data-testid="stMetric"] {
  padding:20px !important;
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
  font-family:"Noto Sans Thai",system-ui,sans-serif !important;
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
  border-radius:var(--crm-radius-sm) !important;
  box-shadow:none !important;
  font-size:15px !important;
  min-height:44px !important;
}
div[data-baseweb="input"] > div:focus-within,
div[data-baseweb="select"] > div:focus-within,
textarea:focus,
input:focus {
  border-color:var(--crm-primary) !important;
  box-shadow:var(--crm-shadow-focus) !important;
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
  box-shadow:var(--crm-shadow) !important;
  border-radius:18px !important;
}
div[role="option"] {
  color:var(--crm-text) !important;
}
div[role="option"]:hover {
  background:var(--crm-soft) !important;
}
.stButton > button,
button[kind="formSubmit"],
div.stDownloadButton > button {
  min-height:46px !important;
  border-radius:var(--crm-pill) !important;
  border:1px solid var(--crm-border) !important;
  background:var(--crm-surface) !important;
  color:var(--crm-text) !important;
  font-weight:750 !important;
  box-shadow:none !important;
  padding:10px 24px !important;
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
  background:var(--crm-primary-hover) !important;
  color:#FFFFFF !important;
  border-color:var(--crm-primary-hover) !important;
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
  border-radius:14px !important;
  background:#FFFDF9 !important;
}
[data-testid="stAlert"] {
  border-radius:14px !important;
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
  border-radius:var(--crm-pill);
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
  border-radius:18px;
  background:var(--crm-surface);
  box-shadow:var(--crm-shadow-soft);
}
.crm-table-header,
.crm-table-row {
  display:grid;
  gap:0;
  align-items:center;
}
.crm-table-header {
  min-height:50px;
  background:var(--crm-primary-pale);
  border-bottom:1px solid var(--crm-border);
  color:var(--crm-muted);
  font-size:13px;
  font-weight:800;
}
.crm-table-row {
  min-height:54px;
  border-bottom:1px solid #F7E8D8;
}
.crm-table-row:nth-child(even) {
  background:var(--crm-bg-lift);
}
.crm-table-row:hover {
  background:#FFF5EB;
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
  padding:11px 14px;
  background:var(--crm-primary-pale);
  border:1px solid var(--crm-border);
  border-radius:12px;
  color:var(--crm-text);
  font-size:15px;
  font-weight:800;
}
.crm-muted {
  color:var(--crm-muted) !important;
}
a.crm-link {
  color:var(--crm-primary) !important;
  font-weight:750;
  text-decoration:none;
}
a.crm-link:hover {
  color:var(--crm-primary-hover) !important;
  text-decoration:underline;
}
a.crm-outline-link {
  display:inline-flex;
  align-items:center;
  justify-content:center;
  min-height:34px;
  padding:6px 12px;
  border:1px solid var(--crm-primary);
  border-radius:var(--crm-pill);
  color:var(--crm-primary) !important;
  background:#FFFFFF;
  text-decoration:none !important;
  font-weight:800;
}
a.crm-outline-link:hover {
  background:var(--crm-soft);
  color:var(--crm-primary-hover) !important;
  border-color:var(--crm-primary-hover);
}
.crm-detail-card {
  background:var(--crm-surface);
  border:1px solid var(--crm-border);
  border-radius:22px;
  box-shadow:var(--crm-shadow);
  padding:22px;
  margin:14px 0 24px;
}
.crm-table-header-soft {
  background:var(--crm-primary-pale);
  border:1px solid var(--crm-border);
  border-radius:16px 16px 0 0;
  padding:12px 12px;
  color:var(--crm-text);
  font-weight:800;
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
