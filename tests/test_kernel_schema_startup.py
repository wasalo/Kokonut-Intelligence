"""Regression checks for the Kernel supervisor's pre-spawn schema gate."""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from services.core import runtime, schema_readiness


def test_schema_failure_prevents_api_and_worker_processes_from_starting(monkeypatch) -> None:
    spawn = Mock()
    monkeypatch.setattr(runtime.subprocess, "Popen", spawn)

    def fail_readiness(**_kwargs) -> None:
        raise schema_readiness.SchemaReadinessError("pending_migrations", not_applied=1)

    monkeypatch.setattr(schema_readiness, "require_schema_ready", fail_readiness)

    result = runtime.run(with_workers=True, require_schema=True)

    assert result == 1
    spawn.assert_not_called()


@pytest.mark.parametrize(
    "unsafe_values",
    [
        ("kokonut", "kokonut", True, False, True, False, False, False, False, False, False, False),
        ("kokonut", "kokonut", True, False, False, True, False, False, False, False, False, False),
        ("kokonut", "kokonut", True, False, False, False, True, False, False, False, False, False),
        ("kokonut", "kokonut", True, False, False, False, False, True, False, False, False, False),
        ("kokonut", "kokonut", True, False, False, False, False, False, True, False, False, False),
        ("kokonut_runtime", "kokonut", True, False, False, False, False, False, False, False, False, False),
        ("kokonut_runtime", "kokonut_runtime", False, False, False, False, False, False, False, False, False, False),
        ("kokonut_runtime", "kokonut_runtime", True, True, False, False, False, False, False, False, False, False),
        ("kokonut_runtime", "kokonut_runtime", True, False, False, False, False, False, False, True, False, False),
        ("kokonut_runtime", "kokonut_runtime", True, False, False, False, False, False, False, False, True, False),
        ("kokonut_runtime", "kokonut_runtime", True, False, False, False, False, False, False, False, False, True),
    ],
)
def test_runtime_role_readiness_rejects_privileged_or_non_login_roles(unsafe_values) -> None:
    cursor = Mock()
    cursor.fetchone.return_value = unsafe_values

    with pytest.raises(schema_readiness.SchemaReadinessError):
        schema_readiness._require_non_admin_runtime_role(cursor)

    cursor.execute.assert_called_once()
    assert "pg_roles" in cursor.execute.call_args.args[0]


def test_runtime_role_readiness_accepts_dedicated_unprivileged_login() -> None:
    cursor = Mock()
    cursor.fetchone.return_value = (
        "kokonut_runtime",
        "kokonut_runtime",
        True,
        False,
        False,
        False,
        False,
        False,
        False,
        False,
        False,
        False,
    )

    schema_readiness._require_non_admin_runtime_role(cursor)

    cursor.execute.assert_called_once()


def test_missing_runtime_role_is_a_safe_readiness_error() -> None:
    cursor = Mock()
    cursor.fetchone.return_value = None

    with pytest.raises(schema_readiness.SchemaReadinessError) as error:
        schema_readiness._require_non_admin_runtime_role(cursor)

    assert error.value.code == "runtime_role_unavailable"


def test_unsafe_runtime_role_prevents_api_and_worker_processes_from_starting(monkeypatch) -> None:
    spawn = Mock()
    readiness = Mock(side_effect=schema_readiness.SchemaReadinessError("runtime_role_unsafe"))
    monkeypatch.setattr(runtime.subprocess, "Popen", spawn)
    monkeypatch.setattr(schema_readiness, "require_schema_ready", readiness)

    result = runtime.run(with_workers=True, require_runtime_role=True)

    assert result == 1
    readiness.assert_called_once_with(require_runtime_role=True)
    spawn.assert_not_called()
