"""Tests for the shared synthesis agent base (services.agents.base)."""

from __future__ import annotations

from unittest import mock

from services.agents.base import SynthesisAgent, agent_cli, run_fetch


class _FakeCursor:
    def __init__(self) -> None:
        self.executed: tuple | None = None

    def execute(self, sql: str, params: tuple) -> None:
        self.executed = (sql, params)

    def fetchone(self) -> list[str]:
        return ["stored-id"]

    def close(self) -> None:
        pass


class _FakeConn:
    def __init__(self) -> None:
        self.cursor_obj = _FakeCursor()
        self.committed = False
        self.closed = False

    def cursor(self) -> _FakeCursor:
        return self.cursor_obj

    def commit(self) -> None:
        self.committed = True

    def close(self) -> None:
        self.closed = True


class _DummyAgent(SynthesisAgent):
    task_key = "dummy_synthesis"
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
                out = _DummyAgent().run("loc-1", store=store)
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


def test_run_uses_sentinel_subject_id_for_locationless_summary():
    conn = _FakeConn()
    with mock.patch("services.agents.base.get_db", return_value=conn):
        with mock.patch("services.agents.base.assert_agent_action_allowed"):
            with mock.patch("services.agents.base.validate_output", return_value=[]):
                _DummyAgent().run(store=True)
    _, params = conn.cursor_obj.executed
    assert params[1] == "00000000-0000-0000-0000-000000000000"


def test_run_raises_on_validation_errors():
    conn = _FakeConn()
    with mock.patch("services.agents.base.get_db", return_value=conn):
        with mock.patch("services.agents.base.assert_agent_action_allowed"):
            with mock.patch("services.agents.base.validate_output", return_value=["bad field"]):
                try:
                    _DummyAgent().run("loc-1")
                except ValueError as exc:
                    assert "bad field" in str(exc)
                else:
                    raise AssertionError("expected ValueError")
    assert conn.closed is True


def test_run_fetch_validates_and_closes():
    conn = _FakeConn()

    def fetch(conn, scorecard_id):
        return {"scorecard_id": scorecard_id}

    with mock.patch("services.agents.base.get_db", return_value=conn):
        with mock.patch("services.agents.base.assert_agent_action_allowed") as safety:
            with mock.patch("services.agents.base.validate_output", return_value=[]):
                out = run_fetch("ebf_evidence_gap", "ebf_scorecard", fetch, scorecard_id="sc-1")
    assert out == {"scorecard_id": "sc-1"}
    safety.assert_called_once_with("read", "ebf_scorecard", {"scorecard_id": "sc-1"})
    assert conn.closed is True


def test_agent_cli_builds_parser():
    # --help should exit 0 (argparse prints usage) without touching the DB
    with mock.patch("sys.argv", ["prog", "--help"]):
        try:
            agent_cli(_DummyAgent())
        except SystemExit as exc:
            assert exc.code == 0
        else:
            raise AssertionError("expected SystemExit from argparse --help")
