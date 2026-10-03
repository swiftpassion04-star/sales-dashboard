"""Ownership runs on two sides: the CRM team, and Upsell plus "no team yet".

CRM may not collide with CRM over a linked phone group; the open side is never
blocked and never overwrites the CRM owner. The customer directory therefore
shows one entry per customer per side.

No pytest in this environment -- discovered via the repo's stdlib test_*
runner, same as every other tests/test_*.py file here.
"""

import inspect
import sys
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import neon_utils as neon


CRM = neon.OWNERSHIP_SIDE_CRM
OPEN = neon.OWNERSHIP_SIDE_OPEN


def row(**overrides) -> dict:
    base = {
        "id": "10",
        "order_id": "ORDER-10",
        "owner": "CRM Owner A",
        "staff_code": "CRMA",
        "uploaded_by": "a@example.com",
        "current_team_code": "CRM_TEAM",
        "matched_phone": "0812345678",
        "order_date": "2026-08-01",
        "uploaded_at": "2026-08-01",
    }
    base.update(overrides)
    return base


class FakeCursor:
    """Models the one contract the lock query relies on: only rows on the
    requested ownership side come back, newest first."""

    def __init__(self, rows):
        self.rows = list(rows)
        self.statement = ""
        self.params = []
        self.side = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, statement, params=None):
        self.statement = " ".join(statement.split()).lower()
        self.params = list(params or [])
        self.side = self.params[-1] if self.params and self.params[-1] in (CRM, OPEN) else None

    def _visible(self):
        rows = self.rows
        if self.side:
            want_crm = self.side == CRM
            rows = [
                r for r in rows
                if (neon.normalize_team_code(r.get("current_team_code")) == neon.CRM_TEAM_CODE) == want_crm
            ]
        return sorted(rows, key=lambda r: (r.get("order_date") or "", r.get("uploaded_at") or "", int(r["id"])), reverse=True)

    def fetchone(self):
        rows = self._visible()
        return rows[0] if rows else None

    def fetchall(self):
        return self._visible()


class FakeConnection:
    def __init__(self, rows):
        self.cursor_instance = FakeCursor(rows)

    def cursor(self):
        return self.cursor_instance


@contextmanager
def _patched(rows, team_code=None):
    saved = (neon.neon_connection, neon.ensure_crm_data_imports_schema, neon.fetch_current_user_team_code)
    connection = FakeConnection(rows)

    @contextmanager
    def fake_connection():
        yield connection

    neon.neon_connection = fake_connection
    neon.ensure_crm_data_imports_schema = lambda: None
    neon.fetch_current_user_team_code = lambda email: team_code
    try:
        yield connection
    finally:
        (neon.neon_connection, neon.ensure_crm_data_imports_schema, neon.fetch_current_user_team_code) = saved


def lock_for(rows, owner="CRM Owner B", staff_code="CRMB", team_code="CRM_TEAM") -> dict:
    with _patched(rows, team_code):
        return neon.check_crm_team_duplicate_phone_lock("b@example.com", "0812345678", "", owner, staff_code)


# --- sides ---------------------------------------------------------------------

def test_crm_team_is_its_own_side_everyone_else_shares_the_open_side():
    assert neon.ownership_side_for_team("CRM_TEAM") == CRM
    assert neon.ownership_side_for_team("crm team") == CRM  # normalised
    assert neon.ownership_side_for_team("UPSELL_TEAM") == OPEN
    assert neon.ownership_side_for_team(None) == OPEN
    assert neon.ownership_side_for_team("") == OPEN
    assert neon.ownership_side_for_team("SOMETHING_ELSE") == OPEN


def test_unknown_team_falls_back_to_the_open_side_never_to_crm():
    saved = neon.fetch_current_user_team_code
    neon.fetch_current_user_team_code = lambda email: (_ for _ in ()).throw(RuntimeError("db down"))
    try:
        assert neon.ownership_side_for_user_email("x@example.com") == OPEN
    finally:
        neon.fetch_current_user_team_code = saved


# --- rule 1: CRM must not collide with CRM -------------------------------------

def test_crm_b_is_blocked_when_crm_a_owns_the_linked_group():
    result = lock_for([row()])
    assert result["allowed"] is False
    assert result["duplicate"]["owner"] == "CRM Owner A"
    message = neon.format_duplicate_phone_lock_error(result["duplicate"])
    assert "CRM Owner A" in message and "0812345678" in message


def test_crm_a_can_keep_adding_to_their_own_customer():
    assert lock_for([row()], owner="CRM Owner A", staff_code="CRMA")["allowed"] is True


def test_same_staff_code_counts_as_the_same_crm_owner():
    assert lock_for([row(owner="ครีม (CRMA)")], owner="Cream", staff_code="CRMA")["allowed"] is True


