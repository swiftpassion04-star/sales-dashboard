import inspect
import json
from pathlib import Path
from copy import deepcopy
from datetime import date, datetime, time
from decimal import Decimal
from uuid import UUID, uuid4

import sys
from contextlib import contextmanager

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import neon_utils as neon
import permissions


REPO_ROOT = Path(__file__).resolve().parents[1]
CUSTOMERS_SOURCE = (REPO_ROOT / "pages" / "customers.py").read_text(encoding="utf-8")
NEON_SOURCE = (REPO_ROOT / "neon_utils.py").read_text(encoding="utf-8")
PERMISSIONS_SOURCE = (REPO_ROOT / "permissions.py").read_text(encoding="utf-8")


assert permissions.can_manage_customer_records({"role": "EDITOR"})
assert not permissions.can_manage_customer_records({"role": "ADMIN"})
assert not permissions.can_manage_customer_records({"role": "STAFF"})
assert not permissions.can_manage_customer_records({"role": "พนักงาน"})
assert not permissions.can_manage_customer_records({"role": "USER"})
assert not permissions.can_manage_customer_records({})

assert "def can_manage_customer_records(user: dict | None) -> bool:" in PERMISSIONS_SOURCE
assert "return user_role(user) == ROLE_EDITOR" in inspect.getsource(permissions.can_manage_customer_records)
assert "ORDER_DELETE_ROLES" in PERMISSIONS_SOURCE


assert "can_manage_customer_records" in CUSTOMERS_SOURCE
assert "can_manage_records = can_manage_customer_records(user)" in CUSTOMERS_SOURCE
assert "render_customer_editor_record_actions(row, user)" in CUSTOMERS_SOURCE
assert 'customer_editor_action_key("edit_phone", anchor_id)' in CUSTOMERS_SOURCE
assert 'customer_editor_action_key("delete_order", anchor_id)' in CUSTOMERS_SOURCE
assert 'return f"{name}_{clean(anchor_id)}"' in CUSTOMERS_SOURCE
assert 'merge_key = f"phone_merge_{source_anchor_id}_{target_anchor_id}"' in CUSTOMERS_SOURCE
assert "_request_id" in CUSTOMERS_SOURCE
assert "_in_progress" in CUSTOMERS_SOURCE
assert "str(uuid4())" in CUSTOMERS_SOURCE
assert "neon.preview_customer_order_delete(anchor_id, user)" in CUSTOMERS_SOURCE
assert "neon.delete_customer_order_records(" in CUSTOMERS_SOURCE
assert "neon.preview_customer_phone_update(anchor_id, phone1, phone2, user)" in CUSTOMERS_SOURCE
assert "neon.update_customer_phones(" in CUSTOMERS_SOURCE
assert "neon.merge_customer_phone_collision(" in CUSTOMERS_SOURCE
assert "clear_customer_editor_action_caches()" in CUSTOMERS_SOURCE
assert "st.cache_data.clear()" not in CUSTOMERS_SOURCE


for cache_function in (
    "fetch_customer_page",
    "fetch_customer_export_rows",
    "fetch_filter_options",
    "fetch_followup_filter_options",
    "fetch_dashboard_kpis",
    "fetch_sales_report",
    "fetch_sales_report_rows",
    "fetch_sales_report_owner_options",
    "fetch_team_sales_summary",
    "fetch_team_top_products",
):
    assert cache_function in CUSTOMERS_SOURCE


assert "CRM_DATA_AUDIT_LOG_DDL" in NEON_SOURCE
for column in (
    "request_id text not null unique",
    "action_type text not null",
    "entity_type text not null",
    "entity_key text not null",
    "actor_email text",
    "actor_role text",
    "actor_name text",
    "source_page text",
    "before_snapshot jsonb",
    "after_snapshot jsonb",
    "metadata jsonb",
    "created_at timestamptz",
):
    assert column in NEON_SOURCE

for action_type in ("DELETE_ORDER", "UPDATE_CUSTOMER_PHONE", "MERGE_CUSTOMER_PHONE"):
    assert action_type in NEON_SOURCE

