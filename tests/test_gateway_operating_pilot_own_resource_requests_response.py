"""Strict private response contract for the own resource-request page."""

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
OPERATOR_ID = str(uuid4())
DRAFT_IDS = (str(uuid4()), str(uuid4()))
UPDATED_AT = "2026-10-28T12:00:00Z"


def _item(draft_id, *, resource_type="seeds", description="Native seed request", **overrides):
    item = {
        "draft_id": draft_id,
        "resource_type": resource_type,
        "description": description,
        "urgency": "medium",
        "requested_by": "2026-11-15",
        "status": "draft",
        "created_at": "2026-10-28T10:00:00Z",
        "updated_at": UPDATED_AT,
    }
    item.update(overrides)
    return item


def _page(**overrides):
    page = {
        "location_id": LOCATION_ID,
        "items": [
            _item(DRAFT_IDS[1]),
            _item(DRAFT_IDS[0], updated_at="2026-10-28T11:00:00Z"),
        ],
        "limit": 2,
        "offset": 4,
        "has_more": True,
        "next_offset": 6,
        "total": 12,
    }
    page.update(overrides)
    return page


def _update_first_item(page, **fields):
    page["items"][0].update(fields)
    return page


def _app(monkeypatch, result, *, service_error=None):
    service_calls = []

    def service(operator_id, location_id, **kwargs):
        service_calls.append((operator_id, location_id, kwargs))
        if service_error is not None:
            raise service_error
        return result

    monkeypatch.setattr(
        "services.gateway.operating_pilot_reads.get_location_operating_pilot_own_resource_requests",
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

    return app, service_calls


def _request(client):
    return client.get(
        f"/operator/api/operating-pilot/{LOCATION_ID}/my-resource-requests",
        params={"limit": 2, "offset": 4},
    )


def test_own_resource_requests_openapi_publishes_exact_projection(monkeypatch):
    app, _calls = _app(monkeypatch, _page())
    operation = app.openapi()["paths"][
        "/operator/api/operating-pilot/{location_id}/my-resource-requests"
    ]["get"]
    schema = operation["responses"]["200"]["content"]["application/json"]["schema"]
    assert schema["$ref"].endswith("OperatingPilotOwnResourceRequestsPage")

    page_schema = app.openapi()["components"]["schemas"][
        "OperatingPilotOwnResourceRequestsPage"
    ]
    item_schema = app.openapi()["components"]["schemas"][
        "OperatingPilotOwnResourceRequestItemResponse"
    ]
    assert set(page_schema["properties"]) == {
        "location_id", "items", "limit", "offset", "has_more", "next_offset", "total",
    }
    assert page_schema["additionalProperties"] is False
    assert set(item_schema["properties"]) == {
        "draft_id", "resource_type", "description", "urgency", "requested_by",
        "status", "created_at", "updated_at",
    }
    assert item_schema["additionalProperties"] is False
    assert item_schema["properties"]["description"]["maxLength"] == 2000
    assert item_schema["properties"]["urgency"]["enum"] == [
        "low", "medium", "high", "critical",
    ]
    assert item_schema["properties"]["status"]["enum"] == [
        "draft", "superseded", "submitted",
    ]


def test_own_resource_requests_preserves_wire_shape_and_binds_request(monkeypatch):
    page = _page()
    app, calls = _app(monkeypatch, page)

    with TestClient(app) as client:
        response = _request(client)

    assert response.status_code == 200
    assert response.json() == page
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert calls == [(OPERATOR_ID, LOCATION_ID, {"limit": 2, "offset": 4})]


def test_own_resource_page_accepts_terminal_empty_offset_past_total(monkeypatch):
    page = _page(items=[], has_more=False, next_offset=None, total=3)
    app, _calls = _app(monkeypatch, page)

    with TestClient(app) as client:
        response = _request(client)

    assert response.status_code == 200
    assert response.json() == page


@pytest.mark.parametrize(
    "mutate",
    [
        lambda page: page.update(unexpected="private data"),
        lambda page: page.update(location_id=str(uuid4())),
        lambda page: page.update(limit=1),
        lambda page: page.update(offset=5),
        lambda page: page.update(total=True),
        lambda page: page.update(next_offset=7),
        lambda page: page.update(total=6),
        lambda page: page.update(has_more=False),
        lambda page: _update_first_item(page, status="published"),
        lambda page: _update_first_item(page, urgency="urgent"),
        lambda page: _update_first_item(page, resource_type="bad!type"),
        lambda page: _update_first_item(page, resource_type="x" * 51),
        lambda page: _update_first_item(page, description="  "),
        lambda page: _update_first_item(page, description="x" * 2001),
        lambda page: _update_first_item(page, requested_by="not-a-date"),
        lambda page: _update_first_item(page, created_at="2026-10-28T10:00:00"),
        lambda page: page.update(
            items=[
                _item(DRAFT_IDS[0], updated_at="2026-10-28T11:00:00Z"),
                _item(DRAFT_IDS[1], updated_at=UPDATED_AT),
            ]
        ),
        lambda page: page.update(
            items=[page["items"][0], {**page["items"][1], "draft_id": DRAFT_IDS[1]}]
        ),
        lambda page: _update_first_item(page, extra="private"),
    ],
)
def test_invalid_or_mismatched_resource_projection_fails_closed(monkeypatch, mutate):
    page = deepcopy(_page())
    mutate(page)
    app, calls = _app(monkeypatch, page)

    with TestClient(app) as client:
        response = _request(client)

    assert response.status_code == 500
    assert response.json() == {"error": "Own operating resource read unavailable"}
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert len(calls) == 1


@pytest.mark.parametrize("query", ["limit=0", "limit=51", "offset=-1", "offset=10001"])
def test_own_resource_query_bounds_fail_before_service(monkeypatch, query):
    app, calls = _app(monkeypatch, _page())

    with TestClient(app) as client:
        response = client.get(
            f"/operator/api/operating-pilot/{LOCATION_ID}/my-resource-requests?{query}"
        )

    assert response.status_code == 422
    assert calls == []


def test_own_resource_service_error_status_and_retry_header_are_preserved(monkeypatch):
    psycopg2 = pytest.importorskip("psycopg2")
    app, calls = _app(monkeypatch, None, service_error=psycopg2.Error("synthetic"))

    with TestClient(app) as client:
        response = _request(client)

    assert response.status_code == 503
    assert response.json() == {"error": "Own operating resource read unavailable"}
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert response.headers["retry-after"] == "30"
    assert len(calls) == 1
