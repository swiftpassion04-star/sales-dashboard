import ast
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

TARGET_FILES = (
    "auth_utils.py",
    "ui/import_excel_ui.py",
    "ui/manual_order_ui.py",
)

APPROVED_EVENTS = {
    "auth_login_failed",
    "import_excel_file_read_failed",
    "import_excel_parse_failed",
    "import_excel_validation_failed",
    "import_excel_preview_failed",
    "import_excel_save_failed",
    "manual_order_data_load_failed",
    "manual_order_product_load_failed",
    "manual_order_save_failed",
}

EVENT_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
ALLOWED_METADATA_KEYS = {"page", "action", "component", "outcome"}
SENSITIVE_METADATA_TOKENS = {
    "address",
    "authorization",
    "connection",
    "cookie",
    "customer",
    "email",
    "filename",
    "order_id",
    "password",
    "phone",
    "query",
    "secret",
    "sql",
    "token",
    "url",
    "username",
}

EXPECTED_BOUNDARIES = {
    ("auth_utils.py", "auth_login_failed", "error"): 1,
    ("ui/import_excel_ui.py", "import_excel_file_read_failed", "error"): 1,
    ("ui/import_excel_ui.py", "import_excel_parse_failed", "error"): 1,
    ("ui/import_excel_ui.py", "import_excel_validation_failed", "error"): 1,
    ("ui/import_excel_ui.py", "import_excel_preview_failed", "warning"): 1,
    ("ui/import_excel_ui.py", "import_excel_save_failed", "error"): 2,
    ("ui/manual_order_ui.py", "manual_order_data_load_failed", "warning"): 1,
    ("ui/manual_order_ui.py", "manual_order_product_load_failed", "warning"): 1,
    ("ui/manual_order_ui.py", "manual_order_save_failed", "error"): 1,
}


def parse_source(relative_path: str) -> ast.Module:
    return ast.parse((ROOT / relative_path).read_text(encoding="utf-8"), filename=relative_path)


def call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = call_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return ""


def contains_name(node: ast.AST, name: str) -> bool:
    return any(isinstance(child, ast.Name) and child.id == name for child in ast.walk(node))


