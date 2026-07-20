import ast
import inspect
import sys
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import neon_utils as neon


REPO_ROOT = Path(__file__).resolve().parents[1]
CUSTOMERS_PATH = REPO_ROOT / "pages" / "customers.py"
CUSTOMER_DETAIL_PATH = REPO_ROOT / "pages" / "customer_detail.py"
NEON_PATH = REPO_ROOT / "neon_utils.py"

customers_source = CUSTOMERS_PATH.read_text(encoding="utf-8")
customer_detail_source = CUSTOMER_DETAIL_PATH.read_text(encoding="utf-8")
neon_source = NEON_PATH.read_text(encoding="utf-8")


def extract_customer_helpers() -> dict:
    tree = ast.parse(customers_source)
    needed = {"clean", "customer_phone_key", "build_follow_marker_payload"}
    nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in needed]
    assert {node.name for node in nodes} == needed
    module = ast.Module(body=nodes, type_ignores=[])
    ast.fix_missing_locations(module)
    namespace = {
        "DEFAULT_FOLLOWUP_PRIORITY": neon.DEFAULT_FOLLOWUP_PRIORITY,
        "datetime": datetime,
        "normalize_phone": neon.normalize_phone,
    }
    exec(compile(module, "<customer_follow_marker_helpers>", "exec"), namespace)
    return namespace


helpers = extract_customer_helpers()
build_follow_marker_payload = helpers["build_follow_marker_payload"]

base_row = {
    "id": "42",
    "customer_id": "42",
    "order_id": "ORD-42",
    "customer": "Existing Customer",
    "phone1": "081-234-5678",
    "phone2": "",
    "product_name": "Current Product",
    "sku": "SKU-CURRENT",
    "staff_code": "ST-ROW",
    "sales_staff": "Row Owner",
}

existing_followup = {
    "customer_key": "customer_id:42",
    "crm_data_import_id": "42",
    "order_id": "ORD-OLD",
    "customer_name": "Followup Customer",
    "phone_key": "0812345678",
    "phone1": "0812345678",
    "phone2": "0899999999",
    "product_group": "Group A",
    "product_name": "Followup Product",
    "sku": "SKU-OLD",
    "staff_code": "ST-FOLLOW",
    "owner": "Follow Owner",
    "lead_status": "interested",
    "customer_status": "active",
    "followup_status": "scheduled",
    "next_followup_date": "2026-06-11",
    "followup_note": "Keep this note",
    "follow_up_status": "scheduled",
    "follow_up_date": "2026-06-11",
    "follow_up_note": "Keep this note",
    "priority": "VIP",
}

payload = build_follow_marker_payload(base_row, "2", "agent@example.com", existing_followup)

assert payload["followup_status"] == "2"
assert payload["follow_up_status"] == "2"
assert payload["next_followup_date"] == "2026-06-11"
assert payload["follow_up_date"] == "2026-06-11"
assert payload["followup_note"] == "Keep this note"
assert payload["follow_up_note"] == "Keep this note"
assert payload["lead_status"] == "interested"
assert payload["priority"] == "VIP"
assert payload["customer_status"] == "active"
assert payload["owner"] == "Follow Owner"
assert payload["staff_code"] == "ST-FOLLOW"
assert payload["customer_key"] == "customer_id:42"
assert payload["crm_data_import_id"] == "42"
assert payload["order_id"] == "ORD-OLD"
assert payload["customer_name"] == "Followup Customer"
assert payload["phone_key"] == "0812345678"
assert payload["phone1"] == "0812345678"
assert payload["phone2"] == "0899999999"
assert payload["product_group"] == "Group A"
assert payload["product_name"] == "Followup Product"
assert payload["sku"] == "SKU-OLD"
assert payload["updated_by"] == "agent@example.com"

legacy_only = dict(existing_followup)
legacy_only["next_followup_date"] = ""
legacy_only["followup_note"] = ""
legacy_only["follow_up_date"] = "2026-07-12"
legacy_only["follow_up_note"] = "Legacy note"
legacy_payload = build_follow_marker_payload(base_row, "3", "agent@example.com", legacy_only)
assert legacy_payload["next_followup_date"] == "2026-07-12"
assert legacy_payload["follow_up_date"] == "2026-07-12"
assert legacy_payload["followup_note"] == "Legacy note"
assert legacy_payload["follow_up_note"] == "Legacy note"

