import os
import base64
import json
import time
from urllib.parse import quote

import requests
import streamlit as st
try:
    from streamlit_js_eval import streamlit_js_eval
except ImportError:  # Local fallback until dependencies are installed.
    streamlit_js_eval = None


USER_ROLES_TABLE = "crm_user_roles"
AUTH_STORAGE_KEY = "crm_core_auth_session"
TOKEN_REFRESH_GRACE_SECONDS = 90
LOCAL_STORAGE_TTL_SECONDS = 8 * 60 * 60
ROLE_CEO = "CEO"
ROLE_EDITOR = "EDITOR"
ROLE_STAFF = "พนักงาน"
ROLE_VIEWER = "ทั่วไป"
SYSTEM_VIEW_ROLES = {ROLE_CEO, ROLE_EDITOR}


def get_secret(*names: str) -> str:
    for name in names:
        if name in st.secrets:
            return str(st.secrets[name])
        value = os.getenv(name, "")
        if value:
            return value
    return ""


def supabase_url() -> str:
    return get_secret("CRM_SUPABASE_URL", "SUPABASE_URL").rstrip("/")


def supabase_anon_key() -> str:
    return get_secret("CRM_SUPABASE_ANON_KEY", "SUPABASE_ANON_KEY")


def supabase_service_key() -> str:
    return get_secret("CRM_SUPABASE_SERVICE_KEY", "SUPABASE_SERVICE_KEY")


def inject_auth_css() -> None:
    st.markdown(
        """
<style>
.crm-auth-card {
  background:#fff7ed;
  border:1px solid #fed7aa;
  border-radius:8px;
  padding:12px;
  margin:8px 0 18px;
  color:#111827;
}
.crm-auth-card strong { color:#9a3412; }
[data-testid="stSidebar"] .crm-auth-card * { color:#111827 !important; }
div.stButton > button[kind="primary"],
div.stFormSubmitButton > button {
  background:#f97316 !important;
  color:#ffffff !important;
  border:1px solid #ea580c !important;
  border-radius:8px !important;
  font-weight:700 !important;
}
div.stButton > button[kind="secondary"] {
  background:#ffffff !important;
  color:#9a3412 !important;
  border:1px solid #f97316 !important;
  border-radius:8px !important;
}
</style>
""",
        unsafe_allow_html=True,
    )


def inject_login_css() -> None:
    st.markdown(
        """
<style>
.block-container {
  max-width: 1180px !important;
  padding-top: 4.2rem !important;
}
[data-testid="stDecoration"] { display:none !important; }
.crm-login-shell {
  margin: 0 auto 18px;
  max-width: 430px;
  text-align: left;
}
.crm-login-brand {
  display:flex;
  align-items:center;
  gap:12px;
  margin-bottom:18px;
}
.crm-login-logo {
  width:42px;
  height:42px;
  border-radius:12px;
  background:linear-gradient(135deg,#f97316 0%,#fb923c 54%,#dbeafe 100%);
  box-shadow:0 14px 30px rgba(249,115,22,.22);
}
.crm-login-title {
  font-size:28px;
  line-height:1.05;
  font-weight:800;
  letter-spacing:0;
  color:#111827;
}
.crm-login-subtitle {
  margin-top:4px;
  color:#64748b;
  font-size:14px;
}
.crm-login-note {
  background:#f8fafc;
  border:1px solid #dbeafe;
  color:#334155;
  border-radius:10px;
  padding:12px 14px;
  font-size:14px;
  margin-bottom:14px;
}
div[data-testid="stForm"] {
  max-width:430px;
  margin:0 auto !important;
  background:rgba(255,255,255,.92);
  border:1px solid #fed7aa;
  border-radius:14px;
  padding:22px 22px 20px;
  box-shadow:0 20px 55px rgba(15,23,42,.08);
}
div[data-testid="stForm"] label {
  color:#334155 !important;
  font-weight:700 !important;
  font-size:13px !important;
}
div[data-testid="stForm"] input {
  height:44px !important;
  background:#ffffff !important;
  border:1px solid #e2e8f0 !important;
  color:#0f172a !important;
  border-radius:10px !important;
  box-shadow:none !important;
}
div[data-testid="stForm"] input:focus {
  border-color:#f97316 !important;
  box-shadow:0 0 0 3px rgba(249,115,22,.14) !important;
}
div[data-testid="stForm"] input::placeholder {
  color:#94a3b8 !important;
}
div[data-testid="stForm"] [data-baseweb="input"] > div {
  background:#ffffff !important;
  border-radius:10px !important;
  border-color:#e2e8f0 !important;
}
div[data-testid="stForm"] button {
  min-height:44px !important;
  border-radius:10px !important;
}
@media (max-width: 760px) {
  .block-container { padding-top:2.4rem !important; }
  .crm-login-shell,
  div[data-testid="stForm"] { max-width:100%; }
}
</style>
""",
        unsafe_allow_html=True,
    )


