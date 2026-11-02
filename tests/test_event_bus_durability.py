"""Focused unit tests for durable event delivery semantics."""

import json
import subprocess
import sys
from unittest.mock import MagicMock, patch

import pytest

from services.events.bus import EventBus, _handler_child_environment, resolve_handler
from services.events.dispatch_worker import IsolatedEventBus

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


def test_shared_event_bus_publishes_but_only_isolated_worker_dispatches():
    assert not hasattr(EventBus, "process_pending")
    assert not hasattr(EventBus, "_claim")
    assert hasattr(EventBus, "publish")
    assert callable(getattr(IsolatedEventBus, "process_pending", None))


def test_lazy_event_bus_connection_uses_configured_timeout():
    connection = MagicMock()
    with patch("services.common.database.get_db", return_value=connection) as get_db:
        bus = EventBus(connect_timeout=5)

        assert bus._get_conn() is connection

    get_db.assert_called_once_with(connect_timeout=5)
    bus.close()
    connection.close.assert_called_once()


def test_supervised_event_handler_wait_refreshes_progress_without_changing_result():
    bus = EventBus()
    process = MagicMock(returncode=0)
    process.communicate.side_effect = [
        subprocess.TimeoutExpired(["handler"], 5),
        ('{"succeeded": true}', ""),
    ]
    with (
        patch("services.events.bus.subprocess.Popen", return_value=process),
        patch("services.events.bus.time.monotonic", side_effect=(0, 1, 2)),
        patch("services.core.worker_progress.pulse_worker_progress") as pulse,
    ):
        result = bus._invoke_handler("module", "handler", "event", {}, 10)

    assert result == ("success", None)
    assert process.communicate.call_count == 2
    pulse.assert_called_once_with()


@pytest.mark.parametrize("lease_seconds", [29, 3601, 0, -1, True, False, 30.0, "30", None])
def test_event_bus_rejects_invalid_lease_before_database_access(lease_seconds):
    with patch("services.common.database.get_db") as get_db:
        with pytest.raises(ValueError, match="lease must be between 30 and 3600"):
            EventBus(lease_seconds=lease_seconds)

    get_db.assert_not_called()


@pytest.mark.parametrize("lease_seconds", [30, 3600])
def test_event_bus_accepts_lease_bounds(lease_seconds):
    connection = MagicMock()

    bus = EventBus(conn=connection, lease_seconds=lease_seconds)

    assert bus.lease_seconds == lease_seconds
    assert bus._get_conn() is connection


def test_isolated_worker_bounds_lease_extension_for_maximum_handler_timeout():
    bus = IsolatedEventBus(conn=MagicMock(), lease_seconds=30)
    handler = ("handler", "module", "function", 3570, None)
    calls = []
    results = iter(([handler], (True,), (True,), (True,), (True,)))

    def function(query, parameters, **kwargs):
        calls.append((query, parameters))
        return next(results)

    with patch.object(bus, "_function", side_effect=function), patch.object(
        bus, "_invoke_handler", return_value=("success", None)
    ) as invoke:
        assert bus._process_event("event", "kind", {}, "worker", "lease") == "success"

    renew_query = "SELECT kokonut_security.renew_platform_event_lease(%s, %s, %s, %s)"
    renew = next(parameters for query, parameters in calls if query == renew_query)
    assert renew == ("event", "worker", "lease", 3600)
    invoke.assert_called_once_with("module", "function", "kind", {}, 3570, event_id="event")


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


def test_isolated_dispatch_rolls_back_failed_bounded_call():
    conn, cursor = _connection()
    bus = IsolatedEventBus(conn=conn)
    failure = RuntimeError("bounded call failed")
    cursor.execute.side_effect = failure

    with pytest.raises(RuntimeError, match="bounded call failed"):
        bus._function("SELECT bounded_function()", ())

    assert conn.rollback.call_count == 1


def test_successful_delivery_is_not_invoked_again():
    handler_id = "handler"
    bus = IsolatedEventBus(conn=MagicMock())

    with (
        patch.object(
            bus,
            "_function",
            side_effect=[[(handler_id, "module", "function", 30, "success")], (True,)],
        ),
        patch.object(bus, "_invoke_handler") as invoke,
    ):
        assert bus._process_event("event", "kind", {}, "worker", "lease") == "success"

    invoke.assert_not_called()


