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


def test_evidence_gap_run_uses_signed_source_reader_and_exact_scope(monkeypatch) -> None:
    from unittest.mock import MagicMock

    from services.agents import worker_cli

    setup_cursor = MagicMock()
    query_cursor = MagicMock()
    query_cursor.fetchall.return_value = [
        {"pillar_key": "soil_health", "pillar_name": "Soil Health", "gap_status": "missing_evidence"}
    ]
    connection = MagicMock()
    connection.autocommit = False
    setup_context = MagicMock()
    setup_context.__enter__.return_value = setup_cursor
    connection.cursor.side_effect = lambda *args, **kwargs: (
        query_cursor if kwargs else setup_context
    )
    events = []
    source_context = MagicMock(
        side_effect=lambda *_args, **_kwargs: events.append("signed-context")
    )
    monkeypatch.setattr(worker_cli, "get_worker_credential", lambda key: f"{key}-synthetic-credential-value-123456")
    monkeypatch.setattr(worker_cli, "get_worker_db", lambda key: connection)
    monkeypatch.setattr(worker_cli, "set_agent_source_tenant_context", source_context)
    original_analyze = analyze_evidence_gaps

    def analyze(*args):
        events.append("query")
        return original_analyze(*args)

    monkeypatch.setattr(ebf_evidence_gap_agent, "analyze_evidence_gaps", analyze)

    output = run_ebf_evidence_gap(SCORECARD_ID, LOCATION_ID)

    assert output["evidence_gaps"][0]["pillar_key"] == "soil_health"
    source_context.assert_called_once_with(
        connection,
        credential="agent_ebf_source-synthetic-credential-value-123456",
        location_id=LOCATION_ID,
        resource="ebf_scorecard",
        action="read",
    )
    assert events == ["signed-context", "query"]
    statements = [call.args[0].strip() for call in setup_cursor.execute.call_args_list]
    assert statements[:4] == [
        "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY",
        "SET LOCAL ROLE kokonut_agent_ebf_source_reader",
        "SET LOCAL search_path = kokonut_agent_source, pg_catalog",
        "SET LOCAL statement_timeout = '15s'",
    ]
    assert "FROM v_ebf_evidence_gap_summary" in query_cursor.execute.call_args.args[0]
    assert query_cursor.execute.call_args.args[1] == (SCORECARD_ID, LOCATION_ID)
    connection.commit.assert_not_called()
    connection.rollback.assert_not_called()
    connection.close.assert_called_once_with()


def test_evidence_gap_run_rejects_bad_scope_before_worker_secrets_or_database(monkeypatch):
    from unittest.mock import MagicMock

    from services.agents import worker_cli

    credential = MagicMock(side_effect=AssertionError("invalid input read a credential"))
    database = MagicMock(side_effect=AssertionError("invalid input opened a connection"))
    monkeypatch.setattr(worker_cli, "get_worker_credential", credential)
    monkeypatch.setattr(worker_cli, "get_worker_db", database)

    with pytest.raises(ValueError, match="scorecard_id and location_id must be UUIDs"):
        run_ebf_evidence_gap("invalid", LOCATION_ID)

    credential.assert_not_called()
    database.assert_not_called()


@pytest.mark.parametrize("failure_point", ["execute", "fetchall"])
def test_evidence_gap_agent_closes_cursor_and_connection_on_query_failure(
    failure_point: str, monkeypatch
) -> None:
    from services.agents import worker_cli

    class Cursor:
        closed = False

        def execute(self, query, _params=None):
            if failure_point == "execute" and "FROM v_ebf_evidence_gap_summary" in query:
                raise RuntimeError("synthetic query failure")

        def fetchall(self):
            if failure_point == "fetchall":
                raise RuntimeError("synthetic fetch failure")
            return []

        def close(self):
            self.closed = True

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    class Connection:
        closed = False

        def __init__(self):
            self.cursor_value = Cursor()

        def cursor(self, cursor_factory=None):
            return self.cursor_value

        def close(self):
            self.closed = True

        def rollback(self):
            self.rolled_back = True

    connection = Connection()
    monkeypatch.setattr(worker_cli, "get_worker_credential", lambda _key: "s" * 40)
    monkeypatch.setattr(worker_cli, "get_worker_db", lambda _key: connection)
    monkeypatch.setattr(worker_cli, "set_agent_source_tenant_context", lambda *_a, **_k: None)

    with pytest.raises(RuntimeError, match="synthetic (query|fetch) failure"):
        run_ebf_evidence_gap(SCORECARD_ID, LOCATION_ID)

    assert connection.cursor_value.closed is True
    assert connection.closed is True
    assert connection.rolled_back is True


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
