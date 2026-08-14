"""XLSX export for the Dashboard "ตารางรายการขาย" table.

Mirrors the shape of ui/customer_export_ui.py (pandas + openpyxl into a
BytesIO, handed to st.download_button).

Kept in its own module rather than inside pages/dashboard.py because that
page calls main() at import time, so nothing in it can be imported by a
test without running the whole page against a live database.

Export scope: exactly the rows the table is currently showing, i.e. after
the "จำนวนแถวที่แสดง" limit has been applied -- what you see is what you
download. No new database query is issued; the rows already fetched for
the table are reused.

Values are written as real types rather than the table's display strings
so the sheet is usable: ลำดับ/จำนวนชิ้น as int, ราคาอัพ as float (so Excel
can sum it), and the time without its " น." suffix. Empty text cells are
left blank instead of the table's "-" placeholder.
"""

from datetime import date, datetime
from io import BytesIO

import pandas as pd
import streamlit as st


SALES_EXPORT_HEADERS = [
    "ลำดับ",
    "เวลา",
    "ประเภทคำสั่งซื้อ",
    "เลขคำสั่งซื้อ",
    "ชื่อสินค้า",
    "จำนวนชิ้น",
    "ราคาอัพ",
    "พนักงานที่สร้าง",
]


def _text(value) -> str:
    return str(value or "").strip()


def sales_export_product_name(row: dict) -> str:
    """`sku` + `product_name`, matching how the table builds that column."""
    parts = [_text(row.get("sku")), _text(row.get("product_name"))]
    return " ".join(part for part in parts if part)


def _int(value) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _float(value) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def build_sales_export_rows(display_rows: list[dict]) -> list[dict]:
    """One dict per visible table row, keyed by the Thai column headers.

    `ลำดับ` is the table's 1-based position, so the sheet keeps the same
    ordering the user is looking at.
    """
    exported = []
    for index, row in enumerate(display_rows or [], start=1):
        exported.append(
            {
                "ลำดับ": index,
                "เวลา": _text(row.get("sale_time")),
                "ประเภทคำสั่งซื้อ": _text(row.get("sale_type")),
                "เลขคำสั่งซื้อ": _text(row.get("order_id")),
                "ชื่อสินค้า": sales_export_product_name(row),
                "จำนวนชิ้น": _int(row.get("quantity")),
                "ราคาอัพ": _float(row.get("amount")),
                "พนักงานที่สร้าง": _text(row.get("created_staff")),
            }
        )
    return exported


def build_sales_export_xlsx(display_rows: list[dict]) -> bytes:
    df = pd.DataFrame(build_sales_export_rows(display_rows), columns=SALES_EXPORT_HEADERS)
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="sales_report")
    return buffer.getvalue()


def build_sales_export_filename(start_date: date | None, end_date: date | None) -> str:
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    if start_date and end_date:
        return f"crm_sales_report_{start_date:%Y%m%d}_{end_date:%Y%m%d}_{stamp}.xlsx"
    return f"crm_sales_report_{stamp}.xlsx"


def render_sales_report_download(
    display_rows: list[dict],
    *,
    start_date: date | None = None,
    end_date: date | None = None,
    key: str = "dashboard_sales_report_xlsx",
) -> None:
    """Download button for the rows currently shown in the table."""
    if not display_rows:
        return
    st.download_button(
        f"⬇️ ดาวน์โหลดตารางนี้ (.xlsx) — {len(display_rows):,} รายการ",
        data=build_sales_export_xlsx(display_rows),
        file_name=build_sales_export_filename(start_date, end_date),
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key=key,
    )
