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
    def __init__(self, last_synced, metadata=None):
        row = (
            (last_synced, metadata or {})
            if last_synced is not None
            else None
        )
        self.cursor_instance = _Cursor(row)
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


class _ReceiptCursor(_Cursor):
    def __init__(self, inserted_row=None, existing_row=None):
        super().__init__(None)
        self.inserted_row = inserted_row
        self.existing_row = existing_row
        self._insert_statement = False

    def execute(self, statement, params=None):
        super().execute(statement, params)
        self._insert_statement = statement.lstrip().startswith(
            "INSERT INTO public.gnosis_event_log_receipt"
        )

    def fetchone(self):
        return self.inserted_row if self._insert_statement else self.existing_row


class _ReceiptConnection:
    def __init__(self, inserted_row=None, existing_row=None):
        self.cursor_instance = _ReceiptCursor(inserted_row, existing_row)

    def cursor(self):
        return self.cursor_instance


class _Eth:
    def __init__(self, failures=None, logs=None, block_number_error=None, block_number=20):
        self.failures = failures or {}
        self.logs = logs or []
        self.block_number_error = block_number_error
        self._block_number = block_number
        self.calls = []
        self.block_number_reads = 0

    @property
    def block_number(self):
        self.block_number_reads += 1
        if self.block_number_error:
            raise self.block_number_error
        return self._block_number

    def get_logs(self, query):
        self.calls.append(query)
        failure = self.failures.get(query["fromBlock"])
        if failure:
            raise failure
        return self.logs


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


def _event_log(topic):
    return {
        "topics": [type("Topic", (), {"hex": lambda self: topic})()],
        "transactionHash": bytes.fromhex("11" * 32),
        "logIndex": 3,
        "blockNumber": 12,
        "blockHash": bytes.fromhex("22" * 32),
    }


def test_gnosis_receipt_claim_is_idempotent_for_same_canonical_log():
    log = _event_log("unused")
    block_hash = "0x" + "22" * 32
    connection = _ReceiptConnection(
        inserted_row=(block_hash, 12, "VoteProposal")
    )

    assert gnosis_indexer.claim_gnosis_event_log(
        connection, "gnosis", log, "VoteProposal"
    )
    insert_params = connection.cursor_instance.statements[0][1]
    assert insert_params == (
        "gnosis",
        "0x" + "11" * 32,
        3,
        12,
        block_hash,
        "VoteProposal",
    )

    duplicate = _ReceiptConnection(
        inserted_row=None,
        existing_row=(block_hash, 12, "VoteProposal"),
    )
    assert not gnosis_indexer.claim_gnosis_event_log(
        duplicate, "gnosis", log, "VoteProposal"
    )
    assert len(duplicate.cursor_instance.statements) == 2


def test_gnosis_receipt_claim_rejects_changed_canonical_block_hash():
    log = _event_log("unused")
    connection = _ReceiptConnection(
        inserted_row=None,
        existing_row=("0x" + "33" * 32, 12, "VoteProposal"),
    )

    with pytest.raises(gnosis_indexer.GnosisEventReorgError, match="canonical block data"):
        gnosis_indexer.claim_gnosis_event_log(
            connection, "gnosis", log, "VoteProposal"
        )


def test_gnosis_receipt_claim_requires_identity_before_database_access():
    connection = _ReceiptConnection()
    log = _event_log("unused")
    del log["blockHash"]

    with pytest.raises(ValueError, match="block hash"):
        gnosis_indexer.claim_gnosis_event_log(
            connection, "gnosis", log, "VoteProposal"
        )

    assert connection.cursor_instance.statements == []


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
    assert all(call[0][1] == gnosis_indexer.INDEXER_TYPE for call in status_calls)
    assert connection.cursor_instance.statements[0][1] == (
        gnosis_indexer.KOKONUT_DAO_CHAIN,
        gnosis_indexer.INDEXER_TYPE,
    )
    assert all(call[1]["db"] is connection for call in status_calls)


def test_gnosis_caps_backlog_per_run_without_skipping_uncommitted_blocks(monkeypatch):
    connection = _Connection(last_synced=9)
    web3 = _Web3(_Eth(block_number=50_000))
    status_calls = []
    requested_ranges = []

    def capture_range(start, end, _batch_size):
        requested_ranges.append((start, end))
        return [(start, end)]

    _run_with(monkeypatch, connection, web3, status_calls, [])
    monkeypatch.setattr(gnosis_indexer, "batch_ranges", capture_range)

    gnosis_indexer.run()

    assert requested_ranges == [(10, 10 + gnosis_indexer.MAX_BLOCKS_PER_RUN - 1)]
    assert web3.eth.calls == [{
        "fromBlock": 10,
        "toBlock": 10 + gnosis_indexer.MAX_BLOCKS_PER_RUN - 1,
        "address": gnosis_indexer.Web3.to_checksum_address(
            gnosis_indexer.KOKONUT_MOLOCH_ADDRESSES["token_manager"]
        ),
        "topics": [list(gnosis_indexer.EVENT_TOPICS.keys())],
    }]
    assert [call[0][2] for call in status_calls] == [
        10 + gnosis_indexer.MAX_BLOCKS_PER_RUN - 1,
        10 + gnosis_indexer.MAX_BLOCKS_PER_RUN - 1,
    ]
    assert connection.closed


