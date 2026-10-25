"""Offline contract checks for the signed AI-summary worker entry point."""

import hashlib
import json
import sys
from dataclasses import FrozenInstanceError
from unittest.mock import MagicMock

import pytest

from services.agents import worker_cli
from services.agents.bio_factory_agent import BioFactorySynthesisAgent
from services.common.worker_database import WorkerDatabaseConfigurationError

LOCATION_ID = "00000000-0000-0000-0000-000000000123"
REQUEST_ID = "00000000-0000-0000-0000-000000000456"
SUMMARY_ID = "00000000-0000-0000-0000-000000000789"
_OPERATIONS_SOURCES = (
    "harvest_event",
    "sales_event",
    "crop_cycle",
    "sensor_reading",
)


def _operations_summary(**overrides):
    summary = {
        "location_id": LOCATION_ID,
        "summary_type": "operations",
        "content": "Synthetic operations summary",
        "source_tables": list(_OPERATIONS_SOURCES),
        "source_references": {
            table: {
                "record_ids": [LOCATION_ID],
                "row_count": 1,
                "truncated": False,
            }
            for table in _OPERATIONS_SOURCES
        },
    }
    summary.update(overrides)
    return summary


@pytest.fixture(autouse=True)
def _source_worker_credential(monkeypatch):
    monkeypatch.setattr(worker_cli, "get_worker_credential", lambda _key: "s" * 40)


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
    connection, cursor = _source_connection()
    summary = _operations_summary(content="Synthetic summary")
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

    statements = [call.args[0].strip() for call in cursor.execute.call_args_list]
    assert statements[0] == "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"
    assert "set_config(%s, '', TRUE)" in statements[1]
    assert "kokonut_security.set_worker_tenant_context" in statements[2]
    assert statements[3:] == [
        "SET LOCAL ROLE kokonut_agent_summary_deterministic_reader",
        "SET LOCAL search_path = kokonut_agent_source, pg_catalog",
        "SET LOCAL statement_timeout = '15s'",
        "SET LOCAL lock_timeout = '3s'",
    ]
    assert cursor.execute.call_args_list[2].args[1][1:] == (
        LOCATION_ID,
        "ai_summary",
        "read",
    )
    connection.commit.assert_not_called()
    connection.rollback.assert_not_called()
    connection.close.assert_called_once_with()
    writer.assert_called_once_with(
        LOCATION_ID,
        "operations",
        REQUEST_ID,
        {
            **summary,
            "model_version": "rules-v1",
            "worker_result": summary,
        },
    )
    assert result == {"summary_id": "saved-id", "replayed": False}


def test_deterministic_worker_uses_its_task_identity_for_default_draft_writer(
    monkeypatch,
):
    connection, _cursor = _source_connection()
    writer = MagicMock(return_value={"summary_id": "saved-id", "replayed": False})
    monkeypatch.setattr(worker_cli, "create_worker_ai_summary_draft", writer)
    monkeypatch.setattr(
        "services.agents.safety.assert_agent_action_allowed", lambda *_args: None
    )

    worker_cli.run_worker_summary(
        LOCATION_ID,
        "operations",
        REQUEST_ID,
        connection_factory=lambda: connection,
        summary_builder=lambda *_args: _operations_summary(
            content="Task identity draft"
        ),
        existing_reader=lambda *_args: None,
    )

    assert writer.call_args.args[:3] == (LOCATION_ID, "operations", REQUEST_ID)
    assert writer.call_args.kwargs["worker_key"] == "agent_summary_deterministic_source"


def test_kokonut_commons_synthesis_uses_task_specific_source_identity_and_reader(
    monkeypatch,
):
    from services.agents.kokonut_commons_agent import agent

    connection, cursor = _source_connection()
    monkeypatch.setattr(
        agent,
        "synthesize",
        lambda _connection, location_id=None: {
            "location_id": location_id,
            "synthesis": "Synthetic Kokonut Commons draft",
        },
    )
    monkeypatch.setattr(agent, "collect_source_references", lambda *_args: _empty_synthesis_references(agent))
    database_factory = MagicMock(return_value=connection)
    credential_reader = MagicMock(return_value="f" * 40)
    context_setter = MagicMock()
    monkeypatch.setattr(worker_cli, "get_worker_db", database_factory)
    monkeypatch.setattr(worker_cli, "get_worker_credential", credential_reader)
    monkeypatch.setattr(
        worker_cli, "set_agent_summary_source_tenant_context", context_setter
    )
    monkeypatch.setattr(
        "services.agents.safety.assert_agent_action_allowed", lambda *_args: None
    )

    result = worker_cli.run_worker_synthesis(
        agent,
        LOCATION_ID,
        None,
        persist_draft=False,
        existing_reader=MagicMock(side_effect=AssertionError("read-only run has no receipt")),
        draft_writer=MagicMock(side_effect=AssertionError("read-only run cannot write")),
    )

    assert result == {
        "summary": {
            "location_id": LOCATION_ID,
            "synthesis": "Synthetic Kokonut Commons draft",
        }
    }
    credential_reader.assert_called_once_with("agent_kokonut_commons_source")
    database_factory.assert_called_once_with("agent_kokonut_commons_source")
    context_setter.assert_called_once_with(
        connection,
        credential="f" * 40,
        location_id=LOCATION_ID,
    )
    statements = [call.args[0] for call in cursor.execute.call_args_list]
    assert statements == [
        "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY",
        "SET LOCAL ROLE kokonut_agent_kokonut_commons_reader",
        "SET LOCAL statement_timeout = '15s'",
        "SET LOCAL lock_timeout = '3s'",
    ]
    connection.commit.assert_not_called()
    connection.rollback.assert_not_called()
    connection.close.assert_called_once_with()


def test_synthesis_worker_uses_its_task_identity_for_default_draft_writer(monkeypatch):
    from services.agents.kokonut_commons_agent import agent

    connection, _cursor = _source_connection()
    monkeypatch.setattr(
        agent,
        "synthesize",
        lambda _connection, location_id=None: {
            "location_id": location_id,
            "synthesis": "Task-attributed draft",
        },
    )
    monkeypatch.setattr(agent, "collect_source_references", lambda *_args: _empty_synthesis_references(agent))
    monkeypatch.setattr(
        worker_cli,
        "get_worker_db",
        lambda _key: connection,
    )
    writer = MagicMock(return_value={"summary_id": "saved-id", "replayed": False})
    monkeypatch.setattr(worker_cli, "create_worker_ai_summary_draft", writer)
    monkeypatch.setattr(
        worker_cli, "set_agent_summary_source_tenant_context", lambda *_args, **_kwargs: None
    )
    monkeypatch.setattr(
        "services.agents.safety.assert_agent_action_allowed", lambda *_args: None
    )

    worker_cli.run_worker_synthesis(
        agent,
        LOCATION_ID,
        REQUEST_ID,
        existing_reader=lambda *_args: None,
    )

    assert writer.call_args.args[:3] == (
        LOCATION_ID,
        "kokonut_commons",
        REQUEST_ID,
    )
    assert writer.call_args.kwargs["worker_key"] == "agent_kokonut_commons_source"


def test_unregistered_synthesis_task_fails_before_source_identity_lookup(monkeypatch):
    agent = _synthetic_synthesis_agent()
    monkeypatch.setattr(
        worker_cli,
        "_SYNTHESIS_WORKERS",
        {
            task_key: spec
            for task_key, spec in worker_cli._SYNTHESIS_WORKERS.items()
            if task_key != agent.task_key
        },
    )
    credential_reader = MagicMock(side_effect=AssertionError("no source credential lookup"))
    database_factory = MagicMock(side_effect=AssertionError("no database connection"))
    monkeypatch.setattr(worker_cli, "get_worker_credential", credential_reader)
    monkeypatch.setattr(worker_cli, "get_worker_db", database_factory)
    monkeypatch.setattr(
        "services.agents.safety.assert_agent_action_allowed", lambda *_args: None
    )

    with pytest.raises(ValueError, match="not a registered synthesis agent"):
        worker_cli.run_worker_synthesis(
            agent,
            LOCATION_ID,
            None,
            persist_draft=False,
            existing_reader=MagicMock(side_effect=AssertionError("no receipt")),
            draft_writer=MagicMock(side_effect=AssertionError("no draft write")),
        )

    credential_reader.assert_not_called()
    database_factory.assert_not_called()


def test_every_registered_synthesis_task_has_an_isolated_source_contract():
    workers = worker_cli._SYNTHESIS_WORKERS

    assert len(workers) == 12
    assert all(spec.agent_module.startswith("services.agents.") for spec in workers.values())
    assert all(spec.source_identity.endswith("_source") for spec in workers.values())
    assert all(spec.source_reader.startswith("kokonut_agent_") for spec in workers.values())
    assert len({spec.source_identity for spec in workers.values()}) == len(workers)
    assert len({spec.source_reader for spec in workers.values()}) == len(workers)
    with pytest.raises(TypeError):
        workers["unregistered_task"] = next(iter(workers.values()))
    with pytest.raises(FrozenInstanceError):
        workers["feedback_synthesis"].source_identity = "shared_source"


def test_worker_cli_does_not_write_after_source_generation_failure():
    connection, _cursor = _source_connection()
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


