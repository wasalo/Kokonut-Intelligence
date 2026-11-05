from unittest.mock import Mock

import pytest

from services.common.worker_database import WorkerDatabaseConfigurationError
from services.scheduler import worker


@pytest.mark.parametrize("selection", [
    {"KOKONUT_SCHEDULER_DATABASE_URL": ""},
    {"KOKONUT_ISOLATED_WORKER_KEY": "scheduler"},
    {"KOKONUT_DENY_SHARED_DATABASE": "true"},
])
def test_selected_scheduler_without_dsn_never_uses_runtime(monkeypatch, selection):
    monkeypatch.delenv("KOKONUT_SCHEDULER_DATABASE_URL", raising=False)
    monkeypatch.delenv("KOKONUT_ISOLATED_WORKER_KEY", raising=False)
    monkeypatch.delenv("KOKONUT_DENY_SHARED_DATABASE", raising=False)
    for name, value in selection.items():
        monkeypatch.setenv(name, value)
    shared = Mock()
    monkeypatch.setattr(worker, "get_db", shared)
    with pytest.raises(WorkerDatabaseConfigurationError):
        worker._scheduler_connection()
    shared.assert_not_called()


def test_dedicated_connection_failure_does_not_fallback(monkeypatch):
    monkeypatch.setenv("KOKONUT_SCHEDULER_DATABASE_URL", "postgresql://synthetic")
    shared = Mock()
    dedicated = Mock(side_effect=WorkerDatabaseConfigurationError("wrong identity"))
    monkeypatch.setattr(worker, "get_db", shared)
    monkeypatch.setattr(worker, "get_worker_db", dedicated)
    with pytest.raises(WorkerDatabaseConfigurationError):
        worker._scheduler_connection()
    dedicated.assert_called_once_with("scheduler", connect_timeout=5)
    shared.assert_not_called()


def test_scheduler_child_filters_runtime_credentials_and_unrelated_worker_dsns():
    from services.common.worker_environment import worker_subprocess_environment

    source = {
        "PG_USER": "kokonut_runtime",
        "PG_PASSWORD": "runtime-secret",
        "KOKONUT_SCHEDULER_PASSWORD": "bootstrap-only-secret",
        "KOKONUT_OPERATOR_AUTH_PASSWORD": "operator-secret",
        "KOKONUT_SCHEDULER_DATABASE_URL": "scheduler-dsn",
        "KOKONUT_NOTIFICATION_DELIVERY_DATABASE_URL": "notification-dsn",
    }
    child = worker_subprocess_environment(
        allowed_worker_keys=("scheduler",), isolated_worker_key="scheduler", environ=source,
    )
    assert child["KOKONUT_SCHEDULER_DATABASE_URL"] == "scheduler-dsn"
    assert child["KOKONUT_DENY_SHARED_DATABASE"] == "true"
    assert "KOKONUT_SCHEDULER_PASSWORD" not in child
    assert "PG_USER" not in child
    assert "PG_PASSWORD" not in child
    assert "KOKONUT_OPERATOR_AUTH_PASSWORD" not in child
    assert "KOKONUT_NOTIFICATION_DELIVERY_DATABASE_URL" not in child


@pytest.mark.parametrize("password", ["", "short", "same-password-01234567890123456789"])
def test_scheduler_provisioning_rejects_unsafe_secret_before_database_access(password):
    from services.migration.scheduler_role import provision_scheduler_role

    forbidden = ("same-password-01234567890123456789",)
    connection = Mock()
    with pytest.raises(ValueError):
        provision_scheduler_role(connection, database="fixture", password=password,
                                 forbidden_passwords=forbidden)
    connection.cursor.assert_not_called()
