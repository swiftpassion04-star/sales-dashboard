import ast
import inspect
import sys
from contextlib import contextmanager
from functools import cmp_to_key
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import neon_utils as neon
import ui.manual_order_ui as manual_ui


assert neon.should_enforce_duplicate_phone_lock("CRM_TEAM") is True
assert neon.should_enforce_duplicate_phone_lock(None) is False
assert neon.should_enforce_duplicate_phone_lock("UPSELL_TEAM") is False
assert neon.should_enforce_duplicate_phone_lock("OTHER_TEAM") is False


original_fetch_team = neon.fetch_current_user_team_code
original_find_duplicate = neon.find_duplicate_valid_order_by_phones
original_ensure_schema = neon.ensure_crm_data_imports_schema
original_column_exists = neon.neon_column_exists
original_table_exists = neon.neon_table_exists


def duplicate_row():
    return {
        "id": "10",
        "order_id": "ORDER-10",
        "owner": "Other Owner",
        "staff_code": "OTHER01",
        "current_team_code": "CRM_TEAM",
        "matched_phone": "0812345678",
    }


def same_owner_duplicate_row():
    return {
        "id": "11",
        "order_id": "ORDER-11",
        "owner": "CRM Owner",
        "staff_code": "CRM01",
        "current_team_code": "CRM_TEAM",
        "matched_phone": "0812345678",
    }


def upsell_duplicate_row():
    return {
        "id": "12",
        "order_id": "ORDER-12",
        "owner": "Upsell Owner",
        "staff_code": "UP01",
        "current_team_code": "UPSELL_TEAM",
        "matched_phone": "0812345678",
    }


def unassigned_duplicate_row():
    return {
        "id": "13",
        "order_id": "ORDER-13",
        "owner": "No Team Owner",
        "staff_code": "NO01",
        "current_team_code": None,
        "matched_phone": "0812345678",
    }


def same_staff_code_duplicate_row():
    return {
        "id": "14",
        "order_id": "ORDER-14",
        "owner": "Different Display Name",
        "staff_code": "CRM01",
        "current_team_code": "CRM_TEAM",
        "matched_phone": "0812345678",
    }


def same_owner_name_duplicate_row():
    return {
        "id": "15",
        "order_id": "ORDER-15",
        "owner": "  crm   owner ",
        "staff_code": "OTHER01",
        "current_team_code": "CRM_TEAM",
        "matched_phone": "0812345678",
    }


try:
    neon.fetch_current_user_team_code = lambda email: "CRM_TEAM"
    neon.find_duplicate_valid_order_by_phones = lambda phone1, phone2, owner=None, staff_code=None: duplicate_row()
    blocked = neon.check_crm_team_duplicate_phone_lock(
        "crm@example.com",
        "0812345678",
        "",
        "CRM Owner",
        "CRM01",
    )
    assert blocked["allowed"] is False
    assert blocked["team_code"] == "CRM_TEAM"

    neon.find_duplicate_valid_order_by_phones = lambda phone1, phone2, owner=None, staff_code=None: None
    allowed = neon.check_crm_team_duplicate_phone_lock(
        "crm@example.com",
        "0812345678",
        "",
        "CRM Owner",
        "CRM01",
    )
    assert allowed["allowed"] is True

    neon.fetch_current_user_team_code = lambda email: None
    neon.find_duplicate_valid_order_by_phones = lambda phone1, phone2, owner=None, staff_code=None: duplicate_row()
    assert neon.check_crm_team_duplicate_phone_lock("none@example.com", "0812345678", "", "CRM Owner", "CRM01")["allowed"] is True

    neon.fetch_current_user_team_code = lambda email: "UPSELL_TEAM"
    assert neon.check_crm_team_duplicate_phone_lock("upsell@example.com", "0812345678", "", "CRM Owner", "CRM01")["allowed"] is True

    neon.fetch_current_user_team_code = lambda email: "OTHER_TEAM"
    assert neon.check_crm_team_duplicate_phone_lock("other@example.com", "0812345678", "", "CRM Owner", "CRM01")["allowed"] is True

    def raise_lookup_error(email):
        raise RuntimeError("team lookup unavailable")

    neon.fetch_current_user_team_code = raise_lookup_error
    fail_open = neon.check_crm_team_duplicate_phone_lock("error@example.com", "0812345678", "", "CRM Owner", "CRM01")
    assert fail_open["allowed"] is True
    assert "ตรวจสอบทีมไม่สำเร็จ" in fail_open["warning"]

    neon.fetch_current_user_team_code = lambda email: "CRM_TEAM"
    neon.find_duplicate_valid_order_by_phones = lambda phone1, phone2, owner=None, staff_code=None: None
    same_owner_allowed = neon.check_crm_team_duplicate_phone_lock(
        "crm@example.com",
        "0812345678",
        "",
        "CRM Owner",
        "CRM01",
    )
    assert same_owner_allowed["allowed"] is True

    neon.find_duplicate_valid_order_by_phones = lambda phone1, phone2, owner=None, staff_code=None: duplicate_row()
    neon.ensure_crm_data_imports_schema = lambda: None
    neon.neon_column_exists = lambda table, column: (_ for _ in ()).throw(
        AssertionError("save-layer block should happen before column checks")
    )
    try:
        neon.upsert_manual_order_items(
            {
                "order_id": "ORDER-NEW",
                "customer_name": "Test Customer",
                "phone1": "0812345678",
                "phone2": "",
                "owner": "CRM Owner",
                "staff_code": "CRM01",
                "uploaded_by": "crm@example.com",
                "updated_by": "crm@example.com",
            },
            [{"sku": "SP001", "product_name": "Product", "qty": 1, "amount": 100}],
        )
    except ValueError as exc:
        assert "ทีม CRM ไม่สามารถเพิ่มคำสั่งซื้อซ้ำได้" in str(exc)
    else:
        raise AssertionError("CRM_TEAM duplicate phone should be blocked")