assert "def ensure_crm_data_audit_log_schema() -> bool:" in NEON_SOURCE
assert "def _insert_crm_audit_log(" in NEON_SOURCE
assert "def _to_json_safe(" in NEON_SOURCE
jsonb_source = NEON_SOURCE.split("def _jsonb(value):", 1)[1].split(
    "def _assert_editor_customer_record_action",
    1,
)[0]
assert "safe_value = _to_json_safe(value)" in jsonb_source
assert "Jsonb(safe_value)" in jsonb_source
assert "Jsonb(value)" not in jsonb_source
assert "allow_nan=False" in jsonb_source
audit_insert_source = NEON_SOURCE.split("def _insert_crm_audit_log(", 1)[1].split(
    "def _safe_record_dict",
    1,
)[0]
assert "on conflict (request_id) do nothing" in audit_insert_source
assert "returning id" in audit_insert_source
assert "conn.commit()" not in audit_insert_source
assert "conn.rollback()" not in audit_insert_source


assert "def _assert_editor_customer_record_action" in NEON_SOURCE
assert "can_manage_customer_records" in NEON_SOURCE
assert "can_delete_order" not in NEON_SOURCE

delete_source = NEON_SOURCE.split("def delete_customer_order_records", 1)[1].split(
    "def _fetch_customer_rows_by_phones",
    1,
)[0]
assert "_assert_editor_customer_record_action(user)" in delete_source
assert "ensure_crm_data_audit_log_schema()" in delete_source
assert 'action_type="DELETE_ORDER"' in delete_source
assert "delete from public.crm_data_imports" in delete_source
assert "where id::text = any(%s)" in delete_source
assert "delete from public.crm_data_imports\n                    where order_id" not in delete_source
assert "delete from public.crm_orders" not in delete_source
assert "delete from public.crm_lead_followups" not in delete_source
assert "followups_deleted" in delete_source

preview_delete_source = NEON_SOURCE.split("def preview_customer_order_delete", 1)[1].split(
    "def delete_customer_order_records",
    1,
)[0]
assert "_assert_editor_customer_record_action(user)" in preview_delete_source
assert "row_count" in preview_delete_source
assert "followup_count" in preview_delete_source
assert "record_ids" in preview_delete_source

logical_order_source = NEON_SOURCE.split("def _logical_order_where_from_anchor", 1)[1].split(
    "def _fetch_customer_anchor_row",
    1,
)[0]
assert "Cannot safely identify imported logical order group" in logical_order_source
assert "order_id = %s" in logical_order_source
assert "import_batch_id::text = %s" in logical_order_source
assert "source_file_name" in logical_order_source
assert "sheet_name" in logical_order_source

phone_preview_source = NEON_SOURCE.split("def preview_customer_phone_update", 1)[1].split(
    "def update_customer_phones",
    1,
)[0]
assert "_assert_editor_customer_record_action(user)" in phone_preview_source
assert "_validate_customer_phone_inputs" in phone_preview_source
assert '"collision": bool(target_rows)' in phone_preview_source
assert '"target_anchor_id"' in phone_preview_source

phone_update_source = NEON_SOURCE.split("def update_customer_phones", 1)[1].split(
    "PRIORITY_PRECEDENCE",
    1,
)[0]
assert "_assert_editor_customer_record_action(user)" in phone_update_source
assert "Phone collision detected; merge confirmation is required" in phone_update_source
assert 'action_type="UPDATE_CUSTOMER_PHONE"' in phone_update_source
assert "update public.crm_data_imports" in phone_update_source
assert "update public.crm_lead_followups" in phone_update_source