def test_a_newer_open_side_order_does_not_release_the_crm_side():
    rows = [
        row(order_date="2026-01-01"),
        row(id="20", owner="Upsell Owner", staff_code="UP01", current_team_code="UPSELL_TEAM", order_date="2026-08-01"),
        row(id="21", owner="No Team", staff_code="NT01", current_team_code=None, order_date="2026-09-01"),
    ]
    result = lock_for(rows)
    assert result["allowed"] is False
    assert result["duplicate"]["owner"] == "CRM Owner A"


def test_group_without_any_crm_row_is_open_to_crm():
    rows = [row(id="20", owner="Upsell Owner", current_team_code="UPSELL_TEAM")]
    assert lock_for(rows)["allowed"] is True


def test_lock_reads_the_whole_linked_phone_group():
    with _patched([row()], "CRM_TEAM") as connection:
        neon.check_crm_team_duplicate_phone_lock("b@example.com", "0812345678", "", "B", "CRMB")
    statement = connection.cursor_instance.statement
    assert "with recursive linked_phones as" in statement
    assert "d.phone1 = linked_phones.phone or d.phone2 = linked_phones.phone" in statement
    assert connection.cursor_instance.params[-1] == CRM


# --- rule 2: the open side is never blocked ------------------------------------

def test_upsell_can_add_to_a_customer_the_crm_team_owns():
    result = lock_for([row()], owner="Upsell Owner", staff_code="UP01", team_code="UPSELL_TEAM")
    assert result["allowed"] is True
    assert result["duplicate"] is None


def test_user_without_a_team_can_add_to_a_customer_the_crm_team_owns():
    result = lock_for([row()], owner="No Team", staff_code="NT01", team_code=None)
    assert result["allowed"] is True
    assert result["duplicate"] is None


def test_open_side_members_never_block_each_other():
    rows = [row(id="20", owner="Upsell One", staff_code="UP01", current_team_code="UPSELL_TEAM")]
    assert lock_for(rows, owner="Upsell Two", staff_code="UP02", team_code="UPSELL_TEAM")["allowed"] is True
    assert lock_for(rows, owner="No Team", staff_code="NT01", team_code=None)["allowed"] is True


# --- rule 3: the two sides keep separate owners and separate entries ------------

SAVE_SOURCE = " ".join(inspect.getsource(neon.upsert_manual_order_items).split())
DIRECTORY_SOURCE = " ".join(inspect.getsource(neon.fetch_customer_page).split())


def test_adding_an_order_only_moves_ownership_on_the_actors_own_side():
    # The bulk owner rewrite must be restricted to rows on the actor's side,
    # otherwise an Upsell order renames the CRM owner on shared phones.
    assert "actor_side = ownership_side_for_team(lock_result.get(\"team_code\"))" in SAVE_SOURCE
    update = SAVE_SOURCE.split("update public.crm_data_imports", 1)[1]
    assert "where id in ( select d.id" in update
    assert '{_order_team_joins("d")}' in update
    assert "{_ORDER_TEAM_SIDE_SQL} = %s" in update
    assert "actor_side]" in update


def test_the_save_layer_enforces_the_lock_itself_not_just_the_ui():
    assert "check_crm_team_duplicate_phone_lock(" in SAVE_SOURCE
    assert "raise ValueError(format_duplicate_phone_lock_error(" in SAVE_SOURCE
    # the check runs before any write
    assert SAVE_SOURCE.index("check_crm_team_duplicate_phone_lock(") < SAVE_SOURCE.index("update public.crm_data_imports")


def test_directory_lists_one_entry_per_customer_per_side():
    assert "partition by phone_key, team_side" in DIRECTORY_SOURCE
    assert "select distinct phone_key, team_side" in DIRECTORY_SOURCE
    assert "{_ORDER_TEAM_SIDE_SQL} as team_side" in DIRECTORY_SOURCE
    assert "ranked.team_side," in DIRECTORY_SOURCE


def test_newest_row_wins_within_a_side():
    # Per side, the current owner is the newest order on that side -- the same
    # ordering the lock uses, so the directory and the lock cannot disagree.
    assert '{_current_customer_row_order("keyed")}' in DIRECTORY_SOURCE
    assert '{_current_customer_row_order("d")}' in " ".join(
        inspect.getsource(neon.find_duplicate_valid_order_by_phones).split()
    )


def test_directory_sql_carries_the_side_split_when_executed():
    with _patched([{"total": 0, "id": "1", "order_date": "2026-08-01"}]) as connection:
        neon.fetch_customer_page({}, 10, 1, user=None, enforce_user_scope=False)
    statement = connection.cursor_instance.statement
    assert "partition by phone_key, team_side" in statement
    assert "crm_user_team_assignments" in statement
    assert "as team_side" in statement


def test_customers_page_shows_which_side_each_entry_is():
    page = (Path(__file__).resolve().parents[1] / "pages" / "customers.py").read_text(encoding="utf-8")
    assert "team_side_label(row.get(\"team_side\"))" in page
    assert "\"ทีม\"" in page
    assert "Upsell / ไม่มีทีม" in page
