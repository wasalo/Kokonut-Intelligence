"""Regression checks for the Kernel supervisor's pre-spawn schema gate."""

from __future__ import annotations

from unittest.mock import Mock

from services.core import runtime, schema_readiness


def test_schema_failure_prevents_api_and_worker_processes_from_starting(monkeypatch) -> None:
    spawn = Mock()
    monkeypatch.setattr(runtime.subprocess, "Popen", spawn)

    def fail_readiness() -> None:
        raise schema_readiness.SchemaReadinessError("pending_migrations", not_applied=1)

    monkeypatch.setattr(schema_readiness, "require_schema_ready", fail_readiness)

    result = runtime.run(with_workers=True, require_schema=True)

    assert result == 1
    spawn.assert_not_called()
