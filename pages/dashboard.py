import html
from datetime import date, timedelta

import pandas as pd
import streamlit as st

from auth_utils import current_user, require_login
from crm_theme import render_page_header
from nav_utils import render_sidebar_nav
from neon_utils import fetch_dashboard_kpis, fetch_sales_report, fetch_sales_report_owner_options, fetch_sales_report_rows


st.set_page_config(page_title="Dashboard", layout="wide")


def main() -> None:
    render_sidebar_nav()
    require_login()
    user = current_user() or {}
    render_page_header("Dashboard", "ภาพรวมงาน CRM รายวันสำหรับทีม Telesales")
    with st.spinner("กำลังโหลด KPI จาก Neon..."):
        kpis = fetch_dashboard_kpis(user)

    cols = st.columns(6)
    cols[0].metric("ลูกค้าทั้งหมด", f"{kpis['total_customers']:,}")
    cols[1].metric("ต้องติดตามวันนี้", f"{kpis['due_today']:,}")
    cols[2].metric("ค้างติดตาม", f"{kpis['overdue']:,}")
    cols[3].metric("Lead สนใจ", f"{kpis['interested']:,}")
    cols[4].metric("ปิดการขายแล้ว", f"{kpis['won']:,}")
    cols[5].metric("อัปเดตล่าสุด", kpis["latest_update"][:10] if kpis["latest_update"] else "-")

    st.markdown('<div class="crm-section-title">สถานะระบบ</div>', unsafe_allow_html=True)
    st.markdown(
        """
<div class="crm-card">
  ข้อมูล CRM หลักอ่าน/เขียนจาก Neon PostgreSQL และ Supabase ใช้เฉพาะ Login/Auth เท่านั้น
</div>
""",
        unsafe_allow_html=True,
    )
    render_sales_report(user)


def render_sales_report(user: dict) -> None:
    st.markdown('<div class="crm-section-title">📊 รายงานยอดขาย</div>', unsafe_allow_html=True)
    range_col, owner_col = st.columns([1, 1])
    range_label = range_col.selectbox(
        "ช่วงเวลา",
        ["วันนี้", "เลือกวันเดียว", "เลือกช่วงวันที่", "เมื่อวาน", "7 วัน", "30 วัน", "เดือนนี้"],
        key="dashboard_sales_range",
    )
    start_date, end_date = resolve_sales_range(range_label)
    if range_label == "เลือกวันเดียว":
        selected_date = st.date_input("เลือกวันที่", value=date.today(), key="dashboard_sales_single_date")
        start_date = selected_date
        end_date = selected_date
    elif range_label == "เลือกช่วงวันที่":
        custom_cols = st.columns(2)
        start_date = custom_cols[0].date_input("ตั้งแต่วันที่", value=date.today(), key="dashboard_sales_start")
        end_date = custom_cols[1].date_input("ถึงวันที่", value=date.today(), key="dashboard_sales_end")
        if start_date > end_date:
            st.warning("วันที่เริ่มต้นต้องไม่มากกว่าวันที่สิ้นสุด")
            return

    owner_filter = "ทั้งหมด"
    if (user or {}).get("role") in {"ADMIN", "EDITOR"}:
        owner_options = ["ทั้งหมด", *fetch_sales_report_owner_options(user)]
        owner_filter = owner_col.selectbox("ผู้ดูแล", owner_options, key="dashboard_sales_owner")
    else:
        owner_col.caption("รายงานนี้แสดงเฉพาะข้อมูลของคุณ")

    with st.spinner("กำลังโหลดรายงานยอดขายจาก Neon..."):
        report = fetch_sales_report(user, start_date, end_date, owner_filter)
    if not report.get("ready"):
        st.warning(
            "ยังใช้งานรายงานยอดขายไม่ได้ กรุณารัน migration "
            "`202606060001_add_sales_report_fields.sql` ใน Neon ก่อน"
        )
        return

    summary = report["summary"]
    new_order = summary.get("NEW_ORDER", {})
    upsell = summary.get("UPSELL", {})
    total = summary.get("TOTAL", {})

    st.markdown("##### NEW ORDER")
    cols = st.columns(3)
    cols[0].metric("ยอดขาย NEW ORDER", format_money(new_order.get("sales_amount")))
    cols[1].metric("จำนวนออเดอร์ NEW ORDER", f"{int(new_order.get('order_count') or 0):,}")
    cols[2].metric("ค่าเฉลี่ยต่อออเดอร์", format_money(new_order.get("aov")))

    st.markdown("##### UPSELL")
    cols = st.columns(3)
    cols[0].metric("ยอดขาย UPSELL", format_money(upsell.get("sales_amount")))
    cols[1].metric("จำนวนออเดอร์ UPSELL", f"{int(upsell.get('order_count') or 0):,}")
    cols[2].metric("ค่าเฉลี่ยต่อออเดอร์", format_money(upsell.get("aov")))

    st.markdown("##### รวม")
    cols = st.columns(3)
    cols[0].metric("ยอดขายรวม", format_money(total.get("sales_amount")))
    cols[1].metric("จำนวนออเดอร์รวม", f"{int(total.get('order_count') or 0):,}")
    cols[2].metric("AOV", format_money(total.get("aov")))

    rows = fetch_sales_report_rows(user, start_date, end_date, owner_filter)
    render_sales_order_table(rows, total.get("sales_amount"), total.get("order_count"))

    daily = report.get("daily") or []
    if not daily:
        st.info("ยังไม่พบยอดขายในช่วงเวลานี้")
        return
    chart_df = pd.DataFrame(daily)
    chart_df["sales_date"] = pd.to_datetime(chart_df["sales_date"])
    pivot = (
        chart_df.pivot_table(index="sales_date", columns="sale_type", values="sales_amount", aggfunc="sum")
        .fillna(0)
        .sort_index()
    )
    st.line_chart(pivot, use_container_width=True)


