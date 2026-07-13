"""Focused unit tests for durable event delivery semantics."""

from unittest.mock import MagicMock, patch

from services.events.bus import EventBus


def _connection(fetchall=None, fetchone=None):
    conn = MagicMock()
    cursor = MagicMock()
    cursor.fetchall.return_value = fetchall or []
    cursor.fetchone.return_value = fetchone
    conn.cursor.return_value.__enter__.return_value = cursor
    return conn, cursor


def test_claim_commits_before_event_processing():
    conn, _ = _connection(fetchall=[("event", "kind", {}, 0, 3)])
    bus = EventBus(conn=conn)
    order = []
    conn.commit.side_effect = lambda: order.append("commit")

    with patch.object(bus, "_process_event", side_effect=lambda *args: order.append("handler") or "success"):
        bus.process_pending(worker_id="worker")

    assert order.index("commit") < order.index("handler")


def test_successful_delivery_is_not_invoked_again():
    handler_id = "handler"
    conn, _ = _connection(fetchall=[
        (handler_id, "module", "function", 30, "success")
    ])
    bus = EventBus(conn=conn)

    with patch.object(bus, "_invoke_handler") as invoke, patch.object(bus, "_complete"):
        assert bus._process_event("event", "kind", {}, "worker") == "success"

    invoke.assert_not_called()


def test_handler_timeout_terminates_child():
    bus = EventBus(conn=MagicMock())
    process = MagicMock()
    process.is_alive.return_value = True
    context = MagicMock()
    context.Process.return_value = process

    with patch("services.events.bus.multiprocessing.get_context", return_value=context):
        status, error = bus._invoke_handler("module", "function", "kind", {}, 1)

    assert status == "timeout"
    assert "exceeded" in error
    process.terminate.assert_called_once()


def test_replay_preserves_successful_handler_delivery_state():
    conn, cursor = _connection(fetchone=("event",))
    bus = EventBus(conn=conn)

    assert bus.replay_dead_letter("event", "operator") is True
    sql = " ".join(call.args[0] for call in cursor.execute.call_args_list)
    assert "DELETE FROM event_handler_delivery" not in sql
    assert "status = 'pending'" in sql


def test_injected_connection_is_never_closed():
    conn, _ = _connection()
    bus = EventBus(conn=conn)
    bus.get_stats()
    bus.cleanup_old_events()
    bus.close()
    conn.close.assert_not_called()


def test_claim_query_recovers_expired_processing_lease():
    conn, cursor = _connection()
    EventBus(conn=conn)._claim(10, "worker")
    sql = cursor.execute.call_args.args[0]
    assert "status = 'processing' AND lease_expires_at < NOW()" in sql
    assert "FOR UPDATE SKIP LOCKED" in sql
