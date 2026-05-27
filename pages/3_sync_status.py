from datetime import datetime

import requests
import streamlit as st

from auth_utils import can_manage_system_page, can_view_system_page, require_login


st.set_page_config(page_title="DATA_RAW Sync", layout="wide")

SUPABASE_URL = st.secrets.get("CRM_SUPABASE_URL", st.secrets.get("SUPABASE_URL", ""))
ANON_KEY = st.secrets.get("CRM_SUPABASE_ANON_KEY", st.secrets.get("SUPABASE_ANON_KEY", ""))
SERVICE_KEY = st.secrets.get("CRM_SUPABASE_SERVICE_KEY", st.secrets.get("SUPABASE_SERVICE_KEY", ""))
SYNC_NAME = "data_raw"


st.markdown(
    """
<style>
:root {
    --bg: #fff8f0;
    --panel: #ffffff;
    --panel-soft: #fff1df;
    --line: #fed7aa;
    --line-strong: #fb923c;
    --text: #111827;
    --muted: #6b7280;
    --orange: #ea580c;
    --green: #15803d;
    --red: #b91c1c;
    --blue: #1d4ed8;
}
.stApp {
    background: var(--bg);
    color: var(--text);
}
section[data-testid="stSidebar"] {
    background: #ffffff;
    border-right: 1px solid var(--line);
}
section[data-testid="stSidebar"] * {
    color: var(--text) !important;
}
section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a[href$="/~/+/"],
section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a[href$="/"],
section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a[href*="/~/+/customers"],
section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a[href*="/customers"],
section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a[href*="/~/+/sync_status"],
section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a[href*="/sync_status"] {
    font-size: 0 !important;
}
section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a[href$="/~/+/"]::after,
section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a[href$="/"]::after {
    content: "ข้อมูลลูกค้า";
    font-size: 14px !important;
}
section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a[href*="/~/+/sync_status"]::after,
section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a[href*="/sync_status"]::after {
    content: "สถานะ Sync";
    font-size: 14px !important;
}
section[data-testid="stSidebar"] [aria-current="page"],
section[data-testid="stSidebar"] a:hover {
    background: #ffedd5 !important;
    color: #7c2d12 !important;
}
.block-container {
    max-width: 1280px;
    padding-top: 3rem;
}
h1 {
    color: var(--orange) !important;
    font-size: 2.4rem !important;
    margin-bottom: .25rem !important;
}
h2, h3 {
    color: #9a3412 !important;
}
p, label, span, div {
    color: var(--text);
}
[data-testid="stMetric"] {
    background: var(--panel);
    border: 1px solid var(--line);
    border-radius: 14px;
    padding: 18px 18px 14px;
    box-shadow: 0 8px 24px rgba(234, 88, 12, .08);
}
[data-testid="stMetricLabel"] p {
    color: #7c2d12 !important;
    font-weight: 700 !important;
}
[data-testid="stMetricValue"] {
    color: var(--orange) !important;
    font-weight: 800 !important;
}
.sync-card {
    background: var(--panel);
    border: 1px solid var(--line);
    border-radius: 14px;
    padding: 18px;
    box-shadow: 0 8px 24px rgba(234, 88, 12, .06);
}
.status-line {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
    color: var(--muted);
    margin: 6px 0 18px;
}
.pill {
    display: inline-flex;
    align-items: center;
    border-radius: 999px;
    padding: 5px 12px;
    font-weight: 800;
    font-size: 13px;
    border: 1px solid transparent;
}
.pill-success {
    background: #dcfce7;
    color: var(--green);
    border-color: #86efac;
}
.pill-running, .pill-idle {
    background: #dbeafe;
    color: var(--blue);
    border-color: #93c5fd;
}
.pill-failed, .pill-stopped, .pill-stop_requested {
    background: #fee2e2;
    color: var(--red);
    border-color: #fecaca;
}
.message {
    background: #eff6ff;
    color: #1e3a8a;
    border: 1px solid #bfdbfe;
    border-radius: 12px;
    padding: 14px 16px;
    font-weight: 650;
}
.control-note {
    color: var(--muted);
    font-size: 14px;
}
.run-table {
    width: 100%;
    border-collapse: separate;
    border-spacing: 0;
    overflow: hidden;
    border: 1px solid var(--line);
    border-radius: 14px;
    background: var(--panel);
}
.run-table th {
    background: #ffedd5;
    color: #7c2d12;
    text-align: left;
    font-weight: 800;
    padding: 11px 12px;
    border-bottom: 1px solid var(--line-strong);
    white-space: nowrap;
}
.run-table td {
    color: var(--text);
    padding: 11px 12px;
    border-bottom: 1px solid #f3f4f6;
    vertical-align: top;
}
.run-table tr:nth-child(even) td {
    background: #fffaf5;
}
.run-table tr:last-child td {
    border-bottom: 0;
}
.num {
    text-align: right;
    font-variant-numeric: tabular-nums;
}
.error-text {
    color: var(--red);
    max-width: 360px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
.stTextInput input {
    background: white !important;
    border: 1px solid var(--line-strong) !important;
    color: var(--text) !important;
    border-radius: 12px !important;
}
.stButton > button {
    background: linear-gradient(90deg, #ff7a00 0%, #fb923c 100%);
    color: white !important;
    border: none;
    border-radius: 12px;
    padding: 10px 18px;
    font-weight: 800;
}
.stButton > button:hover {
    filter: brightness(.98);
    border: none;
}
</style>
""",
    unsafe_allow_html=True,
)


def headers(use_service: bool = False) -> dict[str, str]:
    key = SERVICE_KEY if use_service and SERVICE_KEY else ANON_KEY
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def api_get(path: str, params: str) -> list[dict]:
    response = requests.get(f"{SUPABASE_URL}/rest/v1/{path}{params}", headers=headers(), timeout=30)
    if response.status_code >= 300:
        st.error(response.text)
        return []
    return response.json()


