"""Standalone EBF agent module tests."""

from services.agents.ebf_calibration_agent import draft_calibration_memo
from services.agents.ebf_evidence_gap_agent import analyze_evidence_gaps
from services.agents.ebf_scorecard_agent import draft_scorecard


def test_scorecard_agent_outputs_draft_only() -> None:
    output = draft_scorecard("a0000000-0000-0000-0000-000000000001", "2026-01-01", "2026-12-31")
    assert output["scorecard"]["status"] == "draft"
    assert "Human review" in output["safety_note"]


def test_calibration_agent_outputs_draft_memo() -> None:
    output = draft_calibration_memo("a0000000-0000-0000-0000-000000000777")
    assert output["memo"]["status"] == "draft"
    assert output["proposed_decisions"] == []


def test_evidence_gap_agent_summarizes_rows() -> None:
    class Cursor:
        def execute(self, query, params):
            pass
        def fetchall(self):
            return [{"pillar_key": "soil_health", "pillar_name": "Soil Health", "gap_status": "missing_evidence"}]
        def close(self):
            pass
    class Conn:
        def cursor(self, cursor_factory=None):
            return Cursor()
    output = analyze_evidence_gaps(Conn(), "a0000000-0000-0000-0000-000000000100")
    assert output["evidence_gaps"][0]["pillar_key"] == "soil_health"
    assert output["recommendations"]


def test_scorecard_agent_includes_rubric_version() -> None:
    output = draft_scorecard("a0000000-0000-0000-0000-000000000001", "2026-01-01", "2026-12-31")
    assert output["scorecard"]["rubric_version"] == "2026.1"


def test_calibration_agent_includes_review_note() -> None:
    output = draft_calibration_memo("a0000000-0000-0000-0000-000000000777")
    assert "human approval" in output["memo"]["review_note"].lower()


def test_evidence_gap_agent_generates_recommendations_for_non_ready() -> None:
    class Cursor:
        def execute(self, query, params):
            pass
        def fetchall(self):
            return [
                {"pillar_key": "soil_health", "pillar_name": "Soil Health", "gap_status": "missing_evidence"},
                {"pillar_key": "biodiversity", "pillar_name": "Biodiversity", "gap_status": "ready_for_review"},
            ]
        def close(self):
            pass
    class Conn:
        def cursor(self, cursor_factory=None):
            return Cursor()
    output = analyze_evidence_gaps(Conn(), "a0000000-0000-0000-0000-000000000100")
    assert len(output["recommendations"]) == 1
    assert output["recommendations"][0]["pillar_key"] == "soil_health"


if __name__ == "__main__":
    test_scorecard_agent_outputs_draft_only()
    test_calibration_agent_outputs_draft_memo()
    test_evidence_gap_agent_summarizes_rows()
