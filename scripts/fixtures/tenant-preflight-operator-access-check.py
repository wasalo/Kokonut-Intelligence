"""Verify aggregate tenant-preflight operator counts on an isolated migrated DB.

Run only against a disposable database after the ordered schema migrations have
been applied. This fixture inserts synthetic rows and removes them in a finally
block; it does not contact candidate or legacy deployments.
"""

from __future__ import annotations

import json
from pathlib import Path

import psycopg2

from services.common.db import PG_DB, PG_HOST, PG_PASSWORD, PG_PORT, PG_USER
from services.mobile.tenant_preflight import collect_inventory

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_FIXTURE = ROOT / "tests/fixtures/tenant_preflight_operator_access_schema.sql"
TENANT_GRANT_MIGRATION = ROOT / "schemas/postgres/388_tenant_aware_operator_grants.sql"
DEVICE_BINDING_MIGRATION = ROOT / "schemas/postgres/391_mobile_device_tenant_binding.sql"
LOCATION_ID = "a0000000-0000-0000-0000-000000000901"
OWNER_ORG_ID = "a0000000-0000-0000-0000-000000000911"
PARTNER_ORG_ID = "a0000000-0000-0000-0000-000000000912"
OPERATOR_IDS = {
    "owner": "a0000000-0000-0000-0000-000000000921",
    "partner": "a0000000-0000-0000-0000-000000000922",
    "unaffiliated": "a0000000-0000-0000-0000-000000000923",
    "disabled": "a0000000-0000-0000-0000-000000000924",
}


def _connect():
    return psycopg2.connect(
        host=PG_HOST,
        port=PG_PORT,
        dbname=PG_DB,
        user=PG_USER,
        password=PG_PASSWORD,
        connect_timeout=5,
    )


def _remove_fixture(conn):
    with conn.cursor() as cur:
        cur.execute("DELETE FROM operator_scope_grant WHERE location_id = %s", (LOCATION_ID,))
        cur.execute("DELETE FROM location_organization_share WHERE location_id = %s", (LOCATION_ID,))
        cur.execute(
            "DELETE FROM operator_organization_membership WHERE operator_id = ANY(%s::uuid[])",
            (list(OPERATOR_IDS.values()),),
        )
        cur.execute(
            "DELETE FROM location_tenant_owner_verification WHERE location_id = %s",
            (LOCATION_ID,),
        )
        cur.execute("DELETE FROM organization_member WHERE location_id = %s", (LOCATION_ID,))
        cur.execute("DELETE FROM location WHERE id = %s", (LOCATION_ID,))
        cur.execute(
            "DELETE FROM organization WHERE id = ANY(%s::uuid[])",
            ([OWNER_ORG_ID, PARTNER_ORG_ID],),
        )
        cur.execute(
            "DELETE FROM operator_identity WHERE id = ANY(%s::uuid[])",
            (list(OPERATOR_IDS.values()),),
        )
    conn.commit()


def _fixture_row_counts(conn):
    with conn.cursor() as cur:
        cur.execute(
            """SELECT
                   (SELECT COUNT(*) FROM operator_scope_grant WHERE location_id = %s),
                   (SELECT COUNT(*) FROM location_organization_share WHERE location_id = %s),
                   (SELECT COUNT(*) FROM operator_organization_membership
                     WHERE operator_id = ANY(%s::uuid[])),
                   (SELECT COUNT(*) FROM location_tenant_owner_verification
                     WHERE location_id = %s),
                   (SELECT COUNT(*) FROM organization_member WHERE location_id = %s),
                   (SELECT COUNT(*) FROM location WHERE id = %s),
                   (SELECT COUNT(*) FROM organization WHERE id = ANY(%s::uuid[])),
                   (SELECT COUNT(*) FROM operator_identity WHERE id = ANY(%s::uuid[]))""",
            (
                LOCATION_ID,
                LOCATION_ID,
                list(OPERATOR_IDS.values()),
                LOCATION_ID,
                LOCATION_ID,
                LOCATION_ID,
                [OWNER_ORG_ID, PARTNER_ORG_ID],
                list(OPERATOR_IDS.values()),
            ),
        )
        row = cur.fetchone()
    names = (
        "operator_grants",
        "location_shares",
        "operator_memberships",
        "owner_verifications",
        "organization_members",
        "locations",
        "organizations",
        "operator_identities",
    )
    return dict(zip(names, row, strict=True))


