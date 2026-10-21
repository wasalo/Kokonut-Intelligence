"""Offline contract checks for the signed AI-summary worker entry point."""

import json
import sys
from unittest.mock import MagicMock

import pytest

from services.agents import worker_cli
from services.agents.base import SynthesisAgent

LOCATION_ID = "00000000-0000-0000-0000-000000000123"
REQUEST_ID = "00000000-0000-0000-0000-000000000456"


def test_worker_cli_replays_before_opening_source_database():
    prior = {"summary_id": "saved-id", "replayed": True}
    connection_factory = MagicMock(side_effect=AssertionError("source DB must not open"))
    result = worker_cli.run_worker_summary(
        LOCATION_ID,
        "combined",
        REQUEST_ID,
        connection_factory=connection_factory,
        existing_reader=lambda *_args: prior,
    )

    assert result is prior
    connection_factory.assert_not_called()


def test_worker_cli_reads_only_and_sends_lineage_through_signed_writer():
    cursor = MagicMock()
    connection = MagicMock()
    connection.cursor.return_value.__enter__.return_value = cursor
    summary = {
        "content": "Synthetic summary",
        "source_tables": ["harvest_event"],
        "source_references": {
            "harvest_event": {"record_ids": [LOCATION_ID], "row_count": 1, "truncated": False}
        },
    }
    writer = MagicMock(return_value={"summary_id": "saved-id", "replayed": False})

    result = worker_cli.run_worker_summary(
        LOCATION_ID,
        "operations",
        REQUEST_ID,
        connection_factory=lambda: connection,
        summary_builder=lambda *_args: summary,
        existing_reader=lambda *_args: None,
        draft_writer=writer,
    )

    assert [call.args[0] for call in cursor.execute.call_args_list] == [
        "SET TRANSACTION READ ONLY",
        "SET LOCAL statement_timeout = '15s'",
        "SET LOCAL lock_timeout = '3s'",
    ]
    connection.commit.assert_not_called()
    connection.rollback.assert_not_called()
    connection.close.assert_called_once_with()
    writer.assert_called_once_with(
        LOCATION_ID,
        "operations",
        REQUEST_ID,
        {**summary, "model_version": "rules-v1"},
    )
    assert result == {"summary_id": "saved-id", "replayed": False}


def test_worker_cli_does_not_write_after_source_generation_failure():
    connection = MagicMock()
    writer = MagicMock()

    with pytest.raises(RuntimeError, match="source query failed"):
        worker_cli.run_worker_summary(
            LOCATION_ID,
            "combined",
            REQUEST_ID,
            connection_factory=lambda: connection,
            summary_builder=MagicMock(side_effect=RuntimeError("source query failed")),
            existing_reader=lambda *_args: None,
            draft_writer=writer,
        )

    connection.close.assert_called_once_with()
    connection.rollback.assert_called_once_with()
    writer.assert_not_called()


class _SyntheticSynthesisAgent(SynthesisAgent):
    task_key = "ai_summary_synthesis"
    summary_type = "synthetic_agent"
    read_collection = "ai_summary"
    model_version = "synthetic-v1"
    source_tables = ["harvest_event"]

    def synthesize(self, conn, location_id=None):
        return {"location_id": location_id, "synthesis": "Synthetic agent draft"}


def _source_connection():
    cursor = MagicMock()
    connection = MagicMock()
    connection.cursor.return_value.__enter__.return_value = cursor
    return connection, cursor


def test_generic_synthesis_worker_replays_before_source_reads():
    prior = {"summary_id": "saved-id", "content": "original draft"}
    connection_factory = MagicMock(side_effect=AssertionError("source DB must stay closed"))
    agent = _SyntheticSynthesisAgent()
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(
            "services.agents.safety.assert_agent_action_allowed", lambda *_args: None
        )
        result = worker_cli.run_worker_synthesis(
            agent,
            LOCATION_ID,
            REQUEST_ID,
            connection_factory=connection_factory,
            existing_reader=lambda *_args: prior,
        )

    connection_factory.assert_not_called()
    assert result == {
        "summary": {"location_id": LOCATION_ID, "synthesis": "original draft"},
        "ai_summary_id": "saved-id",
        "request_id": REQUEST_ID,
        "replayed": True,
    }


