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


def test_run_store_delegates_to_signed_worker_with_stable_request_id():
    stable_request_id = "a0000000-0000-4000-8000-000000000004"
    with mock.patch(
        "services.agents.worker_cli.run_worker_synthesis",
        return_value={"ai_summary_id": "stored-id", "request_id": stable_request_id},
    ) as run_worker:
        out = _DummyAgent().run(LOCATION_ID, store=True, request_id=stable_request_id)
    assert out["ai_summary_id"] == "stored-id"
    run_worker.assert_called_once()
    assert run_worker.call_args.args[1:] == (LOCATION_ID, stable_request_id)


def test_store_summary_propagates_worker_failure_without_using_legacy_connection():
    error = RuntimeError("synthetic worker failure")
    conn = _FakeConn()
    with mock.patch(
        "services.agents.worker_draft.create_worker_ai_summary_draft",
        side_effect=error,
    ) as write_draft:
        with pytest.raises(RuntimeError, match="synthetic worker failure"):
            _DummyAgent().store_summary(
                conn,
                {"location_id": LOCATION_ID, "synthesis": "synthetic draft"},
                request_id="a0000000-0000-4000-8000-000000000003",
            )
    write_draft.assert_called_once()
    assert conn.cursor_obj.executed is None
    assert conn.committed is False
    assert conn.closed is False


def test_store_summary_attaches_location_source_references_before_signed_write():
    class _ReferencedDummyAgent(_DummyAgent):
        source_reference_views = {"dummy_table": "v_public_dummy_summary"}

    conn = _FakeConn()
    references = {
        "dummy_table": {
            "record_ids": ["a0000000-0000-4000-8000-000000000010"],
            "row_count": 1,
            "truncated": False,
        }
    }
    sequence: list[str] = []

    def collect(agent, connection, location_id):
        sequence.append("collect")
        assert connection is conn
        assert location_id == LOCATION_ID
        return references

    def write(*args):
        sequence.append("write")
        return {"summary_id": "stored-id"}

    with mock.patch.object(_ReferencedDummyAgent, "collect_source_references", collect):
        with mock.patch(
            "services.agents.base.assert_agent_action_allowed",
            side_effect=lambda action, collection, _payload: sequence.append(
                f"{action}:{collection}"
            ),
        ):
            with mock.patch(
                "services.agents.worker_draft.create_worker_ai_summary_draft",
                side_effect=write,
            ) as write_draft:
                result = _ReferencedDummyAgent().store_summary(
                    conn,
                    {"location_id": LOCATION_ID, "synthesis": "synthetic draft"},
                    request_id="a0000000-0000-4000-8000-000000000003",
                )

    assert result == "stored-id"
    assert sequence == ["create:ai_summary", "read:dummy_record", "collect", "write"]
    assert write_draft.call_args.args[3]["source_references"] == references


def test_store_summary_does_not_write_when_source_reference_collection_fails():
    class _ReferencedDummyAgent(_DummyAgent):
        source_reference_views = {"dummy_table": "v_public_dummy_summary"}

    conn = _FakeConn()
    with mock.patch.object(
        _ReferencedDummyAgent,
        "collect_source_references",
        side_effect=RuntimeError("synthetic source query failure"),
    ):
        with mock.patch(
            "services.agents.worker_draft.create_worker_ai_summary_draft"
        ) as write_draft:
            with pytest.raises(RuntimeError, match="synthetic source query failure"):
                _ReferencedDummyAgent().store_summary(
                    conn,
                    {"location_id": LOCATION_ID, "synthesis": "synthetic draft"},
                )

    write_draft.assert_not_called()
    assert conn.committed is False


def test_store_summary_read_denial_prevents_reference_query_and_signed_write():
    class _ReferencedDummyAgent(_DummyAgent):
        source_reference_views = {"dummy_table": "v_public_dummy_summary"}

    conn = _FakeConn()
    collection = mock.Mock(side_effect=AssertionError("reference query must not run"))
    with mock.patch(
        "services.agents.base.assert_agent_action_allowed",
        side_effect=[None, ValueError("agent read denied")],
    ) as authorize:
        with mock.patch.object(
            _ReferencedDummyAgent, "collect_source_references", collection
        ):
            with mock.patch(
                "services.agents.worker_draft.create_worker_ai_summary_draft"
            ) as write_draft:
                with pytest.raises(ValueError, match="agent read denied"):
                    _ReferencedDummyAgent().store_summary(
                        conn,
                        {"location_id": LOCATION_ID, "synthesis": "synthetic draft"},
                    )

    assert [call.args[:2] for call in authorize.call_args_list] == [
        ("create", "ai_summary"),
        ("read", "dummy_record"),
    ]
    collection.assert_not_called()
    write_draft.assert_not_called()


def test_store_summary_rejects_missing_synthesis_before_cursor_access():
    conn = _FakeConn()

    with pytest.raises(ValueError, match="summary.synthesis must be a non-empty string"):
        _DummyAgent().store_summary(conn, {"location_id": LOCATION_ID})

    assert conn.cursor_obj.executed is None
    assert conn.committed is False


