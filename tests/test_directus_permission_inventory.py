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

    assert inventory["summary"]["literal_permission_rows"] == 176
    assert inventory["summary"]["wildcard_field_rows"] == 122
    assert inventory["summary"]["explicit_field_rows"] == 54
    assert inventory["summary"]["declared_farm_activity_rules"] == 0
    assert inventory["summary"]["update_statements"] == 7
    assert inventory["summary"]["delete_statements"] == 1
    assert inventory["summary"]["wildcard_rows_by_policy"]["Auditor Policy"] == 26
    assert "not effective deployed permission state" in inventory["limitations"][0]
    delete = next(item for item in inventory["source_mutations"] if item["operation"] == "delete")
    assert "collection = 'farm_activity'" in delete["statement"]
    assert "policy IN" in delete["statement"]

    analyst_feedback = next(
        rule
        for rule in inventory["rules"]
        if rule["policy"] == "Analyst Policy"
        and rule["collection"] == "stakeholder_feedback"
        and rule["action"] == "read"
    )
    assert analyst_feedback["field_access"] == "explicit"
    assert analyst_feedback["fields"] == [
        "id", "location_id", "farm_id", "feedback_type", "stakeholder_group",
        "feedback_date", "sentiment", "themes", "public_summary", "evidence_maturity",
    ]

    dashboard = next(
        rule
        for rule in inventory["rules"]
        if rule["policy"] == "Auditor Policy"
        and rule["collection"] == "dashboard_dataset"
        and rule["action"] == "read"
    )
    assert dashboard["field_access"] == "explicit"
    assert "query_sql" not in dashboard["fields"]
    assert dashboard["fields"] == [
        "id", "name", "description", "dataset_type", "location_id", "query_id",
        "refresh_interval_minutes", "last_refreshed_at", "status", "metadata",
        "created_at", "updated_at", "updated_by",
    ]
    field_repair = next(
        item
        for item in inventory["source_mutations"]
        if item["operation"] == "update"
        and "collection = 'dashboard_dataset'" in item["statement"]
    )
    assert "fields = '*'" in field_repair["statement"]
    assert "query_sql" not in field_repair["statement"]

    metric_value = next(
        rule
        for rule in inventory["rules"]
        if rule["policy"] == "Auditor Policy"
        and rule["collection"] == "metric_value"
        and rule["action"] == "read"
    )
    assert metric_value["field_access"] == "explicit"
    assert metric_value["fields"] == [
        "id", "metric_id", "location_id", "period_start", "period_end",
        "value", "unit", "computation_method", "computed_at", "verified",
        "verified_at",
    ]
    assert not {"source_record_ids", "metadata", "verified_by", "verification_notes"} & set(
        metric_value["fields"]
    )
    metric_repair = next(
        item
        for item in inventory["source_mutations"]
        if item["operation"] == "update"
        and "collection = 'metric_value'" in item["statement"]
    )
    assert "fields = '*'" in metric_repair["statement"]

    certificate = next(
        rule
        for rule in inventory["rules"]
        if rule["policy"] == "Auditor Policy"
        and rule["collection"] == "retirement_certificate"
        and rule["action"] == "read"
    )
    assert certificate["field_access"] == "explicit"
    assert certificate["fields"] == [
        "id", "retirement_id", "credit_id", "credit_class_id", "credit_batch_id",
        "location_id", "certificate_number", "retired_tonnes", "vintage_year",
        "methodology", "attestation_uid", "chain", "issued_at", "status", "created_at",
    ]
    assert not {
        "beneficiary_name", "beneficiary_wallet", "retirement_reason",
        "retirement_statement", "certificate_hash", "certificate_html",
        "certificate_cid", "verification_url", "qr_code_data", "metadata", "created_by",
    } & set(certificate["fields"])

    feedback = next(
        rule
        for rule in inventory["rules"]
        if rule["policy"] == "Field Worker Policy"
        and rule["collection"] == "stakeholder_feedback"
        and rule["action"] == "read"
    )
    assert feedback["field_access"] == "wildcard"
    assert feedback["fields"] == ["*"]