new_payload = build_follow_marker_payload(base_row, "1", "agent@example.com", {})
assert new_payload["followup_status"] == "1"
assert new_payload["follow_up_status"] == "1"
assert new_payload["next_followup_date"] is None
assert new_payload["follow_up_date"] is None
assert new_payload["followup_note"]
assert new_payload["follow_up_note"] == new_payload["followup_note"]
assert new_payload["lead_status"] == "new"
assert new_payload["priority"] == neon.DEFAULT_FOLLOWUP_PRIORITY
assert new_payload["owner"] == "Row Owner"
assert new_payload["staff_code"] == "ST-ROW"

reset_payload = build_follow_marker_payload(base_row, "RESET", "agent@example.com", {})
assert reset_payload["followup_note"] == "RESET"
assert reset_payload["follow_up_note"] == "RESET"

helper_source = inspect.getsource(neon.fetch_lead_followup_by_customer)
assert "@st.cache_data" not in helper_source
assert "from public.crm_lead_followups" in helper_source
assert "order by updated_at desc nulls last, created_at desc nulls last" in helper_source
assert "limit 1" in helper_source.lower()
assert "coalesce(followup_status, follow_up_status, 'none') as followup_status" in helper_source
assert "coalesce(next_followup_date, follow_up_date)::text as next_followup_date" in helper_source
assert "coalesce(followup_note, follow_up_note, '') as followup_note" in helper_source
assert "insert into" not in helper_source.lower()
assert "delete from" not in helper_source.lower()
assert "update public" not in helper_source.lower()
assert "commit()" not in helper_source


class FakeCursor:
    def __init__(self, row):
        self.row = row
        self.statement = ""
        self.params = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def execute(self, statement, params):
        self.statement = " ".join(statement.split()).lower()
        self.params = list(params)

    def fetchone(self):
        return self.row


class FakeConnection:
    def __init__(self, row):
        self.cursor_instance = FakeCursor(row)

    def cursor(self):
        return self.cursor_instance


fake_connection = FakeConnection(existing_followup)


@contextmanager
def fake_neon_connection():
    yield fake_connection


original_ensure_schema = neon.ensure_crm_data_imports_schema
original_neon_connection = neon.neon_connection
try:
    neon.ensure_crm_data_imports_schema = lambda: True
    neon.neon_connection = fake_neon_connection
    fetched = neon.fetch_lead_followup_by_customer(
        customer_key="customer_id:42",
        crm_data_import_id="42",
        phone1="081-234-5678",
        phone2="",
    )
finally:
    neon.ensure_crm_data_imports_schema = original_ensure_schema
    neon.neon_connection = original_neon_connection

assert fetched == existing_followup
assert "select id::text as id" in fake_connection.cursor_instance.statement
assert "customer_key = %s" in fake_connection.cursor_instance.statement
assert "crm_data_import_id::text = %s" in fake_connection.cursor_instance.statement
assert "(phone1 = %s or phone2 = %s)" in fake_connection.cursor_instance.statement
assert fake_connection.cursor_instance.params == [
    neon.DEFAULT_FOLLOWUP_PRIORITY,
    "customer_id:42",
    "42",
    "0812345678",
    "0812345678",
]
assert neon.fetch_lead_followup_by_customer() == {}

assert "fetch_lead_followup_by_customer," in customer_detail_source
assert "return fetch_lead_followup_by_customer(" in customer_detail_source
assert "neon_connection" not in customer_detail_source.split("from neon_utils import", 1)[1].split(")", 1)[0]
assert "from pages.customer_detail" not in customers_source
assert "import pages.customer_detail" not in customers_source

follow_action_source = customers_source.split("if follow_submitted:", 1)[1].split("if owner_submitted:", 1)[0]
assert "neon.fetch_lead_followup_by_customer(" in follow_action_source
assert "payload = build_follow_marker_payload(row, marker, clean(user.get(\"email\")), current_followup)" in follow_action_source
read_error_source = follow_action_source.split("except Exception as exc:", 1)[1].split("try:", 1)[0]
assert "return" in read_error_source
assert "upsert_lead_followup(" not in read_error_source
assert "st.rerun()" not in read_error_source
assert "neon.clear_cached_data_functions(fetch_followup_filter_options)" in follow_action_source
assert "st.cache_data.clear()" not in follow_action_source

upsert_source = neon_source.split("def upsert_lead_followup", 1)[1].split("def _normalized_text_sql", 1)[0]
assert "on conflict (customer_key) do update" in upsert_source
assert "columns = [" in upsert_source
assert "customer_status" not in upsert_source

print("customer follow marker preservation safety OK")