def test_delphi_agent_worker_uses_signed_location_and_safe_projection(monkeypatch):
    connection, cursor = _source_connection()
    study_id = "00000000-0000-0000-0000-000000000abc"
    source_row = {
        "study_id": study_id,
        "location_id": LOCATION_ID,
        "title": "Synthetic consultation",
        "status": "open",
        "panel_size_available": True,
        "panel_size": 4,
        "items": [{"label": "Synthetic item", "results_available": True}],
    }
    cursor.fetchone.side_effect = [
        ("a0000000-0000-4000-8000-000000000801", LOCATION_ID,
         "a0000000-0000-4000-8000-000000000901", "system_worker"),
        source_row,
    ]
    monkeypatch.setattr(worker_cli, "get_worker_db", lambda _key: connection)
    credential_reader = MagicMock(return_value="d" * 40)
    monkeypatch.setattr(worker_cli, "get_worker_credential", credential_reader)
    monkeypatch.setattr(
        "services.agents.safety.assert_agent_action_allowed", lambda *_args: None
    )

    result = worker_cli.run_worker_delphi_facilitation(study_id, LOCATION_ID)

    statements = [call.args[0].strip() for call in cursor.execute.call_args_list]
    assert statements[0] == "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"
    assert "kokonut_security.set_worker_tenant_context" in statements[2]
    assert cursor.execute.call_args_list[2].args[1][1:] == (
        LOCATION_ID,
        "delphi",
        "read",
    )
    assert statements[3:7] == [
        "SET LOCAL ROLE kokonut_agent_delphi_source_reader",
        "SET LOCAL search_path = kokonut_agent_source, pg_catalog",
        "SET LOCAL statement_timeout = '15s'",
        "SET LOCAL lock_timeout = '3s'",
    ]
    credential_reader.assert_called_once_with("agent_delphi_source")
    assert "FROM kokonut_agent_source.delphi_live_summary" in statements[-1]
    assert cursor.execute.call_args_list[-1].args[1] == (study_id, LOCATION_ID)
    assert result == source_row
    connection.commit.assert_not_called()
    connection.rollback.assert_not_called()
    connection.close.assert_called_once_with()


def test_delphi_agent_worker_rejects_mismatched_source_location(monkeypatch):
    connection, cursor = _source_connection()
    cursor.fetchone.side_effect = [
        ("a0000000-0000-4000-8000-000000000801", LOCATION_ID,
         "a0000000-0000-4000-8000-000000000901", "system_worker"),
        {"study_id": "00000000-0000-0000-0000-000000000abc",
         "location_id": REQUEST_ID},
    ]
    monkeypatch.setattr(worker_cli, "get_worker_db", lambda _key: connection)
    monkeypatch.setattr(
        "services.agents.safety.assert_agent_action_allowed", lambda *_args: None
    )

    with pytest.raises(PermissionError, match="mismatched location"):
        worker_cli.run_worker_delphi_facilitation(
            "00000000-0000-0000-0000-000000000abc", LOCATION_ID
        )

    connection.rollback.assert_called_once_with()
    connection.close.assert_called_once_with()


def _synthetic_synthesis_agent() -> BioFactorySynthesisAgent:
    agent = BioFactorySynthesisAgent()
    agent.synthesize = lambda _conn, location_id=None: {
        "location_id": location_id,
        "synthesis": "Synthetic agent draft",
    }
    agent.collect_source_references = lambda *_args: _empty_synthesis_references(agent)
    return agent


def _empty_synthesis_references(agent):
    references = {}
    for table in type(agent).source_reference_views:
        reference = {"record_ids": [], "row_count": 0, "truncated": False}
        scope = type(agent).source_reference_scopes.get(table, "location")
        if scope != "location":
            reference["scope"] = scope
        references[table] = reference
    return references


def _source_connection():
    cursor = MagicMock()
    cursor.fetchone.return_value = (
        "a0000000-0000-0000-0000-000000000801",
        LOCATION_ID,
        "a0000000-0000-0000-0000-000000000901",
        "system_worker",
    )
    connection = MagicMock()
    connection.autocommit = False
    connection.cursor.return_value.__enter__.return_value = cursor
    return connection, cursor


def test_generic_synthesis_worker_replays_before_source_reads():
    prior = {"summary_id": "saved-id", "content": "original draft"}
    connection_factory = MagicMock(side_effect=AssertionError("source DB must stay closed"))
    agent = _synthetic_synthesis_agent()
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


def test_generic_synthesis_worker_replays_full_stored_structured_result():
    original = {
        "location_id": LOCATION_ID,
        "synthesis": "original draft",
        "confidence": 0.75,
        "source_count": 4,
    }
    connection_factory = MagicMock(side_effect=AssertionError("source DB must stay closed"))
    agent = _synthetic_synthesis_agent()
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(
            "services.agents.safety.assert_agent_action_allowed", lambda *_args: None
        )
        result = worker_cli.run_worker_synthesis(
            agent,
            LOCATION_ID,
            REQUEST_ID,
            connection_factory=connection_factory,
            existing_reader=lambda *_args: {
                "summary_id": "saved-id",
                "content": original["synthesis"],
                "worker_result": original,
            },
        )

    connection_factory.assert_not_called()
    assert result["summary"] == original


def test_generic_synthesis_worker_stops_before_source_reads_when_retry_lookup_rejects_intent():
    connection_factory = MagicMock(side_effect=AssertionError("source DB must stay closed"))
    agent = _synthetic_synthesis_agent()
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(
            "services.agents.safety.assert_agent_action_allowed", lambda *_args: None
        )
        with pytest.raises(RuntimeError, match="request identifier was reused"):
            worker_cli.run_worker_synthesis(
                agent,
                LOCATION_ID,
                REQUEST_ID,
                connection_factory=connection_factory,
                existing_reader=lambda *_args: (_ for _ in ()).throw(
                    RuntimeError("request identifier was reused for another intent")
                ),
            )

    connection_factory.assert_not_called()


def test_generic_synthesis_worker_rejects_instance_source_query_override_preflight():
    connection_factory = MagicMock(side_effect=AssertionError("source DB must stay closed"))
    existing_reader = MagicMock(side_effect=AssertionError("receipt lookup must stay closed"))
    agent = _synthetic_synthesis_agent()
    agent.source_reference_query = "SELECT 'harvest_event' AS source_table, id FROM harvest_event"
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(
            "services.agents.safety.assert_agent_action_allowed", lambda *_args: None
        )
        with pytest.raises(ValueError, match="metadata differs from its registered class"):
            worker_cli.run_worker_synthesis(
                agent,
                LOCATION_ID,
                REQUEST_ID,
                connection_factory=connection_factory,
                existing_reader=existing_reader,
            )

    connection_factory.assert_not_called()
    existing_reader.assert_not_called()


def test_generic_synthesis_worker_reads_only_then_uses_signed_writer():
    agent = _synthetic_synthesis_agent()
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

    statements = [call.args[0] for call in cursor.execute.call_args_list]
    assert statements[0] == "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"
    assert "set_config(%s, '', TRUE)" in statements[1]
    assert "kokonut_security.set_worker_tenant_context" in statements[2]
    assert statements[3:] == [
        "SET LOCAL ROLE kokonut_agent_bio_factory_reader",
        "SET LOCAL statement_timeout = '15s'",
        "SET LOCAL lock_timeout = '3s'",
    ]
    assert "SET LOCAL ROLE kokonut_worker_execution" not in statements
    connection.commit.assert_not_called()
    connection.rollback.assert_not_called()
    connection.close.assert_called_once_with()
    writer.assert_called_once_with(
        LOCATION_ID,
        "bio_factory",
        REQUEST_ID,
        {
            "content": "Synthetic agent draft",
            "source_tables": BioFactorySynthesisAgent.source_tables,
            "model_version": BioFactorySynthesisAgent.model_version,
            "source_references": _empty_synthesis_references(agent),
            "worker_result": {
                "location_id": LOCATION_ID,
                "synthesis": "Synthetic agent draft",
            },
        },
    )
    assert result == {
        "summary": {"location_id": LOCATION_ID, "synthesis": "Synthetic agent draft"},
        "ai_summary_id": "saved-id",
        "request_id": REQUEST_ID,
        "replayed": False,
    }


def test_synthesis_worker_defaults_to_isolated_source_login_not_shared_database(
    monkeypatch,
):
    agent = _synthetic_synthesis_agent()
    connection, _cursor = _source_connection()
    source_factory = MagicMock(return_value=connection)
    monkeypatch.setattr(worker_cli, "get_worker_db", source_factory)
    monkeypatch.setattr(
        "services.agents.safety.assert_agent_action_allowed", lambda *_args: None
    )

    worker_cli.run_worker_synthesis(
        agent,
        LOCATION_ID,
        REQUEST_ID,
        existing_reader=lambda *_args: None,
        draft_writer=lambda *_args: {"summary_id": "saved-id", "replayed": False},
    )

    source_factory.assert_called_once_with("agent_bio_factory_source")


