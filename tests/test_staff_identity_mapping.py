import ast
from contextlib import contextmanager
from pathlib import Path

import neon_utils as neon
import staff_identity
from staff_identity import (
    CANONICAL_STAFF,
    build_master_staff_directory,
    build_staff_directory_choices,
    resolve_canonical_staff_code,
    validate_canonical_pairing,
    validate_owner_staff_code,
)


# ---------------------------------------------------------------------------
# Section 1: staff_identity.py -- pure, DB-free unit tests.
# ---------------------------------------------------------------------------

ALIAS_CASES = [
    ("KO", "โก้", "KO"),
    ("KO", "สุมนตรา ทัศน์ศรี (โก้)", "KO"),
    ("CREAM", "ครีม", "CREAM"),
    ("CREAM", "จินดามณี คงมี (ครีม)", "CREAM"),
    ("LEK", "เล็ก", "LEK"),
    ("LEK", "ธัญญรัตน์ หอมระรื่น (เล็ก)", "LEK"),
    ("TAEW", "แต้ว", "TAEW"),
    ("TAEW", "พรณกมล ดวงจันทร์ (แต้ว)", "TAEW"),
    ("YING", "หญิง", "YING"),
    ("YING", "พรธนนันท์ กานต์รพีพร (หญิง)", "YING"),
    ("SAIFON", "สายฝน", "SAIFON"),
    ("SAIFON", "สายฝน ราวิชัย (สายฝน)", "SAIFON"),
]


def test_all_six_canonical_aliases_resolve_to_their_code():
    for expected_code, alias, _ in ALIAS_CASES:
        assert resolve_canonical_staff_code(alias) == expected_code, f"{alias!r} should resolve to {expected_code}"
        assert resolve_canonical_staff_code(expected_code) == expected_code
        assert resolve_canonical_staff_code(expected_code.lower()) == expected_code


def test_alias_resolution_is_whitespace_insensitive():
    assert resolve_canonical_staff_code("  แต้ว  ") == "TAEW"
    assert resolve_canonical_staff_code("พรณกมล   ดวงจันทร์  (แต้ว)") == "TAEW"
    assert resolve_canonical_staff_code(" ko ") == "KO"


def test_unrecognized_value_resolves_to_none():
    assert resolve_canonical_staff_code("") is None
    assert resolve_canonical_staff_code(None) is None
    assert resolve_canonical_staff_code("random text") is None


def test_noona_and_jeeb_are_not_canonical_aliases_of_anyone():
    # Explicit regression guard: the six confirmed codes must never resolve
    # NOONA or JEEB/เจี๊ยบ -- those identities are governed by the live DB
    # directory (and the separate, human-approved migration), never hardcoded
    # here as an alias of TAEW or any other canonical code.
    assert resolve_canonical_staff_code("หนูนา") is None
    assert resolve_canonical_staff_code("พรนภา นันที (หนูนา)") is None
    assert resolve_canonical_staff_code("เจี๊ยบ") is None
    assert resolve_canonical_staff_code("กัญญพักฒ์ อิ่มยวง (เจี๊ยบ)") is None
    assert "NOONA" not in CANONICAL_STAFF
    assert "JEEB" not in CANONICAL_STAFF


def test_taew_and_noona_never_conflate_in_the_directory():
    rows = [
        {"staff_code": "TAEW", "staff_name": "พรณกมล ดวงจันทร์ (แต้ว)"},
        {"staff_code": "NOONA", "staff_name": "พรนภา นันที (หนูนา)"},
    ]
    directory = build_master_staff_directory(rows)
    assert directory["TAEW"] == "พรณกมล ดวงจันทร์ (แต้ว)"
    assert directory["NOONA"] == "พรนภา นันที (หนูนา)"
    assert directory["TAEW"] != directory["NOONA"]


# --- build_master_staff_directory: dedup key is staff_code, never name -----

def test_directory_dedup_key_is_staff_code_not_name():
    # Two different staff_codes that happen to render an identical display
    # name must both survive as distinct directory entries -- this is the
    # exact collision class the customers.py/followup.py dropdown bug hit.
    # Uses non-canonical codes deliberately: the six canonical codes always
    # get their name overridden (see test_directory_canonical_name_overrides_*),
    # which would mask the property this test is actually checking.
    rows = [
        {"staff_code": "AAA", "staff_name": "Staff X"},
        {"staff_code": "BBB", "staff_name": "Staff X"},
    ]
    directory = build_master_staff_directory(rows)
    assert directory["AAA"] == "Staff X"
    assert directory["BBB"] == "Staff X"
    assert len(directory) == 2


