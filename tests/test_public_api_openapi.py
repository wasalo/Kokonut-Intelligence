"""Regression checks for the intentionally public native API snapshot."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.export_public_api_openapi import build_public_api_spec

ROOT = Path(__file__).resolve().parents[1]


def test_checked_in_openapi_snapshot_matches_only_public_read_routes() -> None:
    spec = build_public_api_spec()
    checked_in = json.loads(
        (ROOT / "docs/refactor/native-public-api-v1.openapi.json").read_text(
            encoding="utf-8"
        )
    )

    assert spec == checked_in
    assert "/api/v1/governance/baal/config" not in spec["paths"]
    assert "/api/v1/governance/baal/proposals" not in spec["paths"]
    drivers = spec["paths"]["/api/v1/drivers"]["get"]
    assert drivers["operationId"] == "listPublicDriversV1"
    assert drivers["x-kokonut-policy"] == {
        "resource": "driver",
        "action": "read",
        "public": True,
        "location_scoped": False,
    }
    driver_parameters = {
        parameter["name"]: parameter["schema"]
        for parameter in drivers["parameters"]
    }
    assert {
        key: driver_parameters["limit"][key]
        for key in ("type", "minimum", "maximum", "default")
    } == {"type": "integer", "minimum": 1, "maximum": 50, "default": 50}
    assert {
        key: driver_parameters["offset"][key]
        for key in ("type", "minimum", "maximum", "default")
    } == {"type": "integer", "minimum": 0, "maximum": 5000, "default": 0}
    driver_schema = spec["components"]["schemas"]["PublicDriverCatalogEntry"]
    assert set(driver_schema["properties"]) == {
        "driver_name",
        "driver_version",
        "driver_type",
    }
    assert set(spec["paths"]["/api/v1/drivers"]) == {"get"}
    for operations in spec["paths"].values():
        assert set(operations) == {"get"}
        policy = operations["get"]["x-kokonut-policy"]
        assert policy["public"] is True
        assert policy["action"] == "read"
