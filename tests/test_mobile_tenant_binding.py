"""Focused migration and preflight checks for owner-bound Field Collector devices."""

from __future__ import annotations

import json
from contextlib import contextmanager
from pathlib import Path

from services.mobile import tenant_preflight

ROOT = Path(__file__).parents[1]
MIGRATION_PATH = ROOT / "schemas/postgres/391_mobile_device_tenant_binding.sql"


def test_migration_adds_nullable_immutable_owner_binding_without_backfill():
    sql = MIGRATION_PATH.read_text().lower()

    assert "alter table mobile_device_enrollment" in sql
    assert "alter table mobile_device" in sql
    assert sql.count("tenant_organization_id uuid") == 2
    assert sql.count("references organization(id) on delete restrict") == 2
    assert "new.location_id is distinct from old.location_id" in sql
    assert "new.tenant_organization_id is distinct from old.tenant_organization_id" in sql
    assert "owner.organization_id = new.tenant_organization_id" in sql
    assert "owner.revoked_at is null" in sql
    assert "tenant.status = 'active'" in sql
    assert "for share of loc, owner, tenant" in sql
    assert "update mobile_device set" not in sql
    assert "update mobile_device_enrollment set" not in sql
    assert "insert into mobile_device " not in sql
    assert "insert into mobile_device_enrollment " not in sql


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def first(self):
        return self._rows[0] if self._rows else None

    def all(self):
        return list(self._rows)


class _PreflightConnection:
    def __init__(self, location_row, unlocated_row):
        self.location_row = location_row
        self.unlocated_row = unlocated_row
        self.queries = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, sql, _params=None):
        normalized = " ".join(sql.lower().split())
        self.queries.append(normalized)
        if normalized.startswith("with required(relation_name, column_name)"):
            return _Result([{
                "required_column_count": len(tenant_preflight._REQUIRED_COLUMNS),
                "missing_columns": [],
            }])
        if "to_regprocedure(" in normalized:
            return _Result([{"present": True}])
        if "to_regclass('public.schema_migration')" in normalized:
            return _Result([{"present": False}])
        if normalized.startswith("with active_org_relationships as"):
            return _Result([self.location_row])
        if normalized.startswith("select (select count(*)::int from mobile_device"):
            return _Result([self.unlocated_row])
        if normalized.startswith("select (select count(*)::int from operator_identity)"):
            return _Result([{
                "operator_identity_count": 0,
                "enabled_operator_identity_count": 0,
                "disabled_operator_identity_count": 0,
                "active_operator_organization_membership_count": 0,
                "active_membership_for_enabled_operator_count": 0,
                "active_membership_for_disabled_operator_count": 0,
                "enabled_operators_with_active_membership_count": 0,
            }])
        return _Result([])


def test_preflight_reports_device_binding_counts_without_leaking_identifiers(monkeypatch):
    location_id = "a0000000-0000-0000-0000-000000000001"
    owner_id = "a0000000-0000-0000-0000-000000000801"
    location_row = {
        "location_id": location_id,
        "location_status": "active",
        "assigned_organization_id": owner_id,
        "active_organization_relationship_count": 1,
        "active_organization_count": 1,
        "owned_primary_organization_ids": [owner_id],
        **{field: 0 for field in tenant_preflight._COUNT_FIELDS},
        **{field: 0 for field in tenant_preflight._TENANT_BINDING_COUNT_FIELDS},
        **{field: 0 for field in tenant_preflight._OPERATOR_ACCESS_COUNT_FIELDS},
        "tenant_unbound_device_count": 1,
        "active_unbound_device_count": 1,
        "owner_mismatch_device_count": 1,
        "pending_unbound_enrollment_count": 1,
    }
    unlocated_row = {
        "mobile_device_count": 0,
        "active_unlocated_device_count": 0,
        "pending_unlocated_unbound_enrollment_count": 0,
        "mobile_collection_count": 0,
        "report_snapshot_count": 0,
        "dashboard_dataset_count": 0,
    }
    connection = _PreflightConnection(location_row, unlocated_row)

    @contextmanager
    def fake_connection(**_kwargs):
        yield connection

    monkeypatch.setattr(tenant_preflight, "get_connection", fake_connection)

    inventory = tenant_preflight.collect_inventory()

    assert inventory["inventory_status"] == "complete"
    assert inventory["tenant_binding_totals_at_locations"]["tenant_unbound_device"] == 1
    assert inventory["tenant_binding_totals_at_locations"]["active_unbound_device"] == 1
    assert inventory["tenant_binding_totals_at_locations"]["owner_mismatch_device"] == 1
    assert inventory["tenant_binding_totals_at_locations"]["pending_unbound_enrollment"] == 1
    assert inventory["locations"][0]["mobile_tenant_binding"]["tenant_unbound_device"] == 1
    assert location_id not in json.dumps(inventory)
    assert owner_id not in json.dumps(inventory)


def test_preflight_inventory_does_not_read_mobile_credential_columns():
    assert "device_token_hash" not in tenant_preflight._INVENTORY_SQL
    assert "device_token_hash" not in tenant_preflight._UNLOCATED_SQL
    assert "code_hash" not in tenant_preflight._INVENTORY_SQL
    assert "push_token" not in tenant_preflight._INVENTORY_SQL