def _auth_headers(key: str) -> dict[str, str]:
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }


def login_with_password(email: str, password: str) -> dict:
    base_url = supabase_url()
    anon_key = supabase_anon_key()
    if not base_url or not anon_key:
        raise RuntimeError("ยังไม่ได้ตั้งค่า CRM_SUPABASE_URL หรือ CRM_SUPABASE_ANON_KEY")

    response = requests.post(
        f"{base_url}/auth/v1/token?grant_type=password",
        headers=_auth_headers(anon_key),
        json={"email": email.strip().lower(), "password": password},
        timeout=20,
    )
    if response.status_code >= 400:
        raise RuntimeError("อีเมลหรือรหัสผ่านไม่ถูกต้อง หรือผู้ใช้ยังไม่ได้ถูกสร้างใน Supabase Auth")
    return response.json()


def refresh_auth_session(refresh_token: str) -> dict:
    base_url = supabase_url()
    anon_key = supabase_anon_key()
    if not base_url or not anon_key:
        raise RuntimeError("ยังไม่ได้ตั้งค่า CRM_SUPABASE_URL หรือ CRM_SUPABASE_ANON_KEY")

    response = requests.post(
        f"{base_url}/auth/v1/token?grant_type=refresh_token",
        headers=_auth_headers(anon_key),
        json={"refresh_token": refresh_token},
        timeout=20,
    )
    if response.status_code >= 400:
        raise RuntimeError("session หมดอายุ กรุณาเข้าสู่ระบบใหม่")
    return response.json()