def constant_string(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and type(node.value) is str:
        return node.value
    return None


def metadata_dict(call: ast.Call) -> ast.Dict:
    positional_count = len(call.args)
    assert positional_count == 2, f"log_exception must use only event and exc positional args at line {call.lineno}"
    for keyword in call.keywords:
        if keyword.arg == "safe_metadata_values":
            assert isinstance(keyword.value, ast.Dict), f"metadata must be a dict literal at line {call.lineno}"
            return keyword.value
    raise AssertionError(f"log_exception missing safe_metadata_values at line {call.lineno}")


def assert_safe_metadata(call: ast.Call) -> dict[str, str]:
    metadata = metadata_dict(call)
    parsed: dict[str, str] = {}
    for key_node, value_node in zip(metadata.keys, metadata.values):
        key = constant_string(key_node)
        value = constant_string(value_node)
        assert key is not None, f"metadata key must be a string literal at line {call.lineno}"
        assert value is not None, f"metadata value for {key!r} must be a string literal at line {call.lineno}"
        assert key in ALLOWED_METADATA_KEYS, f"metadata key {key!r} is not allowed at line {call.lineno}"
        assert key not in parsed, f"metadata key {key!r} duplicated at line {call.lineno}"
        lowered = f"{key} {value}".lower()
        leaked_tokens = sorted(token for token in SENSITIVE_METADATA_TOKENS if token in lowered)
        assert not leaked_tokens, f"sensitive metadata token(s) {leaked_tokens} at line {call.lineno}"
        parsed[key] = value
    assert set(parsed) == ALLOWED_METADATA_KEYS, f"metadata keys mismatch at line {call.lineno}: {sorted(parsed)}"
    assert parsed["outcome"] == "failure", f"outcome must be failure at line {call.lineno}"
    return parsed


def st_ui_method(call: ast.Call) -> str | None:
    name = call_name(call.func)
    if name == "st.error":
        return "error"
    if name == "st.warning":
        return "warning"
    return None


def user_error_reference_arg(call: ast.Call) -> str | None:
    if call_name(call.func) != "user_error_message" or len(call.args) != 1:
        return None
    if isinstance(call.args[0], ast.Name):
        return call.args[0].id
    return None


def assert_ui_uses_safe_message(handler: ast.ExceptHandler, reference_name: str) -> str:
    matched_methods = []
    for node in ast.walk(handler):
        if not isinstance(node, ast.Call):
            continue
        method = st_ui_method(node)
        if method is None:
            continue
        assert not any(contains_name(arg, "exc") for arg in node.args), (
            f"raw exception passed to st.{method} at line {node.lineno}"
        )
        uses_reference = any(user_error_reference_arg(arg) == reference_name for arg in node.args)
        assert uses_reference, f"st.{method} must display user_error_message({reference_name}) at line {node.lineno}"
        matched_methods.append(method)
    assert matched_methods, f"no st.error/st.warning found for {reference_name} in handler at line {handler.lineno}"
    assert len(matched_methods) == 1, f"expected one UI call in handler at line {handler.lineno}"
    return matched_methods[0]


def log_exception_calls(node: ast.AST) -> list[ast.Call]:
    return [
        child
        for child in ast.walk(node)
        if isinstance(child, ast.Call) and call_name(child.func) == "log_exception"
    ]


def test_allowed_files_import_logging_helpers() -> None:
    for relative_path in TARGET_FILES:
        tree = parse_source(relative_path)
        imported_names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "app_logging":
                imported_names.update(alias.name for alias in node.names)
        assert {"log_exception", "user_error_message"} <= imported_names, relative_path


def test_error_boundaries_use_approved_events_and_safe_ui_messages() -> None:
    observed: dict[tuple[str, str, str], int] = {}
    for relative_path in TARGET_FILES:
        tree = parse_source(relative_path)
        for handler in (node for node in ast.walk(tree) if isinstance(node, ast.ExceptHandler)):
            calls = log_exception_calls(handler)
            if not calls:
                continue
            assert len(calls) == 1, f"duplicate log_exception in {relative_path}:{handler.lineno}"
            call = calls[0]
            assert len(call.args) >= 2 and isinstance(call.args[1], ast.Name) and call.args[1].id == "exc"
            event = constant_string(call.args[0])
            assert event is not None, f"event must be a string literal at {relative_path}:{call.lineno}"
            assert event in APPROVED_EVENTS, f"event {event!r} is not approved at {relative_path}:{call.lineno}"
            assert EVENT_PATTERN.fullmatch(event), f"event {event!r} violates event format"
            assert_safe_metadata(call)

            reference_names = [
                node.targets[0].id
                for node in handler.body
                if isinstance(node, ast.Assign)
                and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and node.value is call
            ]
            assert reference_names, f"log_exception result must be assigned at {relative_path}:{call.lineno}"
            ui_method = assert_ui_uses_safe_message(handler, reference_names[0])
            observed[(relative_path, event, ui_method)] = observed.get((relative_path, event, ui_method), 0) + 1

    assert observed == EXPECTED_BOUNDARIES


def test_no_raw_exception_message_in_streamlit_error_or_warning() -> None:
    for relative_path in TARGET_FILES:
        tree = parse_source(relative_path)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or st_ui_method(node) is None:
                continue
            assert not any(contains_name(arg, "exc") for arg in node.args), (
                f"raw exc leaked to UI in {relative_path}:{node.lineno}"
            )
            assert not any(call_name(child.func) in {"str", "repr"} and contains_name(child, "exc") for child in ast.walk(node) if isinstance(child, ast.Call))


def test_metadata_remains_static_and_non_sensitive() -> None:
    for relative_path in TARGET_FILES:
        tree = parse_source(relative_path)
        for call in log_exception_calls(tree):
            metadata = assert_safe_metadata(call)
            assert metadata["page"] in {"login", "import_excel", "manual_order"}
            assert metadata["component"] in {"auth", "excel_import", "manual_order"}


def test_no_forbidden_runtime_helpers_added_to_phase2_files() -> None:
    for relative_path in TARGET_FILES:
        tree = parse_source(relative_path)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = call_name(node.func)
                assert name != "st.exception", f"st.exception added in {relative_path}:{node.lineno}"
                assert name != "print", f"print added in {relative_path}:{node.lineno}"
            if isinstance(node, ast.Import):
                assert all(alias.name != "traceback" for alias in node.names), relative_path
            if isinstance(node, ast.ImportFrom):
                assert node.module != "traceback", relative_path


def test_phase2_static_tests_do_not_import_runtime_modules() -> None:
    source = Path(__file__).read_text(encoding="utf-8")
    runtime_modules = ("auth_utils", "ui.import_excel_ui", "ui.manual_order_ui")
    forbidden_imports = (
        *(f"import {module}" for module in runtime_modules),
        *(f"from {module}" for module in runtime_modules),
    )
    for forbidden in forbidden_imports:
        assert forbidden not in source


if __name__ == "__main__":
    tests = [
        test_allowed_files_import_logging_helpers,
        test_error_boundaries_use_approved_events_and_safe_ui_messages,
        test_no_raw_exception_message_in_streamlit_error_or_warning,
        test_metadata_remains_static_and_non_sensitive,
        test_no_forbidden_runtime_helpers_added_to_phase2_files,
        test_phase2_static_tests_do_not_import_runtime_modules,
    ]
    for test in tests:
        test()
    print(f"{len(tests)} phase2 static tests passed")
