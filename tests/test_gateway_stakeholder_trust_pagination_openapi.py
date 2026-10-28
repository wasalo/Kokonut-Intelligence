"""Route-level contract for stakeholder trust pagination bounds."""

from types import SimpleNamespace

import pytest

pytest.importorskip("fastapi")
from fastapi import FastAPI  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402


def _app(service_calls):
    from services.gateway.stakeholder_trust_routes import register_stakeholder_trust_routes

    class FakePostgresError(Exception):
        pass

    async def run_inline(function, *args, **kwargs):
        service_calls.append((function, args, kwargs))
        return {}

    app = FastAPI()

    @app.middleware("http")
    async def attach_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id="00000000-0000-0000-0000-000000000001")
        )
        return await call_next(request)

    register_stakeholder_trust_routes(
        app.router,
        SimpleNamespace(),
        run_inline,
        SimpleNamespace(Error=FakePostgresError),
    )
    return app


def test_stakeholder_trust_openapi_publishes_service_page_bounds():
    app = _app([])
    operation = app.openapi()["paths"][
        "/operator/api/stakeholder-trust/{location_id}/parties/{party_id}/identity-evidence"
    ]["get"]
    limit = next(parameter for parameter in operation["parameters"] if parameter["name"] == "limit")

    assert limit["schema"]["type"] == "integer"
    assert limit["schema"]["default"] == 50
    assert limit["schema"]["minimum"] == 1
    assert limit["schema"]["maximum"] == 50


@pytest.mark.parametrize("limit", [0, 51, -1, "not-a-number"])
def test_invalid_stakeholder_trust_limit_fails_before_service(limit):
    service_calls = []
    app = _app(service_calls)

    with TestClient(app) as client:
        response = client.get(
            "/operator/api/stakeholder-trust/location/parties/party/identity-evidence",
            params={"limit": limit},
        )

    assert response.status_code == 422
    assert service_calls == []
