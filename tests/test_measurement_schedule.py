"""Measurement schedule tests: schema, analytics, scheduling."""

from datetime import date, timedelta
from pathlib import Path

from services.analytics.measurement_schedule import (
    FREQUENCY_INTERVALS,
    check_overdue_zones,
    compute_next_due_date,
    get_measurement_summary,
    set_measurement_schedule,
    update_schedule_after_measurement,
)

SCHEMA = Path("schemas/postgres/073_measurement_schedule.sql")
SEED = Path("schemas/seeds/073_measurement_schedule.sql")


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------

def test_schema_adds_zone_columns() -> None:
    text = SCHEMA.read_text()
    assert "ALTER TABLE farm_zone ADD COLUMN IF NOT EXISTS measurement_frequency" in text
    assert "ALTER TABLE farm_zone ADD COLUMN IF NOT EXISTS last_measurement_date" in text
    assert "ALTER TABLE farm_zone ADD COLUMN IF NOT EXISTS next_measurement_due" in text


def test_schema_adds_tree_columns() -> None:
    text = SCHEMA.read_text()
    assert "ALTER TABLE tree_record ADD COLUMN IF NOT EXISTS measurement_frequency" in text
    assert "ALTER TABLE tree_record ADD COLUMN IF NOT EXISTS next_measurement_due" in text


def test_schema_defines_views() -> None:
    text = SCHEMA.read_text()
    assert "CREATE OR REPLACE VIEW v_measurement_schedule" in text
    assert "CREATE OR REPLACE VIEW v_measurement_overdue_summary" in text
    assert "CREATE OR REPLACE VIEW v_tree_measurement_schedule" in text


def test_schema_has_check_constraints() -> None:
    text = SCHEMA.read_text()
    assert "CHECK (measurement_frequency IN ('monthly', 'quarterly', 'semi_annual', 'annual'))" in text


def test_schema_has_schedule_status_logic() -> None:
    text = SCHEMA.read_text()
    assert "overdue" in text
    assert "due_soon" in text
    assert "on_track" in text
    assert "no_schedule" in text


def test_schema_has_indexes() -> None:
    text = SCHEMA.read_text()
    assert "idx_farm_zone_measurement_due" in text
    assert "idx_farm_zone_measurement_freq" in text
    assert "idx_tree_measurement_due" in text


# ---------------------------------------------------------------------------
# Seed tests
# ---------------------------------------------------------------------------

def test_seed_sets_frequency() -> None:
    text = SEED.read_text()
    assert "measurement_frequency = 'semi_annual'" in text
    assert "measurement_frequency = 'quarterly'" in text
    assert "measurement_frequency = 'annual'" in text


def test_seed_sets_dates() -> None:
    text = SEED.read_text()
    assert "last_measurement_date = '2026-06-01'" in text
    assert "next_measurement_due = '2026-12-01'" in text


# ---------------------------------------------------------------------------
# Analytics tests
# ---------------------------------------------------------------------------

def test_compute_next_due_monthly() -> None:
    result = compute_next_due_date(date(2026, 1, 1), "monthly")
    assert result == date(2026, 1, 31)


def test_compute_next_due_quarterly() -> None:
    result = compute_next_due_date(date(2026, 1, 1), "quarterly")
    assert result == date(2026, 4, 2)


def test_compute_next_due_semi_annual() -> None:
    result = compute_next_due_date(date(2026, 1, 1), "semi_annual")
    assert result == date(2026, 7, 2)


def test_compute_next_due_annual() -> None:
    result = compute_next_due_date(date(2026, 1, 1), "annual")
    assert result == date(2027, 1, 1)


def test_frequency_intervals_complete() -> None:
    assert "monthly" in FREQUENCY_INTERVALS
    assert "quarterly" in FREQUENCY_INTERVALS
    assert "semi_annual" in FREQUENCY_INTERVALS
    assert "annual" in FREQUENCY_INTERVALS


