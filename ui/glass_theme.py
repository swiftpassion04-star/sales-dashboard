"""Opt-in "Liquid Glass" page styling (white / orange only).

Follows the same isolation technique as ui/daily_matrix_design.py and
ui/design_system.py: a hidden marker span plus `.stApp:has(marker)` on every
rule, so a page opts in by calling inject_liquid_glass() and no other page is
affected. Unlike design_system.py this takes the marker as an argument, so it
is reusable across pages instead of being hardcoded to one.

Colour tokens (--crm-glass-*) come from crm_theme.inject_saas_theme(), which
render_sidebar_nav() already injects on every page -- this module only adds
the glass *surfaces*, never new colours.

Layering rules kept deliberately shallow:
  * The page header is the single strong-orange focal element.
  * Everything else is light glass (~.82 white) so text stays readable.
  * Blur never nests more than 2 deep in one viewport: the header is a
    sibling of the content, and the only nested pair is
    card > form/metric. Tables are NOT blurred -- on the data-heavy pages
    (followup, products, daily_matrix) blurring a long scrolling table is
    the main source of scroll jank.

Deliberately NOT implemented: 3D perspective/rotate tilt. A CSS transform on
an ancestor makes it the containing block for position:fixed descendants,
which mispositions every Streamlit dropdown, date picker and dialog.
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
/* ---- focal element: strong orange glass header ---- */
.stApp:has(.{marker}) .crm-shell-header {{
  background:var(--crm-glass-hero);
  border:1px solid var(--crm-glass-hero-border);
  border-radius:var(--crm-radius-glass);
  box-shadow:var(--crm-glass-hero-shadow);
  backdrop-filter:var(--crm-glass-blur);
  -webkit-backdrop-filter:var(--crm-glass-blur);
  padding:24px 28px;
  margin-bottom:24px;
}}
.stApp:has(.{marker}) .crm-shell-header .crm-title,
.stApp:has(.{marker}) .crm-shell-header h1 {{
  color:var(--crm-on-orange) !important;
}}
.stApp:has(.{marker}) .crm-shell-header .crm-eyebrow,
.stApp:has(.{marker}) .crm-shell-header .crm-subtitle {{
  color:var(--crm-on-orange-soft) !important;
}}
/* A primary button must never sit as deep orange on deep orange -- inside
   the hero it drops to light glass with dark text instead. */
.stApp:has(.{marker}) .crm-shell-header .stButton > button[kind="primary"] {{
  background:rgba(255,255,255,.92) !important;
  color:var(--crm-primary-press) !important;
  border-color:rgba(255,255,255,.75) !important;
  box-shadow:0 6px 18px rgba(120,70,20,.22) !important;
}}
/* ---- light glass surfaces ---- */
.stApp:has(.{marker}) .crm-card,
.stApp:has(.{marker}) .crm-detail-card,
.stApp:has(.{marker}) .crm-table,
.stApp:has(.{marker}) .crm-table-header-soft,
.stApp:has(.{marker}) .crm-inline-detail-title {{
  background:var(--crm-glass-bg-solid);
  border:1px solid var(--crm-glass-border);
  border-radius:var(--crm-radius-glass);
  box-shadow:var(--crm-glass-shadow);
}}
/* Tables get the glass surface but intentionally no backdrop-filter: these
   pages scroll long lists and per-row blur is what makes that feel heavy. */
.stApp:has(.{marker}) .crm-table {{
  overflow:hidden;
}}
.stApp:has(.{marker}) [data-testid="stMetric"] {{
  transition:transform .3s var(--crm-ease-glass),box-shadow .3s var(--crm-ease-glass);
}}
.stApp:has(.{marker}) [data-testid="stMetric"]:hover {{
  transform:translateY(-2px);
  box-shadow:var(--crm-glass-shadow-hover) !important;
  border-color:var(--crm-glass-border-warm) !important;
}}
/* ---- buttons ---- */
.stApp:has(.{marker}) .stButton > button {{
  min-height:56px !important;
  padding:10px 24px !important;
  border-radius:var(--crm-pill) !important;
  background:var(--crm-glass-bg-solid) !important;
  color:var(--crm-text) !important;
}}
.stApp:has(.{marker}) .stButton > button:hover {{
  background:var(--crm-primary-pale) !important;
  border-color:var(--crm-glass-border-warm) !important;
}}
.stApp:has(.{marker}) .stButton > button[kind="primary"],
.stApp:has(.{marker}) button[kind="formSubmit"] {{
  background:var(--crm-glass-active) !important;
  color:var(--crm-on-orange) !important;
  box-shadow:var(--crm-glass-active-glow) !important;
}}
/* ---- fallback: no backdrop-filter support ---- */
@supports not ((backdrop-filter: blur(1px)) or (-webkit-backdrop-filter: blur(1px))) {{
  .stApp:has(.{marker}) .crm-shell-header {{
    background:var(--crm-orange-glass-solid);
  }}
  .stApp:has(.{marker}) .crm-card,
  .stApp:has(.{marker}) .crm-detail-card,
  .stApp:has(.{marker}) .crm-table,
  .stApp:has(.{marker}) .stButton > button {{
    background:rgba(255,255,255,.94) !important;
  }}
}}
/* ---- mobile: no blur, no transforms, higher opacity ---- */
@media (max-width: 768px) {{
  .stApp:has(.{marker}) .crm-shell-header {{
    backdrop-filter:none;
    -webkit-backdrop-filter:none;
    background:var(--crm-orange-glass-solid);
    border-radius:var(--crm-radius);
    padding:16px 18px;
  }}
  .stApp:has(.{marker}) .crm-card,
  .stApp:has(.{marker}) .crm-detail-card,
  .stApp:has(.{marker}) .crm-table {{
    backdrop-filter:none !important;
    -webkit-backdrop-filter:none !important;
    background:rgba(255,255,255,.94) !important;
    border-radius:var(--crm-radius);
  }}
  .stApp:has(.{marker}) [data-testid="stMetric"]:hover,
  .stApp:has(.{marker}) .stButton > button:hover {{
    transform:none !important;
  }}
  /* Repeats crm_theme's global mobile rules because this page-scoped
     selector outranks them -- media queries add no specificity. */
  .stApp:has(.{marker}) .stButton > button {{
    min-height:48px !important;
    background:rgba(255,255,255,.94) !important;
    backdrop-filter:none !important;
    -webkit-backdrop-filter:none !important;
  }}
  .stApp:has(.{marker}) .stButton > button[kind="primary"],
  .stApp:has(.{marker}) button[kind="formSubmit"] {{
    background:var(--crm-glass-active) !important;
    color:var(--crm-on-orange) !important;
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
