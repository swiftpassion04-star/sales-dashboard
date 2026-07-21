import importlib
import json
import logging
import re
import sys
from io import StringIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app_logging


def reject_json_constant(value):
    raise ValueError(f"Non-standard JSON constant: {value}")


class BrokenString:
    def __str__(self):
        raise RuntimeError("cannot stringify")


class BrokenLogger(logging.Logger):
    def log(self, level, msg, *args, **kwargs):
        raise RuntimeError("logger sink unavailable")


class BrokenException(Exception):
    def __str__(self):
        raise RuntimeError("cannot stringify exception")


class HostileExceptionAttributes(Exception):
    def __init__(self, *broken_attributes: str):
        super().__init__("private hostile exception message")
        object.__setattr__(self, "_broken_attributes", set(broken_attributes))

    def __getattribute__(self, name):
        if name != "_broken_attributes" and name in object.__getattribute__(self, "_broken_attributes"):
            raise RuntimeError("hostile attribute access message")
        return super().__getattribute__(name)


class StringSubclass(str):
    pass


def make_capture_logger() -> tuple[logging.Logger, StringIO]:
    stream = StringIO()
    logger = logging.getLogger(f"test_app_logging_{id(stream)}")
    logger.handlers = []
    logger.propagate = False
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    return logger, stream


def parse_logged_records(stream: StringIO) -> list[dict]:
    lines = [line for line in stream.getvalue().splitlines() if line.strip()]
    assert lines
    assert all("\n" not in line for line in lines)
    return [json.loads(line, parse_constant=reject_json_constant) for line in lines]


def parse_single_logged_record(stream: StringIO) -> dict:
    records = parse_logged_records(stream)
    assert len(records) == 1
    return records[0]


def assert_reference_id(value: str) -> None:
    assert isinstance(value, str)
    assert re.fullmatch(r"[0-9a-f]{8}", value)


def serialized(record: dict) -> str:
    return json.dumps(record, ensure_ascii=False, sort_keys=True, allow_nan=False)


def assert_private_values_absent(record: dict, values: tuple[str, ...]) -> None:
    text = serialized(record)
    for value in values:
        assert value not in text


def assert_safe_frame_filename(filename: str) -> None:
    assert filename
    assert not Path(filename).is_absolute()
    assert filename == filename.replace("\\", "/").rsplit("/", 1)[-1]
    forbidden_parts = (
        "C:\\",
        "C:/",
        "/home/",
        "/Users/",
        "\\Users\\",
        "admin",
        "github_sales_dashboard",
    )
    for forbidden in forbidden_parts:
        assert forbidden not in filename


def assert_all_frame_filenames_are_private(record: dict) -> None:
    for chain_item in record["traceback"]["chain"]:
        for frame in chain_item["frames"]:
            assert set(frame) == {"filename", "line_number", "function"}
            assert "line" not in frame
            assert_safe_frame_filename(frame["filename"])


def test_metadata_allowlist_drops_forbidden_and_arbitrary_keys():
    logger, stream = make_capture_logger()
    app_logging.log_event(
        "metadata_allowlist",
        safe_metadata_values={
            "action": "save",
            "page": "customers",
            "source_page": "pages/customers.py",
            "page_size": 50,
            "count": 3,
            "role": "EDITOR",
            "sale_type": "online",
            "component": "phone_merge",
            "outcome": "failed",
            "customer_name": "Alice Customer",
            "phone": "0812345678",
            "email": "alice@example.com",
            "address": "123 Secret Road",
            "order_id": "ORD-123",
            "sql": "select * from customers where phone = %s",
            "query": "select password from users",
            "params": ["0812345678"],
            "parameters": {"email": "alice@example.com"},
            "sql_params": ("ORD-123",),
            "items": ["not allowed"],
            "note": "private note",
        },
        logger=logger,
    )

    record = parse_single_logged_record(stream)
    metadata = record["metadata"]
    text = serialized(record)

    assert metadata == {
        "action": "save",
        "page": "customers",
        "source_page": "pages/customers.py",
        "page_size": 50,
        "count": 3,
        "role": "EDITOR",
        "sale_type": "online",
        "component": "phone_merge",
        "outcome": "failed",
    }
    for leaked in (
        "Alice Customer",
        "0812345678",
        "alice@example.com",
        "123 Secret Road",
        "ORD-123",
        "select *",
        "private note",
        "not allowed",
    ):
        assert leaked not in text


