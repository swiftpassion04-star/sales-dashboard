"""Deactivating a user releases their customers.

The owner reads as empty and the duplicate-phone lock stops holding the
customer, so whoever adds the next order takes over. Nothing is written:
staff_code stays on the row, so the sales reports keep counting that
person's past orders and reactivating the user brings their customers back.

The owner-activity rule is executed against in-memory SQLite (Postgres
syntax translated), so these are real results -- but it is SQLite, not Neon.

No pytest in this environment -- discovered via the repo's stdlib test_*
runner, same as every other tests/test_*.py file here.
"""

import inspect
import re
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import neon_utils as neon


# (id, owner, staff_code, uploaded_by)
ORDERS = [
    (1, "สายฝน (SAIFON)", "SAIFON", "saifon@example.com"),   # active user
    (2, "อุ๊ (AU)", "AU", "au@example.com"),                   # deactivated user
    (3, "อุ๊ (AU)", "au", "someone@example.com"),              # staff_code case differs
    (4, "อุ๊ (AU)", " AU ", ""),                               # padded staff_code
    (5, "ไม่มีรหัส", "", "au@example.com"),                    # no staff_code -> uploader decides
    (6, "ไม่มีรหัส", "", "saifon@example.com"),
    (7, "คนนอกระบบ", "GHOST", "ghost@example.com"),            # not a user at all
    (8, "คนนอกระบบ", "", ""),                                  # nothing to resolve
    # staff_code of an active user, uploaded by the deactivated one:
    # the staff_code verdict wins, so this keeps its owner.
    (9, "สายฝน (SAIFON)", "SAIFON", "au@example.com"),
]
USERS = [
    ("saifon@example.com", "SAIFON", 1),
    ("au@example.com", "AU", 0),
    ("other@example.com", "TAEW", 1),
]


def _to_sqlite(sql: str) -> str:
    sql = sql.replace("public.", "")
    sql = re.sub(r"([A-Za-z_][\w.]*)::(\w+)", r"cast(\1 as \2)", sql)
    sql = re.sub(r"\bbtrim\(", "trim(", sql)
    sql = re.sub(r"\bbool_or\(", "max(", sql)  # SQLite has no bool_or
    return sql


def _owners() -> dict[int, str]:
    """row id -> owner as the app should display it."""
    db = sqlite3.connect(":memory:")
    db.execute("create table crm_data_imports (id integer primary key, owner text, staff_code text, uploaded_by text)")
    db.executemany("insert into crm_data_imports values (?,?,?,?)", ORDERS)
    db.execute("create table crm_user_roles (email text primary key, staff_code text, is_active int)")
    db.executemany("insert into crm_user_roles values (?,?,?)", USERS)
    sql = _to_sqlite(
        f"select d.id, {neon._active_owner_sql('d.owner')} as shown "
        f"from crm_data_imports d {neon._owner_activity_joins('d')}"
    )
    rows = db.execute(sql).fetchall()
    db.close()
    return {row_id: shown for row_id, shown in rows}


SHOWN = _owners()
LOCK_SOURCE = " ".join(inspect.getsource(neon.find_duplicate_valid_order_by_phones).split())
DIRECTORY_SOURCE = " ".join(inspect.getsource(neon.fetch_customer_page).split())
EXPORT_SOURCE = " ".join(inspect.getsource(neon.fetch_customer_export_rows).split())
DETAIL_SOURCE = " ".join(inspect.getsource(neon.fetch_customer_360_base).split())


# --- who still has an owner -----------------------------------------------------

def test_an_active_users_customers_keep_their_owner():
    assert SHOWN[1] == "สายฝน (SAIFON)"
    assert SHOWN[6] == "ไม่มีรหัส"


def test_a_deactivated_users_customers_show_no_owner():
    assert SHOWN[2] == ""


def test_staff_code_is_matched_regardless_of_case_or_padding():
    assert SHOWN[3] == ""
    assert SHOWN[4] == ""


def test_the_uploader_decides_only_when_the_row_has_no_staff_code():
    assert SHOWN[5] == ""                      # uploaded by the deactivated user
    assert SHOWN[9] == "สายฝน (SAIFON)"        # active staff_code wins over that uploader


def test_an_owner_who_is_not_a_user_keeps_their_customers():
    # Imported names and staff without a login must not be wiped out.
    assert SHOWN[7] == "คนนอกระบบ"
    assert SHOWN[8] == "คนนอกระบบ"


def test_nothing_is_released_while_every_user_is_active():
    db = sqlite3.connect(":memory:")
    db.execute("create table crm_data_imports (id integer primary key, owner text, staff_code text, uploaded_by text)")
    db.executemany("insert into crm_data_imports values (?,?,?,?)", ORDERS)
    db.execute("create table crm_user_roles (email text primary key, staff_code text, is_active int)")
    db.executemany("insert into crm_user_roles values (?,?,?)", [(e, s, 1) for e, s, _ in USERS])
    sql = _to_sqlite(
        f"select count(*) from crm_data_imports d {neon._owner_activity_joins('d')} "
        f"where {neon._OWNER_IS_INACTIVE_SQL}"
    )
    released = db.execute(sql).fetchone()[0]
    db.close()
    assert released == 0


# --- what that means in each place ----------------------------------------------

def test_the_lock_lets_the_next_crm_member_take_over():
    assert "not ({_OWNER_IS_INACTIVE_SQL})" in LOCK_SOURCE
    assert '{_owner_activity_joins("d")}' in LOCK_SOURCE


def test_the_customer_directory_shows_the_released_owner_as_empty():
    assert '{_active_owner_sql("d.owner")} as active_owner' in DIRECTORY_SOURCE
    assert '{_owner_activity_joins("d")}' in DIRECTORY_SOURCE
    assert "active_owner as sales_staff" in neon.customer_select_columns()


def test_customer_360_shows_it_too():
    assert '{_active_owner_sql("d.owner")} as active_owner' in DETAIL_SOURCE
    assert '{_owner_activity_joins("d")}' in DETAIL_SOURCE


def test_the_excel_export_agrees_with_the_web_pages():
    assert EXPORT_SOURCE.count('{_active_owner_sql("d.owner")} as owner') == 2  # both sheets
    assert '{_active_owner_sql("d.owner")} as latest_owner' in EXPORT_SOURCE
    assert EXPORT_SOURCE.count('{_owner_activity_joins("d")}') == 2


def test_sales_attribution_is_untouched():
    # staff_code is never blanked, so team sales and the daily matrix keep
    # counting a deactivated person's past orders.
    assert '_active_owner_sql("d.staff_code")' not in DIRECTORY_SOURCE + EXPORT_SOURCE + LOCK_SOURCE
    # the column is still selected as-is everywhere it was before
    assert "staff_code," in neon.customer_select_columns()
    assert "staff_code" in DIRECTORY_SOURCE
    rule = " ".join(neon._OWNER_IS_INACTIVE_SQL.split())
    assert "update" not in rule and "delete" not in rule


def test_releasing_is_read_only_and_reversible():
    # No write statement anywhere in the rule or its joins.
    joins = " ".join(neon._owner_activity_joins("d").split()).lower()
    for keyword in ("insert", "update", "delete", "alter", "create", "drop"):
        assert keyword not in joins
