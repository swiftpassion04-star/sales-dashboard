import sys
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import neon_utils as neon


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
        "matched_phone": "0812345678",
    }


def same_owner_duplicate_row():
    return {
        "id": "11",
        "order_id": "ORDER-11",
        "owner": "CRM Owner",
        "staff_code": "CRM01",
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


class FakeCursor:
    def __init__(self):
        self.statement = ""
        self.params = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def execute(self, statement, params):
        self.statement = " ".join(statement.split()).lower()
        self.params = params

    def fetchone(self):
        return duplicate_row()

    def fetchall(self):
        return [same_owner_duplicate_row(), duplicate_row()]


class FakeConnection:
    def __init__(self):
        self.cursor_instance = FakeCursor()

    def cursor(self):
        return self.cursor_instance


fake_connection = FakeConnection()
original_connection = neon.neon_connection
original_ensure_schema = neon.ensure_crm_data_imports_schema


@contextmanager
def fake_neon_connection():
    yield fake_connection


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

assert duplicate["matched_phone"] == "0812345678"
assert "phone1 = any(%s) or phone2 = any(%s)" in fake_connection.cursor_instance.statement
assert fake_connection.cursor_instance.params == [
    ["0812345678", "0912345678"],
    ["0812345678", "0912345678"],
    ["0812345678", "0912345678"],
    ["0812345678", "0912345678"],
]


source = Path("neon_utils.py").read_text(encoding="utf-8")
insert_start = source.index("def insert_import_records")
manual_start = source.index("def upsert_manual_order")
assert "check_crm_team_duplicate_phone_lock" not in source[insert_start:manual_start]

print("crm team duplicate phone lock safety OK")