def test_organic_readiness_synthesis_uses_task_specific_source_identity_and_reader(
    monkeypatch,
):
    from services.agents.organic_readiness_agent import agent

    connection, cursor = _source_connection()
    monkeypatch.setattr(
        agent,
        "synthesize",
        lambda _connection, location_id=None: {
            "location_id": location_id,
            "synthesis": "Synthetic organic readiness draft",
        },
    )
    monkeypatch.setattr(agent, "collect_source_references", lambda *_args: _empty_synthesis_references(agent))
    database_factory = MagicMock(return_value=connection)
    credential_reader = MagicMock(return_value="o" * 40)
    context_setter = MagicMock()
    monkeypatch.setattr(worker_cli, "get_worker_db", database_factory)
    monkeypatch.setattr(worker_cli, "get_worker_credential", credential_reader)
    monkeypatch.setattr(
        worker_cli, "set_agent_summary_source_tenant_context", context_setter
    )
    monkeypatch.setattr(
        "services.agents.safety.assert_agent_action_allowed", lambda *_args: None
    )

    result = worker_cli.run_worker_synthesis(
        agent,
        LOCATION_ID,
        None,
        persist_draft=False,
        existing_reader=MagicMock(side_effect=AssertionError("read-only run has no receipt")),
        draft_writer=MagicMock(side_effect=AssertionError("read-only run cannot write")),
    )

    assert result == {
        "summary": {
            "location_id": LOCATION_ID,
            "synthesis": "Synthetic organic readiness draft",
        }
    }
    credential_reader.assert_called_once_with("agent_organic_readiness_source")
    database_factory.assert_called_once_with("agent_organic_readiness_source")
    context_setter.assert_called_once_with(
        connection,
        credential="o" * 40,
        location_id=LOCATION_ID,
    )
    statements = [call.args[0] for call in cursor.execute.call_args_list]
    assert statements == [
        "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY",
        "SET LOCAL ROLE kokonut_agent_organic_readiness_reader",
        "SET LOCAL statement_timeout = '15s'",
        "SET LOCAL lock_timeout = '3s'",
    ]
    connection.commit.assert_not_called()
    connection.rollback.assert_not_called()
    connection.close.assert_called_once_with()


def test_ecological_modeling_synthesis_uses_task_specific_source_identity_and_reader(
    monkeypatch,
):
    from services.agents.ecological_modeling_agent import agent

    connection, cursor = _source_connection()
    monkeypatch.setattr(
        agent,
        "synthesize",
        lambda _connection, location_id=None: {
            "location_id": location_id,
            "synthesis": "Synthetic ecological modeling draft",
        },
    )
    monkeypatch.setattr(agent, "collect_source_references", lambda *_args: _empty_synthesis_references(agent))
    database_factory = MagicMock(return_value=connection)
    credential_reader = MagicMock(return_value="e" * 40)
    context_setter = MagicMock()
    monkeypatch.setattr(worker_cli, "get_worker_db", database_factory)
    monkeypatch.setattr(worker_cli, "get_worker_credential", credential_reader)
    monkeypatch.setattr(
        worker_cli, "set_agent_summary_source_tenant_context", context_setter
    )
    monkeypatch.setattr(
        "services.agents.safety.assert_agent_action_allowed", lambda *_args: None
    )

    result = worker_cli.run_worker_synthesis(
        agent,
        LOCATION_ID,
        None,
        persist_draft=False,
        existing_reader=MagicMock(side_effect=AssertionError("read-only run has no receipt")),
        draft_writer=MagicMock(side_effect=AssertionError("read-only run cannot write")),
    )

    assert result == {
        "summary": {
            "location_id": LOCATION_ID,
            "synthesis": "Synthetic ecological modeling draft",
        }
    }
    credential_reader.assert_called_once_with("agent_ecological_modeling_source")
    database_factory.assert_called_once_with("agent_ecological_modeling_source")
    context_setter.assert_called_once_with(
        connection,
        credential="e" * 40,
        location_id=LOCATION_ID,
    )
    statements = [call.args[0] for call in cursor.execute.call_args_list]
    assert statements == [
        "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY",
        "SET LOCAL ROLE kokonut_agent_ecological_modeling_reader",
        "SET LOCAL statement_timeout = '15s'",
        "SET LOCAL lock_timeout = '3s'",
    ]
    connection.commit.assert_not_called()
    connection.rollback.assert_not_called()
    connection.close.assert_called_once_with()


def test_holistic_wellbeing_synthesis_uses_task_specific_source_identity_and_reader(
    monkeypatch,
):
    from services.agents.wellbeing_agent import agent

    connection, cursor = _source_connection()
    monkeypatch.setattr(
        agent,
        "synthesize",
        lambda _connection, location_id=None: {
            "location_id": location_id,
            "synthesis": "Synthetic holistic wellbeing draft",
        },
    )
    monkeypatch.setattr(agent, "collect_source_references", lambda *_args: _empty_synthesis_references(agent))
    database_factory = MagicMock(return_value=connection)
    credential_reader = MagicMock(return_value="w" * 40)
    context_setter = MagicMock()
    monkeypatch.setattr(worker_cli, "get_worker_db", database_factory)
    monkeypatch.setattr(worker_cli, "get_worker_credential", credential_reader)
    monkeypatch.setattr(
        worker_cli, "set_agent_summary_source_tenant_context", context_setter
    )
    monkeypatch.setattr(
        "services.agents.safety.assert_agent_action_allowed", lambda *_args: None
    )

    result = worker_cli.run_worker_synthesis(
        agent,
        LOCATION_ID,
        None,
        persist_draft=False,
        existing_reader=MagicMock(side_effect=AssertionError("read-only run has no receipt")),
        draft_writer=MagicMock(side_effect=AssertionError("read-only run cannot write")),
    )

    assert result == {
        "summary": {
            "location_id": LOCATION_ID,
            "synthesis": "Synthetic holistic wellbeing draft",
        }
    }
    credential_reader.assert_called_once_with("agent_holistic_wellbeing_source")
    database_factory.assert_called_once_with("agent_holistic_wellbeing_source")
    context_setter.assert_called_once_with(
        connection,
        credential="w" * 40,
        location_id=LOCATION_ID,
    )
    statements = [call.args[0] for call in cursor.execute.call_args_list]
    assert statements == [
        "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY",
        "SET LOCAL ROLE kokonut_agent_holistic_wellbeing_reader",
        "SET LOCAL statement_timeout = '15s'",
        "SET LOCAL lock_timeout = '3s'",
    ]
    connection.commit.assert_not_called()
    connection.rollback.assert_not_called()
    connection.close.assert_called_once_with()


def test_feedback_synthesis_uses_task_specific_source_identity_and_reader(monkeypatch):
    from services.agents.feedback_agent import agent

    connection, cursor = _source_connection()
    monkeypatch.setattr(
        agent,
        "synthesize",
        lambda _connection, location_id=None: {
            "location_id": location_id,
            "synthesis": "Synthetic feedback draft",
        },
    )
    monkeypatch.setattr(agent, "collect_source_references", lambda *_args: _empty_synthesis_references(agent))
    database_factory = MagicMock(return_value=connection)
    credential_reader = MagicMock(return_value="f" * 40)
    context_setter = MagicMock()
    monkeypatch.setattr(worker_cli, "get_worker_db", database_factory)
    monkeypatch.setattr(worker_cli, "get_worker_credential", credential_reader)
    monkeypatch.setattr(
        worker_cli, "set_agent_summary_source_tenant_context", context_setter
    )
    monkeypatch.setattr(
        "services.agents.safety.assert_agent_action_allowed", lambda *_args: None
    )

    result = worker_cli.run_worker_synthesis(
        agent,
        LOCATION_ID,
        None,
        persist_draft=False,
        existing_reader=MagicMock(side_effect=AssertionError("read-only run has no receipt")),
        draft_writer=MagicMock(side_effect=AssertionError("read-only run cannot write")),
    )

    assert result == {
        "summary": {
            "location_id": LOCATION_ID,
            "synthesis": "Synthetic feedback draft",
        }
    }
    credential_reader.assert_called_once_with("agent_feedback_source")
    database_factory.assert_called_once_with("agent_feedback_source")
    context_setter.assert_called_once_with(
        connection,
        credential="f" * 40,
        location_id=LOCATION_ID,
    )
    statements = [call.args[0] for call in cursor.execute.call_args_list]
    assert statements == [
        "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY",
        "SET LOCAL ROLE kokonut_agent_feedback_reader",
        "SET LOCAL statement_timeout = '15s'",
        "SET LOCAL lock_timeout = '3s'",
    ]
    connection.commit.assert_not_called()
    connection.rollback.assert_not_called()
    connection.close.assert_called_once_with()


def test_commons_liberation_synthesis_uses_task_specific_source_identity_and_reader(
    monkeypatch,
):
    from services.agents.commons_agent import agent

    connection, cursor = _source_connection()
    monkeypatch.setattr(
        agent,
        "synthesize",
        lambda _connection, location_id=None: {
            "location_id": location_id,
            "synthesis": "Synthetic commons liberation draft",
        },
    )
    monkeypatch.setattr(agent, "collect_source_references", lambda *_args: _empty_synthesis_references(agent))
    database_factory = MagicMock(return_value=connection)
    credential_reader = MagicMock(return_value="c" * 40)
    context_setter = MagicMock()
    monkeypatch.setattr(worker_cli, "get_worker_db", database_factory)
    monkeypatch.setattr(worker_cli, "get_worker_credential", credential_reader)
    monkeypatch.setattr(
        worker_cli, "set_agent_summary_source_tenant_context", context_setter
    )
    monkeypatch.setattr(
        "services.agents.safety.assert_agent_action_allowed", lambda *_args: None
    )

    result = worker_cli.run_worker_synthesis(
        agent,
        LOCATION_ID,
        None,
        persist_draft=False,
        existing_reader=MagicMock(side_effect=AssertionError("read-only run has no receipt")),
        draft_writer=MagicMock(side_effect=AssertionError("read-only run cannot write")),
    )

    assert result == {
        "summary": {
            "location_id": LOCATION_ID,
            "synthesis": "Synthetic commons liberation draft",
        }
    }
    credential_reader.assert_called_once_with("agent_commons_liberation_source")
    database_factory.assert_called_once_with("agent_commons_liberation_source")
    context_setter.assert_called_once_with(
        connection,
        credential="c" * 40,
        location_id=LOCATION_ID,
    )
    statements = [call.args[0] for call in cursor.execute.call_args_list]
    assert statements == [
        "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY",
        "SET LOCAL ROLE kokonut_agent_commons_liberation_reader",
        "SET LOCAL statement_timeout = '15s'",
        "SET LOCAL lock_timeout = '3s'",
    ]
    connection.commit.assert_not_called()
    connection.rollback.assert_not_called()
    connection.close.assert_called_once_with()


