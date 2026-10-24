"""Canonical helpers for disposable Directus effective permission snapshots."""

from __future__ import annotations

import hashlib
import json

MANAGED_POLICY_IDS = (
    "b1000000-0000-0000-0000-000000000001",
    "b1000000-0000-0000-0000-000000000002",
    "b1000000-0000-0000-0000-000000000003",
    "b1000000-0000-0000-0000-000000000004",
    "b1000000-0000-0000-0000-000000000005",
    "b1000000-0000-0000-0000-000000000006",
    "b1000000-0000-0000-0000-000000000007",
    "b1000000-0000-0000-0000-000000000008",
    "b1000000-0000-0000-0000-000000000009",
)


def permission_snapshot_digest(rows: list[dict]) -> str:
    serialized = json.dumps(rows, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def custom_permission_license_restricted(status: int, payload: dict | str) -> bool:
    if status != 403 or not isinstance(payload, dict):
        return False
    errors = payload.get("errors")
    if not isinstance(errors, list):
        return False
    return any(
        isinstance(error, dict)
        and isinstance(error.get("message"), str)
        and "custom_permission_rules_enabled" in error["message"]
        for error in errors
    )


def summarize_permission_snapshot(rows: list[dict]) -> dict[str, object]:
    by_policy: dict[str, int] = {}
    by_collection_action: dict[str, int] = {}
    wildcard_rows = 0
    for row in rows:
        policy = str(row["policy"])
        collection_action = f"{row['collection']}:{row['action']}"
        by_policy[policy] = by_policy.get(policy, 0) + 1
        by_collection_action[collection_action] = by_collection_action.get(collection_action, 0) + 1
        if row["fields"] in ("*", ["*"]):
            wildcard_rows += 1
    return {
        "permission_rows": len(rows),
        "wildcard_field_rows": wildcard_rows,
        "explicit_field_rows": len(rows) - wildcard_rows,
        "rows_by_policy": dict(sorted(by_policy.items())),
        "rows_by_collection_action": dict(sorted(by_collection_action.items())),
        "snapshot_sha256": permission_snapshot_digest(rows),
    }


def permission_snapshot_query() -> str:
    policy_ids = ", ".join(f"'{policy_id}'" for policy_id in MANAGED_POLICY_IDS)
    return f"""
        SELECT COALESCE(
            jsonb_agg(
                jsonb_build_object(
                    'policy', policy.name,
                    'roles', COALESCE((
                        SELECT jsonb_agg(role.name ORDER BY role.name)
                          FROM public.directus_access AS access
                          JOIN public.directus_roles AS role ON role.id = access.role
                         WHERE access.policy = policy.id
                    ), '[]'::jsonb),
                    'collection', permission.collection,
                    'action', permission.action,
                    'row_filter', permission.permissions,
                    'validation', permission.validation,
                    'fields', permission.fields
                ) ORDER BY policy.name, permission.collection,
                           permission.action, permission.id
            ),
            '[]'::jsonb
        )::text
          FROM public.directus_permissions AS permission
          JOIN public.directus_policies AS policy ON policy.id = permission.policy
         WHERE policy.id IN ({policy_ids})
    """
