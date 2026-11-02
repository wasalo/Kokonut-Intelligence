"""Cursor and transaction cleanup for report snapshot persistence."""

from __future__ import annotations

import pytest

from services.export.reports import context


class _Cursor:
    def __init__(self, failure=None):
        self.failure = failure
        self.closed = False

    def execute(self, *_args):
        if self.failure == "execute":
            raise RuntimeError("synthetic snapshot execute failure")

    def fetchone(self):
        if self.failure == "fetchone":
            raise RuntimeError("synthetic snapshot fetch failure")
        return ("snapshot-1",)

    def close(self):
        self.closed = True


class _Connection:
    def __init__(self, cursor):
        self.cursor_instance = cursor
        self.commits = 0
        self.rollbacks = 0

    def cursor(self, **_kwargs):
        return self.cursor_instance

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


@pytest.mark.parametrize("failure", ["execute", "fetchone"])
def test_store_snapshot_rolls_back_and_closes_on_query_failure(failure, monkeypatch):
    cursor = _Cursor(failure)
    conn = _Connection(cursor)
    monkeypatch.setattr(context, "attach_public_interest_context", lambda _c, data, _l: data)

    with pytest.raises(RuntimeError, match="synthetic snapshot"):
        context.store_snapshot(conn, {"report_type": "synthetic"})

    assert cursor.closed
    assert conn.commits == 0
    assert conn.rollbacks == 1


def test_store_snapshot_commits_and_closes_after_success(monkeypatch):
    cursor = _Cursor()
    conn = _Connection(cursor)
    monkeypatch.setattr(context, "attach_public_interest_context", lambda _c, data, _l: data)

    snapshot_id = context.store_snapshot(conn, {"report_type": "synthetic"})

    assert snapshot_id == "snapshot-1"
    assert cursor.closed
    assert conn.commits == 1
    assert conn.rollbacks == 0


def test_verify_snapshot_closes_cursor_when_query_fails(capsys):
    cursor = _Cursor("execute")
    conn = _Connection(cursor)

    with pytest.raises(RuntimeError, match="synthetic snapshot execute failure"):
        context._verify_snapshot(conn, "00000000-0000-4000-8000-000000000001")

    assert cursor.closed
    assert capsys.readouterr().out == ""
