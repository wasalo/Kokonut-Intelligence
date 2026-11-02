"""Strict response contract for the independent capacity-review queue."""

from copy import deepcopy
from types import SimpleNamespace
from uuid import UUID, uuid4

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


def _item(profile_id, updated_at, **overrides):
    item = {
        "profile_id": profile_id,
        "period_start": "2026-10-01",
        "period_end": "2026-10-31",
        "available_hours": 40,
        "committed_hours": 10,
        "protected_hours": 5,
        "status": "submitted",
        "updated_at": updated_at,
    }
    item.update(overrides)
    return item


def _page(**overrides):
    page = {
        "location_id": LOCATION_ID,
        "items": [
            _item(
                "b0000000-0000-4000-8000-000000000002",
                "2026-10-22T12:00:00+00:00",
            ),
            _item(
                "b0000000-0000-4000-8000-000000000001",
                "2026-10-22T12:00:00+00:00",
            ),
        ],
        "limit": 2,
        "offset": 4,
        "has_more": False,
        "next_offset": None,
        "total": 6,
    }
    page.update(overrides)
    return page


def _app(monkeypatch, result):
    calls = []

    def service(operator_id, location_id, **kwargs):
        calls.append((operator_id, location_id, kwargs))
        return result

    monkeypatch.setattr(
        "services.gateway.operating_pilot_reads.get_location_operating_pilot_capacity_review_queue",
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
        f"/operator/api/operating-pilot/{LOCATION_ID}/capacity-review-queue",
        params={"limit": 2, "offset": 4},
    )


def test_capacity_review_queue_openapi_matches_sql_projection(monkeypatch):
    app, _calls = _app(monkeypatch, _page())
    schema = app.openapi()
    operation = schema["paths"][
        "/operator/api/operating-pilot/{location_id}/capacity-review-queue"
    ]["get"]
    response_schema = operation["responses"]["200"]["content"]["application/json"]["schema"]
    assert response_schema == {
        "$ref": "#/components/schemas/OperatingPilotCapacityReviewPage"
    }

    page_schema = schema["components"]["schemas"]["OperatingPilotCapacityReviewPage"]
    item_schema = schema["components"]["schemas"]["OperatingPilotCapacityReviewItem"]
    assert set(page_schema["properties"]) == {
        "location_id",
        "items",
        "limit",
        "offset",
        "has_more",
        "next_offset",
        "total",
    }
    assert page_schema["additionalProperties"] is False
    assert set(item_schema["properties"]) == {
        "profile_id",
        "period_start",
        "period_end",
        "available_hours",
        "committed_hours",
        "protected_hours",
        "status",
        "updated_at",
    }
    assert item_schema["additionalProperties"] is False
    assert item_schema["properties"]["status"]["const"] == "submitted"


def test_capacity_review_queue_response_preserves_sql_page_and_binds_request(monkeypatch):
    page = _page()
    app, calls = _app(monkeypatch, page)

    with TestClient(app) as client:
        response = _request(client)

    assert response.status_code == 200
    assert response.json() == page
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert calls == [(OPERATOR_ID, LOCATION_ID, {"limit": 2, "offset": 4})]


@pytest.mark.parametrize(
    "mutate",
    [
        lambda page: page.update(unexpected="private data"),
        lambda page: page["items"][0].update(party_id="private"),
        lambda page: page.pop("total"),
        lambda page: page.update(location_id=OTHER_LOCATION_ID),
        lambda page: page.update(limit=1),
        lambda page: page.update(offset=3),
        lambda page: page.update(total=7),
        lambda page: page.update(has_more=True, next_offset=7),
        lambda page: page.update(has_more=True, next_offset=6, items=page["items"][:1], total=7),
        lambda page: page.update(total=5),
        lambda page: page.update(items=[page["items"][1], page["items"][0]]),
        lambda page: page.update(items=[page["items"][0], page["items"][0]]),
        lambda page: page["items"][0].update(period_end="2026-09-30"),
        lambda page: page["items"][0].update(committed_hours=36),
        lambda page: page["items"][0].update(status="approved"),
        lambda page: page["items"][0].update(available_hours=-1),
        lambda page: page["items"][0].update(available_hours=100000000),
        lambda page: page["items"][0].update(updated_at="2026-10-22T12:00:00"),
    ],
)
def test_malformed_capacity_review_queue_response_fails_closed(monkeypatch, mutate):
    page = deepcopy(_page())
    mutate(page)
    app, _calls = _app(monkeypatch, page)

    with TestClient(app) as client:
        response = _request(client)

    assert response.status_code == 500
    assert response.json() == {"error": "Operating capacity review queue unavailable"}
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"


def test_capacity_review_queue_rejects_response_without_location(monkeypatch):
    page = _page()
    page.pop("location_id")
    app, _calls = _app(monkeypatch, page)

    with TestClient(app) as client:
        response = _request(client)

    assert response.status_code == 500
    assert response.json() == {"error": "Operating capacity review queue unavailable"}
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"


def test_capacity_review_queue_emits_numeric_hours_as_json_numbers(monkeypatch):
    page = _page(
        items=[
            _item(
                "b0000000-0000-4000-8000-000000000002",
                "2026-10-22T12:00:00Z",
                available_hours=40.25,
                committed_hours=10.25,
                protected_hours=5.5,
            )
        ],
        total=5,
    )
    app, _calls = _app(monkeypatch, page)

    with TestClient(app) as client:
        response = _request(client)

    assert response.status_code == 200
    assert response.json()["items"][0]["available_hours"] == 40.25
    assert isinstance(response.json()["items"][0]["available_hours"], float)


def test_capacity_review_models_accept_uuid_and_native_postgres_json_values(monkeypatch):
    page = _page(
        location_id=UUID(LOCATION_ID),
        items=[
            _item(
                UUID("b0000000-0000-4000-8000-000000000002"),
                "2026-10-22T12:00:00+00:00",
                period_start="2026-10-01",
                period_end="2026-10-31",
            )
        ],
        total=5,
    )
    app, _calls = _app(monkeypatch, page)

    with TestClient(app) as client:
        response = _request(client)

    assert response.status_code == 200
    assert response.json()["location_id"] == LOCATION_ID
