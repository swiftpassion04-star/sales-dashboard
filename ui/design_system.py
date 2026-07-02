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
  --crm-surface-glass-strong:rgba(255,255,255,.76);
  --crm-surface-card:#FFF9F2;
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
  --crm-gradient-page:linear-gradient(155deg,#FFF7ED 0%,#FFFBF5 48%,#FFFFFF 100%);
  --crm-gradient-glass:linear-gradient(135deg,rgba(255,255,255,.82),rgba(255,247,237,.58));
  --crm-gradient-crm-team:linear-gradient(138deg,#FFF7ED 0%,#FED7AA 58%,#FDBA74 100%);
  --crm-gradient-upsell-team:linear-gradient(138deg,#FFF4E6 0%,#FEC89A 54%,#FB923C 100%);
  --crm-gradient-kpi:linear-gradient(145deg,#FFFFFF 0%,#FFF9F2 55%,#FFEDD5 100%);
  --crm-gradient-kpi-upsell:linear-gradient(145deg,#FFFFFF 0%,#FFF6EA 52%,#FDDDBB 100%);
  --crm-table-header:#FFF0DF;
  --crm-table-row-odd:rgba(255,255,255,.94);
  --crm-table-row-even:rgba(255,247,237,.82);
  --crm-table-row-hover:#FFE8CF;
  --crm-table-grid:rgba(249,115,22,.12);
  --crm-radius-sm:12px;
  --crm-radius-md:16px;
  --crm-radius-lg:22px;
  --crm-radius-xl:28px;
  --crm-radius-pill:999px;
  --crm-shadow-glass:0 22px 54px rgba(15,23,42,.09),0 3px 12px rgba(249,115,22,.07);
  --crm-shadow-neu:10px 10px 24px rgba(213,177,136,.28),-10px -10px 24px rgba(255,255,255,.92),inset 1px 1px 0 rgba(255,255,255,.9);
  --crm-shadow-neu-soft:7px 7px 17px rgba(213,177,136,.23),-7px -7px 17px rgba(255,255,255,.88),inset 1px 1px 0 rgba(255,255,255,.82);
  --crm-shadow-neu-hover:12px 12px 28px rgba(213,177,136,.28),-10px -10px 24px rgba(255,255,255,.94),inset 1px 1px 0 rgba(255,255,255,.9);
  --crm-shadow-inset:inset 4px 4px 9px rgba(213,177,136,.20),inset -4px -4px 9px rgba(255,255,255,.9);
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
  background:var(--crm-gradient-glass);
  border:1px solid var(--crm-border-glass);
  border-radius:var(--crm-radius-xl);
  box-shadow:var(--crm-shadow-glass);
  backdrop-filter:blur(22px) saturate(118%);
  -webkit-backdrop-filter:blur(22px) saturate(118%);
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
  background:var(--crm-gradient-kpi);
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
  background:var(--crm-gradient-page) !important;
}
.stApp:has(.crm-team-sales-page-marker) .block-container {
  max-width:1480px;
}
.stApp:has(.crm-team-sales-page-marker) .crm-shell-header,
.stApp:has(.crm-team-sales-page-marker) .st-key-team_sales_filter_panel,
.stApp:has(.crm-team-sales-page-marker) .st-key-team_sales_summary_panel,
.stApp:has(.crm-team-sales-page-marker) .st-key-team_sales_top_products,
.stApp:has(.crm-team-sales-page-marker) .st-key-team_sales_assignment_panel {
  background:var(--crm-gradient-glass);
  border:1px solid var(--crm-border-glass);
  border-radius:var(--crm-radius-xl);
  box-shadow:var(--crm-shadow-glass);
  backdrop-filter:blur(22px) saturate(118%);
  -webkit-backdrop-filter:blur(22px) saturate(118%);
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
  background:var(--crm-gradient-crm-team);
  border:1px solid var(--crm-border-soft);
  border-radius:var(--crm-radius-lg);
  box-shadow:var(--crm-shadow-neu);
  padding:var(--crm-space-lg);
  margin-bottom:var(--crm-space-md);
  backdrop-filter:blur(14px);
  -webkit-backdrop-filter:blur(14px);
}
.stApp:has(.crm-team-sales-page-marker) .st-key-team_sales_team_card_crm_team {
  background:var(--crm-gradient-crm-team);
  border-color:rgba(234,88,12,.32);
  box-shadow:0 16px 35px rgba(234,88,12,.16),-8px -8px 20px rgba(255,255,255,.78),inset 1px 1px 0 rgba(255,255,255,.72);
}
.stApp:has(.crm-team-sales-page-marker) .st-key-team_sales_team_card_upsell_team {
  background:var(--crm-gradient-upsell-team);
  border-color:rgba(194,65,12,.34);
  box-shadow:0 18px 38px rgba(194,65,12,.18),-8px -8px 20px rgba(255,255,255,.74),inset 1px 1px 0 rgba(255,255,255,.68);
}
.stApp:has(.crm-team-sales-page-marker) .st-key-team_sales_team_card_crm_team h3,
.stApp:has(.crm-team-sales-page-marker) .st-key-team_sales_team_card_upsell_team h3 {
  color:#431407;
  font-size:19px;
  font-weight:800;
  line-height:1.35;
  margin-bottom:var(--crm-space-sm);
}
.stApp:has(.crm-team-sales-page-marker) .st-key-team_sales_summary_panel [data-testid="stMetric"] {
  background:var(--crm-gradient-kpi) !important;
  border:1px solid rgba(255,255,255,.72) !important;
  border-radius:var(--crm-radius-lg) !important;
  box-shadow:var(--crm-shadow-neu-soft) !important;
  min-height:128px;
  padding:20px !important;
  transition:transform .18s ease,box-shadow .18s ease;
}
.stApp:has(.crm-team-sales-page-marker) .st-key-team_sales_team_card_upsell_team [data-testid="stMetric"] {
  background:var(--crm-gradient-kpi-upsell) !important;
}
.stApp:has(.crm-team-sales-page-marker) .st-key-team_sales_summary_panel [data-testid="stMetric"]:hover {
  box-shadow:var(--crm-shadow-neu-hover) !important;
  transform:translateY(-1px);
}
.stApp:has(.crm-team-sales-page-marker) .st-key-team_sales_summary_panel [data-testid="stMetricLabel"] * {
  color:var(--crm-text-muted) !important;
  font-size:13px !important;
  font-weight:700 !important;
}
.stApp:has(.crm-team-sales-page-marker) .st-key-team_sales_summary_panel [data-testid="stMetricValue"] {
  color:var(--crm-text-main) !important;
  font-size:31px !important;
  font-weight:850 !important;
  letter-spacing:0 !important;
  line-height:1.1 !important;
}
.stApp:has(.crm-team-sales-page-marker) .crm-top-products-table-wrap {
  width:100%;
  max-width:100%;
  overflow:hidden;
  border:1px solid var(--crm-table-grid);
  border-radius:var(--crm-radius-md);
  box-shadow:0 12px 30px rgba(15,23,42,.065);
  background:rgba(255,255,255,.76);
}
.stApp:has(.crm-team-sales-page-marker) .crm-top-products-table {
  width:100%;
  max-width:100%;
  table-layout:fixed;
  border-collapse:separate;
  border-spacing:0;
  color:var(--crm-text-main);
  font-size:12px;
  line-height:1.35;
}
.stApp:has(.crm-team-sales-page-marker) .crm-top-products-table .crm-col-rank {
  width:11%;
}
.stApp:has(.crm-team-sales-page-marker) .crm-top-products-table .crm-col-sku {
  width:18%;
}
.stApp:has(.crm-team-sales-page-marker) .crm-top-products-table .crm-col-product {
  width:37%;
}
.stApp:has(.crm-team-sales-page-marker) .crm-top-products-table .crm-col-quantity {
  width:19%;
}
.stApp:has(.crm-team-sales-page-marker) .crm-top-products-table .crm-col-orders {
  width:15%;
}
.stApp:has(.crm-team-sales-page-marker) .crm-top-products-table th {
  background:var(--crm-table-header);
  color:#7C2D12;
  font-size:11px;
  font-weight:750;
  padding:11px 6px;
  border-bottom:1px solid rgba(249,115,22,.2);
  white-space:nowrap;
}
.stApp:has(.crm-team-sales-page-marker) .crm-top-products-table td {
  padding:11px 6px;
  border-bottom:1px solid var(--crm-table-grid);
  vertical-align:middle;
  transition:background-color .15s ease;
}
.stApp:has(.crm-team-sales-page-marker) .crm-top-products-table tbody tr:nth-child(odd) td {
  background:var(--crm-table-row-odd);
}
.stApp:has(.crm-team-sales-page-marker) .crm-top-products-table tbody tr:nth-child(even) td {
  background:var(--crm-table-row-even);
}
.stApp:has(.crm-team-sales-page-marker) .crm-top-products-table tbody tr:hover td {
  background:var(--crm-table-row-hover);
}
.stApp:has(.crm-team-sales-page-marker) .crm-top-products-table tbody tr:last-child td {
  border-bottom:0;
}
.stApp:has(.crm-team-sales-page-marker) .crm-top-products-table .crm-table-number,
.stApp:has(.crm-team-sales-page-marker) .crm-top-products-table .crm-table-sku {
  text-align:center;
  font-variant-numeric:tabular-nums;
}
.stApp:has(.crm-team-sales-page-marker) .crm-top-products-table .crm-table-number {
  white-space:nowrap;
}
.stApp:has(.crm-team-sales-page-marker) .crm-top-products-table .crm-table-sku {
  overflow-wrap:anywhere;
  word-break:break-word;
}
.stApp:has(.crm-team-sales-page-marker) .crm-top-products-table .crm-table-product {
  text-align:left;
  overflow-wrap:anywhere;
  word-break:break-word;
}
.stApp:has(.crm-team-sales-page-marker) .st-key-team_sales_summary_panel [data-testid="stAlert"] {
  background:var(--crm-warning-bg) !important;
  border:1px solid var(--crm-warning-border) !important;
  border-radius:var(--crm-radius-lg) !important;
  box-shadow:0 8px 22px rgba(234,179,8,.08) !important;
  color:#713F12 !important;
}
.stApp:has(.crm-team-sales-page-marker) .st-key-team_sales_assignment_panel [data-testid="stForm"] {
  background:linear-gradient(145deg,#FFFFFF 0%,#FFF9F2 100%) !important;
  border:1px solid rgba(255,255,255,.72) !important;
  border-radius:var(--crm-radius-md) !important;
  box-shadow:var(--crm-shadow-neu-soft) !important;
  padding:var(--crm-space-md) !important;
  margin-bottom:var(--crm-space-sm);
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
