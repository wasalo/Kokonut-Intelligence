"""Tests for the shared synthesis agent base (services.agents.base)."""

from __future__ import annotations

from unittest import mock

import pytest

from services.agents.base import SynthesisAgent, agent_cli, run_fetch

LOCATION_ID = "a0000000-0000-4000-8000-000000000001"
SCORECARD_ID = "a0000000-0000-4000-8000-000000000002"


class _FakeCursor:
    def __init__(
        self,
        execute_error: Exception | None = None,
        fetch_error: Exception | None = None,
    ) -> None:
        self.executed: tuple | None = None
        self.execute_error = execute_error
        self.fetch_error = fetch_error
        self.closed = False

    def execute(self, sql: str, params: tuple) -> None:
        if self.execute_error is not None:
            raise self.execute_error
        self.executed = (sql, params)

    def fetchone(self) -> list[str]:
        if self.fetch_error is not None:
            raise self.fetch_error
        return ["stored-id"]

    def close(self) -> None:
        self.closed = True


class _FakeConn:
    def __init__(
        self,
        execute_error: Exception | None = None,
        fetch_error: Exception | None = None,
    ) -> None:
        self.cursor_obj = _FakeCursor(
            execute_error=execute_error,
            fetch_error=fetch_error,
        )
        self.committed = False
        self.closed = False

    def cursor(self) -> _FakeCursor:
        return self.cursor_obj

    def commit(self) -> None:
        self.committed = True

    def close(self) -> None:
        self.closed = True


class _DummyAgent(SynthesisAgent):
    task_key = "ai_summary_synthesis"
    summary_type = "dummy"
    read_collection = "dummy_record"
    model_version = "dummy-agent-v1"
    source_tables = ["dummy_table"]

    def synthesize(self, conn, location_id=None) -> dict:
        return {"location_id": location_id or "00000000-0000-0000-0000-000000000000", "synthesis": "hello"}


def _run_with_fakes(store: bool):
    conn = _FakeConn()
    with mock.patch("services.agents.base.get_db", return_value=conn):
        with mock.patch("services.agents.base.assert_agent_action_allowed"):
            with mock.patch("services.agents.base.validate_output", return_value=[]):
                out = _DummyAgent().run(LOCATION_ID, store=store)
    return out, conn


def test_run_synthesizes_and_closes_connection():
    out, conn = _run_with_fakes(store=False)
    assert out["summary"]["synthesis"] == "hello"
    assert conn.closed is True


def test_run_store_inserts_draft_and_commits():
    out, conn = _run_with_fakes(store=True)
    assert out["ai_summary_id"] == "stored-id"
    assert conn.committed is True
    sql, params = conn.cursor_obj.executed
    assert "INSERT INTO ai_summary" in sql
    assert params[2] == "dummy"  # summary_type
    assert params[4] == ["dummy_table"]  # source_tables
    assert conn.cursor_obj.closed is True


@pytest.mark.parametrize("failure_stage", ["insert", "fetch"])
def test_store_summary_closes_cursor_and_does_not_commit_on_persistence_failure(
    failure_stage: str,
):
    error = RuntimeError(f"synthetic {failure_stage} failure")
    conn = _FakeConn(
        execute_error=error if failure_stage == "insert" else None,
        fetch_error=error if failure_stage == "fetch" else None,
    )

    with pytest.raises(RuntimeError, match=f"synthetic {failure_stage} failure"):
        _DummyAgent().store_summary(
            conn,
            {"location_id": LOCATION_ID, "synthesis": "synthetic draft"},
        )

    assert conn.cursor_obj.closed is True
    assert conn.committed is False


def test_store_summary_rejects_missing_synthesis_before_cursor_access():
    conn = _FakeConn()

    with pytest.raises(ValueError, match="summary.synthesis must be a non-empty string"):
        _DummyAgent().store_summary(conn, {"location_id": LOCATION_ID})

    assert conn.cursor_obj.executed is None
    assert conn.committed is False