merge_source = NEON_SOURCE.split("def merge_customer_phone_collision", 1)[1].split(
    "def assign_owner_to_order_record",
    1,
)[0]
assert "_assert_editor_customer_record_action(user)" in merge_source
assert 'action_type="MERGE_CUSTOMER_PHONE"' in merge_source
assert "lock=True" in merge_source
assert "for update" in NEON_SOURCE.split("def _fetch_customer_rows_by_phones", 1)[1].split(
    "def _fetch_followups_by_phones",
    1,
)[0]
assert "for update" in NEON_SOURCE.split("def _fetch_followups_by_phones", 1)[1].split(
    "def _validate_customer_phone_inputs",
    1,
)[0]
assert "update public.crm_data_imports" in merge_source
assert "update public.crm_lead_followups" in merge_source
assert "delete from public.crm_lead_followups" not in merge_source
assert "survivor" in merge_source
assert "owner_source" in merge_source
assert "url_source" in merge_source
assert "ข้อมูลเดิมฝั่ง Target:" in NEON_SOURCE
assert "ข้อมูลจากฝั่งที่นำมารวม:" in NEON_SOURCE
assert "Super VIP" in NEON_SOURCE
assert "VIP" in NEON_SOURCE
assert "Premium" in NEON_SOURCE
assert "Economy" in NEON_SOURCE
assert "NEW" in NEON_SOURCE


upsert_manual_source = NEON_SOURCE.split("def upsert_manual_order_items", 1)[1].split(
    "def fetch_existing_order_ids",
    1,
)[0]
assert "crm_data_audit_log" not in upsert_manual_source
assert "DELETE_ORDER" not in upsert_manual_source
assert "MERGE_CUSTOMER_PHONE" not in upsert_manual_source

upsert_followup_source = NEON_SOURCE.split("def upsert_lead_followup", 1)[1].split(
    "def _normalized_text_sql",
    1,
)[0]
assert "crm_data_audit_log" not in upsert_followup_source
assert "DELETE_ORDER" not in upsert_followup_source
assert "MERGE_CUSTOMER_PHONE" not in upsert_followup_source

assert "fetch_customer_page(" in NEON_SOURCE
assert "def fetch_customer_page" in NEON_SOURCE
assert "def upsert_manual_order_items" in NEON_SOURCE
assert "def upsert_lead_followup" in NEON_SOURCE


class StringOnlyObject:
    def __str__(self):
        return "string-only-object"

    def __eq__(self, other):
        return isinstance(other, StringOnlyObject)


payload_id = uuid4()
item_uuid = uuid4()
tuple_uuid = uuid4()
set_uuid = uuid4()
frozen_uuid = uuid4()
nested_key_uuid = uuid4()
nested_value_uuid = uuid4()
payload = {
    "id": payload_id,
    "created_at": datetime(2026, 7, 21, 9, 30, 15),
    "date": date(2026, 7, 21),
    "time": time(9, 30, 15),
    "amount": Decimal("123.45"),
    "items": [
        {"record_id": item_uuid},
        (tuple_uuid, Decimal("0.10")),
    ],
    "values": {set_uuid},
    "frozen": frozenset({frozen_uuid}),
    "nested": {
        nested_key_uuid: {
            "ids": [nested_value_uuid],
        },
    },
    "unknown": StringOnlyObject(),
}
original_payload = deepcopy(payload)
safe_payload = neon._to_json_safe(payload)
json.dumps(safe_payload, ensure_ascii=False, allow_nan=False)
assert payload == original_payload
assert safe_payload["id"] == str(payload_id)
assert safe_payload["created_at"] == "2026-07-21T09:30:15"
assert safe_payload["date"] == "2026-07-21"
assert safe_payload["time"] == "09:30:15"
assert safe_payload["amount"] == "123.45"
assert safe_payload["items"][0]["record_id"] == str(item_uuid)
assert safe_payload["items"][1] == [str(tuple_uuid), "0.10"]
assert safe_payload["values"] == [str(set_uuid)]
assert safe_payload["frozen"] == [str(frozen_uuid)]
assert str(nested_key_uuid) in safe_payload["nested"]
assert safe_payload["nested"][str(nested_key_uuid)]["ids"] == [str(nested_value_uuid)]
assert safe_payload["unknown"] == "string-only-object"
assert all(isinstance(key, str) for key in safe_payload["nested"].keys())


def unwrap_json_payload(value):
    if hasattr(value, "obj"):
        return value.obj
    if isinstance(value, str) and value[:1] in {"{", "["}:
        return json.loads(value)
    return value


