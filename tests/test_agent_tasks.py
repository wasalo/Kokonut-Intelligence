"""Agent task catalogue tests."""

from services.agents.cids_agent import run_cids_export
from services.agents.feedback_agent import synthesize_feedback
from services.agents.safety import assess_agent_action
from services.agents.tasks import get_task, list_tasks, validate_output


def test_task_catalogue_contains_green_paper_agents() -> None:
    tasks = list_tasks()
    assert "cids_export" in tasks
    assert "feedback_synthesis" in tasks
    assert "holistic_wellbeing_synthesis" in tasks
    assert "financial_resilience_synthesis" in tasks
    assert "ebf_scorecard_draft" in tasks
    assert "ebf_evidence_gap" in tasks
    assert "ebf_calibration_memo" in tasks
    assert get_task("cids_export")["high_risk"] is False
    assert get_task("holistic_wellbeing_synthesis")["writes"] == ["ai_summary:draft"]
    assert get_task("financial_resilience_synthesis")["writes"] == ["ai_summary:draft"]
    assert "verify" not in " ".join(get_task("ebf_scorecard_draft")["writes"])


def test_output_validation_checks_required_fields() -> None:
    errors = validate_output("cids_export", {"graph_count": 1})
    assert "Missing required output field: document" in errors


def test_cids_agent_output_with_monkeypatch(monkeypatch) -> None:
    class Conn:
        def close(self) -> None:
            pass

    import services.agents.cids_agent as cids_agent

    monkeypatch.setattr(cids_agent, "get_connection", lambda: Conn())
    monkeypatch.setattr(
        cids_agent,
        "export_location",
        lambda conn, location_id: {
            "@graph": [{"@type": "cids:Organization"}],
            "kokonut:alignmentTier": "essential",
            "kokonut:cidsVersion": "3.2.0",
        },
    )

    output = run_cids_export("a0000000-0000-0000-0000-000000000001")
    assert output["graph_count"] == 1
    assert output["alignment_tier"] == "essential"


def test_feedback_synthesis_omits_private_raw_text() -> None:
    class Cursor:
        calls = 0

        def execute(self, query, params):
            self.calls += 1

        def fetchall(self):
            if self.calls == 1:
                return [{
                    "stakeholder_group": "farm_operator",
                    "feedback_type": "farmer_feedback",
                    "sentiment": "mixed",
                    "public_summary": "Operators requested simpler Spanish summaries.",
                    "evidence_maturity": 3,
                    "evidence_maturity_label": "Reviewed record",
                }]
            return [{
                "stakeholder_group": "local_resident",
                "feedback_type": "local_resident_feedback",
                "sentiment": "positive",
                "status": "verified",
                "consent_given": False,
                "is_public": False,
                "evidence_maturity": 2,
                "feedback_count": 1,
                "private_or_no_consent_count": 1,
                "harm_count": 0,
            }]

        def close(self):
            pass

    class Conn:
        def cursor(self, cursor_factory=None):
            return Cursor()

    summary = synthesize_feedback(Conn(), "a0000000-0000-0000-0000-000000000001")
    assert summary["public_feedback_count"] == 1
    assert summary["private_or_no_consent_count"] == 1
    assert "Raw private feedback is not included" in summary["safety_note"]


def test_ebf_agent_safety_blocks_publish_and_public_maturity() -> None:
    publish_decision = assess_agent_action("update", "ebf_scorecard", {"status": "published"})
    assert publish_decision.allowed is False
    assert publish_decision.requires_human_approval is True

    maturity_decision = assess_agent_action("update", "ebf_score", {"evidence_maturity_level": 4})
    assert maturity_decision.allowed is False
    assert "public-claim levels" in maturity_decision.reason


if __name__ == "__main__":
    test_task_catalogue_contains_green_paper_agents()
    test_output_validation_checks_required_fields()
    test_ebf_agent_safety_blocks_publish_and_public_maturity()
