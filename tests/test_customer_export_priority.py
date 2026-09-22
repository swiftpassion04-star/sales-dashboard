"""DB-free tests for the "ความสำคัญ" column in the customer .xlsx export.

The column must carry the customer's *current* priority -- the value the
follow-up page shows for that customer -- on every one of their order rows.

The query tests run the real fetch_customer_export_rows / fetch_followup_page
against an in-memory SQLite database. Only the connection is swapped, and the
SQL goes through a small Postgres -> SQLite translation (schema prefix, `::`
casts, least -> min). That exercises the real joins and ranking, but it is
SQLite, not Neon.

No pytest in this environment -- discovered via the repo's stdlib test_*
runner, same as every other tests/test_*.py file here.
"""

import ast
import re
import sqlite3
import sys
from contextlib import contextmanager
from datetime import date, datetime
from io import BytesIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import openpyxl

import neon_utils
from ui.customer_export_ui import (
    CRM_EXPORT_HEADERS,
    CRM_LATEST_OWNER_HEADER,
    build_customer_export_xlsx,
    customer_export_row,
)


NEON_SOURCE = (Path(__file__).resolve().parents[1] / "neon_utils.py").read_text(encoding="utf-8")
FOLLOWUP_JOIN_KEY = "concat('customer_id:', d.id::text)"
PHONE_KEY_SQL = (
    "case when nullif(phone1, '') is not null and nullif(phone2, '') is not null "
    "then least(phone1, phone2) else coalesce(nullif(phone1, ''), nullif(phone2, ''), id::text) end"
)


# --- fixture data -----------------------------------------------------------
# (id, phone1, phone2, order_date, import_status)
ORDERS = [
    # A: current row is 3 (Super VIP). Row 1 has a stale record, row 4 is
    # invalid, and there is also a record keyed by the bare phone number.
    (1, "0811111111", "", "2026-07-01", "valid"),
    (2, "0811111111", "", "2026-08-01", "valid"),
    (3, "0811111111", "", "2026-09-01", "valid"),
    (4, "0811111111", "", "2026-09-15", "invalid"),
    # B: current row 6 is VIP.
    (5, "0822222222", "", "2026-07-05", "valid"),
    (6, "0822222222", "", "2026-08-05", "valid"),
    # C: current row 8 holds the legacy value "urgent".
    (7, "0833333333", "", "2026-07-07", "valid"),
    (8, "0833333333", "", "2026-08-07", "valid"),
    # D: no follow-up record anywhere.
    (9, "0844444444", "", "2026-07-09", "valid"),
    (10, "0844444444", "", "2026-08-09", "valid"),
    # E: one customer across phone1/phone2 -- both rows key to least() = 0855555555.
    (11, "0866666666", "0855555555", "2026-07-11", "valid"),
    (12, "0855555555", "", "2026-08-11", "valid"),
    # F: only the OLD row has a record; the current row 14 has none.
    (13, "0877777777", "", "2026-07-13", "valid"),
    (14, "0877777777", "", "2026-08-13", "valid"),
    # G: no phone at all -- the row is its own customer (phone_key = id).
    (15, "", "", "2026-07-15", "valid"),
    # H: same order_date and uploaded_at; the tie goes to the larger numeric id
    # (100 > 98), whereas text ordering would pick "98".
    (98, "0888888888", "", "2026-08-20", "valid"),
    (100, "0888888888", "", "2026-08-20", "valid"),
]
FOLLOWUPS = {
    "customer_id:1": "Premium",
    "customer_id:3": "Super VIP",
    "customer_id:4": "Economy",
    "0811111111": "Dismiss",
    "customer_id:6": "VIP",
    "customer_id:8": "urgent",
    "customer_id:12": "Premium",
    "customer_id:13": "VIP",
    "customer_id:15": "Economy",
    "customer_id:98": "Economy",
    "customer_id:100": "VIP",
}
VALID_IDS = [str(o[0]) for o in ORDERS if o[4] == "valid"]


