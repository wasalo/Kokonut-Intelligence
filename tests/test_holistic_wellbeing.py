"""Holistic well-being and cultural context tests."""

from pathlib import Path

from services.agents.tasks import get_task, list_tasks, validate_output
from services.agents.wellbeing_agent import synthesize_wellbeing
from services.export.report_generator import REPORT_GENERATORS, generate_holistic_wellbeing


SCHEMA = Path("schemas/postgres/034_holistic_wellbeing.sql")
SEED = Path("schemas/seeds/035_holistic_wellbeing.sql")
PILOT_SEED = Path("schemas/seeds/029_pilot_impact_accountability.sql")


def test_holistic_schema_defines_public_safe_records_and_views() -> None:
    text = SCHEMA.read_text()
    for table in [
        "cultural_context_record",
        "wellbeing_metric_observation",
        "participatory_action_record",
    ]:
        assert f"CREATE TABLE IF NOT EXISTS {table}" in text
    for view in [
        "v_public_cultural_context_summary",
        "v_public_wellbeing_metric_summary",
        "v_public_participatory_governance_summary",
    ]:
        assert f"CREATE OR REPLACE VIEW {view}" in text
    assert "chk_cultural_context_public_opt_in" in text
    assert "consent_given = TRUE" in text
    assert "farm_registry_record" in text


def test_holistic_metric_seed_and_dashboards_exist() -> None:
    text = SEED.read_text()
    for metric in [
        "operator_capability_score",
        "local_language_reporting_coverage",
        "community_trust_signal",
        "worker_safety_signal",
        "training_access_hours",
        "benefit_distribution_transparency",
        "cultural_capital_activity_count",
    ]:
        assert metric in text
    assert "refresh_cron" in text
    assert Path("dashboards/metabase/sql/26_holistic_wellbeing.sql").exists()
    assert Path("dashboards/metabase/sql/27_participatory_governance.sql").exists()
    assert Path("dashboards/metabase/26_holistic_wellbeing.json").exists()
    assert Path("dashboards/metabase/27_participatory_governance.json").exists()


def test_pilot_seed_links_feedback_to_language_culture_and_action() -> None:
    text = PILOT_SEED.read_text()
    assert "Spanish operator summaries" in text
    assert "operator_capability_score" in text
    assert "local_language_reporting_coverage" in text
    assert "participatory_action_record" in text
    assert "a0000000-0000-0000-0000-000000000900" in text
    assert "a0000000-0000-0000-0000-000000000930" in text


def test_wellbeing_agent_task_catalogue_and_validation() -> None:
    assert "holistic_wellbeing_synthesis" in list_tasks()
    task = get_task("holistic_wellbeing_synthesis")
    assert task["writes"] == ["ai_summary:draft"]
    assert task["high_risk"] is False
    assert validate_output("holistic_wellbeing_synthesis", {}) == ["Missing required output field: summary"]


def test_wellbeing_agent_omits_private_raw_text() -> None:
    class Cursor:
        calls = 0

        def execute(self, query, params):
            self.calls += 1

        def fetchall(self):
            if self.calls == 1:
                return [{
                    "practice_name": "Spanish operator summaries",
                    "practice_type": "local_language",
                    "stakeholder_group": "farm_operator",
                    "language": "es",
                    "public_summary": "Operators need Spanish summaries.",
                    "evidence_maturity": 3,
                    "evidence_maturity_label": "Reviewed record",
                }]
            if self.calls == 2:
                return [{
                    "metric_key": "operator_capability_score",
                    "metric_name": "Operator Capability Score",
                    "observation_date": "2026-03-10",
                    "stakeholder_group": "farm_operator",
                    "language": "es",
                    "score_value": 6.5,
                    "count_value": None,
                    "public_summary": "Operators report improved capability.",
                    "evidence_maturity": 3,
                    "evidence_maturity_label": "Reviewed record",
                }]
            if self.calls == 3:
                return [{
                    "action_type": "metric_proposal",
                    "action_date": "2026-03-08",
                    "stakeholder_group": "farm_operator",
                    "feedback_type": "farmer_feedback",
                    "sentiment": "mixed",
                    "metric_name": "Spanish monthly operator summary delivered",
                    "metric_proposal_status": "approved",
                    "decision_status": "completed",
                    "public_summary": "Feedback became a metric proposal.",
                    "evidence_maturity": 3,
                    "evidence_maturity_label": "Reviewed record",
                }]
            return [{"language": "es", "feedback_count": 2, "public_safe_count": 1}]

        def close(self):
            pass

    class Conn:
        def cursor(self, cursor_factory=None):
            return Cursor()

    summary = synthesize_wellbeing(Conn(), "a0000000-0000-0000-0000-000000000001")
    assert summary["cultural_context_count"] == 1
    assert summary["wellbeing_metric_count"] == 1
    assert summary["participatory_action_count"] == 1
    assert summary["languages"] == ["es"]
    assert "raw private" in summary["safety_note"]


def test_holistic_report_generator_registered_and_public_safe() -> None:
    assert "holistic_wellbeing" in REPORT_GENERATORS

    class Cursor:
        calls = 0

        def execute(self, query, params):
            self.calls += 1

        def fetchone(self):
            return {"name": "Kokonut Adelphi"}
        def fetchall(self):
            if self.calls == 2:
                return [{"practice_name": "Spanish operator summaries", "language": "es", "public_summary": "Public summary"}]
            if self.calls == 3:
                return [{"metric_key": "operator_capability_score", "language": "es", "public_summary": "Public metric"}]
            return [{"action_type": "metric_proposal", "public_summary": "Public action"}]
        def close(self):
            pass

    class Conn:
        def cursor(self, cursor_factory=None):
            return Cursor()

    report = generate_holistic_wellbeing(Conn(), "a0000000-0000-0000-0000-000000000001")
    assert report["report_type"] == "holistic_wellbeing"
    assert report["languages"] == ["es"]
    assert "Private stakeholder feedback" in report["limitations"][1]


if __name__ == "__main__":
    test_holistic_schema_defines_public_safe_records_and_views()
    test_holistic_metric_seed_and_dashboards_exist()
    test_pilot_seed_links_feedback_to_language_culture_and_action()
    test_wellbeing_agent_task_catalogue_and_validation()
    test_wellbeing_agent_omits_private_raw_text()
    test_holistic_report_generator_registered_and_public_safe()