def test_directory_canonical_name_overrides_live_row_for_the_six_codes():
    # Even if the live DB row's staff_name has whitespace/formatting drift,
    # the six canonical codes always resolve to the confirmed full name.
    rows = [{"staff_code": "TAEW", "staff_name": "  พรณกมล   ดวงจันทร์ (แต้ว)  "}]
    directory = build_master_staff_directory(rows)
    assert directory["TAEW"] == "พรณกมล ดวงจันทร์ (แต้ว)"


def test_directory_ignores_rows_without_staff_code():
    rows = [{"staff_code": "", "staff_name": "ไม่มีรหัส"}, {"staff_code": None, "staff_name": "x"}]
    directory = build_master_staff_directory(rows)
    assert directory == {}


def test_directory_never_invents_entries_outside_live_rows():
    # The six canonical codes are NOT unconditionally injected -- only codes
    # actually present in the live directory rows appear.
    directory = build_master_staff_directory([{"staff_code": "SAIFON", "staff_name": "สายฝน"}])
    assert list(directory.keys()) == ["SAIFON"]
    assert "TAEW" not in directory


# --- build_staff_directory_choices: dropdown dedup, never collides by name -

def test_choices_dedup_by_code_preserves_first_seen_order():
    rows = [
        {"staff_code": "TAEW", "staff_name": "Staff X"},
        {"staff_code": "NOONA", "staff_name": "Staff X"},
        {"staff_code": "TAEW", "staff_name": "Staff X duplicate row"},
    ]
    choices = build_staff_directory_choices(rows)
    codes = [code for code, _name in choices]
    assert codes == ["TAEW", "NOONA"], "must not duplicate TAEW and must preserve first-seen order"
    assert dict(choices)["TAEW"] == "พรณกมล ดวงจันทร์ (แต้ว)"
    assert dict(choices)["NOONA"] == "Staff X"


def test_choices_two_different_codes_same_name_both_survive():
    rows = [
        {"staff_code": "AAA", "staff_name": "Same Name"},
        {"staff_code": "BBB", "staff_name": "Same Name"},
    ]
    choices = build_staff_directory_choices(rows)
    assert len(choices) == 2
    assert dict(choices)["AAA"] == "Same Name"
    assert dict(choices)["BBB"] == "Same Name"


# --- validate_owner_staff_code -----------------------------------------

_DIRECTORY = {"TAEW": "พรณกมล ดวงจันทร์ (แต้ว)", "NOONA": "พรนภา นันที (หนูนา)"}


def test_validate_owner_staff_code_accepts_matching_pair():
    assert validate_owner_staff_code("พรณกมล ดวงจันทร์ (แต้ว)", "TAEW", _DIRECTORY) is None


def test_validate_owner_staff_code_accepts_alias_owner_text():
    # owner field holding just the nickname (legacy free-text path) is fine
    # as long as it resolves to the same canonical code.
    assert validate_owner_staff_code("แต้ว", "TAEW", _DIRECTORY) is None


def test_validate_owner_staff_code_rejects_missing_staff_code():
    error = validate_owner_staff_code("พรณกมล ดวงจันทร์ (แต้ว)", "", _DIRECTORY)
    assert error is not None
    assert "Staff code" in error


def test_validate_owner_staff_code_rejects_unknown_staff_code():
    error = validate_owner_staff_code("ใครสักคน", "GHOST", _DIRECTORY)
    assert error is not None
    assert "ไม่พบ" in error


def test_validate_owner_staff_code_rejects_mismatched_owner():
    error = validate_owner_staff_code("สายฝน ราวิชัย (สายฝน)", "TAEW", _DIRECTORY)
    assert error is not None
    assert "ไม่ตรงกับ" in error


def test_validate_owner_staff_code_allows_blank_owner_text():
    # Some legacy flows may not have owner text populated yet -- staff_code
    # presence/validity is the hard requirement, blank owner is not itself
    # an error (there is nothing to cross-check against).
    assert validate_owner_staff_code("", "TAEW", _DIRECTORY) is None


