"""Route-level pagination bounds for the business architecture projection."""

from types import SimpleNamespace
from uuid import uuid4

import pytest

pytest.importorskip("fastapi")
from fastapi import APIRouter, FastAPI  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

from services.gateway.business_architecture_routes import (  # noqa: E402
    register_business_architecture_routes,
)

LOCATION_ID = str(uuid4())
PATH = f"/operator/api/business-architecture/{LOCATION_ID}/summary"


def _client():
    app = FastAPI()
    router = APIRouter()

    async def run_in_threadpool(*_args, **_kwargs):
        pytest.fail("invalid page values must be rejected before service access")

    register_business_architecture_routes(
        router, object(), run_in_threadpool, SimpleNamespace(Error=Exception)
    )
    app.include_router(router)

    @app.middleware("http")
    async def add_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=str(uuid4()))
        )
        return await call_next(request)

    return TestClient(app)


def test_business_architecture_openapi_documents_service_pagination_bounds():
    with _client() as client:
        operation = client.get("/openapi.json").json()["paths"][
            "/operator/api/business-architecture/{location_id}/summary"
        ]["get"]

    parameters = {parameter["name"]: parameter for parameter in operation["parameters"]}
    limit = parameters["limit"]["schema"]
    offset = parameters["offset"]["schema"]
    assert (limit["default"], limit["minimum"], limit["maximum"]) == (25, 1, 50)
    assert (offset["default"], offset["minimum"], offset["maximum"]) == (0, 0, 10000)


@pytest.mark.parametrize("query", ["limit=0", "limit=51", "offset=-1", "offset=10001"])
def test_invalid_business_architecture_page_values_fail_before_service_access(query):
    with _client() as client:
        response = client.get(f"{PATH}?{query}")

    assert response.status_code == 422
