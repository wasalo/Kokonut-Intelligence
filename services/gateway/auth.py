"""Gateway auth — unified authentication (API key, capability token, session)."""

from __future__ import annotations

import hmac
import os

from services.common.logging import get_logger

logger = get_logger("gateway.auth")

# Role that is granted full access by design (the Directus admin token).
ADMIN_ROLE = "admin"


def verify_request(request, resource: str, action: str, location_id: str | None = None) -> dict:
    """Verify authentication for a gateway request.

    Checks (in order):
    1. Capability token (x-capability-token header) — fine-grained, resource-scoped.
    2. API key (x-api-key header) — trusted service key, scope-enforced.
    Returns a structured result with caller, scope, and capability metadata.
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
            return {
                "authenticated": True,
                "caller": result.get("holder", "cap-token"),
                "capability_token_id": result.get("token_id"),
                "resource": resource,
                "action": action,
                "location_id": location_id,
            }
        return {
            "authenticated": False,
            "reason": "invalid_capability_token",
            "resource": resource,
            "action": action,
            "location_id": location_id,
        }

    # 2. Check API key
    api_key = headers.get("x-api-key") or headers.get("api-key")
    if api_key:
        key_meta = _match_api_key(api_key)
        if key_meta is None:
            return {
                "authenticated": False,
                "reason": "invalid_api_key",
                "resource": resource,
                "action": action,
                "location_id": location_id,
            }

        # Admin role is full-access by design (Directus admin token).
        if key_meta.get("role") == ADMIN_ROLE:
            return {
                "authenticated": True,
                "caller": key_meta.get("name", "admin"),
                "resource": resource,
                "action": action,
                "location_id": location_id,
            }

        # Service/custom keys are fail-closed: the route's resource/action
        # must be explicitly permitted by the key's configured scopes.
        if _scope_allows(key_meta, resource, action):
            return {
                "authenticated": True,
                "caller": key_meta.get("name", "api-key"),
                "resource": resource,
                "action": action,
                "location_id": location_id,
            }
        return {
            "authenticated": False,
            "reason": "api_key_scope_denied",
            "resource": resource,
            "action": action,
            "location_id": location_id,
        }

    return {
        "authenticated": False,
        "reason": "credentials_required",
        "resource": resource,
        "action": action,
        "location_id": location_id,
    }


def _match_api_key(api_key: str) -> dict | None:
    """Constant-time match of an API key against the configured key set."""
    best: dict | None = None
    for candidate, meta in _get_valid_api_keys().items():
        if hmac.compare_digest(candidate, api_key):
            best = meta
            break
    return best


def _scope_allows(key_meta: dict, resource: str, action: str) -> bool:
    """Return True if the key's scopes permit the (resource, action).

    Scopes come from KOKONUT_API_KEY_SCOPES (format ``name:resource:action``,
    where ``resource`` or ``action`` may be ``*``). A key with no configured
    scopes is denied access to every non-public route (fail-closed).
    """
    scopes = key_meta.get("scopes") or []
    for scope in scopes:
        scope_resource, _, scope_action = scope.partition(":")
        if scope_resource in ("*", resource) and scope_action in ("*", action):
            return True
    return False


def _get_valid_api_keys() -> dict:
    """Load valid API keys from environment.

    Keys are looked up by value at auth time (constant-time). Each entry
    carries a ``role`` and, for non-admin keys, a ``scopes`` list built from
    ``KOKONUT_API_KEY_SCOPES`` (format ``name:resource:action[,name:resource:action]``).
    """
    keys: dict[str, dict] = {}
    # Directus admin token — full access by design.
    admin_token = os.environ.get("DIRECTUS_ADMIN_TOKEN")
    if admin_token:
        keys[admin_token] = {"name": "admin", "role": ADMIN_ROLE}

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

    # Resolve scopes by key name.
    scopes_raw = os.environ.get("KOKONUT_API_KEY_SCOPES", "")
    name_to_scopes: dict[str, list[str]] = {}
    for scope in scopes_raw.split(","):
        scope = scope.strip()
        if not scope:
            continue
        name, _, rest = scope.partition(":")
        name_to_scopes.setdefault(name.strip(), []).append(rest)

    for meta in keys.values():
        meta["scopes"] = name_to_scopes.get(meta.get("name", ""), [])

    return keys
