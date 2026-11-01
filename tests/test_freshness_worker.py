"""Focused contract checks for the default-off isolated freshness worker."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import Mock, patch

import pytest

from services.common.worker_environment import DENY_SHARED_DATABASE_ENV
from services.ingestion import data_freshness, freshness_worker


class _Cursor:
    def __init__(self, connection, cursor_factory=None):
        self.connection = connection
        self.cursor_factory = cursor_factory
        self.row = None
        self.rows = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, statement, parameters=()):
        self.connection.calls.append((statement, parameters))
        if "list_freshness_configs" in statement:
            self.rows = [{
                "id": "config-id", "source_system": "weather",
                "stale_threshold_minutes": 60, "critical_threshold_minutes": 120,
                "location_scoped": True, "alert_cooldown_minutes": 60,
                "escalation_cooldown_minutes": 15,
            }]
        elif "list_freshness_locations" in statement:
            self.rows = [{"location_id": "location-id"}]
        elif "get_freshness_alert_state" in statement:
            self.rows = [{
                "id": "state-id", "current_status": "no_data",
                "last_event_status": None, "last_event_at": None,
            }]
        elif "read_freshness_data_at" in statement:
            self.row = (datetime(2026, 1, 1, tzinfo=timezone.utc),)
        elif "create_freshness_check" in statement:
            self.row = ("check-id",)
        elif "record_freshness_alert_event" in statement:
            self.row = ("alert-id",)
        elif "enqueue_freshness_event" in statement:
            self.row = ("alert-id",)
        elif "update_freshness" in statement:
            self.row = (None,)
        else:
            self.row = (None,)

    def fetchone(self):
        return self.row

    def fetchall(self):
        return self.rows

    def close(self):
        return None


class _Connection:
    def __init__(self):
        self.calls = []
        self.commits = 0
        self.rollbacks = 0
        self.closed = False

    def cursor(self, cursor_factory=None):
        return _Cursor(self, cursor_factory)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed = True


def test_freshness_persistence_uses_bounded_source_and_write_functions():
    connection = _Connection()
    persistence = freshness_worker.FreshnessPersistence(connection)

    configs = persistence.list_configs("weather")
    locations = persistence.list_location_ids()
    observed_at = persistence.latest_data_at("weather", True, "location-id")
    check_id = persistence.insert_check(
        "config-id", "weather", "location-id", observed_at, 1, "fresh", False, None, {}
    )
    state = persistence.lock_alert_state("weather", "location-id")
    alert_id = persistence.persist_alert_event(
        state, check_id, "weather", "location-id", "alert", "no_data",
        "stale", 61, datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    event_id = persistence.enqueue_alert_event(
        alert_id, "weather", "stale", 61, observed_at, "alert", "location-id"
    )
    persistence.update_alert_state("state-id", "fresh", datetime.now(timezone.utc))
    persistence.update_check_alert(check_id, False, "event_bus")

    assert configs[0]["source_system"] == "weather"
    assert locations == ["location-id"]
    assert observed_at == datetime(2026, 1, 1, tzinfo=timezone.utc)
    assert check_id == "check-id"
    assert alert_id == event_id == "alert-id"
    sql = "\n".join(statement for statement, _ in connection.calls)
    assert "kokonut_security.read_freshness_data_at" in sql
    assert "kokonut_security.create_freshness_check" in sql
    assert "kokonut_security.record_freshness_alert_event" in sql
    assert "kokonut_security.enqueue_freshness_event" in sql
    assert "SELECT MAX(" not in sql
    assert "INSERT INTO public." not in sql


def test_isolated_worker_is_default_off_and_closes_its_connection(monkeypatch):
    connection = _Connection()
    monkeypatch.setattr(freshness_worker, "require_feature", Mock())
    get_worker_db = Mock(return_value=connection)
    monkeypatch.setattr(freshness_worker, "get_worker_db", get_worker_db)
    expected = {"checked": 1, "results": []}
    monkeypatch.setattr(freshness_worker, "check_freshness", lambda *_args, **_kwargs: expected)

    result = freshness_worker.run("weather")

    assert result is expected
    assert connection.closed is True
    freshness_worker.require_feature.assert_called_once_with("isolated_freshness_worker")
    get_worker_db.assert_called_once_with("freshness")


def test_disabled_feature_fails_before_database_connection(monkeypatch):
    from services.core import features

    monkeypatch.setitem(
        features.FEATURES,
        "isolated_freshness_worker",
        {"enabled": False, "critical": False, "category": "security"},
    )
    get_worker_db = Mock()
    monkeypatch.setattr(freshness_worker, "get_worker_db", get_worker_db)

    with pytest.raises(RuntimeError, match="isolated_freshness_worker"):
        freshness_worker.run()

    get_worker_db.assert_not_called()


def test_isolated_worker_still_closes_connection_when_sweep_fails(monkeypatch):
    connection = _Connection()
    monkeypatch.setattr(freshness_worker, "require_feature", Mock())
    monkeypatch.setattr(freshness_worker, "get_worker_db", lambda _key: connection)
    monkeypatch.setattr(
        freshness_worker, "check_freshness", Mock(side_effect=RuntimeError("synthetic failure"))
    )

    with pytest.raises(RuntimeError, match="synthetic failure"):
        freshness_worker.run()

    assert connection.closed is True


def test_check_freshness_routes_every_database_effect_through_isolated_persistence(monkeypatch):
    connection = _Connection()
    persistence = Mock()
    persistence.list_configs.return_value = [{
        "id": "config-id", "source_system": "weather", "stale_threshold_minutes": 60,
        "critical_threshold_minutes": 120, "location_scoped": True,
        "alert_cooldown_minutes": 60, "escalation_cooldown_minutes": 15,
    }]
    persistence.list_location_ids.return_value = ["location-id"]
    persistence.latest_data_at.return_value = datetime.now(timezone.utc)
    persistence.insert_check.return_value = "check-id"
    persistence.lock_alert_state.return_value = {
        "id": "state-id", "current_status": "no_data",
        "last_event_status": None, "last_event_at": None,
    }
    result = data_freshness.check_freshness(connection, persistence=persistence)

    assert result["checked"] == 1
    assert result["fresh"] == 1
    persistence.list_configs.assert_called_once_with(None)
    persistence.list_location_ids.assert_called_once_with()
    persistence.latest_data_at.assert_called_once_with("weather", True, "location-id")
    persistence.insert_check.assert_called_once()
    persistence.lock_alert_state.assert_called_once_with("weather", "location-id")
    persistence.update_alert_state.assert_called_once_with(
        "state-id", "fresh", persistence.update_alert_state.call_args.args[2]
    )
    persistence.update_check_alert.assert_called_once_with("check-id", False, None)
    assert connection.commits == 1
    assert [statement for statement, _parameters in connection.calls] == [
        "SAVEPOINT freshness_scope",
        "RELEASE SAVEPOINT freshness_scope",
    ]


def test_check_freshness_requires_persistence_before_touching_database():
    class NoDatabaseAccess:
        def cursor(self, *_args, **_kwargs):
            raise AssertionError("shared database connection was touched")

    with pytest.raises(RuntimeError, match="isolated persistence adapter"):
        data_freshness.check_freshness(NoDatabaseAccess())


def test_worker_cli_reports_paused_before_database_when_feature_is_off(
    monkeypatch, capsys
):
    from services.core import features

    monkeypatch.setattr(features, "is_enabled", lambda name: name != "isolated_freshness_worker")
    monkeypatch.setattr(
        freshness_worker,
        "get_worker_db",
        lambda *_args: pytest.fail("disabled worker opened its database"),
    )

    freshness_worker.main(["--check"])

    assert json.loads(capsys.readouterr().out) == {
        "status": "paused",
        "reason": "isolated freshness worker is not enabled",
    }


@pytest.mark.parametrize(
    "enabled",
    [False, True],
    ids=("default-off-pauses-in-worker", "enabled-worker"),
)
def test_freshness_job_always_dispatches_only_the_isolated_worker(monkeypatch, enabled):
    from services.core import jobs

    monkeypatch.setattr(jobs, "is_enabled", lambda name: enabled if name == "isolated_freshness_worker" else True)
    with patch("services.core.jobs._run_job_spec", return_value={"status": "success"}) as dispatch:
        jobs.run_job("freshness")

    dispatch.assert_called_once_with(
        "freshness",
        jobs.JOBS["freshness"],
        location_id=None,
        driver_instance_id=None,
        chain=None,
    )


def test_new_kernel_freshness_job_plan_is_review_only_and_targets_isolated_worker():
    from services.scheduler.job_plan import build_job_plan

    plan = build_job_plan("freshness", "hourly")

    assert plan["activation_ready"] is False
    assert plan["scheduled_task"]["module_path"] == "services.ingestion.freshness_worker"
    assert plan["scheduled_task"]["command_args"] == ["--check"]


def test_freshness_worker_receives_only_its_named_dsn_in_isolated_child():
    from services.common.worker_environment import (
        scheduled_module_worker_key,
        worker_subprocess_environment,
    )

    assert scheduled_module_worker_key("services.ingestion.freshness_worker") == "freshness"
    environment = worker_subprocess_environment(
        allowed_worker_keys=("freshness",),
        isolated_database_credentials=True,
        environ={
            "PATH": "/synthetic/bin",
            "PG_USER": "shared-runtime",
            "PG_PASSWORD": "shared-secret",
            "KOKONUT_FRESHNESS_DATABASE_URL": "postgresql://dedicated",
            "KOKONUT_BAAL_INDEXER_DATABASE_URL": "postgresql://unrelated",
        },
    )

    assert environment["KOKONUT_FRESHNESS_DATABASE_URL"] == "postgresql://dedicated"
    assert "KOKONUT_BAAL_INDEXER_DATABASE_URL" not in environment
    assert "PG_USER" not in environment
    assert "PG_PASSWORD" not in environment
    assert environment[DENY_SHARED_DATABASE_ENV] == "true"
