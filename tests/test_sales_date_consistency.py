"""Cross-module tests proving Dashboard, Daily Matrix, and Team Sales agree
on the sales date for the exact same underlying data.

Team Sales (crm_data/team_sales.py) is the reference implementation -- it
already filtered/grouped by created_at converted to Asia/Bangkok before this
change, and its logic is NOT touched here. These tests only ADD coverage
that (a) Dashboard and Daily Matrix now reuse Team Sales' own _date_bounds
helper (proving no independent, possibly-diverging reimplementation), and
(b) given one shared set of raw rows, all three modules compute the same
Bangkok-day total.

No pytest in this environment -- discovered via the repo's stdlib test_*
runner, same as every other tests/test_*.py file in this repo.
"""

import sys
from contextlib import contextmanager
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import neon_utils as neon
import crm_data.dashboard as crm_dashboard
import crm_data.daily_matrix as daily_matrix
import crm_data.team_sales as team_sales
from crm_data.common import BANGKOK_TZ


REPO_ROOT = Path(__file__).resolve().parents[1]
TEAM_SALES_SOURCE = (REPO_ROOT / "crm_data" / "team_sales.py").read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 1. Single source of truth: Dashboard and Daily Matrix must reuse Team
#    Sales' own _date_bounds function object, not a separately-written copy
#    that could silently drift from it over time.
# ---------------------------------------------------------------------------
def test_dashboard_and_daily_matrix_reuse_team_sales_date_bounds_identity():
    assert crm_dashboard._date_bounds is team_sales._date_bounds
    assert daily_matrix._date_bounds is team_sales._date_bounds


# ---------------------------------------------------------------------------
# 2. Team Sales reference test: it must still be the ORIGINAL
#    created_at-based, Asia/Bangkok-bounded implementation -- untouched by
#    this change. This is the "reference" test requested instead of any
#    edit to crm_data/team_sales.py itself.
# ---------------------------------------------------------------------------
def test_team_sales_remains_the_created_at_bangkok_reference():
    summary_source = TEAM_SALES_SOURCE.split("def fetch_team_sales_summary", 1)[1].split(
        "def fetch_team_top_products", 1
    )[0]
    assert "start_ts, end_ts = _date_bounds(start_date, end_date)" in summary_source
    assert "d.created_at >= %s" in summary_source
    assert "d.created_at < %s" in summary_source
    assert "d.order_date" not in summary_source
    assert "_MANUAL_ROW_SQL" in summary_source


