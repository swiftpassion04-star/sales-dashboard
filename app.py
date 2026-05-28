import streamlit as st
import pandas as pd
import requests
import plotly.graph_objects as go
import plotly.express as px
from urllib.parse import quote

from auth_utils import can_view_system_page, require_login

st.set_page_config(
    page_title="Sales Dashboard Pro Ultra",
    page_icon="📊",
    layout="wide"
)

auth_user = require_login()
if not can_view_system_page(auth_user):
    st.warning("หน้านี้เป็น dashboard หลังบ้าน เฉพาะ CEO/EDITOR เท่านั้นที่เข้าได้")
    st.stop()

SUPABASE_URL = st.secrets.get("SUPABASE_URL", st.secrets.get("CRM_SUPABASE_URL", ""))
SUPABASE_KEY = st.secrets.get("SUPABASE_ANON_KEY", st.secrets.get("CRM_SUPABASE_ANON_KEY", ""))

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Prefer": "count=exact"
}

# ── PALETTE ───────────────────────────────────────────────────
ORANGE      = "#FF7A00"
ORANGE_LIGHT= "#FB923C"
ORANGE_PALE = "#FED7AA"
DARK        = "#1C1917"
TEXT        = "#292524"
TEXT2       = "#57534E"
WHITE       = "#FFFFFF"
BG          = "#FFFBF7"
CARD        = "#FFFFFF"

# Bar chart color sequence (warm → cool contrast)
CHART_COLORS = [
    "#FF7A00","#F97316","#FB923C",
    "#FDBA74","#FCD34D","#86EFAC",
    "#6EE7B7","#5EEAD4","#67E8F9","#93C5FD"
]

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Kanit:wght@400;600;700;900&family=IBM+Plex+Sans+Thai:wght@300;400;500;600&display=swap');

* {{ font-family: 'IBM Plex Sans Thai', sans-serif !important; }}
h1,h2,h3,h4 {{ font-family: 'Kanit', sans-serif !important; font-weight: 700 !important; }}

html, body, .stApp {{
    background-color: {BG} !important;
    color: {TEXT} !important;
}}

