"""Database calls for the authenticated Control Plane location setup flow."""

from __future__ import annotations

import json
from collections.abc import Callable
from uuid import UUID


def list_location_setup_organizations(
    session_token_hash: str, *, connection_factory: Callable
) -> list[dict]:
    """Return the bounded active organization choices for an authorized setup operator."""
    connection = connection_factory()
    try:
        with connection.cursor() as cursor:
            # The security-definer capability check locks the active operator
            # session and identity to serialize reads against revocation.
            # PostgreSQL rejects that SELECT FOR UPDATE in a read-only txn;
            # this path still performs no business-data writes.
            cursor.execute("SET LOCAL statement_timeout = '5s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
            cursor.execute(
                """SELECT id, org_key, name
                     FROM kokonut_security.list_location_setup_organizations(%s::text)""",
                (session_token_hash,),
            )
            rows = cursor.fetchall()
        connection.commit()
        return [
            {"id": str(row[0]), "org_key": row[1], "name": row[2]}
            for row in rows
        ]
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def list_location_setup_locations(
    session_token_hash: str,
    organization_id: str,
    *,
    connection_factory: Callable,
) -> list[dict]:
    """Return active, verified locations already owned by the selected tenant."""
    normalized_organization_id = str(UUID(organization_id))
    connection = connection_factory()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '5s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
            cursor.execute(
                """SELECT id, name, slug, country, region, active_farm_count
                     FROM kokonut_security.list_location_setup_locations(%s::text, %s::uuid)""",
                (session_token_hash, normalized_organization_id),
            )
            rows = cursor.fetchall()
        connection.commit()
        return [
            {
                "id": str(row[0]),
                "name": row[1],
                "slug": row[2],
                "country": row[3],
                "region": row[4],
                "active_farm_count": int(row[5]),
            }
            for row in rows
        ]
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def create_operator_farm_for_existing_location(
    session_token_hash: str,
    organization_id: str,
    location_id: str,
    farm: dict,
    owner_decision_reference: str,
    *,
    connection_factory: Callable,
) -> dict:
    """Create a satellite farm under a verified existing location."""
    normalized_organization_id = str(UUID(organization_id))
    normalized_location_id = str(UUID(location_id))
    connection = connection_factory()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '15s'")
            cursor.execute("SET LOCAL lock_timeout = '5s'")
            cursor.execute(
                """SELECT kokonut_security.create_operator_farm_for_location(
                           %s::text, %s::uuid, %s::uuid, %s::jsonb, %s
                       )""",
                (
                    session_token_hash,
                    normalized_organization_id,
                    normalized_location_id,
                    json.dumps(farm, separators=(",", ":")),
                    owner_decision_reference,
                ),
            )
            row = cursor.fetchone()
        if row is None or not isinstance(row[0], dict):
            raise RuntimeError("existing-location farm setup did not return a result")
        connection.commit()
        return row[0]
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def create_operator_location_setup(
    session_token_hash: str,
    organization_id: str,
    location: dict,
    farm: dict,
    owner_decision_reference: str,
    *,
    connection_factory: Callable,
) -> dict:
    """Create a tenant-qualified location/farm and its bounded starter scopes."""
    normalized_organization_id = str(UUID(organization_id))
    connection = connection_factory()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '15s'")
            cursor.execute("SET LOCAL lock_timeout = '5s'")
            cursor.execute(
                """SELECT kokonut_security.create_operator_location_setup(
                           %s::text, %s::uuid, %s::jsonb, %s::jsonb, %s
                       )""",
                (
                    session_token_hash,
                    normalized_organization_id,
                    json.dumps(location, separators=(",", ":")),
                    json.dumps(farm, separators=(",", ":")),
                    owner_decision_reference,
                ),
            )
            row = cursor.fetchone()
        if row is None or not isinstance(row[0], dict):
            raise RuntimeError("location setup did not return a result")
        connection.commit()
        return row[0]
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
