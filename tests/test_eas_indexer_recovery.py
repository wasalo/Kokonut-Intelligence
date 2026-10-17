"""EAS cursor state must commit with the records and projections it covers."""

import json
from unittest.mock import MagicMock, patch

import pytest

from services.ingestion import eas_indexer
from services.ingestion.clickhouse_outbox import OutboxEnqueueError


def _connection_with_wallets(wallets):
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchall.return_value = wallets
    return connection


def _attestation(uid, timestamp):
    return {
        "id": uid,
        "time": timestamp,
        "schema": {"id": "schema-id", "schema": ""},
        "revoked": False,
    }


def _executed(connection):
    cursor = connection.cursor.return_value.__enter__.return_value
    return [call.args for call in cursor.execute.call_args_list]


def test_recipient_cursors_advance_independently_in_same_transaction():
    connection = _connection_with_wallets(
        [
            ("wallet-1", "0x111", "celo"),
            ("wallet-2", "0x222", "celo"),
        ]
    )
    cursor_updates = []
    recipient_cursors = {"wallet-1": 100, "wallet-2": 170}

    def query(_chain, _query, variables):
        timestamp = 150 if variables["recipient"] == "0x111" else 180
        return {"attestations": [_attestation(variables["recipient"], timestamp)]}

    with (
        patch("services.ingestion.eas_indexer.get_db", return_value=connection),
        patch(
            "services.ingestion.eas_indexer.get_last_attestation_time",
            side_effect=lambda _db, _chain, wallet_id: recipient_cursors[wallet_id],
        ),
        patch(
            "services.ingestion.eas_indexer.advance_attestation_cursor",
            side_effect=lambda _db, chain, wallet_id, timestamp: cursor_updates.append(
                (chain, wallet_id, timestamp)
            ),
        ),
        patch("services.ingestion.eas_indexer.get_chain_attestation_watermark", return_value=180),
        patch("services.ingestion.eas_indexer.query_eas", side_effect=query),
        patch("services.ingestion.eas_indexer.insert_attestation", return_value="record-id"),
        patch("services.ingestion.eas_indexer.insert_clickhouse"),
        patch("services.ingestion.base.get_db", side_effect=AssertionError("opened a second connection")),
    ):
        eas_indexer.run(chain="celo")

    calls = _executed(connection)
    status_writes = [args for args in calls if "INSERT INTO chain_indexer_status" in args[0]]
    audit_writes = [args for args in calls if "INSERT INTO ingestion_log" in args[0]]
    assert len(status_writes) == 1
    assert status_writes[0][1][3] == "healthy"
    assert json.loads(status_writes[0][1][5]) == {"last_attestation_time": 180}
    assert len(audit_writes) == 1
    assert audit_writes[0][1][7] == "success"
    assert audit_writes[0][1][9] == 2
    assert cursor_updates == [("celo", "wallet-1", 150), ("celo", "wallet-2", 180)]
    statements = [args[0] for args in calls]
    assert any("pg_advisory_xact_lock" in sql for sql in statements)
    assert statements.count("SAVEPOINT eas_wallet_index") == 2
    connection.commit.assert_called_once_with()
    connection.close.assert_called_once_with()


def test_failed_wallet_rolls_back_its_rows_and_keeps_prior_watermark():
    connection = _connection_with_wallets(
        [
            ("wallet-1", "0x111", "celo"),
            ("wallet-2", "0x222", "celo"),
        ]
    )
    cursor_updates = []

    def query(_chain, _query, variables):
        if variables["recipient"] == "0x222":
            raise RuntimeError("provider unavailable")
        return {"attestations": [_attestation("known", 150)]}

    with (
        patch("services.ingestion.eas_indexer.get_db", return_value=connection),
        patch("services.ingestion.eas_indexer.get_last_attestation_time", return_value=100),
        patch(
            "services.ingestion.eas_indexer.advance_attestation_cursor",
            side_effect=lambda _db, chain, wallet_id, timestamp: cursor_updates.append(
                (chain, wallet_id, timestamp)
            ),
        ),
        patch("services.ingestion.eas_indexer.get_chain_attestation_watermark", return_value=150),
        patch("services.ingestion.eas_indexer.query_eas", side_effect=query),
        patch("services.ingestion.eas_indexer.insert_attestation", return_value="record-id"),
        patch("services.ingestion.eas_indexer.insert_clickhouse"),
        patch("services.ingestion.base.get_db", side_effect=AssertionError("opened a second connection")),
        pytest.raises(RuntimeError, match=r"incomplete for chain\(s\): celo"),
    ):
        eas_indexer.run(chain="celo")

    calls = _executed(connection)
    status_writes = [args for args in calls if "INSERT INTO chain_indexer_status" in args[0]]
    audit_writes = [args for args in calls if "INSERT INTO ingestion_log" in args[0]]
    assert status_writes[0][1][3] == "error"
    assert status_writes[0][1][4] == "provider unavailable"
    assert json.loads(status_writes[0][1][5]) == {"last_attestation_time": 150}
    assert audit_writes[0][1][7] == "partial"
    assert audit_writes[0][1][9] == 1
    assert cursor_updates == [("celo", "wallet-1", 150)]
    statements = [args[0] for args in calls]
    assert "ROLLBACK TO SAVEPOINT eas_wallet_index" in statements
    connection.commit.assert_called_once_with()
    connection.rollback.assert_not_called()
    connection.close.assert_called_once_with()


def test_outbox_failure_rolls_back_records_and_never_commits_cursor():
    connection = _connection_with_wallets([("wallet-1", "0x111", "celo")])

    with (
        patch("services.ingestion.eas_indexer.get_db", return_value=connection),
        patch("services.ingestion.eas_indexer.get_last_attestation_time", return_value=100),
        patch(
            "services.ingestion.eas_indexer.query_eas",
            return_value={"attestations": [_attestation("known", 150)]},
        ),
        patch("services.ingestion.eas_indexer.insert_attestation", return_value="record-id"),
        patch("services.ingestion.eas_indexer.advance_attestation_cursor") as advance_cursor,
        patch(
            "services.ingestion.eas_indexer.insert_clickhouse",
            side_effect=OutboxEnqueueError("queue unavailable"),
        ),
        patch("services.ingestion.base.get_db", side_effect=AssertionError("opened a second connection")),
        pytest.raises(OutboxEnqueueError, match="queue unavailable"),
    ):
        eas_indexer.run(chain="celo")

    connection.rollback.assert_called_once_with()
    connection.commit.assert_not_called()
    assert not any(
        "INSERT INTO chain_indexer_status" in args[0] for args in _executed(connection)
    )
    advance_cursor.assert_not_called()
    connection.close.assert_called_once_with()


def test_invalid_chain_fails_before_opening_database():
    with (
        patch("services.ingestion.eas_indexer.get_db") as get_db,
        pytest.raises(ValueError, match="Unsupported EAS chain"),
    ):
        eas_indexer.run(chain="ethereum")

    get_db.assert_not_called()