def test_gnosis_requires_explicit_checkpoint_for_inherited_shared_cursor(monkeypatch):
    connection = _Connection(
        last_synced=9,
        metadata={"cursor_origin": "legacy_shared_rpc"},
    )
    web3 = _Web3(_Eth())
    status_calls = []
    _run_with(monkeypatch, connection, web3, status_calls, [(10, 20)])

    with pytest.raises(RuntimeError, match="pass --from-block explicitly"):
        gnosis_indexer.run()

    assert web3.eth.calls == []
    assert web3.eth.block_number_reads == 0
    assert status_calls == []
    assert connection.closed


def test_gnosis_explicit_checkpoint_reviews_inherited_cursor_after_success(monkeypatch):
    connection = _Connection(
        last_synced=9,
        metadata={"cursor_origin": "legacy_shared_rpc"},
    )
    web3 = _Web3(_Eth())
    status_calls = []
    _run_with(monkeypatch, connection, web3, status_calls, [(10, 20)])

    gnosis_indexer.run(from_block=10, to_block=20)

    assert [call[0][2] for call in status_calls] == [20, 20]
    assert all(call[1]["metadata"] == {"cursor_reviewed": True} for call in status_calls)
    assert connection.commits == 2
    assert connection.closed


def test_gnosis_latest_block_failure_does_not_expose_provider_details(monkeypatch):
    connection = _Connection(last_synced=9)
    secret = "rpc-secret-token"
    web3 = _Web3(_Eth(block_number_error=OSError(f"request failed at https://rpc.example/{secret}")))
    status_calls = []
    _run_with(monkeypatch, connection, web3, status_calls, [])

    with pytest.raises(RuntimeError, match=r"Gnosis latest block lookup failed \(OSError\)") as error:
        gnosis_indexer.run()

    assert secret not in str(error.value)
    assert status_calls == []
    assert connection.closed


@pytest.mark.parametrize(
    ("from_block", "to_block", "message"),
    [
        (-1, None, "--from-block must be non-negative"),
        (None, -1, "--to-block must be non-negative"),
        (11, 10, "--to-block must be greater than or equal to --from-block"),
    ],
)
def test_gnosis_rejects_invalid_block_window_before_provider_or_database(
    monkeypatch, from_block, to_block, message
):
    monkeypatch.setattr(
        gnosis_indexer,
        "get_web3",
        lambda: pytest.fail("invalid range must be rejected before provider setup"),
    )
    monkeypatch.setattr(
        gnosis_indexer,
        "get_db",
        lambda: pytest.fail("invalid range must be rejected before database setup"),
    )

    with pytest.raises(ValueError, match=message):
        gnosis_indexer.run(from_block=from_block, to_block=to_block)


def test_gnosis_run_skips_previously_claimed_log_before_projecting(monkeypatch):
    connection = _Connection(last_synced=9)
    topic = next(
        topic for topic, name in gnosis_indexer.EVENT_TOPICS.items()
        if name == "VoteProposal"
    )
    web3 = _Web3(_Eth(logs=[_event_log(topic)]))
    status_calls = []
    _run_with(monkeypatch, connection, web3, status_calls, [(10, 20)])
    claimed = []
    monkeypatch.setattr(
        gnosis_indexer,
        "claim_gnosis_event_log",
        lambda *_args, **_kwargs: claimed.append(True) or False,
    )

    gnosis_indexer.run()

    assert claimed == [True]
    assert connection.commits == 2
    assert connection.closed


def test_gnosis_failed_range_rolls_back_and_preserves_last_checkpoint(monkeypatch):
    connection = _Connection(last_synced=9)
    secret = "rpc-secret-token"
    web3 = _Web3(_Eth({16: OSError(f"request failed at https://rpc.example/{secret}")}))
    status_calls = []
    _run_with(monkeypatch, connection, web3, status_calls, [(10, 15), (16, 20)])

    with pytest.raises(RuntimeError, match="Gnosis block range 16-20 failed") as error:
        gnosis_indexer.run()

    assert len(web3.eth.calls) == 2
    assert connection.commits == 2  # First range and the durable error status.
    assert connection.rollbacks == 1
    assert connection.closed
    assert [call[0][2] for call in status_calls] == [15, 15]
    assert [call[0][3] for call in status_calls] == ["syncing", "error"]
    assert all(call[0][1] == gnosis_indexer.INDEXER_TYPE for call in status_calls)
    assert status_calls[-1][0][4] == "OSError during Gnosis block processing"
    assert secret not in str(error.value)
    assert secret not in status_calls[-1][0][4]
    assert all(call[1]["db"] is connection for call in status_calls)


def test_gnosis_outbox_failure_propagates_without_advancing_failed_range(monkeypatch):
    connection = _Connection(last_synced=9)
    secret = "rpc-secret-token"
    failure = OutboxEnqueueError(f"outbox request failed https://clickhouse.example/{secret}")
    web3 = _Web3(_Eth({10: failure}))
    status_calls = []
    _run_with(monkeypatch, connection, web3, status_calls, [(10, 15)])

    with pytest.raises(OutboxEnqueueError, match="ClickHouse outbox enqueue failed") as error:
        gnosis_indexer.run()

    assert connection.commits == 1  # Error status only; failed range stays rolled back.
    assert connection.rollbacks == 1
    assert connection.closed
    assert [call[0][2] for call in status_calls] == [9]
    assert [call[0][3] for call in status_calls] == ["error"]
    assert status_calls[-1][0][4] == "ClickHouse outbox enqueue failed"
    assert secret not in str(error.value)
    assert secret not in status_calls[-1][0][4]
    assert all(call[0][1] == gnosis_indexer.INDEXER_TYPE for call in status_calls)