/* Sidebar */
section[data-testid="stSidebar"] {{
    background: linear-gradient(160deg, #FFF7ED 0%, #FFFBF7 100%) !important;
    border-right: 2px solid {ORANGE_PALE};
}}
section[data-testid="stSidebar"] * {{ color: {TEXT} !important; }}
section[data-testid="stSidebar"] label {{
    font-weight: 600 !important;
    font-size: 12px !important;
    letter-spacing: .5px !important;
    text-transform: uppercase !important;
    color: {TEXT2} !important;
}}

/* Metric cards */
[data-testid="stMetric"] {{
    background: {CARD} !important;
    border: 1.5px solid {ORANGE_PALE} !important;
    border-radius: 20px !important;
    padding: 20px 22px !important;
    box-shadow: 0 4px 20px rgba(255,122,0,.08) !important;
}}
[data-testid="stMetricLabel"] {{
    color: {TEXT2} !important;
    font-size: 11px !important;
    font-weight: 700 !important;
    letter-spacing: .6px !important;
    text-transform: uppercase !important;
}}
[data-testid="stMetricValue"] {{
    color: {DARK} !important;
    font-family: 'Kanit', sans-serif !important;
    font-size: 26px !important;
    font-weight: 900 !important;
}}

/* Buttons */
.stButton > button {{
    background: linear-gradient(90deg, {ORANGE} 0%, {ORANGE_LIGHT} 100%) !important;
    color: {WHITE} !important;
    border: none !important;
    border-radius: 12px !important;
    font-weight: 700 !important;
    font-size: 13px !important;
    padding: 10px 18px !important;
    transition: all .2s ease !important;
}}
.stButton > button:hover {{
    transform: translateY(-2px) !important;
    box-shadow: 0 8px 20px rgba(255,122,0,.3) !important;
}}

/* Selectbox */
div[data-baseweb="select"] > div {{
    background: {WHITE} !important;
    border: 1.5px solid {ORANGE_PALE} !important;
    border-radius: 12px !important;
    color: {TEXT} !important;
}}
div[data-baseweb="select"] * {{ color: {TEXT} !important; }}

/* Divider */
hr {{ border-color: {ORANGE_PALE} !important; opacity: .6; }}

/* Hide Streamlit branding */
#MainMenu, footer, header {{ visibility: hidden; }}

/* Section label */
.section-label {{
    font-family: 'Kanit', sans-serif;
    font-size: 15px;
    font-weight: 700;
    color: {TEXT2};
    letter-spacing: .5px;
    text-transform: uppercase;
    margin-bottom: 4px;
}}

/* Glass card */
.glass-card {{
    background: {CARD};
    border: 1.5px solid {ORANGE_PALE};
    border-radius: 24px;
    padding: 24px 26px;
    box-shadow: 0 6px 24px rgba(17,24,39,.05);
    margin-bottom: 18px;
}}

/* Hero */
.hero {{
    background: linear-gradient(135deg, {ORANGE} 0%, #FB923C 60%, #FDBA74 100%);
    border-radius: 28px;
    padding: 30px 36px;
    margin-bottom: 24px;
    box-shadow: 0 16px 40px rgba(255,122,0,.22);
    color: white;
}}
.hero-title {{
    font-family: 'Kanit', sans-serif;
    font-size: 36px;
    font-weight: 900;
    margin: 0;
    line-height: 1.1;
}}
.hero-sub {{
    font-size: 14px;
    opacity: .9;
    margin-top: 6px;
}}
</style>
""", unsafe_allow_html=True)


# ── PLOTLY THEME ──────────────────────────────────────────────
def fig_layout(fig, title="", height=320):
    fig.update_layout(
        title=dict(text=title, font=dict(size=15, color=TEXT, family="Kanit"), x=0),
        height=height,
        margin=dict(l=0, r=0, t=36, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="IBM Plex Sans Thai", color=TEXT, size=12),
        xaxis=dict(
            showgrid=False,
            tickfont=dict(color=TEXT2, size=11),
            linecolor=ORANGE_PALE,
            zeroline=False
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor="#F3EDE6",
            tickfont=dict(color=TEXT2, size=11),
            linecolor=ORANGE_PALE,
            zeroline=False
        ),
        showlegend=False,
    )
    return fig

def bar_chart(labels, values, title="", horizontal=False, color_seq=None):
    colors = color_seq or [CHART_COLORS[i % len(CHART_COLORS)] for i in range(len(labels))]

    if horizontal:
        fig = go.Figure(go.Bar(
            x=values, y=labels,
            orientation="h",
            marker=dict(color=colors, line=dict(width=0)),
            text=[f"{v:,.0f}" for v in values],
            textposition="outside",
            textfont=dict(color=TEXT, size=11, family="Kanit"),
            hovertemplate="%{y}: %{x:,.0f}<extra></extra>"
        ))
        fig.update_layout(
            yaxis=dict(autorange="reversed", categoryorder="total ascending",
                       tickfont=dict(color=TEXT, size=11)),
            xaxis=dict(showgrid=True, gridcolor="#F3EDE6", tickfont=dict(color=TEXT2, size=10)),
        )
    else:
        fig = go.Figure(go.Bar(
            x=labels, y=values,
            marker=dict(
                color=values,
                colorscale=[[0,"#FDBA74"],[0.5,ORANGE_LIGHT],[1,ORANGE]],
                showscale=False,
                line=dict(width=0)
            ),
            text=[f"{v:,.0f}" for v in values],
            textposition="outside",
            textfont=dict(color=TEXT, size=11, family="Kanit"),
            hovertemplate="%{x}: %{y:,.0f}<extra></extra>"
        ))
        fig.update_xaxes(tickangle=-30)

    fig_layout(fig, title)
    return fig

def line_chart(df_in, x_col, y_col, title=""):
    df_sorted = df_in.sort_values(x_col)
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df_sorted[x_col], y=df_sorted[y_col],
        mode="lines+markers",
        line=dict(color=ORANGE, width=3),
        marker=dict(color=ORANGE, size=7, line=dict(color=WHITE, width=2)),
        fill="tozeroy",
        fillcolor="rgba(255,122,0,0.08)",
        hovertemplate="%{x}: %{y:,.0f}<extra></extra>"
    ))
    fig_layout(fig, title)
    return fig


# ── API ───────────────────────────────────────────────────────
def api_get_all(path, params, page_size=1000, max_rows=300000):
    all_rows, offset = [], 0
    while offset < max_rows:
        url = f"{SUPABASE_URL}/rest/v1/{path}?{'&'.join(params + [f'limit={page_size}', f'offset={offset}'])}"
        res = requests.get(url, headers=HEADERS)
        if res.status_code not in [200, 206]:
            st.error(res.text); return []
        rows = res.json()
        if not rows: break
        all_rows.extend(rows)
        if len(rows) < page_size: break
        offset += page_size
    return all_rows


def build_filter_params(year, month, province, channel, sales_staff, source_sheet):
    params = []
    if year         != "ทั้งหมด": params.append(f"year=eq.{quote(str(year))}")
    if month        != "ทั้งหมด": params.append(f"month=eq.{quote(str(month))}")
    if province     != "ทั้งหมด": params.append(f"province=eq.{quote(str(province))}")
    if channel      != "ทั้งหมด": params.append(f"channel=eq.{quote(str(channel))}")
    if sales_staff  != "ทั้งหมด": params.append(f"sales_staff=eq.{quote(str(sales_staff))}")
    if source_sheet != "ทั้งหมด": params.append(f"source_sheet=eq.{quote(str(source_sheet))}")
    return params


def sort_months(values):
    normal, others = [], []
    for v in values:
        try: normal.append(int(v))
        except: others.append(v)
    return [str(v) for v in sorted(normal)] + sorted(others)


@st.cache_data(ttl=300)
def load_summary_all():
    rows = api_get_all("dashboard_summary", [
        "select=year,month,province,channel,sales_staff,source_sheet,total_sales,total_orders,total_customers",
    ])
    df = pd.DataFrame(rows)
    if df.empty: return df
    for col in ["total_sales","total_orders","total_customers"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    return df


@st.cache_data(ttl=180)
def load_summary_filtered(year, month, province, channel, sales_staff, source_sheet):
    filters = build_filter_params(year, month, province, channel, sales_staff, source_sheet)
    rows = api_get_all("dashboard_summary", [
        "select=year,month,province,channel,sales_staff,source_sheet,total_sales,total_orders,total_customers"
    ] + filters)
    df = pd.DataFrame(rows)
    if df.empty: return df
    for col in ["total_sales","total_orders","total_customers"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    return df


# ── LOAD ALL (for filter options) ────────────────────────────
all_df = load_summary_all()
if all_df.empty:
    st.warning("ไม่พบข้อมูลใน dashboard_summary")
    st.stop()

years         = sorted(all_df["year"].dropna().astype(str).unique().tolist())
months        = sort_months(all_df["month"].dropna().astype(str).unique().tolist())
provinces     = sorted(all_df["province"].dropna().astype(str).unique().tolist())
channels      = sorted(all_df["channel"].dropna().astype(str).unique().tolist())
sales_staffs  = sorted(all_df["sales_staff"].dropna().astype(str).unique().tolist())
source_sheets = sorted(all_df["source_sheet"].dropna().astype(str).unique().tolist())

# ── SIDEBAR ───────────────────────────────────────────────────
st.sidebar.markdown("## 🔎 ตัวกรอง")
year         = st.sidebar.selectbox("ปี",            ["ทั้งหมด"] + years)
month        = st.sidebar.selectbox("เดือน",         ["ทั้งหมด"] + months)
source_sheet = st.sidebar.selectbox("แหล่งข้อมูล",   ["ทั้งหมด"] + source_sheets)
province     = st.sidebar.selectbox("จังหวัด",       ["ทั้งหมด"] + provinces)
channel      = st.sidebar.selectbox("ช่องทาง",       ["ทั้งหมด"] + channels)
sales_staff  = st.sidebar.selectbox("พนักงานขาย",    ["ทั้งหมด"] + sales_staffs)

if st.sidebar.button("🔄 ล้าง Cache / Refresh"):
    st.cache_data.clear()
    st.rerun()

# ── HERO ──────────────────────────────────────────────────────
st.markdown("""
<div class="hero">
    <div class="hero-title">📊 Sales Dashboard Pro</div>
    <div class="hero-sub">ภาพรวมยอดขาย — โหลดเร็ว ไม่ดึงข้อมูลดิบทั้งหมด</div>
</div>
""", unsafe_allow_html=True)

# ── LOAD FILTERED ─────────────────────────────────────────────
with st.spinner("กำลังโหลดข้อมูล..."):
    df = load_summary_filtered(year, month, province, channel, sales_staff, source_sheet)

if df.empty:
    st.warning("ไม่พบข้อมูลตามตัวกรอง")
    st.stop()

# ── KPI ──────────────────────────────────────────────────────
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("💰 ยอดขายรวม",     f"{df['total_sales'].sum():,.0f}")
k2.metric("📦 ออเดอร์",        f"{df['total_orders'].sum():,.0f}")
k3.metric("👤 ลูกค้า",         f"{df['total_customers'].sum():,.0f}")
k4.metric("📍 จังหวัด",        f"{df['province'].nunique():,}")
k5.metric("👨‍💼 พนักงานขาย",   f"{df['sales_staff'].nunique():,}")

st.divider()

# ── ROW 1: ยอดขายตามเวลา + จังหวัด ──────────────────────────
c1, c2 = st.columns(2)

with c1:
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    if month == "ทั้งหมด":
        yearly = df.groupby("year")["total_sales"].sum().reset_index()
        yearly["year"] = yearly["year"].astype(str)
        yearly = yearly.sort_values("year")
        fig = line_chart(yearly, "year", "total_sales", "📅 ยอดขายรายปี")
    else:
        monthly = df.groupby(["year","month"], as_index=False)["total_sales"].sum()
        monthly["month_sort"] = pd.to_numeric(monthly["month"], errors="coerce").fillna(99)
        monthly = monthly.sort_values(["year","month_sort"])
        monthly["period"] = monthly["year"].astype(str) + "/" + monthly["month"].astype(str)
        fig = line_chart(monthly, "period", "total_sales",
                         f"📅 ยอดขายรายเดือน {'ปี ' + year if year != 'ทั้งหมด' else ''}")
        fig.update_xaxes(tickangle=-30)
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    st.markdown('</div>', unsafe_allow_html=True)

with c2:
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    prov = (df.groupby("province")["total_sales"].sum()
              .sort_values(ascending=True).tail(10).reset_index())
    fig = bar_chart(prov["province"].tolist(), prov["total_sales"].tolist(),
                    "🏆 ยอดขายตามจังหวัด Top 10", horizontal=True)
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    st.markdown('</div>', unsafe_allow_html=True)

# ── ROW 2: พนักงาน + ช่องทาง ────────────────────────────────
c3, c4 = st.columns(2)

with c3:
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    staff = (df.groupby("sales_staff")["total_sales"].sum()
               .sort_values(ascending=True).tail(10).reset_index())
    fig = bar_chart(staff["sales_staff"].tolist(), staff["total_sales"].tolist(),
                    "👨‍💼 ยอดขายตามพนักงาน Top 10", horizontal=True)
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    st.markdown('</div>', unsafe_allow_html=True)

with c4:
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    ch = (df.groupby("channel")["total_sales"].sum()
            .sort_values(ascending=False).reset_index())
    # Donut chart สำหรับช่องทาง
    fig = go.Figure(go.Pie(
        labels=ch["channel"],
        values=ch["total_sales"],
        hole=.55,
        marker=dict(colors=CHART_COLORS[:len(ch)],
                    line=dict(color=WHITE, width=2)),
        textfont=dict(size=12, color=TEXT, family="IBM Plex Sans Thai"),
        hovertemplate="%{label}: %{value:,.0f} (%{percent})<extra></extra>",
        textinfo="label+percent"
    ))
    fig.update_layout(
        title=dict(text="🛒 ยอดขายตามช่องทาง",
                   font=dict(size=15, color=TEXT, family="Kanit"), x=0),
        height=320,
        margin=dict(l=0, r=0, t=36, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family="IBM Plex Sans Thai", color=TEXT),
        legend=dict(font=dict(color=TEXT, size=11), bgcolor="rgba(0,0,0,0)")
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    st.markdown('</div>', unsafe_allow_html=True)

# ── ROW 3: Source Sheet ───────────────────────────────────────
if "source_sheet" in df.columns and df["source_sheet"].nunique() > 1:
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    src = (df.groupby("source_sheet")["total_orders"].sum()
             .sort_values(ascending=False).reset_index())
    fig = bar_chart(src["source_sheet"].tolist(), src["total_orders"].tolist(),
                    "📂 ออเดอร์ตามแหล่งข้อมูล")
    fig_layout(fig, height=260)
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    st.markdown('</div>', unsafe_allow_html=True)

st.caption(f"โหลดจากตารางสรุป: {len(df):,} แถว | ไม่โหลดรายการข้อมูลดิบจาก orders")
