"""Strict success response contract for landscape summary reads."""

from types import SimpleNamespace
from uuid import uuid4

import pytest

pytest.importorskip("fastapi")
from fastapi import APIRouter, FastAPI  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

from services.gateway.landscape_conservation_routes import (  # noqa: E402
    register_landscape_conservation_routes,
)


def _landscape_payload(location_id):
    return {
        "location_id": location_id,
        "habitats": [{
            "habitat_type": "riparian",
            "status": "active",
            "biodiversity_value": "high",
            "record_count": 2,
            "total_area_ha": 1.25,
        }],
        "corridors": [{
            "condition": "good",
            "status": "active",
            "record_count": 1,
            "total_length_m": 120.0,
            "mean_width_m": 4.5,
        }],
        "hedgerows": [{
            "condition": "fair",
            "status": "active",
            "record_count": 3,
            "total_length_m": 90.0,
            "mean_height_m": 1.8,
        }],
        "verified_buffer_checks": [{
            "compliant": True,
            "erosion_observed": False,
            "record_count": 2,
            "first_check_date": "2026-02-01",
            "last_check_date": "2026-03-01",
        }],
        "verified_assessments": {
            "assessment_count": 2,
            "mean_species_richness": 18.5,
            "mean_shannon_index": 1.2,
            "mean_habitat_diversity_index": 1.5,
            "mean_connectivity_score": 6.5,
            "mean_overall_score": 7.0,
            "first_assessment_date": "2026-01-01",
            "last_assessment_date": "2026-04-01",
        },
        "dashboard_calculations": {
            "active_habitats": {
                "zone_count": 2,
                "total_area_ha": 1.25,
                "critical_habitats": 0,
                "high_value_habitats": 2,
            },
            "active_corridors": {
                "corridor_count": 1,
                "healthy_corridors": 1,
                "total_length_m": 120.0,
                "mean_width_m": 4.5,
            },
            "verified_buffer_checks": {
                "total_checks": 2,
                "compliant_checks": 2,
                "compliance_pct": 100.0,
                "erosion_incidents": 0,
            },
            "legacy_connectivity_ratio_pct": 50.0,
        },
    }


def _landscape_app(provider):
    app = FastAPI()
    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_landscape_conservation_routes(
        router, provider, run_in_threadpool, SimpleNamespace(Error=Exception)
    )
    app.include_router(router)

    @app.middleware("http")
    async def add_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=str(uuid4()))
        )
        return await call_next(request)

    return app


def test_landscape_success_schema_is_published_and_bounded():
    app = _landscape_app(object())
    operation = app.openapi()["paths"][
        "/operator/api/landscape/{location_id}/summary"
    ]["get"]
    assert operation["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/LandscapeSummaryResponse"
    }

    schemas = app.openapi()["components"]["schemas"]
    for name in (
        "LandscapeSummaryResponse",
        "LandscapeHabitatAggregate",
        "LandscapeCorridorAggregate",
        "LandscapeHedgerowAggregate",
        "LandscapeBufferCheckAggregate",
        "VerifiedLandscapeAssessments",
        "LandscapeDashboardCalculations",
    ):
        assert schemas[name]["additionalProperties"] is False
    properties = schemas["LandscapeSummaryResponse"]["properties"]
    assert properties["habitats"]["maxItems"] == 200
    assert properties["corridors"]["maxItems"] == 30
    assert properties["hedgerows"]["maxItems"] == 25
    assert properties["verified_buffer_checks"]["maxItems"] == 9


def test_landscape_route_returns_only_the_validated_projection(monkeypatch):
    location_id = str(uuid4())
    payload = _landscape_payload(location_id)
    monkeypatch.setattr(
        "services.gateway.landscape_conservation_reads.get_location_landscape_summary",
        lambda *_args: payload,
    )
    with TestClient(_landscape_app(object())) as client:
        response = client.get(f"/operator/api/landscape/{location_id}/summary")

    assert response.status_code == 200
    assert response.json() == payload
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"


@pytest.mark.parametrize(
    "invalid_field",
    [
        "top_level_extra",
        "nested_extra",
        "unknown_habitat_type",
        "negative_count",
        "non_finite",
        "percentage",
        "location_mismatch",
    ],
)
def test_landscape_route_rejects_invalid_projection(monkeypatch, invalid_field):
    location_id = str(uuid4())
    payload = _landscape_payload(location_id)
    if invalid_field == "top_level_extra":
        payload["source_ids"] = [str(uuid4())]
    elif invalid_field == "nested_extra":
        payload["habitats"][0]["private_note"] = "must not be returned"
    elif invalid_field == "unknown_habitat_type":
        payload["habitats"][0]["habitat_type"] = "unknown"
    elif invalid_field == "negative_count":
        payload["habitats"][0]["record_count"] = -1
    elif invalid_field == "non_finite":
        payload["verified_assessments"]["mean_overall_score"] = float("nan")
    elif invalid_field == "percentage":
        payload["dashboard_calculations"]["verified_buffer_checks"]["compliance_pct"] = 101
    else:
        payload["location_id"] = str(uuid4())

    monkeypatch.setattr(
        "services.gateway.landscape_conservation_reads.get_location_landscape_summary",
        lambda *_args: payload,
    )
    with TestClient(_landscape_app(object())) as client:
        response = client.get(f"/operator/api/landscape/{location_id}/summary")

    assert response.status_code == 500
    assert response.json() == {"error": "Landscape summary unavailable"}
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
