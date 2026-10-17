"""Contract checks for the isolated scheduled EAS worker."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from services.ingestion import eas_worker

WALLET_ID = "a0000000-0000-0000-0000-000000000001"
RECIPIENT = "0x" + "a" * 40


def _attestation(uid: int = 1, timestamp: int = 1_800_000_000) -> dict:
    return {
        "id": "0x" + f"{uid:064x}",
        "txid": "0x" + "b" * 64,
        "schema": {"id": "0x" + "c" * 64, "schema": "uint256 value"},
        "attester": "0x" + "d" * 40,
        "recipient": RECIPIENT,
        "data": "0x1234",
        "time": str(timestamp),
        "timeCreated": str(timestamp),
        "revocable": True,
        "revoked": False,
        "expirationTime": "0",
    }


def test_worker_help_imports_without_shared_database_environment():
    project_root = Path(eas_worker.__file__).resolve().parents[2]
    environment = {
        "KOKONUT_ENV": "production",
        "PATH": os.environ.get("PATH", ""),
        "PYTHONPATH": project_root,
    }
    result = subprocess.run(
        [sys.executable, "-m", "services.ingestion.eas_worker", "--help"],
        cwd=str(project_root),
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
    )

    assert result.returncode == 0, result.stderr
    assert "--chain" in result.stdout


class _Cursor:
    def __init__(self, connection):
        self.connection = connection
        self.result = None
        self.rows = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, statement, params=()):
        self.connection.statements.append((statement, params))
        if "list_eas_indexer_recipients" in statement:
            self.rows = [(WALLET_ID, RECIPIENT)]
        elif "read_eas_indexer_cursor" in statement:
            self.result = (100,)
        elif "store_eas_indexer_page" in statement:
            self.result = (1,)
        elif "advance_eas_indexer_cursor" in statement:
            self.result = (1800000000,)
        elif "finish_eas_indexer_chain" in statement:
            self.result = (1800000000,)
        elif "release_eas_indexer_chain_lock" in statement:
            self.result = (True,)
        else:
            self.result = (None,)

    def fetchone(self):
        return self.result

    def fetchall(self):
        return self.rows


class _Connection:
    def __init__(self):
        self.statements = []
        self.commits = 0
        self.rollbacks = 0
        self.closed = False

    @contextmanager
    def cursor(self):
        yield _Cursor(self)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed = True


def test_worker_is_default_off_and_fails_before_database_access(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["eas_worker", "--chain", "celo"])
    with (
        patch.object(eas_worker, "is_enabled", return_value=False),
        patch.object(eas_worker, "get_worker_db") as get_db,
        pytest.raises(SystemExit),
    ):
        eas_worker.main()
    get_db.assert_not_called()


def test_worker_requires_an_explicit_chain_before_database_access(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["eas_worker"])
    with (
        patch.object(eas_worker, "is_enabled", return_value=True),
        patch.object(eas_worker, "get_worker_db") as get_db,
        pytest.raises(SystemExit),
    ):
        eas_worker.main()
    get_db.assert_not_called()


def test_wallet_pages_use_only_bounded_functions_and_advance_after_success():
    connection = _Connection()
    attestation = _attestation(timestamp=150)
    with patch.object(eas_worker, "query_eas", return_value={"attestations": [attestation]}) as query:
        inserted, cursor_time = eas_worker._fetch_wallet_pages(
            connection,
            chain="celo",
            wallet_id=WALLET_ID,
            recipient=RECIPIENT,
            cursor_time=100,
            sleep=lambda _seconds: None,
        )

    assert (inserted, cursor_time) == (1, 150)
    query.assert_called_once_with(
        "celo",
        eas_worker.ATTESTATIONS_BY_RECIPIENT,
        {"recipient": RECIPIENT, "after": 0},
    )
    statements = [statement for statement, _ in connection.statements]
    assert len(statements) == 2
    assert all("kokonut_security." in statement for statement in statements)
    assert "store_eas_indexer_page" in statements[0]
    page = json.loads(connection.statements[0][1][2])
    assert page == [
        {
            "attestation": attestation,
            "payload_hash": hashlib.sha256(json.dumps(attestation, sort_keys=True, default=str).encode()).hexdigest(),
        }
    ]
    assert "advance_eas_indexer_cursor" in statements[1]
    assert connection.commits == 2
    assert connection.rollbacks == 0


def test_provider_failure_does_not_advance_the_cursor_after_prior_page():
    connection = _Connection()
    full_page = [_attestation(uid=index + 1, timestamp=150) for index in range(100)]
    with patch.object(
        eas_worker,
        "query_eas",
        side_effect=[{"attestations": full_page}, TimeoutError("temporary")],
    ):
        with pytest.raises(TimeoutError, match="temporary"):
            eas_worker._fetch_wallet_pages(
                connection,
                chain="celo",
                wallet_id=WALLET_ID,
                recipient=RECIPIENT,
                cursor_time=100,
                sleep=lambda _seconds: None,
            )

    statements = [statement for statement, _ in connection.statements]
    assert len(statements) == 1
    assert "store_eas_indexer_page" in statements[0]
    assert connection.commits == 1


def test_wallet_scan_stops_after_inclusive_cursor_boundary():
    connection = _Connection()
    page = [_attestation(uid=index + 1, timestamp=200) for index in range(99)]
    page.append(_attestation(uid=100, timestamp=199))
    with patch.object(eas_worker, "query_eas", return_value={"attestations": page}) as query:
        inserted, cursor_time = eas_worker._fetch_wallet_pages(
            connection,
            chain="celo",
            wallet_id=WALLET_ID,
            recipient=RECIPIENT,
            cursor_time=200,
            sleep=lambda _seconds: None,
        )

    assert (inserted, cursor_time) == (1, 200)
    query.assert_called_once_with(
        "celo",
        eas_worker.ATTESTATIONS_BY_RECIPIENT,
        {"recipient": RECIPIENT, "after": 0},
    )
    page_write = next(params for statement, params in connection.statements if "store_eas_indexer_page" in statement)
    persisted = json.loads(page_write[2])
    assert [row["attestation"]["time"] for row in persisted] == ["200"] * 99
    assert connection.commits == 2


def test_unordered_provider_page_fails_before_cursor_advance():
    connection = _Connection()
    page = [_attestation(uid=1, timestamp=199), _attestation(uid=2, timestamp=200)]
    with (
        patch.object(eas_worker, "query_eas", return_value={"attestations": page}),
        pytest.raises(ValueError, match="not ordered newest first"),
    ):
        eas_worker._fetch_wallet_pages(
            connection,
            chain="celo",
            wallet_id=WALLET_ID,
            recipient=RECIPIENT,
            cursor_time=200,
            sleep=lambda _seconds: None,
        )

    assert not any("store_eas_indexer_page" in statement for statement, _ in connection.statements)
    assert not any("advance_eas_indexer_cursor" in statement for statement, _ in connection.statements)
    assert connection.commits == 0


def test_missing_attestations_field_does_not_advance_the_cursor():
    connection = _Connection()
    with (
        patch.object(eas_worker, "query_eas", return_value={}),
        pytest.raises(ValueError, match="missing attestations"),
    ):
        eas_worker._fetch_wallet_pages(
            connection,
            chain="celo",
            wallet_id=WALLET_ID,
            recipient=RECIPIENT,
            cursor_time=100,
            sleep=lambda _seconds: None,
        )

    assert not any(
        "advance_eas_indexer_cursor" in statement
        for statement, _params in connection.statements
    )
    assert connection.commits == 0


def test_persistence_failure_aborts_without_cursor_advance():
    connection = _Connection()
    connection.cursor = MagicMock(side_effect=RuntimeError("database error"))
    with patch.object(eas_worker, "query_eas", return_value={"attestations": [_attestation(timestamp=150)]}):
        with pytest.raises(eas_worker.EASWorkerPersistenceError):
            eas_worker._fetch_wallet_pages(
                connection,
                chain="celo",
                wallet_id=WALLET_ID,
                recipient=RECIPIENT,
                cursor_time=100,
                sleep=lambda _seconds: None,
            )
    assert connection.rollbacks == 1
