"""Pure checks for the optional Directus permission snapshot summary."""

from scripts.directus_permission_snapshot import (
    MANAGED_POLICY_IDS,
    custom_permission_license_restricted,
    permission_snapshot_digest,
    permission_snapshot_query,
    summarize_permission_snapshot,
)


def test_permission_summary_counts_wildcards_and_groups_effective_rules() -> None:
    rows = [
        {
            "policy": "Analyst Policy",
            "roles": ["Analyst"],
            "collection": "field_note",
            "action": "read",
            "row_filter": {"status": {"_eq": "published"}},
            "validation": {},
            "fields": "*",
        },
        {
            "policy": "Analyst Policy",
            "roles": ["Analyst"],
            "collection": "harvest_event",
            "action": "read",
            "row_filter": {},
            "validation": {},
            "fields": ["id", "location_id"],
        },
        {
            "policy": "Manager Policy",
            "roles": ["Manager"],
            "collection": "harvest_event",
            "action": "update",
            "row_filter": {"status": {"_eq": "draft"}},
            "validation": {},
            "fields": ["status"],
        },
    ]

    summary = summarize_permission_snapshot(rows)

    assert summary["permission_rows"] == 3
    assert summary["wildcard_field_rows"] == 1
    assert summary["explicit_field_rows"] == 2
    assert summary["rows_by_policy"] == {"Analyst Policy": 2, "Manager Policy": 1}
    assert summary["rows_by_collection_action"] == {
        "field_note:read": 1,
        "harvest_event:read": 1,
        "harvest_event:update": 1,
    }
    assert len(summary["snapshot_sha256"]) == 64


def test_permission_snapshot_digest_is_canonical_for_object_key_order() -> None:
    first = [{"policy": "Manager Policy", "row_filter": {"b": 2, "a": 1}}]
    reordered = [{"row_filter": {"a": 1, "b": 2}, "policy": "Manager Policy"}]

    assert permission_snapshot_digest(first) == permission_snapshot_digest(reordered)


def test_permission_query_is_scoped_to_repository_managed_policies() -> None:
    query = permission_snapshot_query()

    assert len(MANAGED_POLICY_IDS) == 9
    assert all(policy_id in query for policy_id in MANAGED_POLICY_IDS)
    assert "public.directus_permissions" in query
    assert "public.directus_access" in query
    assert "row_filter" in query
    assert "validation" in query


def test_custom_permission_license_gate_requires_explicit_directus_restriction() -> None:
    restricted = {
        "errors": [
            {
                "message": "custom_permission_rules_enabled is a restricted resource.",
                "extensions": {"code": "FORBIDDEN"},
            }
        ]
    }

    assert custom_permission_license_restricted(403, restricted)
    assert not custom_permission_license_restricted(401, restricted)
    assert not custom_permission_license_restricted(
        403, {"errors": [{"message": "not authorized", "extensions": {"code": "FORBIDDEN"}}]}
    )
