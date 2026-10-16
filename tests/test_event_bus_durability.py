"""Focused unit tests for durable event delivery semantics."""

import json
import subprocess
import sys
from unittest.mock import MagicMock, patch

from services.events.bus import EventBus, _handler_child_environment, resolve_handler

REGISTERED_HANDLERS = (
    ("services.ingestion.anomaly_detector", "handle_sensor_reading"),
    ("services.events.handlers", "handle_stale_data"),
    ("services.cache.events", "handle_metric_computed"),
    ("services.cache.events", "handle_crisp_scored"),
    ("services.events.handlers", "handle_alert_notification"),
)


def test_every_registered_handler_resolves_to_a_callable():
    for module_path, function_name in REGISTERED_HANDLERS:
        assert callable(resolve_handler(module_path, function_name))


def test_lazy_event_bus_connection_uses_configured_timeout():
    connection = MagicMock()
    with patch("services.common.database.get_db", return_value=connection) as get_db:
        bus = EventBus(connect_timeout=5)

        assert bus._get_conn() is connection

    get_db.assert_called_once_with(connect_timeout=5)
    bus.close()
    connection.close.assert_called_once()


def test_unregistered_event_handler_is_rejected_before_import():
    with patch("services.events.bus.importlib.import_module") as importer:
        try:
            resolve_handler("os", "system")
            assert False, "unregistered handler should fail closed"
        except ValueError:
            importer.assert_not_called()


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


def test_handler_child_environment_removes_all_worker_secrets():
    env = _handler_child_environment(
        {
            "KOKONUT_SENSOR_ANOMALY_DATABASE_URL": "postgresql://worker",
            "KOKONUT_SENSOR_ANOMALY_WORKER_CREDENTIAL": "worker-secret",
            "KOKONUT_OTHER_WORKER_DATABASE_URL": "postgresql://other",
            "KOKONUT_OTHER_WORKER_WORKER_CREDENTIAL": "other-secret",
            "PG_PASSWORD": "legacy-runtime-secret",
            "KOKONUT_OPERATOR_AUTH_PASSWORD": "operator-secret",
            "DATABASE_URL": "application-config",
        }
    )

    assert env == {
        "PG_PASSWORD": "legacy-runtime-secret",
        "KOKONUT_OPERATOR_AUTH_PASSWORD": "operator-secret",
        "DATABASE_URL": "application-config",
    }


def test_handler_success_uses_filtered_environment_and_stdin_request():
    bus = EventBus(conn=MagicMock())
    process = MagicMock()
    process.communicate.return_value = ('{"succeeded":true}', "")
    process.returncode = 0

    with patch.dict(
        "os.environ",
        {
            "KOKONUT_SENSOR_ANOMALY_DATABASE_URL": "postgresql://worker",
            "KOKONUT_SENSOR_ANOMALY_WORKER_CREDENTIAL": "worker-secret",
            "PG_PASSWORD": "runtime-secret",
        },
        clear=True,
    ), patch("services.events.bus.subprocess.Popen", return_value=process) as popen:
        status, error = bus._invoke_handler(
            "module", "function", "kind", {"value": 2}, 5, event_id="event-1"
        )

    assert (status, error) == ("success", None)
    args, kwargs = popen.call_args
    assert args[0] == [sys.executable, "-m", "services.events.handler_runner"]
    assert kwargs["env"] == {"PG_PASSWORD": "runtime-secret"}
    assert kwargs["stdin"] == subprocess.PIPE
    assert kwargs["stdout"] == subprocess.PIPE
    assert kwargs["text"] is True
    request = json.loads(process.communicate.call_args.args[0])
    assert request == {
        "module_path": "module",
        "function_name": "function",
        "event_type": "kind",
        "payload": {"value": 2},
        "event_id": "event-1",
    }
    assert "worker-secret" not in repr(args)


def test_handler_error_result_is_bounded():
    bus = EventBus(conn=MagicMock())
    process = MagicMock()
    process.communicate.return_value = (
        json.dumps({"succeeded": False, "error": "RuntimeError: handler failed"}),
        "",
    )
    process.returncode = 0

    with patch("services.events.bus.subprocess.Popen", return_value=process):
        status, error = bus._invoke_handler("module", "function", "kind", {}, 5)

    assert (status, error) == ("error", "RuntimeError: handler failed")


def test_handler_timeout_kills_and_reaps_child():
    bus = EventBus(conn=MagicMock())
    process = MagicMock()
    process.communicate.side_effect = [
        subprocess.TimeoutExpired("handler", 1),
        ("", ""),
    ]

    with patch("services.events.bus.subprocess.Popen", return_value=process):
        status, error = bus._invoke_handler("module", "function", "kind", {}, 1)

    assert status == "timeout"
    assert "exceeded" in error
    process.kill.assert_called_once()
    assert process.communicate.call_count == 2


def test_handler_nonzero_exit_does_not_expose_stderr_or_environment():
    bus = EventBus(conn=MagicMock())
    process = MagicMock()
    process.communicate.return_value = ("", "worker-secret")
    process.returncode = 7

    with patch("services.events.bus.subprocess.Popen", return_value=process):
        status, error = bus._invoke_handler("module", "function", "kind", {}, 5)

    assert (status, error) == ("error", "Handler process exited with code 7")
    assert "worker-secret" not in error


