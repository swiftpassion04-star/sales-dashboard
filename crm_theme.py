import html

import streamlit as st


def inject_saas_theme() -> None:
    st.markdown(
        """
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+Thai:wght@400;500;600;700;800&display=swap');
:root {
  --crm-bg:#FAFAFA;
  --crm-card:#FFFFFF;
  --crm-border:#E5E7EB;
  --crm-text:#111827;
  --crm-muted:#6B7280;
  --crm-primary:#2563EB;
  --crm-success:#16A34A;
  --crm-warning:#F59E0B;
  --crm-danger:#DC2626;
  --crm-soft:#F3F4F6;
  --crm-radius:8px;
  --crm-shadow:0 1px 2px rgba(17,24,39,.05);
}
html, body, [class*="css"], .stApp {
  font-family:"Noto Sans Thai", "Prompt", system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif !important;
}
.stApp {
  background:var(--crm-bg) !important;
  color:var(--crm-text) !important;
}
.block-container {
  max-width:1420px;
  padding:24px 32px 56px;
}
[data-testid="stSidebar"] {
  background:#FFFFFF !important;
  border-right:1px solid var(--crm-border) !important;
}
[data-testid="stSidebar"] * { color:var(--crm-text) !important; }
[data-testid="stSidebarNav"] { display:none !important; }
.crm-shell-header {
  display:flex;
  justify-content:space-between;
  gap:16px;
  align-items:flex-start;
  margin:4px 0 20px;
}
.crm-eyebrow {
  color:var(--crm-muted);
  font-size:13px;
  font-weight:700;
  letter-spacing:.02em;
  margin-bottom:4px;
}
.crm-title {
  color:var(--crm-text);
  font-size:30px;
  line-height:1.2;
  font-weight:800;
  letter-spacing:0;
  margin:0;
}
.crm-subtitle {
  color:var(--crm-muted);
  font-size:14px;
  margin-top:6px;
}
.crm-card {
  background:var(--crm-card);
  border:1px solid var(--crm-border);
  border-radius:var(--crm-radius);
  box-shadow:var(--crm-shadow);
  padding:18px;
}
.crm-section-title {
  color:var(--crm-text);
  font-size:18px;
  font-weight:800;
  margin:18px 0 10px;
}
.crm-nav-brand {
  padding:8px 8px 18px;
  margin-bottom:10px;
  border-bottom:1px solid var(--crm-border);
}
.crm-nav-brand-title {
  font-size:17px;
  font-weight:800;
  color:var(--crm-text);
}
.crm-nav-brand-subtitle {
  font-size:12px;
  color:var(--crm-muted) !important;
  margin-top:2px;
}
.crm-nav-title {
  margin:18px 8px 6px;
  color:var(--crm-muted) !important;
  font-size:12px;
  font-weight:800;
  text-transform:uppercase;
  letter-spacing:.04em;
}
.crm-nav-spacer { height:6px; }
[data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"] {
  min-height:36px !important;
  border-radius:8px !important;
  padding:7px 10px !important;
  font-weight:650 !important;
}
[data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"]:hover,
[data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"][aria-current="page"] {
  background:#EFF6FF !important;
  color:var(--crm-primary) !important;
}
h1, h2, h3, p, label, span, div[data-testid="stMarkdownContainer"] {
  color:var(--crm-text);
  letter-spacing:0;
}
[data-testid="stCaptionContainer"] { color:var(--crm-muted) !important; }
[data-testid="stForm"],
[data-testid="stExpander"],
[data-testid="stDataFrame"],
[data-testid="stMetric"],
[data-testid="stFileUploader"] {
  background:#FFFFFF !important;
  border:1px solid var(--crm-border) !important;
  border-radius:8px !important;
  box-shadow:var(--crm-shadow) !important;
}
[data-testid="stMetric"] {
  padding:16px 18px !important;
}
[data-testid="stMetric"] label,
[data-testid="stMetric"] label *,
[data-testid="stMetricLabel"],
[data-testid="stMetricLabel"] * {
  color:var(--crm-muted) !important;
  font-weight:700 !important;
}
[data-testid="stMetricValue"] {
  color:var(--crm-text) !important;
  font-weight:800 !important;
}
div[data-baseweb="input"] > div,
div[data-baseweb="select"] > div,
div[data-baseweb="base-input"],
div[data-baseweb="textarea"],
textarea,
input {
  background:#FFFFFF !important;
  color:var(--crm-text) !important;
  -webkit-text-fill-color:var(--crm-text) !important;
  border:1px solid var(--crm-border) !important;
  border-radius:8px !important;
  box-shadow:none !important;
}
div[data-baseweb="input"] > div:focus-within,
div[data-baseweb="select"] > div:focus-within,
textarea:focus,
input:focus {
  border-color:var(--crm-primary) !important;
  box-shadow:0 0 0 3px rgba(37,99,235,.12) !important;
  outline:none !important;
}
input::placeholder, textarea::placeholder {
  color:#9CA3AF !important;
}
div[data-baseweb="select"] svg,
div[data-baseweb="input"] svg {
  color:var(--crm-muted) !important;
  fill:var(--crm-muted) !important;
}
.stButton > button,
button[kind="formSubmit"],
div.stDownloadButton > button {
  min-height:38px !important;
  border-radius:8px !important;
  border:1px solid var(--crm-border) !important;
  background:#FFFFFF !important;
  color:var(--crm-text) !important;
  font-weight:700 !important;
  box-shadow:none !important;
}
button[kind="formSubmit"],
.stButton > button[kind="primary"] {
  background:var(--crm-primary) !important;
  color:#FFFFFF !important;
  border-color:var(--crm-primary) !important;
}
[data-testid="stExpander"] details,
[data-testid="stExpander"] details summary,
[data-testid="stExpander"] details summary *,
[data-testid="stFileUploader"] section,
[data-testid="stFileUploader"] section * {
  background:#FFFFFF !important;
  color:var(--crm-text) !important;
}
[data-testid="stAlert"] {
  border-radius:8px !important;
  color:var(--crm-text) !important;
}
[data-testid="stAlert"] * { color:var(--crm-text) !important; }
.crm-badge {
  display:inline-flex;
  align-items:center;
  min-height:24px;
  padding:2px 9px;
  border-radius:999px;
  background:var(--crm-soft);
  color:var(--crm-text);
  font-weight:700;
  font-size:12px;
}
.crm-badge-blue { background:#DBEAFE; color:#1D4ED8; }
.crm-badge-green { background:#DCFCE7; color:#166534; }
.crm-badge-yellow { background:#FEF3C7; color:#92400E; }
.crm-badge-orange { background:#FFEDD5; color:#C2410C; }
.crm-badge-red { background:#FEE2E2; color:#B91C1C; }
.crm-badge-gray { background:#F3F4F6; color:#4B5563; }
.crm-table {
  width:100%;
  border-collapse:separate;
  border-spacing:0;
  overflow:hidden;
  border:1px solid var(--crm-border);
  border-radius:8px;
  background:#FFFFFF;
}
.crm-table-header,
.crm-table-row {
  display:grid;
  gap:0;
  align-items:center;
}
.crm-table-header {
  min-height:44px;
  background:#F9FAFB;
  border-bottom:1px solid var(--crm-border);
  color:var(--crm-muted);
  font-size:13px;
  font-weight:800;
}
.crm-table-row {
  min-height:52px;
  border-bottom:1px solid #F3F4F6;
}
.crm-table-row:nth-child(even) { background:#FCFCFD; }
.crm-table-row:last-child { border-bottom:0; }
.crm-table-cell {
  padding:10px 12px;
  color:var(--crm-text);
  font-size:14px;
  overflow-wrap:anywhere;
}
.crm-inline-detail-title {
  margin:10px 0 8px;
  padding:10px 14px;
  background:#EFF6FF;
  border:1px solid #BFDBFE;
  border-radius:8px;
  color:#1D4ED8;
  font-size:14px;
  font-weight:800;
}
.crm-muted { color:var(--crm-muted) !important; }
a.crm-link { color:var(--crm-primary) !important; font-weight:700; text-decoration:none; }
a.crm-link:hover { text-decoration:underline; }
@media (max-width: 900px) {
  .block-container { padding:18px 16px 48px; }
  .crm-shell-header { display:block; }
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
