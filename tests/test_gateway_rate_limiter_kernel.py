"""Focused contract tests for the PostgreSQL-backed Gateway limiter."""

from __future__ import annotations

import hashlib
import sys
import types
from contextlib import contextmanager

import pytest

from services.gateway import postgres_rate_limiter, rate_limit_cli
from services.migration import runtime_role


class _Result:
    def __init__(self, row):
        self.row = row

    def first(self):
        return self.row


class _Connection:
    def __init__(self, row):
        self.row = row
        self.calls = []

    def execute(self, statement, parameters=None):
        self.calls.append((statement, parameters))
        if statement.startswith("SELECT allowed"):
            return _Result(self.row)
        return _Result(None)


def _patch_limiter_connection(monkeypatch, conn):
    @contextmanager
    def get_connection(**kwargs):
        assert kwargs == {"connect_timeout": 3}
        yield conn

    monkeypatch.setattr("services.common.cli.get_connection", get_connection)


def test_postgres_limiter_calls_only_bounded_consume_function_with_hashed_caller(monkeypatch):
    caller = "203.0.113.11"
    conn = _Connection({"allowed": False, "retry_after_seconds": 7})
    _patch_limiter_connection(monkeypatch, conn)

    limiter = postgres_rate_limiter.PostgresRateLimiter()
    assert limiter.check(caller, 4) is False
    assert limiter.retry_after(caller, 4) == 7

    function_calls = [
        (statement, parameters)
        for statement, parameters in conn.calls
        if "consume_gateway_rate_bucket" in statement
    ]
    assert len(function_calls) == 2
    for index, (statement, parameters) in enumerate(function_calls):
        assert statement.strip().startswith("SELECT allowed")
        assert "INSERT INTO" not in statement.upper()
        assert "UPDATE " not in statement.upper()
        assert caller not in statement
        assert parameters == {
            "caller_hash": hashlib.sha256(caller.encode()).hexdigest(),
            "tokens_needed": 4,
            "consume": index == 0,
        }
    assert sum("lock_timeout" in statement for statement, _ in conn.calls) == 2
    assert sum("statement_timeout" in statement for statement, _ in conn.calls) == 2


@pytest.mark.parametrize(
    ("caller", "tokens", "consume"),
    [
        ("", 1, True),
        ("x" * 256, 1, True),
        ("caller", 0, True),
        ("caller", 101, True),
        ("caller", 1, 1),
        ("caller", True, True),
    ],
)
def test_postgres_limiter_rejects_invalid_request_before_connection(
    monkeypatch, caller, tokens, consume
):
    def unexpected_connection(**_kwargs):
        raise AssertionError("invalid request must fail before database access")

    monkeypatch.setattr("services.common.cli.get_connection", unexpected_connection)
    with pytest.raises(ValueError):
        postgres_rate_limiter.PostgresRateLimiter()._budget(
            caller, tokens, consume=consume
        )


@pytest.mark.parametrize(
    "row",
    [
        None,
        {"allowed": 1, "retry_after_seconds": 1},
        {"allowed": True, "retry_after_seconds": 0},
        {"allowed": True, "retry_after_seconds": True},
        {"allowed": True, "retry_after_seconds": 1.5},
    ],
)
def test_postgres_limiter_fails_closed_on_malformed_function_result(monkeypatch, row):
    _patch_limiter_connection(monkeypatch, _Connection(row))
    with pytest.raises(RuntimeError):
        postgres_rate_limiter.PostgresRateLimiter().check("caller")


def test_postgres_limiter_does_not_swallow_database_failures(monkeypatch):
    @contextmanager
    def failing_connection(**_kwargs):
        raise TimeoutError("database timeout")
        yield  # pragma: no cover - makes this a generator context manager

    monkeypatch.setattr("services.common.cli.get_connection", failing_connection)
    with pytest.raises(TimeoutError, match="database timeout"):
        postgres_rate_limiter.PostgresRateLimiter().check("caller")


