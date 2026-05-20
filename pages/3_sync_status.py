from datetime import datetime

import pandas as pd
import requests
import streamlit as st


st.set_page_config(page_title="DATA_RAW Sync", layout="wide")

SUPABASE_URL = st.secrets.get("CRM_SUPABASE_URL", st.secrets.get("SUPABASE_URL", ""))
ANON_KEY = st.secrets.get("CRM_SUPABASE_ANON_KEY", st.secrets.get("SUPABASE_ANON_KEY", ""))
SERVICE_KEY = st.secrets.get("CRM_SUPABASE_SERVICE_KEY", st.secrets.get("SUPABASE_SERVICE_KEY", ""))
ADMIN_PASSWORD = st.secrets.get("CRM_SYNC_ADMIN_PASSWORD", "")
SYNC_NAME = "data_raw"


st.markdown(
    """
<style>
.stApp { background:#FFF7ED; color:#111827; }
section[data-testid="stSidebar"] { background:#FFFFFF; border-right:1px solid #FED7AA; }
h1,h2,h3 { color:#EA580C !important; }
[data-testid="stMetric"] {
    background:white; border:1px solid #FED7AA; border-radius:14px; padding:16px;
}
.stButton > button {
    background:linear-gradient(90deg,#FF7A00 0%,#FB923C 100%);
    color:white; border:none; border-radius:12px; font-weight:700;
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


st.title("DATA_RAW Sync")

if not SUPABASE_URL or not ANON_KEY:
    st.error("ยังไม่ได้ตั้งค่า Supabase secrets")
    st.stop()

control_rows = api_get("sync_control", f"?sync_name=eq.{SYNC_NAME}&select=*")
control = control_rows[0] if control_rows else {}

status_cols = st.columns(4)
status_cols[0].metric("สถานะล่าสุด", control.get("last_status") or "-")
status_cols[1].metric("อ่านแถว", f"{int(control.get('last_rows_read') or 0):,}")
status_cols[2].metric("อัปเดตเข้า Supabase", f"{int(control.get('last_records_upserted') or 0):,}")
status_cols[3].metric("ไฟล์ล่าสุด", control.get("last_source") or "-")

st.caption(f"เริ่มล่าสุด: {fmt(control.get('last_started_at'))} | จบล่าสุด: {fmt(control.get('last_finished_at'))}")
st.info(control.get("last_message") or "ยังไม่มีข้อความ")

st.subheader("ควบคุมการรัน")
password = st.text_input("รหัสผู้ดูแล", type="password")
is_admin = bool(ADMIN_PASSWORD and password == ADMIN_PASSWORD)

if not ADMIN_PASSWORD:
    st.warning("ยังไม่ได้ตั้งค่า CRM_SYNC_ADMIN_PASSWORD ใน Streamlit Secrets จึงยังใช้ปุ่มควบคุมไม่ได้")
elif not is_admin:
    st.caption("ใส่รหัสผู้ดูแลเพื่อกดหยุดหรือรันต่อ")
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

st.subheader("ประวัติการรันล่าสุด")
runs = api_get(
    "sync_runs",
    f"?sync_name=eq.{SYNC_NAME}&select=id,status,trigger_type,started_at,finished_at,current_source,rows_read,records_upserted,skipped_rows,error_message&order=started_at.desc&limit=20",
)
if runs:
    df = pd.DataFrame(runs)
    df = df.rename(
        columns={
            "status": "สถานะ",
            "trigger_type": "ชนิด Trigger",
            "started_at": "เริ่ม",
            "finished_at": "จบ",
            "current_source": "ไฟล์ล่าสุด",
            "rows_read": "อ่านแถว",
            "records_upserted": "เข้า Supabase",
            "skipped_rows": "ข้าม",
            "error_message": "Error",
        }
    )
    st.dataframe(df, use_container_width=True, hide_index=True)
else:
    st.warning("ยังไม่มีประวัติการรัน")