finally:
    neon.fetch_current_user_team_code = original_fetch_team
    neon.find_duplicate_valid_order_by_phones = original_find_duplicate
    neon.ensure_crm_data_imports_schema = original_ensure_schema
    neon.neon_column_exists = original_column_exists
    neon.neon_table_exists = original_table_exists


def parse_order_keys(order_sql):
    """(column, qualified, nulls_last) for each key of an ORDER BY clause."""
    keys = []
    for part in order_sql.split(","):
        part = part.strip()
        if not part:
            continue
        reference = part.split()[0]
        keys.append((reference.split(".")[-1], "." in reference, "nulls last" in part))
    return keys


def order_value(row, column, qualified):
    value = row.get(column)
    if column == "id" and value is not None:
        # crm_data_imports.id is bigint, but these queries also expose
        # "id::text as id". PostgreSQL binds a bare "id" in ORDER BY to that text
        # output column, so only a qualified reference sorts numerically.
        return int(value) if qualified else str(value)
    return value


def compare_order_keys(left, right, keys):
    for column, qualified, nulls_last in keys:
        left_value = order_value(left, column, qualified)
        right_value = order_value(right, column, qualified)
        if left_value == right_value:
            continue
        if left_value is None:
            return 1 if nulls_last else -1
        if right_value is None:
            return -1 if nulls_last else 1
        return -1 if left_value > right_value else 1
    return 0


class FakeCursor:
    def __init__(self, rows=None):
        self.statement = ""
        self.params = []
        self.rows = [duplicate_row()] if rows is None else list(rows)

    def ordered_rows(self):
        if "order by " not in self.statement:
            return list(self.rows)
        main_order = self.statement.rsplit(" limit ", 1)[0].rsplit("order by ", 1)[-1]
        keys = parse_order_keys(main_order)
        return sorted(
            self.rows,
            key=cmp_to_key(lambda left, right: compare_order_keys(left, right, keys)),
        )

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def execute(self, statement, params):
        self.statement = " ".join(statement.split()).lower()
        self.params = params

    def fetchone(self):
        rows = self.ordered_rows()
        return rows[0] if rows else None

    def fetchall(self):
        return self.ordered_rows()


class FakeConnection:
    def __init__(self, rows=None):
        self.cursor_instance = FakeCursor(rows)

    def cursor(self):
        return self.cursor_instance


fake_connection = FakeConnection()
original_connection = neon.neon_connection
original_ensure_schema = neon.ensure_crm_data_imports_schema


@contextmanager
def fake_neon_connection():
    yield fake_connection


@contextmanager
def fake_neon_connection_for(connection):
    yield connection