def test_normalize_event_accepts_valid_identifiers():
    logger, stream = make_capture_logger()

    for event in ("save_lead", "import_excel", "load_customers", "phase1_error"):
        app_logging.log_event(event, logger=logger)

    records = parse_logged_records(stream)
    assert [record["event"] for record in records] == [
        "save_lead",
        "import_excel",
        "load_customers",
        "phase1_error",
    ]


def test_invalid_events_become_unknown_event_and_do_not_leak_values():
    logger, stream = make_capture_logger()
    unsafe_events = (
        "save lead",
        "SaveLead",
        "save-lead",
        "save_lead\nforged_record",
        "customer@example.com",
        "0812345678",
        "x" * 65,
        "",
        None,
        123,
        b"save_lead",
        {"event": "save_lead"},
        ["save_lead"],
        ("save_lead",),
        ValueError("private exception message"),
        BrokenString(),
    )

    for event in unsafe_events:
        app_logging.log_event(event, logger=logger)

    records = parse_logged_records(stream)
    assert len(records) == len(unsafe_events)
    assert all(record["event"] == app_logging.UNKNOWN_EVENT for record in records)
    text = stream.getvalue()
    for leaked in (
        "save lead",
        "SaveLead",
        "save-lead",
        "forged_record",
        "customer@example.com",
        "0812345678",
        "private exception message",
    ):
        assert leaked not in text


def test_bytes_event_is_unknown_for_event_and_exception_logging():
    logger, stream = make_capture_logger()

    app_logging.log_event(b"save_lead", logger=logger)
    try:
        raise RuntimeError("private bytes event exception")
    except RuntimeError as exc:
        reference_id = app_logging.log_exception(b"save_lead", exc, logger=logger)

    records = parse_logged_records(stream)
    assert len(records) == 2
    assert all(record["event"] == app_logging.UNKNOWN_EVENT for record in records)
    assert_reference_id(reference_id)
    assert records[1]["error_reference_id"] == reference_id
    text = serialized({"records": records})
    assert "save_lead" not in text
    assert "private bytes event exception" not in text


def test_str_subclass_event_is_unknown_for_event_and_exception_logging():
    logger, stream = make_capture_logger()

    app_logging.log_event(StringSubclass("save_lead"), logger=logger)
    try:
        raise RuntimeError("private subclass event exception")
    except RuntimeError as exc:
        reference_id = app_logging.log_exception(StringSubclass("save_lead"), exc, logger=logger)

    records = parse_logged_records(stream)
    assert len(records) == 2
    assert all(record["event"] == app_logging.UNKNOWN_EVENT for record in records)
    assert_reference_id(reference_id)
    assert records[1]["error_reference_id"] == reference_id
    text = serialized({"records": records})
    assert "save_lead" not in text
    assert "private subclass event exception" not in text


def test_control_character_events_are_unknown_and_one_line_json():
    logger, stream = make_capture_logger()
    unsafe_events = ("save_lead\tforged", "save_lead\x00forged")

    for event in unsafe_events:
        app_logging.log_event(event, logger=logger)

    records = parse_logged_records(stream)
    assert len(records) == len(unsafe_events)
    assert all(record["event"] == app_logging.UNKNOWN_EVENT for record in records)
    text = stream.getvalue()
    assert len([line for line in text.splitlines() if line.strip()]) == len(unsafe_events)
    assert "save_lead" not in text
    assert "forged" not in text


