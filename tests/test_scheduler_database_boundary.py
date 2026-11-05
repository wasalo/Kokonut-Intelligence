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
