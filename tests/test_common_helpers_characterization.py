from datetime import date, datetime, timedelta, timezone
from uuid import UUID

import pandas as pd

from neon_utils import (
    BANGKOK_TZ,
    PHONE_RULE_MESSAGE,
    clean,
    make_dedupe_key,
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


def assert_sha256_hex(value: str) -> None:
    assert isinstance(value, str)
    assert len(value) == 64
    assert value == value.lower()
    int(value, 16)


def test_make_dedupe_key_empty_values_have_stable_hash():
    expected = "be5be69f55e91af25e54ecc2154d4da359b67b3b27e25f5cc0b3ff54eb74dff3"

    assert make_dedupe_key("", "", "", "") == expected
    assert make_dedupe_key(None, None, None, None) == expected
    assert_sha256_hex(expected)


def test_make_dedupe_key_trims_and_normalizes_phone_formatting():
    expected = "ec8dbb1bdf94987c1ccc5fd9ad0539c5abdb789aac0777812353046ed415fc3f"
    plain = make_dedupe_key("A001", "0812345678", "", "TH123")
    trimmed = make_dedupe_key(" A001 ", "081-234-5678", "", " TH123 ")
    spaced_phone = make_dedupe_key("A001", "081 234 5678", "", "TH123")

    assert plain == expected
    assert trimmed == expected
    assert spaced_phone == expected
    assert_sha256_hex(plain)


def test_make_dedupe_key_preserves_plus66_behavior():
    value = make_dedupe_key("A001", "+66 81 234 5678", "", "TH123")

    assert value == "11f19b85145a1957e15d478d1f08450950ba6aac6ef8fc4a81cf815e71e5acac"
    assert value != make_dedupe_key("A001", "0812345678", "", "TH123")
    assert_sha256_hex(value)


def test_make_dedupe_key_phone_order_is_significant():
    phone_pair = make_dedupe_key("A001", "0812345678", "0912345678", "TH123")
    swapped = make_dedupe_key("A001", "0912345678", "0812345678", "TH123")

    assert phone_pair == "c0a65085d6de99ede6a618504ed8011cc0ff7364fb26d616f461aca7477b1f80"
    assert swapped == "104d8e45836dec28b278f882e73b2bbd1d974e9c7b108a6c7178bc951cf78677"
    assert phone_pair != swapped
    assert_sha256_hex(phone_pair)
    assert_sha256_hex(swapped)


def test_make_dedupe_key_is_case_sensitive_and_stringifies_numbers():
    lowercase = make_dedupe_key("a001", "0812345678", "", "th123")
    numeric_phone = make_dedupe_key("A001", 812345678, "", "TH123")
    base = make_dedupe_key("A001", "0812345678", "", "TH123")

    assert lowercase == "94901deafe1ad488c160de674462687848a0e39608dae6b3c78440ba1791763b"
    assert numeric_phone == "5e4e53e5998d15cef598fd707d92b57beb6e2cb34c4ca30e0d8666fcfb093072"
    assert lowercase != base
    assert numeric_phone != base
    assert_sha256_hex(lowercase)
