"""Strict location-scoped response contract for aggregate capacity periods."""

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


def _item(start, end, *, suppressed=False, **hours):
    item = {
        "period_start": start,
        "period_end": end,
        "suppressed": suppressed,
        "available_hours": 24.0,
        "committed_hours": 8.0,
        "protected_hours": 4.0,
    }
    if suppressed:
        item.update(
            available_hours=None,
            committed_hours=None,
            protected_hours=None,
        )
    item.update(hours)
    return item


def _page(**overrides):
    page = {
        "location_id": LOCATION_ID,
        "scope_configured": True,
        "limit": 2,
        "offset": 4,
        "items": [
            _item("2026-01-01", "2026-01-31"),
            _item("2026-02-01", "2026-02-28", suppressed=True),
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
        "services.gateway.operating_pilot_reads.get_location_operating_pilot_capacity_periods",
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
        f"/operator/api/operating-pilot/{LOCATION_ID}/capacity-periods",
        params={"limit": 2, "offset": 4},
    )


def test_capacity_periods_openapi_publishes_exact_redacted_projection(monkeypatch):
    app, _calls = _app(monkeypatch, _page())
    schema = app.openapi()
    operation = schema["paths"][
        "/operator/api/operating-pilot/{location_id}/capacity-periods"
    ]["get"]
    response_schema = operation["responses"]["200"]["content"]["application/json"]["schema"]
    assert response_schema["$ref"].endswith("OperatingPilotCapacityPeriodsPage")

    page_schema = schema["components"]["schemas"]["OperatingPilotCapacityPeriodsPage"]
    item_schema = schema["components"]["schemas"]["OperatingPilotCapacityPeriodItem"]
    assert set(page_schema["properties"]) == {
        "location_id", "scope_configured", "limit", "offset", "items",
        "has_more", "next_offset",
    }
    assert page_schema["additionalProperties"] is False
    assert set(item_schema["properties"]) == {
        "period_start", "period_end", "suppressed", "available_hours",
        "committed_hours", "protected_hours",
    }
    assert item_schema["additionalProperties"] is False


def test_capacity_periods_response_preserves_shape_and_binds_request(monkeypatch):
    page = _page(has_more=True, next_offset=6)
    app, calls = _app(monkeypatch, page)

    with TestClient(app) as client:
        response = _request(client)

    assert response.status_code == 200
    assert response.json() == page
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert calls == [(OPERATOR_ID, LOCATION_ID, {"limit": 2, "offset": 4})]


def test_capacity_periods_accepts_unconfigured_empty_scope(monkeypatch):
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
        lambda page: page["items"][0].update(period_end="2025-12-31"),
        lambda page: page["items"][0].update(period_start="not-a-date"),
        lambda page: page["items"][0].update(available_hours=-1),
        lambda page: page["items"][0].update(available_hours=24.123),
        lambda page: page["items"][0].update(committed_hours=21.0),
        lambda page: page["items"][1].update(available_hours=24.0),
        lambda page: page["items"][0].update(available_hours=None),
        lambda page: page["items"][0].update(extra="private"),
        lambda page: page.update(scope_configured=False),
    ],
)
def test_malformed_capacity_periods_response_fails_closed(monkeypatch, mutate):
    page = deepcopy(_page())
    mutate(page)
    app, _calls = _app(monkeypatch, page)

    with TestClient(app) as client:
        response = _request(client)

    assert response.status_code == 500
    assert response.json() == {"error": "Operating capacity read unavailable"}
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"

