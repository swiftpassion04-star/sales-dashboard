"""DB-free tests for the "ความสำคัญ" column in the customer .xlsx export.

The column is a customer-level value: the highest priority level found in the
customer's whole follow-up history (Super VIP > VIP > Premium > Economy, else
NEW), shown on every one of their order rows in both export modes.

The query tests run the real fetch_customer_export_rows against an in-memory
SQLite database. Only the connection is swapped, and the SQL goes through a
small Postgres -> SQLite translation (schema prefix, `::` casts, least -> min,
btrim -> trim). That exercises the real joins and aggregation, but it is
SQLite, not Neon.

No pytest in this environment -- discovered via the repo's stdlib test_*
runner, same as every other tests/test_*.py file here.
"""

import ast
import re
import sqlite3
import sys
from contextlib import contextmanager
from datetime import date, datetime, timedelta
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


# --- fixture data -----------------------------------------------------------
# One customer per phone. Order dates rise with the id, so the last id of each
# customer is their newest order. (id, phone1, phone2, import_status)
CUSTOMERS = {
    "was_vip_new_order_has_no_followup": [(1, "0810000001"), (2, "0810000001")],
    "was_premium_then_new": [(3, "0810000002"), (4, "0810000002")],
    "economy_and_premium": [(5, "0810000003"), (6, "0810000003")],
    "premium_and_vip": [(7, "0810000004"), (8, "0810000004")],
    "vip_and_super_vip": [(9, "0810000005"), (10, "0810000005")],
    "urgent_and_new": [(11, "0810000006"), (12, "0810000006")],
    "only_new": [(13, "0810000007"), (14, "0810000007")],
    "no_followup_at_all": [(15, "0810000008"), (16, "0810000008")],
    "super_vip_new_and_none": [(17, "0810000009"), (18, "0810000009"), (19, "0810000009")],
    "premium_vip_super_vip": [(20, "0810000010"), (21, "0810000010"), (22, "0810000010")],
    "economy_and_vip": [(23, "0810000011"), (24, "0810000011")],
    "only_non_level_values": [(25, "0810000012"), (26, "0810000012"), (27, "0810000012")],
    "vip_then_dismiss": [(28, "0810000013"), (29, "0810000013")],
    "phone_keyed_record_only": [(30, "0810000014"), (31, "0810000014")],
    "legacy_high_and_low": [(36, "0810000017"), (37, "0810000017")],
}
EXTRA_ORDERS = [
    # One customer across phone1/phone2: both rows key to least() = 0820000001.
    (32, "0820000002", "0820000001", "valid"),
    (33, "0820000001", "", "valid"),
    # Valid order without follow-up + an INVALID row carrying Super VIP.
    (34, "0810000016", "", "valid"),
    (35, "0810000016", "", "invalid"),
    # No phone: the row is its own customer (phone_key = id).
    (38, "", "", "valid"),
]
ORDERS = sorted(
    [(row_id, phone, "", "valid") for rows in CUSTOMERS.values() for row_id, phone in rows] + EXTRA_ORDERS
)
FOLLOWUPS = {
    "customer_id:1": "VIP",
    "customer_id:3": "Premium",
    "customer_id:4": "NEW",
    "customer_id:5": "Premium",
    "customer_id:6": "Economy",
    "customer_id:7": "VIP",
    "customer_id:8": "Premium",
    "customer_id:9": "Super VIP",
    "customer_id:10": "VIP",
    "customer_id:11": "urgent",
    "customer_id:12": "NEW",
    "customer_id:13": "NEW",
    "customer_id:14": "NEW",
    "customer_id:17": "Super VIP",
    "customer_id:18": "NEW",
    "customer_id:20": "Super VIP",
    "customer_id:21": "Premium",
    "customer_id:22": "VIP",
    "customer_id:23": "VIP",
    "customer_id:24": "Economy",
    "customer_id:25": "Upsell",
    "customer_id:26": "โอนชำระ",
    "customer_id:27": "Dismiss",
    "customer_id:28": "VIP",
    "customer_id:29": "Dismiss",
    "0810000014": "VIP",  # keyed by the bare phone_key (customers page / merge)
    "customer_id:32": "Premium",
    "customer_id:35": "Super VIP",  # invalid row: not part of the history
    "customer_id:36": "high",
    "customer_id:37": "low",
    "customer_id:38": "Economy",
    "38": "VIP",  # no-phone customer keyed by the bare row id
}
VALID_IDS = [str(o[0]) for o in ORDERS if o[3] == "valid"]


