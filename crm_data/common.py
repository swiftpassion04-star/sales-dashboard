from datetime import datetime, timezone
from uuid import uuid4
from zoneinfo import ZoneInfo


BANGKOK_TZ = ZoneInfo("Asia/Bangkok")


def new_batch_id() -> str:
    return str(uuid4())


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
