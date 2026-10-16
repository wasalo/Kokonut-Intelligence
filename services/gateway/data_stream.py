"""Tenant-scoped Gateway commands for Data Stream operations."""

from __future__ import annotations

import re
from typing import Any, Callable, Mapping
from uuid import UUID

from services.common.tenant_context import TenantContextDenied

_POST_READ_COLUMNS = """
    id, location_id, post_type, title, content, visibility, status,
    is_anchored, attestation_uid, chain, anchored_at, content_hash,
    created_at, created_by
"""


def _validated_gateway_scope(
    authorization: Mapping[str, Any],
    *,
    location_value: Any,
    action: str,
) -> str:
    if not isinstance(authorization, Mapping):
        raise ValueError("Gateway authorization metadata is required")

    try:
        location_id = str(UUID(str(location_value)))
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValueError("location_id must be a UUID") from exc

    expected = {"resource": "data_stream_post", "action": action}
    if any(authorization.get(key) != value for key, value in expected.items()):
        raise ValueError(f"Gateway authorization does not match Data Stream {action}")
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
    return location_id


def _set_data_stream_context(connection, authorization, location_id, action):
    from services.common.tenant_context import set_gateway_tenant_context

    tenant = set_gateway_tenant_context(
        connection,
        credential_type=authorization.get("credential_type"),
        credential_hash=authorization.get("credential_hash"),
        location_id=location_id,
        resource="data_stream_post",
        action=action,
    )
    if tenant.location_id != location_id:
        raise TenantContextDenied("Database returned a different Data Stream location")
    return tenant


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
    from services.data_stream.post import create_post

    if not isinstance(body, Mapping):
        raise ValueError("request body must be an object")
    location_id = _validated_gateway_scope(
        authorization,
        location_value=body.get("location_id"),
        action="create",
    )

    factory = connection_factory or get_connection
    with factory() as connection:
        tenant = _set_data_stream_context(connection, authorization, location_id, "create")
        return create_post(
            connection,
            location_id=tenant.location_id,
            post_type=body.get("post_type", "monitoring_report"),
            title=body.get("title", ""),
            content=body.get("content", ""),
            created_by=tenant.actor_id,
        )


def list_gateway_data_stream_posts(
    location_id: str,
    authorization: Mapping[str, Any],
    *,
    query_text: str | None = None,
    limit: int = 20,
    offset: int = 0,
    connection_factory: Callable[[], Any] | None = None,
) -> list[dict[str, Any]]:
    """List or search posts after DB verification of the exact tenant read grant.

    The query is always location-qualified and returns a fixed projection. In
    particular, source lineage, arbitrary metadata, evidence URLs, and file
    identifiers are not exposed by this endpoint.
    """
    from services.common.database import get_connection

    normalized_location_id = _validated_gateway_scope(
        authorization,
        location_value=location_id,
        action="read",
    )
    if isinstance(query_text, str):
        query_text = query_text.strip() or None
    elif query_text is not None:
        raise ValueError("q must be a string")
    if query_text is not None and len(query_text) > 200:
        raise ValueError("q must be at most 200 characters")
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
        raise ValueError("limit must be an integer between 1 and 100")
    if isinstance(offset, bool) or not isinstance(offset, int) or not 0 <= offset <= 5000:
        raise ValueError("offset must be an integer between 0 and 5000")

    query_filter = ""
    order_by = "created_at DESC"
    params: dict[str, Any] = {
        "location_id": normalized_location_id,
        "limit": limit,
        "offset": offset,
    }
    if query_text is not None:
        query_filter = " AND content_search @@ plainto_tsquery('english', :query)"
        order_by = "search_rank DESC, created_at DESC"
        params["query"] = query_text
        search_rank = "ts_rank(content_search, plainto_tsquery('english', :query))"
    else:
        search_rank = "NULL::REAL"

    sql = (
        f"SELECT {_POST_READ_COLUMNS}, {search_rank} AS search_rank "
        "FROM data_stream_post "
        "WHERE location_id = :location_id"
        f"{query_filter} "
        f"ORDER BY {order_by} LIMIT :limit OFFSET :offset"
    )
    factory = connection_factory or get_connection
    with factory() as connection:
        _set_data_stream_context(connection, authorization, normalized_location_id, "read")
        result = connection.execute(connection.text(sql), params)
        return [dict(row) for row in result.mappings()]
