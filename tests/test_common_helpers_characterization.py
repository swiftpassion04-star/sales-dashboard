from datetime import datetime, timedelta, timezone
from uuid import UUID

import pandas as pd

from neon_utils import BANGKOK_TZ, clean, new_batch_id, now_iso


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


def test_bangkok_timezone_key():
    assert BANGKOK_TZ.key == "Asia/Bangkok"


def test_bangkok_timezone_offset_is_plus_7():
    value = datetime(2026, 6, 29, 12, 0, tzinfo=BANGKOK_TZ)

    assert value.utcoffset() == timedelta(hours=7)


def test_bangkok_midnight_converts_to_previous_day_utc_17():
    bangkok_midnight = datetime(2026, 6, 29, 0, 0, tzinfo=BANGKOK_TZ)
    utc_value = bangkok_midnight.astimezone(timezone.utc)

    assert utc_value == datetime(2026, 6, 28, 17, 0, tzinfo=timezone.utc)


def test_bangkok_date_range_end_boundary_is_exclusive_next_midnight():
    start = datetime(2026, 6, 29, 0, 0, tzinfo=BANGKOK_TZ)
    end = datetime(2026, 6, 30, 0, 0, tzinfo=BANGKOK_TZ)

    start_utc = start.astimezone(timezone.utc)
    end_utc = end.astimezone(timezone.utc)

    assert end > start
    assert end_utc - start_utc == timedelta(days=1)


def test_clean_empty_like_values():
    assert clean(None) == ""
    assert clean("") == ""
    assert clean("   ") == ""
    assert clean(float("nan")) == ""
    assert clean(pd.NaT) == ""


def test_clean_preserves_current_pd_na_behavior():
    assert clean(pd.NA) == "<NA>"


def test_clean_strips_and_stringifies_values():
    assert clean("  abc  ") == "abc"
    assert clean(123) == "123"
    assert clean(0) == "0"
    assert clean(False) == "False"


def test_clean_sentinel_strings_become_empty():
    assert clean("NULL") == ""
    assert clean("none") == ""
    assert clean(" NaN ") == ""
    assert clean("nat") == ""