def _timestamp(order_date: str) -> str:
    return f"{order_date} 03:00:00+00:00"


def _build_db() -> sqlite3.Connection:
    db = sqlite3.connect(":memory:")
    db.execute(
        """
        create table crm_data_imports (
          id integer primary key, order_date text, order_id text, sku text,
          product_name text, quantity numeric, total_amount numeric, amount numeric,
          carrier text, tracking_no text, url text, customer_name text,
          phone1 text, phone2 text, address text, city text, province text,
          postal_code text, owner text, staff_code text, order_status text,
          raw_data text, import_status text, uploaded_at text, created_at text,
          updated_at text
        )
        """
    )
    db.execute(
        """
        create table crm_lead_followups (
          customer_key text primary key, priority text, lead_status text,
          followup_status text, follow_up_status text, next_followup_date text,
          follow_up_date text, followup_note text, follow_up_note text,
          updated_by text, updated_at text
        )
        """
    )
    for row_id, phone1, phone2, order_date, status in ORDERS:
        stamp = _timestamp(order_date)
        db.execute(
            "insert into crm_data_imports (id, order_date, order_id, phone1, phone2, owner,"
            " import_status, uploaded_at, created_at, updated_at) values (?,?,?,?,?,?,?,?,?,?)",
            (row_id, order_date, f"ORD{row_id}", phone1, phone2, "owner", status, stamp, stamp, stamp),
        )
    for key, priority in FOLLOWUPS.items():
        db.execute("insert into crm_lead_followups (customer_key, priority) values (?, ?)", (key, priority))
    return db


def _to_sqlite(sql: str) -> str:
    sql = sql.replace("public.", "")
    sql = sql.replace(")::text", ")")
    sql = re.sub(r"([A-Za-z_][\w.]*)::(\w+)", r"cast(\1 as \2)", sql)
    sql = re.sub(r"\bleast\(", "min(", sql)
    return sql.replace("%s", "?")


def _param(value):
    return value.isoformat(sep=" ") if isinstance(value, datetime) else value


class _Cursor:
    def __init__(self, db: sqlite3.Connection):
        self._cur = db.cursor()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self._cur.close()

    def execute(self, sql, params=()):
        self._cur.execute(_to_sqlite(sql), [_param(p) for p in params])

    def _dicts(self, rows):
        cols = [c[0] for c in self._cur.description]
        return [dict(zip(cols, row)) for row in rows]

    def fetchall(self):
        return self._dicts(self._cur.fetchall())

    def fetchone(self):
        return self._dicts([self._cur.fetchone()])[0]


class _Connection:
    def __init__(self, db: sqlite3.Connection):
        self._db = db

    def cursor(self):
        return _Cursor(self._db)


@contextmanager
def _sqlite_neon():
    db = _build_db()
    names = ("neon_connection", "ensure_crm_data_imports_schema", "neon_column_exists")
    saved = {name: getattr(neon_utils, name) for name in names}

    @contextmanager
    def connection():
        yield _Connection(db)

    neon_utils.neon_connection = connection
    neon_utils.ensure_crm_data_imports_schema = lambda: None
    neon_utils.neon_column_exists = lambda *args, **kwargs: True
    try:
        yield
    finally:
        for name, value in saved.items():
            setattr(neon_utils, name, value)
        db.close()


def _export(latest_owner_only=False, start_date=None, end_date=None) -> list[dict]:
    with _sqlite_neon():
        return neon_utils.fetch_customer_export_rows(
            {}, None, start_date=start_date, end_date=end_date, latest_owner_only=latest_owner_only
        )


def _priority_by_id(rows) -> dict[str, str]:
    # Through the real export row builder, so normalization is included.
    return {str(row["id"]): customer_export_row(row)["ความสำคัญ"] for row in rows}


def _phone_key(row: dict, row_id) -> str:
    phone1, phone2 = row.get("phone1") or "", row.get("phone2") or ""
    if phone1 and phone2:
        return min(phone1, phone2)
    return phone1 or phone2 or str(row_id)