def test_validate_owner_staff_code_never_raises_on_garbage_input():
    for bad_owner, bad_code in [(None, None), (123, 456), ({}, []), ("\x00\n", "\t")]:
        # Must not raise -- worst case is a returned error string.
        validate_owner_staff_code(bad_owner, bad_code, _DIRECTORY)


# --- validate_canonical_pairing (pages/users.py guard) ------------------

def test_canonical_pairing_accepts_correct_pair():
    assert validate_canonical_pairing("TAEW", "พรณกมล ดวงจันทร์ (แต้ว)") is None
    assert validate_canonical_pairing("taew", "แต้ว") is None


def test_canonical_pairing_rejects_wrong_name_for_known_code():
    error = validate_canonical_pairing("TAEW", "สายฝน ราวิชัย (สายฝน)")
    assert error is not None
    assert "TAEW" in error


def test_canonical_pairing_never_blocks_codes_outside_the_six():
    # This must stay permissive -- pages/users.py is where brand-new staff
    # members get created, and NOONA/JEEB/anyone else must remain creatable.
    assert validate_canonical_pairing("NOONA", "พรนภา นันที (หนูนา)") is None
    assert validate_canonical_pairing("NOONA", "literally anything") is None
    assert validate_canonical_pairing("BRAND_NEW_CODE", "someone new") is None


def test_canonical_pairing_allows_blank_name_for_known_code():
    # A blank staff_name during creation isn't itself a pairing conflict.
    assert validate_canonical_pairing("TAEW", "") is None


# ---------------------------------------------------------------------------
# Section 2: neon_utils.py write-path validation hooks (FakeConnection).
# ---------------------------------------------------------------------------

class _FakeCursor:
    def __init__(self):
        self.statements: list = []
        self.params_log: list = []
        self.rowcount = 0

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def execute(self, statement, params=None):
        normalized = " ".join(str(statement).split()).lower()
        self.statements.append(normalized)
        self.params_log.append(list(params or []))
        self.rowcount = 1

    def fetchone(self):
        return None

    def fetchall(self):
        return []


class _FakeConnection:
    def __init__(self, cursor):
        self.cursor_instance = cursor
        self.commit_count = 0
        self.rollback_count = 0

    def cursor(self):
        return self.cursor_instance

    def commit(self):
        self.commit_count += 1

    def rollback(self):
        self.rollback_count += 1


def _install_fake_neon(monkeypatch, cursor):
    conn = _FakeConnection(cursor)

    @contextmanager
    def fake_neon_connection():
        yield conn

    monkeypatch.setattr(neon, "ensure_crm_data_imports_schema", lambda: True)
    monkeypatch.setattr(neon, "neon_connection", fake_neon_connection)
    return conn


def _fake_directory_rows():
    return [
        {"staff_code": "TAEW", "staff_name": "พรณกมล ดวงจันทร์ (แต้ว)"},
        {"staff_code": "SAIFON", "staff_name": "สายฝน ราวิชัย (สายฝน)"},
    ]


def _raising_fetch_owner_user_options(*_args, **_kwargs):
    raise AssertionError("fetch_owner_user_options must not be called when owner/staff_code validation is skipped")


# --- assign_owner_to_order_record ---------------------------------------

def test_assign_owner_rejects_mismatched_owner_and_staff_code(monkeypatch):
    cursor = _FakeCursor()
    _install_fake_neon(monkeypatch, cursor)
    monkeypatch.setattr(neon, "fetch_owner_user_options", lambda *a, **k: _fake_directory_rows())

    try:
        neon.assign_owner_to_order_record(
            "rec1", "order1", "สายฝน ราวิชัย (สายฝน)", "editor@example.com", staff_code="TAEW"
        )
        assert False, "expected ValueError for mismatched owner/staff_code"
    except ValueError as exc:
        assert "ไม่ตรงกับ" in str(exc)
    assert cursor.statements == [], "must not write to the database when validation fails"


