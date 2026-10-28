"""OpenAPI and request-validation contract for planning-budget pagination."""

from types import SimpleNamespace
from unittest.mock import patch

import pytest

pytest.importorskip("fastapi")
from fastapi import APIRouter, FastAPI  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

LOCATION_ID = "10000000-0000-0000-0000-000000000001"


def _app():
    from services.gateway.planning_budget_routes import register_planning_budget_routes

    app = FastAPI()
    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_planning_budget_routes(
        router,
        object(),
        run_in_threadpool,
        SimpleNamespace(Error=Exception),
    )
    app.include_router(router)
    return app


def test_openapi_publishes_planning_budget_reader_page_bounds():
    operation = _app().openapi()["paths"][
        "/operator/api/planning/{location_id}/budgets"
    ]["get"]
    parameters = {parameter["name"]: parameter for parameter in operation["parameters"]}

    assert parameters["limit"]["schema"] == {
        "title": "Limit",
        "maximum": 50,
        "minimum": 1,
        "type": "integer",
        "default": 25,
    }
    assert parameters["offset"]["schema"] == {
        "title": "Offset",
        "maximum": 10000,
        "minimum": 0,
        "type": "integer",
        "default": 0,
    }


@pytest.mark.parametrize(
    "query",
    [
        {"limit": "0"},
        {"limit": "51"},
        {"limit": "many"},
        {"offset": "-1"},
        {"offset": "10001"},
    ],
)
def test_invalid_pagination_is_rejected_before_service_access(query):
    service = patch(
        "services.gateway.planning_budget_reads.list_location_budget_summaries",
        side_effect=AssertionError("invalid pagination must fail before service access"),
    )
    with service:
        with TestClient(_app()) as client:
            response = client.get(
                f"/operator/api/planning/{LOCATION_ID}/budgets", params=query
            )

    assert response.status_code == 422
