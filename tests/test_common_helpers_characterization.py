from datetime import datetime, timedelta
from uuid import UUID

from neon_utils import new_batch_id, now_iso


def test_new_batch_id_returns_unique_uuid_strings():
    first = new_batch_id()
    second = new_batch_id()

    assert isinstance(first, str)
    assert isinstance(second, str)
    assert UUID(first)
    assert UUID(second)
    assert first != second


def test_now_iso_returns_parseable_utc_timestamp():
    value = now_iso()

    assert isinstance(value, str)
    parsed = datetime.fromisoformat(value)
    assert parsed.tzinfo is not None
    assert parsed.utcoffset() == timedelta(0)
