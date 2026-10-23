"""The customer directory lists one entry per customer per side.

A customer is the phone group, not a single phone_key: phone_key is
least(phone1, phone2), so an order that adds a lower-numbered backup phone
lands under a different key and the same person was listed twice.

The grouping CTEs are executed against in-memory SQLite (Postgres syntax
translated), so these are real results, not SQL-text assertions -- but it is
SQLite, not Neon.

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


# (id, phone1, phone2, import_status)
ORDERS = [
    # One customer: the older order has one phone, the newer adds a LOWER
    # backup phone, so the two orders key differently. This is the reported
    # case -- two rows for one person, both on the same team.
    (1, "0896525947", "", "valid"),
    (2, "0896525947", "0874746460", "valid"),
    # Plain customer, one key, several orders.
    (3, "0811111111", "", "valid"),
    (4, "0811111111", "", "valid"),
    # Chain: ...41 shares ...42 with the middle order, which shares ...43.
    # ...41 and ...43 never appear together, so only the transitive closure
    # puts all three under one customer.
    (5, "0930000041", "0930000042", "valid"),
    (6, "0930000042", "0930000043", "valid"),
    (7, "0930000043", "", "valid"),
    # Two unrelated customers that must stay apart.
    (8, "0820000001", "", "valid"),
    (9, "0820000002", "", "valid"),
    # An invalid row must not link anything.
    (10, "0830000001", "0830000002", "invalid"),
    (11, "0830000001", "", "valid"),
    (12, "0830000002", "", "valid"),
    # No phone at all: the row is its own customer.
    (13, "", "", "valid"),
]


def _to_sqlite(sql: str) -> str:
    sql = sql.replace("public.", "")
    sql = re.sub(r"([A-Za-z_][\w.]*)::(\w+)", r"cast(\1 as \2)", sql)
    sql = re.sub(r"\bleast\(", "min(", sql)
    return sql


def _groups() -> dict[str, str]:
    """phone_key -> group_key, straight from the shared CTEs."""
    db = sqlite3.connect(":memory:")
    db.execute("create table crm_data_imports (id integer primary key, phone1 text, phone2 text, import_status text)")
    db.executemany("insert into crm_data_imports (id, phone1, phone2, import_status) values (?,?,?,?)", ORDERS)
    sql = _to_sqlite(
        f"with recursive {neon._CUSTOMER_PHONE_GROUP_CTES} select phone_key, group_key from customer_groups"
    )
    rows = db.execute(sql).fetchall()
    db.close()
    return {phone_key: group_key for phone_key, group_key in rows}


GROUPS = _groups()
DIRECTORY_SOURCE = " ".join(inspect.getsource(neon.fetch_customer_page).split())


def _same_customer(*phone_keys: str) -> bool:
    return len({GROUPS[key] for key in phone_keys}) == 1


# --- the reported case ----------------------------------------------------------

def test_an_order_that_adds_a_lower_backup_phone_stays_the_same_customer():
    # order 1 keys on the phone itself, order 2 on the lower backup number
    assert GROUPS["0896525947"] and GROUPS["0874746460"]
    assert _same_customer("0896525947", "0874746460")


def test_every_key_of_one_customer_shares_a_group_key():
    assert _same_customer("0930000041", "0930000042", "0930000043")


def test_unrelated_customers_keep_their_own_groups():
    assert not _same_customer("0820000001", "0820000002")
    assert not _same_customer("0896525947", "0811111111")


def test_an_invalid_row_does_not_link_two_customers():
    # row 10 carries both numbers but is invalid, so ...01 and ...02 stay apart
    assert not _same_customer("0830000001", "0830000002")


def test_a_customer_without_a_phone_is_their_own_group():
    assert GROUPS["13"] == "13"


def test_group_mapping_covers_every_key_exactly_once():
    valid_keys = set()
    for row_id, phone1, phone2, status in ORDERS:
        if status != "valid":
            continue
        phones = [p for p in (phone1, phone2) if p]
        valid_keys.add(min(phones) if len(phones) == 2 else (phones[0] if phones else str(row_id)))
    assert set(GROUPS) == valid_keys
    assert len(GROUPS) == len(valid_keys)


def test_group_key_is_stable_and_is_one_of_the_member_keys():
    members = {}
    for key, group in GROUPS.items():
        members.setdefault(group, set()).add(key)
    for group, keys in members.items():
        assert group in keys, (group, keys)
        assert group == min(keys)


# --- how the directory uses it ---------------------------------------------------

def test_directory_partitions_by_customer_and_side():
    assert "partition by customer_groups.group_key, keyed.team_side" in DIRECTORY_SOURCE
    assert "join customer_groups on customer_groups.phone_key = keyed.phone_key" in DIRECTORY_SOURCE
    assert "partition by phone_key, team_side" not in DIRECTORY_SOURCE


def test_directory_counts_entries_the_same_way_it_lists_them():
    assert "select distinct customer_groups.group_key, keyed.team_side" in DIRECTORY_SOURCE
    assert "count(*) as total" in DIRECTORY_SOURCE


def test_directory_and_priority_export_share_one_grouping_definition():
    assert "{_CUSTOMER_PHONE_GROUP_CTES}" in DIRECTORY_SOURCE
    priority = " ".join(neon._CUSTOMER_CURRENT_PRIORITY_SQL.split())
    group = " ".join(neon._CUSTOMER_PHONE_GROUP_CTES.split())
    assert group in priority


def test_grouping_runs_over_all_valid_rows_not_the_filtered_page():
    # The CTEs read crm_data_imports directly; if they were filtered by the
    # page's where clause, hiding the linking order would split a customer.
    group = " ".join(neon._CUSTOMER_PHONE_GROUP_CTES.split())
    assert "from public.crm_data_imports where import_status = 'valid'" in group
    assert "%s" not in group


def test_both_sides_still_get_their_own_entry():
    assert "keyed.team_side" in DIRECTORY_SOURCE
    assert "page.team_side," in DIRECTORY_SOURCE


# --- the follow-up status lookup runs on the page, not the whole directory -------

def test_the_page_is_cut_before_the_followup_status_is_looked_up():
    # That lookup matches an id OR either phone column, so no index can serve
    # it; running it before the limit meant one scan of crm_lead_followups per
    # customer in the whole directory (~25k) instead of per row shown.
    page_cte = DIRECTORY_SOURCE.index("page as (")
    followup_cte = DIRECTORY_SOURCE.index("followup as (")
    lookup = DIRECTORY_SOURCE.index("public.crm_lead_followups l")
    assert page_cte < followup_cte < lookup
    assert DIRECTORY_SOURCE.index("limit %s offset %s") < followup_cte


def test_the_followup_lookup_reads_only_page_rows():
    followup_part = DIRECTORY_SOURCE.split("followup as (", 1)[1].split("select {select_cols}", 1)[0]
    assert "from page" in followup_part
    assert "page.id" in followup_part and "page.phone1" in followup_part
    assert "ranked" not in followup_part


def test_the_page_order_is_applied_again_on_the_outer_select():
    # A CTE does not guarantee row order, so the final select repeats it.
    assert '{_current_customer_row_order("ranked")}' in DIRECTORY_SOURCE
    assert '{_current_customer_row_order("page")}' in DIRECTORY_SOURCE


def test_the_followup_join_cannot_duplicate_a_page_row():
    assert "page.id as followup_page_id" in DIRECTORY_SOURCE
    assert "left join followup on followup.followup_page_id = page.id" in DIRECTORY_SOURCE
    assert "coalesce(followup.followup_status, '0') as followup_status" in DIRECTORY_SOURCE