try:
    neon.ensure_crm_data_imports_schema = lambda: None
    neon.neon_connection = fake_neon_connection
    duplicate = neon.find_duplicate_valid_order_by_phones(
        "0812345678",
        "0912345678",
        "CRM Owner",
        "CRM01",
    )
finally:
    neon.neon_connection = original_connection
    neon.ensure_crm_data_imports_schema = original_ensure_schema

assert duplicate == duplicate_row()
assert "phone1 = any(%s) or phone2 = any(%s)" in fake_connection.cursor_instance.statement
assert "order by d.order_date desc nulls last, d.uploaded_at desc, d.id desc" in fake_connection.cursor_instance.statement
assert "public.crm_user_team_assignments" in fake_connection.cursor_instance.statement
assert "public.crm_user_roles" in fake_connection.cursor_instance.statement
assert "coalesce(staff_team.team_code, uploaded_team.team_code)" in fake_connection.cursor_instance.statement
assert "lower(btrim(d.uploaded_by))" in fake_connection.cursor_instance.statement
assert "effective_to is null" in fake_connection.cursor_instance.statement
assert fake_connection.cursor_instance.params == [
    ["0812345678", "0912345678"],
    ["0812345678", "0912345678"],
    ["0812345678", "0912345678"],
    ["0812345678", "0912345678"],
]


def row_with(row, **overrides):
    merged = dict(row)
    merged.update(overrides)
    return merged


def find_conflict_for_rows(rows, owner="CRM Owner", staff_code="CRM01"):
    connection = FakeConnection(rows)
    try:
        neon.ensure_crm_data_imports_schema = lambda: None
        neon.neon_connection = lambda: fake_neon_connection_for(connection)
        return neon.find_duplicate_valid_order_by_phones(
            "0812345678",
            "0912345678",
            owner,
            staff_code,
        )
    finally:
        neon.neon_connection = original_connection
        neon.ensure_crm_data_imports_schema = original_ensure_schema


# "Current owner" is whoever owns the newest order by order_date, i.e. exactly the
# row the customer directory shows. Older orders are history: they must never block
# a customer who has since been reassigned, no matter how recently they were edited.

# the reported bug: an old order edited later must not outrank the newest order
reassigned_history_row = row_with(
    duplicate_row(), order_date="2026-01-05", uploaded_at="2026-01-05", updated_at="2026-08-30"
)
reassigned_current_row = row_with(
    same_owner_duplicate_row(), order_date="2026-08-01", uploaded_at="2026-08-01", updated_at="2026-08-01"
)
assert find_conflict_for_rows([reassigned_history_row, reassigned_current_row]) is None

# newest order by order_date belongs to another CRM member -> blocked
crm_current_row = row_with(
    duplicate_row(), order_date="2026-08-01", uploaded_at="2026-08-01", updated_at="2026-01-01"
)
own_history_row = row_with(
    same_owner_duplicate_row(), order_date="2026-01-01", uploaded_at="2026-01-01", updated_at="2026-08-30"
)
assert find_conflict_for_rows([crm_current_row, own_history_row]) == crm_current_row

# newest order belongs to Upsell, CRM appears only in history -> allowed
crm_history_row = row_with(duplicate_row(), order_date="2026-01-01", updated_at="2026-08-30")
assert find_conflict_for_rows([row_with(upsell_duplicate_row(), order_date="2026-08-01"), crm_history_row]) is None

# newest order has no team at all, CRM appears only in history -> allowed
assert find_conflict_for_rows([row_with(unassigned_duplicate_row(), order_date="2026-08-01"), crm_history_row]) is None

# same staff_code on the current row -> allowed even when the display name differs
assert find_conflict_for_rows([row_with(same_staff_code_duplicate_row(), order_date="2026-08-01"), crm_history_row]) is None

# owner name matches after normalisation -> allowed even when staff_code differs
assert find_conflict_for_rows([row_with(same_owner_name_duplicate_row(), order_date="2026-08-01"), crm_history_row]) is None

# no rows at all -> allowed
assert find_conflict_for_rows([]) is None