def api_patch(path: str, params: str, payload: dict) -> None:
    response = requests.patch(
        f"{SUPABASE_URL}/rest/v1/{path}{params}",
        headers=headers(use_service=True),
        json=payload,
        timeout=30,
    )
    if response.status_code >= 300:
        st.error(response.text)
    else:
        st.success("บันทึกคำสั่งแล้ว")
        st.cache_data.clear()


def fmt(value: object) -> str:
    if not value:
        return "-"
    text = str(value)
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return text


def status_pill(status: object) -> str:
    value = str(status or "-")
    css = value.lower().replace(" ", "_")
    return f'<span class="pill pill-{css}">{value}</span>'


def short_id(value: object) -> str:
    text = str(value or "")
    return text[:8] if text else "-"


def as_int(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def render_runs_table(runs: list[dict]) -> None:
    if not runs:
        st.warning("ยังไม่มีประวัติการรัน")
        return

    rows = []
    for run in runs:
        rows.append(
            "<tr>"
            f"<td>{short_id(run.get('id'))}</td>"
            f"<td>{status_pill(run.get('status'))}</td>"
            f"<td>{run.get('trigger_type') or '-'}</td>"
            f"<td>{fmt(run.get('started_at'))}</td>"
            f"<td>{fmt(run.get('finished_at'))}</td>"
            f"<td>{run.get('current_source') or '-'}</td>"
            f"<td class='num'>{as_int(run.get('rows_read')):,}</td>"
            f"<td class='num'>{as_int(run.get('records_upserted')):,}</td>"
            f"<td class='num'>{as_int(run.get('skipped_rows')):,}</td>"
            f"<td class='error-text'>{run.get('error_message') or '-'}</td>"
            "</tr>"
        )

    table = (
        "<table class='run-table'>"
        "<thead><tr>"
        "<th>Run</th><th>สถานะ</th><th>Trigger</th><th>เริ่ม</th><th>จบ</th>"
        "<th>ไฟล์ล่าสุด</th><th class='num'>อ่านแถว</th><th class='num'>เข้า Supabase</th>"
        "<th class='num'>ข้าม</th><th>Error</th>"
        "</tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )
    st.markdown(table, unsafe_allow_html=True)


st.title("DATA_RAW Sync")
st.markdown("<div class='status-line'>ระบบซิงก์ประวัติ DATA_RAW 2565-2569 เข้า Supabase สำหรับหน้าข้อมูลลูกค้า</div>", unsafe_allow_html=True)

if not SUPABASE_URL or not ANON_KEY:
    st.error("ยังไม่ได้ตั้งค่า Supabase secrets")
    st.stop()

auth_user = require_login()
if not can_view_system_page(auth_user):
    st.warning("หน้านี้เป็นระบบหลังบ้าน เฉพาะ CEO/EDITOR เท่านั้นที่เข้าได้")
    st.stop()
can_manage_sync = can_manage_system_page(auth_user)

control_rows = api_get("sync_control", f"?sync_name=eq.{SYNC_NAME}&select=*")
control = control_rows[0] if control_rows else {}

status_cols = st.columns(4)
status_cols[0].metric("สถานะล่าสุด", control.get("last_status") or "-")
status_cols[1].metric("อ่านแถว", f"{as_int(control.get('last_rows_read')):,}")
status_cols[2].metric("อัปเดตเข้า Supabase", f"{as_int(control.get('last_records_upserted')):,}")
status_cols[3].metric("ไฟล์ล่าสุด", control.get("last_source") or "-")

st.markdown(
    f"""
    <div class="status-line">
        {status_pill(control.get("last_status"))}
        <span>เริ่มล่าสุด: {fmt(control.get("last_started_at"))}</span>
        <span>จบล่าสุด: {fmt(control.get("last_finished_at"))}</span>
    </div>
    <div class="message">{control.get("last_message") or "ยังไม่มีข้อความ"}</div>
    """,
    unsafe_allow_html=True,
)

st.markdown("### ควบคุมการรัน")
with st.container():
    st.markdown("<div class='sync-card'>", unsafe_allow_html=True)
    if not can_manage_sync:
        st.markdown("<div class='control-note'>read-only: เฉพาะ EDITOR เท่านั้นที่หยุดหรือเปิด sync ได้</div>", unsafe_allow_html=True)
    else:
        col_stop, col_resume, col_refresh = st.columns(3)
        if col_stop.button("หยุดรัน DATA_RAW", use_container_width=True):
            api_patch(
                "sync_control",
                f"?sync_name=eq.{SYNC_NAME}",
                {
                    "is_paused": True,
                    "stop_requested": True,
                    "last_status": "stop_requested",
                    "last_message": "รอ worker หยุดเมื่อถึง checkpoint ถัดไป",
                },
            )
            st.rerun()
        if col_resume.button("รันต่อรอบถัดไป", use_container_width=True):
            api_patch(
                "sync_control",
                f"?sync_name=eq.{SYNC_NAME}",
                {
                    "is_paused": False,
                    "stop_requested": False,
                    "last_status": "idle",
                    "last_message": "พร้อมให้ trigger รอบถัดไปทำงาน",
                },
            )
            st.rerun()
        if col_refresh.button("Refresh สถานะ", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

st.markdown("### ประวัติการรันล่าสุด")
runs = api_get(
    "sync_runs",
    f"?sync_name=eq.{SYNC_NAME}&select=id,status,trigger_type,started_at,finished_at,current_source,rows_read,records_upserted,skipped_rows,error_message&order=started_at.desc&limit=20",
)
render_runs_table(runs)
