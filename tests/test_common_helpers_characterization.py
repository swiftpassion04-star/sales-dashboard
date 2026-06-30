from datetime import date, datetime, timedelta, timezone
from uuid import UUID

import pandas as pd

from neon_utils import (
    BANGKOK_TZ,
    PHONE_RULE_MESSAGE,
    clean,
    new_batch_id,
    normalize_phone,
    now_iso,
    parse_date,
    to_number,
    validate_phone_pair,
    validate_phone_value,
)


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


def test_to_number_empty_like_values():
    assert to_number(None) is None
    assert to_number("") is None
    assert to_number("   ") is None
    assert to_number(float("nan")) is None
    assert to_number(pd.NA) is None


def test_to_number_numeric_values():
    assert to_number(123) == 123.0
    assert to_number(0) == 0.0
    assert to_number("1,234.56") == 1234.56
    assert to_number("-12.5") == -12.5
    assert to_number("1e3") == 1000.0


def test_to_number_invalid_values():
    assert to_number(False) is None
    assert to_number("$123") is None
    assert to_number("(123)") is None
    assert to_number("abc") is None


def test_parse_date_empty_and_invalid_values():
    assert parse_date(None) is None
    assert parse_date("") is None
    assert parse_date("   ") is None
    assert parse_date(pd.NaT) is None
    assert parse_date("not a date") is None
    assert parse_date(45000) is None


def test_parse_date_valid_values_and_dayfirst_behavior():
    assert parse_date("2026-06-30") == "2026-06-30"
    assert parse_date("30/06/2026") == "2026-06-30"
    assert parse_date("01/02/2026") == "2026-02-01"
    assert parse_date(datetime(2026, 6, 30, 8, 15)) == "2026-06-30"
    assert parse_date(date(2026, 6, 30)) == "2026-06-30"


def test_normalize_phone_preserves_current_digit_extraction_behavior():
    assert normalize_phone(None) == ""
    assert normalize_phone("") == ""
    assert normalize_phone("   ") == ""
    assert normalize_phone("0812345678") == "0812345678"
    assert normalize_phone("081-234-5678") == "0812345678"
    assert normalize_phone("081 234 5678") == "0812345678"
    assert normalize_phone("+66 81 234 5678") == "66812345678"
    assert normalize_phone("abc0812345678xyz") == "0812345678"
    assert normalize_phone(812345678) == "812345678"


def test_phone_rule_message_is_stable():
    assert PHONE_RULE_MESSAGE == "ต้องเป็นตัวเลข 10 หลัก ขึ้นต้นด้วย 0 และห้ามมีสัญลักษณ์"


def test_validate_phone_value_preserves_current_labelled_messages():
    invalid_message = f"เบอร์โทรใส่ไม่ถูกต้อง {PHONE_RULE_MESSAGE}"

    assert validate_phone_value("", "เบอร์โทร") == ""
    assert validate_phone_value("0812345678", "เบอร์โทร") == ""
    assert validate_phone_value("812345678", "เบอร์โทร") == invalid_message
    assert validate_phone_value("081234567", "เบอร์โทร") == invalid_message
    assert validate_phone_value("08123456789", "เบอร์โทร") == invalid_message
    assert validate_phone_value("081-234-5678", "เบอร์โทร") == invalid_message
    assert validate_phone_value("+66 81 234 5678", "เบอร์โทร") == invalid_message
    assert validate_phone_value("abc0812345678xyz", "เบอร์โทร") == invalid_message


def test_validate_phone_pair_preserves_current_required_and_valid_behavior():
    assert validate_phone_pair("", "") == ["กรุณากรอกเบอร์โทรหรือเบอร์สำรอง"]
    assert validate_phone_pair("", "", require_one=False) == []
    assert validate_phone_pair("0812345678", "") == []
    assert validate_phone_pair("", "0812345678") == []
    assert validate_phone_pair("0812345678", "0912345678") == []


def test_validate_phone_pair_rejects_symbols_and_invalid_lengths():
    primary_error = f"เบอร์โทรใส่ไม่ถูกต้อง {PHONE_RULE_MESSAGE}"
    secondary_error = f"เบอร์สำรองใส่ไม่ถูกต้อง {PHONE_RULE_MESSAGE}"

    assert validate_phone_pair("081-234-5678", "") == [primary_error]
    assert validate_phone_pair("", "091-234-5678") == [secondary_error]
    assert validate_phone_pair("812345678", "") == [primary_error]