def test_handler_child_environment_allows_only_exact_anomaly_worker_identity():
    env = _handler_child_environment(
        "services.ingestion.anomaly_detector",
        "handle_sensor_reading",
        {
            "KOKONUT_SENSOR_ANOMALY_DATABASE_URL": "postgresql://worker",
            "KOKONUT_SENSOR_ANOMALY_WORKER_CREDENTIAL": "worker-secret",
            "KOKONUT_OTHER_WORKER_DATABASE_URL": "postgresql://other",
            "KOKONUT_OTHER_WORKER_WORKER_CREDENTIAL": "other-secret",
            "PG_PASSWORD": "legacy-runtime-secret",
            "PG_USER": "kokonut_runtime",
            "KOKONUT_OPERATOR_AUTH_PASSWORD": "operator-secret",
            "GEE_SERVICE_ACCOUNT_KEY": "global-gee-secret",
            "COPERNICUS_CLIENT_SECRET": "global-copernicus-secret",
            "DATABASE_URL": "application-config",
        }
    )

    assert env == {
        "KOKONUT_SENSOR_ANOMALY_DATABASE_URL": "postgresql://worker",
        "KOKONUT_SENSOR_ANOMALY_WORKER_CREDENTIAL": "worker-secret",
        "KOKONUT_ISOLATED_WORKER_KEY": "sensor_anomaly",
        "KOKONUT_DENY_SHARED_DATABASE": "true",
    }


def test_cache_handlers_receive_only_their_exact_worker_identity():
    source = {
        "KOKONUT_CACHE_INVALIDATION_DATABASE_URL": "postgresql://cache-worker",
        "KOKONUT_CACHE_INVALIDATION_WORKER_CREDENTIAL": "cache-secret",
        "KOKONUT_SENSOR_ANOMALY_DATABASE_URL": "postgresql://anomaly-worker",
        "KOKONUT_SENSOR_ANOMALY_WORKER_CREDENTIAL": "anomaly-secret",
        "KOKONUT_SCHEDULER_DATABASE_URL": "postgresql://scheduler",
        "KOKONUT_SCHEDULER_WORKER_CREDENTIAL": "scheduler-secret",
        "PG_PASSWORD": "legacy-runtime-secret",
        "PG_USER": "kokonut_runtime",
        "DATABASE_URL": "application-config",
    }

    for function_name in (
        "handle_metric_computed",
        "handle_crisp_scored",
        "handle_sensor_reading",
        "handle_harvest_recorded",
    ):
        env = _handler_child_environment(
            "services.cache.events",
            function_name,
            {**source, "KOKONUT_FEATURE_SIGNED_CACHE_INVALIDATION": "true"},
        )
        assert env == {
            "KOKONUT_CACHE_INVALIDATION_DATABASE_URL": "postgresql://cache-worker",
            "KOKONUT_CACHE_INVALIDATION_WORKER_CREDENTIAL": "cache-secret",
            "KOKONUT_ISOLATED_WORKER_KEY": "cache_invalidation",
            "KOKONUT_FEATURE_SIGNED_CACHE_INVALIDATION": "true",
            "KOKONUT_DENY_SHARED_DATABASE": "true",
        }


def test_notification_handlers_receive_only_their_enqueue_identity():
    env = _handler_child_environment(
        "services.events.handlers",
        "handle_alert_notification",
        {
            "KOKONUT_NOTIFICATION_ENQUEUE_DATABASE_URL": "postgresql://notification-enqueue",
            "KOKONUT_SENSOR_ANOMALY_DATABASE_URL": "postgresql://worker",
            "KOKONUT_SENSOR_ANOMALY_WORKER_CREDENTIAL": "worker-secret",
            "KOKONUT_EVENT_BUS_DATABASE_URL": "postgresql://events",
            "KOKONUT_EVENT_BUS_WORKER_CREDENTIAL": "event-secret",
            "DATABASE_URL": "application-config",
            "KOKONUT_FEATURE_ISOLATED_NOTIFICATION_ENQUEUE": "true",
        },
    )

    assert env == {
        "KOKONUT_NOTIFICATION_ENQUEUE_DATABASE_URL": "postgresql://notification-enqueue",
        "KOKONUT_ISOLATED_WORKER_KEY": "notification_enqueue",
        "KOKONUT_FEATURE_ISOLATED_NOTIFICATION_ENQUEUE": "true",
        "KOKONUT_DENY_SHARED_DATABASE": "true",
    }


def test_feature_off_notification_handler_has_no_database_identity():
    env = _handler_child_environment(
        "services.events.handlers",
        "handle_alert_notification",
        {
            "DATABASE_URL": "application-config",
            "PG_PASSWORD": "shared-secret",
            "KOKONUT_NOTIFICATION_ENQUEUE_DATABASE_URL": "postgresql://notification-enqueue",
            "KOKONUT_NOTIFICATION_ENQUEUE_WORKER_CREDENTIAL": "worker-secret",
        },
    )

    assert env == {"KOKONUT_DENY_SHARED_DATABASE": "true"}


def test_feature_off_cache_handler_has_no_database_identity():
    env = _handler_child_environment(
        "services.cache.events",
        "handle_metric_computed",
        {
            "PG_PASSWORD": "shared-secret",
            "KOKONUT_CACHE_INVALIDATION_DATABASE_URL": "postgresql://cache-worker",
            "KOKONUT_CACHE_INVALIDATION_WORKER_CREDENTIAL": "worker-secret",
        },
    )

    assert env == {"KOKONUT_DENY_SHARED_DATABASE": "true"}


