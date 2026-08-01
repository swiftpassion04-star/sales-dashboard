"""Static, DB-free structural checks on neon/manual_sql/202607_jeeb_to_noona_merge.sql.

These tests only read the SQL file as text and assert about its structure
(statement order, which tables are touched, which keys the rollback plan
uses, etc.) -- they never connect to a database and never execute any SQL.
That mirrors this whole migration-rewrite phase: offline review only.
"""

import re
from pathlib import Path

SQL_PATH = (
    Path(__file__).resolve().parent.parent
    / "neon"
    / "manual_sql"
    / "202607_jeeb_to_noona_merge.sql"
)

RAW_SQL = SQL_PATH.read_text(encoding="utf-8")


def _strip_line_comments(text: str) -> str:
    """Remove everything from `--` to end-of-line, on every line.

    This file has no string literal containing `--`, so a naive per-line
    strip is safe and matches the same approach used elsewhere this session
    (see the investigation runner script) for separating "what actually
    executes" from "what is only ever discussed in a comment".
    """
    stripped_lines = [line.split("--", 1)[0] for line in text.splitlines()]
    return "\n".join(stripped_lines)


EXECUTABLE_SQL = _strip_line_comments(RAW_SQL)


def test_file_exists_and_is_non_trivial():
    assert SQL_PATH.exists()
    assert len(RAW_SQL) > 1000


def test_no_crm_orders_reference_in_executable_sql():
    # crm_orders is discussed in the header comments (explaining why it was
    # removed) but must never appear in any statement that would actually
    # run -- it does not exist in Production.
    assert "crm_orders" not in EXECUTABLE_SQL.lower()


def test_crm_orders_removal_is_documented():
    # The removal must be explained, not silent.
    assert "does not exist" in RAW_SQL.lower()
    assert "crm_orders" in RAW_SQL.lower()


def test_single_transaction_begin_and_commit():
    # Exactly one top-level transaction BEGIN and COMMIT. PL/pgSQL `begin`
    # keywords inside `do $$ ... $$` blocks never have a semicolon directly
    # after them in this file, so this regex does not confuse the two.
    begins = re.findall(r"(?im)^\s*begin\s*;\s*$", EXECUTABLE_SQL)
    commits = re.findall(r"(?im)^\s*commit\s*;\s*$", EXECUTABLE_SQL)
    assert len(begins) == 1, f"expected exactly one top-level BEGIN, found {len(begins)}"
    assert len(commits) == 1, f"expected exactly one top-level COMMIT, found {len(commits)}"


def test_writes_confined_to_four_approved_tables_and_backups():
    approved_tables = {
        "crm_data_imports",
        "crm_lead_followups",
        "crm_user_roles",
        "crm_staff_options",
    }
    backup_table_prefix = "crm_jeeb_noona_merge_backup_"

    write_stmt_re = re.compile(
        r"(?im)^\s*(update|insert into|create table)\s+public\.([a-zA-Z0-9_]+)"
    )
    touched = set()
    for match in write_stmt_re.finditer(EXECUTABLE_SQL):
        table_name = match.group(2)
        touched.add(table_name)

    assert touched, "expected to find at least one write statement"
    for table_name in touched:
        assert (
            table_name in approved_tables or table_name.startswith(backup_table_prefix)
        ), f"write statement touches unexpected table: {table_name}"

    # And every approved table must actually be written to somewhere.
    for table_name in approved_tables:
        assert table_name in touched, f"expected a write statement touching {table_name}"


def test_no_active_delete_statement():
    # The hard-delete variant must remain commented out (stripped away by
    # _strip_line_comments); only the soft-disable UPDATEs may be active.
    assert not re.search(r"(?im)^\s*delete\s+from", EXECUTABLE_SQL)
    # But the option should still be documented for a human to opt into.
    assert "hard-delete" in RAW_SQL.lower()


def test_no_dynamic_sql_execute():
    # No EXECUTE-based dynamic SQL anywhere -- preflight checks use static,
    # hardcoded table/column names with plain SELECT ... INTO, never EXECUTE
    # format(...) to paper over a schema mismatch.
    assert not re.search(r"(?im)\bexecute\s+(format|'|\")", EXECUTABLE_SQL)


def test_preflight_precedes_backup_and_update():
    preflight_pos = EXECUTABLE_SQL.find("PREFLIGHT FAILED")
    backup_pos = EXECUTABLE_SQL.find("create table public.crm_jeeb_noona_merge_backup")
    update_pos = EXECUTABLE_SQL.find("update public.crm_data_imports")
    assert preflight_pos != -1
    assert backup_pos != -1
    assert update_pos != -1
    assert preflight_pos < backup_pos < update_pos


def test_conflict_guard_present_for_owner_and_name_matches():
    assert "CONFLICT GUARD TRIPPED" in RAW_SQL
    for table in ("crm_data_imports", "crm_lead_followups", "crm_staff_options"):
        assert f"CONFLICT GUARD TRIPPED in {table}" in RAW_SQL

    conflict_pos = EXECUTABLE_SQL.find("CONFLICT GUARD TRIPPED")
    backup_pos = EXECUTABLE_SQL.find("create table public.crm_jeeb_noona_merge_backup")
    assert conflict_pos != -1 and backup_pos != -1
    assert conflict_pos < backup_pos, "conflict guard must run before any backup/update"


def test_conflict_guard_excludes_blank_and_legacy_codes():
    # The dangerous case is owner/name text matching JEEB while staff_code is
    # some OTHER real code -- blank and JEEB/เจี๊ยบ codes must be excluded
    # from being flagged as conflicts. Each of the 3 conflict-guard blocks
    # must exclude '', 'JEEB', and 'เจี๊ยบ' from its "different code" check.
    exclusion_count = len(re.findall(r"not in \('', 'JEEB', 'เจี๊ยบ'\)", RAW_SQL))
    assert exclusion_count >= 3, (
        f"expected at least 3 conflict-guard exclusion clauses, found {exclusion_count}"
    )