def test_gnh_alignment_synthesis_uses_task_specific_source_identity_and_reader(
    monkeypatch,
):
    from services.agents.gnh_agent import agent

    connection, cursor = _source_connection()
    monkeypatch.setattr(
        agent,
        "synthesize",
        lambda _connection, location_id=None: {
            "location_id": location_id,
            "synthesis": "Synthetic GNH alignment draft",
        },
    )
    monkeypatch.setattr(agent, "collect_source_references", lambda *_args: _empty_synthesis_references(agent))
    database_factory = MagicMock(return_value=connection)
    credential_reader = MagicMock(return_value="g" * 40)
    context_setter = MagicMock()
    monkeypatch.setattr(worker_cli, "get_worker_db", database_factory)
    monkeypatch.setattr(worker_cli, "get_worker_credential", credential_reader)
    monkeypatch.setattr(
        worker_cli, "set_agent_summary_source_tenant_context", context_setter
    )
    monkeypatch.setattr(
        "services.agents.safety.assert_agent_action_allowed", lambda *_args: None
    )

    result = worker_cli.run_worker_synthesis(
        agent,
        LOCATION_ID,
        None,
        persist_draft=False,
        existing_reader=MagicMock(side_effect=AssertionError("read-only run has no receipt")),
        draft_writer=MagicMock(side_effect=AssertionError("read-only run cannot write")),
    )

    assert result == {
        "summary": {
            "location_id": LOCATION_ID,
            "synthesis": "Synthetic GNH alignment draft",
        }
    }
    credential_reader.assert_called_once_with("agent_gnh_alignment_source")
    database_factory.assert_called_once_with("agent_gnh_alignment_source")
    context_setter.assert_called_once_with(
        connection,
        credential="g" * 40,
        location_id=LOCATION_ID,
    )
    statements = [call.args[0] for call in cursor.execute.call_args_list]
    assert statements == [
        "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY",
        "SET LOCAL ROLE kokonut_agent_gnh_alignment_reader",
        "SET LOCAL statement_timeout = '15s'",
        "SET LOCAL lock_timeout = '3s'",
    ]
    connection.commit.assert_not_called()
    connection.rollback.assert_not_called()
    connection.close.assert_called_once_with()


def test_regenerator_synthesis_uses_task_specific_source_identity_and_reader(
    monkeypatch,
):
    from services.agents.regenerator_agent import agent

    connection, cursor = _source_connection()
    monkeypatch.setattr(
        agent,
        "synthesize",
        lambda _connection, location_id=None: {
            "location_id": location_id,
            "synthesis": "Synthetic regenerator draft",
        },
    )
    monkeypatch.setattr(agent, "collect_source_references", lambda *_args: _empty_synthesis_references(agent))
    database_factory = MagicMock(return_value=connection)
    credential_reader = MagicMock(return_value="r" * 40)
    context_setter = MagicMock()
    monkeypatch.setattr(worker_cli, "get_worker_db", database_factory)
    monkeypatch.setattr(worker_cli, "get_worker_credential", credential_reader)
    monkeypatch.setattr(
        worker_cli, "set_agent_summary_source_tenant_context", context_setter
    )
    monkeypatch.setattr(
        "services.agents.safety.assert_agent_action_allowed", lambda *_args: None
    )

    result = worker_cli.run_worker_synthesis(
        agent,
        LOCATION_ID,
        None,
        persist_draft=False,
        existing_reader=MagicMock(side_effect=AssertionError("read-only run has no receipt")),
        draft_writer=MagicMock(side_effect=AssertionError("read-only run cannot write")),
    )

    assert result == {
        "summary": {
            "location_id": LOCATION_ID,
            "synthesis": "Synthetic regenerator draft",
        }
    }
    credential_reader.assert_called_once_with("agent_regenerator_source")
    database_factory.assert_called_once_with("agent_regenerator_source")
    context_setter.assert_called_once_with(
        connection,
        credential="r" * 40,
        location_id=LOCATION_ID,
    )
    statements = [call.args[0] for call in cursor.execute.call_args_list]
    assert statements == [
        "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY",
        "SET LOCAL ROLE kokonut_agent_regenerator_reader",
        "SET LOCAL statement_timeout = '15s'",
        "SET LOCAL lock_timeout = '3s'",
    ]
    connection.commit.assert_not_called()
    connection.rollback.assert_not_called()
    connection.close.assert_called_once_with()


def test_capital_efficiency_synthesis_uses_task_specific_source_identity_and_reader(
    monkeypatch,
):
    from services.agents.capital_efficiency_agent import agent

    connection, cursor = _source_connection()
    monkeypatch.setattr(
        agent,
        "synthesize",
        lambda _connection, location_id=None: {
            "location_id": location_id,
            "synthesis": "Synthetic capital efficiency draft",
        },
    )
    monkeypatch.setattr(agent, "collect_source_references", lambda *_args: _empty_synthesis_references(agent))
    database_factory = MagicMock(return_value=connection)
    credential_reader = MagicMock(return_value="c" * 40)
    context_setter = MagicMock()
    monkeypatch.setattr(worker_cli, "get_worker_db", database_factory)
    monkeypatch.setattr(worker_cli, "get_worker_credential", credential_reader)
    monkeypatch.setattr(
        worker_cli, "set_agent_summary_source_tenant_context", context_setter
    )
    monkeypatch.setattr(
        "services.agents.safety.assert_agent_action_allowed", lambda *_args: None
    )

    result = worker_cli.run_worker_synthesis(
        agent,
        LOCATION_ID,
        None,
        persist_draft=False,
        existing_reader=MagicMock(side_effect=AssertionError("read-only run has no receipt")),
        draft_writer=MagicMock(side_effect=AssertionError("read-only run cannot write")),
    )

    assert result == {
        "summary": {
            "location_id": LOCATION_ID,
            "synthesis": "Synthetic capital efficiency draft",
        }
    }
    credential_reader.assert_called_once_with("agent_capital_efficiency_source")
    database_factory.assert_called_once_with("agent_capital_efficiency_source")
    context_setter.assert_called_once_with(
        connection,
        credential="c" * 40,
        location_id=LOCATION_ID,
    )
    statements = [call.args[0] for call in cursor.execute.call_args_list]
    assert statements == [
        "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY",
        "SET LOCAL ROLE kokonut_agent_capital_efficiency_reader",
        "SET LOCAL statement_timeout = '15s'",
        "SET LOCAL lock_timeout = '3s'",
    ]
    connection.commit.assert_not_called()
    connection.rollback.assert_not_called()
    connection.close.assert_called_once_with()


def test_financial_resilience_synthesis_uses_task_specific_source_identity_and_reader(
    monkeypatch,
):
    from services.agents.resilience_agent import agent

    connection, cursor = _source_connection()
    monkeypatch.setattr(
        agent,
        "synthesize",
        lambda _connection, location_id=None: {
            "location_id": location_id,
            "synthesis": "Synthetic financial resilience draft",
        },
    )
    monkeypatch.setattr(agent, "collect_source_references", lambda *_args: _empty_synthesis_references(agent))
    database_factory = MagicMock(return_value=connection)
    credential_reader = MagicMock(return_value="f" * 40)
    context_setter = MagicMock()
    monkeypatch.setattr(worker_cli, "get_worker_db", database_factory)
    monkeypatch.setattr(worker_cli, "get_worker_credential", credential_reader)
    monkeypatch.setattr(
        worker_cli, "set_agent_summary_source_tenant_context", context_setter
    )
    monkeypatch.setattr(
        "services.agents.safety.assert_agent_action_allowed", lambda *_args: None
    )

    result = worker_cli.run_worker_synthesis(
        agent,
        LOCATION_ID,
        None,
        persist_draft=False,
        existing_reader=MagicMock(side_effect=AssertionError("read-only run has no receipt")),
        draft_writer=MagicMock(side_effect=AssertionError("read-only run cannot write")),
    )

    assert result == {
        "summary": {
            "location_id": LOCATION_ID,
            "synthesis": "Synthetic financial resilience draft",
        }
    }
    credential_reader.assert_called_once_with("agent_financial_resilience_source")
    database_factory.assert_called_once_with("agent_financial_resilience_source")
    context_setter.assert_called_once_with(
        connection,
        credential="f" * 40,
        location_id=LOCATION_ID,
    )
    statements = [call.args[0] for call in cursor.execute.call_args_list]
    assert statements == [
        "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY",
        "SET LOCAL ROLE kokonut_agent_financial_resilience_reader",
        "SET LOCAL statement_timeout = '15s'",
        "SET LOCAL lock_timeout = '3s'",
    ]
    connection.commit.assert_not_called()
    connection.rollback.assert_not_called()
    connection.close.assert_called_once_with()


