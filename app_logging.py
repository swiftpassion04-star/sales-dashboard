import json
import logging
import math
import re
import sys
import traceback
from datetime import datetime, timezone
from uuid import uuid4


LOGGER_NAME = "sales_crm"
ERROR_REFERENCE_LENGTH = 8
REDACTED = "[REDACTED]"
UNSUPPORTED_METADATA_VALUE = "[UNSUPPORTED_METADATA_VALUE]"
UNKNOWN_EVENT = "unknown_event"
MAX_METADATA_STRING_LENGTH = 128
MAX_TRACEBACK_CHAIN_DEPTH = 8
EVENT_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,63}$")

SAFE_METADATA_KEYS = frozenset(
    {
        "action",
        "page",
        "source_page",
        "page_size",
        "count",
        "role",
        "sale_type",
        "component",
        "outcome",
    }
)

FORBIDDEN_METADATA_KEY_PATTERNS = (
    "customer_name",
    "phone",
    "email",
    "address",
    "order_id",
    "sql",
    "query",
    "params",
    "parameters",
    "sql_params",
)

SENSITIVE_KEY_PATTERNS = (
    "password",
    "passwd",
    "token",
    "access_token",
    "refresh_token",
    "api_key",
    "apikey",
    "cookie",
    "set-cookie",
    "authorization",
    "database_url",
    "db_url",
    "connection_string",
    "dsn",
)

_SENSITIVE_TEXT_PATTERNS = [
    re.compile(
        r"(?i)\b([a-z0-9_.-]*(?:password|passwd|token|access_token|refresh_token|api[_-]?key|apikey|secret|cookie|set-cookie|authorization|database_url|db_url|connection_string|dsn)[a-z0-9_.-]*)"
        r"(\s*[:=]\s*)"
        r"(?:bearer\s+)?([^\s,;]+)"
    ),
    re.compile(r"(?i)(bearer\s+)[a-z0-9._~+/=-]+"),
    re.compile(r"(?i)\b(postgres(?:ql)?|mysql|mssql|mongodb)://[^\s]+"),
]


def get_app_logger() -> logging.Logger:
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if not any(getattr(handler, "_crm_app_logging_handler", False) for handler in logger.handlers):
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("%(message)s"))
        handler._crm_app_logging_handler = True
        logger.addHandler(handler)
    return logger


def new_error_reference_id() -> str:
    return uuid4().hex[:ERROR_REFERENCE_LENGTH]


def user_error_message(error_reference_id: str) -> str:
    return f"เกิดข้อผิดพลาด กรุณาลองใหม่อีกครั้ง (รหัสอ้างอิง: {error_reference_id})"


def normalize_event(event: object) -> str:
    if type(event) is not str:
        return UNKNOWN_EVENT
    if not EVENT_PATTERN.fullmatch(event):
        return UNKNOWN_EVENT
    return event


def _normalized_key(key: object) -> str:
    if isinstance(key, str):
        return key.strip().casefold()
    return ""


def _is_allowed_metadata_key(key: object) -> bool:
    normalized = _normalized_key(key)
    if normalized not in SAFE_METADATA_KEYS:
        return False
    return not any(pattern in normalized for pattern in FORBIDDEN_METADATA_KEY_PATTERNS)


def _is_sensitive_key(key: object) -> bool:
    normalized = _normalized_key(key)
    return any(pattern in normalized for pattern in SENSITIVE_KEY_PATTERNS)


def redact_text(value: str) -> str:
    """Best-effort sanitizer for short operational labels, not a privacy boundary.

    Do not use this as justification to log arbitrary exception messages,
    customer data, secrets, SQL text, or SQL parameter values. Callers must keep
    raw PII and secrets out of logs even when metadata keys are allowlisted.
    """
    redacted = str(value)
    for pattern in _SENSITIVE_TEXT_PATTERNS:
        if pattern.pattern.startswith("(?i)(bearer"):
            redacted = pattern.sub(r"\1" + REDACTED, redacted)
        elif "://" in pattern.pattern:
            redacted = pattern.sub(lambda match: f"{match.group(1)}://{REDACTED}", redacted)
        else:
            redacted = pattern.sub(lambda match: f"{match.group(1)}{match.group(2)}{REDACTED}", redacted)
    return redacted