def test_sensitive_key_variants_are_redacted_case_insensitively():
    samples = {
        "password": "PASSWORD=one",
        "passwd": "passwd=two",
        "token": "token=three",
        "access_token": "ACCESS_TOKEN=four",
        "refresh_token": "refresh_token=five",
        "api_key": "api_key=six",
        "apikey": "apikey=seven",
        "cookie": "cookie=eight",
        "set-cookie": "Set-Cookie=nine",
        "authorization": "Authorization: Bearer ten.token",
        "database_url": "database_url=postgres://user:pass@host/db",
        "db_url": "db_url=mysql://user:pass@host/db",
        "connection_string": "connection_string=mongodb://user:pass@host/db",
        "dsn": "dsn=mssql://user:pass@host/db",
        "mixed": "MyAccess_Token=secret-value",
    }

    for raw_value in samples.values():
        redacted = app_logging.redact_text(raw_value)
        assert app_logging.REDACTED in redacted
        assert "user:pass" not in redacted
        assert "secret-value" not in redacted
        assert "ten.token" not in redacted


def test_nested_and_unsafe_metadata_values_do_not_leak_representations():
    logger, stream = make_capture_logger()
    app_logging.log_event(
        "metadata_unsafe",
        safe_metadata_values={
            "action": {"nested": {"password": "nested-secret", "phone": "0812345678"}},
            "component": ["customer_name", "Alice"],
            "outcome": ("email", "alice@example.com"),
            "role": BrokenString(),
            "sale_type": ValueError("order_id ORD-123"),
            "count": float("nan"),
            "page_size": float("inf"),
            "arbitrary": {"access_token": "nested-token"},
        },
        logger=logger,
    )

    record = parse_single_logged_record(stream)
    text = serialized(record)

    assert record["metadata"] == {
        "action": app_logging.UNSUPPORTED_METADATA_VALUE,
        "component": app_logging.UNSUPPORTED_METADATA_VALUE,
        "outcome": app_logging.UNSUPPORTED_METADATA_VALUE,
        "role": app_logging.UNSUPPORTED_METADATA_VALUE,
        "sale_type": app_logging.UNSUPPORTED_METADATA_VALUE,
        "count": app_logging.UNSUPPORTED_METADATA_VALUE,
        "page_size": app_logging.UNSUPPORTED_METADATA_VALUE,
    }
    for leaked in ("nested-secret", "0812345678", "Alice", "alice@example.com", "ORD-123", "nested-token"):
        assert leaked not in text


def test_metadata_bool_values_are_preserved_as_booleans():
    logger, stream = make_capture_logger()
    app_logging.log_event(
        "metadata_bool",
        safe_metadata_values={"outcome": True, "role": False},
        logger=logger,
    )

    record = parse_single_logged_record(stream)
    metadata = record["metadata"]

    assert metadata["outcome"] is True
    assert type(metadata["outcome"]) is bool
    assert metadata["role"] is False
    assert type(metadata["role"]) is bool
    text = stream.getvalue()
    assert '"outcome": true' in text
    assert '"role": false' in text
    assert '"outcome": 1' not in text
    assert '"role": 0' not in text


def test_long_metadata_string_is_truncated_without_leaking_tail():
    logger, stream = make_capture_logger()
    tail = "excess_tail_marker"
    long_value = ("a" * app_logging.MAX_METADATA_STRING_LENGTH) + tail

    app_logging.log_event(
        "metadata_long_string",
        safe_metadata_values={"component": long_value},
        logger=logger,
    )

    record = parse_single_logged_record(stream)
    saved_value = record["metadata"]["component"]

    assert saved_value == ("a" * (app_logging.MAX_METADATA_STRING_LENGTH - len("..."))) + "..."
    assert len(saved_value) <= app_logging.MAX_METADATA_STRING_LENGTH
    assert len(saved_value) == app_logging.MAX_METADATA_STRING_LENGTH
    assert saved_value.endswith("...")
    assert tail not in serialized(record)


