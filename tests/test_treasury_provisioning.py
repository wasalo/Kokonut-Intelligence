"""Tests for farm SAFE provisioning (KI-12 Phase C).

Mocks the DB layer — verifies propose → approve lifecycle and validation.
"""

import uuid

import pytest

from services.treasury.provisioning import (
    SafeProvisioningRequest,
    approve_farm_safe,
    propose_farm_safe,
)

VALID_LOCATION = "a0000000-0000-0000-0000-000000000001"
STEWARD_A = "0x1111111111111111111111111111111111111111"
STEWARD_B = "0x2222222222222222222222222222222222222222"


class _FakeRow:
    def __init__(self, **kw):
        self.__dict__.update(kw)
        self._mapping = kw


class _FakeCursor:
    def __init__(self, rows=None):
        self.rows = rows or []
        self.calls = []

    def execute(self, sql, params=None):
        self.calls.append((sql, params))
        return self

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return self.rows


class _FakeConn:
    def __init__(self, rows=None):
        self.cursor_ = _FakeCursor(rows)
        self.committed = False

    def execute(self, sql, params=None):
        self.cursor_.execute(sql, params)
        return self

    def fetchone(self):
        return self.cursor_.fetchone()

    def fetchall(self):
        return self.cursor_.fetchall()

    def commit(self):
        self.committed = True

    def rollback(self):
        pass

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_propose_requires_stewards(monkeypatch):
    monkeypatch.setattr("services.treasury.provisioning._db", lambda: _FakeConn())
    with pytest.raises(ValueError, match="steward"):
        propose_farm_safe(SafeProvisioningRequest(location_id=VALID_LOCATION, stewards=[]))


def test_propose_requires_valid_threshold(monkeypatch):
    monkeypatch.setattr("services.treasury.provisioning._db", lambda: _FakeConn())
    with pytest.raises(ValueError, match="Threshold"):
        propose_farm_safe(SafeProvisioningRequest(
            location_id=VALID_LOCATION, stewards=[STEWARD_A], threshold=0))
    with pytest.raises(ValueError, match="exceeds"):
        propose_farm_safe(SafeProvisioningRequest(
            location_id=VALID_LOCATION, stewards=[STEWARD_A], threshold=2))


def test_propose_rejects_unknown_location(monkeypatch):
    conn = _FakeConn()  # no rows -> location not found
    monkeypatch.setattr("services.treasury.provisioning._db", lambda: conn)
    with pytest.raises(ValueError, match="Location not found"):
        propose_farm_safe(SafeProvisioningRequest(
            location_id=str(uuid.uuid4()), stewards=[STEWARD_A]))


def test_propose_creates_draft_record(monkeypatch):
    conn = _FakeConn(rows=[_FakeRow(id=VALID_LOCATION, name="Adelphi")])
    monkeypatch.setattr("services.treasury.provisioning._db", lambda: conn)
    result = propose_farm_safe(SafeProvisioningRequest(
        location_id=VALID_LOCATION,
        chain="gnosis",
        stewards=[STEWARD_A, STEWARD_B],
        threshold=2,
        name="Adelphi Farm SAFE",
    ))
    assert result["provisioning_status"] == "proposed"
    assert result["status"] == "draft"
    assert result["threshold"] == 2
    assert result["stewards"] == [STEWARD_A, STEWARD_B]
    # the INSERT was executed
    assert any("INSERT INTO safe_account" in c[0] for c in conn.cursor_.calls)


def test_approve_requires_proposed_state(monkeypatch):
    conn = _FakeConn(rows=[_FakeRow(
        id=str(uuid.uuid4()), provisioning_status="active", status="published")])
    monkeypatch.setattr("services.treasury.provisioning._db", lambda: conn)
    with pytest.raises(ValueError, match="Cannot approve"):
        approve_farm_safe(str(uuid.uuid4()), "0xabc")


def test_approve_with_deployed_address(monkeypatch):
    safe_id = str(uuid.uuid4())
    deployed = "0xAbC1234567890123456789012345678901234567"
    conn = _FakeConn(rows=[_FakeRow(
        id=safe_id, provisioning_status="proposed", status="draft")])
    monkeypatch.setattr("services.treasury.provisioning._db", lambda: conn)
    result = approve_farm_safe(safe_id, deployed)
    assert result["provisioning_status"] == "active"
    # UPDATE with the lowercased deployed address
    update_sql = [c[0] for c in conn.cursor_.calls if "UPDATE safe_account" in c[0]]
    assert update_sql
    assert conn.cursor_.calls[-1][1][0] == deployed.lower()


def test_approve_without_address_marks_approved(monkeypatch):
    safe_id = str(uuid.uuid4())
    conn = _FakeConn(rows=[_FakeRow(
        id=safe_id, provisioning_status="proposed", status="draft")])
    monkeypatch.setattr("services.treasury.provisioning._db", lambda: conn)
    result = approve_farm_safe(safe_id)
    assert result["provisioning_status"] == "approved"
