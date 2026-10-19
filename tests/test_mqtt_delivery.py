"""Focused MQTT durable receipt state-machine checks using a fake connection."""

from __future__ import annotations

from uuid import uuid4

import pytest

from services.ingestion import mqtt_delivery


class _Result:
    def __init__(self, row=None):
        self._row = row

    def first(self):
        return self._row


class _Connection:
    def __init__(self, *, status="pending", attempt_count=0):
        self.row = {"id": uuid4(), "status": status, "attempt_count": attempt_count}
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def execute(self, statement, params=None):
        sql = str(statement).strip()
        self.calls.append((sql, params))
        if sql.startswith("SELECT * FROM mqtt_delivery"):
            return _Result(self.row)
        return _Result()


def _connection(monkeypatch, *, status="pending", attempt_count=0):
    conn = _Connection(status=status, attempt_count=attempt_count)
    monkeypatch.setattr(mqtt_delivery, "get_connection", lambda: conn)
    return conn


def _update(conn):
    return next(params for sql, params in conn.calls if sql.startswith("UPDATE mqtt_delivery"))


def test_accepted_delivery_persists_terminal_outcome(monkeypatch):
    conn = _connection(monkeypatch)
    calls = []

    result = mqtt_delivery.process_delivery("sensors/a/b/readings", b"{}", lambda: calls.append(1) or "accepted")

    assert result == {"id": str(conn.row["id"]), "status": "accepted", "attempt_count": 1}
    assert calls == [1]
    assert _update(conn)["status"] == "accepted"
    assert _update(conn)["error"] is None


def test_terminal_delivery_suppresses_duplicate_handler(monkeypatch):
    conn = _connection(monkeypatch, status="accepted", attempt_count=2)
    called = False

    def handler():
        nonlocal called
        called = True
        return "accepted"

    result = mqtt_delivery.process_delivery("sensors/a/b/readings", b"{}", handler)

    assert result == {"id": str(conn.row["id"]), "status": "accepted", "attempt_count": 2}
    assert called is False
    assert not any(sql.startswith("UPDATE mqtt_delivery") for sql, _ in conn.calls)


def test_rejection_is_a_terminal_acknowledgeable_outcome(monkeypatch):
    conn = _connection(monkeypatch)

    result = mqtt_delivery.process_delivery("sensors/a/b/readings", b"bad", lambda: "rejected")

    assert result["status"] == "rejected"
    assert _update(conn)["status"] == "rejected"
    assert _update(conn)["attempt"] == 1


def test_retryable_failure_records_only_exception_class(monkeypatch):
    conn = _connection(monkeypatch)

    def fail_with_private_detail():
        raise ValueError("private payload and credential detail")

    result = mqtt_delivery.process_delivery("sensors/a/b/readings", b"{}", fail_with_private_detail)

    assert result["status"] == "failed"
    assert _update(conn)["error"] == "ValueError"
    assert "private payload" not in str(conn.calls)
    assert _update(conn)["attempt"] == 1


def test_fifth_failure_becomes_dead_letter(monkeypatch):
    conn = _connection(monkeypatch, attempt_count=4)

    def fail():
        raise OSError("provider/database details")

    result = mqtt_delivery.process_delivery("sensors/a/b/readings", b"{}", fail)

    assert result["status"] == "dead_letter"
    assert result["attempt_count"] == mqtt_delivery.MAX_ATTEMPTS
    assert _update(conn)["status"] == "dead_letter"
    assert _update(conn)["error"] == "OSError"


def test_replay_records_operator_action_and_starts_new_attempt_budget(monkeypatch):
    conn = _connection(monkeypatch, status="dead_letter", attempt_count=5)

    def retry():
        raise TimeoutError("private transport details")

    result = mqtt_delivery.process_delivery(
        "sensors/a/b/readings", b"{}", retry, replay_actor="operator-1", replay_reason="upstream fixed"
    )

    action = next(params for sql, params in conn.calls if sql.startswith("INSERT INTO mqtt_delivery_action"))
    assert action["actor"] == "operator-1"
    assert action["reason"] == "upstream fixed"
    assert result["status"] == "failed"
    assert result["attempt_count"] == 1
    assert _update(conn)["attempt"] == 1
    assert _update(conn)["error"] == "TimeoutError"


@pytest.mark.parametrize(
    ("replay_actor", "replay_reason"),
    [("", "reason"), (None, "reason"), ("operator", None), ("operator", "  ")],
)
def test_invalid_replay_metadata_fails_before_database(monkeypatch, replay_actor, replay_reason):
    def unexpected_connection():
        raise AssertionError("database must not be opened")

    monkeypatch.setattr(mqtt_delivery, "get_connection", unexpected_connection)
    with pytest.raises(ValueError, match="Replay requires an actor and reason"):
        mqtt_delivery.process_delivery(
            "sensors/a/b/readings", b"{}", lambda: "accepted",
            replay_actor=replay_actor, replay_reason=replay_reason,
        )


def test_oversized_payload_fails_before_database(monkeypatch):
    def unexpected_connection():
        raise AssertionError("database must not be opened")

    monkeypatch.setattr(mqtt_delivery, "get_connection", unexpected_connection)
    with pytest.raises(ValueError, match="exceeds the broker's evidence limit"):
        mqtt_delivery.process_delivery("sensors/a/b/readings", b"x" * 10_241, lambda: "accepted")