def _function_source(name: str) -> str:
    tree = ast.parse(NEON_SOURCE)
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
    return ast.get_source_segment(NEON_SOURCE, node)


def _squash(sql: str) -> str:
    return " ".join(sql.split())


# --- column shape -------------------------------------------------------------

def test_priority_header_sits_right_after_owner():
    assert CRM_EXPORT_HEADERS.count("ความสำคัญ") == 1
    owner_index = CRM_EXPORT_HEADERS.index("พนักงานดูแล")
    assert CRM_EXPORT_HEADERS[owner_index + 1] == "ความสำคัญ"


def test_latest_owner_mode_keeps_its_column_last():
    row = customer_export_row({"priority": "VIP", "latest_owner": "A"}, include_latest_owner=True)
    assert list(row) == [*CRM_EXPORT_HEADERS, CRM_LATEST_OWNER_HEADER]
    assert row["ความสำคัญ"] == "VIP"


def test_row_value_mapping_matches_the_followup_badge():
    assert customer_export_row({"priority": "Premium"})["ความสำคัญ"] == "Premium"
    assert customer_export_row({"priority": "urgent"})["ความสำคัญ"] == "Super VIP"
    assert customer_export_row({"priority": "Upsell โอนชำระ"})["ความสำคัญ"] == "โอนชำระ"
    assert customer_export_row({})["ความสำคัญ"] == "NEW"
    assert customer_export_row({"priority": None})["ความสำคัญ"] == "NEW"


def test_priority_comes_from_followups_not_import_raw_data():
    row = {"priority": None, "raw_data": {"ความสำคัญ": "VIP"}}
    assert customer_export_row(row)["ความสำคัญ"] == "NEW"


def test_xlsx_contains_priority_column():
    data = build_customer_export_xlsx([{"order_id": "690523", "priority": "Premium"}, {"order_id": "1"}])
    ws = openpyxl.load_workbook(BytesIO(data)).active
    header = [c.value for c in ws[1]]
    column = header.index("ความสำคัญ") + 1
    assert ws.cell(row=2, column=column).value == "Premium"
    assert ws.cell(row=3, column=column).value == "NEW"
    assert ws.max_row == 3


# --- current priority on every order (query executed on SQLite) ---------------

def test_every_order_of_a_super_vip_customer_reads_super_vip():
    got = _priority_by_id(_export())
    # Row 1 has its own stale "Premium" record; the customer is Super VIP now.
    assert [got["1"], got["2"], got["3"]] == ["Super VIP"] * 3


def test_every_order_of_a_vip_customer_reads_vip():
    got = _priority_by_id(_export())
    assert [got["5"], got["6"]] == ["VIP", "VIP"]


def test_legacy_value_on_the_current_record_is_mapped_on_every_order():
    got = _priority_by_id(_export())
    assert [got["7"], got["8"]] == ["Super VIP", "Super VIP"]


def test_customer_without_followup_record_reads_new_on_every_order():
    got = _priority_by_id(_export())
    assert [got["9"], got["10"]] == ["NEW", "NEW"]


def test_record_on_an_older_order_is_ignored_like_the_followup_page():
    # The follow-up page reads only the record keyed to the current row (14),
    # which has none, so it shows NEW -- and so must every order row here.
    got = _priority_by_id(_export())
    assert [got["13"], got["14"]] == ["NEW", "NEW"]


def test_phone_keyed_and_invalid_row_records_do_not_leak():
    got = _priority_by_id(_export())
    assert "4" not in got  # invalid row: not exported, never the current row
    assert got["3"] == "Super VIP"  # not "Dismiss" (phone-keyed) nor "Economy" (invalid row 4)


def test_customer_is_matched_across_phone1_and_phone2():
    got = _priority_by_id(_export())
    assert [got["11"], got["12"]] == ["Premium", "Premium"]


def test_customer_with_no_phone_is_its_own_customer():
    assert _priority_by_id(_export())["15"] == "Economy"