def test_generic_synthesis_worker_reads_only_then_uses_signed_writer():
    agent = _SyntheticSynthesisAgent()
    connection, cursor = _source_connection()
    writer = MagicMock(return_value={"summary_id": "saved-id", "replayed": False})
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(
            "services.agents.safety.assert_agent_action_allowed", lambda *_args: None
        )
        result = worker_cli.run_worker_synthesis(
            agent,
            LOCATION_ID,
            REQUEST_ID,
            connection_factory=lambda: connection,
            existing_reader=lambda *_args: None,
            draft_writer=writer,
        )

    assert [call.args[0] for call in cursor.execute.call_args_list] == [
        "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY",
        "SET LOCAL statement_timeout = '15s'",
        "SET LOCAL lock_timeout = '3s'",
    ]
    connection.commit.assert_not_called()
    connection.rollback.assert_not_called()
    connection.close.assert_called_once_with()
    writer.assert_called_once_with(
        LOCATION_ID,
        "synthetic_agent",
        REQUEST_ID,
        {
            "content": "Synthetic agent draft",
            "source_tables": ["harvest_event"],
            "model_version": "synthetic-v1",
            "source_references": {},
        },
    )
    assert result == {
        "summary": {"location_id": LOCATION_ID, "synthesis": "Synthetic agent draft"},
        "ai_summary_id": "saved-id",
        "request_id": REQUEST_ID,
        "replayed": False,
    }


def test_generic_synthesis_worker_attaches_collected_refs_from_read_snapshot():
    agent = _SyntheticSynthesisAgent()
    references = {
        "harvest_event": {
            "record_ids": ["e0000000-0000-4000-8000-000000000001"],
            "row_count": 1,
            "truncated": False,
        }
    }
    agent.collect_source_references = MagicMock(return_value=references)
    connection, _cursor = _source_connection()
    writer = MagicMock(return_value={"summary_id": "saved-id", "replayed": False})
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(
            "services.agents.safety.assert_agent_action_allowed", lambda *_args: None
        )
        worker_cli.run_worker_synthesis(
            agent,
            LOCATION_ID,
            REQUEST_ID,
            connection_factory=lambda: connection,
            existing_reader=lambda *_args: None,
            draft_writer=writer,
        )

    agent.collect_source_references.assert_called_once_with(connection, LOCATION_ID)
    assert writer.call_args.args[3]["source_references"] == references
    connection.close.assert_called_once_with()


def test_generic_synthesis_worker_does_not_write_when_reference_collection_fails():
    agent = _SyntheticSynthesisAgent()
    agent.collect_source_references = MagicMock(
        side_effect=RuntimeError("source reference query failed")
    )
    connection, _cursor = _source_connection()
    writer = MagicMock()
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(
            "services.agents.safety.assert_agent_action_allowed", lambda *_args: None
        )
        with pytest.raises(RuntimeError, match="source reference query failed"):
            worker_cli.run_worker_synthesis(
                agent,
                LOCATION_ID,
                REQUEST_ID,
                connection_factory=lambda: connection,
                existing_reader=lambda *_args: None,
                draft_writer=writer,
            )

    connection.rollback.assert_called_once_with()
    connection.close.assert_called_once_with()
    writer.assert_not_called()


def test_generic_synthesis_worker_rejects_locationless_scope_before_connections():
    agent = _SyntheticSynthesisAgent()
    connection_factory = MagicMock(side_effect=AssertionError("DB must stay closed"))
    with pytest.raises(ValueError, match="location_id and request_id must be UUIDs"):
        worker_cli.run_worker_synthesis(
            agent,
            None,
            REQUEST_ID,
            connection_factory=connection_factory,
            existing_reader=lambda *_args: None,
        )
    connection_factory.assert_not_called()


def test_generic_synthesis_worker_rejects_invalid_metadata_before_receipt_lookup():
    agent = _SyntheticSynthesisAgent()
    agent.source_tables = ["harvest_event", "harvest_event"]
    reader = MagicMock(side_effect=AssertionError("invalid metadata must fail first"))
    connection_factory = MagicMock(side_effect=AssertionError("DB must stay closed"))
    with pytest.raises(ValueError, match="source_tables must be unique"):
        worker_cli.run_worker_synthesis(
            agent,
            LOCATION_ID,
            REQUEST_ID,
            connection_factory=connection_factory,
            existing_reader=reader,
        )
    reader.assert_not_called()
    connection_factory.assert_not_called()


