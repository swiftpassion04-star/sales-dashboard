import importlib.util
from pathlib import Path

import streamlit as st

from auth_utils import can_manage_all, require_login
from crm_theme import render_page_header
from nav_utils import render_sidebar_nav


st.set_page_config(page_title="Users", layout="wide")


def main() -> None:
    render_sidebar_nav()
    auth_user = require_login()
    if not can_manage_all(auth_user):
        st.warning("หน้านี้จัดการได้เฉพาะ EDITOR เท่านั้น")
        st.stop()
    render_page_header("User / Role", "จัดการรายชื่อผู้ดูแลและข้อมูล staff mapping")
    legacy = load_legacy_users_page()
    legacy.require_config()
    legacy.render_staff_options(auth_user)


def load_legacy_users_page():
    path = next(Path("pages").glob("7_*.py"))
    source = path.read_text(encoding="utf-8")
    safe_source = "\n".join(line for line in source.splitlines() if "st.set_page_config" not in line and "main()" != line.strip())
    spec = importlib.util.spec_from_loader("legacy_users_page", loader=None)
    module = importlib.util.module_from_spec(spec)
    module.__file__ = str(path)
    exec(compile(safe_source, str(path), "exec"), module.__dict__)
    return module


main()