def test_unmapped_event_handler_receives_no_worker_identity():
    env = _handler_child_environment(
        "services.events.handlers",
        "handle_unregistered_handler",
        {
            "KOKONUT_NOTIFICATION_ENQUEUE_DATABASE_URL": "postgresql://notification-enqueue",
            "KOKONUT_SENSOR_ANOMALY_DATABASE_URL": "postgresql://worker",
            "KOKONUT_SENSOR_ANOMALY_WORKER_CREDENTIAL": "worker-secret",
            "DATABASE_URL": "application-config",
            "PG_PASSWORD": "legacy-runtime-secret",
        },
    )

    assert env == {"KOKONUT_DENY_SHARED_DATABASE": "true"}


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
            "services.ingestion.anomaly_detector",
            "handle_sensor_reading",
            "sensor_reading",
            {"sensor_id": "sensor-1", "location_id": "location-1"},
            5,
            event_id="event-1",
        )

    assert (status, error) == ("success", None)
    args, kwargs = popen.call_args
    assert args[0] == [sys.executable, "-m", "services.events.handler_runner"]
    assert kwargs["env"] == {
        "KOKONUT_SENSOR_ANOMALY_DATABASE_URL": "postgresql://worker",
        "KOKONUT_SENSOR_ANOMALY_WORKER_CREDENTIAL": "worker-secret",
        "KOKONUT_ISOLATED_WORKER_KEY": "sensor_anomaly",
        "KOKONUT_DENY_SHARED_DATABASE": "true",
    }
    assert "KOKONUT_EVENT_BUS_WORKER_CREDENTIAL" not in kwargs["env"]
    assert kwargs["stdin"] == subprocess.PIPE
    assert kwargs["stdout"] == subprocess.PIPE
    assert kwargs["text"] is True
    request = json.loads(process.communicate.call_args.args[0])
    assert request == {
        "module_path": "services.ingestion.anomaly_detector",
        "function_name": "handle_sensor_reading",
        "event_type": "sensor_reading",
        "payload": {"sensor_id": "sensor-1", "location_id": "location-1"},
        "event_id": "event-1",
    }
    assert "worker-secret" not in repr(args)


def test_handler_error_result_is_bounded():
    bus = EventBus(conn=MagicMock())
    process = MagicMock()
    process.communicate.return_value = (
        json.dumps({
            "succeeded": False,
            "error": "handler execution failed",
            "error_class": "RuntimeError",
        }),
        "",
    )
    process.returncode = 0

    with patch("services.events.bus.subprocess.Popen", return_value=process):
        status, error = bus._invoke_handler("module", "function", "kind", {}, 5)

    assert (status, error) == ("error", "Handler failed (RuntimeError)")


def test_handler_error_result_does_not_trust_child_error_text():
    secret = "database URL password=secret-row-data"
    bus = EventBus(conn=MagicMock())
    process = MagicMock()
    process.communicate.return_value = (
        json.dumps({"succeeded": False, "error": secret}),
        "",
    )
    process.returncode = 0

    with patch("services.events.bus.subprocess.Popen", return_value=process):
        status, error = bus._invoke_handler("module", "function", "kind", {}, 5)

    assert (status, error) == ("error", "Handler failed")
    assert secret not in error


def test_handler_timeout_kills_and_reaps_child():
    bus = EventBus(conn=MagicMock())
    process = MagicMock()
    process.communicate.side_effect = [
        subprocess.TimeoutExpired("handler", 1),
        ("", ""),
    ]
    process.poll.return_value = None

    with (
        patch("services.events.bus.subprocess.Popen", return_value=process),
        patch("services.events.bus.time.monotonic", side_effect=(0, 0, 2)),
    ):
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


def test_completion_reports_lost_lease_from_bounded_function():
    bus = IsolatedEventBus(conn=MagicMock())
    with patch.object(bus, "_function", return_value=(False,)) as function:
        assert bus._complete("event", "stale-worker", "lease") is False

    function.assert_called_once_with(
        "SELECT kokonut_security.complete_platform_event(%s, %s, %s)",
        ("event", "stale-worker", "lease"),
    )


def test_process_event_does_not_report_success_after_lease_loss():
    bus = IsolatedEventBus(conn=MagicMock())
    with patch.object(bus, "_function", side_effect=[[], (False,)]):
        assert bus._process_event("event", "kind", {}, "worker", "lease") == "lease_lost"


def test_process_pending_reports_lease_loss_separately_from_handler_failure():
    bus = IsolatedEventBus(conn=MagicMock())

    with (
        patch.object(
            bus,
            "_claim",
            return_value=[("event", "kind", {}, 0, 3, "lease")],
        ),
        patch.object(bus, "_process_event", return_value="lease_lost"),
        patch.object(bus, "_retry_or_dead_letter") as retry,
    ):
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
