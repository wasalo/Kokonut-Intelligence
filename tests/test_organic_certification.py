"""Organic certification tests: schema, seeds, analytics, views, metrics, reports."""

from pathlib import Path

from services.analytics.organic_certification import (
    compute_buffer_adequacy,
    compute_harvest_segregation_score,
    compute_input_compliance_pct,
    compute_organic_readiness_score,
    compute_prohibited_substance_clearance,
    compute_record_completeness,
    compute_transition_progress,
)

SCHEMA = Path("schemas/postgres/055_organic_certification.sql")
SEED = Path("schemas/seeds/055_organic_certification.sql")


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------

def test_schema_defines_tables() -> None:
    text = SCHEMA.read_text()
    for table in [
        "organic_certification_record", "organic_transition_plan",
        "prohibited_substance_record", "buffer_zone",
        "organic_input_audit", "harvest_handling_record",
        "organic_compliance_checklist", "organic_readiness_assessment",
    ]:
        assert f"CREATE TABLE IF NOT EXISTS {table}" in text, f"Missing table: {table}"


def test_schema_defines_views() -> None:
    text = SCHEMA.read_text()
    for view in [
        "v_public_organic_readiness", "v_public_organic_transition",
        "v_public_organic_certifications", "v_public_prohibited_substance_audit",
        "v_public_buffer_zone_status", "v_public_organic_input_audit",
        "v_public_harvest_segregation", "v_public_organic_compliance_dashboard",
    ]:
        assert f"CREATE OR REPLACE VIEW {view}" in text, f"Missing view: {view}"


def test_schema_has_check_constraints() -> None:
    text = SCHEMA.read_text()
    assert "CHECK (certification_type IN" in text
    assert "CHECK (status IN ('planned', 'preparing', 'submitted'" in text
    assert "CHECK (buffer_type IN" in text
    assert "CHECK (input_category IN" in text
    assert "CHECK (handling_type IN" in text
    assert "CHECK (inspection_type IN" in text
    assert "CHECK (overall_result IN" in text
    assert "CHECK (width_m > 0)" in text


def test_schema_has_triggers() -> None:
    text = SCHEMA.read_text()
    for trigger in [
        "trg_organic_cert_updated_at", "trg_transition_updated_at",
        "trg_prohibited_updated_at", "trg_buffer_updated_at",
        "trg_input_audit_updated_at", "trg_harvest_handling_updated_at",
        "trg_checklist_updated_at", "trg_readiness_updated_at",
    ]:
        assert trigger in text, f"Missing trigger: {trigger}"


def test_schema_has_governed_columns() -> None:
    text = SCHEMA.read_text()
    for col in ["source_system", "source_id", "source_raw", "created_at", "updated_at", "created_by", "updated_by"]:
        assert col in text, f"Missing governed column: {col}"


# ---------------------------------------------------------------------------
# Seed tests
# ---------------------------------------------------------------------------

def test_seed_has_metrics() -> None:
    text = SEED.read_text()
    assert "organic_readiness_score" in text
    assert "organic_input_compliance_pct" in text


def test_seed_has_pilot_data() -> None:
    text = SEED.read_text()
    assert "IFOAM" in text
    assert "Caribbean Organic Certification Body" in text
    assert "adelphi-organic-cert-ifoam" in text
    assert "North Hedgerow Buffer" in text
    assert "East Uncultivated Strip" in text
    assert "Adelphi Compost" in text
    assert "Neem Oil Extract" in text


def test_seed_has_checklist() -> None:
    text = SEED.read_text()
    assert "checklist_items" in text
    assert "non_conformances" in text
    assert "corrective_actions_required" in text
    assert "conditional" in text


def test_seed_has_readiness_assessment() -> None:
    text = SEED.read_text()
    assert "overall_score" in text
    assert "soil_health_score" in text
    assert "input_compliance_pct" in text
    assert "pest_management_score" in text
    assert "biodiversity_score" in text
    assert "buffer_zone_score" in text


def test_seed_has_eas_attestation() -> None:
    text = SEED.read_text()
    assert "attestation_record" in text
    assert "organic" in text
    assert "transition_year_2" in text


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


def test_organic_readiness_score_analytics() -> None:
    single = (72.5, 66.7, 82.0, 100.0, 88.0, 75.0, 85.0, 78.0, 90.0, 95.0,
              ["barrier1"], ["rec1"], "2026-02-20", "IFOAM")
    result = compute_organic_readiness_score(_MockConn(single=single), "test-location")
    assert result["overall_score"] == 72.5
    assert result["standard"] == "IFOAM"
    assert result["input_compliance_pct"] == 100.0