def test_metadata_string_truncation_boundaries():
    logger, stream = make_capture_logger()
    exact_value = "e" * app_logging.MAX_METADATA_STRING_LENGTH
    one_over_tail = "~"
    one_over_value = ("o" * app_logging.MAX_METADATA_STRING_LENGTH) + one_over_tail
    very_long_tail = "unique_tail_marker"
    very_long_value = ("v" * (app_logging.MAX_METADATA_STRING_LENGTH * 3)) + very_long_tail

    app_logging.log_event(
        "metadata_boundary_exact",
        safe_metadata_values={"component": exact_value},
        logger=logger,
    )
    app_logging.log_event(
        "metadata_boundary_one",
        safe_metadata_values={"component": one_over_value},
        logger=logger,
    )
    app_logging.log_event(
        "metadata_boundary_long",
        safe_metadata_values={"component": very_long_value},
        logger=logger,
    )

    exact_record, one_over_record, very_long_record = parse_logged_records(stream)
    exact_saved = exact_record["metadata"]["component"]
    one_over_saved = one_over_record["metadata"]["component"]
    very_long_saved = very_long_record["metadata"]["component"]

    assert exact_saved == exact_value
    assert len(exact_saved) == app_logging.MAX_METADATA_STRING_LENGTH
    assert not exact_saved.endswith("...")

    assert len(one_over_saved) == app_logging.MAX_METADATA_STRING_LENGTH
    assert one_over_saved.endswith("...")
    assert one_over_tail not in serialized(one_over_record)

    assert len(very_long_saved) == app_logging.MAX_METADATA_STRING_LENGTH
    assert very_long_saved.endswith("...")
    assert very_long_tail not in serialized(very_long_record)


def test_non_finite_floats_are_strict_json_safe():
    logger, stream = make_capture_logger()
    app_logging.log_event(
        "finite_values",
        safe_metadata_values={
            "count": float("nan"),
            "page_size": float("inf"),
            "outcome": float("-inf"),
        },
        logger=logger,
    )

    record = parse_single_logged_record(stream)
    assert record["metadata"] == {
        "count": app_logging.UNSUPPORTED_METADATA_VALUE,
        "page_size": app_logging.UNSUPPORTED_METADATA_VALUE,
        "outcome": app_logging.UNSUPPORTED_METADATA_VALUE,
    }
    text = stream.getvalue()
    assert "NaN" not in text
    assert "Infinity" not in text


def test_safe_frame_filename_normalizes_paths_without_private_parts():
    cases = {
        r"C:\Users\admin\project\pages\orders.py": "orders.py",
        "C:/Users/admin/project/pages/orders.py": "orders.py",
        "/home/admin/project/pages/orders.py": "orders.py",
        "orders.py": "orders.py",
        "": "unknown.py",
        None: "unknown.py",
        object(): "unknown.py",
        BrokenString(): "unknown.py",
    }

    for raw_filename, expected in cases.items():
        filename = app_logging._safe_frame_filename(raw_filename)
        assert filename == expected
        assert_safe_frame_filename(filename)


def test_exception_logging_omits_raw_messages_and_keeps_stack_structure():
    logger, stream = make_capture_logger()

    def inner():
        raise RuntimeError(
            "customer Alice 0812345678 alice@example.com ORD-123 sql params ['secret-param']"
        )

    try:
        inner()
    except RuntimeError as exc:
        reference_id = app_logging.log_exception(
            "customer_merge_failed",
            exc,
            safe_metadata_values={"action": "merge", "component": "customer_editor"},
            logger=logger,
        )

    record = parse_single_logged_record(stream)
    text = serialized(record)

    assert record["error_reference_id"] == reference_id
    assert_reference_id(reference_id)
    assert record["exception_type"] == "RuntimeError"
    assert record["traceback"]["chain"][0]["exception_type"] == "RuntimeError"
    assert record["traceback"]["chain"][0]["frames"]
    assert_all_frame_filenames_are_private(record)
    for leaked in ("Alice", "0812345678", "alice@example.com", "ORD-123", "secret-param", "sql params"):
        assert leaked not in text