def _order_date(row_id: int) -> str:
    return (date(2026, 7, 1) + timedelta(days=row_id)).isoformat()


def _timestamp(row_id: int) -> str:
    return f"{_order_date(row_id)} 03:00:00+00:00"


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
    db.execute("create table crm_lead_followups (customer_key text primary key, priority text)")
    for row_id, phone1, phone2, status in ORDERS:
        stamp = _timestamp(row_id)
        db.execute(
            "insert into crm_data_imports (id, order_date, order_id, sku, phone1, phone2, owner,"
            " import_status, uploaded_at, created_at, updated_at) values (?,?,?,?,?,?,?,?,?,?,?)",
            (row_id, _order_date(row_id), f"ORD{row_id}", f"SKU{row_id}", phone1, phone2, f"owner{row_id}", status, stamp, stamp, stamp),
        )
    for key, priority in FOLLOWUPS.items():
        db.execute("insert into crm_lead_followups (customer_key, priority) values (?, ?)", (key, priority))
    return db


def _to_sqlite(sql: str) -> str:
    sql = sql.replace("public.", "")
    sql = re.sub(r"([A-Za-z_][\w.]*)::(\w+)", r"cast(\1 as \2)", sql)
    sql = re.sub(r"\bleast\(", "min(", sql)
    sql = re.sub(r"\bbtrim\(", "trim(", sql)
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

    def fetchall(self):
        cols = [c[0] for c in self._cur.description]
        return [dict(zip(cols, row)) for row in self._cur.fetchall()]


class _Connection:
    def __init__(self, db: sqlite3.Connection):
        self._db = db

    def cursor(self):
        return _Cursor(self._db)


@contextmanager
def _sqlite_neon(**overrides):
    db = _build_db()
    patches = {
        "neon_connection": None,
        "ensure_crm_data_imports_schema": lambda: None,
        "neon_column_exists": lambda *args, **kwargs: True,
        **overrides,
    }
    saved = {name: getattr(neon_utils, name) for name in patches}

    @contextmanager
    def connection():
        yield _Connection(db)

    patches["neon_connection"] = connection
    for name, value in patches.items():
        setattr(neon_utils, name, value)
    try:
        yield
    finally:
        for name, value in saved.items():
            setattr(neon_utils, name, value)
        db.close()


def _export(latest_owner_only=False, start_date=None, end_date=None, **overrides) -> list[dict]:
    with _sqlite_neon(**overrides):
        return neon_utils.fetch_customer_export_rows(
            {}, None, start_date=start_date, end_date=end_date, latest_owner_only=latest_owner_only
        )


def _export_without_priority(latest_owner_only=False) -> list[dict]:
    # The same export with an empty priority lookup: the rows the query would
    # return if the priority join did not exist.
    empty = "select cast(null as text) as phone_key, cast(null as text) as priority where 1 = 0"
    return _export(latest_owner_only, _CUSTOMER_CURRENT_PRIORITY_SQL=empty)


def _phone_key(row: dict, row_id) -> str:
    phone1, phone2 = row.get("phone1") or "", row.get("phone2") or ""
    if phone1 and phone2:
        return min(phone1, phone2)
    return phone1 or phone2 or str(row_id)


def _priority(row: dict) -> str:
    # Through the real export row builder, so normalization is included.
    return customer_export_row(row)["ความสำคัญ"]