def render_sales_order_table(rows: list[dict], total_amount, total_orders) -> None:
    st.markdown("##### ตารางรายการขาย")
    if not rows:
        st.info("ยังไม่มีรายการ NEW_ORDER / UPSELL ในช่วงเวลานี้")
        return
    st.markdown(
        """
<style>
.sales-sheet-grid {
  display: grid;
  grid-template-columns: 52px 84px 132px 120px minmax(300px, 2fr) 96px 112px minmax(160px, 1fr);
  border: 1px solid #d97706;
  border-radius: 10px;
  overflow: hidden;
  background: #fff;
}
.sales-sheet-cell {
  border-right: 1px solid #f59e0b;
  border-bottom: 1px solid #f59e0b;
  min-height: 38px;
  padding: 8px 10px;
  font-size: 14px;
  line-height: 1.35;
  color: #111827;
  display: flex;
  align-items: center;
}
.sales-sheet-head {
  background: #fff200;
  color: #111827;
  font-weight: 800;
  justify-content: center;
}
.sales-sheet-row-alt {
  background: #fff7ed;
}
.sales-sheet-center {
  justify-content: center;
  text-align: center;
}
.sales-sheet-right {
  justify-content: flex-end;
  text-align: right;
}
.sales-summary-card {
  margin-top: 14px;
  max-width: 460px;
  border: 1px solid #d97706;
  border-radius: 10px;
  overflow: hidden;
  background: #fff7ed;
}
.sales-summary-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  border-bottom: 1px solid #f59e0b;
}
.sales-summary-row:last-child {
  border-bottom: 0;
}
.sales-summary-label {
  padding: 8px 12px;
  background: #fbbf24;
  font-weight: 800;
}
.sales-summary-value {
  padding: 8px 12px;
  background: #ffedd5;
  font-weight: 800;
  text-align: right;
}
.sales-summary-total .sales-summary-label,
.sales-summary-total .sales-summary-value {
  background: #f97316;
  color: #fff;
}
</style>
""",
        unsafe_allow_html=True,
    )
    header = ["ลำดับ", "เวลา", "ประเภทคำสั่งซื้อ", "เลขคำสั่งซื้อ", "ชื่อสินค้า", "จำนวนชิ้น", "ราคาอัพ", "หมายเหตุ"]
    html_parts = ['<div class="sales-sheet-grid">']
    for label in header:
        html_parts.append(f'<div class="sales-sheet-cell sales-sheet-head">{html.escape(label)}</div>')
    for index, row in enumerate(rows, start=1):
        sale_type = str(row.get("sale_type") or "").strip()
        row_class = "sales-sheet-row-alt" if index % 2 == 0 else ""
        product = " ".join(part for part in [str(row.get("sku") or "").strip(), str(row.get("product_name") or "").strip()] if part)
        cells = [
            (str(index), "sales-sheet-center"),
            (f"{row.get('sale_time') or '-'} น.", "sales-sheet-center"),
            (sale_type or "-", "sales-sheet-center"),
            (str(row.get("order_id") or "-"), "sales-sheet-center"),
            (product or "-", ""),
            (str(int(row.get("quantity") or 0)), "sales-sheet-center"),
            (format_money(row.get("amount")), "sales-sheet-right"),
            (str(row.get("note") or ""), ""),
        ]
        for value, extra_class in cells:
            classes = " ".join(part for part in ["sales-sheet-cell", row_class, extra_class] if part)
            html_parts.append(f'<div class="{classes}">{html.escape(value)}</div>')
    html_parts.append("</div>")
    st.markdown("".join(html_parts), unsafe_allow_html=True)
    st.markdown(
        f"""
<div class="sales-summary-card">
  <div class="sales-summary-row"><div class="sales-summary-label">จำนวนออเดอร์</div><div class="sales-summary-value">{int(total_orders or 0):,}</div></div>
  <div class="sales-summary-row sales-summary-total"><div class="sales-summary-label">ยอดขายทั้งหมด</div><div class="sales-summary-value">{format_money(total_amount)}</div></div>
</div>
""",
        unsafe_allow_html=True,
    )


def resolve_sales_range(label: str) -> tuple[date, date]:
    today = date.today()
    if label == "เมื่อวาน":
        yesterday = today - timedelta(days=1)
        return yesterday, yesterday
    if label == "7 วัน":
        return today - timedelta(days=6), today
    if label == "30 วัน":
        return today - timedelta(days=29), today
    if label == "เดือนนี้":
        return today.replace(day=1), today
    return today, today


def format_money(value) -> str:
    return f"{float(value or 0):,.2f}"


main()