def test_store_summary_rejects_malformed_location_before_cursor_access():
    conn = _FakeConn()

    with pytest.raises(ValueError, match="Invalid task input format for field: location_id"):
        _DummyAgent().store_summary(conn, {"location_id": "bad-id", "synthesis": "draft"})

    assert conn.cursor_obj.executed is None
    assert conn.committed is False


def test_run_uses_sentinel_subject_id_for_locationless_summary():
    class _LocationlessDummyAgent(_DummyAgent):
        task_key = "financial_resilience_synthesis"

    conn = _FakeConn()
    with mock.patch("services.agents.base.get_db", return_value=conn):
        with mock.patch("services.agents.base.assert_agent_action_allowed"):
            with mock.patch("services.agents.base.validate_output", return_value=[]):
                _LocationlessDummyAgent().run(store=True)
    _, params = conn.cursor_obj.executed
    assert params[1] == "00000000-0000-0000-0000-000000000000"


def test_run_raises_on_validation_errors():
    conn = _FakeConn()
    with mock.patch("services.agents.base.get_db", return_value=conn):
        with mock.patch("services.agents.base.assert_agent_action_allowed"):
            with mock.patch("services.agents.base.validate_output", return_value=["bad field"]):
                try:
                    _DummyAgent().run(LOCATION_ID)
                except ValueError as exc:
                    assert "bad field" in str(exc)
                else:
                    raise AssertionError("expected ValueError")
    assert conn.closed is True


def test_run_does_not_store_invalid_draft_output():
    conn = _FakeConn()
    with mock.patch("services.agents.base.get_db", return_value=conn):
        with mock.patch("services.agents.base.assert_agent_action_allowed"):
            with mock.patch("services.agents.base.validate_output", return_value=["bad field"]):
                try:
                    _DummyAgent().run(LOCATION_ID, store=True)
                except ValueError as exc:
                    assert "bad field" in str(exc)
                else:
                    raise AssertionError("expected ValueError")
    assert conn.cursor_obj.executed is None
    assert conn.committed is False
    assert conn.closed is True


def test_run_fetch_validates_and_closes():
    conn = _FakeConn()

    def fetch(conn, scorecard_id):
        return {"scorecard_id": scorecard_id}

    with mock.patch("services.agents.base.get_db", return_value=conn):
        with mock.patch("services.agents.base.assert_agent_action_allowed") as safety:
            with mock.patch("services.agents.base.validate_output", return_value=[]):
                out = run_fetch(
                    "ebf_evidence_gap", "ebf_scorecard", fetch, scorecard_id=SCORECARD_ID
                )
    assert out == {"scorecard_id": SCORECARD_ID}
    safety.assert_called_once_with("read", "ebf_scorecard", {"scorecard_id": SCORECARD_ID})
    assert conn.closed is True


def test_run_rejects_malformed_scope_before_database_access():
    with mock.patch("services.agents.base.get_db", side_effect=AssertionError("database opened")):
        with mock.patch("services.agents.base.assert_agent_action_allowed") as safety:
            try:
                _DummyAgent().run("not-a-uuid")
            except ValueError as exc:
                assert "Invalid task input format for field: location_id" in str(exc)
            else:
                raise AssertionError("expected malformed location rejection")
    safety.assert_not_called()


def test_run_fetch_rejects_malformed_scope_before_database_access():
    with mock.patch("services.agents.base.get_db", side_effect=AssertionError("database opened")):
        with mock.patch("services.agents.base.assert_agent_action_allowed") as safety:
            try:
                run_fetch("ebf_evidence_gap", "ebf_scorecard", lambda *_args: {}, scorecard_id="bad")
            except ValueError as exc:
                assert "Invalid task input format for field: scorecard_id" in str(exc)
            else:
                raise AssertionError("expected malformed scorecard rejection")
    safety.assert_not_called()


def test_agent_cli_builds_parser():
    # --help should exit 0 (argparse prints usage) without touching the DB
    with mock.patch("sys.argv", ["prog", "--help"]):
        try:
            agent_cli(_DummyAgent())
        except SystemExit as exc:
            assert exc.code == 0
        else:
            raise AssertionError("expected SystemExit from argparse --help")
