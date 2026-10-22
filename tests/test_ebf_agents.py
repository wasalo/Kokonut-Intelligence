"""Standalone EBF agent module tests."""

import pytest

from services.agents import ebf_evidence_gap_agent
from services.agents.ebf_calibration_agent import draft_calibration_memo
from services.agents.ebf_evidence_gap_agent import analyze_evidence_gaps, run_ebf_evidence_gap
from services.agents.ebf_scorecard_agent import draft_scorecard

LOCATION_ID = "a0000000-0000-0000-0000-000000000001"
SCORECARD_ID = "a0000000-0000-0000-0000-000000000100"


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
        query = None
        params = None

        def execute(self, query, params):
            self.query = query
            self.params = params

        def fetchall(self):
            return [{"pillar_key": "soil_health", "pillar_name": "Soil Health", "gap_status": "missing_evidence"}]

        def close(self):
            pass

    cursor = Cursor()

    class Conn:
        def cursor(self, cursor_factory=None):
            return cursor

    output = analyze_evidence_gaps(Conn(), SCORECARD_ID, LOCATION_ID)
    assert output["evidence_gaps"][0]["pillar_key"] == "soil_health"
    assert output["recommendations"]
    assert "scorecard_id = %s AND location_id = %s" in cursor.query
    assert cursor.params == (SCORECARD_ID, LOCATION_ID)


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
    output = analyze_evidence_gaps(Conn(), SCORECARD_ID, LOCATION_ID)
    assert len(output["recommendations"]) == 1
    assert output["recommendations"][0]["pillar_key"] == "soil_health"


@pytest.mark.parametrize("failure_point", ["execute", "fetchall"])
def test_evidence_gap_agent_closes_cursor_and_connection_on_query_failure(
    failure_point: str, monkeypatch
) -> None:
    class Cursor:
        closed = False

        def execute(self, _query, _params):
            if failure_point == "execute":
                raise RuntimeError("synthetic query failure")

        def fetchall(self):
            if failure_point == "fetchall":
                raise RuntimeError("synthetic fetch failure")
            return []

        def close(self):
            self.closed = True

    class Connection:
        closed = False

        def __init__(self):
            self.cursor_value = Cursor()

        def cursor(self, cursor_factory=None):
            return self.cursor_value

        def close(self):
            self.closed = True

    connection = Connection()
    monkeypatch.setattr("services.agents.base.get_db", lambda: connection)

    with pytest.raises(RuntimeError, match="synthetic (query|fetch) failure"):
        run_ebf_evidence_gap(SCORECARD_ID, LOCATION_ID)

    assert connection.cursor_value.closed is True
    assert connection.closed is True


def test_evidence_gap_cli_requires_location(monkeypatch) -> None:
    monkeypatch.setattr("sys.argv", ["ebf-evidence-gap", "--scorecard-id", SCORECARD_ID])
    monkeypatch.setattr(
        ebf_evidence_gap_agent,
        "run_ebf_evidence_gap",
        lambda *_args: pytest.fail("CLI must reject missing location before running the agent"),
    )
    with pytest.raises(SystemExit) as exc:
        ebf_evidence_gap_agent.main()
    assert exc.value.code == 2


if __name__ == "__main__":
    test_scorecard_agent_outputs_draft_only()
    test_calibration_agent_outputs_draft_memo()
    test_evidence_gap_agent_summarizes_rows()
