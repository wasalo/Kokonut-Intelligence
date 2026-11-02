"""Organic certification tests: schema, seeds, analytics, views, metrics, reports."""

import re
from datetime import date
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
from services.export.reports.operations import (
    generate_organic_certification_readiness,
    generate_organic_input_audit,
    generate_organic_transition_progress,
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


def test_organic_compliance_dashboard_projection_preserves_full_payload() -> None:
    location_id = "a0000000-0000-0000-0000-000000000001"
    dashboard_row = {
        "location_id": location_id,
        "location_name": "Kokonut Adelphi",
        "latitude": 18.5,
        "longitude": -69.9,
        "farm_registry_id": "b0000000-0000-0000-0000-000000000001",
        "farm_status": "verified",
        "active_standard": "IFOAM",
        "certification_status": "in_transition",
        "certification_expiry": date(2027, 3, 31),
        "transition_status": "active",
        "transition_year": 2,
        "transition_total_years": 3,
        "total_prohibited_substances": 3,
        "cleared_substances": 2,
        "pending_substances": 1,
        "buffer_zone_count": 4,
        "adequate_buffers": 3,
        "total_inputs": 12,
        "organic_inputs": 9,
        "prohibited_inputs": 1,
        "total_harvests": 8,
        "segregated_harvests": 7,
        "latest_readiness_score": 82.5,
        "latest_readiness_date": date(2026, 3, 15),
        "latest_inspection_result": "conditional_pass",
    }
    columns = (
        "location_id, location_name, latitude, longitude, farm_registry_id, farm_status, active_standard, "
        "certification_status, certification_expiry, transition_status, transition_year, "
        "transition_total_years, total_prohibited_substances, cleared_substances, pending_substances, "
        "buffer_zone_count, adequate_buffers, total_inputs, organic_inputs, prohibited_inputs, "
        "total_harvests, segregated_harvests, latest_readiness_score, latest_readiness_date, "
        "latest_inspection_result"
    )

    class Cursor:
        def __init__(self):
            self.executed = []
            self.fetchone_calls = 0
            self.fetchall_calls = 0

        def execute(self, query, params):
            self.executed.append((query, params))

        def fetchone(self):
            self.fetchone_calls += 1
            if self.fetchone_calls == 1:
                return {"name": "Kokonut Adelphi"}
            if self.fetchone_calls == 2:
                return {"overall_score": 82.5, "barriers": ["buffer review"]}
            return dashboard_row

        def fetchall(self):
            self.fetchall_calls += 1
            return []

        def close(self):
            pass

    class Conn:
        def __init__(self):
            self.cursor_value = Cursor()

        def cursor(self, cursor_factory=None):
            return self.cursor_value

    conn = Conn()
    report = generate_organic_certification_readiness(conn, location_id)
    query, params = conn.cursor_value.executed[4]

    assert re.sub(r"\s+", " ", query).strip() == (
        f"SELECT {columns} FROM v_public_organic_compliance_dashboard WHERE location_id = %s"
    )
    assert params == (location_id,)
    assert report["report_type"] == "organic_certification_readiness"
    assert report["location_name"] == "Kokonut Adelphi"
    assert report["compliance_dashboard"] == dashboard_row
    assert report["overall_score"] == 82.5
    assert report["top_barriers"] == ["buffer review"]


def test_organic_reports_use_exact_public_projections_and_preserve_payloads() -> None:
    location_id = "a0000000-0000-0000-0000-000000000001"
    readiness_columns = [
        "id", "location_id", "location_name", "latitude", "longitude",
        "farm_registry_id", "farm_status", "assessment_date", "standard",
        "overall_score", "transition_progress_pct", "soil_health_score",
        "input_compliance_pct", "pest_management_score", "biodiversity_score",
        "buffer_zone_score", "record_completeness_pct", "training_completion_pct",
        "harvest_segregation_score", "barriers", "recommendations", "assessor",
        "notes", "created_at",
    ]
    transition_columns = [
        "id", "location_id", "location_name", "latitude", "longitude",
        "farm_registry_id", "farm_status", "standard", "transition_start_date",
        "expected_certification_date", "current_year", "total_years_required",
        "status", "progress_pct", "prohibited_substance_free_date",
        "buffer_zone_established_date", "record_keeping_ready_date",
        "training_completed_date", "organic_management_plan_date",
        "readiness_score", "barriers", "notes", "created_at",
    ]
    certification_columns = [
        "id", "location_id", "location_name", "latitude", "longitude",
        "farm_registry_id", "farm_status", "standard", "certification_type",
        "certification_body", "application_date", "inspection_date",
        "certification_date", "expiration_date", "certificate_number", "status",
        "scope", "scope_areas", "annual_fee_usd", "notes", "created_at",
    ]
    prohibited_columns = [
        "id", "location_id", "location_name", "farm_registry_id", "substance_name",
        "substance_category", "cas_number", "date_used", "quantity", "unit",
        "remediation_action", "remediation_date", "withdrawal_end_date",
        "compliance_status", "clearance_status", "notes", "created_at",
    ]
    input_columns = [
        "id", "location_id", "location_name", "farm_registry_id", "application_date",
        "input_category", "input_name", "input_source", "organic_certified",
        "supplier_name", "quantity", "unit", "application_method",
        "target_pest_or_nutrient", "pre_harvest_interval_days",
        "reentry_interval_hours", "is_prohibited", "prohibition_standard", "notes",
        "created_at",
    ]
    harvest_columns = [
        "id", "location_id", "location_name", "farm_registry_id", "harvest_event_id",
        "handling_date", "handling_type", "organic_segregated", "equipment_cleaned",
        "contamination_risk", "temperature_controlled", "organic_lot_number",
        "buyer_requirements_met", "storage_conditions", "notes", "created_at",
    ]
    readiness = {
        "id": "00000000-0000-4000-8000-000000000001",
        "location_id": location_id,
        "overall_score": 82.5,
        "barriers": ["buffer review"],
        "assessment_date": "2026-10-01",
    }
    transition = {
        "id": "00000000-0000-4000-8000-000000000002",
        "location_id": location_id,
        "standard": "IFOAM",
        "status": "active",
        "progress_pct": 66.7,
        "barriers": [],
    }
    certification = {
        "id": "00000000-0000-4000-8000-000000000003",
        "location_id": location_id,
        "standard": "IFOAM",
        "status": "in_transition",
        "certificate_number": "SYNTHETIC-001",
    }
    prohibited = {
        "id": "00000000-0000-4000-8000-000000000004",
        "location_id": location_id,
        "substance_name": "Synthetic test substance",
        "compliance_status": "under_review",
        "clearance_status": "pending",
    }
    inputs = [
        {
            "id": "00000000-0000-4000-8000-000000000005",
            "location_id": location_id,
            "input_name": "Compost",
            "organic_certified": True,
            "is_prohibited": False,
        },
        {
            "id": "00000000-0000-4000-8000-000000000006",
            "location_id": location_id,
            "input_name": "Reviewed exception",
            "organic_certified": False,
            "is_prohibited": True,
        },
    ]
    harvest = {
        "id": "00000000-0000-4000-8000-000000000007",
        "location_id": location_id,
        "handling_type": "storage",
        "organic_segregated": True,
    }
    dashboard = {
        "location_id": location_id,
        "location_name": "Kokonut Adelphi",
        "total_inputs": 2,
        "organic_inputs": 1,
    }
    rows_by_view = {
        "v_public_organic_readiness": [readiness],
        "v_public_organic_transition": [transition],
        "v_public_organic_certifications": [certification],
        "v_public_prohibited_substance_audit": [prohibited],
        "v_public_organic_input_audit": inputs,
        "v_public_harvest_segregation": [harvest],
    }

    class Cursor:
        def __init__(self):
            self.calls = []
            self.current_query = ""

        def execute(self, query, params=None):
            self.current_query = " ".join(query.split())
            self.calls.append((self.current_query, params))

        def fetchone(self):
            if "FROM location" in self.current_query:
                return {"name": "Kokonut Adelphi"}
            if "v_public_organic_readiness" in self.current_query:
                return readiness
            if "v_public_organic_compliance_dashboard" in self.current_query:
                return dashboard
            return None

        def fetchall(self):
            for view, rows in rows_by_view.items():
                if view in self.current_query:
                    return rows
            return []

        def close(self):
            pass

    class Connection:
        def __init__(self):
            self.cursors = []

        def cursor(self, cursor_factory=None):
            cursor = Cursor()
            self.cursors.append(cursor)
            return cursor

    def assert_projection(query, view, columns):
        projection = re.search(rf"SELECT (.*?) FROM {view}", query)
        assert projection is not None
        assert [column.strip() for column in projection.group(1).split(",")] == columns

    connection = Connection()
    readiness_report = generate_organic_certification_readiness(connection, location_id)
    readiness_cursor = connection.cursors[-1]
    assert_projection(readiness_cursor.calls[1][0], "v_public_organic_readiness", readiness_columns)
    assert_projection(readiness_cursor.calls[2][0], "v_public_organic_transition", transition_columns)
    assert_projection(readiness_cursor.calls[3][0], "v_public_organic_certifications", certification_columns)
    assert readiness_cursor.calls[1][1] == (location_id,)
    assert "ORDER BY assessment_date DESC LIMIT 1" in readiness_cursor.calls[1][0]
    assert readiness_cursor.calls[2][1] == (location_id,)
    assert "status = 'active'" in readiness_cursor.calls[2][0]
    assert readiness_cursor.calls[3][1] == (location_id,)
    assert "ORDER BY created_at DESC" in readiness_cursor.calls[3][0]
    assert readiness_report["readiness_assessment"] == readiness
    assert readiness_report["active_transitions"] == [transition]
    assert readiness_report["certifications"] == [certification]
    assert readiness_report["overall_score"] == 82.5
    assert readiness_report["top_barriers"] == ["buffer review"]
    assert readiness_report["compliance_dashboard"] == dashboard

    transition_report = generate_organic_transition_progress(connection, location_id)
    transition_cursor = connection.cursors[-1]
    assert_projection(transition_cursor.calls[1][0], "v_public_organic_transition", transition_columns)
    assert_projection(transition_cursor.calls[2][0], "v_public_prohibited_substance_audit", prohibited_columns)
    assert transition_cursor.calls[1][1] == (location_id,)
    assert transition_cursor.calls[2][1] == (location_id,)
    assert transition_report["transitions"] == [transition]
    assert transition_report["active_transition"] == transition
    assert transition_report["prohibited_substances"] == [prohibited]
    assert transition_report["active_count"] == 1

    input_report = generate_organic_input_audit(connection, location_id)
    input_cursor = connection.cursors[-1]
    assert_projection(input_cursor.calls[1][0], "v_public_organic_input_audit", input_columns)
    assert_projection(input_cursor.calls[2][0], "v_public_harvest_segregation", harvest_columns)
    assert input_cursor.calls[1][1] == (location_id,)
    assert "ORDER BY application_date DESC" in input_cursor.calls[1][0]
    assert input_cursor.calls[2][1] == (location_id,)
    assert input_report["inputs"] == inputs
    assert input_report["harvest_handling"] == [harvest]
    assert input_report["total_inputs"] == 2
    assert input_report["organic_certified_inputs"] == 1
    assert input_report["prohibited_inputs"] == 1
    assert input_report["compliance_pct"] == 50.0


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
    test_organic_reports_use_exact_public_projections_and_preserve_payloads()
    test_record_completeness_analytics()
    test_prohibited_substance_clearance_analytics()
    test_prohibited_substance_with_violations()
    test_report_types_registered()
    print("All tests passed.")