def test_unserializable_handler_request_fails_before_process_start():
    bus = EventBus(conn=MagicMock())

    with patch("services.events.bus.subprocess.Popen") as popen:
        status, error = bus._invoke_handler("module", "function", "kind", {"value": object()}, 5)

    assert (status, error) == ("error", "Handler request could not be encoded")
    popen.assert_not_called()


def test_replay_preserves_successful_handler_delivery_state():
    conn, cursor = _connection(fetchone=("event",))
    bus = EventBus(conn=conn)

    assert bus.replay_dead_letter("event", "operator") is True
    sql = " ".join(call.args[0] for call in cursor.execute.call_args_list)
    assert "DELETE FROM event_handler_delivery" not in sql
    assert "status = 'pending'" in sql


def test_injected_connection_is_never_closed(monkeypatch):
    monkeypatch.setenv("KOKONUT_FEATURE_EVENT_RETENTION_CLEANUP", "true")
    conn, _ = _connection(fetchall=[("policy", 30)], fetchone=(0,))
    bus = EventBus(conn=conn)
    bus.get_stats()
    bus.cleanup_old_events(actor="operator")
    bus.close()
    conn.close.assert_not_called()


def test_cleanup_preserves_events_with_pending_disposition_or_failed_delivery(monkeypatch):
    monkeypatch.setenv("KOKONUT_FEATURE_EVENT_RETENTION_CLEANUP", "true")
    conn, cursor = _connection(fetchall=[("policy", 30)], fetchone=(2,))

    EventBus(conn=conn).cleanup_old_events(actor="operator")

    policy_sql = " ".join(cursor.execute.call_args_list[1].args[0].split())
    assert "jurisdiction_code IS NULL" in policy_sql
    assert "purpose_code IS NULL" in policy_sql
    assert "FROM data_retention_policy overlap" in policy_sql
    sql = " ".join(cursor.execute.call_args_list[2].args[0].split())
    assert "dead.disposition = 'pending'" in sql
    assert "dead.original_event_id = platform_event.id" in sql
    assert "AND NOT EXISTS ( SELECT 1 FROM event_dead_letter dead" in sql
    assert "AND NOT EXISTS ( SELECT 1 FROM event_handler_delivery delivery" in sql
    assert "delivery.status <> 'success'" in sql
    assert "data_retention_legal_hold hold" in sql
    assert "hold.released_at IS NULL" in sql
    assert "status IN ('completed', 'dead_letter')" in sql
    assert cursor.execute.call_args_list[2].args[1] == (30,)


def test_cleanup_fails_closed_without_one_approved_policy(monkeypatch):
    import pytest

    monkeypatch.setenv("KOKONUT_FEATURE_EVENT_RETENTION_CLEANUP", "true")
    conn, _ = _connection()
    bus = EventBus(conn=conn)

    with pytest.raises(RuntimeError, match="exactly one approved"):
        bus.cleanup_old_events(actor="operator")

    conn.rollback.assert_called_once()


def test_cleanup_fails_closed_without_approved_retention_feature(monkeypatch):
    import pytest

    monkeypatch.delenv("KOKONUT_FEATURE_EVENT_RETENTION_CLEANUP", raising=False)
    bus = EventBus(conn=MagicMock())

    with pytest.raises(RuntimeError, match="KOKONUT_FEATURE_EVENT_RETENTION_CLEANUP=true"):
        bus.cleanup_old_events(actor="operator")

    bus._conn.cursor.assert_not_called()


def test_claim_query_recovers_expired_processing_lease():
    conn, cursor = _connection()
    EventBus(conn=conn)._claim(10, "worker")
    sql = cursor.execute.call_args.args[0]
    assert "status = 'processing' AND lease_expires_at < NOW()" in sql
    assert "FOR UPDATE SKIP LOCKED" in sql


def test_completion_reports_lost_lease_when_update_changes_no_row():
    conn, cursor = _connection(fetchone=None)
    bus = EventBus(conn=conn)

    assert bus._complete("event", "stale-worker") is False
    assert "status = 'processing'" in cursor.execute.call_args.args[0]


def test_process_event_does_not_report_success_after_lease_loss():
    conn, _ = _connection(fetchall=[])
    bus = EventBus(conn=conn)
    with patch.object(bus, "_complete", return_value=False):
        assert bus._process_event("event", "kind", {}, "worker") == "lease_lost"


def test_process_pending_reports_lease_loss_separately_from_handler_failure():
    conn, _ = _connection(fetchall=[("event", "kind", {}, 0, 3)])
    bus = EventBus(conn=conn)

    with patch.object(bus, "_process_event", return_value="lease_lost"), patch.object(
        bus, "_retry_or_dead_letter"
    ) as retry:
        stats = bus.process_pending(worker_id="stale-worker")

    assert stats == {"processed": 0, "failed": 0, "skipped": 0, "lease_lost": 1}
    retry.assert_not_called()


def test_orphaned_dead_letter_cannot_report_successful_replay():
    conn, _ = _connection(fetchone=None)
    bus = EventBus(conn=conn)

    assert bus.replay_dead_letter("missing-event", "operator") is False


def test_dead_letter_operator_actions_require_identity_and_reason():
    bus = EventBus(conn=MagicMock())
    try:
        bus.replay_dead_letter("event", "")
        assert False, "blank replay actor should fail"
    except ValueError:
        pass
    try:
        bus.dispose_dead_letter("event", "discarded", "operator", "")
        assert False, "blank disposal reason should fail"
    except ValueError:
        pass