def test_bio_factory_synthesis_uses_task_specific_source_identity_and_reader(
    monkeypatch,
):
    from services.agents.bio_factory_agent import agent

    connection, cursor = _source_connection()
    monkeypatch.setattr(
        agent,
        "synthesize",
        lambda _connection, location_id=None: {
            "location_id": location_id,
            "synthesis": "Synthetic bio factory draft",
        },
    )
    monkeypatch.setattr(agent, "collect_source_references", lambda *_args: _empty_synthesis_references(agent))
    database_factory = MagicMock(return_value=connection)
    credential_reader = MagicMock(return_value="f" * 40)
    context_setter = MagicMock()
    monkeypatch.setattr(worker_cli, "get_worker_db", database_factory)
    monkeypatch.setattr(worker_cli, "get_worker_credential", credential_reader)
    monkeypatch.setattr(
        worker_cli, "set_agent_summary_source_tenant_context", context_setter
    )
    monkeypatch.setattr(
        "services.agents.safety.assert_agent_action_allowed", lambda *_args: None
    )

    result = worker_cli.run_worker_synthesis(
        agent,
        LOCATION_ID,
        None,
        persist_draft=False,
        existing_reader=MagicMock(side_effect=AssertionError("read-only run has no receipt")),
        draft_writer=MagicMock(side_effect=AssertionError("read-only run cannot write")),
    )

    assert result == {
        "summary": {
            "location_id": LOCATION_ID,
            "synthesis": "Synthetic bio factory draft",
        }
    }
    credential_reader.assert_called_once_with("agent_bio_factory_source")
    database_factory.assert_called_once_with("agent_bio_factory_source")
    context_setter.assert_called_once_with(
        connection,
        credential="f" * 40,
        location_id=LOCATION_ID,
    )
    statements = [call.args[0] for call in cursor.execute.call_args_list]
    assert statements == [
        "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY",
        "SET LOCAL ROLE kokonut_agent_bio_factory_reader",
        "SET LOCAL statement_timeout = '15s'",
        "SET LOCAL lock_timeout = '3s'",
    ]
    connection.commit.assert_not_called()
    connection.rollback.assert_not_called()
    connection.close.assert_called_once_with()


def test_open_source_capitalist_synthesis_uses_task_specific_source_identity_and_reader(
    monkeypatch,
):
    from services.agents.open_source_capitalist_agent import agent

    connection, cursor = _source_connection()
    monkeypatch.setattr(
        agent,
        "synthesize",
        lambda _connection, location_id=None: {
            "location_id": location_id,
            "synthesis": "Synthetic open source capitalist draft",
        },
    )
    monkeypatch.setattr(agent, "collect_source_references", lambda *_args: _empty_synthesis_references(agent))
    database_factory = MagicMock(return_value=connection)
    credential_reader = MagicMock(return_value="f" * 40)
    context_setter = MagicMock()
    monkeypatch.setattr(worker_cli, "get_worker_db", database_factory)
    monkeypatch.setattr(worker_cli, "get_worker_credential", credential_reader)
    monkeypatch.setattr(
        worker_cli, "set_agent_summary_source_tenant_context", context_setter
    )
    monkeypatch.setattr(
        "services.agents.safety.assert_agent_action_allowed", lambda *_args: None
    )

    result = worker_cli.run_worker_synthesis(
        agent,
        LOCATION_ID,
        None,
        persist_draft=False,
        existing_reader=MagicMock(side_effect=AssertionError("read-only run has no receipt")),
        draft_writer=MagicMock(side_effect=AssertionError("read-only run cannot write")),
    )

    assert result == {
        "summary": {
            "location_id": LOCATION_ID,
            "synthesis": "Synthetic open source capitalist draft",
        }
    }
    credential_reader.assert_called_once_with("agent_open_source_capitalist_source")
    database_factory.assert_called_once_with("agent_open_source_capitalist_source")
    context_setter.assert_called_once_with(
        connection,
        credential="f" * 40,
        location_id=LOCATION_ID,
    )
    statements = [call.args[0] for call in cursor.execute.call_args_list]
    assert statements == [
        "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY",
        "SET LOCAL ROLE kokonut_agent_open_source_capitalist_reader",
        "SET LOCAL statement_timeout = '15s'",
        "SET LOCAL lock_timeout = '3s'",
    ]
    connection.commit.assert_not_called()
    connection.rollback.assert_not_called()
    connection.close.assert_called_once_with()
def test_registered_synthesis_read_only_run_uses_signed_source_scope_without_receipt_or_write(
    monkeypatch,
):
    agent = _synthetic_synthesis_agent()
    connection, cursor = _source_connection()
    events = []
    agent.synthesize = lambda _connection, location_id=None: (
        events.append("synthesize")
        or {"location_id": location_id, "synthesis": "Read-only result"}
    )
    agent.collect_source_references = lambda *_args: events.append("references") or _empty_synthesis_references(agent)
    context_setter = MagicMock(
        side_effect=lambda *_args, **_kwargs: events.append("signed-context")
    )
    monkeypatch.setattr(worker_cli, "set_agent_summary_source_tenant_context", context_setter)
    credential_reader = MagicMock(return_value="s" * 40)
    monkeypatch.setattr(worker_cli, "get_worker_credential", credential_reader)
    action_policy = MagicMock()
    monkeypatch.setattr(
        "services.agents.safety.assert_agent_action_allowed", action_policy
    )
    receipt_reader = MagicMock(side_effect=AssertionError("read-only run has no receipt"))
    draft_writer = MagicMock(side_effect=AssertionError("read-only run cannot write"))

    result = worker_cli.run_worker_synthesis(
        agent,
        LOCATION_ID,
        None,
        persist_draft=False,
        connection_factory=lambda: connection,
        existing_reader=receipt_reader,
        draft_writer=draft_writer,
    )

    assert result == {"summary": {"location_id": LOCATION_ID, "synthesis": "Read-only result"}}
    credential_reader.assert_called_once_with("agent_bio_factory_source")
    context_setter.assert_called_once_with(
        connection,
        credential="s" * 40,
        location_id=LOCATION_ID,
    )
    receipt_reader.assert_not_called()
    draft_writer.assert_not_called()
    action_policy.assert_any_call("read", agent.read_collection, {"location_id": LOCATION_ID})
    assert all(call.args[0] != "create" for call in action_policy.call_args_list)
    assert events == ["signed-context", "synthesize", "references"]
    assert cursor.execute.call_args_list[0].args[0] == (
        "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"
    )
    assert connection.commit.call_count == 0
    connection.rollback.assert_not_called()
    connection.close.assert_called_once_with()


def test_synthesis_worker_requires_source_credential_before_opening_source_database(
    monkeypatch,
):
    agent = _synthetic_synthesis_agent()
    source_factory = MagicMock(side_effect=AssertionError("source DB must stay closed"))
    credential_reader = MagicMock(
        side_effect=WorkerDatabaseConfigurationError("source credential is required")
    )
    monkeypatch.setattr(worker_cli, "get_worker_credential", credential_reader)

    with pytest.raises(WorkerDatabaseConfigurationError, match="source credential is required"):
        worker_cli.run_worker_synthesis(
            agent,
            LOCATION_ID,
            REQUEST_ID,
            connection_factory=source_factory,
            existing_reader=lambda *_args: None,
        )

    credential_reader.assert_called_once_with("agent_bio_factory_source")
    source_factory.assert_not_called()


def test_deterministic_worker_defaults_to_its_own_source_login(monkeypatch):
    connection, _cursor = _source_connection()
    source_factory = MagicMock(return_value=connection)
    monkeypatch.setattr(worker_cli, "get_worker_db", source_factory)

    result = worker_cli.run_worker_summary(
        LOCATION_ID,
        "operations",
        REQUEST_ID,
        summary_builder=lambda *_args: _operations_summary(content="synthetic"),
        existing_reader=lambda *_args: None,
        draft_writer=lambda *_args: {"summary_id": "saved-id", "replayed": False},
    )

    source_factory.assert_called_once_with("agent_summary_deterministic_source")
    assert result["summary_id"] == "saved-id"


def test_deterministic_worker_rejects_output_for_another_location_before_draft_write():
    connection, _cursor = _source_connection()
    writer = MagicMock(side_effect=AssertionError("mismatched output must not be persisted"))
    summary_builder = MagicMock(
        return_value={
            "location_id": "00000000-0000-0000-0000-000000000999",
            "content": "Synthetic summary for a different location",
            "source_tables": ["harvest_event"],
        }
    )

    with pytest.raises(ValueError, match="output location does not match its signed scope"):
        worker_cli.run_worker_summary(
            LOCATION_ID,
            "operations",
            REQUEST_ID,
            connection_factory=lambda: connection,
            summary_builder=summary_builder,
            existing_reader=lambda *_args: None,
            draft_writer=writer,
        )

    summary_builder.assert_called_once()
    writer.assert_not_called()
    connection.rollback.assert_called_once_with()
    connection.close.assert_called_once_with()