# id is the tie-break, and it must sort as bigint. With a text sort "9" outranks
# "10", so the lock would pick the wrong row whenever a customer has two orders
# on the same day.
tie_break_own_newest_row = row_with(
    same_owner_duplicate_row(), id="10", order_date="2026-08-01", uploaded_at="2026-08-01"
)
tie_break_other_older_row = row_with(
    duplicate_row(), id="9", order_date="2026-08-01", uploaded_at="2026-08-01"
)
assert find_conflict_for_rows([tie_break_other_older_row, tie_break_own_newest_row]) is None

tie_break_other_newest_row = row_with(
    duplicate_row(), id="10", order_date="2026-08-01", uploaded_at="2026-08-01"
)
tie_break_own_older_row = row_with(
    same_owner_duplicate_row(), id="9", order_date="2026-08-01", uploaded_at="2026-08-01"
)
assert (
    find_conflict_for_rows([tie_break_own_older_row, tie_break_other_newest_row])
    == tie_break_other_newest_row
)


# The lock and the customer directory must read one shared ordering definition,
# and every reference must be table-qualified so "id" stays the bigint column.
assert neon._current_customer_row_order("d") == (
    "d.order_date desc nulls last, d.uploaded_at desc, d.id desc"
)
assert neon._current_customer_row_order("keyed") == (
    "keyed.order_date desc nulls last, keyed.uploaded_at desc, keyed.id desc"
)
assert neon._current_customer_row_order("ranked") == (
    "ranked.order_date desc nulls last, ranked.uploaded_at desc, ranked.id desc"
)
assert not hasattr(neon, "_CURRENT_CUSTOMER_ROW_ORDER")

duplicate_lock_source = " ".join(inspect.getsource(neon.find_duplicate_valid_order_by_phones).split())
customer_page_source = " ".join(inspect.getsource(neon.fetch_customer_page).split())
assert '{_current_customer_row_order("d")}' in duplicate_lock_source
assert '{_current_customer_row_order("keyed")}' in customer_page_source
assert '{_current_customer_row_order("ranked")}' in customer_page_source
assert "order by updated_at desc" not in duplicate_lock_source
assert "cur.fetchone()" in duplicate_lock_source
assert "fetchall()" not in duplicate_lock_source
assert "for row in rows" not in duplicate_lock_source

# ...and the SQL actually sent must carry that ordering plus a single-row limit.
limit_probe_connection = FakeConnection([row_with(duplicate_row(), order_date="2026-08-01")])
try:
    neon.ensure_crm_data_imports_schema = lambda: None
    neon.neon_connection = lambda: fake_neon_connection_for(limit_probe_connection)
    neon.find_duplicate_valid_order_by_phones("0812345678", "0912345678", "CRM Owner", "CRM01")
finally:
    neon.neon_connection = original_connection
    neon.ensure_crm_data_imports_schema = original_ensure_schema

lock_statement = limit_probe_connection.cursor_instance.statement
assert lock_statement.endswith(
    "order by d.order_date desc nulls last, d.uploaded_at desc, d.id desc limit 1"
)
# no unqualified reference may survive: those would bind to "id::text as id"
assert "order by order_date" not in lock_statement
assert ", id desc" not in lock_statement
assert "uploaded_at desc nulls last" not in lock_statement

customer_page_connection = FakeConnection([{"total": 0, "id": "1", "order_date": "2026-08-01"}])
try:
    neon.ensure_crm_data_imports_schema = lambda: None
    neon.neon_connection = lambda: fake_neon_connection_for(customer_page_connection)
    neon.fetch_customer_page({}, 10, 1, user=None, enforce_user_scope=False)
finally:
    neon.neon_connection = original_connection
    neon.ensure_crm_data_imports_schema = original_ensure_schema

customer_page_statement = customer_page_connection.cursor_instance.statement
assert (
    "order by keyed.order_date desc nulls last, keyed.uploaded_at desc, keyed.id desc"
    in customer_page_statement
)
assert (
    "order by ranked.order_date desc nulls last, ranked.uploaded_at desc, ranked.id desc"
    in customer_page_statement
)
assert "uploaded_at desc nulls last" not in customer_page_statement
assert "order by order_date" not in customer_page_statement
assert ", id desc" not in customer_page_statement


