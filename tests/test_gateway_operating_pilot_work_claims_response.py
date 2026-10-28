"""Strict private aggregate response contract for operating-pilot work claims."""

from copy import deepcopy
from types import SimpleNamespace
from uuid import uuid4

import pytest

pytest.importorskip("fastapi")
from fastapi import APIRouter, FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from services.gateway.operating_pilot_routes import (  # noqa: E402
    register_operating_pilot_routes,
)

LOCATION_ID = str(uuid4())
OTHER_LOCATION_ID = str(uuid4())
OPERATOR_ID = str(uuid4())


def _item(work_type, *, suppressed=False, claim_count=4, **overrides):
    item = {
        "work_type": work_type,
        "suppressed": suppressed,
        "claim_count": claim_count,
    }
    item.update(overrides)
    return item


def _page(**overrides):
    page = {
        "location_id": LOCATION_ID,
        "scope_configured": True,
        "limit": 2,
        "offset": 4,
        "items": [
            _item("agroforestry", suppressed=True, claim_count=None),
            _item("general", claim_count=4),
        ],
        "has_more": False,
        "next_offset": None,
    }
    page.update(overrides)
    return page


def _app(monkeypatch, result):
    calls = []

    def service(operator_id, location_id, **kwargs):
        calls.append((operator_id, location_id, kwargs))
        return result

    monkeypatch.setattr(
        "services.gateway.operating_pilot_reads.get_location_operating_pilot_work_claims",
        service,
    )
    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_operating_pilot_routes(
        router, object(), run_in_threadpool, SimpleNamespace(Error=Exception)
    )
    app = FastAPI()
    app.include_router(router)

    @app.middleware("http")
    async def add_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    return app, calls


def _request(client):
    return client.get(
        f"/operator/api/operating-pilot/{LOCATION_ID}/work-claims",
        params={"limit": 2, "offset": 4},
    )


def test_work_claim_openapi_publishes_exact_suppressed_projection(monkeypatch):
    app, _calls = _app(monkeypatch, _page())
    schema = app.openapi()
    operation = schema["paths"][
        "/operator/api/operating-pilot/{location_id}/work-claims"
    ]["get"]
    response_schema = operation["responses"]["200"]["content"]["application/json"]["schema"]
    assert response_schema["$ref"].endswith("OperatingPilotWorkClaimsPage")

    page_schema = schema["components"]["schemas"]["OperatingPilotWorkClaimsPage"]
    item_schema = schema["components"]["schemas"]["OperatingPilotWorkClaimItem"]
    assert set(page_schema["properties"]) == {
        "location_id", "scope_configured", "limit", "offset", "items",
        "has_more", "next_offset",
    }
    assert page_schema["additionalProperties"] is False
    assert set(item_schema["properties"]) == {"work_type", "suppressed", "claim_count"}
    assert item_schema["additionalProperties"] is False
    assert item_schema["properties"]["work_type"]["enum"] == [
        "general", "planting", "harvest", "irrigation", "monitoring",
        "maintenance", "tree-care", "agroforestry", "soil-health",
        "water-management", "other",
    ]


def test_work_claim_response_preserves_shape_and_binds_request(monkeypatch):
    page = _page(has_more=True, next_offset=6)
    app, calls = _app(monkeypatch, page)

    with TestClient(app) as client:
        response = _request(client)

    assert response.status_code == 200
    assert response.json() == page
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert calls == [(OPERATOR_ID, LOCATION_ID, {"limit": 2, "offset": 4})]


def test_unconfigured_work_claim_scope_returns_empty_terminal_page(monkeypatch):
    page = _page(scope_configured=False, items=[])
    app, _calls = _app(monkeypatch, page)

    with TestClient(app) as client:
        response = _request(client)

    assert response.status_code == 200
    assert response.json() == page


@pytest.mark.parametrize(
    "mutate",
    [
        lambda page: page.update(unexpected="private data"),
        lambda page: page.update(location_id=OTHER_LOCATION_ID),
        lambda page: page.update(limit=1),
        lambda page: page.update(offset=3),
        lambda page: page.update(scope_configured="true"),
        lambda page: page.update(next_offset=6),
        lambda page: page.update(has_more=True, next_offset=7),
        lambda page: page.update(has_more=True, next_offset=6, items=page["items"][:1]),
        lambda page: page.update(items=[page["items"][1], page["items"][0]]),
        lambda page: page.update(items=[page["items"][0], page["items"][0]]),
        lambda page: page["items"][0].update(work_type="individual-task"),
        lambda page: page["items"][0].update(suppressed="true"),
        lambda page: page["items"][0].update(suppressed=True, claim_count=2),
        lambda page: page["items"][1].update(suppressed=False, claim_count=None),
        lambda page: page["items"][1].update(claim_count=True),
        lambda page: page.update(scope_configured=False),
        lambda page: page.update(items=[*page["items"], _item("other")]),
    ],
)
def test_malformed_work_claim_response_fails_closed(monkeypatch, mutate):
    page = deepcopy(_page())
    mutate(page)
    app, _calls = _app(monkeypatch, page)

    with TestClient(app) as client:
        response = _request(client)

    assert response.status_code == 500
    assert response.json() == {"error": "Operating work-claim read unavailable"}
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"

