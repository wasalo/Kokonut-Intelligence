"""Configurable containers tests: farm templates, specifications, needs, aspirations, objectives."""

from pathlib import Path

from services.analytics.configurable_containers import (
    compute_farm_template_summary,
    compute_farm_specification_status,
    compute_needs_assessment_summary,
    compute_aspirations_summary,
    compute_objectives_progress,
)

SCHEMA = Path("schemas/postgres/053_configurable_containers.sql")
SEED = Path("schemas/seeds/053_configurable_containers.sql")


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------

def test_schema_defines_tables() -> None:
    text = SCHEMA.read_text()
    for table in [
        "farm_template", "farm_specification", "needs_assessment",
        "stakeholder_aspiration", "objective",
    ]:
        assert f"CREATE TABLE IF NOT EXISTS {table}" in text, f"Missing table: {table}"


def test_schema_defines_views() -> None:
    text = SCHEMA.read_text()
    for view in [
        "v_public_farm_templates", "v_public_farm_specifications",
        "v_public_needs_assessment", "v_public_stakeholder_aspirations",
        "v_public_objectives",
    ]:
        assert f"CREATE OR REPLACE VIEW {view}" in text, f"Missing view: {view}"


def test_schema_has_constraints() -> None:
    text = SCHEMA.read_text()
    assert "chk_farm_template_type" in text
    assert "chk_farm_template_status" in text
    assert "chk_farm_spec_validation" in text
    assert "chk_farm_spec_status" in text
    assert "chk_needs_category" in text
    assert "chk_needs_severity" in text
    assert "chk_needs_urgency" in text
    assert "chk_needs_mitigation" in text
    assert "chk_needs_status" in text
    assert "chk_aspiration_category" in text
    assert "chk_aspiration_priority" in text
    assert "chk_aspiration_status" in text
    assert "chk_objective_type" in text
    assert "chk_objective_priority" in text
    assert "chk_objective_status" in text
    assert "configurable-containers-v1" in text


def test_schema_has_progress_pct_generated() -> None:
    text = SCHEMA.read_text()
    assert "GENERATED ALWAYS AS" in text
    assert "progress_pct" in text


# ---------------------------------------------------------------------------
# Seed tests
# ---------------------------------------------------------------------------

def test_seed_has_metrics() -> None:
    text = SEED.read_text()
    assert "objective_completion_pct" in text
    assert "needs_resolution_rate" in text


def test_seed_has_adelphi_data() -> None:
    text = SEED.read_text()
    assert "Kokonut Syntropic Farm Template" in text
    assert "Adelphi Syntropic Farm Specification" in text
    assert "Water Storage Capacity" in text
    assert "Bio-input Production Skills" in text
    assert "Local Market Access" in text
    assert "Become a Regional Model" in text
    assert "Achieve Financial Self-Sufficiency" in text
    assert "Train 50 Community Members" in text
    assert "Establish Adelphi as Proof-of-Concept" in text
    assert "Achieve 80% Soil Organic Matter" in text
    assert "syntropic" in text
    assert "moloch_dao" in text


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


def test_farm_template_summary_analytics() -> None:
    rows = [
        ("t1", "Syntropic Template", "syntropic", "1.0", [{"zone_type": "syntropic_plot"}], "moloch_dao", ["ebf"], ["soil_protection"], "syntropic", ["pilot"], 2),
    ]
    result = compute_farm_template_summary(_MockConn(rows))
    assert result["total_templates"] == 1
    assert result["templates"][0]["zone_count"] == 1
    assert result["templates"][0]["instances_count"] == 2


def test_needs_assessment_summary_analytics() -> None:
    rows = [
        ("infrastructure", "high", "high", "in_progress", 2, 8.0),
        ("capacity_building", "medium", "medium", "in_progress", 1, 8.0),
        ("market", "medium", "medium", "planned", 1, 12.0),
    ]
    result = compute_needs_assessment_summary(_MockConn(rows), "test-location")
    assert result["total_needs"] == 4
    assert result["resolved_needs"] == 0
    assert result["resolution_rate_pct"] == 0.0


def test_aspirations_summary_analytics() -> None:
    rows = [
        ("ecological", "high", "approved", 1, 36.0),
        ("financial", "high", "approved", 1, 36.0),
        ("capacity", "medium", "approved", 1, 24.0),
    ]
    result = compute_aspirations_summary(_MockConn(rows), "test-location")
    assert result["total_aspirations"] == 3
    assert result["achieved_aspirations"] == 0
    assert result["achievement_rate_pct"] == 0.0


def test_objectives_progress_analytics() -> None:
    rows = [
        ("o1", None, "Proof of Concept", "strategic", "operational", 2.0, 1.0, "cycles", "2027-03-01", 50.0, "critical", "in_progress"),
        ("o2", "o1", "Soil Organic Matter", "operational", "ecological", 80.0, 45.0, "percent", "2027-10-01", 56.25, "high", "in_progress"),
        ("o3", "o1", "Train Workers", "operational", "capacity", 20.0, 4.0, "workers", "2026-10-01", 20.0, "high", "in_progress"),
    ]
    result = compute_objectives_progress(_MockConn(rows), "test-location")
    assert result["total_objectives"] == 3
    assert result["in_progress"] == 3
    assert result["achieved"] == 0
    assert abs(result["avg_progress_pct"] - 42.08) < 0.1


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    test_schema_defines_tables()
    test_schema_defines_views()
    test_schema_has_constraints()
    test_schema_has_progress_pct_generated()
    test_seed_has_metrics()
    test_seed_has_adelphi_data()
    test_farm_template_summary_analytics()
    test_needs_assessment_summary_analytics()
    test_aspirations_summary_analytics()
    test_objectives_progress_analytics()
    print("All tests passed.")