def assert_no_raw_uuid(value):
    value = unwrap_json_payload(value)
    if isinstance(value, dict):
        for key, item in value.items():
            assert isinstance(key, str)
            assert not isinstance(key, UUID)
            assert_no_raw_uuid(item)
        return
    if isinstance(value, list):
        for item in value:
            assert_no_raw_uuid(item)
        return
    assert not isinstance(value, UUID)
    json.dumps(value, ensure_ascii=False, allow_nan=False)


nested_uuid_payload = {"outer": [{"record_id": uuid4(), "amount": Decimal("1.25")}]}
jsonb_value = neon._jsonb(nested_uuid_payload)
assert_no_raw_uuid(jsonb_value)
original_jsonb = neon.Jsonb
try:
    neon.Jsonb = None
    fallback_jsonb_value = neon._jsonb(nested_uuid_payload)
    assert isinstance(fallback_jsonb_value, str)
    assert_no_raw_uuid(fallback_jsonb_value)
finally:
    neon.Jsonb = original_jsonb

try:
    neon._jsonb({"bad": float("nan")})
    raise AssertionError("_jsonb should reject NaN")
except ValueError:
    pass


class FakeCursor:
    def __init__(
        self,
        *,
        rows_by_kind=None,
        audit_conflict: bool = False,
        fail_on_audit_insert: bool = False,
        fail_on_business_write: str | None = None,
    ):
        self.rows_by_kind = {key: list(value) for key, value in (rows_by_kind or {}).items()}
        self.audit_conflict = audit_conflict
        self.fail_on_audit_insert = fail_on_audit_insert
        self.fail_on_business_write = fail_on_business_write
        self.statement = ""
        self.statements: list[str] = []
        self.params_log: list[list] = []
        self.current_rows = []
        self.rowcount = 0
        self.audit_inserts = 0
        self.business_writes = 0
        self.data_import_updates = 0
        self.followup_updates = 0
        self.data_import_deletes = 0
        self.order_item_deletes = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def _pop_rows(self, key):
        values = self.rows_by_kind.get(key) or []
        if values and isinstance(values[0], list):
            return values.pop(0)
        return values

    def execute(self, statement, params=None):
        normalized = " ".join(str(statement).split()).lower()
        self.statement = normalized
        self.statements.append(normalized)
        self.params_log.append(list(params or []))
        self.current_rows = []
        self.rowcount = 0

        if "insert into public.crm_data_audit_log" in normalized:
            if self.fail_on_audit_insert:
                raise RuntimeError("injected audit insert failure")
            if self.audit_conflict:
                self.current_rows = []
                return
            self.audit_inserts += 1
            self.current_rows = [{"id": self.audit_inserts}]
            return

        if "select * from public.crm_data_imports" in normalized and "where id::text = %s" in normalized:
            self.current_rows = self._pop_rows("anchors")
            return

        if "select * from public.crm_data_imports" in normalized and "phone1 = any" in normalized:
            self.current_rows = self._pop_rows("customer_rows")
            return

        if "select * from public.crm_data_imports" in normalized and "order by id asc" in normalized:
            self.current_rows = self._pop_rows("order_rows")
            return

        if "select count(*)::int as count from public.crm_lead_followups" in normalized:
            self.current_rows = [{"count": 0}]
            return

        if "select * from public.crm_lead_followups" in normalized:
            self.current_rows = self._pop_rows("followup_rows")
            return

        if "delete from public.crm_order_items" in normalized:
            self.business_writes += 1
            self.order_item_deletes += 1
            self.rowcount = 2
            return

        if "delete from public.crm_data_imports" in normalized:
            if "order_id" in normalized:
                raise AssertionError("delete_customer_order_records must delete crm_data_imports by id list only")
            if self.fail_on_business_write == "crm_data_imports":
                raise RuntimeError("injected crm_data_imports failure")
            self.business_writes += 1
            self.data_import_deletes += 1
            self.rowcount = 2
            return

        if "update public.crm_data_imports" in normalized:
            if self.fail_on_business_write == "crm_data_imports":
                raise RuntimeError("injected crm_data_imports failure")
            self.business_writes += 1
            self.data_import_updates += 1
            self.rowcount = 2
            return

        if "update public.crm_lead_followups" in normalized:
            if self.fail_on_business_write == "crm_lead_followups":
                raise RuntimeError("injected crm_lead_followups failure")
            self.business_writes += 1
            self.followup_updates += 1
            self.rowcount = 2
            return

    def fetchone(self):
        if not self.current_rows:
            return None
        return self.current_rows.pop(0)

    def fetchall(self):
        rows = list(self.current_rows)
        self.current_rows = []
        return rows


