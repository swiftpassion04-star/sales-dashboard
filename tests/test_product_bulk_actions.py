import sys
import types
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from crm_data.products import bulk_update_product_active, validate_product_ids


assert validate_product_ids([]) == []
assert validate_product_ids([1, 2, 3]) == [1, 2, 3]
assert validate_product_ids([1, 2, 1]) == [1, 2]
assert bulk_update_product_active([], True) == 0

for invalid_ids in (["1"], [1.2], [True], [0], [-1]):
    try:
        validate_product_ids(invalid_ids)
    except ValueError:
        pass
    else:
        raise AssertionError(f"expected invalid product IDs to be rejected: {invalid_ids}")


class FakeCursor:
    rowcount = 2

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


class FakeConnection:
    def __init__(self):
        self.cursor_instance = FakeCursor()
        self.committed = False
        self.rolled_back = False

    def cursor(self):
        return self.cursor_instance

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True


fake_connection = FakeConnection()


@contextmanager
def fake_neon_connection():
    yield fake_connection


original_neon_utils = sys.modules.get("neon_utils")
sys.modules["neon_utils"] = types.SimpleNamespace(
    ensure_crm_data_imports_schema=lambda: None,
    neon_connection=fake_neon_connection,
)
try:
    updated_count = bulk_update_product_active([1, 2], False, "editor@example.com")
finally:
    if original_neon_utils is None:
        del sys.modules["neon_utils"]
    else:
        sys.modules["neon_utils"] = original_neon_utils

assert updated_count == 2
assert "where id = any(%s::bigint[])" in fake_connection.cursor_instance.statement
assert fake_connection.cursor_instance.params == [False, "editor@example.com", [1, 2]]
assert fake_connection.committed is True
assert fake_connection.rolled_back is False

print("product bulk action safety OK")
