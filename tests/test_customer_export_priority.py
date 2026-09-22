"""DB-free tests for the "ความสำคัญ" column in the customer .xlsx export.

No pytest in this environment -- discovered via the repo's stdlib test_*
runner, same as every other tests/test_*.py file here.
"""

import ast
import sys
from io import BytesIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import openpyxl

from ui.customer_export_ui import (
    CRM_EXPORT_HEADERS,
    CRM_LATEST_OWNER_HEADER,
    build_customer_export_xlsx,
    customer_export_row,
)


NEON_SOURCE = (Path(__file__).resolve().parents[1] / "neon_utils.py").read_text(encoding="utf-8")
FOLLOWUP_JOIN_KEY = "concat('customer_id:', d.id::text)"


def _function_source(name: str) -> str:
    tree = ast.parse(NEON_SOURCE)
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
    return ast.get_source_segment(NEON_SOURCE, node)


def test_priority_header_sits_right_after_owner():
    assert CRM_EXPORT_HEADERS.count("ความสำคัญ") == 1
    owner_index = CRM_EXPORT_HEADERS.index("พนักงานดูแล")
    assert CRM_EXPORT_HEADERS[owner_index + 1] == "ความสำคัญ"


def test_priority_value_is_exported():
    assert customer_export_row({"priority": "Premium"})["ความสำคัญ"] == "Premium"


def test_legacy_priority_values_read_like_the_followup_badge():
    assert customer_export_row({"priority": "urgent"})["ความสำคัญ"] == "Super VIP"
    assert customer_export_row({"priority": "Upsell โอนชำระ"})["ความสำคัญ"] == "โอนชำระ"


def test_row_without_followup_record_reads_new():
    # The follow-up page shows coalesce(l.priority, 'NEW') for such a row.
    assert customer_export_row({})["ความสำคัญ"] == "NEW"
    assert customer_export_row({"priority": None})["ความสำคัญ"] == "NEW"
    assert customer_export_row({"priority": "  "})["ความสำคัญ"] == "NEW"


def test_priority_comes_from_followup_table_not_import_raw_data():
    row = {"priority": None, "raw_data": {"ความสำคัญ": "VIP"}}
    assert customer_export_row(row)["ความสำคัญ"] == "NEW"


def test_latest_owner_mode_keeps_its_column_last():
    row = customer_export_row({"priority": "VIP", "latest_owner": "A"}, include_latest_owner=True)
    assert list(row) == [*CRM_EXPORT_HEADERS, CRM_LATEST_OWNER_HEADER]
    assert row["ความสำคัญ"] == "VIP"


def test_xlsx_contains_priority_column():
    data = build_customer_export_xlsx([{"order_id": "690523", "priority": "Premium"}, {"order_id": "1"}])
    ws = openpyxl.load_workbook(BytesIO(data)).active
    header = [c.value for c in ws[1]]
    column = header.index("ความสำคัญ") + 1
    assert ws.cell(row=2, column=column).value == "Premium"
    assert ws.cell(row=3, column=column).value == "NEW"
    assert ws.max_row == 3


def test_export_query_left_joins_followups_in_both_modes():
    source = _function_source("fetch_customer_export_rows")
    joins = source.count("left join public.crm_lead_followups lf")
    assert joins == 2, joins
    assert source.count(f"on lf.customer_key = {FOLLOWUP_JOIN_KEY}") == 2
    # An inner join would silently drop every order that was never followed up.
    assert "inner join public.crm_lead_followups" not in source
    assert "\n                join public.crm_lead_followups" not in source
    assert source.count("lf.priority") == 2


def test_join_cannot_duplicate_rows_because_it_is_on_the_primary_key():
    assert "customer_key text primary key" in NEON_SOURCE


def test_export_uses_the_same_join_key_as_the_followup_page():
    followup_source = _function_source("fetch_followup_page")
    assert f"on l.customer_key = {FOLLOWUP_JOIN_KEY}" in followup_source
    assert "coalesce(l.priority, 'NEW') as priority" in followup_source
