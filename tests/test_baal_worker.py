"""Focused contracts for the isolated Baal governance worker."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from services.common.worker_environment import (
    ISOLATED_WORKER_KEY_ENV,
    scheduled_module_worker_key,
    worker_subprocess_environment,
)
from services.ingestion import baal_worker


def test_endpoint_requires_https_without_embedded_credentials():
    endpoint = "https://rpc.example.invalid/v1/synthetic-token"
    assert baal_worker._rpc_endpoint({baal_worker.RPC_ENV: endpoint}) == endpoint

    for invalid in (
        "",
        "http://rpc.example.invalid",
        "https://user:password@rpc.example.invalid",
        "https:///missing-host",
    ):
        with pytest.raises(ValueError, match="HTTPS endpoint"):
            baal_worker._rpc_endpoint({baal_worker.RPC_ENV: invalid})


def test_scheduled_child_receives_only_baal_worker_inputs():
    endpoint = "https://rpc.example.invalid/v1/synthetic-token"
    source = {
        "KOKONUT_BAAL_INDEXER_DATABASE_URL": "postgresql://isolated",
        baal_worker.RPC_ENV: endpoint,
        "KOKONUT_GNOSIS_INDEXER_DATABASE_URL": "postgresql://other-worker",
        "GNOSIS_RPC_URL": "https://shared-provider.invalid",
        "PG_PASSWORD": "shared-password",
    }
    module = "services.ingestion.baal_worker"
    worker_key = scheduled_module_worker_key(module)

    assert worker_key == "baal_indexer"
    assert worker_subprocess_environment(
        allowed_worker_keys=(worker_key,),
        isolated_database_credentials=True,
        environ=source,
    ) == {
        "KOKONUT_BAAL_INDEXER_DATABASE_URL": "postgresql://isolated",
        baal_worker.RPC_ENV: endpoint,
        ISOLATED_WORKER_KEY_ENV: "baal_indexer",
    }


def test_worker_routes_dedicated_database_endpoint_and_persistence(monkeypatch):
    endpoint = "https://rpc.example.invalid/v1/synthetic-token"
    monkeypatch.setattr(baal_worker, "is_enabled", lambda _name: True)
    monkeypatch.setenv(baal_worker.RPC_ENV, endpoint)
    calls = []
    monkeypatch.setattr(
        baal_worker,
        "get_worker_db",
        lambda key: calls.append(("db", key)) or "dedicated-connection",
    )
    monkeypatch.setattr(
        baal_worker.baal_indexer,
        "run",
        lambda **kwargs: calls.append(("run", kwargs)),
    )

    baal_worker.execute(from_block=12, to_block=15)

    assert calls[0][0] == "run"
    kwargs = calls[0][1]
    assert kwargs["from_block"] == 12
    assert kwargs["to_block"] == 15
    assert kwargs["rpc_url"] == endpoint
    assert kwargs["database_factory"]() == "dedicated-connection"
    assert calls[1] == ("db", "baal_indexer")
    assert isinstance(kwargs["persistence"], baal_worker.BaalWorkerPersistence)


def test_disabled_worker_fails_before_database_open(monkeypatch):
    monkeypatch.setattr(baal_worker, "is_enabled", lambda _name: False)
    monkeypatch.setattr(
        baal_worker,
        "get_worker_db",
        lambda *_args: pytest.fail("database opened while worker is disabled"),
    )
    with pytest.raises(RuntimeError, match="disabled"):
        baal_worker.execute()


def test_persistence_adapter_calls_only_migration_644_functions():
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = ("synthetic-id",)
    persistence = baal_worker.BaalWorkerPersistence()
    record = {
        "chain": "gnosis",
        "event_type": "vote_cast",
        "tx_hash": "0x" + "a" * 64,
    }

    persistence.acquire_lock(connection)
    persistence.release_lock(connection)
    persistence.read_cursor(connection)
    assert persistence.resolve_protocol(connection) == "synthetic-id"
    assert persistence.resolve_wallet(connection, "0x" + "b" * 40) == "synthetic-id"
    persistence.store_governance_event(connection, record)
    persistence.update_status(connection, 12, "healthy")

    statements = [call.args[0] for call in cursor.execute.call_args_list]
    assert statements == [
        "SELECT kokonut_security.acquire_baal_indexer_lock()",
        "SELECT kokonut_security.release_baal_indexer_lock()",
        "SELECT * FROM kokonut_security.read_baal_indexer_cursor()",
        "SELECT kokonut_security.resolve_baal_protocol()",
        "SELECT kokonut_security.resolve_baal_wallet(%s)",
        "SELECT kokonut_security.store_baal_governance_event(%s::jsonb)",
        "SELECT kokonut_security.update_baal_indexer_status(%s,%s,%s)",
    ]
    event_payload = json.loads(cursor.execute.call_args_list[5].args[1][0])
    assert event_payload == record
    assert cursor.execute.call_args_list[6].args[1] == (12, "healthy", None)


def test_indexer_keeps_each_event_batch_and_cursor_in_one_transaction(monkeypatch):
    events = []

    class Connection:
        def commit(self):
            events.append(("commit",))

        def rollback(self):
            events.append(("rollback",))

        def close(self):
            events.append(("close",))

    class Persistence:
        def acquire_lock(self, _connection):
            events.append(("lock",))

        def release_lock(self, _connection):
            events.append(("unlock",))

        def read_cursor(self, _connection):
            events.append(("cursor",))
            return (0, {})

        def resolve_protocol(self, _connection):
            return "protocol-id"

        def resolve_wallet(self, _connection, _address):
            return None

        def store_governance_event(self, _connection, record):
            events.append(("store", record["event_type"]))

        def update_status(self, _connection, block, status, _error=None):
            events.append(("status", block, status))

    web3 = SimpleNamespace(eth=SimpleNamespace(block_number=2))

    class FakeWeb3:
        HTTPProvider = staticmethod(lambda _url: object())

        def __new__(cls, _provider):
            return web3

    monkeypatch.setattr("services.ingestion.baal_indexer.Web3", FakeWeb3)
    monkeypatch.setattr(
        "services.ingestion.baal_indexer.BaalReadClient",
        lambda **_kwargs: SimpleNamespace(
            _baal=SimpleNamespace(
                events={
                    name: (lambda name=name: SimpleNamespace(
                        get_logs=lambda **_params: [object()] if name == "SubmitProposal" else []
                    ))
                    for name in baal_worker.baal_indexer.EVENT_DECODERS
                }
            )
        ),
    )
    monkeypatch.setattr(
        "services.ingestion.baal_indexer._decode_event",
        lambda *_args: {
            "chain": "gnosis",
            "event_type": "proposal_created",
            "tx_hash": "0x" + "a" * 64,
            "block_number": 1,
            "block_timestamp": datetime(2026, 10, 25, tzinfo=timezone.utc),
            "protocol_id": "protocol-id",
        },
    )
    monkeypatch.setattr("services.ingestion.baal_indexer.batch_ranges", lambda *_args: [(1, 2)])
    connection = Connection()

    result = baal_worker.baal_indexer.run(
        from_block=1,
        to_block=2,
        database_factory=lambda: connection,
        rpc_url="https://rpc.example.invalid",
        persistence=Persistence(),
    )

    assert result == 1
    store_position = events.index(("store", "proposal_created"))
    syncing_position = events.index(("status", 2, "syncing"))
    batch_commit_position = events.index(("commit",), syncing_position)
    assert store_position < syncing_position < batch_commit_position
    assert events[batch_commit_position - 1] == ("status", 2, "syncing")
    assert events[-3:] == [("unlock",), ("commit",), ("close",)]
