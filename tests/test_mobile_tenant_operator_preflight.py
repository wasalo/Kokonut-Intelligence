"""Aggregate-only operator access reporting in the ownership preflight."""

from __future__ import annotations

import json
from contextlib import contextmanager
from pathlib import Path

from services.mobile import tenant_preflight

ROOT = Path(__file__).parents[1]


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def first(self):
        return self._rows[0] if self._rows else None

    def all(self):
        return list(self._rows)


class _PreflightConnection:
    def __init__(self, location_row, unlocated_row, operator_row, *, function_present=True):
        self.location_row = location_row
        self.unlocated_row = unlocated_row
        self.operator_row = operator_row
        self.function_present = function_present
        self.queries = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, sql, _params=None):
        normalized = " ".join(sql.lower().split())
        self.queries.append(normalized)
        if normalized.startswith("with execution_role as"):
            return _Result([{
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
            }])
        if normalized.startswith("with required(relation_name, column_name)"):
            return _Result([{
                "required_column_count": len(tenant_preflight._REQUIRED_COLUMNS),
                "missing_columns": [],
            }])
        if "to_regprocedure(" in normalized:
            return _Result([{"present": self.function_present}])
        if "to_regclass('public.schema_migration')" in normalized:
            return _Result([{"present": False}])
        if normalized.startswith("with active_org_relationships as"):
            return _Result([self.location_row])
        if normalized.startswith("select (select count(*)::int from mobile_device"):
            return _Result([self.unlocated_row])
        if normalized.startswith("select (select count(*)::int from operator_identity)"):
            return _Result([self.operator_row])
        return _Result([])


def _location_row():
    owner_id = "a0000000-0000-0000-0000-000000000801"
    row = {
        "location_id": "a0000000-0000-0000-0000-000000000001",
        "location_status": "active",
        "assigned_organization_id": owner_id,
        "active_organization_relationship_count": 1,
        "active_organization_count": 1,
        "owned_primary_organization_ids": [owner_id],
        **{field: 0 for field in tenant_preflight._COUNT_FIELDS},
        **{field: 0 for field in tenant_preflight._TENANT_BINDING_COUNT_FIELDS},
    }
    row.update({
        "active_operator_grant_count": 4,
        "active_legacy_operator_grant_count": 1,
        "active_tenant_qualified_operator_grant_count": 3,
        "authorized_tenant_qualified_operator_grant_count": 1,
        "invalid_tenant_qualified_operator_grant_count": 2,
        "operators_with_active_legacy_grant_count": 1,
        "operators_with_authorized_tenant_grant_count": 1,
    })
    return row


def _unlocated_row():
    return {
        "mobile_device_count": 0,
        "active_unlocated_device_count": 0,
        "pending_unlocated_unbound_enrollment_count": 0,
        "mobile_collection_count": 0,
        "report_snapshot_count": 0,
        "dashboard_dataset_count": 0,
    }


def _operator_row():
    return {
        "operator_identity_count": 3,
        "enabled_operator_identity_count": 2,
        "disabled_operator_identity_count": 1,
        "active_operator_organization_membership_count": 2,
        "active_membership_for_enabled_operator_count": 1,
        "active_membership_for_disabled_operator_count": 1,
        "enabled_operators_with_active_membership_count": 1,
    }


def _fake_connection(connection):
    @contextmanager
    def factory(**_kwargs):
        yield connection

    return factory


def test_preflight_reports_aggregate_operator_access_without_identifiers(monkeypatch):
    location_id = "a0000000-0000-0000-0000-000000000001"
    owner_id = "a0000000-0000-0000-0000-000000000801"
    connection = _PreflightConnection(_location_row(), _unlocated_row(), _operator_row())
    inventory = tenant_preflight.collect_inventory(connection_factory=_fake_connection(connection))

    assert inventory["database_readiness"]["execution_identity"]["status"] == "ready"
    assert inventory["database_readiness"]["execution_identity"]["role_name_emitted"] is False
    assert inventory["database_readiness"]["execution_identity_policy"] == (
        "dedicated_read_only_preflight_role_required"
    )
    access = inventory["locations"][0]["operator_access"]
    assert access["active_operator_grant"] == 4
    assert access["active_legacy_operator_grant"] == 1
    assert access["active_tenant_qualified_operator_grant"] == 3
    assert access["authorized_tenant_qualified_operator_grant"] == 1
    assert access["invalid_tenant_qualified_operator_grant"] == 2
    assert inventory["operator_affiliations_and_grants"]["identity_and_membership_counts"] == _operator_row()
    assert inventory["operator_affiliations_and_grants"]["identifiers_emitted"] is False
    assert location_id not in json.dumps(inventory)
    assert owner_id not in json.dumps(inventory)
    assert any("operator_scope_grant_allows" in query for query in connection.queries)


def test_missing_authorization_function_stops_before_inventory_queries(monkeypatch):
    connection = _PreflightConnection(
        _location_row(), _unlocated_row(), _operator_row(), function_present=False
    )
    inventory = tenant_preflight.collect_inventory(connection_factory=_fake_connection(connection))

    assert inventory["inventory_status"] == "schema_incomplete"
    assert inventory["schema_coverage"]["available_function_count"] == 0
    assert inventory["schema_coverage"]["missing_functions"] == [
        "public.operator_scope_grant_allows(uuid,text,text,uuid)"
    ]
    assert not any(query.startswith("with active_org_relationships as") for query in connection.queries)
    assert not any(query.startswith("select (select count(*)::int from operator_identity)") for query in connection.queries)


def test_operator_inventory_sql_uses_shared_authorization_predicate_and_no_identity_fields():
    sql = tenant_preflight._INVENTORY_SQL.lower()
    global_sql = tenant_preflight._OPERATOR_GLOBAL_SQL.lower()

    assert "operator_scope_grant_allows(" in sql
    assert "grant_row.organization_id is null" in sql
    assert "grant_row.organization_id is not null" in sql
    assert "display_name" not in global_sql
    assert "email" not in global_sql
    assert "subject" not in global_sql
    assert "issuer" not in global_sql
    assert "select membership.operator_id" not in global_sql