def test_noona_target_preflight_present():
    assert "no active NOONA entry found" in RAW_SQL


def test_pk_preflight_checks_all_four_tables_with_expected_keys():
    expected = {
        "crm_data_imports": "id",
        "crm_lead_followups": "id",
        "crm_user_roles": "email",
        "crm_staff_options": "id",
    }
    for table, key in expected.items():
        pattern = (
            rf"tc\.table_name = '{table}'.*?constraint_type = 'PRIMARY KEY'"
        )
        assert re.search(pattern, RAW_SQL, re.DOTALL), f"missing PK lookup for {table}"

    # And each has an explicit "is distinct from '<key>'" abort check.
    assert re.search(r"pk_data_imports is distinct from 'id'", RAW_SQL)
    assert re.search(r"pk_lead_followups is distinct from 'id'", RAW_SQL)
    assert re.search(r"pk_user_roles is distinct from 'email'", RAW_SQL)
    assert re.search(r"pk_staff_options is distinct from 'id'", RAW_SQL)


def test_verification_step_covers_all_four_tables():
    step5_start = RAW_SQL.find("STEP 5:")
    step5_end = RAW_SQL.find("commit;", step5_start)
    assert step5_start != -1 and step5_end != -1
    step5_block = RAW_SQL[step5_start:step5_end]
    for table in (
        "crm_data_imports",
        "crm_lead_followups",
        "crm_user_roles",
        "crm_staff_options",
    ):
        assert table in step5_block, f"STEP 5 verification does not mention {table}"


def test_zero_impact_is_documented_as_valid_not_an_error():
    lowered = RAW_SQL.lower()
    assert "0 is expected and valid" in lowered or "0 rows moved" in lowered
    assert "jeeb_remaining <> 0" in RAW_SQL
    # The check compares moved-count consistency, not "must be nonzero".
    assert "jeeb_total_before > 0" not in RAW_SQL
    assert "must be greater than 0" not in lowered


def test_no_ying_noona_mismatch_fixing_logic():
    # The known mismatch row (id=536766) must only ever be SELECTed for
    # verification, never targeted by an UPDATE.
    for match in re.finditer(r"(?im)^\s*update\b.*?;", EXECUTABLE_SQL, re.DOTALL):
        assert "536766" not in match.group(0)
    assert "536766" in RAW_SQL  # still verified, just never written to


def test_no_au_touching_logic():
    for match in re.finditer(r"(?im)^\s*update\b.*?;", EXECUTABLE_SQL, re.DOTALL):
        stmt = match.group(0)
        assert "'AU'" not in stmt and "= AU" not in stmt
    assert "'AU'" in RAW_SQL  # still checked for in verification, never written


def test_rollback_plan_uses_correct_keys_including_email_for_user_roles():
    rollback_start = RAW_SQL.find("ROLLBACK PLAN")
    assert rollback_start != -1
    rollback_block = RAW_SQL[rollback_start:]

    # crm_user_roles must restore by email, and must NOT use id.
    user_roles_stmt = re.search(
        r"update public\.crm_user_roles.*?where[^\n]*", rollback_block, re.DOTALL
    )
    assert user_roles_stmt is not None
    assert "u.email = b.email" in user_roles_stmt.group(0)
    assert "u.id = b.id" not in user_roles_stmt.group(0)

    # The other three restore by id.
    for table, alias in (
        ("crm_data_imports", "d"),
        ("crm_lead_followups", "f"),
        ("crm_staff_options", "s"),
    ):
        stmt = re.search(
            rf"update public\.{table}.*?where[^\n]*", rollback_block, re.DOTALL
        )
        assert stmt is not None, f"rollback statement for {table} not found"
        assert f"{alias}.id = b.id" in stmt.group(0)

    # No "repeat the same pattern"-style hand-waving left over from REV 1.
    assert "repeat the same pattern" not in rollback_block.lower()


def test_rollback_plan_does_not_reference_crm_orders():
    rollback_start = RAW_SQL.find("ROLLBACK PLAN")
    assert rollback_start != -1
    rollback_block = RAW_SQL[rollback_start:]
    assert "crm_orders" not in rollback_block.lower()


def test_backup_table_names_are_unique_to_this_revision():
    # REV 1 used a 20260723 date stamp for its backup tables; REV 2 must use
    # a different stamp so re-running against a database that still has
    # REV 1's (never-committed, but possibly manually-created) backup
    # tables around does not collide silently.
    assert "crm_jeeb_noona_merge_backup_20260724_data_imports" in RAW_SQL
    assert "crm_jeeb_noona_merge_backup_20260723_data_imports" not in RAW_SQL


def test_backup_collision_guard_present():
    assert "BACKUP GUARD TRIPPED" in RAW_SQL
    guard_pos = EXECUTABLE_SQL.find("BACKUP GUARD TRIPPED")
    first_create_pos = EXECUTABLE_SQL.find("create table public.crm_jeeb_noona_merge_backup")
    assert guard_pos != -1 and first_create_pos != -1
    assert guard_pos < first_create_pos


def test_schema_column_existence_preflight_present():
    assert "PREFLIGHT FAILED: expected column" in RAW_SQL
    for table in (
        "crm_data_imports",
        "crm_lead_followups",
        "crm_user_roles",
        "crm_staff_options",
    ):
        assert f"('{table}'," in RAW_SQL
