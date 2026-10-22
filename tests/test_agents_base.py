"""Tests for the shared synthesis agent base (services.agents.base)."""

from __future__ import annotations

from unittest import mock

import pytest

from services.agents.base import SynthesisAgent, agent_cli, run_fetch
from services.agents.bio_factory_agent import BioFactorySynthesisAgent

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


class _MappedDummyAgent(_DummyAgent):
    source_reference_views = {"dummy_table": "v_public_dummy_summary"}


def test_unmapped_synthesis_fails_before_shared_database_access():
    with mock.patch(
        "services.agents.base.get_db",
        side_effect=AssertionError("shared application database must not open"),
        create=True,
    ):
        with pytest.raises(ValueError, match="registered signed source-reference view map"):
            _DummyAgent().run(LOCATION_ID)


def test_run_store_delegates_to_signed_worker_with_stable_request_id():
    stable_request_id = "a0000000-0000-4000-8000-000000000004"
    with mock.patch(
        "services.agents.worker_cli.run_worker_synthesis",
        return_value={"ai_summary_id": "stored-id", "request_id": stable_request_id},
    ) as run_worker:
        out = _MappedDummyAgent().run(LOCATION_ID, store=True, request_id=stable_request_id)
    assert out["ai_summary_id"] == "stored-id"
    run_worker.assert_called_once()
    assert run_worker.call_args.args[1:] == (LOCATION_ID, stable_request_id)


def test_registered_synthesis_read_only_run_uses_signed_worker_source_boundary():
    with mock.patch(
        "services.agents.base.get_db",
        side_effect=AssertionError("registered synthesis must not use shared runtime DB"),
        create=True,
    ):
        with mock.patch(
            "services.agents.worker_cli.run_worker_synthesis",
            return_value={"summary": {"synthesis": "synthetic"}},
        ) as run_worker:
            result = BioFactorySynthesisAgent().run(LOCATION_ID)

    assert result == {"summary": {"synthesis": "synthetic"}}
    run_worker.assert_called_once()
    assert run_worker.call_args.args[1:] == (LOCATION_ID, None)
    assert run_worker.call_args.kwargs == {"persist_draft": False}


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
        with pytest.raises(ValueError, match="location_id"):
            _LocationlessDummyAgent().run(store=True)


def test_mapped_synthesis_read_only_run_uses_worker_validation():
    with mock.patch(
        "services.agents.worker_cli.run_worker_synthesis",
        side_effect=ValueError("worker output rejected"),
    ) as run_worker:
        with pytest.raises(ValueError, match="worker output rejected"):
            _MappedDummyAgent().run(LOCATION_ID)
    run_worker.assert_called_once_with(
        mock.ANY, LOCATION_ID, None, persist_draft=False
    )


def test_run_store_delegates_to_worker_without_shared_database_fallback():
    with mock.patch(
        "services.agents.base.get_db",
        side_effect=AssertionError("shared runtime DB must not be imported or opened"),
        create=True,
    ):
        with mock.patch(
            "services.agents.worker_cli.run_worker_synthesis",
            return_value={"ai_summary_id": "stored-id"},
        ) as run_worker:
            assert _MappedDummyAgent().run(LOCATION_ID, store=True)["ai_summary_id"] == "stored-id"
    run_worker.assert_called_once()


def test_agent_cli_requires_location_for_registered_synthesis_sources(monkeypatch):
    class _ScopedDummyAgent(_DummyAgent):
        source_reference_views = {"example_source": "v_public_example_source"}

        def run(self, *args, **kwargs):
            raise AssertionError("CLI must reject a missing location before running")

    monkeypatch.setattr("sys.argv", ["scoped-agent"])

    with pytest.raises(SystemExit) as exc:
        agent_cli(_ScopedDummyAgent(), location_required=False)

    assert exc.value.code == 2


def test_location_required_synthesis_cli_rejects_malformed_uuid_before_run(monkeypatch):
    class _ScopedDummyAgent(_DummyAgent):
        source_reference_views = {"example_source": "v_public_example_source"}

    monkeypatch.setattr("sys.argv", ["scoped-agent", "--location-id", "not-a-uuid"])

    with pytest.raises(ValueError, match="Invalid task input format for field: location_id"):
        agent_cli(_ScopedDummyAgent(), location_required=False)


def test_run_fetch_is_retired_before_callback_or_database_access():
    fetch = mock.Mock(side_effect=AssertionError("fetch callback must not run"))
    with mock.patch(
        "services.agents.base.get_db",
        side_effect=AssertionError("shared application database must not open"),
        create=True,
    ):
        with mock.patch("services.agents.base.assert_agent_action_allowed") as safety:
            with pytest.raises(RuntimeError, match="run_fetch is retired"):
                run_fetch(
                    "ebf_evidence_gap",
                    "ebf_scorecard",
                    fetch,
                    scorecard_id=SCORECARD_ID,
                    location_id=LOCATION_ID,
                )
    fetch.assert_not_called()
    safety.assert_not_called()


def test_run_rejects_malformed_scope_before_database_access():
    with mock.patch(
        "services.agents.base.get_db",
        side_effect=AssertionError("database opened"),
        create=True,
    ):
        with mock.patch("services.agents.base.assert_agent_action_allowed") as safety:
            try:
                _DummyAgent().run("not-a-uuid")
            except ValueError as exc:
                assert "Invalid task input format for field: location_id" in str(exc)
            else:
                raise AssertionError("expected malformed location rejection")
    safety.assert_not_called()


def test_run_fetch_rejects_malformed_scope_before_database_access():
    with pytest.raises(RuntimeError, match="run_fetch is retired"):
        run_fetch(
            "ebf_evidence_gap",
            "ebf_scorecard",
            lambda *_args: {},
            scorecard_id="bad",
            location_id=LOCATION_ID,
        )


def test_run_fetch_rejects_missing_location_before_database_access():
    with pytest.raises(RuntimeError, match="run_fetch is retired"):
        run_fetch(
            "ebf_evidence_gap",
            "ebf_scorecard",
            lambda *_args: {},
            scorecard_id=SCORECARD_ID,
        )


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
