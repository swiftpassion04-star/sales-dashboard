import os
from datetime import date

import pandas as pd
import requests
import streamlit as st


st.set_page_config(page_title="Project CRM Dashboard", layout="wide")

PRODUCT_GROUP_ORDER = [
    "ยา/อาหารเสริม",
    "DKUB",
    "SMASH",
    "เด็ก/คุณแม่",
    "สัตว์เลี้ยง",
    "รถ/เครื่องมือช่าง",
    "สินค้าทั่วไป",
]


def get_secret(*names: str) -> str:
    for name in names:
        if name in st.secrets:
            return st.secrets[name]
        value = os.getenv(name, "")
        if value:
            return value
    return ""


def get_named_secret(name: str) -> str:
    if name in st.secrets:
        return st.secrets[name]
    return os.getenv(name, "")


SUPABASE_URL = get_secret("CRM_SUPABASE_URL", "SUPABASE_URL").rstrip("/")
SUPABASE_ANON_KEY = get_secret("CRM_SUPABASE_ANON_KEY", "SUPABASE_ANON_KEY")


def require_config() -> None:
    missing = [name for name, value in {
        "SUPABASE_URL": SUPABASE_URL,
        "SUPABASE_ANON_KEY": SUPABASE_ANON_KEY,
    }.items() if not value]
    if missing:
        st.error("ยังไม่ได้ตั้งค่า: " + ", ".join(missing))
        st.stop()


@st.cache_data(ttl=120, show_spinner=False)
def load_customers() -> pd.DataFrame:
    require_config()
    endpoint = f"{SUPABASE_URL}/rest/v1/crm_customers"
    headers = {
        "apikey": SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
    }
    params = {
        "select": "*",
        "order": "updated_at.desc",
        "limit": "50000",
    }
    response = requests.get(endpoint, headers=headers, params=params, timeout=30)
    if response.status_code >= 300:
        st.error(response.text)
        st.stop()
    return pd.DataFrame(response.json())


def normalize_dates(df: pd.DataFrame) -> pd.DataFrame:
    for col in ["updated_at", "synced_at", "call_date_1", "call_date_2", "call_date_3"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")
    return df


def sidebar_filters(df: pd.DataFrame) -> pd.DataFrame:
    st.sidebar.header("ตัวกรอง")

    product_options = [g for g in PRODUCT_GROUP_ORDER if g in set(df.get("product_group", []))]
    extra_groups = sorted(set(df.get("product_group", pd.Series(dtype=str)).dropna()) - set(product_options))
    product_group = st.sidebar.selectbox("กลุ่มสินค้า", ["ทั้งหมด"] + product_options + extra_groups)

    staff_options = sorted(df.get("sales_staff", pd.Series(dtype=str)).dropna().unique().tolist())
    staff = st.sidebar.selectbox("พนักงาน", ["ทั้งหมด"] + staff_options)

    keyword = st.sidebar.text_input("ค้นหา", placeholder="ชื่อลูกค้า เบอร์ URL หรือสินค้า")

    min_date = df["updated_at"].min().date() if "updated_at" in df and df["updated_at"].notna().any() else date.today()
    max_date = df["updated_at"].max().date() if "updated_at" in df and df["updated_at"].notna().any() else date.today()
    date_range = st.sidebar.date_input("ช่วงวันที่อัปเดต", value=(min_date, max_date))

    filtered = df.copy()
    if product_group != "ทั้งหมด":
        filtered = filtered[filtered["product_group"] == product_group]
    if staff != "ทั้งหมด":
        filtered = filtered[filtered["sales_staff"] == staff]
    if keyword:
        text_cols = ["customer", "phone1", "phone2", "product_url", "product_name", "note"]
        haystack = filtered[text_cols].fillna("").astype(str).agg(" ".join, axis=1)
        filtered = filtered[haystack.str.contains(keyword, case=False, na=False)]
    if isinstance(date_range, tuple) and len(date_range) == 2 and "updated_at" in filtered:
        start, end = date_range
        filtered = filtered[
            (filtered["updated_at"].dt.date >= start)
            & (filtered["updated_at"].dt.date <= end)
        ]
    return filtered


st.title("Project CRM Dashboard")

df = normalize_dates(load_customers())
if df.empty:
    st.warning("ยังไม่มีข้อมูลใน Supabase")
    st.stop()

filtered = sidebar_filters(df)

col1, col2, col3, col4 = st.columns(4)
col1.metric("ลูกค้าทั้งหมด", f"{filtered['customer_id'].nunique():,}")
col2.metric("จำนวนแถว", f"{len(filtered):,}")
col3.metric("กลุ่มสินค้า", f"{filtered['product_group'].nunique():,}")
col4.metric("พนักงาน", f"{filtered['sales_staff'].nunique():,}")

tab_table, tab_group, tab_staff = st.tabs(["ข้อมูลลูกค้า", "ตามกลุ่มสินค้า", "ตามพนักงาน"])

with tab_table:
    display_cols = [
        "customer",
        "sales_staff",
        "product_group",
        "product_name",
        "phone1",
        "phone2",
        "note",
        "updated_at",
        "synced_at",
    ]
    cols = [col for col in display_cols if col in filtered.columns]
    table_df = filtered[cols].copy()
    table_df = table_df.rename(
        columns={
            "customer": "ชื่อลูกค้า",
            "sales_staff": "ผู้ดูแล",
            "product_group": "กลุ่มสินค้า",
            "product_name": "สินค้า",
            "phone1": "เบอร์โทรติดต่อ",
            "phone2": "เบอร์โทรสำรอง",
            "note": "โน๊ต",
            "updated_at": "อัพเดต",
            "synced_at": "สถานะ",
        }
    )
    if "สถานะ" in table_df.columns:
        table_df["สถานะ"] = "ซิงก์แล้ว"
    st.dataframe(table_df, use_container_width=True, hide_index=True)

with tab_group:
    group_df = (
        filtered.groupby("product_group", dropna=False)
        .agg(customers=("customer_id", "nunique"), rows=("customer_id", "count"))
        .reset_index()
        .sort_values("customers", ascending=False)
    )
    st.bar_chart(group_df.set_index("product_group")["customers"])
    st.dataframe(group_df, use_container_width=True, hide_index=True)

with tab_staff:
    staff_df = (
        filtered.groupby("sales_staff", dropna=False)
        .agg(customers=("customer_id", "nunique"), rows=("customer_id", "count"))
        .reset_index()
        .sort_values("customers", ascending=False)
    )
    st.bar_chart(staff_df.set_index("sales_staff")["customers"])
    st.dataframe(staff_df, use_container_width=True, hide_index=True)
