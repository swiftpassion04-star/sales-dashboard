"""Opt-in "Liquid Glass" page styling (white / orange only).

Follows the same isolation technique as ui/daily_matrix_design.py and
ui/design_system.py: a hidden marker span plus `.stApp:has(marker)` on every
rule, so a page opts in by calling inject_liquid_glass() and no other page is
affected. Unlike design_system.py this takes the marker as an argument, so it
is reusable across pages instead of being hardcoded to one.

Colour tokens (--crm-glass-*) come from crm_theme.inject_saas_theme(), which
render_sidebar_nav() already injects on every page -- this module only adds
the glass *surfaces*, never new colours.

Deliberately NOT implemented: 3D perspective/rotate tilt. A CSS transform on
an ancestor makes it the containing block for position:fixed descendants,
which mispositions every Streamlit dropdown, date picker and dialog. The
depth here comes from layered shadows instead.
"""

import streamlit as st


def inject_liquid_glass(page_marker: str) -> None:
    """Inject glass styling scoped to `page_marker`.

    page_marker must be a bare CSS class name unique to the calling page,
    e.g. "crm-dashboard-glass".
    """
    marker = str(page_marker or "").strip()
    if not marker:
        raise ValueError("page_marker is required")

    st.markdown(
        f"""
<span class="crm-page-shell {marker}" aria-hidden="true"></span>
<style>
.crm-page-shell.{marker} {{
  display:none;
}}
.stApp:has(.{marker}) .crm-shell-header {{
  background:var(--crm-glass-bg);
  border:1px solid var(--crm-glass-border);
  border-radius:var(--crm-radius-glass);
  box-shadow:var(--crm-glass-shadow);
  backdrop-filter:var(--crm-glass-blur);
  -webkit-backdrop-filter:var(--crm-glass-blur);
  padding:24px 28px;
  margin-bottom:24px;
}}
.stApp:has(.{marker}) .crm-card,
.stApp:has(.{marker}) .crm-detail-card {{
  background:var(--crm-glass-bg-solid);
  border:1px solid var(--crm-glass-border);
  border-radius:var(--crm-radius-glass);
  box-shadow:var(--crm-glass-shadow);
}}
.stApp:has(.{marker}) [data-testid="stMetric"] {{
  transition:transform .3s var(--crm-ease-glass),box-shadow .3s var(--crm-ease-glass);
}}
.stApp:has(.{marker}) [data-testid="stMetric"]:hover {{
  transform:translateY(-2px);
  box-shadow:var(--crm-glass-shadow-hover) !important;
  border-color:var(--crm-glass-border-warm) !important;
}}
.stApp:has(.{marker}) .stButton > button {{
  min-height:56px !important;
  padding:10px 24px !important;
  border-radius:var(--crm-pill) !important;
  background:var(--crm-glass-bg-strong) !important;
}}
.stApp:has(.{marker}) .stButton > button[kind="primary"] {{
  background:var(--crm-glass-active) !important;
  color:#FFF8F0 !important;
  box-shadow:var(--crm-glass-active-glow) !important;
}}
/* Fallback: no backdrop-filter support -> opaque surface, never
   unreadable near-transparent text. */
@supports not ((backdrop-filter: blur(1px)) or (-webkit-backdrop-filter: blur(1px))) {{
  .stApp:has(.{marker}) .crm-shell-header {{
    background:rgba(255,255,255,.88);
  }}
}}
@media (max-width: 768px) {{
  .stApp:has(.{marker}) .crm-shell-header {{
    backdrop-filter:none;
    -webkit-backdrop-filter:none;
    background:rgba(255,255,255,.90);
    border-radius:var(--crm-radius);
    padding:16px 18px;
  }}
  .stApp:has(.{marker}) [data-testid="stMetric"]:hover,
  .stApp:has(.{marker}) .stButton > button:hover {{
    transform:none !important;
  }}
  /* These repeat the global mobile rules from crm_theme because the
     page-scoped selector here outranks them -- media queries add no
     specificity, so without this the button would keep its blur on
     phones. */
  .stApp:has(.{marker}) .stButton > button {{
    min-height:48px !important;
    background:rgba(255,255,255,.90) !important;
    backdrop-filter:none !important;
    -webkit-backdrop-filter:none !important;
  }}
  .stApp:has(.{marker}) .stButton > button[kind="primary"] {{
    background:var(--crm-glass-active) !important;
  }}
}}
@media (prefers-reduced-motion: reduce) {{
  .stApp:has(.{marker}) [data-testid="stMetric"],
  .stApp:has(.{marker}) .stButton > button {{
    transition:none !important;
  }}
  .stApp:has(.{marker}) [data-testid="stMetric"]:hover,
  .stApp:has(.{marker}) .stButton > button:hover {{
    transform:none !important;
  }}
}}
</style>
""",
        unsafe_allow_html=True,
    )
