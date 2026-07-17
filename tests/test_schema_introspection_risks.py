"""Tests for ER risk linting used by the schema workflow."""

from services.schema_introspection.inventory import risk_findings


def test_risk_linter_reports_polymorphism_and_embedded_relationships():
    report = {
        "polymorphic_references": [
            {"table_name": "thing", "type_column": "owner_type", "id_column": "owner_id"}
        ],
        "relationship_shaped_columns": [
            {"table_name": "thing", "column_name": "source_ids", "type": "_uuid"}
        ],
    }
    findings = risk_findings(report)
    assert findings == [
        "polymorphic reference: thing.owner_type + owner_id",
        "relationship-shaped column: thing.source_ids (_uuid)",
    ]