class _MaintenanceConnection:
    def __init__(self, row):
        self.row = row
        self.calls = []
        self.committed = False
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.committed = exc_type is None
        self.closed = True
        return False

    def execute(self, statement, parameters=None):
        self.calls.append((statement, parameters))
        return _Result(self.row)


def test_rate_limit_cleanup_requires_dedicated_dsn_user_before_connect(monkeypatch):
    monkeypatch.delenv(rate_limit_cli._MAINTENANCE_DSN_ENV, raising=False)
    with pytest.raises(RuntimeError, match="KOKONUT_RATE_LIMIT_MAINTENANCE_DSN"):
        rate_limit_cli._maintenance_connection()

    monkeypatch.setenv(
        rate_limit_cli._MAINTENANCE_DSN_ENV,
        "postgresql://kokonut_runtime:synthetic@database/kokonut_intelligence",
    )
    monkeypatch.setattr(
        rate_limit_cli.psycopg2,
        "connect",
        lambda *_args, **_kwargs: pytest.fail("wrong login must fail before connect"),
    )
    with pytest.raises(RuntimeError, match="dedicated maintenance login"):
        rate_limit_cli._maintenance_connection()

    monkeypatch.setenv(
        rate_limit_cli._MAINTENANCE_USER_ENV, "kokonut_runtime"
    )
    monkeypatch.setenv(
        rate_limit_cli._MAINTENANCE_DSN_ENV,
        "postgresql://kokonut_runtime:synthetic@database/kokonut_intelligence",
    )
    with pytest.raises(RuntimeError, match="must be kokonut_rate_limit_maintenance_login"):
        rate_limit_cli._maintenance_connection()


def test_rate_limit_cleanup_opens_dedicated_dsn_with_short_timeout(monkeypatch):
    monkeypatch.delenv(rate_limit_cli._MAINTENANCE_USER_ENV, raising=False)
    dsn = (
        "postgresql://kokonut_rate_limit_maintenance_login:synthetic@"
        "database/kokonut_intelligence"
    )
    monkeypatch.setenv(rate_limit_cli._MAINTENANCE_DSN_ENV, dsn)
    raw_connection = object()
    seen = {}

    def connect(actual_dsn, **kwargs):
        seen.update(dsn=actual_dsn, kwargs=kwargs)
        return raw_connection

    class _Wrapped:
        def __init__(self, *, connection):
            self.connection = connection

    monkeypatch.setattr(rate_limit_cli.psycopg2, "connect", connect)
    monkeypatch.setitem(
        sys.modules,
        "services.common.database",
        types.SimpleNamespace(DatabaseConnection=_Wrapped),
    )

    wrapped = rate_limit_cli._maintenance_connection()
    assert isinstance(wrapped, _Wrapped)
    assert wrapped.connection is raw_connection
    assert seen == {"dsn": dsn, "kwargs": {"connect_timeout": 3}}


def test_rate_limit_cleanup_uses_bounded_function_and_shared_connection_lifecycle(monkeypatch):
    conn = _MaintenanceConnection({"deleted": 3})
    monkeypatch.setattr(rate_limit_cli, "_maintenance_connection", lambda: conn)

    assert rate_limit_cli.cleanup_idle_buckets(25) == {
        "deleted": 3,
        "limit": 25,
        "idle_hours": 24,
    }
    assert conn.committed and conn.closed
    statements = [statement for statement, _ in conn.calls]
    assert statements[:2] == [
        "SET LOCAL lock_timeout = '2s'",
        "SET LOCAL statement_timeout = '3s'",
    ]
    assert len(statements) == 3
    assert statements[2].lstrip().upper().startswith("SELECT")
    assert "cleanup_idle_gateway_rate_buckets(:limit)" in statements[2]
    assert conn.calls[2][1] == {"limit": 25}