def main() -> int:
    conn = _connect()
    schema_ready = False
    evidence = None
    remaining = None
    try:
        with conn.cursor() as cur:
            cur.execute(SCHEMA_FIXTURE.read_text())
            cur.execute(TENANT_GRANT_MIGRATION.read_text())
            cur.execute(DEVICE_BINDING_MIGRATION.read_text())
        conn.commit()
        schema_ready = True
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO organization (id, org_key, name, org_type)
                   VALUES (%s, 'tenant-preflight-owner-fixture', 'Owner fixture', 'nonprofit'),
                          (%s, 'tenant-preflight-partner-fixture', 'Partner fixture', 'nonprofit')""",
                (OWNER_ORG_ID, PARTNER_ORG_ID),
            )
            cur.execute(
                """INSERT INTO location (id, name, slug, status, organization_id)
                   VALUES (%s, 'Preflight fixture', 'tenant-preflight-fixture', 'active', %s)""",
                (LOCATION_ID, OWNER_ORG_ID),
            )
            cur.execute(
                """INSERT INTO organization_member
                   (organization_id, location_id, membership_type, role, status, metadata)
                   VALUES (%s, %s, 'owned', 'primary', 'active',
                           '{"ownership_reconciliation":"owner_confirmed"}'::jsonb)""",
                (OWNER_ORG_ID, LOCATION_ID),
            )
            cur.execute(
                """INSERT INTO location_tenant_owner_verification
                   (location_id, organization_id, decision_reference, confirmed_by)
                   VALUES (%s, %s, 'tenant-preflight-fixture-owner', 'isolated fixture')""",
                (LOCATION_ID, OWNER_ORG_ID),
            )
            for key, operator_id in OPERATOR_IDS.items():
                cur.execute(
                    """INSERT INTO operator_identity
                       (id, issuer, subject, enabled)
                       VALUES (%s, 'https://tenant-preflight.example', %s, %s)""",
                    (operator_id, f"synthetic-{key}", key != "disabled"),
                )
            cur.execute(
                """INSERT INTO operator_organization_membership
                   (operator_id, organization_id, membership_role, granted_by)
                   VALUES (%s, %s, 'tenant_admin', 'isolated fixture'),
                          (%s, %s, 'operator', 'isolated fixture'),
                          (%s, %s, 'operator', 'isolated fixture')""",
                (
                    OPERATOR_IDS["owner"], OWNER_ORG_ID,
                    OPERATOR_IDS["partner"], PARTNER_ORG_ID,
                    OPERATOR_IDS["disabled"], OWNER_ORG_ID,
                ),
            )
            cur.execute(
                """INSERT INTO location_organization_share
                   (location_id, organization_id, granted_by_operator_id, reason)
                   VALUES (%s, %s, %s, 'synthetic preflight acceptance')""",
                (LOCATION_ID, PARTNER_ORG_ID, OPERATOR_IDS["owner"]),
            )
            cur.execute(
                """INSERT INTO operator_scope_grant
                   (operator_id, resource, action, location_id, granted_by, organization_id)
                   VALUES (%s, 'mobile_collection_review', 'read', %s, 'fixture', %s),
                          (%s, 'mobile_collection_review', 'review', %s, 'fixture', %s),
                          (%s, 'mobile_collection_review', 'detail', %s, 'fixture', %s),
                          (%s, 'mobile_collection_review', 'inventory', %s, 'fixture', %s),
                          (%s, 'mobile_collection_review', 'legacy_read', %s, 'fixture', NULL)""",
                (
                    OPERATOR_IDS["owner"], LOCATION_ID, OWNER_ORG_ID,
                    OPERATOR_IDS["partner"], LOCATION_ID, PARTNER_ORG_ID,
                    OPERATOR_IDS["unaffiliated"], LOCATION_ID, OWNER_ORG_ID,
                    OPERATOR_IDS["disabled"], LOCATION_ID, OWNER_ORG_ID,
                    OPERATOR_IDS["owner"], LOCATION_ID,
                ),
            )
        conn.commit()

        inventory = collect_inventory(LOCATION_ID)
        location_access = inventory["locations"][0]["operator_access"]
        global_access = inventory["operator_affiliations_and_grants"][
            "identity_and_membership_counts"
        ]
        expected_location = {
            "active_operator_grant": 5,
            "active_legacy_operator_grant": 1,
            "active_tenant_qualified_operator_grant": 4,
            "authorized_tenant_qualified_operator_grant": 2,
            "invalid_tenant_qualified_operator_grant": 2,
            "operators_with_active_legacy_grant": 1,
            "operators_with_authorized_tenant_grant": 2,
        }
        expected_global = {
            "operator_identity_count": 4,
            "enabled_operator_identity_count": 3,
            "disabled_operator_identity_count": 1,
            "active_operator_organization_membership_count": 3,
            "active_membership_for_enabled_operator_count": 2,
            "active_membership_for_disabled_operator_count": 1,
            "enabled_operators_with_active_membership_count": 2,
        }
        if location_access != expected_location or global_access != expected_global:
            raise AssertionError("aggregate tenant preflight counts did not match the synthetic fixture")
        if inventory["operator_affiliations_and_grants"]["identifiers_emitted"] is not False:
            raise AssertionError("operator inventory claims to emit identity identifiers")
        serialized = json.dumps(inventory)
        if LOCATION_ID in serialized or OWNER_ORG_ID in serialized or any(
            operator_id in serialized for operator_id in OPERATOR_IDS.values()
        ):
            raise AssertionError("aggregate tenant preflight output leaked a synthetic identifier")

        evidence = {
            "status": "passed",
            "fixture": "synthetic only",
            "per_location_counts": location_access,
            "database_wide_identity_and_membership_counts": global_access,
            "raw_identifiers_emitted": False,
        }
    finally:
        if schema_ready:
            try:
                conn.rollback()
                _remove_fixture(conn)
                remaining = _fixture_row_counts(conn)
                if any(remaining.values()):
                    raise AssertionError("synthetic tenant preflight rows remain after cleanup")
            finally:
                conn.close()
        else:
            conn.close()

    evidence["synthetic_rows_removed"] = True
    evidence["synthetic_row_counts_after_cleanup"] = {
        name: int(count) for name, count in remaining.items()
    }
    print(json.dumps(evidence, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
