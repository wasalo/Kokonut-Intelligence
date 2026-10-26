"""Aggregate-only readiness checks for the Field Collector tenant preflight."""

from __future__ import annotations

import json
from contextlib import contextmanager

import pytest

from services.mobile import tenant_preflight


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def first(self):
        return self._rows[0] if self._rows else None

    def all(self):
        return list(self._rows)


class _Connection:
    def __init__(self, responses):
        self.responses = responses
        self.queries = []
        self.params = []

    def execute(self, sql, params=None):
        normalized = " ".join(sql.lower().split())
        self.queries.append(normalized)
        self.params.append(params or {})
        for marker, response in self.responses.items():
            if marker in normalized:
                return _Result(response)
        return _Result([])


def test_migration_preflight_reports_only_pending_and_drift_counts(monkeypatch):
    sources = [
        {"id": "schema:001_current.sql", "checksum": "current"},
        {"id": "schema:002_drifted.sql", "checksum": "new"},
        {"id": "schema:003_pending.sql", "checksum": "pending"},
    ]
    monkeypatch.setattr(tenant_preflight, "_discover_files", lambda **_kwargs: sources)
    monkeypatch.setattr(tenant_preflight, "_validate_sources", lambda _sources: None)
    connection = _Connection(
        {
            "information_schema.columns": [{"available_column_count": 3}],
            "from schema_migration": [
                {"migration_id": "schema:001_current.sql", "checksum": "current", "status": "applied"},
                {"migration_id": "schema:002_drifted.sql", "checksum": "old", "status": "applied"},
                {"migration_id": "schema:old_removed.sql", "checksum": "old", "status": "applied"},
            ],
        }
    )

    report = tenant_preflight._migration_preflight(connection, True)

    assert report == {
        "status": "drift_detected",
        "source_migration_count": 3,
        "applied_source_migration_count": 2,
        "pending_source_migration_count": 1,
        "checksum_drift_count": 1,
        "applied_ledger_rows_without_source_count": 1,
        "identifiers_emitted": False,
    }
    assert "schema:001_current.sql" not in json.dumps(report)
    assert "old_removed" not in json.dumps(report)
    assert "current" not in json.dumps(report)
    assert '"new"' not in json.dumps(report)
    assert '"old"' not in json.dumps(report)


def test_runtime_role_preflight_reports_privilege_risk_without_role_name():
    connection = _Connection(
        {
            "with runtime_role as": [
                {
                    "superuser": False,
                    "can_create_database": False,
                    "can_create_roles": False,
                    "replication_role": False,
                    "bypasses_rls": False,
                    "public_relation_count": 12,
                    "rls_enabled_relation_count": 4,
                    "rls_forced_relation_count": 2,
                    "dml_relation_count": 7,
                    "dml_relation_without_rls_count": 1,
                    "dml_relation_with_rls_bypass_risk_count": 2,
                }
            ]
        }
    )

    report = tenant_preflight._runtime_role_preflight(connection, "kokonut_runtime")

    assert report["status"] == "dml_with_rls_bypass_risk"
    assert report["dml_relation_without_rls_count"] == 1
    assert report["dml_relation_with_rls_bypass_risk_count"] == 2
    assert report["role_name_emitted"] is False
    assert "kokonut_runtime" not in json.dumps(report)
    assert "rolname = :runtime_role_name" in connection.queries[0]
    assert connection.params[0] == {"runtime_role_name": "kokonut_runtime"}
    assert "rolbypassrls" in connection.queries[0]


def test_preflight_execution_identity_requires_dedicated_direct_read_only_login():
    connection = _Connection(
        {
            "with execution_role as": [{
                "expected_role": True,
                "direct_login": True,
                "transaction_read_only": True,
                "superuser": False,
                "can_create_database": False,
                "can_create_roles": False,
                "replication_role": False,
                "bypasses_rls": False,
                "can_create_database_objects": False,
                "can_create_public_objects": False,
                "membership_count": 0,
                "dml_relation_count": 0,
                "owned_relation_count": 0,
                "inventory_rls_enabled_relation_count": 0,
            }]
        }
    )

    report = tenant_preflight._preflight_execution_identity(connection)

    assert report["status"] == "ready"
    assert report["transaction_read_only"] is True
    assert report["dml_relation_count"] == 0
    assert report["owned_relation_count"] == 0
    assert report["role_name_emitted"] is False
    assert "kokonut_tenant_preflight" not in json.dumps(report)
    assert connection.params[0]["expected_role"] == "kokonut_tenant_preflight"
    assert "mobile_device" in connection.params[0]["inventory_relation_names"]


def test_preflight_execution_identity_rejects_role_switch_and_write_privileges():
    safe_row = {
        "expected_role": True,
        "direct_login": True,
        "transaction_read_only": True,
        "superuser": False,
        "can_create_database": False,
        "can_create_roles": False,
        "replication_role": False,
        "bypasses_rls": False,
        "can_create_database_objects": False,
        "can_create_public_objects": False,
        "membership_count": 0,
        "dml_relation_count": 0,
        "owned_relation_count": 0,
        "inventory_rls_enabled_relation_count": 0,
    }
    for unsafe_field, unsafe_value in (
        ("expected_role", False),
        ("direct_login", False),
        ("transaction_read_only", False),
        ("superuser", True),
        ("can_create_roles", True),
        ("can_create_database_objects", True),
        ("can_create_public_objects", True),
        ("membership_count", 1),
        ("dml_relation_count", 1),
        ("owned_relation_count", 1),
        ("inventory_rls_enabled_relation_count", 1),
        ("bypasses_rls", True),
    ):
        row = {**safe_row, unsafe_field: unsafe_value}
        connection = _Connection({"with execution_role as": [row]})
        report = tenant_preflight._preflight_execution_identity(connection)
        assert report["status"] == "unsafe_execution_identity", unsafe_field