class FakeConnection:
    def __init__(self, cursor: FakeCursor):
        self.cursor_instance = cursor
        self.commit_count = 0
        self.rollback_count = 0

    def cursor(self):
        return self.cursor_instance

    def commit(self):
        self.commit_count += 1

    def rollback(self):
        self.rollback_count += 1


def install_fake_neon(fake_connection: FakeConnection):
    originals = {
        "ensure_crm_data_imports_schema": neon.ensure_crm_data_imports_schema,
        "ensure_crm_data_audit_log_schema": neon.ensure_crm_data_audit_log_schema,
        "neon_connection": neon.neon_connection,
        "neon_table_exists": neon.neon_table_exists,
        "neon_column_exists": neon.neon_column_exists,
    }

    @contextmanager
    def fake_neon_connection():
        yield fake_connection

    neon.ensure_crm_data_imports_schema = lambda: True
    neon.ensure_crm_data_audit_log_schema = lambda: True
    neon.neon_table_exists = lambda table_name: table_name == "crm_order_items"
    neon.neon_column_exists = lambda table_name, column_name: (
        table_name == "crm_order_items" and column_name == "crm_data_import_id"
    )
    neon.neon_connection = fake_neon_connection
    return originals


def restore_fake_neon(originals):
    for name, value in originals.items():
        setattr(neon, name, value)


def make_anchor(record_id="1", phone1="0811111111", phone2="", owner="Target Owner", staff_code="T01", **extra):
    row = {
        "id": record_id,
        "import_batch_id": uuid4(),
        "order_id": f"ORD-{record_id}",
        "phone1": phone1,
        "phone2": phone2,
        "owner": owner,
        "staff_code": staff_code,
        "url": f"https://example.com/{record_id}",
        "source_type": "manual",
        "source_file_name": "manual_order",
        "raw_data": {"source": "manual_order", "snapshot_uuid": uuid4(), "amount": Decimal("9.99")},
        "uploaded_at": datetime(2026, 7, 21, 8, 0, 0),
        "order_date": date(2026, 7, 21),
        "total_amount": Decimal("99.95"),
    }
    row.update(extra)
    return row


def make_followup(
    row_id,
    *,
    lead_status,
    followup_status,
    updated_at,
    created_at,
    phone1="0811111111",
    **extra,
):
    row = {
        "id": row_id,
        "customer_key": f"customer:{row_id}",
        "crm_data_import_id": row_id,
        "phone1": phone1,
        "phone2": "",
        "lead_status": lead_status,
        "followup_status": followup_status,
        "follow_up_status": followup_status,
        "priority": "NEW",
        "next_followup_date": "2026-07-30",
        "followup_note": f"note {row_id}",
        "updated_at": updated_at,
        "created_at": created_at,
        "snapshot_uuid": uuid4(),
    }
    row.update(extra)
    return row


def audit_payloads(cursor: FakeCursor):
    return [
        (params[8], params[9], params[10])
        for statement, params in zip(cursor.statements, cursor.params_log)
        if "insert into public.crm_data_audit_log" in statement
    ]


def assert_audit_payloads_json_safe(cursor: FakeCursor):
    payloads = audit_payloads(cursor)
    assert payloads
    for before_snapshot, after_snapshot, metadata in payloads:
        assert_no_raw_uuid(before_snapshot)
        assert_no_raw_uuid(after_snapshot)
        assert_no_raw_uuid(metadata)


