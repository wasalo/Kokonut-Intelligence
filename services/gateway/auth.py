"""Gateway auth — unified authentication (API key, capability token, session)."""

from __future__ import annotations

import os
from typing import Any

from services.common.logging import get_logger

logger = get_logger("gateway.auth")


def verify_request(request, resource: str, action: str, location_id: str | None = None) -> dict:
    """Verify authentication for a gateway request.

    Checks (in order):
    1. Capability token (x-capability-token header)
    2. API key (x-api-key header)
    Returns dict with 'authenticated' bool and optional 'caller' and 'reason'.
    """
    headers = dict(request.headers)

    # 1. Check capability token
    cap_token = headers.get("x-capability-token") or headers.get("capability-token")
    if cap_token:
        from services.security.capabilities import CapabilityManager
        manager = CapabilityManager()
        result = manager.verify(
            cap_token,
            resource=resource,
            action=action,
            location_id=location_id,
        )
        if result:
            return {"authenticated": True, "caller": result.get("holder", "cap-token")}
        return {"authenticated": False, "reason": "invalid_capability_token"}

    # 2. Check API key
    api_key = headers.get("x-api-key") or headers.get("api-key")
    if api_key:
        valid_keys = _get_valid_api_keys()
        if api_key in valid_keys:
            caller = valid_keys[api_key].get("name", "api-key")
            return {"authenticated": True, "caller": caller}
        return {"authenticated": False, "reason": "invalid_api_key"}

    return {"authenticated": False, "reason": "credentials_required"}


def _get_valid_api_keys() -> dict:
    """Load valid API keys from environment."""
    keys = {}
    # Directus admin token
    admin_token = os.environ.get("DIRECTUS_ADMIN_TOKEN")
    if admin_token:
        keys[admin_token] = {"name": "admin", "role": "admin"}

    # gRPC API key
    grpc_key = os.environ.get("GRPC_API_KEY")
    if grpc_key:
        keys[grpc_key] = {"name": "grpc-service", "role": "service"}

    # Custom API keys (comma-separated format: key:name)
    custom_keys = os.environ.get("KOKONUT_API_KEYS", "")
    for entry in custom_keys.split(","):
        if ":" in entry:
            key, name = entry.split(":", 1)
            keys[key.strip()] = {"name": name.strip(), "role": "custom"}

    return keys