def fetch_auth_user(access_token: str) -> dict:
    base_url = supabase_url()
    anon_key = supabase_anon_key()
    if not base_url or not anon_key:
        raise RuntimeError("ยังไม่ได้ตั้งค่า CRM_SUPABASE_URL หรือ CRM_SUPABASE_ANON_KEY")

    response = requests.get(
        f"{base_url}/auth/v1/user",
        headers={
            "apikey": anon_key,
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
        timeout=20,
    )
    if response.status_code >= 400:
        raise RuntimeError("session ไม่ถูกต้องหรือหมดอายุ")
    return response.json()


@st.cache_data(ttl=600, show_spinner=False)
def fetch_user_role(email: str) -> dict:
    normalized_email = email.strip().lower()
    default_role = {
        "email": normalized_email,
        "role": ROLE_VIEWER,
        "staff_name": "",
        "is_active": True,
    }
    base_url = supabase_url()
    service_key = supabase_service_key()
    if not base_url or not service_key:
        return default_role

    params = (
        f"?email=eq.{quote(normalized_email)}"
        "&is_active=eq.true"
        "&select=email,role,staff_name,is_active"
        "&limit=1"
    )
    response = requests.get(
        f"{base_url}/rest/v1/{USER_ROLES_TABLE}{params}",
        headers=_auth_headers(service_key),
        timeout=20,
    )
    if response.status_code >= 400:
        return default_role
    rows = response.json()
    if not rows:
        return default_role
    row = rows[0]
    row["email"] = normalized_email
    row["role"] = row.get("role") or ROLE_VIEWER
    row["staff_name"] = row.get("staff_name") or ""
    return row


def logout() -> None:
    st.session_state.auth_skip_restore = True
    st.session_state.auth_clear_browser_session = True
    for key in ("auth_access_token", "auth_refresh_token", "auth_user", "auth_role", "auth_session_expires_at"):
        st.session_state.pop(key, None)
    st.rerun()


def current_user() -> dict | None:
    ensure_fresh_session()
    auth_user = st.session_state.get("auth_user")
    auth_role = st.session_state.get("auth_role")
    if not auth_user or not auth_role:
        return None
    return {
        "email": auth_role.get("email") or auth_user.get("email") or "",
        "role": auth_role.get("role") or ROLE_VIEWER,
        "staff_name": auth_role.get("staff_name") or "",
        "raw_user": auth_user,
    }


def render_user_box(user: dict) -> None:
    with st.sidebar:
        st.markdown(
            f"""
<div class="crm-auth-card">
  <strong>เข้าสู่ระบบแล้ว</strong><br>
  {html_escape(user.get("email"))}<br>
  role: <strong>{html_escape(user.get("role"))}</strong><br>
  staff: {html_escape(user.get("staff_name") or "-")}
</div>
""",
            unsafe_allow_html=True,
        )
        if st.button("ออกจากระบบ", use_container_width=True, key="auth_logout_button"):
            logout()


def html_escape(value) -> str:
    return (
        str(value or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def require_login() -> dict:
    inject_auth_css()
    if st.session_state.pop("auth_clear_browser_session", False):
        clear_browser_session()
    restore_status = "empty"
    if not st.session_state.get("auth_skip_restore"):
        restore_status = restore_browser_session()
    user = current_user()
    if user:
        render_user_box(user)
        return user

    inject_login_css()
    if restore_status == "pending":
        st.info("กำลังตรวจสอบ session จาก browser...")
        st.stop()

    left, center, right = st.columns([1, 1.08, 1])
    with center:
        st.markdown(
            """
<div class="crm-login-shell">
  <div class="crm-login-brand">
    <div class="crm-login-logo"></div>
    <div>
      <div class="crm-login-title">Sales CRM</div>
      <div class="crm-login-subtitle">เข้าสู่ระบบเพื่อจัดการข้อมูลลูกค้า</div>
    </div>
  </div>
  <div class="crm-login-note">ใช้บัญชีที่ได้รับสิทธิ์จาก Supabase Auth เท่านั้น</div>
</div>
""",
            unsafe_allow_html=True,
        )
        with st.form("crm_login_form"):
            email = st.text_input("อีเมล", value="", placeholder="name@example.com")
            password = st.text_input("รหัสผ่าน", value="", type="password")
            submitted = st.form_submit_button("เข้าสู่ระบบ", use_container_width=True)

    if submitted:
        try:
            payload = login_with_password(email, password)
            auth_user = payload.get("user") or {}
            user_email = (auth_user.get("email") or email).strip().lower()
            role = fetch_user_role(user_email)
            st.session_state.auth_access_token = payload.get("access_token")
            st.session_state.auth_refresh_token = payload.get("refresh_token")
            st.session_state.auth_user = auth_user
            st.session_state.auth_role = role
            st.session_state.auth_session_expires_at = int(time.time()) + LOCAL_STORAGE_TTL_SECONDS
            st.session_state.pop("auth_skip_restore", None)
            st.session_state.pop("auth_clear_browser_session", None)
            save_browser_session(payload, role)
            user = current_user()
            if user:
                render_user_box(user)
                return user
        except Exception as exc:
            st.error(str(exc))
    st.stop()


def _jwt_exp(access_token: str | None) -> int | None:
    if not access_token or access_token.count(".") < 2:
        return None
    try:
        payload = access_token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        decoded = base64.urlsafe_b64decode(payload.encode("ascii"))
        return int(json.loads(decoded).get("exp"))
    except Exception:
        return None


def ensure_fresh_session() -> None:
    expires_at = int(st.session_state.get("auth_session_expires_at") or 0)
    if expires_at and expires_at <= int(time.time()):
        clear_browser_session()
        for key in ("auth_access_token", "auth_refresh_token", "auth_user", "auth_role", "auth_session_expires_at"):
            st.session_state.pop(key, None)
        return

    refresh_token = st.session_state.get("auth_refresh_token")
    if not refresh_token:
        return
    exp = _jwt_exp(st.session_state.get("auth_access_token"))
    if exp and exp - int(time.time()) > TOKEN_REFRESH_GRACE_SECONDS:
        return
    try:
        payload = refresh_auth_session(refresh_token)
        auth_user = payload.get("user") or st.session_state.get("auth_user") or {}
        user_email = (auth_user.get("email") or current_email()).strip().lower()
        role = fetch_user_role(user_email)
        st.session_state.auth_access_token = payload.get("access_token")
        st.session_state.auth_refresh_token = payload.get("refresh_token") or refresh_token
        st.session_state.auth_user = auth_user
        st.session_state.auth_role = role
        save_browser_session(payload, role)
    except Exception:
        clear_browser_session()
        for key in ("auth_access_token", "auth_refresh_token", "auth_user", "auth_role", "auth_session_expires_at"):
            st.session_state.pop(key, None)


def current_email() -> str:
    auth_role = st.session_state.get("auth_role") or {}
    auth_user = st.session_state.get("auth_user") or {}
    return auth_role.get("email") or auth_user.get("email") or ""


def save_browser_session(payload: dict, role: dict) -> None:
    if streamlit_js_eval is None:
        return
    expires_at = int(st.session_state.get("auth_session_expires_at") or 0) or int(time.time()) + LOCAL_STORAGE_TTL_SECONDS
    st.session_state.auth_session_expires_at = expires_at
    session_payload = {
        "access_token": payload.get("access_token"),
        "refresh_token": payload.get("refresh_token") or st.session_state.get("auth_refresh_token"),
        "user": payload.get("user") or st.session_state.get("auth_user") or {},
        "role": role or st.session_state.get("auth_role") or {},
        "expires_at": expires_at,
    }
    js_value = json.dumps(json.dumps(session_payload, ensure_ascii=False))
    streamlit_js_eval(
        js_expressions=f"localStorage.setItem('{AUTH_STORAGE_KEY}', {js_value}); 'ok'",
        key=f"auth_save_{int(time.time() * 1000)}",
    )


def clear_browser_session() -> None:
    if streamlit_js_eval is None:
        return
    streamlit_js_eval(
        js_expressions=f"localStorage.removeItem('{AUTH_STORAGE_KEY}'); 'ok'",
        key=f"auth_clear_{int(time.time() * 1000)}",
    )


def restore_browser_session() -> str:
    if current_email() or streamlit_js_eval is None:
        return "ready"
    stored = streamlit_js_eval(
        js_expressions=f"localStorage.getItem('{AUTH_STORAGE_KEY}')",
        key="auth_restore_session",
    )
    if stored is None and not st.session_state.get("auth_restore_checked_once"):
        st.session_state.auth_restore_checked_once = True
        return "pending"
    if not stored:
        return "empty"
    try:
        payload = json.loads(stored)
        access_token = payload.get("access_token")
        refresh_token = payload.get("refresh_token")
        expires_at = int(payload.get("expires_at") or 0)
        if not access_token or not refresh_token or not expires_at:
            clear_browser_session()
            return "empty"
        if expires_at <= int(time.time()):
            clear_browser_session()
            return "empty"
        st.session_state.auth_access_token = access_token
        st.session_state.auth_refresh_token = refresh_token
        st.session_state.auth_session_expires_at = expires_at

        try:
            verified_user = fetch_auth_user(access_token)
        except Exception:
            refreshed = refresh_auth_session(refresh_token)
            verified_user = refreshed.get("user") or {}
            st.session_state.auth_access_token = refreshed.get("access_token")
            st.session_state.auth_refresh_token = refreshed.get("refresh_token") or refresh_token

        user_email = (verified_user.get("email") or "").strip().lower()
        if not user_email:
            clear_browser_session()
            return "empty"
        st.session_state.auth_user = verified_user
        st.session_state.auth_role = fetch_user_role(user_email)
        save_browser_session(
            {
                "access_token": st.session_state.get("auth_access_token"),
                "refresh_token": st.session_state.get("auth_refresh_token"),
                "user": verified_user,
            },
            st.session_state.auth_role,
        )
        ensure_fresh_session()
        return "restored"
    except Exception:
        clear_browser_session()
        return "empty"


def can_manage_all(user: dict | None) -> bool:
    return bool(user and user.get("role") == ROLE_EDITOR)


def can_view_system_page(user: dict | None) -> bool:
    return bool(user and user.get("role") in SYSTEM_VIEW_ROLES)


def can_manage_system_page(user: dict | None) -> bool:
    return can_manage_all(user)


def _clean(value) -> str:
    return str(value or "").strip()


def can_edit_customer_lead(user: dict | None, customer) -> bool:
    if not user:
        return False
    role = user.get("role")
    if role == ROLE_EDITOR:
        return True
    if role != ROLE_STAFF:
        return False

    staff_name = _clean(user.get("staff_name"))
    if not staff_name:
        return False

    sales_staff = ""
    for key in ("sales_staff", "owner"):
        try:
            value = customer.get(key)
        except AttributeError:
            value = ""
        if _clean(value):
            sales_staff = _clean(value)
            break
    return sales_staff == staff_name