def test_exception_chaining_logs_types_and_frames_without_messages():
    logger, stream = make_capture_logger()

    try:
        try:
            raise ValueError("password=inner-secret")
        except ValueError as exc:
            raise RuntimeError("outer-token=outer-secret") from exc
    except RuntimeError as exc:
        app_logging.log_exception("chain_test", exc, logger=logger)

    record = parse_single_logged_record(stream)
    chain = record["traceback"]["chain"]
    text = serialized(record)

    assert [item["exception_type"] for item in chain] == ["RuntimeError", "ValueError"]
    assert all(isinstance(item["frames"], list) for item in chain)
    assert_all_frame_filenames_are_private(record)
    assert "inner-secret" not in text
    assert "outer-secret" not in text


def test_implicit_exception_context_is_logged_without_messages_or_paths():
    logger, stream = make_capture_logger()

    try:
        try:
            raise ValueError("private first message")
        except ValueError:
            raise RuntimeError("private second message")
    except RuntimeError as exc:
        app_logging.log_exception("context_test", exc, logger=logger)

    record = parse_single_logged_record(stream)
    chain = record["traceback"]["chain"]
    text = serialized(record)

    assert [item["exception_type"] for item in chain] == ["RuntimeError", "ValueError"]
    assert_all_frame_filenames_are_private(record)
    assert "private first message" not in text
    assert "private second message" not in text


def test_exception_cause_takes_priority_over_context():
    logger, stream = make_capture_logger()
    outer = RuntimeError("outer private message")
    cause = ValueError("cause private message")
    context = KeyError("context private message")
    outer.__cause__ = cause
    outer.__context__ = context

    app_logging.log_exception("cause_priority", outer, logger=logger)

    record = parse_single_logged_record(stream)
    chain = record["traceback"]["chain"]

    assert [item["exception_type"] for item in chain] == ["RuntimeError", "ValueError"]
    assert "KeyError" not in [item["exception_type"] for item in chain]
    assert_private_values_absent(
        record,
        ("outer private message", "cause private message", "context private message"),
    )


def test_suppressed_exception_context_is_not_logged():
    logger, stream = make_capture_logger()

    try:
        try:
            raise ValueError("suppressed private context")
        except ValueError:
            raise RuntimeError("suppressed private outer") from None
    except RuntimeError as exc:
        app_logging.log_exception("suppress_context", exc, logger=logger)

    record = parse_single_logged_record(stream)
    chain = record["traceback"]["chain"]

    assert [item["exception_type"] for item in chain] == ["RuntimeError"]
    assert_private_values_absent(record, ("suppressed private context", "suppressed private outer"))
    assert_all_frame_filenames_are_private(record)


def test_exception_chain_loop_and_depth_limit_do_not_crash():
    logger, stream = make_capture_logger()
    first = RuntimeError("first private message")
    second = ValueError("second private message")
    first.__cause__ = second
    second.__cause__ = first

    reference_id = app_logging.log_exception("loop_test", first, logger=logger)
    record = parse_single_logged_record(stream)

    assert_reference_id(reference_id)
    assert len(record["traceback"]["chain"]) == 2
    assert_private_values_absent(record, ("first private message", "second private message"))

    logger, stream = make_capture_logger()
    exceptions = [RuntimeError(f"private message {index}") for index in range(app_logging.MAX_TRACEBACK_CHAIN_DEPTH + 3)]
    for current, next_exception in zip(exceptions, exceptions[1:]):
        current.__cause__ = next_exception

    reference_id = app_logging.log_exception("depth_test", exceptions[0], logger=logger)
    record = parse_single_logged_record(stream)

    assert_reference_id(reference_id)
    assert len(record["traceback"]["chain"]) == app_logging.MAX_TRACEBACK_CHAIN_DEPTH
    assert_private_values_absent(record, tuple(f"private message {index}" for index in range(len(exceptions))))


