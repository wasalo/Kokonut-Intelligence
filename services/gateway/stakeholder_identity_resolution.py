"""Location-scoped consumer resolution for independently approved identities."""

from __future__ import annotations

from functools import partial
from typing import Callable
from uuid import UUID

from services.common.tenant_context import set_operator_tenant_context


class StakeholderIdentityResolutionInvalid(ValueError):
    """An identity resolution identifier is invalid."""


def _connection_factory() -> Callable:
    from services.common.database import get_db

    return partial(get_db, connect_timeout=3)


def _normalize_uuid(value: str, field: str) -> str:
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError, AttributeError) as exc:
        raise StakeholderIdentityResolutionInvalid(f"Invalid {field} identifier") from exc


def resolve_location_farmer_party_identity(
    operator_id: str,
    location_id: str,
    source_profile_id: str,
    *,
    connection_factory: Callable | None = None,
) -> dict | None:
    """Resolve one source only when approval and current location consent allow it."""
    operator_id = _normalize_uuid(operator_id, "operator")
    location_id = _normalize_uuid(location_id, "location")
    source_profile_id = _normalize_uuid(source_profile_id, "source profile")

    connection = (connection_factory or _connection_factory())()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '8s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
        # Tenant context takes row locks to serialize authorization against
        # grant revocation and ownership changes. The bounded SQL function is
        # STABLE; this transaction performs no persistent writes.
        set_operator_tenant_context(
            connection,
            operator_id=operator_id,
            location_id=location_id,
            resource="stakeholder_identity",
            action="resolve",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM kokonut_security.resolve_location_farmer_party_identity(
                           %s::uuid, %s::uuid
                       )""",
                (location_id, source_profile_id),
            )
            row = cursor.fetchone()
        if row is None:
            return None
        return {
            "party_id": str(row[0]),
            "resolved_at": row[1],
        }
    except Exception:
        connection.rollback()
        raise
    finally:
        try:
            connection.rollback()
        finally:
            connection.close()
