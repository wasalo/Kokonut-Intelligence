"""Strict request-bound success contract for private work opportunities."""

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
WORK_ITEM_A = str(uuid4())
WORK_ITEM_B = str(uuid4())


def _item(work_item_id, *, priority="high", due_at="2026-01-01T12:00:00Z", **overrides):
    item = {
        "work_item_id": work_item_id,
        "title": "Prepare soil beds",
        "work_type": "soil preparation",
        "priority": priority,
        "status": "assigned",
        "selection_mode": "self_selected",
        "estimated_effort_hours": 4.5,
        "due_at": due_at,
        "allocation_status": "open",
        "has_own_claim": False,
        "own_claim_status": None,
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
            _item(WORK_ITEM_A, priority="critical"),
            _item(WORK_ITEM_B, priority="medium", due_at=None),
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
        "services.gateway.operating_pilot_reads.get_location_operating_pilot_work_opportunities",
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
        f"/operator/api/operating-pilot/{LOCATION_ID}/work-opportunities",
        params={"limit": 2, "offset": 4},
    )


def test_work_opportunities_openapi_publishes_exact_read_projection(monkeypatch):
    app, _calls = _app(monkeypatch, _page())
    operation = app.openapi()["paths"][
        "/operator/api/operating-pilot/{location_id}/work-opportunities"
    ]["get"]
    response_schema = operation["responses"]["200"]["content"]["application/json"]["schema"]
    assert response_schema["$ref"].endswith("OperatingPilotWorkOpportunitiesPage")

    page_schema = app.openapi()["components"]["schemas"]["OperatingPilotWorkOpportunitiesPage"]
    item_schema = app.openapi()["components"]["schemas"]["OperatingPilotWorkOpportunityItem"]
    assert set(page_schema["properties"]) == {
        "location_id", "scope_configured", "limit", "offset", "items", "has_more", "next_offset"
    }
    assert page_schema["additionalProperties"] is False
    assert set(item_schema["properties"]) == {
        "work_item_id", "title", "work_type", "priority", "status", "selection_mode",
        "estimated_effort_hours", "due_at", "allocation_status", "has_own_claim",
        "own_claim_status",
    }
    assert item_schema["additionalProperties"] is False


def test_work_opportunities_response_preserves_numeric_json_and_binds_request(monkeypatch):
    page = _page(has_more=True, next_offset=6)
    app, calls = _app(monkeypatch, page)

    with TestClient(app) as client:
        response = _request(client)

    assert response.status_code == 200
    assert response.json() == page
    assert isinstance(response.json()["items"][0]["estimated_effort_hours"], float)
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert calls == [(OPERATOR_ID, LOCATION_ID, {"limit": 2, "offset": 4})]


@pytest.mark.parametrize(
    "mutate",
    [
        lambda page: page.update(unexpected="private data"),
        lambda page: page.update(location_id=OTHER_LOCATION_ID),
        lambda page: page.update(limit=1),
        lambda page: page.update(offset=3),
        lambda page: page.update(scope_configured="true"),
        lambda page: page.update(scope_configured=False),
        lambda page: page.update(next_offset=6),
        lambda page: page.update(has_more=True, next_offset=7),
        lambda page: page.update(has_more=True, next_offset=6, items=page["items"][:1]),
        lambda page: page.update(items=[page["items"][1], page["items"][0]]),
        lambda page: page.update(items=[page["items"][0], page["items"][0]]),
        lambda page: page["items"][0].update(priority="urgent"),
        lambda page: page["items"][0].update(status="done"),
        lambda page: page["items"][0].update(selection_mode="assigned"),
        lambda page: page["items"][0].update(allocation_status="allocated"),
        lambda page: page["items"][0].update(estimated_effort_hours=-1),
        lambda page: page["items"][0].update(estimated_effort_hours=100000000),
        lambda page: page["items"][0].update(estimated_effort_hours=1.234),
        lambda page: page["items"][0].update(due_at="2026-01-01T12:00:00"),
        lambda page: page["items"][0].update(own_claim_status="unreviewed"),
        lambda page: page["items"][0].update(has_own_claim=True),
        lambda page: page["items"][0].update(extra="private"),
    ],
)
def test_malformed_work_opportunities_response_fails_closed(monkeypatch, mutate):
    page = deepcopy(_page())
    mutate(page)
    app, _calls = _app(monkeypatch, page)

    with TestClient(app) as client:
        response = _request(client)

    assert response.status_code == 500
    assert response.json() == {"error": "Operating work-opportunity read unavailable"}
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"

