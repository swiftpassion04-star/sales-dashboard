import streamlit as st


def inject_crm_design_system() -> None:
    st.markdown(
        """
<span class="crm-page-shell crm-team-sales-page-marker" aria-hidden="true"></span>
<style>
:root {
  --crm-bg-main:#FFF7ED;
  --crm-bg-soft:#FFFBF5;
  --crm-surface-glass:rgba(255,255,255,.58);
  --crm-surface-glass-strong:rgba(255,255,255,.72);
  --crm-surface-card:#FFF8EF;
  --crm-primary:#F97316;
  --crm-primary-hover:#EA580C;
  --crm-primary-soft:rgba(249,115,22,.12);
  --crm-primary-border:rgba(249,115,22,.28);
  --crm-text-main:#0F172A;
  --crm-text-muted:#64748B;
  --crm-text-soft:#94A3B8;
  --crm-border-soft:rgba(251,146,60,.20);
  --crm-border-glass:rgba(255,255,255,.65);
  --crm-warning-bg:rgba(254,249,195,.78);
  --crm-warning-border:rgba(234,179,8,.28);
  --crm-radius-sm:12px;
  --crm-radius-md:16px;
  --crm-radius-lg:22px;
  --crm-radius-xl:28px;
  --crm-radius-pill:999px;
  --crm-shadow-glass:0 18px 45px rgba(15,23,42,.08),0 2px 8px rgba(249,115,22,.05);
  --crm-shadow-neu:9px 9px 20px rgba(217,186,150,.35),-9px -9px 20px rgba(255,255,255,.85);
  --crm-shadow-neu-soft:6px 6px 14px rgba(217,186,150,.25),-6px -6px 14px rgba(255,255,255,.78);
  --crm-shadow-inset:inset 4px 4px 8px rgba(217,186,150,.22),inset -4px -4px 8px rgba(255,255,255,.85);
  --crm-space-xs:6px;
  --crm-space-sm:10px;
  --crm-space-md:16px;
  --crm-space-lg:24px;
  --crm-space-xl:32px;
}
.crm-page-shell.crm-team-sales-page-marker {
  display:none;
}
.crm-page-title {
  color:var(--crm-text-main);
  font-size:30px;
  font-weight:800;
  letter-spacing:0;
  line-height:1.2;
}
.crm-section-title {
  color:var(--crm-text-main);
  font-size:20px;
  font-weight:800;
  line-height:1.35;
}
.crm-muted {
  color:var(--crm-text-muted);
  font-size:14px;
}
.crm-glass-panel {
  background:linear-gradient(135deg,rgba(255,255,255,.72),rgba(255,247,237,.46));
  border:1px solid var(--crm-border-glass);
  border-radius:var(--crm-radius-xl);
  box-shadow:var(--crm-shadow-glass);
  backdrop-filter:blur(18px);
  -webkit-backdrop-filter:blur(18px);
}
.crm-glass-panel-compact {
  background:var(--crm-surface-glass);
  border:1px solid var(--crm-border-soft);
  border-radius:var(--crm-radius-lg);
  box-shadow:var(--crm-shadow-glass);
  backdrop-filter:blur(14px);
  -webkit-backdrop-filter:blur(14px);
}
.crm-neu-card {
  background:var(--crm-surface-card);
  border:1px solid rgba(255,255,255,.72);
  border-radius:var(--crm-radius-lg);
  box-shadow:var(--crm-shadow-neu);
}
.crm-neu-card-soft {
  background:var(--crm-bg-soft);
  border:1px solid rgba(255,255,255,.72);
  border-radius:var(--crm-radius-md);
  box-shadow:var(--crm-shadow-neu-soft);
}
.crm-kpi-label {
  color:var(--crm-text-muted);
  font-size:13px;
  font-weight:700;
  margin-bottom:8px;
}
.crm-kpi-value {
  color:var(--crm-text-main);
  font-size:34px;
  font-weight:850;
  letter-spacing:0;
  line-height:1.1;
}
.crm-table-glass {
  background:rgba(255,255,255,.46);
  border:1px solid var(--crm-border-soft);
  border-radius:var(--crm-radius-lg);
  box-shadow:0 10px 28px rgba(15,23,42,.06);
  overflow:hidden;
}
.crm-warning-glass {
  background:var(--crm-warning-bg);
  border:1px solid var(--crm-warning-border);
  border-radius:var(--crm-radius-lg);
  box-shadow:0 8px 22px rgba(234,179,8,.08);
  color:#713F12;
  padding:16px 18px;
}
.stApp:has(.crm-team-sales-page-marker) {
  background:linear-gradient(160deg,var(--crm-bg-main) 0%,var(--crm-bg-soft) 52%,#FFFFFF 100%) !important;
}
.stApp:has(.crm-team-sales-page-marker) .block-container {
  max-width:1480px;
}
.stApp:has(.crm-team-sales-page-marker) .crm-shell-header,
.stApp:has(.crm-team-sales-page-marker) .st-key-team_sales_filter_panel,
.stApp:has(.crm-team-sales-page-marker) .st-key-team_sales_summary_panel,
.stApp:has(.crm-team-sales-page-marker) .st-key-team_sales_top_products,
.stApp:has(.crm-team-sales-page-marker) .st-key-team_sales_assignment_panel {
  background:linear-gradient(135deg,rgba(255,255,255,.72),rgba(255,247,237,.46));
  border:1px solid var(--crm-border-glass);
  border-radius:var(--crm-radius-xl);
  box-shadow:var(--crm-shadow-glass);
  backdrop-filter:blur(18px);
  -webkit-backdrop-filter:blur(18px);
}
.stApp:has(.crm-team-sales-page-marker) .crm-shell-header {
  padding:var(--crm-space-lg);
  margin-bottom:var(--crm-space-lg);
}
.stApp:has(.crm-team-sales-page-marker) .crm-title {
  color:var(--crm-text-main) !important;
  font-size:30px !important;
  letter-spacing:0 !important;
}
.stApp:has(.crm-team-sales-page-marker) .crm-subtitle,
.stApp:has(.crm-team-sales-page-marker) [data-testid="stCaptionContainer"] {
  color:var(--crm-text-muted) !important;
}
.stApp:has(.crm-team-sales-page-marker) .st-key-team_sales_filter_panel,
.stApp:has(.crm-team-sales-page-marker) .st-key-team_sales_summary_panel,
.stApp:has(.crm-team-sales-page-marker) .st-key-team_sales_top_products,
.stApp:has(.crm-team-sales-page-marker) .st-key-team_sales_assignment_panel {
  padding:var(--crm-space-lg);
}
.stApp:has(.crm-team-sales-page-marker) .st-key-team_sales_filter_panel {
  margin-bottom:var(--crm-space-lg);
}
.stApp:has(.crm-team-sales-page-marker) .st-key-team_sales_summary_panel,
.stApp:has(.crm-team-sales-page-marker) .st-key-team_sales_top_products {
  min-height:100%;
}
.stApp:has(.crm-team-sales-page-marker) .st-key-team_sales_team_card_crm_team,
.stApp:has(.crm-team-sales-page-marker) .st-key-team_sales_team_card_upsell_team,
.stApp:has(.crm-team-sales-page-marker) .st-key-team_sales_team_card_unknown {
  background:var(--crm-surface-glass-strong);
  border:1px solid var(--crm-border-soft);
  border-radius:var(--crm-radius-lg);
  box-shadow:var(--crm-shadow-glass);
  padding:var(--crm-space-md);
  margin-bottom:var(--crm-space-md);
  backdrop-filter:blur(14px);
  -webkit-backdrop-filter:blur(14px);
}
.stApp:has(.crm-team-sales-page-marker) .st-key-team_sales_summary_panel [data-testid="stMetric"] {
  background:var(--crm-surface-card) !important;
  border:1px solid rgba(255,255,255,.72) !important;
  border-radius:var(--crm-radius-lg) !important;
  box-shadow:var(--crm-shadow-neu-soft) !important;
  min-height:126px;
  padding:18px !important;
}
.stApp:has(.crm-team-sales-page-marker) .st-key-team_sales_summary_panel [data-testid="stMetricLabel"] * {
  color:var(--crm-text-muted) !important;
  font-size:13px !important;
  font-weight:700 !important;
}
.stApp:has(.crm-team-sales-page-marker) .st-key-team_sales_summary_panel [data-testid="stMetricValue"] {
  color:var(--crm-text-main) !important;
  font-size:30px !important;
  font-weight:850 !important;
  letter-spacing:0 !important;
  line-height:1.1 !important;
}
.stApp:has(.crm-team-sales-page-marker) .st-key-team_sales_top_products [data-testid="stDataFrame"] {
  background:rgba(255,255,255,.46) !important;
  border:1px solid var(--crm-border-soft) !important;
  border-radius:var(--crm-radius-lg) !important;
  box-shadow:0 10px 28px rgba(15,23,42,.06) !important;
  overflow:hidden;
}
.stApp:has(.crm-team-sales-page-marker) .st-key-team_sales_summary_panel [data-testid="stAlert"] {
  background:var(--crm-warning-bg) !important;
  border:1px solid var(--crm-warning-border) !important;
  border-radius:var(--crm-radius-lg) !important;
  box-shadow:0 8px 22px rgba(234,179,8,.08) !important;
}
.stApp:has(.crm-team-sales-page-marker) .st-key-team_sales_assignment_panel [data-testid="stForm"] {
  background:var(--crm-bg-soft) !important;
  border:1px solid rgba(255,255,255,.72) !important;
  border-radius:var(--crm-radius-md) !important;
  box-shadow:var(--crm-shadow-neu-soft) !important;
  padding:var(--crm-space-md) !important;
}
.stApp:has(.crm-team-sales-page-marker) .st-key-team_sales_filter_panel div[data-baseweb="select"] > div,
.stApp:has(.crm-team-sales-page-marker) .st-key-team_sales_filter_panel div[data-baseweb="input"] > div,
.stApp:has(.crm-team-sales-page-marker) .st-key-team_sales_assignment_panel div[data-baseweb="select"] > div {
  background:rgba(255,255,255,.78) !important;
  border:1px solid var(--crm-primary-border) !important;
  border-radius:var(--crm-radius-sm) !important;
  box-shadow:var(--crm-shadow-inset) !important;
}
.stApp:has(.crm-team-sales-page-marker) .st-key-team_sales_assignment_panel button[kind="formSubmit"] {
  background:var(--crm-primary) !important;
  border-color:var(--crm-primary) !important;
  border-radius:var(--crm-radius-pill) !important;
  color:#FFFFFF !important;
}
.stApp:has(.crm-team-sales-page-marker) .st-key-team_sales_assignment_panel button[kind="formSubmit"]:hover {
  background:var(--crm-primary-hover) !important;
  border-color:var(--crm-primary-hover) !important;
}
@media (max-width:900px) {
  .stApp:has(.crm-team-sales-page-marker) .crm-shell-header,
  .stApp:has(.crm-team-sales-page-marker) .st-key-team_sales_filter_panel,
  .stApp:has(.crm-team-sales-page-marker) .st-key-team_sales_summary_panel,
  .stApp:has(.crm-team-sales-page-marker) .st-key-team_sales_top_products,
  .stApp:has(.crm-team-sales-page-marker) .st-key-team_sales_assignment_panel {
    border-radius:var(--crm-radius-lg);
    padding:var(--crm-space-md);
  }
  .stApp:has(.crm-team-sales-page-marker) .st-key-team_sales_summary_panel [data-testid="stMetricValue"] {
    font-size:26px !important;
  }
}
</style>
""",
        unsafe_allow_html=True,
    )