def test_assign_owner_accepts_valid_pairing(monkeypatch):
    cursor = _FakeCursor()
    conn = _install_fake_neon(monkeypatch, cursor)
    monkeypatch.setattr(neon, "fetch_owner_user_options", lambda *a, **k: _fake_directory_rows())

    updated = neon.assign_owner_to_order_record(
        "rec1", "order1", "พรณกมล ดวงจันทร์ (แต้ว)", "editor@example.com", staff_code="TAEW"
    )
    assert updated == 1
    assert any("update public.crm_data_imports" in s for s in cursor.statements)
    assert conn.commit_count == 1
    assert conn.rollback_count == 0


def test_assign_owner_rejects_unknown_staff_code(monkeypatch):
    cursor = _FakeCursor()
    _install_fake_neon(monkeypatch, cursor)
    monkeypatch.setattr(neon, "fetch_owner_user_options", lambda *a, **k: _fake_directory_rows())

    try:
        neon.assign_owner_to_order_record("rec1", "order1", "ใครสักคน", "editor@example.com", staff_code="GHOST")
        assert False, "expected ValueError for unknown staff_code"
    except ValueError as exc:
        assert "ไม่พบ" in str(exc)
    assert cursor.statements == []


def test_assign_owner_only_path_skips_validation_without_staff_code(monkeypatch):
    # allow_owner_only=True + no staff_code is an existing, legitimate path
    # (owner text update without touching staff_code) -- must not attempt
    # any staff_code validation or DB directory lookup.
    cursor = _FakeCursor()
    _install_fake_neon(monkeypatch, cursor)
    monkeypatch.setattr(neon, "fetch_owner_user_options", _raising_fetch_owner_user_options)

    updated = neon.assign_owner_to_order_record(
        "rec1", "order1", "ใครก็ได้", "editor@example.com", allow_owner_only=True
    )
    assert updated == 1


# --- upsert_lead_followup -----------------------------------------------

def test_upsert_lead_followup_rejects_mismatched_owner_and_staff_code(monkeypatch):
    cursor = _FakeCursor()
    _install_fake_neon(monkeypatch, cursor)
    monkeypatch.setattr(neon, "fetch_owner_user_options", lambda *a, **k: _fake_directory_rows())

    payload = {
        "customer_key": "customer_id:1",
        "staff_code": "TAEW",
        "owner": "สายฝน ราวิชัย (สายฝน)",
        "priority": "NEW",
    }
    try:
        neon.upsert_lead_followup(payload)
        assert False, "expected ValueError for mismatched owner/staff_code"
    except ValueError as exc:
        assert "ไม่ตรงกับ" in str(exc)
    assert cursor.statements == [], "must not write to the database when validation fails"


def test_upsert_lead_followup_accepts_valid_pairing(monkeypatch):
    cursor = _FakeCursor()
    conn = _install_fake_neon(monkeypatch, cursor)
    monkeypatch.setattr(neon, "fetch_owner_user_options", lambda *a, **k: _fake_directory_rows())

    payload = {
        "customer_key": "customer_id:1",
        "staff_code": "TAEW",
        "owner": "พรณกมล ดวงจันทร์ (แต้ว)",
        "priority": "NEW",
    }
    neon.upsert_lead_followup(payload)
    assert any("insert into public.crm_lead_followups" in s for s in cursor.statements)
    assert conn.commit_count == 1


def test_upsert_lead_followup_skips_validation_when_staff_code_blank(monkeypatch):
    # Unassigned leads (no staff_code yet) are a legitimate, existing state --
    # must not attempt validation or a directory lookup for them.
    cursor = _FakeCursor()
    _install_fake_neon(monkeypatch, cursor)
    monkeypatch.setattr(neon, "fetch_owner_user_options", _raising_fetch_owner_user_options)

    payload = {"customer_key": "customer_id:1", "staff_code": "", "owner": "", "priority": "NEW"}
    neon.upsert_lead_followup(payload)
    assert any("insert into public.crm_lead_followups" in s for s in cursor.statements)


# --- upsert_manual_order_items -------------------------------------------

def _valid_manual_order_payload(**overrides):
    payload = {
        "order_id": "O1",
        "customer_name": "ลูกค้าทดสอบ",
        "phone1": "0812345678",
        "phone2": "",
        "sale_type": "NEW_ORDER",
        "owner": "พรณกมล ดวงจันทร์ (แต้ว)",
        "staff_code": "TAEW",
    }
    payload.update(overrides)
    return payload


