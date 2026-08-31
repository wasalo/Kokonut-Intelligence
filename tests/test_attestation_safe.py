"""Tests for SAFE-proposed attestation flow (KI-14 D2).

Mocks the EASClient, SAFE Transaction Service, and DB to verify the
propose → reconcile lifecycle without touching a real chain.
"""

import uuid
from unittest.mock import patch

import pytest

from services.attestation.safe_flow import (
    propose_attestation,
    reconcile_attestation_executions,
)

REQ_ID = str(uuid.uuid4())
SUBJECT_ID = str(uuid.uuid4())
CORE_TEAM_SAFE = "0x03779B674CbCBfc0B801c4cAc9DFaC8aACbbD5c5"
SAFE_TX_HASH = "0x" + "aa" * 32


class _FakeRow:
    def __init__(self, **kw):
        self._mapping = kw
        for k, v in kw.items():
            setattr(self, k, v)

    def __getitem__(self, key):
        return self._mapping[key]

    def __contains__(self, key):
        return key in self._mapping

    def get(self, key, default=None):
        return self._mapping.get(key, default)


class _FakeCursor:
    def __init__(self, rows=None):
        self.rows = rows or []
        self.calls = []

    def execute(self, sql, params=None):
        self.calls.append((sql, params))
        return self

    def fetchone(self):
        return self.rows.pop(0) if self.rows else None

    def fetchall(self):
        out = self.rows[:]
        self.rows = []
        return out

    def mappings(self):
        return self

    def first(self):
        return self.rows.pop(0) if self.rows else None

    def all(self):
        out = self.rows[:]
        self.rows = []
        return out


class _FakeConn:
    def __init__(self, rows=None):
        self.cursor_ = _FakeCursor(rows)

    def execute(self, sql, params=None):
        self.cursor_.execute(sql, params)
        return self.cursor_

    def text(self, sql):
        return sql

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


@pytest.fixture
def pending_request() -> _FakeRow:
    return _FakeRow(
        id=REQ_ID,
        subject_type="data_stream_post",
        subject_id=SUBJECT_ID,
        schema_name="kokonutDataPostV1",
        chain="celo",
        metadata='{"content_payload_hash": "0xabc123"}',
    )


@pytest.fixture
def data_stream_post() -> _FakeRow:
    from datetime import datetime, timezone
    return _FakeRow(
        id=SUBJECT_ID,
        location_id="a0000000-0000-0000-0000-000000000001",
        post_type="test",
        title="Test attestation",
        content_hash="0xdeadbeef",
        media_type="text",
        anchored_at=datetime.now(timezone.utc),
        visibility="public",
    )


class _FakeEASClient:
    def __init__(self, *args, **kwargs):
        pass

    def build_attest_call(self, **kwargs):
        return {
            "to": "0x0000000000000000000000000000000000000001",
            "value": 0,
            "data": "0xdeadbeef",
            "from": "0x0000000000000000000000000000000000000002",
            "chainId": 42220,
        }


def test_propose_attestation(monkeypatch, pending_request, data_stream_post):
    # Block the attestation module chain from loading (imports trigger SOPS).
    # Provide fake modules so lazy imports inside propose_attestation work.
    import sys
    import types

    fake_eas = types.ModuleType("services.attestation.eas_client")
    fake_eas.EASClient = _FakeEASClient
    sys.modules["services.attestation.eas_client"] = fake_eas

    fake_pub = types.ModuleType("services.attestation.publisher")
    fake_pub._resolve_schema_uid = lambda *a, **kw: "0x" + "12" * 32
    sys.modules["services.attestation.publisher"] = fake_pub

    fake_schemas = types.ModuleType("services.attestation.schemas")
    fake_schemas.prepare_data_post_attestation_data = (
        lambda **kw: [{"name": "x", "type": "string", "value": "y"}]
    )
    sys.modules["services.attestation.schemas"] = fake_schemas

    conn = _FakeConn(rows=[pending_request, data_stream_post])

    # Mock SafeProposeClient at its source
    class _FakeSafePropose:
        def __init__(self, *args, **kwargs):
            pass

        def propose(self, tx):
            tx.safe_tx_hash = SAFE_TX_HASH
            return {"safeTxHash": SAFE_TX_HASH, "nonce": "0"}

    monkeypatch.setattr(
        "services.attestation.safe_flow.SafeProposeClient",
        _FakeSafePropose,
    )
    monkeypatch.setenv("SAFE_DELEGATE_KEY", "0x" + "11" * 32)

    result = propose_attestation(conn, REQ_ID, safe_chain="celo")
    assert result["proposal_status"] == "proposed"
    assert result["safe_tx_hash"] == SAFE_TX_HASH
    assert result["safe_chain"] == "celo"


def test_reconcile_marks_executed(monkeypatch):
    conn = _FakeConn(rows=[
        _FakeRow(id=REQ_ID, safe_tx_hash=SAFE_TX_HASH),
    ])

    from services.treasury.safe import SafeTransaction

    executed_tx = SafeTransaction(
        safe_tx_hash=SAFE_TX_HASH,
        nonce=0,
        to="0x0000000000000000000000000000000000000001",
        value="0",
        executed=True,
        execution_date="2026-08-30T12:00:00Z",
    )

    class _FakeReader:
        def __init__(self, *args, **kwargs):
            pass

        def multisig_transactions(self, address, limit=50):
            return [executed_tx]

    monkeypatch.setattr(
        "services.treasury.safe.SafeReadClient",
        lambda *a, **kw: _FakeReader(),
    )

    result = reconcile_attestation_executions(conn, safe_chain="celo")
    assert result["checked"] == 1
    assert result["executed"] == 1


def test_reconcile_skips_non_executed(monkeypatch):
    conn = _FakeConn(rows=[
        _FakeRow(id=REQ_ID, safe_tx_hash=SAFE_TX_HASH),
    ])

    from services.treasury.safe import SafeTransaction

    pending_tx = SafeTransaction(
        safe_tx_hash=SAFE_TX_HASH,
        nonce=0,
        to="0x0000000000000000000000000000000000000001",
        value="0",
        executed=None,
        execution_date=None,
    )

    class _FakeReader:
        def __init__(self, *args, **kwargs):
            pass

        def multisig_transactions(self, address, limit=50):
            return [pending_tx]

    monkeypatch.setattr(
        "services.treasury.safe.SafeReadClient",
        lambda *a, **kw: _FakeReader(),
    )

    result = reconcile_attestation_executions(conn, safe_chain="celo")
    assert result["checked"] == 1
    assert result["executed"] == 0