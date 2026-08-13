"""Page-local CSS for pages/daily_matrix.py.

Follows the same isolation technique as ui/design_system.py (its own hidden
marker span + `.stApp:has(marker)` scoping) rather than reusing that file
directly -- design_system.py's selectors are hardcoded to team_sales's own
marker class, so it isn't a general-purpose stylesheet.
"""

import streamlit as st

_MARKER = "crm-daily-matrix-page-marker"


def inject_daily_matrix_design() -> None:
    st.markdown(
        f"""
<span class="crm-page-shell {_MARKER}" aria-hidden="true"></span>
<style>
.crm-page-shell.{_MARKER} {{
  display:none;
}}
/* Header matches the strong-orange focal element used by the pages that
   inject ui/glass_theme.py. That module is deliberately NOT injected on
   this page: it would add a second scoped stylesheet and, more
   importantly, put a blur layer around a very large scrolling table.
   Only the header is blurred here; .dm-table-wrap below stays unblurred. */
.stApp:has(.{_MARKER}) .crm-shell-header {{
  background:var(--crm-glass-hero);
  border:1px solid var(--crm-glass-hero-border);
  border-radius:var(--crm-radius-glass);
  box-shadow:var(--crm-glass-hero-shadow);
  backdrop-filter:var(--crm-glass-blur);
  -webkit-backdrop-filter:var(--crm-glass-blur);
  padding:24px 28px;
  margin-bottom:24px;
}}
.stApp:has(.{_MARKER}) .crm-shell-header .crm-title {{
  color:var(--crm-on-orange) !important;
}}
.stApp:has(.{_MARKER}) .crm-shell-header .crm-eyebrow,
.stApp:has(.{_MARKER}) .crm-shell-header .crm-subtitle {{
  color:var(--crm-on-orange-soft) !important;
}}
@supports not ((backdrop-filter: blur(1px)) or (-webkit-backdrop-filter: blur(1px))) {{
  .stApp:has(.{_MARKER}) .crm-shell-header {{
    background:var(--crm-orange-glass-solid);
  }}
}}
@media (max-width: 768px) {{
  .stApp:has(.{_MARKER}) .crm-shell-header {{
    backdrop-filter:none;
    -webkit-backdrop-filter:none;
    background:var(--crm-orange-glass-solid);
    border-radius:var(--crm-radius);
    padding:16px 18px;
  }}
}}
.stApp:has(.{_MARKER}) .dm-table-wrap {{
  width:100%;
  max-width:100%;
  overflow-x:auto;
  border:1px solid rgba(255,122,26,.18);
  border-radius:14px;
  box-shadow:0 12px 30px rgba(120,70,20,.10);
}}
.stApp:has(.{_MARKER}) .dm-table {{
  width:100%;
  border-collapse:separate;
  border-spacing:0;
  font-size:12px;
  line-height:1.35;
  color:#1F160F;
}}
.stApp:has(.{_MARKER}) .dm-table th,
.stApp:has(.{_MARKER}) .dm-table td {{
  padding:6px 7px;
  border-bottom:1px solid rgba(255,122,26,.12);
  border-right:1px solid rgba(255,122,26,.08);
  white-space:nowrap;
  text-align:center;
  font-variant-numeric:tabular-nums;
}}
.stApp:has(.{_MARKER}) .dm-table thead th {{
  font-weight:750;
  color:#8A3D05;
  font-size:11px;
}}
.stApp:has(.{_MARKER}) .dm-table .dm-col-staff {{
  max-width:72px;
  overflow:hidden;
  text-overflow:ellipsis;
}}
.stApp:has(.{_MARKER}) .dm-table .dm-group-upsell {{
  background:#FFE0BF;
  color:#8A3D05;
}}
.stApp:has(.{_MARKER}) .dm-table .dm-group-crm {{
  background:#FFEEDC;
  color:#9A5A22;
}}
.stApp:has(.{_MARKER}) .dm-table .dm-group-unassigned {{
  background:#F6EEE8;
  color:#7B5C44;
}}
.stApp:has(.{_MARKER}) .dm-table .dm-col-date {{
  text-align:left;
  font-weight:650;
}}
.stApp:has(.{_MARKER}) .dm-table .dm-cell-normal {{
  background:rgba(255,255,255,.9);
}}
/* Threshold tiers. These deliberately break the page's orange-only palette:
   the tiers encode DIFFERENT MEANINGS (upsell stretch target vs "team hit
   its goal"), so they need distinct hues, not shades of one colour --
   intensity alone was not readable as three separate states.
     yellow = UPSELL per-person over 3,000
     blue   = UPSELL per-person over 4,500
     green  = target reached (CRM per-person over 11,000, UPSELL team total
              over 11,000, CRM team total over 40,000)
   Class names come straight from classify_*_cell_tone() in
   crm_data/daily_matrix.py, whose return values are asserted in
   tests/test_daily_matrix.py -- renaming them would be a logic change. */
.stApp:has(.{_MARKER}) .dm-table .dm-cell-yellow {{
  background:#FFEBC7;
  color:#8A5A00;
  font-weight:650;
}}
.stApp:has(.{_MARKER}) .dm-table .dm-cell-blue {{
  background:#D6EAFF;
  color:#0B4C87;
  font-weight:750;
}}
.stApp:has(.{_MARKER}) .dm-table .dm-cell-green {{
  background:#DFF5E7;
  color:#14663B;
  font-weight:650;
}}
.stApp:has(.{_MARKER}) .dm-table .dm-col-total {{
  font-weight:750;
  background:rgba(255,122,26,.06);
}}
/* A total cell carries BOTH .dm-col-total and its tone class. These two
   rules have equal specificity, so without this the later .dm-col-total
   background silently painted over the tone and the "team hit its goal"
   highlight never appeared. Combining both classes raises specificity so
   the tone wins regardless of source order. */
.stApp:has(.{_MARKER}) .dm-table .dm-col-total.dm-cell-green {{
  background:#DFF5E7;
  color:#14663B;
}}
.stApp:has(.{_MARKER}) .dm-table .dm-col-total.dm-cell-blue {{
  background:#D6EAFF;
  color:#0B4C87;
}}
.stApp:has(.{_MARKER}) .dm-table tr.dm-row-holiday td {{
  background:#FBDCD2 !important;
  color:#A32D0C !important;
}}
.stApp:has(.{_MARKER}) .dm-table td.dm-cell-personal-off {{
  background:#FBDCD2 !important;
  color:#A32D0C !important;
  font-weight:650;
  cursor:help;
}}
.stApp:has(.{_MARKER}) .dm-table tfoot td {{
  font-weight:750;
  background:#FFF0DF;
  border-top:2px solid rgba(255,122,26,.25);
}}
.stApp:has(.{_MARKER}) .dm-legend {{
  display:flex;
  flex-wrap:wrap;
  gap:14px;
  font-size:12px;
  color:#6B5545;
  margin:6px 0 12px 0;
}}
.stApp:has(.{_MARKER}) .dm-legend-swatch {{
  display:inline-block;
  width:11px;
  height:11px;
  border-radius:3px;
  margin-right:5px;
  vertical-align:middle;
}}
</style>
""",
        unsafe_allow_html=True,
    )