def test_generic_synthesis_worker_rolls_back_generation_failure_without_writing():
    agent = _SyntheticSynthesisAgent()
    agent.synthesize = MagicMock(side_effect=RuntimeError("source query failed"))
    connection, _cursor = _source_connection()
    writer = MagicMock()
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(
            "services.agents.safety.assert_agent_action_allowed", lambda *_args: None
        )
        with pytest.raises(RuntimeError, match="source query failed"):
            worker_cli.run_worker_synthesis(
                agent,
                LOCATION_ID,
                REQUEST_ID,
                connection_factory=lambda: connection,
                existing_reader=lambda *_args: None,
                draft_writer=writer,
            )
    connection.rollback.assert_called_once_with()
    connection.close.assert_called_once_with()
    writer.assert_not_called()


def test_generic_synthesis_worker_rejects_invalid_output_without_writing():
    agent = _SyntheticSynthesisAgent()
    agent.synthesize = lambda _conn, _location_id: {"location_id": LOCATION_ID}
    connection, _cursor = _source_connection()
    writer = MagicMock()
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(
            "services.agents.safety.assert_agent_action_allowed", lambda *_args: None
        )
        with pytest.raises(ValueError, match="summary.synthesis must be non-empty text"):
            worker_cli.run_worker_synthesis(
                agent,
                LOCATION_ID,
                REQUEST_ID,
                connection_factory=lambda: connection,
                existing_reader=lambda *_args: None,
                draft_writer=writer,
            )
    connection.close.assert_called_once_with()
    connection.rollback.assert_called_once_with()
    writer.assert_not_called()


def test_worker_cli_resolves_only_registered_synthesis_agents():
    agent = worker_cli.resolve_synthesis_agent("feedback_synthesis")
    assert agent.task_key == "feedback_synthesis"
    with pytest.raises(ValueError, match="not a registered synthesis agent"):
        worker_cli.resolve_synthesis_agent("unregistered_task")


def test_worker_cli_registry_resolves_all_declared_synthesis_tasks():
    resolved = {
        task_key: worker_cli.resolve_synthesis_agent(task_key)
        for task_key in worker_cli._SYNTHESIS_AGENT_MODULES
    }
    assert set(resolved) == set(worker_cli._SYNTHESIS_AGENT_MODULES)
    assert all(agent.task_key == task_key for task_key, agent in resolved.items())


def test_worker_cli_dispatches_registered_synthesis_task_without_content_output(
    monkeypatch, capsys
):
    agent = _SyntheticSynthesisAgent()
    agent.task_key = "feedback_synthesis"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "worker_cli",
            "--location-id",
            LOCATION_ID,
            "--task-key",
            agent.task_key,
            "--request-id",
            REQUEST_ID,
        ],
    )
    monkeypatch.setattr(worker_cli, "resolve_synthesis_agent", lambda _task: agent)
    monkeypatch.setattr(
        worker_cli,
        "run_worker_synthesis",
        lambda *_args: {
            "ai_summary_id": "saved-id",
            "request_id": REQUEST_ID,
            "replayed": False,
            "summary": {"synthesis": "private generated content"},
        },
    )

    worker_cli.main()

    output = capsys.readouterr().out
    assert json.loads(output) == {
        "summary_id": "saved-id",
        "resulting_status": "draft",
        "request_id": REQUEST_ID,
        "replayed": False,
    }
    assert "private generated content" not in output


def test_cli_output_does_not_print_summary_content_or_source_references(monkeypatch, capsys):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "worker_cli",
            "--location-id",
            LOCATION_ID,
            "--summary-type",
            "operations",
            "--request-id",
            REQUEST_ID,
        ],
    )
    monkeypatch.setattr(
        worker_cli,
        "run_worker_summary",
        lambda *_args: {
            "summary_id": "saved-id",
            "resulting_status": "draft",
            "replayed": False,
            "content": "private farm summary",
            "source_references": {"harvest_event": {"record_ids": [LOCATION_ID]}},
        },
    )

    worker_cli.main()

    output = capsys.readouterr().out
    assert json.loads(output) == {
        "summary_id": "saved-id",
        "resulting_status": "draft",
        "request_id": REQUEST_ID,
        "replayed": False,
    }
    assert "private farm summary" not in output
    assert LOCATION_ID not in output