def test_deterministic_worker_rejects_non_object_output_before_draft_write():
    connection, _cursor = _source_connection()
    writer = MagicMock(side_effect=AssertionError("invalid output must not be persisted"))

    with pytest.raises(ValueError, match="worker output must be an object"):
        worker_cli.run_worker_summary(
            LOCATION_ID,
            "operations",
            REQUEST_ID,
            connection_factory=lambda: connection,
            summary_builder=lambda *_args: None,
            existing_reader=lambda *_args: None,
            draft_writer=writer,
        )

    writer.assert_not_called()
    connection.rollback.assert_called_once_with()
    connection.close.assert_called_once_with()


@pytest.mark.parametrize("missing", ["source_table", "source_reference"])
def test_deterministic_worker_rejects_incomplete_source_coverage_before_draft_write(
    missing,
):
    connection, _cursor = _source_connection()
    writer = MagicMock(side_effect=AssertionError("incomplete provenance must not persist"))
    summary = _operations_summary()
    source = _OPERATIONS_SOURCES[0]
    if missing == "source_table":
        summary["source_tables"].remove(source)
    else:
        del summary["source_references"][source]

    with pytest.raises(ValueError, match="source tables|source references"):
        worker_cli.run_worker_summary(
            LOCATION_ID,
            "operations",
            REQUEST_ID,
            connection_factory=lambda: connection,
            summary_builder=lambda *_args: summary,
            existing_reader=lambda *_args: None,
            draft_writer=writer,
        )

    writer.assert_not_called()
    connection.rollback.assert_called_once_with()
    connection.close.assert_called_once_with()


def test_deterministic_read_only_run_uses_signed_source_scope_without_receipt_or_write(
    monkeypatch,
):
    connection, cursor = _source_connection()
    events = []
    context_setter = MagicMock(
        side_effect=lambda *_args, **_kwargs: events.append("signed-context")
    )
    monkeypatch.setattr(worker_cli, "set_agent_summary_source_tenant_context", context_setter)
    builder = MagicMock(
        side_effect=lambda *_args: events.append("summary")
        or _operations_summary(content="Synthetic read-only summary")
    )
    receipt_reader = MagicMock(side_effect=AssertionError("read-only run has no receipt"))
    draft_writer = MagicMock(side_effect=AssertionError("read-only run cannot write"))
    action_policy = MagicMock()
    monkeypatch.setattr(
        "services.agents.safety.assert_agent_action_allowed", action_policy
    )

    result = worker_cli.run_worker_summary(
        LOCATION_ID,
        "operations",
        None,
        persist_draft=False,
        connection_factory=lambda: connection,
        summary_builder=builder,
        existing_reader=receipt_reader,
        draft_writer=draft_writer,
    )

    assert result == {
        "summary": _operations_summary(content="Synthetic read-only summary")
    }
    context_setter.assert_called_once_with(
        connection,
        credential="s" * 40,
        location_id=LOCATION_ID,
    )
    receipt_reader.assert_not_called()
    draft_writer.assert_not_called()
    action_policy.assert_any_call("read", "ai_summary", {"location_id": LOCATION_ID})
    assert all(call.args[0] != "create" for call in action_policy.call_args_list)
    assert events == ["signed-context", "summary"]
    assert cursor.execute.call_args_list[:2][0].args[0] == (
        "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"
    )
    assert cursor.execute.call_args_list[2].args[0] == (
        "SET LOCAL search_path = kokonut_agent_source, pg_catalog"
    )
    connection.close.assert_called_once_with()
    connection.rollback.assert_not_called()


def test_deterministic_worker_requires_source_credential_before_opening_source_db(
    monkeypatch,
):
    connection_factory = MagicMock(side_effect=AssertionError("source DB must stay closed"))
    credential_reader = MagicMock(
        side_effect=WorkerDatabaseConfigurationError(
            "deterministic source credential is required"
        )
    )
    monkeypatch.setattr(worker_cli, "get_worker_credential", credential_reader)

    with pytest.raises(WorkerDatabaseConfigurationError, match="source credential is required"):
        worker_cli.run_worker_summary(
            LOCATION_ID,
            "operations",
            REQUEST_ID,
            connection_factory=connection_factory,
            existing_reader=lambda *_args: None,
        )

    credential_reader.assert_called_once_with("agent_summary_deterministic_source")
    connection_factory.assert_not_called()


def test_worker_summary_rejects_unregistered_type_before_request_lookup():
    existing_reader = MagicMock(side_effect=AssertionError("invalid type reached receipt lookup"))
    connection_factory = MagicMock(side_effect=AssertionError("invalid type opened source DB"))

    with pytest.raises(ValueError, match="registered deterministic worker summary"):
        worker_cli.run_worker_summary(
            LOCATION_ID,
            "unregistered_summary",
            REQUEST_ID,
            connection_factory=connection_factory,
            existing_reader=existing_reader,
        )

    existing_reader.assert_not_called()
    connection_factory.assert_not_called()


@pytest.mark.parametrize(
    ("location_id", "request_id"),
    [
        ("not-a-location", REQUEST_ID),
        (LOCATION_ID, "not-a-request"),
        (None, REQUEST_ID),
        (LOCATION_ID, None),
    ],
)
def test_worker_summary_rejects_invalid_identifiers_before_receipt_or_database(
    location_id, request_id
):
    existing_reader = MagicMock(side_effect=AssertionError("invalid IDs reached receipt lookup"))
    connection_factory = MagicMock(side_effect=AssertionError("invalid IDs opened source DB"))

    with pytest.raises(ValueError, match="location_id and request_id must be UUIDs"):
        worker_cli.run_worker_summary(
            location_id,
            "combined",
            request_id,
            connection_factory=connection_factory,
            existing_reader=existing_reader,
        )

    existing_reader.assert_not_called()
    connection_factory.assert_not_called()


def test_worker_summary_normalizes_ids_before_receipt_lookup():
    normalized_location = LOCATION_ID.upper()
    normalized_request = REQUEST_ID.upper()
    existing_reader = MagicMock(return_value={"summary_id": "saved-id", "replayed": True})

    result = worker_cli.run_worker_summary(
        normalized_location,
        "combined",
        normalized_request,
        existing_reader=existing_reader,
        connection_factory=MagicMock(side_effect=AssertionError("retry opened source DB")),
    )

    existing_reader.assert_called_once_with(LOCATION_ID, "combined", REQUEST_ID)
    assert result == {"summary_id": "saved-id", "replayed": True}


@pytest.mark.parametrize("denied_action", ["read", "create"])
def test_worker_summary_enforces_safety_before_receipt_lookup(
    monkeypatch, denied_action
):
    existing_reader = MagicMock(side_effect=AssertionError("denied action reached receipt lookup"))
    connection_factory = MagicMock(side_effect=AssertionError("denied action opened source DB"))

    def deny_selected_action(action, _collection, _payload):
        if action == denied_action:
            raise ValueError(f"{action} denied by test policy")

    monkeypatch.setattr(
        "services.agents.safety.assert_agent_action_allowed", deny_selected_action
    )

    with pytest.raises(ValueError, match=f"{denied_action} denied by test policy"):
        worker_cli.run_worker_summary(
            LOCATION_ID,
            "combined",
            REQUEST_ID,
            connection_factory=connection_factory,
            existing_reader=existing_reader,
        )

    existing_reader.assert_not_called()
    connection_factory.assert_not_called()


def test_worker_summary_rejects_unsafe_task_registry_before_receipt_lookup(monkeypatch):
    from services.agents.tasks import TASK_CATALOGUE

    writes = TASK_CATALOGUE["ai_summary_synthesis"]["writes"]
    monkeypatch.setitem(TASK_CATALOGUE["ai_summary_synthesis"], "writes", ["ai_summary:published"])
    existing_reader = MagicMock(side_effect=AssertionError("unsafe task reached receipt lookup"))
    connection_factory = MagicMock(side_effect=AssertionError("unsafe task opened source DB"))

    with pytest.raises(ValueError, match="unapproved write capability"):
        worker_cli.run_worker_summary(
            LOCATION_ID,
            "combined",
            REQUEST_ID,
            connection_factory=connection_factory,
            existing_reader=existing_reader,
        )

    existing_reader.assert_not_called()
    connection_factory.assert_not_called()
    assert writes == ["ai_summary:draft"]


