"""Gap closure tests (6, 10, 12/17)."""

from pathlib import Path

SCHEMA = Path("schemas/postgres/095_soil_protocol.sql")


def test_schema_file_exists():
    assert SCHEMA.exists()


# --- Gap 6: Soil Sampling Protocol ---

def test_sampling_protocol_table_exists():
    content = SCHEMA.read_text()
    assert "CREATE TABLE IF NOT EXISTS sampling_protocol" in content


def test_sampling_protocol_has_required_fields():
    content = SCHEMA.read_text()
    for field in ["domain", "sampling_design", "sub_sample_count", "target_depth_cm",
                  "collection_method", "required_analyses", "analytical_method",
                  "lab_accreditation_required", "monitoring_frequency", "version"]:
        assert field in content, f"Missing field: {field}"


def test_soil_sample_has_enhanced_fields():
    content = SCHEMA.read_text()
    for field in ["lab_accredited", "analytical_method", "protocol_id",
                  "composite_count", "sub_sample_count", "gps_latitude",
                  "collector_name", "chain_of_custody", "container_type",
                  "preservative", "sample_mass_g", "moisture_conditions"]:
        assert field in content, f"Missing soil_sample field: {field}"


def test_soil_carbon_has_enhanced_fields():
    content = SCHEMA.read_text()
    assert "ALTER TABLE soil_carbon_measurement ADD COLUMN IF NOT EXISTS lab_accredited" in content
    assert "ALTER TABLE soil_carbon_measurement ADD COLUMN IF NOT EXISTS protocol_id" in content


def test_sampling_protocol_service_exists():
    assert Path("services/analytics/sampling_protocol.py").exists()


def test_service_has_create():
    from services.analytics.sampling_protocol import create_sampling_protocol
    assert callable(create_sampling_protocol)


def test_service_has_validate():
    from services.analytics.sampling_protocol import validate_sample_compliance
    assert callable(validate_sample_compliance)


def test_service_has_get_protocol():
    from services.analytics.sampling_protocol import get_protocol_for_location
    assert callable(get_protocol_for_location)


# --- Gap 10: Mitigation Approach ---

def test_mitigation_approach_table_exists():
    content = SCHEMA.read_text()
    assert "CREATE TABLE IF NOT EXISTS mitigation_approach" in content


def test_mitigation_has_required_fields():
    content = SCHEMA.read_text()
    for field in ["mitigation_type", "source_table", "source_id",
                  "description", "mechanism", "target_reduction_pct",
                  "measured_value", "effectiveness_rating",
                  "estimated_cost_usd", "reporting_obligation",
                  "evidence_maturity"]:
        assert field in content, f"Missing field: {field}"


def test_mitigation_has_type_constraint():
    content = SCHEMA.read_text()
    assert "chk_ma_type" in content
    assert "emission_reduction" in content
    assert "adaptation" in content


def test_mitigation_service_exists():
    assert Path("services/analytics/mitigation.py").exists()


def test_mitigation_has_create():
    from services.analytics.mitigation import create_mitigation
    assert callable(create_mitigation)


def test_mitigation_has_outcome():
    from services.analytics.mitigation import track_mitigation_outcome
    assert callable(track_mitigation_outcome)


def test_mitigation_has_effectiveness():
    from services.analytics.mitigation import compute_effectiveness
    assert callable(compute_effectiveness)


def test_mitigation_has_source_query():
    from services.analytics.mitigation import get_mitigations_by_source
    assert callable(get_mitigations_by_source)


# --- Gap 12/17: Reporting Cadence ---

def test_reporting_cadence_table_exists():
    content = SCHEMA.read_text()
    assert "CREATE TABLE IF NOT EXISTS reporting_cadence" in content


def test_reporting_cadence_has_required_fields():
    content = SCHEMA.read_text()
    for field in ["report_type", "frequency", "next_due_date", "last_completed_date",
                  "compliance_status", "overdue_count", "auto_generate_report",
                  "report_generator_command", "escalation_role", "escalation_after_days"]:
        assert field in content, f"Missing field: {field}"


def test_reporting_cadence_has_type_constraint():
    content = SCHEMA.read_text()
    assert "chk_rc_type" in content
    assert "grant_report" in content
    assert "annual_impact" in content
    assert "carbon_verification" in content


def test_reporting_cadence_has_frequency_constraint():
    content = SCHEMA.read_text()
    assert "chk_rc_frequency" in content
    assert "weekly" in content
    assert "quarterly" in content
    assert "annual" in content


def test_reporting_cadence_has_compliance_constraint():
    content = SCHEMA.read_text()
    assert "chk_rc_compliance" in content
    assert "overdue" in content
    assert "at_risk" in content


def test_reporting_cadence_has_auto_generate():
    content = SCHEMA.read_text()
    assert "auto_generate_report" in content
    assert "report_generator_command" in content


def test_reporting_cadence_service_exists():
    assert Path("services/analytics/reporting_cadence.py").exists()


def test_cadence_has_create():
    from services.analytics.reporting_cadence import create_cadence
    assert callable(create_cadence)


def test_cadence_has_check_overdue():
    from services.analytics.reporting_cadence import check_overdue
    assert callable(check_overdue)


def test_cadence_has_mark_completed():
    from services.analytics.reporting_cadence import mark_completed
    assert callable(mark_completed)


def test_cadence_has_escalate():
    from services.analytics.reporting_cadence import escalate_overdue
    assert callable(escalate_overdue)


def test_cadence_has_auto_generate():
    from services.analytics.reporting_cadence import trigger_auto_generation
    assert callable(trigger_auto_generation)


def test_cadence_has_summary():
    from services.analytics.reporting_cadence import get_cadence_summary
    assert callable(get_cadence_summary)


# --- Cross-cutting ---

def test_all_three_gaps_addressed():
    content = SCHEMA.read_text()
    assert "sampling_protocol" in content
    assert "mitigation_approach" in content
    assert "reporting_cadence" in content
