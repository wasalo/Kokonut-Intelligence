"""EBF agent permission boundary tests."""

from services.agents.safety import assess_agent_action
from services.agents.tasks import get_task


def test_agents_cannot_publish_or_raise_ebf_maturity() -> None:
    assert assess_agent_action("update", "ebf_scorecard", {"status": "published"}).allowed is False
    assert assess_agent_action("update", "ebf_score", {"evidence_maturity_level": 4}).allowed is False


def test_ebf_agent_tasks_are_draft_or_read_only() -> None:
    assert get_task("ebf_evidence_gap")["writes"] == []
    assert get_task("ebf_scorecard_draft")["writes"] == ["ebf_scorecard:draft", "ebf_score:draft"]


def test_agents_cannot_verify_ebf_scores() -> None:
    result = assess_agent_action("update", "ebf_scorecard", {"status": "verified"})
    assert result.allowed is False


def test_agents_cannot_delete_governed_ebf_collections() -> None:
    for collection in ("ebf_scorecard", "ebf_calibration_decision"):
        result = assess_agent_action("update", collection, {"status": "verified"})
        assert result.allowed is False


def test_agents_can_create_draft_ebf_scorecards() -> None:
    result = assess_agent_action("create", "ebf_scorecard", {"status": "draft"})
    assert result.allowed is True


if __name__ == "__main__":
    test_agents_cannot_publish_or_raise_ebf_maturity()
    test_ebf_agent_tasks_are_draft_or_read_only()
