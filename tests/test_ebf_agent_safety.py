"""EBF agent permission boundary tests."""

from services.agents.safety import assess_agent_action
from services.agents.tasks import get_task


def test_agents_cannot_publish_or_raise_ebf_maturity() -> None:
    assert assess_agent_action("update", "ebf_scorecard", {"status": "published"}).allowed is False
    assert assess_agent_action("update", "ebf_score", {"evidence_maturity_level": 4}).allowed is False


def test_ebf_agent_tasks_are_draft_or_read_only() -> None:
    assert get_task("ebf_evidence_gap")["writes"] == []
    assert get_task("ebf_scorecard_draft")["writes"] == ["ebf_scorecard:draft", "ebf_score:draft"]


if __name__ == "__main__":
    test_agents_cannot_publish_or_raise_ebf_maturity()
    test_ebf_agent_tasks_are_draft_or_read_only()
