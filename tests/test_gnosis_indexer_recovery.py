"""Mocked checkpoint and failure-boundary checks for the Gnosis indexer."""

from __future__ import annotations

import pytest

from services.ingestion import gnosis_indexer
from services.ingestion.clickhouse_outbox import OutboxEnqueueError


class _Cursor:
    def __init__(self, row):
        self.row = row
        self.statements = []

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def execute(self, statement, params=None):
        self.statements.append((statement, params))

    def fetchone(self):
        return self.row


class _Connection:
    def __init__(self, last_synced):
        self.cursor_instance = _Cursor((last_synced,) if last_synced is not None else None)
        self.commits = 0
        self.rollbacks = 0
        self.closed = False

    def cursor(self):
        return self.cursor_instance

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed = True


class _Eth:
    block_number = 20

    def __init__(self, failures=None):
        self.failures = failures or {}
        self.calls = []

    def get_logs(self, query):
        self.calls.append(query)
        failure = self.failures.get(query["fromBlock"])
        if failure:
            raise failure
        return []


class _Web3:
    def __init__(self, eth):
        self.eth = eth


def _run_with(monkeypatch, connection, web3, status_calls, batches):
    monkeypatch.setattr(gnosis_indexer, "get_db", lambda: connection)
    monkeypatch.setattr(gnosis_indexer, "get_web3", lambda: web3)
    monkeypatch.setattr(gnosis_indexer, "get_moloch_contract", lambda _w3: object())
    monkeypatch.setattr(gnosis_indexer, "get_treasury_contract", lambda _w3: object())
    monkeypatch.setattr(gnosis_indexer, "batch_ranges", lambda *_args, **_kwargs: batches)
    monkeypatch.setattr(
        gnosis_indexer,
        "update_indexer_status",
        lambda *args, **kwargs: status_calls.append((args, kwargs)),
    )


def test_gnosis_commits_each_range_with_its_checkpoint_in_same_connection(monkeypatch):
    connection = _Connection(last_synced=9)
    web3 = _Web3(_Eth())
    status_calls = []
    _run_with(monkeypatch, connection, web3, status_calls, [(10, 15), (16, 20)])

    gnosis_indexer.run()

    assert [call["fromBlock"] for call in web3.eth.calls] == [10, 16]
    assert connection.commits == 3
    assert connection.rollbacks == 0
    assert connection.closed
    assert [call[0][2] for call in status_calls] == [15, 20, 20]
    assert [call[0][3] for call in status_calls] == ["syncing", "syncing", "healthy"]
    assert all(call[1]["db"] is connection for call in status_calls)


def test_gnosis_failed_range_rolls_back_and_preserves_last_checkpoint(monkeypatch):
    connection = _Connection(last_synced=9)
    web3 = _Web3(_Eth({16: OSError("provider failed")}))
    status_calls = []
    _run_with(monkeypatch, connection, web3, status_calls, [(10, 15), (16, 20)])

    with pytest.raises(RuntimeError, match="Gnosis block range 16-20 failed"):
        gnosis_indexer.run()

    assert len(web3.eth.calls) == 2
    assert connection.commits == 2  # First range and the durable error status.
    assert connection.rollbacks == 1
    assert connection.closed
    assert [call[0][2] for call in status_calls] == [15, 15]
    assert [call[0][3] for call in status_calls] == ["syncing", "error"]
    assert "provider failed" in status_calls[-1][0][4]
    assert all(call[1]["db"] is connection for call in status_calls)


def test_gnosis_outbox_failure_propagates_without_advancing_failed_range(monkeypatch):
    connection = _Connection(last_synced=9)
    failure = OutboxEnqueueError("outbox unavailable")
    web3 = _Web3(_Eth({10: failure}))
    status_calls = []
    _run_with(monkeypatch, connection, web3, status_calls, [(10, 15)])

    with pytest.raises(OutboxEnqueueError, match="outbox unavailable"):
        gnosis_indexer.run()

    assert connection.commits == 1  # Error status only; failed range stays rolled back.
    assert connection.rollbacks == 1
    assert connection.closed
    assert [call[0][2] for call in status_calls] == [9]
    assert [call[0][3] for call in status_calls] == ["error"]

