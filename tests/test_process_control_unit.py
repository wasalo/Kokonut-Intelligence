"""Unit regression tests for process capability persistence."""

import pytest

from services.systems import process_control as pc

CAPABILITY = {"cp": 1.2, "cpk": 1.0, "pp": 1.1, "ppk": 0.9, "sigma_level": 3.0}


class _Cursor:
    def __init__(self, row):
        self.row = row
        self.params = None

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def execute(self, _sql, params):
        self.params = params

    def fetchone(self):
        return self.row


class _Connection:
    def __init__(self, row):
        self.cursor_ = _Cursor(row)
        self.committed = False
        self.rollbacks = 0

    def cursor(self, **_kwargs):
        return self.cursor_

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rollbacks += 1


def test_persist_capability_returns_row_before_commit(monkeypatch):
    record = {"id": "cap-1", "metric": "cycle_time"}
    conn = _Connection(record)
    monkeypatch.setattr(pc, "process_capability", lambda *_args: CAPABILITY)

    result = pc.persist_capability(conn, "farm", "cycle_time", 10.0, 1.0)

    assert result["persisted"] is True
    assert result["record"] == record
    assert conn.committed
    assert conn.rollbacks == 0


def test_persist_capability_rolls_back_when_returning_row_missing(monkeypatch):
    conn = _Connection(None)
    monkeypatch.setattr(pc, "process_capability", lambda *_args: CAPABILITY)

    with pytest.raises(RuntimeError, match="RETURNING"):
        pc.persist_capability(conn, "farm", "cycle_time", 10.0, 1.0)

    assert not conn.committed
    assert conn.rollbacks == 1