def test_generic_synthesis_worker_attaches_collected_refs_from_read_snapshot():
    agent = _synthetic_synthesis_agent()
    references = _empty_synthesis_references(agent)
    references["bio_factory_batch"] = {
            "record_ids": ["e0000000-0000-4000-8000-000000000001"],
            "row_count": 1,
            "truncated": False,
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


def test_generic_synthesis_worker_rejects_missing_view_reference_before_draft_write():
    agent = _synthetic_synthesis_agent()
    agent.collect_source_references = MagicMock(return_value={})
    connection, _cursor = _source_connection()
    writer = MagicMock(side_effect=AssertionError("incomplete provenance must not persist"))
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(
            "services.agents.safety.assert_agent_action_allowed", lambda *_args: None
        )
        with pytest.raises(ValueError, match="cover every registered provenance view"):
            worker_cli.run_worker_synthesis(
                agent,
                LOCATION_ID,
                REQUEST_ID,
                connection_factory=lambda: connection,
                existing_reader=lambda *_args: None,
                draft_writer=writer,
            )

    writer.assert_not_called()
    connection.rollback.assert_called_once_with()
    connection.close.assert_called_once_with()


def test_generic_synthesis_worker_does_not_write_when_reference_collection_fails():
    agent = _synthetic_synthesis_agent()
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
    agent = _synthetic_synthesis_agent()
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
    agent = _synthetic_synthesis_agent()
    agent.source_tables = ["harvest_event", "harvest_event"]
    reader = MagicMock(side_effect=AssertionError("invalid metadata must fail first"))
    connection_factory = MagicMock(side_effect=AssertionError("DB must stay closed"))
    with pytest.raises(ValueError, match="metadata differs from its registered class"):
        worker_cli.run_worker_synthesis(
            agent,
            LOCATION_ID,
            REQUEST_ID,
            connection_factory=connection_factory,
            existing_reader=reader,
        )
    reader.assert_not_called()
    connection_factory.assert_not_called()


def test_synthesis_worker_rejects_catalogue_only_task_before_receipt_lookup():
    agent = _synthetic_synthesis_agent()
    agent.task_key = "ebf_scorecard_draft"
    reader = MagicMock(side_effect=AssertionError("unsupported task reached receipt lookup"))
    connection_factory = MagicMock(side_effect=AssertionError("unsupported task opened source DB"))

    with pytest.raises(ValueError, match="not a registered synthesis agent"):
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
    agent = _synthetic_synthesis_agent()
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
    agent = _synthetic_synthesis_agent()
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
        for task_key in worker_cli._SYNTHESIS_WORKERS
    }
    assert set(resolved) == set(worker_cli._SYNTHESIS_WORKERS)
    assert all(agent.task_key == task_key for task_key, agent in resolved.items())


def test_worker_cli_dispatches_registered_synthesis_task_without_content_output(
    monkeypatch, capsys
):
    agent = _synthetic_synthesis_agent()
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
            "--source-only",
            "--read-only",
        ],
    )
    monkeypatch.setattr(worker_cli, "resolve_synthesis_agent", lambda _task: agent)
    run = MagicMock(
        return_value={"summary": {"synthesis": "private generated content"}}
    )
    monkeypatch.setattr(worker_cli, "run_worker_synthesis", run)

    worker_cli.main()

    output = capsys.readouterr().out
    run.assert_called_once_with(agent, LOCATION_ID, None, persist_draft=False)
    assert json.loads(output) == {
        "task_key": agent.task_key,
        "summary_type": agent.summary_type,
        "resulting_status": "computed_not_persisted",
    }
    assert "private generated content" not in output


def test_worker_cli_redacts_execution_exception_details(monkeypatch, caplog, capsys):
    private_detail = "private source row and connection detail"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "worker_cli",
            "--location-id",
            LOCATION_ID,
            "--summary-type",
            "combined",
            "--persist-draft",
            "--request-id",
            REQUEST_ID,
        ],
    )
    monkeypatch.setattr(
        worker_cli,
        "run_worker_summary",
        MagicMock(side_effect=RuntimeError(private_detail)),
    )

    with pytest.raises(SystemExit) as error:
        worker_cli.main()

    captured = capsys.readouterr()
    assert error.value.code == 1
    assert "RuntimeError" in caplog.text
    assert private_detail not in caplog.text
    assert private_detail not in captured.out + captured.err
    assert "Traceback" not in captured.err


def test_source_only_cli_rejects_deterministic_summary_before_dispatch(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "worker_cli",
            "--location-id",
            LOCATION_ID,
            "--request-id",
            REQUEST_ID,
            "--source-only",
        ],
    )
    summary = MagicMock(side_effect=AssertionError("deterministic worker must not run"))
    monkeypatch.setattr(worker_cli, "run_worker_summary", summary)

    with pytest.raises(SystemExit) as error:
        worker_cli.main()

    assert error.value.code == 2
    summary.assert_not_called()


def test_cids_worker_uses_signed_source_reader_and_preserves_export_contract(monkeypatch):
    connection, cursor = _source_connection()
    events = []
    context_setter = MagicMock(
        side_effect=lambda *_args, **_kwargs: events.append("signed-context")
    )
    credential_reader = MagicMock(return_value="c" * 40)
    source_factory = MagicMock(return_value=connection)
    action_policy = MagicMock()
    document = {
        "@graph": [{"@type": "cids:Organization"}],
        "kokonut:alignmentTier": "essential",
        "kokonut:cidsVersion": "3.2.0",
    }
    exporter = MagicMock(side_effect=lambda *_args, **_kwargs: events.append("export") or document)
    monkeypatch.setattr(worker_cli, "get_worker_db", source_factory)
    monkeypatch.setattr(worker_cli, "get_worker_credential", credential_reader)
    monkeypatch.setattr(worker_cli, "set_agent_source_tenant_context", context_setter)
    monkeypatch.setattr(
        "services.agents.safety.assert_agent_action_allowed", action_policy
    )
    monkeypatch.setattr("services.registry.cids_export.export_location", exporter)

    result = worker_cli.run_worker_cids_export(LOCATION_ID)

    statements = [call.args[0].strip() for call in cursor.execute.call_args_list]
    assert statements == [
        "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY",
        "SET LOCAL ROLE kokonut_agent_cids_source_reader",
        "SET LOCAL search_path = kokonut_agent_source, pg_catalog",
        "SET LOCAL statement_timeout = '15s'",
        "SET LOCAL lock_timeout = '3s'",
    ]
    context_setter.assert_called_once_with(
        connection,
        credential="c" * 40,
        location_id=LOCATION_ID,
        resource="cids_export",
        action="read",
    )
    source_factory.assert_called_once_with("agent_cids_source")
    credential_reader.assert_called_once_with("agent_cids_source")
    exporter.assert_called_once_with(
        connection, LOCATION_ID, source_schema="kokonut_agent_source"
    )
    action_policy.assert_called_once_with(
        "read", "cids_export", {"location_id": LOCATION_ID}
    )
    assert events == ["signed-context", "export"]
    assert result == {
        "document": document,
        "graph_count": 1,
        "alignment_tier": "essential",
        "cids_version": "3.2.0",
    }
    connection.rollback.assert_not_called()
    connection.close.assert_called_once_with()


def test_ebf_worker_uses_its_task_specific_source_identity(monkeypatch):
    connection, cursor = _source_connection()
    scorecard_id = "00000000-0000-0000-0000-000000000abc"
    context_setter = MagicMock()
    credential_reader = MagicMock(return_value="e" * 40)
    source_factory = MagicMock(return_value=connection)
    result = {"evidence_gaps": [], "recommendations": []}
    analyzer = MagicMock(return_value=result)
    monkeypatch.setattr(worker_cli, "get_worker_db", source_factory)
    monkeypatch.setattr(worker_cli, "get_worker_credential", credential_reader)
    monkeypatch.setattr(worker_cli, "set_agent_source_tenant_context", context_setter)
    monkeypatch.setattr(
        "services.agents.safety.assert_agent_action_allowed", lambda *_args: None
    )
    monkeypatch.setattr(
        "services.agents.ebf_evidence_gap_agent.analyze_evidence_gaps", analyzer
    )

    output = worker_cli.run_worker_ebf_evidence_gap(scorecard_id, LOCATION_ID)

    statements = [call.args[0].strip() for call in cursor.execute.call_args_list]
    assert statements == [
        "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY",
        "SET LOCAL ROLE kokonut_agent_ebf_source_reader",
        "SET LOCAL search_path = kokonut_agent_source, pg_catalog",
        "SET LOCAL statement_timeout = '15s'",
        "SET LOCAL lock_timeout = '3s'",
    ]
    credential_reader.assert_called_once_with("agent_ebf_source")
    source_factory.assert_called_once_with("agent_ebf_source")
    context_setter.assert_called_once_with(
        connection,
        credential="e" * 40,
        location_id=LOCATION_ID,
        resource="ebf_scorecard",
        action="read",
    )
    analyzer.assert_called_once_with(connection, scorecard_id, LOCATION_ID)
    assert output == result
    connection.close.assert_called_once_with()


def test_cids_worker_rolls_back_and_closes_when_projection_fails(monkeypatch):
    connection, _cursor = _source_connection()
    monkeypatch.setattr(worker_cli, "get_worker_db", lambda _key: connection)
    monkeypatch.setattr(
        worker_cli,
        "set_agent_source_tenant_context",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        "services.agents.safety.assert_agent_action_allowed", lambda *_args: None
    )
    monkeypatch.setattr(
        "services.registry.cids_export.export_location",
        MagicMock(side_effect=RuntimeError("synthetic source failure")),
    )

    with pytest.raises(RuntimeError, match="synthetic source failure"):
        worker_cli.run_worker_cids_export(LOCATION_ID)

    connection.rollback.assert_called_once_with()
    connection.close.assert_called_once_with()