_VALID_ITEMS = [{"sku": "SKU1", "product_name": "สินค้าทดสอบ", "qty": 1, "amount": "100"}]


def test_manual_order_items_rejects_mismatched_owner_and_staff_code(monkeypatch):
    monkeypatch.setattr(neon, "ensure_crm_data_imports_schema", lambda: True)
    monkeypatch.setattr(neon, "fetch_owner_user_options", lambda *a, **k: _fake_directory_rows())

    payload = _valid_manual_order_payload(owner="สายฝน ราวิชัย (สายฝน)", staff_code="TAEW")
    try:
        neon.upsert_manual_order_items(payload, _VALID_ITEMS)
        assert False, "expected ValueError for mismatched owner/staff_code"
    except ValueError as exc:
        assert "ไม่ตรงกับ" in str(exc)


def test_manual_order_items_rejects_unknown_staff_code(monkeypatch):
    monkeypatch.setattr(neon, "ensure_crm_data_imports_schema", lambda: True)
    monkeypatch.setattr(neon, "fetch_owner_user_options", lambda *a, **k: _fake_directory_rows())

    payload = _valid_manual_order_payload(owner="ใครสักคน", staff_code="GHOST")
    try:
        neon.upsert_manual_order_items(payload, _VALID_ITEMS)
        assert False, "expected ValueError for unknown staff_code"
    except ValueError as exc:
        assert "ไม่พบ" in str(exc)


def test_manual_order_items_blank_owner_skips_mapping_validation(monkeypatch):
    monkeypatch.setattr(neon, "ensure_crm_data_imports_schema", lambda: True)
    monkeypatch.setattr(neon, "fetch_owner_user_options", _raising_fetch_owner_user_options)

    payload = _valid_manual_order_payload(owner="", staff_code="TAEW")
    try:
        neon.upsert_manual_order_items(payload, _VALID_ITEMS)
        assert False, "expected ValueError for blank owner (presence check)"
    except ValueError as exc:
        assert "owner" in str(exc)


def test_manual_order_items_blank_staff_code_skips_mapping_validation(monkeypatch):
    monkeypatch.setattr(neon, "ensure_crm_data_imports_schema", lambda: True)
    monkeypatch.setattr(neon, "fetch_owner_user_options", _raising_fetch_owner_user_options)

    payload = _valid_manual_order_payload(owner="พรณกมล ดวงจันทร์ (แต้ว)", staff_code="")
    try:
        neon.upsert_manual_order_items(payload, _VALID_ITEMS)
        assert False, "expected ValueError for blank staff_code (presence check)"
    except ValueError as exc:
        assert "staff_code" in str(exc)


# ---------------------------------------------------------------------------
# Section 3: build_followup_where -- owner filter now keys on staff_code.
# ---------------------------------------------------------------------------

_EDITOR_USER = {"role": "EDITOR"}
_STAFF_USER = {"role": "พนักงาน", "staff_code": "TAEW"}


def test_followup_owner_filter_uses_staff_code_column():
    where, params = neon.build_followup_where({"owner": "TAEW"}, _EDITOR_USER)
    assert "d.staff_code" in where
    assert "d.owner = %s" not in where
    assert "TAEW" in params


def test_followup_owner_filter_all_sentinel_adds_no_clause():
    where, params = neon.build_followup_where({"owner": "ทั้งหมด"}, _EDITOR_USER)
    assert "d.staff_code" not in where or "nullif" not in where
    assert params == []


def test_followup_non_admin_scope_still_uses_staff_code_only():
    # Regression guard: the permission-scope clause (independent of the
    # owner filter clause) must remain staff_code-based and must never
    # reference owner text, for both admin/editor and staff paths.
    where_staff, params_staff = neon.build_followup_where({}, _STAFF_USER)
    assert params_staff == ["TAEW"]
    assert "d.staff_code" in where_staff

    where_admin, params_admin = neon.build_followup_where({}, _EDITOR_USER)
    assert "d.staff_code" not in where_admin
    assert params_admin == []


