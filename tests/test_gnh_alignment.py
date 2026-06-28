"""GNH alignment, cultural preservation, renewable energy, vulnerable access, and foundational well-being tests."""

from pathlib import Path

from services.agents.gnh_agent import synthesize_gnh
from services.agents.tasks import get_task, list_tasks, validate_output
from services.export.report_generator import (
    REPORT_GENERATORS,
    generate_cultural_preservation,
    generate_foundational_wellbeing,
    generate_gnh_alignment,
    generate_renewable_energy,
    generate_vulnerable_access,
)


SCHEMA = Path("schemas/postgres/038_gnh_alignment_and_inclusion.sql")
SEED = Path("schemas/seeds/039_gnh_alignment_and_inclusion.sql")
PILOT_SEED = Path("schemas/seeds/039_pilot_gnh_alignment.sql")


def test_gnh_schema_defines_records_and_public_views() -> None:
    text = SCHEMA.read_text()
    for table in [
        "gnh_alignment_assessment",
        "cultural_preservation_plan",
        "renewable_energy_plan",
        "vulnerable_group_access_plan",
        "foundational_wellbeing_observation",
    ]:
        assert f"CREATE TABLE IF NOT EXISTS {table}" in text
    for view in [
        "v_public_gnh_alignment_summary",
        "v_public_cultural_preservation_summary",
        "v_public_renewable_energy_summary",
        "v_public_vulnerable_access_summary",
        "v_public_foundational_wellbeing_summary",
    ]:
        assert f"CREATE OR REPLACE VIEW {view}" in text
    assert "evidence_maturity >= 3" in text
    assert "farm_registry_record" in text
    assert "alignment_score IS NULL OR alignment_score BETWEEN 0 AND 10" in text


def test_gnh_seed_and_dashboards_exist() -> None:
    text = SEED.read_text()
    for metric in [
        "gnh_alignment_score",
        "cultural_preservation_activity_count",
        "local_language_access_coverage_pct",
        "renewable_energy_share_pct",
        "fossil_energy_displacement_estimate",
        "vulnerable_group_access_coverage_pct",
        "foundational_wellbeing_score",
        "peace_and_safety_signal",
    ]:
        assert metric in text
    for sql in [
        "39_gnh_alignment.sql",
        "40_cultural_preservation.sql",
        "41_renewable_energy.sql",
        "42_vulnerable_access.sql",
        "43_foundational_wellbeing.sql",
    ]:
        assert Path("dashboards/metabase/sql").joinpath(sql).exists()
    for dashboard in [
        "39_gnh_alignment.json",
        "40_cultural_preservation.json",
        "41_renewable_energy.json",
        "42_vulnerable_access.json",
        "43_foundational_wellbeing.json",
    ]:
        assert Path("dashboards/metabase").joinpath(dashboard).exists()
    assert "refresh_cron" in text


def test_pilot_seed_has_adelphi_examples_and_claim_boundaries() -> None:
    text = PILOT_SEED.read_text()
    assert "adelphi-gnh-ecological-diversity-2026-03" in text
    assert "adelphi-cultural-preservation-2026-03" in text
    assert "planned_not_implemented" in text
    assert "disabled participants" in text
    assert "Bhutan readiness" in text
    assert "Kokonut Venus Farm" in text
    assert "100% women-based leadership" not in text


def test_gnh_agent_task_catalogue_and_validation() -> None:
    assert "gnh_alignment_synthesis" in list_tasks()
    task = get_task("gnh_alignment_synthesis")
    assert task["writes"] == ["ai_summary:draft"]
    assert task["high_risk"] is False
    assert validate_output("gnh_alignment_synthesis", {}) == ["Missing required output field: summary"]


