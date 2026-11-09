"""Database calls for the authenticated Control Plane location setup flow."""

from __future__ import annotations

import json
from collections.abc import Callable
from uuid import UUID


def list_location_setup_organizations(
    operator_id: str, *, connection_factory: Callable
) -> list[dict]:
    """Return the bounded active organization choices for an authorized setup operator."""
    normalized_operator_id = str(UUID(operator_id))
    connection = connection_factory()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION READ ONLY")
            cursor.execute("SET LOCAL statement_timeout = '5s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
            cursor.execute(
                """SELECT id, org_key, name
                     FROM kokonut_security.list_location_setup_organizations(%s::uuid)""",
                (normalized_operator_id,),
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


def create_operator_location_setup(
    operator_id: str,
    organization_id: str,
    location: dict,
    farm: dict,
    owner_decision_reference: str,
    *,
    connection_factory: Callable,
) -> dict:
    """Create a tenant-qualified location/farm and its bounded starter scopes."""
    normalized_operator_id = str(UUID(operator_id))
    normalized_organization_id = str(UUID(organization_id))
    connection = connection_factory()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '15s'")
            cursor.execute("SET LOCAL lock_timeout = '5s'")
            cursor.execute(
                """SELECT kokonut_security.create_operator_location_setup(
                           %s::uuid, %s::uuid, %s::jsonb, %s::jsonb, %s
                       )""",
                (
                    normalized_operator_id,
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
