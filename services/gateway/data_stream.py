"""Tenant-scoped Gateway commands for Data Stream writes."""

from __future__ import annotations

import re
from typing import Any, Callable, Mapping
from uuid import UUID

from services.common.tenant_context import TenantContextDenied


def create_gateway_data_stream_post(
    body: Mapping[str, Any],
    authorization: Mapping[str, Any],
    *,
    connection_factory: Callable[[], Any] | None = None,
) -> dict[str, Any]:
    """Create a draft post using DB-verified Gateway identity and tenant scope.

    The authenticated request metadata is supplied by Gateway middleware. The
    database revalidates the credential, route scope, and current location
    owner before the INSERT runs on the same transaction.
    """
    from services.common.database import get_connection
    from services.common.tenant_context import set_gateway_tenant_context
    from services.data_stream.post import create_post

    if not isinstance(body, Mapping):
        raise ValueError("request body must be an object")
    if not isinstance(authorization, Mapping):
        raise ValueError("Gateway authorization metadata is required")

    location_value = body.get("location_id")
    try:
        location_id = str(UUID(str(location_value)))
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValueError("location_id must be a UUID") from exc

    expected = {
        "resource": "data_stream_post",
        "action": "create",
    }
    if any(authorization.get(key) != value for key, value in expected.items()):
        raise ValueError("Gateway authorization does not match Data Stream create")
    try:
        authorized_location_id = str(UUID(str(authorization.get("location_id"))))
    except (TypeError, ValueError, AttributeError) as exc:
        raise TenantContextDenied("Gateway authorization has no valid location scope") from exc
    if authorized_location_id != location_id:
        raise ValueError("Gateway authorization location does not match request")
    if authorization.get("credential_type") not in {"api_key", "capability_token"}:
        raise TenantContextDenied("Gateway credential cannot establish tenant context")
    credential_hash = authorization.get("credential_hash")
    if not isinstance(credential_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", credential_hash):
        raise TenantContextDenied("Gateway credential cannot establish tenant context")

    factory = connection_factory or get_connection
    with factory() as connection:
        tenant = set_gateway_tenant_context(
            connection,
            credential_type=authorization.get("credential_type"),
            credential_hash=authorization.get("credential_hash"),
            location_id=location_id,
            resource="data_stream_post",
            action="create",
        )
        return create_post(
            connection,
            location_id=tenant.location_id,
            post_type=body.get("post_type", "monitoring_report"),
            title=body.get("title", ""),
            content=body.get("content", ""),
            created_by=tenant.actor_id,
        )