def test_hostile_exception_attributes_do_not_crash_exception_logging():
    cases = (
        ("broken_traceback", ("__traceback__",)),
        ("broken_cause", ("__cause__",)),
        ("broken_context", ("__context__",)),
        ("broken_suppress_context", ("__suppress_context__",)),
        (
            "broken_multiple_attributes",
            ("__traceback__", "__cause__", "__context__", "__suppress_context__"),
        ),
    )

    for event, broken_attributes in cases:
        logger, stream = make_capture_logger()

        reference_id = app_logging.log_exception(
            event,
            HostileExceptionAttributes(*broken_attributes),
            logger=logger,
        )

        record = parse_single_logged_record(stream)
        assert_reference_id(reference_id)
        assert record["error_reference_id"] == reference_id
        assert record["event"] == event
        assert record["exception_type"] == "HostileExceptionAttributes"
        assert record["traceback"]["chain"][0]["exception_type"] == "HostileExceptionAttributes"
        assert_all_frame_filenames_are_private(record)
        assert_private_values_absent(
            record,
            ("private hostile exception message", "hostile attribute access message"),
        )


def test_broken_exception_str_and_logger_failure_do_not_crash():
    logger, stream = make_capture_logger()

    try:
        raise BrokenException()
    except BrokenException as exc:
        reference_id = app_logging.log_exception("broken_exception", exc, logger=logger)

    record = parse_single_logged_record(stream)
    assert record["error_reference_id"] == reference_id
    assert record["exception_type"] == "BrokenException"

    app_logging.log_exception("broken_logger", BrokenException(), logger=BrokenLogger("broken_logger"))
    app_logging.log_event("broken_logger_event", logger=BrokenLogger("broken_logger_event"))


def test_user_error_message_hides_raw_exception_and_traceback():
    message = app_logging.user_error_message("abc123ef")

    assert "abc123ef" in message
    assert "Traceback" not in message
    assert "RuntimeError" not in message
    assert "database exploded" not in message
    assert "select * from" not in message.casefold()


def test_reference_ids_are_unique_short_hex_and_returned_in_log():
    values = {app_logging.new_error_reference_id() for _ in range(1000)}
    assert len(values) == 1000
    assert all(re.fullmatch(r"[0-9a-f]{8}", value) for value in values)

    logger, stream = make_capture_logger()
    reference_id = app_logging.log_exception("reference_test", ValueError("hidden"), logger=logger)
    record = parse_single_logged_record(stream)

    assert_reference_id(reference_id)
    assert record["error_reference_id"] == reference_id


def test_logger_outputs_stdout_one_line_json_and_avoids_duplicate_handlers():
    logger = app_logging.get_app_logger()
    before_count = len(logger.handlers)
    assert any(
        getattr(handler, "_crm_app_logging_handler", False) and handler.stream is sys.stdout
        for handler in logger.handlers
    )
    assert logger.propagate is False

    for _ in range(5):
        app_logging.get_app_logger()
    assert len(logger.handlers) == before_count

    reloaded = importlib.reload(app_logging)
    reloaded_logger = reloaded.get_app_logger()
    assert len(reloaded_logger.handlers) == before_count
    assert reloaded_logger.propagate is False

    capture_logger, stream = make_capture_logger()
    reloaded.log_event("json_output", safe_metadata_values={"action": "load"}, logger=capture_logger)
    record = parse_single_logged_record(stream)
    assert record["event"] == "json_output"
    assert record["metadata"] == {"action": "load"}


def run_all_tests() -> None:
    for name, value in sorted(globals().items()):
        if name.startswith("test_") and callable(value):
            value()


if __name__ == "__main__":
    run_all_tests()
    print("app logging safety OK")
