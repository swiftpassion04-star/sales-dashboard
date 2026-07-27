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
.stApp:has(.{_MARKER}) .dm-table-wrap {{
  width:100%;
  max-width:100%;
  overflow-x:auto;
  border:1px solid rgba(249,115,22,.18);
  border-radius:14px;
  box-shadow:0 12px 30px rgba(15,23,42,.06);
}}
.stApp:has(.{_MARKER}) .dm-table {{
  width:100%;
  border-collapse:separate;
  border-spacing:0;
  font-size:12px;
  line-height:1.35;
  color:#0F172A;
}}
.stApp:has(.{_MARKER}) .dm-table th,
.stApp:has(.{_MARKER}) .dm-table td {{
  padding:8px 10px;
  border-bottom:1px solid rgba(249,115,22,.12);
  border-right:1px solid rgba(249,115,22,.08);
  white-space:nowrap;
  text-align:center;
  font-variant-numeric:tabular-nums;
}}
.stApp:has(.{_MARKER}) .dm-table thead th {{
  font-weight:750;
  color:#7C2D12;
}}
.stApp:has(.{_MARKER}) .dm-table .dm-group-upsell {{
  background:#DBEAFE;
  color:#1E3A8A;
}}
.stApp:has(.{_MARKER}) .dm-table .dm-group-crm {{
  background:#EDE9FE;
  color:#5B21B6;
}}
.stApp:has(.{_MARKER}) .dm-table .dm-col-date {{
  text-align:left;
  font-weight:650;
}}
.stApp:has(.{_MARKER}) .dm-table .dm-cell-normal {{
  background:rgba(255,255,255,.9);
}}
.stApp:has(.{_MARKER}) .dm-table .dm-cell-yellow {{
  background:#FFF3CC;
  color:#8A5A00;
  font-weight:650;
}}
.stApp:has(.{_MARKER}) .dm-table .dm-cell-blue {{
  background:#D6EAFF;
  color:#0B5394;
  font-weight:650;
}}
.stApp:has(.{_MARKER}) .dm-table .dm-cell-green {{
  background:#E9F8EF;
  color:#166534;
  font-weight:650;
}}
.stApp:has(.{_MARKER}) .dm-table .dm-col-total {{
  font-weight:750;
  background:rgba(249,115,22,.06);
}}
.stApp:has(.{_MARKER}) .dm-table tr.dm-row-holiday td {{
  background:#FDE4E4 !important;
  color:#B91C1C !important;
}}
.stApp:has(.{_MARKER}) .dm-table tfoot td {{
  font-weight:750;
  background:#FFF0DF;
  border-top:2px solid rgba(249,115,22,.25);
}}
.stApp:has(.{_MARKER}) .dm-legend {{
  display:flex;
  flex-wrap:wrap;
  gap:14px;
  font-size:12px;
  color:#64748B;
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