def _key_of(row_id: int) -> str:
    order = next(o for o in ORDERS if o[0] == row_id)
    return _phone_key({"phone1": order[1], "phone2": order[2]}, row_id)


def _assert_customer(row_ids: list[int], expected: str):
    all_orders = {str(r["id"]): _priority(r) for r in _export()}
    assert [all_orders[str(i)] for i in row_ids] == [expected] * len(row_ids), (row_ids, all_orders)
    latest = {_phone_key(r, r["id"]): _priority(r) for r in _export(latest_owner_only=True)}
    assert latest[_key_of(row_ids[0])] == expected, (row_ids, latest)


def _ids(name: str) -> list[int]:
    return [row_id for row_id, _ in CUSTOMERS[name]]


def _function_source(name: str) -> str:
    tree = ast.parse(NEON_SOURCE)
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
    return ast.get_source_segment(NEON_SOURCE, node)


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


# --- ranking ------------------------------------------------------------------

def test_ranking_is_super_vip_vip_premium_economy_then_new():
    assert neon_utils.CUSTOMER_PRIORITY_LEVELS == ("Super VIP", "VIP", "Premium", "Economy")
    level_sql = neon_utils._customer_priority_level_sql("r")
    assert level_sql == (
        "case r when 4 then 'Super VIP' when 3 then 'VIP' "
        "when 2 then 'Premium' when 1 then 'Economy' else 'NEW' end"
    )


def test_every_spelling_is_ranked_by_the_level_the_followup_page_shows():
    rank_sql = neon_utils._customer_priority_rank_sql("p")
    expected = {"Super VIP": 4, "VIP": 3, "Premium": 2, "Economy": 1}
    vocabulary = {*neon_utils.FOLLOWUP_PRIORITY_OPTIONS, *neon_utils.LEGACY_FOLLOWUP_PRIORITY_MAP}
    for raw in vocabulary:
        level = neon_utils.normalize_followup_priority(raw)
        if level in expected:
            assert f"when '{raw}' then {expected[level]}" in rank_sql, raw
        else:
            assert f"when '{raw}' " not in rank_sql, raw
    # Legacy spellings map before comparing.
    assert "when 'urgent' then 4" in rank_sql
    assert rank_sql.endswith("else 0 end")


def test_sql_has_no_percent_sign_psycopg_would_read_as_a_placeholder():
    assert "%" not in neon_utils._CUSTOMER_CURRENT_PRIORITY_SQL


# --- the requested cases (both sheets, query executed on SQLite) ---------------

def test_was_vip_and_new_order_without_followup_reads_vip():
    _assert_customer(_ids("was_vip_new_order_has_no_followup"), "VIP")


def test_was_premium_then_new_reads_premium():
    _assert_customer(_ids("was_premium_then_new"), "Premium")


def test_economy_and_premium_reads_premium():
    _assert_customer(_ids("economy_and_premium"), "Premium")


def test_premium_and_vip_reads_vip():
    _assert_customer(_ids("premium_and_vip"), "VIP")


def test_vip_and_super_vip_reads_super_vip():
    _assert_customer(_ids("vip_and_super_vip"), "Super VIP")


def test_urgent_and_new_reads_super_vip():
    _assert_customer(_ids("urgent_and_new"), "Super VIP")


def test_only_new_reads_new():
    _assert_customer(_ids("only_new"), "NEW")


def test_no_followup_at_all_reads_new():
    _assert_customer(_ids("no_followup_at_all"), "NEW")


def test_super_vip_then_new_then_no_followup_reads_super_vip_on_all_three():
    _assert_customer(_ids("super_vip_new_and_none"), "Super VIP")


def test_premium_vip_and_super_vip_reads_super_vip():
    _assert_customer(_ids("premium_vip_super_vip"), "Super VIP")


def test_economy_and_vip_reads_vip():
    _assert_customer(_ids("economy_and_vip"), "VIP")


