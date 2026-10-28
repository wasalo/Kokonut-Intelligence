"""Strict private response contract for solution retirement candidates."""

from unittest.mock import Mock
from uuid import uuid4

from fastapi import APIRouter, FastAPI
from starlette.testclient import TestClient

from services.gateway.solution_lifecycle_routes import (
    register_solution_lifecycle_routes,
)

LOCATION_ID = str(uuid4())
OPERATOR_ID = str(uuid4())


def _solution(solution_id=None):
    return {
        "solution_id": solution_id or str(uuid4()),
        "solution_name": "Soil cover",
        "solution_type": "practice",
        "current_stage": "testing",
        "solution_status": "active",
    }


def _page(**overrides):
    page = {
        "location_id": LOCATION_ID,
        "offset": 5,
        "solutions": [_solution(), _solution()],
        "has_more": True,
        "next_offset": 7,
    }
    page.update(overrides)
    return page


def _app(monkeypatch, result):
    service = Mock(return_value=result)
    monkeypatch.setattr(
        "services.gateway.solution_lifecycle_reads.list_location_solution_retirement_candidates",
        service,
    )
    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_solution_lifecycle_routes(
        router, object(), run_in_threadpool, type("Psycopg", (), {"Error": Exception})
    )
    app = FastAPI()
    app.include_router(router)

    @app.middleware("http")
    async def add_operator(request, call_next):
        from types import SimpleNamespace

        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    return app, service


def test_retirement_candidate_openapi_publishes_exact_projection(monkeypatch):
    app, _service = _app(monkeypatch, _page())
    operation = app.openapi()["paths"][
        "/operator/api/solution-lifecycle/{location_id}/retirement-candidates"
    ]["get"]
    response_schema = operation["responses"]["200"]["content"][
        "application/json"
    ]["schema"]
    assert response_schema["$ref"].endswith("SolutionRetirementCandidatesResponse")

    components = app.openapi()["components"]["schemas"]
    item = components["SolutionRetirementCandidateItemResponse"]
    assert set(item["properties"]) == {
        "solution_id",
        "solution_name",
        "solution_type",
        "current_stage",
        "solution_status",
    }
    assert item["additionalProperties"] is False


def test_retirement_candidate_returns_exact_page_with_existing_private_headers(monkeypatch):
    page = _page()
    app, service = _app(monkeypatch, page)

    with TestClient(app) as client:
        response = client.get(
            f"/operator/api/solution-lifecycle/{LOCATION_ID}/retirement-candidates",
            params={"limit": 2, "offset": 5},
        )

    assert response.status_code == 200
    assert response.json() == page
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    service.assert_called_once()


def test_retirement_candidate_rejects_unreviewed_fields_and_request_scope_mismatch(
    monkeypatch,
):
    cases = [
        _page(location_id=str(uuid4())),
        _page(offset=4),
        _page(solutions=[{**_solution(), "party_id": str(uuid4())}, _solution()]),
        _page(solutions=[{**_solution(), "private_note": "hidden"}, _solution()]),
        _page(next_offset=8),
    ]
    for invalid in cases:
        app, _service = _app(monkeypatch, invalid)
        with TestClient(app) as client:
            response = client.get(
                f"/operator/api/solution-lifecycle/{LOCATION_ID}/retirement-candidates",
                params={"limit": 2, "offset": 5},
            )
        assert response.status_code == 500
        assert response.json() == {"error": "Solution retirement candidate read unavailable"}
        assert response.headers["cache-control"] == "no-store"
        assert response.headers["vary"] == "Cookie"


def test_retirement_candidate_rejects_incomplete_or_oversized_continuation(monkeypatch):
    for invalid, limit in (
        (_page(solutions=[_solution()]), 2),
        (_page(solutions=[_solution(), _solution(), _solution()]), 2),
    ):
        app, _service = _app(monkeypatch, invalid)
        with TestClient(app) as client:
            response = client.get(
                f"/operator/api/solution-lifecycle/{LOCATION_ID}/retirement-candidates",
                params={"limit": limit, "offset": 5},
            )
        assert response.status_code == 500

    app, _service = _app(monkeypatch, _page(has_more=False, next_offset=None))
    with TestClient(app) as client:
        response = client.get(
            f"/operator/api/solution-lifecycle/{LOCATION_ID}/retirement-candidates",
            params={"limit": 2, "offset": 5},
        )
    assert response.status_code == 200

