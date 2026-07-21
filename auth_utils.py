import os
import base64
import json
import time

import requests
import streamlit as st
from app_logging import log_exception, user_error_message
from permissions import (
    ROLE_EDITOR,
    ROLE_STAFF,
    ROLE_STAFF_ALIASES,
    ROLE_STAFF_READONLY,
    ROLE_TELESELL,
    ROLE_TELESELL_ALIASES,
    ROLE_VIEWER,
    SYSTEM_VIEW_ROLES,
    can_edit_customer_lead as permission_can_edit_customer_lead,
    can_manage_all as permission_can_manage_all,
    can_manage_system_page as permission_can_manage_system_page,
    can_view_system_page as permission_can_view_system_page,
    clean as permission_clean,
)
try:
    from streamlit_js_eval import streamlit_js_eval
except ImportError:  # Local fallback until dependencies are installed.
    streamlit_js_eval = None


AUTH_STORAGE_KEY = "crm_core_auth_session"
TOKEN_REFRESH_GRACE_SECONDS = 90
LOCAL_STORAGE_TTL_SECONDS = 8 * 60 * 60
BROWSER_SESSION_PENDING = "pending"
BROWSER_SESSION_EMPTY = "empty"
BROWSER_SESSION_HAS_SESSION = "has_session"
BROWSER_SESSION_INVALID = "invalid"
_BROWSER_SESSION_BRIDGE_READY_KEY = "bridge_ready"
_BROWSER_SESSION_BRIDGE_PAYLOAD_KEY = "session_payload"


def _decode_browser_session_payload(payload) -> tuple[str, dict | None]:
    if payload is None:
        return BROWSER_SESSION_PENDING, None

    decoded = payload
    if isinstance(decoded, str):
        try:
            decoded = json.loads(decoded)
        except (TypeError, json.JSONDecodeError):
            return BROWSER_SESSION_INVALID, None

    if not isinstance(decoded, dict):
        return BROWSER_SESSION_INVALID, None

    if decoded.get(_BROWSER_SESSION_BRIDGE_READY_KEY) is True:
        stored_payload = decoded.get(_BROWSER_SESSION_BRIDGE_PAYLOAD_KEY)
        if stored_payload in (None, ""):
            return BROWSER_SESSION_EMPTY, None
        try:
            decoded = json.loads(stored_payload) if isinstance(stored_payload, str) else stored_payload
        except (TypeError, json.JSONDecodeError):
            return BROWSER_SESSION_INVALID, None
        if not isinstance(decoded, dict):
            return BROWSER_SESSION_INVALID, None

    if not decoded:
        return BROWSER_SESSION_EMPTY, None
    if decoded.get("access_token") and decoded.get("refresh_token"):
        return BROWSER_SESSION_HAS_SESSION, decoded
    return BROWSER_SESSION_INVALID, None


def classify_browser_session_payload(payload) -> str:
    state, _ = _decode_browser_session_payload(payload)
    return state


def get_secret(*names: str) -> str:
    for name in names:
        if name in st.secrets:
            return str(st.secrets[name])
        value = os.getenv(name, "")
        if value:
            return value
    return ""


def supabase_url() -> str:
    return get_secret(
        "AUTH_SUPABASE_URL",
        "SUPABASE_AUTH_URL",
        "CRM_SUPABASE_URL",
        "SUPABASE_URL",
    ).rstrip("/")


def supabase_anon_key() -> str:
    return get_secret(
        "AUTH_SUPABASE_ANON_KEY",
        "SUPABASE_AUTH_ANON_KEY",
        "CRM_SUPABASE_ANON_KEY",
        "SUPABASE_ANON_KEY",
    )


def inject_auth_css() -> None:
    st.markdown(
        """
<style>
.crm-auth-card {
  background:#FFFFFF;
  border:1px solid #F3E4D2;
  border-radius:18px;
  padding:16px;
  margin:12px 0 18px;
  color:#1F2937;
  box-shadow:0 4px 14px rgba(124,45,18,.045);
}
.crm-auth-card strong { color:#9A4B12; }
[data-testid="stSidebar"] .crm-auth-card * { color:#1F2937 !important; }
div.stButton > button[kind="primary"],
div.stFormSubmitButton > button {
  background:#F97316 !important;
  color:#ffffff !important;
  border:1px solid #EA580C !important;
  border-radius:999px !important;
  font-weight:700 !important;
  min-height:46px !important;
  padding:10px 24px !important;
}
div.stButton > button[kind="secondary"] {
  background:#ffffff !important;
  color:#9A4B12 !important;
  border:1px solid #F97316 !important;
  border-radius:999px !important;
  min-height:46px !important;
  padding:10px 24px !important;
}
div[data-baseweb="input"] > div,
div[data-baseweb="select"] > div,
div[data-baseweb="base-input"],
div[data-baseweb="textarea"],
textarea,
input {
  background:#ffffff !important;
  color:#1F2937 !important;
  -webkit-text-fill-color:#1F2937 !important;
}
[data-testid="stExpander"] details,
[data-testid="stExpander"] details summary,
[data-testid="stFileUploader"] section,
[data-testid="stFileUploader"] section * {
  background:#ffffff !important;
  color:#1F2937 !important;
}
</style>
""",
        unsafe_allow_html=True,
    )