def run_with_fake_connection(function, fake_connection, *args, **kwargs):
    originals = install_fake_neon(fake_connection)
    try:
        return function(*args, **kwargs)
    finally:
        restore_fake_neon(originals)


for helper in (
    neon.delete_customer_order_records,
    neon.update_customer_phones,
    neon.merge_customer_phone_collision,
):
    for blocked_user in ({"role": "STAFF"}, {"role": "ADMIN"}, None):
        fake = FakeConnection(FakeCursor(rows_by_kind={}))
        try:
            helper("1", blocked_user, "REQ") if helper is neon.delete_customer_order_records else (
                helper("1", "0812222222", "", blocked_user, "REQ")
                if helper is neon.update_customer_phones
                else helper("1", "2", "0812222222", "", blocked_user, "REQ")
            )
            raise AssertionError("blocked role should not reach write path")
        except PermissionError:
            assert fake.cursor_instance.business_writes == 0
            assert fake.commit_count == 0


delete_rows = [[make_anchor("1")], [make_anchor("1"), make_anchor("2")]]
delete_cursor = FakeCursor(rows_by_kind={"anchors": [delete_rows[0]], "order_rows": [delete_rows[1]]})
delete_conn = FakeConnection(delete_cursor)
delete_result = run_with_fake_connection(
    neon.delete_customer_order_records,
    delete_conn,
    "1",
    {"role": "EDITOR", "email": "editor@example.com"},
    "REQ-DELETE-1",
)
assert delete_result["duplicate_request"] is False
assert delete_conn.commit_count == 1
assert delete_conn.rollback_count == 0
assert delete_cursor.audit_inserts == 1
assert_audit_payloads_json_safe(delete_cursor)
assert delete_cursor.order_item_deletes == 1
assert delete_cursor.data_import_deletes == 1
assert delete_cursor.business_writes == 2
assert any("delete from public.crm_order_items" in statement for statement in delete_cursor.statements)
assert any("where crm_data_import_id::text = any(%s)" in statement for statement in delete_cursor.statements)
assert any("delete from public.crm_data_imports" in statement for statement in delete_cursor.statements)
assert any("where id::text = any(%s)" in statement for statement in delete_cursor.statements)
assert not any("delete from public.crm_lead_followups" in statement for statement in delete_cursor.statements)

conflict_cursor = FakeCursor(
    rows_by_kind={"anchors": [[make_anchor("1")]], "order_rows": [[make_anchor("1")]]},
    audit_conflict=True,
)
conflict_conn = FakeConnection(conflict_cursor)
conflict_result = run_with_fake_connection(
    neon.delete_customer_order_records,
    conflict_conn,
    "1",
    {"role": "EDITOR", "email": "editor@example.com"},
    "REQ-DELETE-1",
)
assert conflict_result["duplicate_request"] is True
assert conflict_cursor.business_writes == 0
assert conflict_conn.commit_count == 0

rollback_cursor = FakeCursor(
    rows_by_kind={"anchors": [[make_anchor("1")]], "order_rows": [[make_anchor("1")]]},
    fail_on_business_write="crm_data_imports",
)
rollback_conn = FakeConnection(rollback_cursor)
try:
    run_with_fake_connection(
        neon.delete_customer_order_records,
        rollback_conn,
        "1",
        {"role": "EDITOR", "email": "editor@example.com"},
        "REQ-DELETE-ROLLBACK",
    )
    raise AssertionError("injected delete failure should rollback")
except RuntimeError:
    assert rollback_conn.commit_count == 0
    assert rollback_conn.rollback_count == 1


phone_collision_cursor = FakeCursor(
    rows_by_kind={
        "anchors": [[make_anchor("1", phone1="0811111111")]],
        "customer_rows": [
            [make_anchor("1", phone1="0811111111")],
            [make_anchor("9", phone1="0899999999")],
        ],
    }
)
phone_collision_conn = FakeConnection(phone_collision_cursor)
try:
    run_with_fake_connection(
        neon.update_customer_phones,
        phone_collision_conn,
        "1",
        "0899999999",
        "",
        {"role": "EDITOR", "email": "editor@example.com"},
        "REQ-PHONE-COLLISION",
    )
    raise AssertionError("phone collision should require merge confirmation")