def test_gnh_agent_summarizes_public_safe_records() -> None:
    class Cursor:
        calls = 0

        def execute(self, query, params=None):
            self.calls += 1

        def fetchall(self):
            if self.calls == 1:
                return [{
                    "gnh_domain": "culture",
                    "location_id": "a0000000-0000-0000-0000-000000000001",
                    "assessment_date": "2026-03-31",
                    "principle_refs": ["GNH-10"],
                    "alignment_score": 6.5,
                    "strengths": ["Spanish summaries"],
                    "gaps": ["local review"],
                    "safeguards": ["consent"],
                    "public_summary": "GNH summary.",
                    "evidence_maturity": 3,
                    "evidence_maturity_label": "Reviewed record",
                }]
            if self.calls == 2:
                return [{
                    "cultural_element": "Spanish summaries",
                    "location_id": "a0000000-0000-0000-0000-000000000001",
                    "plan_date": "2026-03-31",
                    "preservation_type": "local_language",
                    "local_language": "es",
                    "digital_integration_strategy": "public summaries",
                    "consent_protocol": "consent required",
                    "local_reviewer_role": "Community Guild",
                    "implementation_status": "planned",
                    "public_summary": "Culture summary.",
                    "evidence_maturity": 3,
                    "evidence_maturity_label": "Reviewed record",
                }]
            if self.calls == 3:
                return [{
                    "energy_use_case": "irrigation",
                    "location_id": "a0000000-0000-0000-0000-000000000001",
                    "plan_date": "2026-03-31",
                    "renewable_source": "solar",
                    "implementation_status": "planned",
                    "current_energy_source": "grid",
                    "planned_capacity_kw": 2.5,
                    "estimated_annual_kwh": 3600,
                    "renewable_share_pct": 35,
                    "fossil_displacement_estimate_co2e_tonnes": 1.8,
                    "public_summary": "Renewable summary.",
                    "evidence_maturity": 3,
                    "evidence_maturity_label": "Reviewed record",
                }]
            if self.calls == 4:
                return [{
                    "access_scope": "governance",
                    "location_id": "a0000000-0000-0000-0000-000000000001",
                    "plan_date": "2026-03-31",
                    "vulnerable_groups": ["disabled participants"],
                    "access_barriers": ["dashboard accessibility"],
                    "accommodations": ["accessibility review"],
                    "participation_pathways": ["assisted reporting"],
                    "accountable_role": "Community Guild",
                    "implementation_status": "planned",
                    "access_coverage_pct": 50,
                    "public_summary": "Access summary.",
                    "evidence_maturity": 3,
                    "evidence_maturity_label": "Reviewed record",
                }]
            return [{
                "wellbeing_domain": "peace",
                "location_id": "a0000000-0000-0000-0000-000000000001",
                "observation_date": "2026-03-31",
                "stakeholder_group": "local_resident",
                "score_value": 6.5,
                "count_value": None,
                "public_summary": "Wellbeing summary.",
                "evidence_maturity": 3,
                "evidence_maturity_label": "Reviewed record",
            }]

        def close(self):
            pass

    class Conn:
        def cursor(self, cursor_factory=None):
            return Cursor()

    summary = synthesize_gnh(Conn(), "a0000000-0000-0000-0000-000000000001")
    assert summary["gnh_alignment_count"] == 1
    assert summary["cultural_preservation_count"] == 1
    assert summary["renewable_energy_count"] == 1
    assert summary["vulnerable_access_count"] == 1
    assert summary["foundational_wellbeing_count"] == 1
    assert summary["planned_renewable_count"] == 1
    assert "Bhutan-readiness claims" in summary["safety_note"]


def test_gnh_report_generators_registered() -> None:
    for report_type in [
        "gnh_alignment",
        "cultural_preservation",
        "renewable_energy",
        "vulnerable_access",
        "foundational_wellbeing",
    ]:
        assert report_type in REPORT_GENERATORS


def test_gnh_report_generators_public_safe() -> None:
    class Cursor:
        calls = 0

        def execute(self, query, params=None):
            self.calls += 1

        def fetchone(self):
            return {"name": "Kokonut Adelphi"}

        def fetchall(self):
            return [{
                "public_summary": "Public summary",
                "alignment_score": 7,
                "implementation_status": "planned",
            }]

        def close(self):
            pass

    class Conn:
        def cursor(self, cursor_factory=None):
            return Cursor()

    conn = Conn()
    gnh = generate_gnh_alignment(conn, "a0000000-0000-0000-0000-000000000001")
    assert gnh["report_type"] == "gnh_alignment"
    assert "not Bhutan readiness certification" in gnh["limitations"][0]
    assert generate_cultural_preservation(conn, "a0000000-0000-0000-0000-000000000001")["report_type"] == "cultural_preservation"
    renewable = generate_renewable_energy(conn, "a0000000-0000-0000-0000-000000000001")
    assert renewable["planned_count"] == 1
    assert generate_vulnerable_access(conn, "a0000000-0000-0000-0000-000000000001")["report_type"] == "vulnerable_access"
    assert generate_foundational_wellbeing(conn, "a0000000-0000-0000-0000-000000000001")["report_type"] == "foundational_wellbeing"


if __name__ == "__main__":
    test_gnh_schema_defines_records_and_public_views()
    test_gnh_seed_and_dashboards_exist()
    test_pilot_seed_has_adelphi_examples_and_claim_boundaries()
    test_gnh_agent_task_catalogue_and_validation()
    test_gnh_agent_summarizes_public_safe_records()
    test_gnh_report_generators_registered()
    test_gnh_report_generators_public_safe()
