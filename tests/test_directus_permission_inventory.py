"""Static inventory regressions for the curated Directus permission seed."""

from pathlib import Path

from scripts.directus_permission_inventory import _insert_rows, build_inventory


def test_insert_parser_handles_multiline_rows_quoted_delimiters_and_comments() -> None:
    sql = """
    -- INSERT INTO directus_permissions (ignored) VALUES ('x');
    INSERT INTO directus_permissions (collection, action, permissions, validation, fields, policy)
    VALUES
      ('farm_activity', 'read', '{\"label\":\"semi; comma, ok\"}', '{}', '*', 'policy-1'),
      ('feedback', 'create', '{}', '{}', 'name,description', 'policy-2');
    /* INSERT INTO directus_permissions (ignored) VALUES ('x'); */
    """

    rows = _insert_rows(sql, "directus_permissions")

    assert rows == [
        {
            "line": 5,
            "collection": "farm_activity",
            "action": "read",
            "permissions": '{"label":"semi; comma, ok"}',
            "validation": "{}",
            "fields": "*",
            "policy": "policy-1",
        },
        {
            "line": 6,
            "collection": "feedback",
            "action": "create",
            "permissions": "{}",
            "validation": "{}",
            "fields": "name,description",
            "policy": "policy-2",
        },
    ]


def test_inventory_counts_literal_wildcard_rules_and_keeps_limits_explicit() -> None:
    root = Path(__file__).resolve().parents[1]
    inventory = build_inventory(root / "config/directus/permissions.sql", root)

    assert inventory["summary"]["literal_permission_rows"] == 175
    assert inventory["summary"]["wildcard_field_rows"] == 125
    assert inventory["summary"]["explicit_field_rows"] == 50
    assert inventory["summary"]["declared_farm_activity_rules"] == 0
    assert inventory["summary"]["update_statements"] == 4
    assert inventory["summary"]["delete_statements"] == 1
    assert inventory["summary"]["wildcard_rows_by_policy"]["Auditor Policy"] == 28
    assert "not effective deployed permission state" in inventory["limitations"][0]
    delete = next(item for item in inventory["source_mutations"] if item["operation"] == "delete")
    assert "collection = 'farm_activity'" in delete["statement"]
    assert "policy IN" in delete["statement"]

    feedback = next(
        rule
        for rule in inventory["rules"]
        if rule["policy"] == "Field Worker Policy"
        and rule["collection"] == "stakeholder_feedback"
        and rule["action"] == "read"
    )
    assert feedback["field_access"] == "wildcard"
    assert feedback["fields"] == ["*"]

