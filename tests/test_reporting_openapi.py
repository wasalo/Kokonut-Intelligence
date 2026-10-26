"""Dashboard OpenAPI contract follows the registered reporting-query model."""

from pathlib import Path

import yaml

OPENAPI_PATH = Path(__file__).resolve().parents[1] / "docs" / "openapi.yaml"


def test_dashboard_dataset_openapi_uses_registered_query_ids_only_for_writes():
    spec = yaml.safe_load(OPENAPI_PATH.read_text(encoding="utf-8"))
    schemas = spec["components"]["schemas"]

    dataset = schemas["DashboardDataset"]["properties"]
    create = schemas["DashboardDatasetCreate"]["properties"]
    update = schemas["DashboardDatasetUpdate"]["properties"]

    assert dataset["query_id"]["type"] == "string"
    assert dataset["query_sql"]["deprecated"] is True
    assert dataset["query_sql"]["readOnly"] is True
    assert "never executed" in schemas["DashboardDataset"]["description"]
    assert "query_id" in create
    assert "query_id" in update
    assert "query_sql" not in create
    assert "query_sql" not in update