except ValueError:
    assert phone_collision_cursor.data_import_updates == 0
    assert phone_collision_cursor.followup_updates == 0
    assert phone_collision_conn.commit_count == 0
    assert phone_collision_conn.rollback_count == 1

phone_success_cursor = FakeCursor(
    rows_by_kind={
        "anchors": [[make_anchor("1", phone1="0811111111")]],
        "customer_rows": [[make_anchor("1", phone1="0811111111")], []],
        "followup_rows": [[make_followup("1", lead_status="new", followup_status="none", updated_at="2026-07-20", created_at="2026-07-19")]],
    }
)
phone_success_conn = FakeConnection(phone_success_cursor)
phone_result = run_with_fake_connection(
    neon.update_customer_phones,
    phone_success_conn,
    "1",
    "0822222222",
    "",
    {"role": "EDITOR", "email": "editor@example.com"},
    "REQ-PHONE-SUCCESS",
)
assert phone_result["duplicate_request"] is False
assert phone_success_cursor.audit_inserts == 1
assert_audit_payloads_json_safe(phone_success_cursor)
assert phone_success_cursor.data_import_updates == 1
assert phone_success_cursor.followup_updates == 1
assert phone_success_conn.commit_count == 1

audit_failure_cursor = FakeCursor(
    rows_by_kind={
        "anchors": [[make_anchor("1", phone1="0811111111")]],
        "customer_rows": [[make_anchor("1", phone1="0811111111")], []],
        "followup_rows": [[make_followup("1", lead_status="new", followup_status="none", updated_at="2026-07-20", created_at="2026-07-19")]],
    },
    fail_on_audit_insert=True,
)
audit_failure_conn = FakeConnection(audit_failure_cursor)
audit_failure_success = True
try:
    run_with_fake_connection(
        neon.update_customer_phones,
        audit_failure_conn,
        "1",
        "0822222222",
        "",
        {"role": "EDITOR", "email": "editor@example.com"},
        "REQ-AUDIT-FAILURE",
    )
except RuntimeError:
    audit_failure_success = False
assert audit_failure_success is False
assert audit_failure_cursor.business_writes == 0
assert audit_failure_conn.commit_count == 0
assert audit_failure_conn.rollback_count == 1


target_followup = make_followup(
    "10",
    lead_status="สนใจ",
    followup_status="รอติดตาม",
    updated_at="2026-07-20T10:00:00Z",
    created_at="2026-07-20T09:00:00Z",
    phone1="0899999999",
)
source_followup = make_followup(
    "20",
    lead_status="ปิดการขาย",
    followup_status="สำเร็จ",
    updated_at="2026-07-21T10:00:00Z",
    created_at="2026-07-21T09:00:00Z",
    phone1="0811111111",
)
merge_cursor = FakeCursor(
    rows_by_kind={
        "anchors": [[make_anchor("1", phone1="0811111111", owner="Source Owner", staff_code="S01")], [make_anchor("9", phone1="0899999999", owner="Target Owner", staff_code="T01")]],
        "customer_rows": [
            [make_anchor("1", phone1="0811111111", owner="Source Owner", staff_code="S01")],
            [make_anchor("9", phone1="0899999999", owner="Target Owner", staff_code="T01")],
        ],
        "followup_rows": [[source_followup], [target_followup]],
    }
)
merge_conn = FakeConnection(merge_cursor)
merge_result = run_with_fake_connection(
    neon.merge_customer_phone_collision,
    merge_conn,
    "1",
    "9",
    "0899999999",
    "",
    {"role": "EDITOR", "email": "editor@example.com"},
    "REQ-MERGE-STATUS",
)
assert merge_result["duplicate_request"] is False
assert merge_cursor.audit_inserts == 1
assert merge_cursor.data_import_updates == 1
assert merge_cursor.followup_updates == 1
assert merge_conn.commit_count == 1
assert merge_conn.rollback_count == 0
assert_audit_payloads_json_safe(merge_cursor)
followup_update_params = [
    params
    for statement, params in zip(merge_cursor.statements, merge_cursor.params_log)
    if "update public.crm_lead_followups" in statement
][0]
assert followup_update_params[5] == "ปิดการขาย"
assert followup_update_params[6] == "สำเร็จ"
assert any("lead_status = coalesce(nullif(%s, ''), lead_status)" in statement for statement in merge_cursor.statements)
assert any("followup_status = coalesce(nullif(%s, ''), followup_status)" in statement for statement in merge_cursor.statements)

