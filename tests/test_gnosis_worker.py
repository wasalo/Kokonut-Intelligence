"""Focused contracts for the isolated Gnosis Moloch worker adapter."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from services.common.worker_environment import (
    ISOLATED_WORKER_KEY_ENV,
    scheduled_module_worker_key,
    worker_subprocess_environment,
)
from services.ingestion import gnosis_worker


def test_endpoint_requires_exact_https_gnosis_secret():
    endpoint = "https://rpc.example.invalid/v1/synthetic-token"
    assert gnosis_worker._rpc_endpoint(
        {gnosis_worker.RPC_ENV: json.dumps({"gnosis": endpoint})}
    ) == endpoint

    for invalid in (
        "",
        json.dumps({"gnosis": "http://rpc.example.invalid"}),
        json.dumps({"gnosis": "https://user:password@rpc.example.invalid"}),
        json.dumps({"gnosis": "https://rpc.example.invalid", "celo": "https://other.invalid"}),
        "not-json",
    ):
        with pytest.raises(ValueError):
            gnosis_worker._rpc_endpoint({gnosis_worker.RPC_ENV: invalid})


def test_worker_routes_only_its_database_identity_and_provider_endpoint(monkeypatch):
    monkeypatch.setattr(gnosis_worker, "is_enabled", lambda _name: True)
    endpoint = "https://rpc.example.invalid/v1/synthetic-token"
    monkeypatch.setenv(gnosis_worker.RPC_ENV, json.dumps({"gnosis": endpoint}))
    calls = []
    monkeypatch.setattr(gnosis_worker, "get_worker_db", lambda key: calls.append(("db", key)))
    monkeypatch.setattr(
        gnosis_worker.gnosis_indexer,
        "run",
        lambda **kwargs: calls.append(("run", kwargs)),
    )

    gnosis_worker.execute(from_block=12, to_block=15)

    assert calls[0][0] == "run"
    kwargs = calls[0][1]
    assert kwargs["from_block"] == 12
    assert kwargs["to_block"] == 15
    assert kwargs["rpc_url"] == endpoint
    connection = kwargs["database_factory"]()
    assert calls[1] == ("db", "gnosis_indexer")
    assert isinstance(kwargs["persistence"], gnosis_worker.GnosisWorkerPersistence)
    assert connection is None


def test_worker_child_receives_only_gnosis_secrets_and_no_shared_or_global_rpc():
    source = {
        "KOKONUT_GNOSIS_INDEXER_DATABASE_URL": "postgresql://isolated",
        gnosis_worker.RPC_ENV: '{"gnosis":"https://rpc.invalid"}',
        "KOKONUT_RPC_INDEXER_DATABASE_URL": "postgresql://other-worker",
        "GNOSIS_RPC_URL": "https://shared-provider.invalid",
        "PG_PASSWORD": "shared-password",
    }
    module = "services.ingestion.gnosis_worker"
    worker_key = scheduled_module_worker_key(module)

    assert worker_key == "gnosis_indexer"
    assert worker_subprocess_environment(
        allowed_worker_keys=(worker_key,),
        isolated_database_credentials=True,
        environ=source,
    ) == {
        "KOKONUT_GNOSIS_INDEXER_DATABASE_URL": "postgresql://isolated",
        gnosis_worker.RPC_ENV: '{"gnosis":"https://rpc.invalid"}',
        ISOLATED_WORKER_KEY_ENV: "gnosis_indexer",
    }


def test_disabled_isolated_worker_fails_before_opening_database(monkeypatch):
    monkeypatch.setattr(gnosis_worker, "is_enabled", lambda _name: False)
    monkeypatch.setattr(
        gnosis_worker, "get_worker_db", lambda *_args: pytest.fail("database opened")
    )
    with pytest.raises(RuntimeError, match="disabled"):
        gnosis_worker.execute()


def test_persistence_uses_fixed_migration_function_queries():
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = ("synthetic-receipt",)
    persistence = gnosis_worker.GnosisWorkerPersistence()
    record = {"event_type": "vote_cast", "metadata": {"source": "synthetic"}}

    assert persistence.store_governance_event(connection, record) == "synthetic-receipt"
    assert persistence.store_treasury_event(connection, record) == "synthetic-receipt"
    assert persistence.store_digital_lego_usage(connection, record) == "synthetic-receipt"

    calls = cursor.execute.call_args_list
    assert [call.args[0] for call in calls] == [
        "SELECT kokonut_security.store_gnosis_governance_event(%s::jsonb)",
        "SELECT kokonut_security.store_gnosis_treasury_event(%s::jsonb)",
        "SELECT kokonut_security.store_gnosis_digital_lego_usage(%s::jsonb)",
    ]
    assert json.loads(calls[0].args[1][0]) == record
    assert json.loads(calls[1].args[1][0]) == {
        **record,
        "source": "moloch_dao",
        "notes": json.dumps(record["metadata"]),
    }
    assert json.loads(calls[2].args[1][0]) == record