def test_preflight_identity_requires_rls_visibility_for_inventory_relations():
    row = {
        "expected_role": True,
        "direct_login": True,
        "transaction_read_only": True,
        "superuser": False,
        "can_create_database": False,
        "can_create_roles": False,
        "replication_role": False,
        "bypasses_rls": True,
        "can_create_database_objects": False,
        "can_create_public_objects": False,
        "membership_count": 0,
        "dml_relation_count": 0,
        "owned_relation_count": 0,
        "inventory_rls_enabled_relation_count": 1,
    }
    connection = _Connection({"with execution_role as": [row]})

    report = tenant_preflight._preflight_execution_identity(connection)

    assert report["status"] == "ready"
    assert report["bypasses_rls"] is True
    assert report["inventory_rls_enabled_relation_count"] == 1


def test_inventory_stops_before_schema_queries_when_preflight_identity_is_unsafe():
    connection = _Connection(
        {
            "with execution_role as": [{
                "expected_role": False,
                "direct_login": False,
                "transaction_read_only": True,
                "superuser": False,
                "can_create_database": False,
                "can_create_roles": False,
                "replication_role": False,
                "bypasses_rls": False,
                "can_create_database_objects": False,
                "can_create_public_objects": False,
                "membership_count": 0,
                "dml_relation_count": 0,
                "owned_relation_count": 0,
                "inventory_rls_enabled_relation_count": 0,
            }]
        }
    )

    @contextmanager
    def connection_factory(**_kwargs):
        yield connection

    with pytest.raises(RuntimeError, match="direct, read-only kokonut_tenant_preflight"):
        tenant_preflight.collect_inventory(connection_factory=connection_factory)

    assert any("with execution_role as" in query for query in connection.queries)
    assert not any("information_schema.columns" in query for query in connection.queries)


def test_preflight_connection_requires_dedicated_dsn_and_sanitizes_driver_error(monkeypatch):
    monkeypatch.setattr(tenant_preflight, "load_dotenv", lambda: None)
    monkeypatch.delenv("KOKONUT_TENANT_PREFLIGHT_DSN", raising=False)
    with pytest.raises(RuntimeError, match="KOKONUT_TENANT_PREFLIGHT_DSN is required"):
        tenant_preflight.get_preflight_connection()

    secret_dsn = "postgresql://preflight:secret-value@db.invalid/kokonut"
    monkeypatch.setenv("KOKONUT_TENANT_PREFLIGHT_DSN", secret_dsn)
    monkeypatch.setattr(
        tenant_preflight.psycopg2,
        "connect",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError(secret_dsn)),
    )
    with pytest.raises(RuntimeError, match="tenant preflight database connection failed") as error:
        tenant_preflight.get_preflight_connection()
    assert secret_dsn not in str(error.value)


def test_scheduled_task_preflight_validates_enabled_contracts_without_echoing_data():
    connection = _Connection(
        {
            "to_regclass('public.scheduled_task')": [{"present": True}],
            "information_schema.columns": [{"available_column_count": 3}],
            "from scheduled_task": [
                {
                    "name": "synthetic-sensitive-task-name",
                    "module_path": "services.metrics",
                    "command_args": ["--compute", "--all-locations"],
                },
                {
                    "name": "another-sensitive-name",
                    "module_path": "services.export.dataset_refresh",
                    "command_args": ["--all"],
                },
                {
                    "name": "invalid-task",
                    "module_path": "services.events",
                    "command_args": ["--cleanup"],
                },
            ],
        }
    )

    report = tenant_preflight._scheduled_task_preflight(connection)

    assert report == {
        "status": "review_required",
        "enabled_task_count": 3,
        "contract_valid_count": 1,
        "contract_rejected_count": 2,
        "known_unbounded_scope_task_count": 1,
        "enabled_tasks_without_signed_tenant_context_count": 3,
        "tenant_context_support": "not_implemented",
        "identifiers_and_arguments_emitted": False,
    }
    serialized = json.dumps(report)
    assert "synthetic-sensitive-task-name" not in serialized
    assert "another-sensitive-name" not in serialized
    assert "--cleanup" not in serialized
    assert "services.metrics" not in serialized


def test_database_readiness_requires_a_dedicated_role_before_rls():
    connection = _Connection(
        {
            "with runtime_role as": [],
            "to_regclass('public.scheduled_task')": [{"present": False}],
        }
    )

    report = tenant_preflight._database_readiness_preflight(connection)

    assert report["execution_identity_policy"] == "dedicated_read_only_preflight_role_required"
    assert report["runtime_role"]["status"] == "not_available"
    assert report["scheduled_tasks"]["status"] == "not_available"
