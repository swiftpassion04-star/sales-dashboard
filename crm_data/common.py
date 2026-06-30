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


def new_batch_id() -> str:
    return str(uuid4())


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