# All three entry points must inherit the current-owner rule from the shared helper.
# 1. manual order page
manual_allowed_connection = FakeConnection([reassigned_history_row, reassigned_current_row])
manual_blocked_connection = FakeConnection([crm_current_row, own_history_row])
try:
    neon.ensure_crm_data_imports_schema = lambda: None
    neon.neon_connection = lambda: fake_neon_connection_for(manual_allowed_connection)
    manual_allowed = manual_ui.find_manual_order_owner_conflict(
        "0812345678", "0912345678", {"staff_code": "CRM01"}, "CRM Owner", "CRM01"
    )
    neon.neon_connection = lambda: fake_neon_connection_for(manual_blocked_connection)
    manual_blocked = manual_ui.find_manual_order_owner_conflict(
        "0812345678", "0912345678", {"staff_code": "CRM01"}, "CRM Owner", "CRM01"
    )
finally:
    neon.neon_connection = original_connection
    neon.ensure_crm_data_imports_schema = original_ensure_schema

assert manual_allowed == {}
assert manual_blocked == crm_current_row

# 2. follow-up popup. pages/followup.py calls main() at import time, so the real
# function is compiled out of the page source instead of importing the module.
followup_page_source = Path("pages/followup.py").read_text(encoding="utf-8")
popup_conflict_node = next(
    node
    for node in ast.parse(followup_page_source).body
    if isinstance(node, ast.FunctionDef) and node.name == "find_popup_order_owner_conflict"
)
popup_namespace = {"neon": neon, "clean": neon.clean}
exec(
    compile(ast.Module(body=[popup_conflict_node], type_ignores=[]), "pages/followup.py", "exec"),
    popup_namespace,
)
find_popup_order_owner_conflict = popup_namespace["find_popup_order_owner_conflict"]

popup_allowed_connection = FakeConnection([reassigned_history_row, reassigned_current_row])
popup_blocked_connection = FakeConnection([crm_current_row, own_history_row])
try:
    neon.fetch_current_user_team_code = lambda email: "CRM_TEAM"
    neon.ensure_crm_data_imports_schema = lambda: None
    neon.neon_connection = lambda: fake_neon_connection_for(popup_allowed_connection)
    popup_allowed = find_popup_order_owner_conflict(
        "0812345678", "0912345678", {"email": "crm@example.com"}, "CRM Owner", "CRM01"
    )
    neon.neon_connection = lambda: fake_neon_connection_for(popup_blocked_connection)
    popup_blocked = find_popup_order_owner_conflict(
        "0812345678", "0912345678", {"email": "crm@example.com"}, "CRM Owner", "CRM01"
    )
finally:
    neon.fetch_current_user_team_code = original_fetch_team
    neon.neon_connection = original_connection
    neon.ensure_crm_data_imports_schema = original_ensure_schema

assert popup_allowed == {}
assert popup_blocked == crm_current_row


# 3. central save layer: a reassigned customer must get past the lock and reach the
# write path, proven by the column probe that runs immediately after the lock.
class ReachedSaveLayer(Exception):
    pass


def reached_save_layer(_table, _column):
    raise ReachedSaveLayer()


save_layer_connection = FakeConnection([reassigned_history_row, reassigned_current_row])
try:
    neon.fetch_current_user_team_code = lambda email: "CRM_TEAM"
    neon.ensure_crm_data_imports_schema = lambda: None
    neon.neon_connection = lambda: fake_neon_connection_for(save_layer_connection)
    neon.neon_column_exists = reached_save_layer
    try:
        neon.upsert_manual_order_items(
            {
                "order_id": "ORDER-NEW",
                "customer_name": "Test Customer",
                "phone1": "0812345678",
                "phone2": "",
                "owner": "CRM Owner",
                "staff_code": "CRM01",
                "uploaded_by": "crm@example.com",
                "updated_by": "crm@example.com",
            },
            [{"sku": "SP001", "product_name": "Product", "qty": 1, "amount": 100}],
        )
    except ReachedSaveLayer:
        pass
    else:
        raise AssertionError("a reassigned customer must reach the save layer")
finally:
    neon.fetch_current_user_team_code = original_fetch_team
    neon.neon_column_exists = original_column_exists
    neon.neon_connection = original_connection
    neon.ensure_crm_data_imports_schema = original_ensure_schema



source = Path("neon_utils.py").read_text(encoding="utf-8")
insert_start = source.index("def insert_import_records")
manual_start = source.index("def upsert_manual_order")
assert "check_crm_team_duplicate_phone_lock" not in source[insert_start:manual_start]

print("crm team duplicate phone lock safety OK")