def inject_login_css() -> None:
    st.markdown(
        """
<style>
.stApp,
[data-testid="stAppViewContainer"],
[data-testid="stMain"] {
  background:
    radial-gradient(circle at 20% 10%, rgba(255,219,181,.48), transparent 28%),
    radial-gradient(circle at 82% 4%, rgba(255,242,226,.72), transparent 34%),
    #FFF8F0 !important;
  color:#1F2937 !important;
}
[data-testid="stSidebar"] {
  background:#FFF3E8 !important;
  border-right:1px solid #F3E4D2 !important;
}
[data-testid="stSidebarNav"] {
  display:none !important;
}
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
  border-radius:14px;
  background:#F97316;
  box-shadow:0 12px 24px rgba(249,115,22,.18);
}
.crm-login-title {
  font-size:28px;
  line-height:1.05;
  font-weight:800;
  letter-spacing:0;
  color:#1F2937;
}
.crm-login-subtitle {
  margin-top:4px;
  color:#6B7280;
  font-size:14px;
}
.crm-login-note {
  background:#FFF8F0;
  border:1px solid #F3E4D2;
  color:#6B7280;
  border-radius:18px;
  padding:12px 14px;
  font-size:14px;
  margin-bottom:14px;
}
.crm-login-status {
  max-width:430px;
  margin:0 auto;
  background:#FFFFFF;
  border:1px solid #F3E4D2;
  color:#6B7280;
  border-radius:24px;
  padding:18px 20px;
  box-shadow:0 18px 42px rgba(124,45,18,.10);
}
div[data-testid="stForm"] {
  max-width:430px;
  margin:0 auto !important;
  background:#FFFFFF;
  border:1px solid #F3E4D2;
  border-radius:24px;
  padding:24px 24px 22px;
  box-shadow:0 18px 42px rgba(124,45,18,.10);
}
div[data-testid="stForm"] label {
  color:#1F2937 !important;
  font-weight:700 !important;
  font-size:13px !important;
}
div[data-testid="stForm"] input {
  height:46px !important;
  background:#ffffff !important;
  border:1px solid #F3E4D2 !important;
  color:#1F2937 !important;
  border-radius:14px !important;
  box-shadow:none !important;
}
div[data-testid="stForm"] input:focus {
  border-color:#F97316 !important;
  box-shadow:0 0 0 4px rgba(249,115,22,.14) !important;
}
div[data-testid="stForm"] input::placeholder {
  color:#94a3b8 !important;
}
div[data-testid="stForm"] [data-baseweb="input"] > div {
  background:#ffffff !important;
  border-radius:14px !important;
  border-color:#F3E4D2 !important;
}
div[data-testid="stForm"] button {
  min-height:46px !important;
  border-radius:999px !important;
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


def _supabase_auth_request(method: str, url: str, **kwargs) -> requests.Response:
    try:
        return requests.request(method, url, timeout=20, **kwargs)
    except requests.Timeout as exc:
        raise RuntimeError("เชื่อมต่อ Supabase Auth timeout กรุณาลองใหม่อีกครั้ง") from exc
    except requests.RequestException as exc:
        raise RuntimeError("เชื่อมต่อ Supabase Auth ไม่สำเร็จ กรุณาตรวจอินเทอร์เน็ตหรือ Supabase project") from exc


def _raise_auth_error(response: requests.Response, default_message: str) -> None:
    if response.status_code == 402:
        raise RuntimeError("Supabase Auth ถูกจำกัดการใช้งาน กรุณาตรวจ Supabase project หรือ billing")
    if response.status_code >= 400:
        raise RuntimeError(default_message)


def login_with_password(email: str, password: str) -> dict:
    base_url = supabase_url()
    anon_key = supabase_anon_key()
    if not base_url or not anon_key:
        raise RuntimeError("ยังไม่ได้ตั้งค่า CRM_SUPABASE_URL หรือ CRM_SUPABASE_ANON_KEY")

    response = _supabase_auth_request(
        "POST",
        f"{base_url}/auth/v1/token?grant_type=password",
        headers=_auth_headers(anon_key),
        json={"email": email.strip().lower(), "password": password},
    )
    _raise_auth_error(response, "อีเมลหรือรหัสผ่านไม่ถูกต้อง หรือผู้ใช้ยังไม่ได้ถูกสร้างใน Supabase Auth")
    return response.json()


def refresh_auth_session(refresh_token: str) -> dict:
    base_url = supabase_url()
    anon_key = supabase_anon_key()
    if not base_url or not anon_key:
        raise RuntimeError("ยังไม่ได้ตั้งค่า CRM_SUPABASE_URL หรือ CRM_SUPABASE_ANON_KEY")

    response = _supabase_auth_request(
        "POST",
        f"{base_url}/auth/v1/token?grant_type=refresh_token",
        headers=_auth_headers(anon_key),
        json={"refresh_token": refresh_token},
    )
    _raise_auth_error(response, "session หมดอายุ กรุณาเข้าสู่ระบบใหม่")
    return response.json()


def fetch_auth_user(access_token: str) -> dict:
    base_url = supabase_url()
    anon_key = supabase_anon_key()
    if not base_url or not anon_key:
        raise RuntimeError("ยังไม่ได้ตั้งค่า CRM_SUPABASE_URL หรือ CRM_SUPABASE_ANON_KEY")

    response = _supabase_auth_request(
        "GET",
        f"{base_url}/auth/v1/user",
        headers={
            "apikey": anon_key,
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
    )
    _raise_auth_error(response, "session ไม่ถูกต้องหรือหมดอายุ")
    return response.json()


@st.cache_data(ttl=600, show_spinner=False)
def fetch_user_role(email: str) -> dict:
    normalized_email = email.strip().lower()
    default_role = {
        "email": normalized_email,
        "role": ROLE_VIEWER,
        "staff_code": "",
        "staff_name": "",
        "is_active": True,
    }
    try:
        from neon_utils import fetch_user_role_from_neon

        row = fetch_user_role_from_neon(normalized_email)
    except Exception:
        return default_role
    if not row:
        return default_role
    row["email"] = normalized_email
    row["role"] = row.get("role") or ROLE_VIEWER
    row["staff_code"] = row.get("staff_code") or ""
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
        "staff_code": auth_role.get("staff_code") or "",
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


def render_login_shell(message: str | None = None) -> None:
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
        if message:
            st.markdown(
                f'<div class="crm-login-status">{html_escape(message)}</div>',
                unsafe_allow_html=True,
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
        if restore_status == "restored" and st.session_state.get("crm_sidebar_nav_last_disabled"):
            st.session_state.crm_sidebar_nav_last_disabled = False
            st.rerun()
        render_user_box(user)
        return user

    inject_login_css()
    if restore_status == "pending":
        render_login_shell("กำลังตรวจสอบ session จาก browser...")
        st.stop()

    render_login_shell()
    left, center, right = st.columns([1, 1.08, 1])
    with center:
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
            error_reference_id = log_exception(
                "auth_login_failed",
                exc,
                safe_metadata_values={
                    "page": "login",
                    "action": "login",
                    "component": "auth",
                    "outcome": "failure",
                },
            )
            st.error(user_error_message(error_reference_id))
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
        js_expressions=(
            "JSON.stringify({"
            f"{_BROWSER_SESSION_BRIDGE_READY_KEY}:true,"
            f"{_BROWSER_SESSION_BRIDGE_PAYLOAD_KEY}:localStorage.getItem({json.dumps(AUTH_STORAGE_KEY)})"
            "})"
        ),
        key="auth_restore_session",
    )
    restore_state, payload = _decode_browser_session_payload(stored)
    if restore_state == BROWSER_SESSION_PENDING:
        return "pending"
    if restore_state == BROWSER_SESSION_EMPTY:
        return "empty"
    try:
        if restore_state == BROWSER_SESSION_INVALID:
            raise ValueError("invalid browser session payload")
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

        refreshed_payload = None
        try:
            verified_user = fetch_auth_user(access_token)
        except Exception:
            refreshed = refresh_auth_session(refresh_token)
            refreshed_payload = refreshed
            verified_user = refreshed.get("user") or {}
            st.session_state.auth_access_token = refreshed.get("access_token")
            st.session_state.auth_refresh_token = refreshed.get("refresh_token") or refresh_token

        user_email = (verified_user.get("email") or "").strip().lower()
        if not user_email:
            clear_browser_session()
            return "empty"
        st.session_state.auth_user = verified_user
        st.session_state.auth_role = fetch_user_role(user_email)
        if refreshed_payload is not None:
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
    return permission_can_manage_all(user)


def can_view_system_page(user: dict | None) -> bool:
    return permission_can_view_system_page(user)


def can_manage_system_page(user: dict | None) -> bool:
    return permission_can_manage_system_page(user)


def _clean(value) -> str:
    return permission_clean(value)


def can_edit_customer_lead(user: dict | None, customer) -> bool:
    return permission_can_edit_customer_lead(user, customer)
