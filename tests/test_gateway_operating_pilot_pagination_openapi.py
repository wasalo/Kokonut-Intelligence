"""OpenAPI and pre-service bounds for operating-pilot list routes."""

from types import SimpleNamespace

import pytest

pytest.importorskip("fastapi")
from fastapi import APIRouter, FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from services.gateway.operating_pilot_routes import register_operating_pilot_routes

LOCATION_ID = "b0000000-0000-4000-8000-000000000001"
LIST_PATHS = (
    "/operator/api/operating-pilot/{location_id}/work-claim-review-queue",
    "/operator/api/operating-pilot/{location_id}/work-claim-allocation-queue",
    "/operator/api/operating-pilot/{location_id}/demand-signals",
    "/operator/api/operating-pilot/{location_id}/capacity-periods",
    "/operator/api/operating-pilot/{location_id}/my-capacity-profiles",
    "/operator/api/operating-pilot/{location_id}/my-competency-assessments",
    "/operator/api/operating-pilot/{location_id}/my-learning-plans",
    "/operator/api/operating-pilot/{location_id}/my-coaching-sessions",
    "/operator/api/operating-pilot/{location_id}/coaching-participants",
    "/operator/api/operating-pilot/{location_id}/my-demand-signals",
    "/operator/api/operating-pilot/{location_id}/my-resource-requests",
    "/operator/api/operating-pilot/{location_id}/capacity-review-queue",
    "/operator/api/operating-pilot/{location_id}/competency-review-queue",
    "/operator/api/operating-pilot/{location_id}/learning-plan-review-queue",
    "/operator/api/operating-pilot/{location_id}/learning-plan-activation-queue",
    "/operator/api/operating-pilot/{location_id}/demand-review-queue",
    "/operator/api/operating-pilot/{location_id}/resource-review-queue",
    "/operator/api/operating-pilot/{location_id}/resource-fulfillment-queue",
    "/operator/api/operating-pilot/{location_id}/work-claims",
    "/operator/api/operating-pilot/{location_id}/resource-categories",
    "/operator/api/operating-pilot/{location_id}/work-opportunities",
)


@pytest.fixture
def route_app():
    calls = []

    async def run_in_threadpool(function, *args, **kwargs):
        calls.append((function, args, kwargs))
        return {}

    app = FastAPI()
    router = APIRouter()
    register_operating_pilot_routes(
        router, object(), run_in_threadpool, SimpleNamespace(Error=Exception)
    )
    app.include_router(router)
    return app, calls


def test_all_list_routes_publish_downstream_page_bounds(route_app):
    app, _calls = route_app
    openapi = app.openapi()

    assert len(LIST_PATHS) == 21
    for path in LIST_PATHS:
        parameters = openapi["paths"][path]["get"]["parameters"]
        by_name = {parameter["name"]: parameter["schema"] for parameter in parameters}
        assert by_name["limit"]["type"] == "integer"
        assert by_name["limit"]["minimum"] == 1
        assert by_name["limit"]["maximum"] == 50
        assert by_name["limit"]["default"] == 25
        assert by_name["offset"]["type"] == "integer"
        assert by_name["offset"]["minimum"] == 0
        assert by_name["offset"]["maximum"] == 10000
        assert by_name["offset"]["default"] == 0


@pytest.mark.parametrize("path", LIST_PATHS)
def test_all_list_routes_reject_out_of_range_page_before_service(route_app, path):
    app, calls = route_app
    concrete_path = path.replace("{location_id}", LOCATION_ID)

    with TestClient(app) as client:
        response = client.get(f"{concrete_path}?limit=51")

    assert response.status_code == 422
    assert calls == []


@pytest.mark.parametrize("query", ["limit=0", "offset=-1", "offset=10001"])
def test_invalid_lower_and_offset_bounds_fail_before_service(route_app, query):
    app, calls = route_app
    path = LIST_PATHS[0].replace("{location_id}", LOCATION_ID)

    with TestClient(app) as client:
        response = client.get(f"{path}?{query}")

    assert response.status_code == 422
    assert calls == []


def test_demand_route_publishes_strict_openapi_projection(route_app):
    app, _calls = route_app
    schema = app.openapi()
    operation = schema["paths"][
        "/operator/api/operating-pilot/{location_id}/demand-signals"
    ]["get"]

    assert operation["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/OperatingPilotDemandSignalsPage"
    }
    item_schema = schema["components"]["schemas"]["OperatingPilotDemandSignalItem"]
    assert item_schema["additionalProperties"] is False
    assert set(item_schema["properties"]) == {
        "work_type",
        "period_start",
        "period_end",
        "required_hours",
        "priority",
        "status",
    }