def test_summary_inspection_list_uses_signed_exact_location_source_reader(monkeypatch):
    connection, cursor = _source_connection()
    cursor.fetchall.return_value = [
        {
            "id": "c0000000-0000-4000-8000-000000000101",
            "summary_type": "operations",
            "status": "draft",
            "created_at": "2026-10-22",
            "preview": "Synthetic location preview",
        }
    ]
    context_setter = MagicMock()
    credential = "i" * 40
    source_factory = MagicMock(return_value=connection)
    monkeypatch.setattr(worker_cli, "get_worker_db", source_factory)
    monkeypatch.setattr(worker_cli, "get_worker_credential", lambda _key: credential)
    monkeypatch.setattr(worker_cli, "set_agent_summary_source_tenant_context", context_setter)
    monkeypatch.setattr(
        "services.agents.safety.assert_agent_action_allowed", lambda *_args: None
    )

    rows = worker_cli.run_worker_summary_list(LOCATION_ID)

    statements = [call.args[0].strip() for call in cursor.execute.call_args_list]
    assert statements[:4] == [
        "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY",
        "SET LOCAL ROLE kokonut_agent_summary_inspection_reader",
        "SET LOCAL search_path = kokonut_agent_source, pg_catalog",
        "SET LOCAL statement_timeout = '15s'",
    ]
    assert "FROM kokonut_agent_source.ai_summary_list" in statements[-1]
    assert "WHERE location_id = %s" in statements[-1]
    assert "LIMIT 20" in statements[-1]
    assert cursor.execute.call_args_list[-1].args[1] == (LOCATION_ID,)
    source_factory.assert_called_once_with("agent_summary_inspection_source")
    context_setter.assert_called_once_with(
        connection, credential=credential, location_id=LOCATION_ID
    )
    assert rows[0]["preview"] == "Synthetic location preview"
    connection.rollback.assert_not_called()
    connection.close.assert_called_once_with()


def test_summary_digest_returns_metadata_only_for_exact_location(monkeypatch):
    connection, cursor = _source_connection()
    raw_content = "Sensitive synthetic summary"
    cursor.fetchone.return_value = {
        "id": SUMMARY_ID,
        "summary_type": "operations",
        "status": "draft",
        "model_version": "synthetic-v1",
        "content_sha256": hashlib.sha256(raw_content.encode()).hexdigest(),
        "content_length": len(raw_content),
    }
    monkeypatch.setattr(worker_cli, "get_worker_db", lambda _key: connection)
    monkeypatch.setattr(worker_cli, "get_worker_credential", lambda _key: "i" * 40)
    monkeypatch.setattr(
        worker_cli, "set_agent_summary_source_tenant_context", lambda *_a, **_k: None
    )
    monkeypatch.setattr(
        "services.agents.safety.assert_agent_action_allowed", lambda *_args: None
    )

    result = worker_cli.run_worker_summary_digest(LOCATION_ID, SUMMARY_ID)

    query_call = cursor.execute.call_args_list[-1]
    assert "FROM kokonut_agent_source.ai_summary_digest" in query_call.args[0]
    assert "content_sha256" in query_call.args[0]
    assert "content_length" in query_call.args[0]
    assert "summary.content" not in query_call.args[0]
    assert "WHERE id = %s AND location_id = %s" in query_call.args[0]
    assert query_call.args[1] == (SUMMARY_ID, LOCATION_ID)
    assert result == {
        "id": SUMMARY_ID,
        "summary_type": "operations",
        "status": "draft",
        "model_version": "synthetic-v1",
        "content_sha256": hashlib.sha256(raw_content.encode()).hexdigest(),
        "content_length": len(raw_content),
    }
    assert raw_content not in str(result)
    connection.rollback.assert_not_called()
    connection.close.assert_called_once_with()


def test_summary_inspection_rejects_malformed_scope_before_worker_credentials(monkeypatch):
    credential = MagicMock(side_effect=AssertionError("credential read before validation"))
    connection = MagicMock(side_effect=AssertionError("DB opened before validation"))
    monkeypatch.setattr(worker_cli, "get_worker_credential", credential)
    monkeypatch.setattr(worker_cli, "get_worker_db", connection)

    with pytest.raises(ValueError, match="location_id and summary_id must be UUIDs"):
        worker_cli.run_worker_summary_digest("bad-location", "bad-summary")

    credential.assert_not_called()
    connection.assert_not_called()


def test_summary_inspection_rolls_back_and_closes_after_query_failure(monkeypatch):
    connection, cursor = _source_connection()
    cursor.execute.side_effect = [None, None, None, None, RuntimeError("summary read failed")]
    monkeypatch.setattr(worker_cli, "get_worker_db", lambda _key: connection)
    monkeypatch.setattr(worker_cli, "get_worker_credential", lambda _key: "i" * 40)
    monkeypatch.setattr(
        worker_cli, "set_agent_summary_source_tenant_context", lambda *_a, **_k: None
    )
    monkeypatch.setattr(
        "services.agents.safety.assert_agent_action_allowed", lambda *_args: None
    )

    with pytest.raises(RuntimeError, match="summary read failed"):
        worker_cli.run_worker_summary_list(LOCATION_ID)

    connection.rollback.assert_called_once_with()
    connection.close.assert_called_once_with()


@pytest.mark.parametrize(
    ("extra_args", "message"),
    [
        (["--deterministic-only"], "requires --summary-type"),
        (
            ["--deterministic-only", "--summary-type", "operations", "--task-key", "feedback_synthesis", "--source-only"],
            "cannot be combined with --task-key",
        ),
    ],
)
def test_deterministic_only_cli_rejects_other_worker_modes_before_dispatch(
    monkeypatch, extra_args, message
):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "worker_cli",
            "--location-id",
            LOCATION_ID,
            "--request-id",
            REQUEST_ID,
            *extra_args,
        ],
    )
    summary = MagicMock(side_effect=AssertionError("invalid mode must not dispatch"))
    synthesis = MagicMock(side_effect=AssertionError("invalid mode must not dispatch"))
    monkeypatch.setattr(worker_cli, "run_worker_summary", summary)
    monkeypatch.setattr(worker_cli, "run_worker_synthesis", synthesis)

    with pytest.raises(SystemExit) as error:
        worker_cli.main()

    assert error.value.code == 2
    summary.assert_not_called()
    synthesis.assert_not_called()


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
            "--read-only",
        ],
    )
    run = MagicMock(
        return_value={
            "summary": {
                "content": "private farm summary",
                "source_references": {"harvest_event": {"record_ids": [LOCATION_ID]}},
            }
        }
    )
    monkeypatch.setattr(worker_cli, "run_worker_summary", run)

    worker_cli.main()

    output = capsys.readouterr().out
    run.assert_called_once_with(
        LOCATION_ID, "operations", None, persist_draft=False
    )
    assert json.loads(output) == {
        "task_key": "ai_summary_synthesis",
        "summary_type": "operations",
        "resulting_status": "computed_not_persisted",
    }
    assert "private farm summary" not in output
    assert LOCATION_ID not in output


def test_worker_cli_persists_only_with_the_exact_gateway_request(monkeypatch, capsys):
    agent = MagicMock(task_key="feedback_synthesis", summary_type="stakeholder_feedback")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "worker_cli",
            "--location-id",
            LOCATION_ID,
            "--task-key",
            "feedback_synthesis",
            "--persist-draft",
            "--request-id",
            REQUEST_ID.upper(),
        ],
    )
    monkeypatch.setattr(worker_cli, "resolve_synthesis_agent", lambda _task: agent)
    run = MagicMock(
        return_value={
            "summary": {"synthesis": "private farm summary"},
            "ai_summary_id": SUMMARY_ID,
            "request_id": REQUEST_ID,
            "replayed": False,
        }
    )
    monkeypatch.setattr(worker_cli, "run_worker_synthesis", run)

    worker_cli.main()

    run.assert_called_once_with(
        agent, LOCATION_ID, REQUEST_ID, persist_draft=True
    )
    output = capsys.readouterr().out
    assert json.loads(output) == {
        "task_key": "feedback_synthesis",
        "summary_type": "stakeholder_feedback",
        "resulting_status": "draft",
        "request_id": REQUEST_ID,
    }
    assert "private farm summary" not in output
    assert LOCATION_ID not in output


def test_worker_cli_persist_mode_rejects_invalid_request_before_task_resolution(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "worker_cli",
            "--location-id",
            LOCATION_ID,
            "--task-key",
            "feedback_synthesis",
            "--persist-draft",
            "--request-id",
            "not-a-uuid",
        ],
    )
    resolver = MagicMock(side_effect=AssertionError("task must not resolve"))
    monkeypatch.setattr(worker_cli, "resolve_synthesis_agent", resolver)

    with pytest.raises(SystemExit) as error:
        worker_cli.main()

    assert error.value.code == 2
    resolver.assert_not_called()


def test_worker_cli_rejects_draft_persistence_before_task_resolution(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        ["worker_cli", "--location-id", LOCATION_ID, "--task-key", "feedback_synthesis"],
    )
    resolver = MagicMock(side_effect=AssertionError("task must not resolve"))
    runner = MagicMock(side_effect=AssertionError("worker must not run"))
    monkeypatch.setattr(worker_cli, "resolve_synthesis_agent", resolver)
    monkeypatch.setattr(worker_cli, "run_worker_synthesis", runner)

    with pytest.raises(SystemExit) as error:
        worker_cli.main()

    assert error.value.code == 2
    resolver.assert_not_called()
    runner.assert_not_called()


def test_worker_cli_read_only_rejects_request_id_before_task_resolution(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "worker_cli",
            "--location-id",
            LOCATION_ID,
            "--task-key",
            "feedback_synthesis",
            "--read-only",
            "--request-id",
            REQUEST_ID,
        ],
    )
    resolver = MagicMock(side_effect=AssertionError("task must not resolve"))
    monkeypatch.setattr(worker_cli, "resolve_synthesis_agent", resolver)

    with pytest.raises(SystemExit) as error:
        worker_cli.main()

    assert error.value.code == 2
    resolver.assert_not_called()
