"""Emergency response tests: schema, seeds, analytics, views, metrics."""

from datetime import date
from pathlib import Path

from services.analytics.emergency_response import (
    compute_emergency_impact_summary,
    compute_emergency_response_time,
)

SCHEMA = Path("schemas/postgres/056_emergency_response.sql")
SEED = Path("schemas/seeds/056_emergency_response.sql")


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------

def test_schema_defines_table() -> None:
    text = SCHEMA.read_text()
    assert "CREATE TABLE IF NOT EXISTS emergency_incident" in text


def test_schema_defines_view() -> None:
    text = SCHEMA.read_text()
    assert "CREATE OR REPLACE VIEW v_public_emergency_incidents" in text


def test_schema_has_check_constraints() -> None:
    text = SCHEMA.read_text()
    assert "CHECK (incident_type IN" in text
    assert "CHECK (severity IN" in text
    assert "CHECK (detection_method IN" in text
    assert "CHECK (status IN" in text
    assert "CHECK (affected_area_pct >= 0 AND affected_area_pct <= 100)" in text
    assert "CHECK (affected_plant_count >= 0)" in text


def test_schema_has_indexes() -> None:
    text = SCHEMA.read_text()
    assert "idx_emergency_location" in text
    assert "idx_emergency_type" in text
    assert "idx_emergency_severity" in text
    assert "idx_emergency_status" in text
    assert "idx_emergency_detection" in text


def test_schema_has_trigger() -> None:
    text = SCHEMA.read_text()
    assert "trg_emergency_updated_at" in text


def test_schema_has_governed_columns() -> None:
    text = SCHEMA.read_text()
    for col in ["source_system", "source_id", "source_raw", "created_at", "updated_at", "created_by", "updated_by"]:
        assert col in text, f"Missing governed column: {col}"


def test_schema_has_response_time_calculation() -> None:
    text = SCHEMA.read_text()
    assert "(e.recovery_date - e.detection_date)" in text
    assert "response_time_days" in text
    assert "met_deadline" in text


# ---------------------------------------------------------------------------
# Seed tests
# ---------------------------------------------------------------------------

def test_seed_has_metric() -> None:
    text = SEED.read_text()
    assert "emergency_response_time_days" in text


def test_seed_has_pilot_data() -> None:
    text = SEED.read_text()
    assert "drought" in text
    assert "high" in text
    assert "weather_forecast" in text
    assert "Emergency watering protocol activated" in text
    assert "40.0" in text
    assert "1200.00" in text
    assert "resolved" in text
    assert "adelphi-emergency-drought-2025" in text


def test_seed_has_response_actions() -> None:
    text = SEED.read_text()
    assert "response_actions" in text
    assert "Adelphi Steward" in text
    assert "Kokonut DAO" in text
    assert "completed" in text


def test_seed_has_lessons_learned() -> None:
    text = SEED.read_text()
    assert "lessons_learned" in text
    assert "Early detection" in text
    assert "drip irrigation" in text


# ---------------------------------------------------------------------------
# Analytics tests
# ---------------------------------------------------------------------------

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


def test_response_time_analytics() -> None:
    rows = [
        ("inc1", "drought", "high", date(2025, 9, 1), date(2025, 9, 22), date(2025, 9, 30), 40.0, 1200.0, "resolved"),
        ("inc2", "flood", "medium", date(2025, 11, 10), date(2025, 11, 18), date(2025, 11, 20), 15.0, 300.0, "resolved"),
    ]
    result = compute_emergency_response_time(_MockConn(rows=rows), "test-location")
    assert result["total_incidents"] == 2
    assert result["resolved_incidents"] == 2
    assert result["avg_response_time_days"] == 14.5  # (21 + 8) / 2
    assert result["met_deadline_count"] == 2


def test_response_time_no_resolved() -> None:
    rows = [
        ("inc1", "drought", "high", date(2025, 9, 1), None, date(2025, 9, 30), 40.0, 1200.0, "responding"),
    ]
    result = compute_emergency_response_time(_MockConn(rows=rows), "test-location")
    assert result["total_incidents"] == 1
    assert result["resolved_incidents"] == 0
    assert result["avg_response_time_days"] is None


def test_impact_summary_analytics() -> None:
    by_type = [
        ("drought", 2, 30.0, 2400.0),
        ("flood", 1, 15.0, 300.0),
    ]
    by_severity = [
        ("high", 2, 35.0, 2100.0),
        ("medium", 1, 10.0, 600.0),
    ]
    totals = (3, 2700.0, 25.0, 2, 1)

    class _ImpactConn:
        def __init__(self):
            self._calls = 0
        def cursor(self, cursor_factory=None):
            c = _MockCursor()
            def execute(query, params=None):
                self._calls += 1
                if self._calls == 1:
                    c._rows = by_type
                elif self._calls == 2:
                    c._rows = by_severity
                elif self._calls == 3:
                    c._single = totals
            c.execute = execute
            return c

    result = compute_emergency_impact_summary(_ImpactConn(), "test-location")
    assert result["total_incidents"] == 3
    assert result["total_financial_impact_usd"] == 2700.0
    assert result["resolved_count"] == 2
    assert result["escalated_count"] == 1
    assert len(result["by_type"]) == 2
    assert len(result["by_severity"]) == 2


def test_impact_summary_no_incidents() -> None:
    class _EmptyConn:
        def __init__(self):
            self._calls = 0
        def cursor(self, cursor_factory=None):
            c = _MockCursor()
            def execute(query, params=None):
                self._calls += 1
                if self._calls <= 2:
                    c._rows = []
                elif self._calls == 3:
                    c._single = (0, 0, 0, 0, 0)
            c.execute = execute
            return c

    result = compute_emergency_impact_summary(_EmptyConn(), "test-location")
    assert result["total_incidents"] == 0
    assert result["total_financial_impact_usd"] == 0


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    test_schema_defines_table()
    test_schema_defines_view()
    test_schema_has_check_constraints()
    test_schema_has_indexes()
    test_schema_has_trigger()
    test_schema_has_governed_columns()
    test_schema_has_response_time_calculation()
    test_seed_has_metric()
    test_seed_has_pilot_data()
    test_seed_has_response_actions()
    test_seed_has_lessons_learned()
    test_response_time_analytics()
    test_response_time_no_resolved()
    test_impact_summary_analytics()
    test_impact_summary_no_incidents()
    print("All tests passed.")