class _MockCursor:
    def __init__(self, rows=None, single=None):
        self._rows = rows or []
        self._single = single
        self._calls = 0

    def execute(self, query, params=None):
        self._calls += 1

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._single

    def close(self):
        pass


class _MockConn:
    def __init__(self, rows=None, single=None):
        self._rows = rows or []
        self._single = single

    def cursor(self, cursor_factory=None):
        return _MockCursor(self._rows, self._single)


def test_check_overdue_zones() -> None:
    rows = [
        ("z1", "loc-1", "Adelphi", "Agro Corridor", "agroforestry",
         "semi_annual", "2026-01-01", "2026-07-01", "overdue", 7, 15),
    ]
    result = check_overdue_zones(_MockConn(rows=rows), "loc-1")
    assert result["total_overdue"] == 1
    assert result["overdue_zones"][0]["days_overdue"] == 7


def test_check_overdue_zones_empty() -> None:
    result = check_overdue_zones(_MockConn(rows=[]), "loc-1")
    assert result["total_overdue"] == 0


def test_get_measurement_summary() -> None:
    class _SummaryConn:
        def __init__(self):
            self._calls = 0
        def cursor(self, cursor_factory=None):
            c = _MockCursor()
            def execute(query, params=None):
                self._calls += 1
                c._single = (10, 2, 1, 5, 2)
            c.execute = execute
            return c

    result = get_measurement_summary(_SummaryConn(), "loc-1")
    assert result["total_scheduled"] == 10
    assert result["overdue"] == 2
    assert result["due_soon"] == 1
    assert result["on_track"] == 5


def test_set_measurement_schedule_invalid_frequency() -> None:
    result = set_measurement_schedule(_MockConn(), "zone-1", "weekly")
    assert "error" in result


def test_set_measurement_schedule_valid() -> None:
    class _SetConn:
        def __init__(self):
            self._calls = 0
            self._params = None
        def cursor(self, cursor_factory=None):
            c = _MockCursor()
            def execute(query, params=None):
                self._calls += 1
                self._params = params
            c.execute = execute
            return c

    conn = _SetConn()
    result = set_measurement_schedule(conn, "zone-1", "quarterly", date(2026, 6, 1))
    assert result["zone_id"] == "zone-1"
    assert result["frequency"] == "quarterly"
    assert result["next_measurement_due"] == "2026-08-31"


def test_update_schedule_after_measurement() -> None:
    class _UpdateConn:
        def __init__(self):
            self._calls = 0
            self._params = None
        def cursor(self, cursor_factory=None):
            c = _MockCursor()
            def execute(query, params=None):
                self._calls += 1
                if self._calls == 1:
                    c._single = ("semi_annual",)
                elif self._calls == 2:
                    self._params = params
            c.execute = execute
            return c

    conn = _UpdateConn()
    result = update_schedule_after_measurement(conn, "zone-1", date(2026, 6, 15))
    assert result["zone_id"] == "zone-1"
    assert result["last_measurement_date"] == "2026-06-15"
    assert result["next_measurement_due"] == "2026-12-14"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    test_schema_adds_zone_columns()
    test_schema_adds_tree_columns()
    test_schema_defines_views()
    test_schema_has_check_constraints()
    test_schema_has_schedule_status_logic()
    test_schema_has_indexes()
    test_seed_sets_frequency()
    test_seed_sets_dates()
    test_compute_next_due_monthly()
    test_compute_next_due_quarterly()
    test_compute_next_due_semi_annual()
    test_compute_next_due_annual()
    test_frequency_intervals_complete()
    test_check_overdue_zones()
    test_check_overdue_zones_empty()
    test_get_measurement_summary()
    test_set_measurement_schedule_invalid_frequency()
    test_set_measurement_schedule_valid()
    test_update_schedule_after_measurement()
    print("All tests passed.")