def test_store_summary_rejects_overlong_synthesis_before_cursor_access():
    conn = _FakeConn()

    with pytest.raises(ValueError, match="content must be at most 20000 characters"):
        _DummyAgent().store_summary(
            conn,
            {"location_id": LOCATION_ID, "synthesis": "x" * 20_001},
        )

    assert conn.cursor_obj.executed is None
    assert conn.committed is False


def test_store_summary_rejects_malformed_location_before_cursor_access():
    conn = _FakeConn()

    with pytest.raises(ValueError, match="Invalid task input format for field: location_id"):
        _DummyAgent().store_summary(conn, {"location_id": "bad-id", "synthesis": "draft"})

    assert conn.cursor_obj.executed is None
    assert conn.committed is False


@pytest.mark.parametrize(
    "source_tables",
    [
        [],
        [f"table_{index}" for index in range(21)],
        ["valid_table", "not-valid"],
    ],
)
def test_store_summary_rejects_invalid_source_table_metadata_before_cursor_access(
    source_tables: list[str],
):
    class _InvalidSourceAgent(_DummyAgent):
        pass

    _InvalidSourceAgent.source_tables = source_tables
    conn = _FakeConn()

    with pytest.raises(ValueError, match="source_tables must contain 1 to 20"):
        _InvalidSourceAgent().store_summary(
            conn,
            {"location_id": LOCATION_ID, "synthesis": "synthetic draft"},
        )

    assert conn.cursor_obj.executed is None
    assert conn.cursor_obj.closed is False
    assert conn.committed is False


def test_run_rejects_locationless_storage_before_worker_access():
    class _LocationlessDummyAgent(_DummyAgent):
        task_key = "financial_resilience_synthesis"

    with mock.patch(
        "services.agents.worker_cli.run_worker_synthesis",
        side_effect=AssertionError("worker must not run without location scope"),
    ):
        with pytest.raises(ValueError, match="requires an exact location_id"):
            _LocationlessDummyAgent().run(store=True)


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


def test_run_store_delegates_before_opening_shared_database():
    with mock.patch(
        "services.agents.base.get_db",
        side_effect=AssertionError("base runner must delegate to worker"),
    ):
        with mock.patch(
            "services.agents.worker_cli.run_worker_synthesis",
            return_value={"ai_summary_id": "stored-id"},
        ) as run_worker:
            assert _DummyAgent().run(LOCATION_ID, store=True)["ai_summary_id"] == "stored-id"
    run_worker.assert_called_once()


def test_run_fetch_validates_and_closes():
    conn = _FakeConn()

    def fetch(conn, scorecard_id, location_id):
        return {"scorecard_id": scorecard_id, "location_id": location_id}

    with mock.patch("services.agents.base.get_db", return_value=conn):
        with mock.patch("services.agents.base.assert_agent_action_allowed") as safety:
            with mock.patch("services.agents.base.validate_output", return_value=[]):
                out = run_fetch(
                    "ebf_evidence_gap",
                    "ebf_scorecard",
                    fetch,
                    scorecard_id=SCORECARD_ID,
                    location_id=LOCATION_ID,
                )
    assert out == {"scorecard_id": SCORECARD_ID, "location_id": LOCATION_ID}
    safety.assert_called_once_with(
        "read",
        "ebf_scorecard",
        {"scorecard_id": SCORECARD_ID, "location_id": LOCATION_ID},
    )
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
                run_fetch(
                    "ebf_evidence_gap",
                    "ebf_scorecard",
                    lambda *_args: {},
                    scorecard_id="bad",
                    location_id=LOCATION_ID,
                )
            except ValueError as exc:
                assert "Invalid task input format for field: scorecard_id" in str(exc)
            else:
                raise AssertionError("expected malformed scorecard rejection")
    safety.assert_not_called()


def test_run_fetch_rejects_missing_location_before_database_access():
    with mock.patch("services.agents.base.get_db", side_effect=AssertionError("database opened")):
        with mock.patch("services.agents.base.assert_agent_action_allowed") as safety:
            try:
                run_fetch(
                    "ebf_evidence_gap",
                    "ebf_scorecard",
                    lambda *_args: {},
                    scorecard_id=SCORECARD_ID,
                )
            except ValueError as exc:
                assert "Missing required task input: location_id" in str(exc)
            else:
                raise AssertionError("expected missing location rejection")
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


def test_agent_cli_redacts_content_after_storing_draft():
    agent = _DummyAgent()
    agent.run = mock.Mock(
        return_value={
            "summary": {"synthesis": "private farm content"},
            "ai_summary_id": "saved-id",
            "request_id": "a0000000-0000-4000-8000-000000000005",
            "replayed": False,
        }
    )
    with mock.patch(
        "sys.argv",
        ["prog", "--location-id", LOCATION_ID, "--store"],
    ):
        with mock.patch("services.agents.base.print_json") as print_json:
            agent_cli(agent)

    print_json.assert_called_once_with(
        {
            "ai_summary_id": "saved-id",
            "request_id": "a0000000-0000-4000-8000-000000000005",
            "resulting_status": "draft",
            "replayed": False,
        }
    )