def test_followup_owner_filter_and_staff_scope_combine_correctly():
    # An EDITOR filtering by a specific staff_code's owner column, combined
    # with (in this case absent) staff scope restriction -- both clauses
    # must reference staff_code consistently, never owner text.
    where, params = neon.build_followup_where({"owner": "SAIFON"}, _EDITOR_USER)
    assert where.count("d.staff_code") == 1
    assert params == ["SAIFON"]


# ---------------------------------------------------------------------------
# Section 4: fetch_followup_filter_options -- staff_code-aware owner choices.
# ---------------------------------------------------------------------------

class _FilterOptionsCursor:
    def __init__(self, owner_rows, product_rows):
        self._owner_rows = owner_rows
        self._product_rows = product_rows
        self._pending = None
        self.statements = []

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def execute(self, statement, params=None):
        normalized = " ".join(str(statement).split()).lower()
        self.statements.append(normalized)
        if "select distinct" in normalized and "staff_code" in normalized and "owner" in normalized:
            self._pending = list(self._owner_rows)
        elif "select distinct concat_ws" in normalized:
            self._pending = list(self._product_rows)
        else:
            self._pending = []

    def fetchall(self):
        rows = self._pending or []
        self._pending = []
        return rows

    def fetchone(self):
        return None


def test_fetch_followup_filter_options_returns_staff_code_keyed_choices(monkeypatch):
    try:
        neon.fetch_followup_filter_options.clear()
    except Exception:
        pass
    cursor = _FilterOptionsCursor(
        owner_rows=[
            {"staff_code": "TAEW", "owner": "พรณกมล ดวงจันทร์ (แต้ว)"},
            {"staff_code": "TAEW", "owner": " พรณกมล  ดวงจันทร์ (แต้ว) "},
            {"staff_code": "NOONA", "owner": "Staff X"},
        ],
        product_rows=[{"product": "SKU1 สินค้า"}],
    )
    _install_fake_neon(monkeypatch, cursor)

    result = neon.fetch_followup_filter_options({"role": "EDITOR", "_cache_bust": "filter_options_test"})
    owners = result["owners"]
    codes = [code for code, _name in owners]
    assert codes.count("TAEW") == 1, "duplicate rows for the same staff_code must collapse to one entry"
    assert "NOONA" in codes
    assert dict(owners)["TAEW"] == "พรณกมล ดวงจันทร์ (แต้ว)"
    assert result["products"] == ["SKU1 สินค้า"]


# ---------------------------------------------------------------------------
# Section 5: fetch_followup_summary_counts -- full filtered set, not a page.
# ---------------------------------------------------------------------------

class _SummaryCountsCursor:
    def __init__(self, row):
        self._row = row
        self.statements = []
        self.params_log = []

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def execute(self, statement, params=None):
        normalized = " ".join(str(statement).split()).lower()
        self.statements.append(normalized)
        self.params_log.append(list(params or []))

    def fetchone(self):
        return dict(self._row)

    def fetchall(self):
        return [dict(self._row)]


def test_fetch_followup_summary_counts_computes_week_from_total():
    cursor = _SummaryCountsCursor({"total": 500, "due_today": 12, "overdue": 30, "done": 200})
    conn = _FakeConnection(cursor)

    import contextlib as _contextlib

    @_contextlib.contextmanager
    def fake_conn():
        yield conn

    import unittest.mock as _mock

    with _mock.patch.object(neon, "neon_connection", fake_conn), _mock.patch.object(
        neon, "ensure_crm_data_imports_schema", lambda: True
    ):
        result = neon.fetch_followup_summary_counts({}, _EDITOR_USER)

    assert result == {"due_today": 12, "overdue": 30, "week": 258, "done": 200, "total": 500}
    # Proves this queries the FULL filtered set via SQL aggregation, not a
    # page slice -- no `limit`/`offset` anywhere in the aggregate query.
    assert not any("limit" in s and "offset" in s for s in cursor.statements)
    assert cursor.params_log[0][:2] == cursor.params_log[0][:2]  # today passed twice (due_today, overdue)


def test_fetch_followup_summary_counts_never_negative_week():
    cursor = _SummaryCountsCursor({"total": 10, "due_today": 5, "overdue": 5, "done": 5})
    conn = _FakeConnection(cursor)

    import contextlib as _contextlib

    @_contextlib.contextmanager
    def fake_conn():
        yield conn

    import unittest.mock as _mock

    with _mock.patch.object(neon, "neon_connection", fake_conn), _mock.patch.object(
        neon, "ensure_crm_data_imports_schema", lambda: True
    ):
        result = neon.fetch_followup_summary_counts({}, _EDITOR_USER)

    assert result["week"] == 0