def test_team_sales_date_bounds_converts_bangkok_midnight_to_utc():
    # Direct behavioral proof of the exact conversion every module now shares.
    start_ts, end_ts = team_sales._date_bounds(date(2026, 8, 1), date(2026, 8, 1))
    assert start_ts == datetime(2026, 7, 31, 17, 0, 0, tzinfo=timezone.utc)
    assert end_ts == datetime(2026, 8, 1, 17, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# 3. Same dataset, same Bangkok day -> Dashboard, Daily Matrix, and Team
#    Sales must all report the identical total. Each fake cursor enforces
#    (via assertion inside execute()) that the REAL SQL text for that
#    module's own predicate is what actually ran -- not merely assumed.
#    The two rows below satisfy every real-world predicate used by all
#    three pages at once (import_status='valid' AND source_type='manual'),
#    so the "same dataset" claim is honest, not cherry-picked per module.
# ---------------------------------------------------------------------------
SHARED_ROWS = [
    {
        # Bangkok 2026-08-01 01:00
        "created_at": datetime(2026, 7, 31, 18, 0, 0, tzinfo=timezone.utc),
        "amount": 1200.0,
        "sale_type": "NEW_ORDER",
        "staff_code": "KO",
        "uploaded_by": "ko@example.com",
        "import_status": "valid",
        "source_type": "manual",
    },
    {
        # Bangkok 2026-08-01 17:00
        "created_at": datetime(2026, 8, 1, 10, 0, 0, tzinfo=timezone.utc),
        "amount": 800.0,
        "sale_type": "UPSELL",
        "staff_code": "KO",
        "uploaded_by": "ko@example.com",
        "import_status": "valid",
        "source_type": "manual",
    },
]
SHARED_DAY = date(2026, 8, 1)
SHARED_DAY_TOTAL = 2000.0


def test_dashboard_daily_matrix_and_team_sales_agree_on_same_dataset():
    dashboard_total = _dashboard_total_for_shared_day()
    daily_matrix_total = _daily_matrix_total_for_shared_day()
    team_sales_total = _team_sales_total_for_shared_day()

    assert dashboard_total == SHARED_DAY_TOTAL, dashboard_total
    assert daily_matrix_total == SHARED_DAY_TOTAL, daily_matrix_total
    assert team_sales_total == SHARED_DAY_TOTAL, team_sales_total
    assert dashboard_total == daily_matrix_total == team_sales_total, (
        f"Dashboard={dashboard_total} Daily Matrix={daily_matrix_total} "
        f"Team Sales={team_sales_total} must all match on the same dataset/day"
    )


def _dashboard_total_for_shared_day() -> float:
    class FakeCursor:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def execute(self, sql, params):
            flat = " ".join(sql.split())
            assert "d.import_status = 'valid'" in flat
            assert "d.created_at >= %s" in flat
            assert "d.created_at < %s" in flat
            assert "at time zone 'Asia/Bangkok')::date" in flat
            start_ts, end_ts = params[0], params[1]
            total = sum(
                row["amount"]
                for row in SHARED_ROWS
                if row["import_status"] == "valid" and start_ts <= row["created_at"] < end_ts
            )
            self._rows = [{"sales_date": SHARED_DAY, "sale_type": "NEW_ORDER", "sales_amount": total}] if total else []

        def fetchall(self):
            return self._rows

    class FakeConn:
        def __init__(self, cursor):
            self._cursor = cursor

        def cursor(self):
            return self._cursor

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    fake_cursor = FakeCursor()
    admin_user = {"role": "EDITOR", "email": "editor@example.com"}

    original_ensure_schema = neon.ensure_crm_data_imports_schema
    original_neon_connection = neon.neon_connection
    original_ready = crm_dashboard.crm_sales_report_ready
    original_fetch_rows = crm_dashboard.fetch_sales_report_rows
    try:
        neon.ensure_crm_data_imports_schema = lambda: True
        neon.neon_connection = lambda: FakeConn(fake_cursor)
        crm_dashboard.crm_sales_report_ready = lambda: True
        crm_dashboard.fetch_sales_report_rows = lambda *a, **k: []
        report = crm_dashboard.fetch_sales_report(admin_user, SHARED_DAY, SHARED_DAY, "ทั้งหมด")
    finally:
        neon.ensure_crm_data_imports_schema = original_ensure_schema
        neon.neon_connection = original_neon_connection
        crm_dashboard.crm_sales_report_ready = original_ready
        crm_dashboard.fetch_sales_report_rows = original_fetch_rows

    return sum(row["sales_amount"] for row in report["daily"])


def _daily_matrix_total_for_shared_day() -> float:
    class FakeCursor:
        def __init__(self):
            self._rows = []

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def execute(self, sql, params):
            flat = " ".join(sql.split())
            if "crm_data_imports" not in flat:
                self._rows = []  # empty roster
                return
            assert "coalesce(d.source_type, '') = 'manual'" in flat
            assert "d.created_at >= %s" in flat
            start_ts, end_ts = params
            buckets: dict = {}
            for row in SHARED_ROWS:
                if row["source_type"] != "manual":
                    continue
                if not (start_ts <= row["created_at"] < end_ts):
                    continue
                bangkok_date = row["created_at"].astimezone(BANGKOK_TZ).date()
                buckets[bangkok_date] = buckets.get(bangkok_date, 0.0) + row["amount"]
            self._rows = [
                {
                    "staff_code_norm": "KO",
                    "sales_date": bucket_date,
                    "day_amount": amount,
                    "staff_name": None,
                    "team_code": None,
                    "is_ambiguous": False,
                }
                for bucket_date, amount in buckets.items()
            ]

        def fetchall(self):
            return self._rows

    class FakeConn:
        def __init__(self, cursor):
            self._cursor = cursor

        def cursor(self):
            return self._cursor

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    fake_conn = FakeConn(FakeCursor())
    matrix = daily_matrix.fetch_daily_matrix.__wrapped__(2026, 8, conn_or_none=fake_conn)
    unassigned = matrix["teams"][daily_matrix.UNASSIGNED_TEAM_CODE]
    day_bucket = unassigned["days"].get(SHARED_DAY, {"team_total": 0.0})
    return day_bucket["team_total"]


def _team_sales_total_for_shared_day() -> float:
    class FakeCursor:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def execute(self, sql, params):
            flat = " ".join(sql.split())
            assert "coalesce(d.source_type, '') = 'manual'" in flat
            assert "d.created_at >= %s" in flat
            assert "d.created_at < %s" in flat
            start_ts, end_ts = params[0], params[1]
            total = sum(
                row["amount"]
                for row in SHARED_ROWS
                if row["source_type"] == "manual" and start_ts <= row["created_at"] < end_ts
            )
            self._rows = (
                [
                    {
                        "team_code": "UNASSIGNED",
                        "team_name": "ยังไม่เลือกทีม",
                        "order_count": 0,
                        "sales_amount": total,
                        "row_count": len(SHARED_ROWS),
                    }
                ]
                if total
                else []
            )

        def fetchall(self):
            return self._rows

    class FakeConn:
        def __init__(self, cursor):
            self._cursor = cursor

        def cursor(self):
            return self._cursor

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    fake_cursor = FakeCursor()
    original_neon_connection = neon.neon_connection
    try:
        neon.neon_connection = lambda: FakeConn(fake_cursor)
        summary = team_sales.fetch_team_sales_summary.__wrapped__(SHARED_DAY, SHARED_DAY, None)
    finally:
        neon.neon_connection = original_neon_connection

    return summary["unassigned"]["sales_amount"]


print("Dashboard / Daily Matrix / Team Sales sales-date consistency tests defined OK")
