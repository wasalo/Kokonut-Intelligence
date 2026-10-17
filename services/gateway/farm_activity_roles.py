"""Explicit Gateway scope templates for the legacy farm-activity roles.

These templates are an operator provisioning aid, not roles attached to an
OIDC token. Each selected template expands into ordinary location-scoped
operator grants which can be inspected and revoked independently.
"""

from __future__ import annotations

from types import MappingProxyType

FARM_ACTIVITY_ROLE_SCOPES = MappingProxyType(
    {
        "field_worker": (
            ("farm_activity", "read"),
            ("farm_activity", "read_detail"),
            ("farm_activity", "create_draft"),
            ("farm_activity", "edit_draft"),
            ("mobile_collection_review", "read_detail"),
        ),
        "supervisor": (
            ("farm_activity", "read"),
            ("farm_activity", "read_detail"),
            ("farm_activity", "submit"),
        ),
        "manager": (
            ("farm_activity", "read"),
            ("farm_activity", "read_detail"),
            ("farm_activity", "verify"),
            ("farm_activity", "reject"),
            ("farm_activity", "rework"),
            ("farm_activity", "publish"),
            ("farm_activity", "close_exception"),
        ),
        "finance": (
            ("farm_activity", "read"),
            ("farm_activity", "read_detail"),
        ),
        "analyst": (
            ("farm_activity", "read_published"),
            ("farm_activity", "read_published_detail"),
        ),
        "auditor": (
            ("farm_activity", "read"),
            ("farm_activity", "read_detail"),
        ),
    }
)


def get_farm_activity_role_scopes(role: str) -> tuple[tuple[str, str], ...]:
    """Return the exact scope bundle for a legacy Directus role name."""
    normalized = role.strip().lower().replace(" ", "_") if isinstance(role, str) else ""
    try:
        return FARM_ACTIVITY_ROLE_SCOPES[normalized]
    except KeyError as exc:
        raise ValueError(f"Unknown farm activity role template: {role}") from exc