def _safe_metadata_value(value: object):
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else UNSUPPORTED_METADATA_VALUE
    if isinstance(value, str):
        text = redact_text(value)
        if len(text) > MAX_METADATA_STRING_LENGTH:
            suffix = "..."
            return f"{text[:MAX_METADATA_STRING_LENGTH - len(suffix)]}{suffix}"
        return text
    return UNSUPPORTED_METADATA_VALUE


def safe_metadata(value: object) -> dict:
    """Return deny-by-default metadata safe for server logs.

    Only keys in SAFE_METADATA_KEYS are preserved. Values are limited to
    str/int/float/bool/None. Dicts, lists, tuples, exceptions, and custom objects
    are replaced with a fixed marker to avoid leaking object representations.
    Callers must not send PII, secrets, SQL text, or SQL parameter values even
    under allowlisted keys.
    """
    if not isinstance(value, dict):
        return {}
    safe = {}
    for key, item in value.items():
        normalized = _normalized_key(key)
        if not _is_allowed_metadata_key(key):
            continue
        if _is_sensitive_key(key):
            continue
        safe[normalized] = _safe_metadata_value(item)
    return safe


def _safe_frame_filename(filename: object) -> str:
    if not isinstance(filename, str) or not filename:
        return "unknown.py"
    try:
        basename = filename.replace("\\", "/").rsplit("/", 1)[-1]
    except Exception:
        return "unknown.py"
    if not basename or basename in {".", ".."}:
        return "unknown.py"
    return basename


def _stack_frames(tb) -> list[dict]:
    frames = []
    try:
        extracted_frames = traceback.extract_tb(tb)
    except Exception:
        return frames
    for frame in extracted_frames:
        try:
            frames.append(
                {
                    "filename": _safe_frame_filename(frame.filename),
                    "line_number": frame.lineno,
                    "function": frame.name if isinstance(frame.name, str) else "unknown",
                }
            )
        except Exception:
            continue
    return frames


def _safe_exception_attribute(exception: object, attribute: str, fallback: object = None) -> object:
    try:
        return getattr(exception, attribute)
    except BaseException:
        return fallback


def _exception_chain(exc: object) -> list[dict]:
    chain = []
    seen = set()
    current = exc
    while current is not None and id(current) not in seen and len(chain) < MAX_TRACEBACK_CHAIN_DEPTH:
        seen.add(id(current))
        chain.append(
            {
                "exception_type": type(current).__name__,
                "frames": _stack_frames(_safe_exception_attribute(current, "__traceback__")),
            }
        )
        cause = _safe_exception_attribute(current, "__cause__")
        suppress_context = _safe_exception_attribute(current, "__suppress_context__", True)
        context = _safe_exception_attribute(current, "__context__")
        if cause is not None:
            current = cause
        elif not suppress_context:
            current = context
        else:
            current = None
    return chain


def _json_log(logger: logging.Logger, level: int, record: dict) -> None:
    try:
        message = json.dumps(record, ensure_ascii=False, sort_keys=True, allow_nan=False)
    except Exception:
        try:
            message = json.dumps(
                {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "level": "ERROR",
                    "event": "logging_failure",
                    "error_reference_id": record.get("error_reference_id"),
                },
                ensure_ascii=False,
                sort_keys=True,
                allow_nan=False,
            )
        except Exception:
            return
    try:
        logger.log(level, message)
    except Exception:
        pass


def log_event(event: str, *, safe_metadata_values: dict | None = None, logger: logging.Logger | None = None) -> None:
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "level": "INFO",
        "event": normalize_event(event),
        "metadata": safe_metadata(safe_metadata_values or {}),
    }
    _json_log(logger or get_app_logger(), logging.INFO, record)


def log_exception(
    event: str,
    exc: BaseException,
    *,
    safe_metadata_values: dict | None = None,
    logger: logging.Logger | None = None,
) -> str:
    error_reference_id = new_error_reference_id()
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "level": "ERROR",
        "event": normalize_event(event),
        "error_reference_id": error_reference_id,
        "exception_type": type(exc).__name__,
        "traceback": {"chain": _exception_chain(exc)},
        "metadata": safe_metadata(safe_metadata_values or {}),
    }
    _json_log(logger or get_app_logger(), logging.ERROR, record)
    return error_reference_id