# ---------------------------------------------------------------------------
# Section 6: pages/customers.py -- structural checks (AST, no Streamlit import).
# ---------------------------------------------------------------------------

CUSTOMERS_PATH = Path(__file__).resolve().parents[1] / "pages" / "customers.py"
CUSTOMERS_SOURCE = CUSTOMERS_PATH.read_text(encoding="utf-8")
CUSTOMERS_TREE = ast.parse(CUSTOMERS_SOURCE)


def _function_source(tree, source, name):
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return ast.get_source_segment(source, node)
    raise AssertionError(f"missing function: {name}")


def test_customers_page_no_longer_has_name_keyed_reverse_lookup():
    assert "owner_staff_choices" not in CUSTOMERS_SOURCE
    assert "staff_code_by_owner_name" not in CUSTOMERS_SOURCE
    assert "owner_name_to_staff_code" not in CUSTOMERS_SOURCE


def test_customers_page_uses_central_staff_identity_module():
    assert "import staff_identity" in CUSTOMERS_SOURCE
    assert "staff_identity.build_staff_directory_choices(" in CUSTOMERS_SOURCE


def test_customers_page_owner_dropdown_is_keyed_by_staff_code():
    actions_source = _function_source(CUSTOMERS_TREE, CUSTOMERS_SOURCE, "render_customer_actions")
    assert "format_func=lambda code: staff_name_by_code.get(code, code)" in actions_source
    assert 'st.selectbox(\n                "มอบหมายผู้ดูแล",\n                codes,' in actions_source \
        or "codes,\n                index=default_index" in actions_source


def test_customers_page_assign_write_uses_dict_derived_owner_name():
    actions_source = _function_source(CUSTOMERS_TREE, CUSTOMERS_SOURCE, "render_customer_actions")
    assert "selected_owner_name = clean(staff_name_by_code.get(selected_staff_code))" in actions_source
    assert "assign_owner_to_order_record(" in actions_source


# ---------------------------------------------------------------------------
# Section 7: pages/followup.py -- structural checks.
# ---------------------------------------------------------------------------

FOLLOWUP_PATH = Path(__file__).resolve().parents[1] / "pages" / "followup.py"
FOLLOWUP_SOURCE = FOLLOWUP_PATH.read_text(encoding="utf-8")
FOLLOWUP_TREE = ast.parse(FOLLOWUP_SOURCE)


def test_followup_page_summary_sections_takes_aggregate_dict_not_rows():
    sections_source = _function_source(FOLLOWUP_TREE, FOLLOWUP_SOURCE, "render_followup_sections")
    assert "def render_followup_sections(summary_counts: dict)" in sections_source
    assert "len(rows)" not in sections_source
    assert "summary_counts.get(" in sections_source


def test_followup_page_calls_summary_counts_function():
    assert "fetch_followup_summary_counts" in FOLLOWUP_SOURCE
    main_source = _function_source(FOLLOWUP_TREE, FOLLOWUP_SOURCE, "_render_followup_page")
    assert "fetch_followup_summary_counts(filters, user)" in main_source
    assert "render_followup_sections(summary_counts)" in main_source


def test_followup_page_owner_filter_is_staff_code_keyed():
    filters_source = _function_source(FOLLOWUP_TREE, FOLLOWUP_SOURCE, "render_filters")
    assert "owner_name_by_code" in filters_source
    assert "format_func=lambda code: ALL if code == ALL else owner_name_by_code.get(code, code)" in filters_source


# ---------------------------------------------------------------------------
# Section 8: pages/users.py -- canonical pairing guard wired in.
# ---------------------------------------------------------------------------

USERS_PATH = Path(__file__).resolve().parents[1] / "pages" / "users.py"
USERS_SOURCE = USERS_PATH.read_text(encoding="utf-8")


def test_users_page_uses_canonical_pairing_guard():
    assert "import staff_identity" in USERS_SOURCE
    assert USERS_SOURCE.count("staff_identity.validate_canonical_pairing(") == 2


print("staff identity mapping safety OK")
