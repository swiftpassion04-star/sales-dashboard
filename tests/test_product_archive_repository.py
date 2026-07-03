import sys
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import neon_utils
from crm_data import products


class FakeCursor:
    def __init__(self, rowcount):
        self.rowcount = rowcount
        self.executed = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def execute(self, sql, params):
        self.executed.append((sql, params))


class FakeConnection:
    def __init__(self, rowcount):
        self.cursor_instance = FakeCursor(rowcount)
        self.committed = False
        self.rolled_back = False

    def cursor(self):
        return self.cursor_instance

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True


class FakeConnectionContext:
    def __init__(self, connection):
        self.connection = connection

    def __enter__(self):
        return self.connection

    def __exit__(self, exc_type, exc, traceback):
        return False


def normalized_sql(sql):
    return " ".join(sql.lower().split())


archive_sql = normalized_sql(products._ARCHIVE_PRODUCTS_SQL)
assert "delete " not in archive_sql
assert "archived_at = now()" in archive_sql
assert "is_active = false" in archive_sql
assert "and archived_at is null" in archive_sql
assert "where id = any(%s::bigint[])" in archive_sql

restore_sql = normalized_sql(products._RESTORE_ARCHIVED_PRODUCTS_SQL)
assert "delete " not in restore_sql
assert "archived_at = null" in restore_sql
assert "archived_by = null" in restore_sql
assert "archive_reason = null" in restore_sql
assert "is_active = false" in restore_sql
assert "and archived_at is not null" in restore_sql
assert "where id = any(%s::bigint[])" in restore_sql

try:
    products.archive_products([1, "2"])
except ValueError:
    pass
else:
    raise AssertionError("archive_products must validate product IDs")

archive_connection = FakeConnection(rowcount=1)
with (
    patch.object(
        neon_utils,
        "neon_connection",
        return_value=FakeConnectionContext(archive_connection),
    ),
    patch.object(products.fetch_product_page, "clear", Mock()) as clear_page,
    patch.object(products.fetch_product_options, "clear", Mock()) as clear_options,
):
    archive_result = products.archive_products(
        [3, 3, 8],
        archived_by=" editor@example.com ",
        reason=" duplicate product ",
    )
    assert archive_result == {"requested": 2, "updated": 1, "skipped": 1}
    assert archive_connection.committed is True
    assert archive_connection.rolled_back is False
    assert archive_connection.cursor_instance.executed == [
        (
            products._ARCHIVE_PRODUCTS_SQL,
            ["editor@example.com", "duplicate product", "editor@example.com", [3, 8]],
        )
    ]
    clear_page.assert_called_once_with()
    clear_options.assert_called_once_with()

restore_connection = FakeConnection(rowcount=2)
with (
    patch.object(
        neon_utils,
        "neon_connection",
        return_value=FakeConnectionContext(restore_connection),
    ),
    patch.object(products.fetch_product_page, "clear", Mock()) as clear_page,
    patch.object(products.fetch_product_options, "clear", Mock()) as clear_options,
):
    restore_result = products.restore_archived_products([5, 9], restored_by="editor@example.com")
    assert restore_result == {"requested": 2, "updated": 2, "skipped": 0}
    assert restore_connection.committed is True
    assert restore_connection.rolled_back is False
    assert restore_connection.cursor_instance.executed == [
        (products._RESTORE_ARCHIVED_PRODUCTS_SQL, ["editor@example.com", [5, 9]])
    ]
    clear_page.assert_called_once_with()
    clear_options.assert_called_once_with()

print("product archive repository safety OK")
