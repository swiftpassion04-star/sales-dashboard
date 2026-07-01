import hashlib
from datetime import datetime, timezone
from uuid import uuid4
from zoneinfo import ZoneInfo

import pandas as pd


BANGKOK_TZ = ZoneInfo("Asia/Bangkok")


def clean(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and pd.isna(value):
        return ""
    text = str(value).strip()
    return "" if text.upper() in {"NULL", "NONE", "NAN", "NAT"} else text


def normalize_phone(value) -> str:
    return "".join(ch for ch in clean(value) if ch.isdigit())


def make_dedupe_key(order_id: str, phone1: str, phone2: str, tracking_no: str) -> str:
    text = "|".join([clean(order_id), normalize_phone(phone1), normalize_phone(phone2), clean(tracking_no)])
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


PHONE_RULE_MESSAGE = "ต้องเป็นตัวเลข 10 หลัก ขึ้นต้นด้วย 0 และห้ามมีสัญลักษณ์"


def validate_phone_value(value, label: str) -> str:
    text = clean(value)
    if not text:
        return ""
    if not text.isdigit() or len(text) != 10 or not text.startswith("0"):
        return f"{label}ใส่ไม่ถูกต้อง {PHONE_RULE_MESSAGE}"
    return ""


def validate_phone_pair(phone1, phone2, require_one: bool = True) -> list[str]:
    first = clean(phone1)
    second = clean(phone2)
    if require_one and not first and not second:
        return ["กรุณากรอกเบอร์โทรหรือเบอร์สำรอง"]

    errors = []
    for value, label in ((first, "เบอร์โทร"), (second, "เบอร์สำรอง")):
        error = validate_phone_value(value, label)
        if error:
            errors.append(error)
    return errors


def to_number(value):
    text = clean(value).replace(",", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def parse_date(value) -> str | None:
    text = clean(value)
    if not text:
        return None
    parsed = pd.to_datetime(text, errors="coerce", dayfirst=True)
    if pd.isna(parsed):
        return None
    return parsed.date().isoformat()


def new_batch_id() -> str:
    return str(uuid4())


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