@pytest.mark.parametrize("limit", [True, 0, -1, 1001, 1.5])
def test_rate_limit_cleanup_bounds_fail_before_opening_connection(monkeypatch, limit):
    monkeypatch.setattr(
        rate_limit_cli,
        "_maintenance_connection",
        lambda: pytest.fail("invalid limit must fail before database access"),
    )
    with pytest.raises(ValueError):
        rate_limit_cli.cleanup_idle_buckets(limit)


@pytest.mark.parametrize("deleted", [None, -1, 1001, True, 1.5])
def test_rate_limit_cleanup_rejects_malformed_function_results(monkeypatch, deleted):
    monkeypatch.setattr(
        rate_limit_cli,
        "_maintenance_connection",
        lambda: _MaintenanceConnection({"deleted": deleted}),
    )
    with pytest.raises(RuntimeError, match="invalid row count"):
        rate_limit_cli.cleanup_idle_buckets(1000)


def test_rate_limit_cleanup_connection_error_does_not_expose_dsn(monkeypatch):
    monkeypatch.delenv(rate_limit_cli._MAINTENANCE_USER_ENV, raising=False)
    secret_dsn = "postgresql://kokonut_rate_limit_maintenance_login:sensitive@db/kokonut"
    monkeypatch.setenv(rate_limit_cli._MAINTENANCE_DSN_ENV, secret_dsn)
    monkeypatch.setattr(
        rate_limit_cli.psycopg2,
        "connect",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            OSError(f"connection refused for {secret_dsn}")
        ),
    )
    with pytest.raises(RuntimeError) as error:
        rate_limit_cli._maintenance_connection()
    assert secret_dsn not in str(error.value)


def test_runtime_role_declares_exact_rate_limit_function_and_table_boundaries():
    assert runtime_role._GATEWAY_RATE_LIMIT_FUNCTIONS == (
        "kokonut_security.consume_gateway_rate_bucket(text,integer,boolean)",
        "kokonut_rate_limit_maintenance.cleanup_idle_gateway_rate_buckets(integer)",
    )
    assert set(runtime_role._GATEWAY_RATE_LIMIT_FUNCTIONS).issubset(
        runtime_role._PRIVATE_RUNTIME_FUNCTIONS
    )
    assert dict(runtime_role._SECURITY_DEFINER_OWNERS)[
        runtime_role._GATEWAY_RATE_LIMIT_CONSUME_FUNCTION
    ] == "kokonut_gateway_rate_limit_owner"
    assert dict(runtime_role._SECURITY_DEFINER_OWNERS)[
        runtime_role._GATEWAY_RATE_LIMIT_CLEANUP_FUNCTION
    ] == "kokonut_gateway_rate_limit_owner"
    assert runtime_role._GATEWAY_RATE_LIMIT_CLEANUP_FUNCTION.startswith(
        "kokonut_rate_limit_maintenance."
    )
    assert "allowed_public_functions" not in runtime_role._verify_bounded_indexer_login.__kwdefaults__
    assert "gateway_rate_bucket" in runtime_role._RUNTIME_PRIVATE_TABLES
    assert "gateway_rate_bucket" not in runtime_role._RUNTIME_MUTATION_TABLES


def test_rate_limit_maintenance_role_is_fixed_optional_and_pair_validated():
    common = {
        "database": "kokonut_intelligence",
        "admin_user": "kokonut_admin",
        "admin_password": "A" * 30,
        "runtime_user": "kokonut_runtime",
        "runtime_password": "B" * 30,
        "operator_auth_user": "kokonut_operator_auth",
        "operator_auth_password": "C" * 30,
    }
    with pytest.raises(ValueError, match="provided together"):
        runtime_role.provision_runtime_role(
            None,
            **common,
            rate_limit_maintenance_user="kokonut_rate_limit_maintenance_login",
        )
    with pytest.raises(ValueError, match="must use kokonut_rate_limit_maintenance_login"):
        runtime_role.provision_runtime_role(
            None,
            **common,
            rate_limit_maintenance_user="other_login",
            rate_limit_maintenance_password="D" * 30,
        )