def test_same_day_tie_is_broken_by_numeric_id_like_the_followup_page():
    got = _priority_by_id(_export())
    assert [got["98"], got["100"]] == ["VIP", "VIP"]


def test_date_range_does_not_change_the_current_priority():
    july_first = date(2026, 7, 1)
    rows = _export(start_date=july_first, end_date=july_first)
    assert [str(r["id"]) for r in rows] == ["1"]
    assert _priority_by_id(rows) == {"1": "Super VIP"}
    latest = _export(latest_owner_only=True, start_date=july_first, end_date=july_first)
    assert _priority_by_id(latest) == {"1": "Super VIP"}


def test_export_matches_followup_page_for_every_customer():
    with _sqlite_neon():
        page_rows, total = neon_utils.fetch_followup_page({}, {"role": "ADMIN"}, page_size=100, page=1)
    page = {_phone_key(r, r["crm_data_import_id"]): r["priority"] for r in page_rows}
    assert len(page) == total
    for mode in (False, True):
        rows = _export(latest_owner_only=mode)
        assert rows
        for row in rows:
            key = _phone_key(row, row["id"])
            assert customer_export_row(row)["ความสำคัญ"] == page[key], (mode, row["id"], key)


# --- row count / duplication ---------------------------------------------------

def test_all_orders_mode_keeps_every_valid_row_exactly_once_in_order():
    rows = _export()
    ids = [str(r["id"]) for r in rows]
    assert len(ids) == len(set(ids)) == len(VALID_IDS)
    # Unchanged export order: created_at desc, order_date desc, id desc.
    by_order = sorted(
        (o for o in ORDERS if o[4] == "valid"),
        key=lambda o: (_timestamp(o[3]), o[3], o[0]),
        reverse=True,
    )
    assert ids == [str(o[0]) for o in by_order]


def test_latest_owner_mode_has_one_row_per_customer():
    rows = _export(latest_owner_only=True)
    keys = [_phone_key(r, r["id"]) for r in rows]
    assert len(keys) == len(set(keys))
    assert len(rows) == len({_phone_key({"phone1": o[1], "phone2": o[2]}, o[0]) for o in ORDERS if o[4] == "valid"})


def test_current_priority_is_one_row_per_customer_by_construction():
    sql = _squash(neon_utils._CUSTOMER_CURRENT_PRIORITY_SQL)
    assert "where cust_row.rn = 1" in sql
    assert "partition by v.phone_key" in sql
    # customer_key is the follow-up table's primary key, so this join adds no rows.
    assert "customer_key text primary key" in NEON_SOURCE
    assert "left join public.crm_lead_followups cust_fu on cust_fu.customer_key = concat('customer_id:', cust_row.id::text)" in sql


# --- reuse / parity with the follow-up page --------------------------------------

def test_current_row_rule_is_the_followup_pages_rule():
    page = _squash(_function_source("fetch_followup_page"))
    export_sql = _squash(neon_utils._CUSTOMER_CURRENT_PRIORITY_SQL)
    # Same ordering: the helper, rendered for the page's alias, is exactly the page's order.
    assert f"order by {neon_utils._current_customer_row_order('d')}" in page
    assert f"order by {neon_utils._current_customer_row_order('v')}" in export_sql
    # Same customer key and same valid-rows-only population.
    assert PHONE_KEY_SQL in page
    assert f"{PHONE_KEY_SQL} as phone_key from public.crm_data_imports where import_status = 'valid'" in export_sql
    # Same record: keyed to the current row, defaulting to NEW.
    assert f"on l.customer_key = {FOLLOWUP_JOIN_KEY}" in page
    assert "coalesce(l.priority, 'NEW') as priority" in page


def test_export_uses_current_priority_in_both_modes_and_no_per_order_join():
    source = _function_source("fetch_customer_export_rows")
    assert source.count("with current_priority as ({_CUSTOMER_CURRENT_PRIORITY_SQL})") == 2
    assert source.count("left join current_priority cp") == 2
    assert "crm_lead_followups" not in source