def test_legacy_high_and_low_rank_as_vip_and_economy():
    _assert_customer(_ids("legacy_high_and_low"), "VIP")


def test_upsell_transfer_and_dismiss_are_not_levels():
    _assert_customer(_ids("only_non_level_values"), "NEW")
    _assert_customer(_ids("vip_then_dismiss"), "VIP")


def test_record_keyed_by_bare_phone_counts_as_history():
    _assert_customer(_ids("phone_keyed_record_only"), "VIP")


def test_record_keyed_by_bare_row_id_counts_for_a_customer_without_phone():
    _assert_customer([38], "VIP")


def test_customer_is_matched_across_phone1_and_phone2():
    _assert_customer([32, 33], "Premium")


def test_invalid_row_is_not_part_of_the_history():
    _assert_customer([34], "NEW")
    assert "35" not in {str(r["id"]) for r in _export()}


def test_date_range_does_not_change_the_customer_priority():
    # Only order 19 (no follow-up of its own) is in range; the customer is Super VIP.
    day = date.fromisoformat(_order_date(19))
    rows = _export(start_date=day, end_date=day)
    assert [str(r["id"]) for r in rows] == ["19"]
    assert _priority(rows[0]) == "Super VIP"
    latest = _export(latest_owner_only=True, start_date=day, end_date=day)
    assert [_priority(r) for r in latest] == ["Super VIP"]


def test_every_order_of_a_customer_shows_the_same_value_in_both_sheets():
    by_customer: dict[str, set] = {}
    for row in _export():
        by_customer.setdefault(_phone_key(row, row["id"]), set()).add(_priority(row))
    assert all(len(values) == 1 for values in by_customer.values()), by_customer
    latest = {_phone_key(r, r["id"]): _priority(r) for r in _export(latest_owner_only=True)}
    assert {key: values.pop() for key, values in by_customer.items()} == latest


# --- row count / duplication ---------------------------------------------------

def test_all_orders_rows_are_unchanged_by_the_priority_join():
    rows = _export()
    baseline = _export_without_priority()
    assert len(rows) == len(baseline) == len(VALID_IDS)
    ids = [str(r["id"]) for r in rows]
    assert len(ids) == len(set(ids))
    # Same rows, same order, same values -- only the priority column differs.
    strip = lambda r: {k: v for k, v in r.items() if k != "priority"}
    assert [strip(r) for r in rows] == [strip(r) for r in baseline]


def test_latest_owner_rows_are_unchanged_by_the_priority_join():
    rows = _export(latest_owner_only=True)
    baseline = _export_without_priority(latest_owner_only=True)
    strip = lambda r: {k: v for k, v in r.items() if k != "priority"}
    assert [strip(r) for r in rows] == [strip(r) for r in baseline]
    keys = [_phone_key(r, r["id"]) for r in rows]
    assert len(keys) == len(set(keys))
    assert len(rows) == len({_key_of(int(i)) for i in VALID_IDS})


def test_priority_lookup_returns_one_row_per_customer():
    with _sqlite_neon():
        with neon_utils.neon_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(neon_utils._CUSTOMER_CURRENT_PRIORITY_SQL)
                lookup = cur.fetchall()
    keys = [row["phone_key"] for row in lookup]
    assert len(keys) == len(set(keys))
    assert " group by phone_key" in " ".join(neon_utils._CUSTOMER_CURRENT_PRIORITY_SQL.split())


def test_export_uses_the_customer_lookup_in_both_modes_only():
    source = _function_source("fetch_customer_export_rows")
    assert source.count("with current_priority as ({_CUSTOMER_CURRENT_PRIORITY_SQL})") == 2
    assert source.count("left join current_priority cp") == 2
    assert "crm_lead_followups" not in source
    # Priority is not picked from the newest order any more.
    assert "row_number" not in neon_utils._CUSTOMER_CURRENT_PRIORITY_SQL