assert neon._resolve_latest_followup_statuses(
    [
        make_followup("1", lead_status="old", followup_status="old-follow", updated_at="2026-07-21T10:00:00Z", created_at="2026-07-21T09:00:00Z"),
        make_followup("2", lead_status="newer-created", followup_status="newer-follow", updated_at="2026-07-21T10:00:00Z", created_at="2026-07-21T09:30:00Z"),
    ]
) == {"lead_status": "newer-created", "followup_status": "newer-follow"}
assert neon._resolve_latest_followup_statuses(
    [
        make_followup("1", lead_status="low-id", followup_status="low-follow", updated_at="2026-07-21T10:00:00Z", created_at="2026-07-21T09:00:00Z"),
        make_followup("9", lead_status="high-id", followup_status="high-follow", updated_at="2026-07-21T10:00:00Z", created_at="2026-07-21T09:00:00Z"),
    ]
) == {"lead_status": "high-id", "followup_status": "high-follow"}
assert neon._resolve_latest_followup_statuses(
    [
        make_followup("9", lead_status="", followup_status=None, updated_at="2026-07-21T10:00:00Z", created_at="2026-07-21T09:00:00Z"),
        make_followup("1", lead_status="fallback", followup_status="fallback-follow", updated_at="2026-07-20T10:00:00Z", created_at="2026-07-20T09:00:00Z"),
    ]
) == {"lead_status": "fallback", "followup_status": "fallback-follow"}

merge_rollback_cursor = FakeCursor(
    rows_by_kind={
        "anchors": [[make_anchor("1", phone1="0811111111")], [make_anchor("9", phone1="0899999999")]],
        "customer_rows": [[make_anchor("1", phone1="0811111111")], [make_anchor("9", phone1="0899999999")]],
        "followup_rows": [[source_followup], [target_followup]],
    },
    fail_on_business_write="crm_lead_followups",
)
merge_rollback_conn = FakeConnection(merge_rollback_cursor)
try:
    run_with_fake_connection(
        neon.merge_customer_phone_collision,
        merge_rollback_conn,
        "1",
        "9",
        "0899999999",
        "",
        {"role": "EDITOR", "email": "editor@example.com"},
        "REQ-MERGE-ROLLBACK",
    )
    raise AssertionError("injected merge failure should rollback")
except RuntimeError:
    assert merge_rollback_conn.commit_count == 0
    assert merge_rollback_conn.rollback_count == 1

direct_audit_cursor = FakeCursor()
direct_inserted = neon._insert_crm_audit_log(
    direct_audit_cursor,
    request_id="REQ-DIRECT-AUDIT",
    action_type="TEST_NESTED_AUDIT",
    entity_type="customer_phone",
    entity_key="1",
    actor={"role": "EDITOR", "email": "editor@example.com", "staff_name": "Editor"},
    source_page="tests/test_customer_editor_actions.py",
    before_snapshot={
        "id": uuid4(),
        "amount": Decimal("15.50"),
        "created_at": datetime(2026, 7, 21, 10, 0, 0),
        "items": [{"id": uuid4(), "dates": (date(2026, 7, 21), time(10, 0, 0))}],
    },
    after_snapshot={"ids": {uuid4()}, "nested": {uuid4(): [Decimal("0.01")]}},
    metadata={"request_uuid": uuid4(), "frozen": frozenset({uuid4()})},
)
assert direct_inserted is True
assert_audit_payloads_json_safe(direct_audit_cursor)

print("customer editor actions safety OK")