def test_organic_readiness_no_assessment() -> None:
    result = compute_organic_readiness_score(_MockConn(single=None), "test-location")
    assert result["overall_score"] == 0
    assert result["status"] == "no_assessment"


def test_transition_progress_analytics() -> None:
    rows = [
        ("id1", "IFOAM", "2024-09-01", "2027-09-01", 2, 3, "active",
         "2024-09-01", "2024-10-15", "2024-11-01", "2025-03-01",
         "2025-06-01", 72.5, ["barrier1"]),
    ]
    result = compute_transition_progress(_MockConn(rows=rows), "test-location")
    assert result["transition_count"] == 1
    assert result["active_transitions"][0]["progress_pct"] == 66.7


def test_input_compliance_analytics() -> None:
    single = (10, 8, 8, 0, 2, 3)
    result = compute_input_compliance_pct(_MockConn(single=single), "test-location")
    assert result["total_inputs"] == 10
    assert result["compliant_inputs"] == 8
    assert result["compliance_pct"] == 80.0
    assert result["status"] == "non_compliant"


def test_buffer_adequacy_analytics() -> None:
    rows = [
        ("buf1", "North Buffer", "hedgerow", 4.0, 120.0, 480.0, "conventional_farm", "adequate", "2024-10-15", "2026-01-10"),
        ("buf2", "East Buffer", "uncultivated_strip", 5.0, 80.0, 400.0, "road", "adequate", "2024-10-20", "2026-01-10"),
    ]
    result = compute_buffer_adequacy(_MockConn(rows=rows), "test-location")
    assert result["total_buffers"] == 2
    assert result["adequate_buffers"] == 2
    assert result["adequacy_pct"] == 100.0


def test_harvest_segregation_analytics() -> None:
    single = (5, 4, 5, 2, 5, 4, 5)
    result = compute_harvest_segregation_score(_MockConn(single=single), "test-location")
    assert result["total_harvests"] == 5
    assert result["segregated_harvests"] == 4
    assert result["segregation_pct"] == 80.0


def test_record_completeness_analytics() -> None:
    class _CompletenessConn:
        def __init__(self):
            self._calls = 0
        def cursor(self, cursor_factory=None):
            c = _MockCursor()
            def execute(query, params=None):
                self._calls += 1
                if self._calls <= 7:
                    c._single = (1,)
                else:
                    c._single = (0,)
            c.execute = execute
            return c

    result = compute_record_completeness(_CompletenessConn(), "test-location")
    assert result["populated_tables"] == 7
    assert result["completeness_pct"] == 87.5


def test_prohibited_substance_clearance_analytics() -> None:
    single = (3, 3, 0, 0, 0, None)
    result = compute_prohibited_substance_clearance(_MockConn(single=single), "test-location")
    assert result["total_substances"] == 3
    assert result["cleared"] == 3
    assert result["all_clear"] is True


def test_prohibited_substance_with_violations() -> None:
    single = (3, 1, 1, 1, 0, "2026-06-01")
    result = compute_prohibited_substance_clearance(_MockConn(single=single), "test-location")
    assert result["violations"] == 1
    assert result["all_clear"] is False


# ---------------------------------------------------------------------------
# Report type tests
# ---------------------------------------------------------------------------

def test_report_types_registered() -> None:
    import importlib
    mod = importlib.import_module("services.export.report_generator")
    assert "organic_certification_readiness" in mod.REPORT_GENERATORS
    assert "organic_transition_progress" in mod.REPORT_GENERATORS
    assert "organic_input_audit" in mod.REPORT_GENERATORS


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    test_schema_defines_tables()
    test_schema_defines_views()
    test_schema_has_check_constraints()
    test_schema_has_triggers()
    test_schema_has_governed_columns()
    test_seed_has_metrics()
    test_seed_has_pilot_data()
    test_seed_has_checklist()
    test_seed_has_readiness_assessment()
    test_seed_has_eas_attestation()
    test_organic_readiness_score_analytics()
    test_organic_readiness_no_assessment()
    test_transition_progress_analytics()
    test_input_compliance_analytics()
    test_buffer_adequacy_analytics()
    test_harvest_segregation_analytics()
    test_record_completeness_analytics()
    test_prohibited_substance_clearance_analytics()
    test_prohibited_substance_with_violations()
    test_report_types_registered()
    print("All tests passed.")
