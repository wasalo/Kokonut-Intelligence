"""Strict private response contract for own competency assessments."""

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
DRAFT_IDS = (
    "f0000000-0000-4000-8000-000000000002",
    "f0000000-0000-4000-8000-000000000001",
)


def _item(draft_id, *, created_at="2026-10-28T12:00:00Z", **overrides):
    item = {
        "draft_id": draft_id,
        "competency_key": "facilitation",
        "current_level": 2.5,
        "target_level": 4.0,
        "evidence_note": "Private self-assessment evidence",
        "status": "draft",
        "review_reason": None,
        "reviewed_at": None,
        "created_at": created_at,
        "updated_at": "2026-10-28T12:00:00Z",
    }
    item.update(overrides)
    return item


def _page(**overrides):
    page = {
        "location_id": LOCATION_ID,
        "limit": 2,
        "offset": 4,
        "items": [_item(DRAFT_IDS[0]), _item(DRAFT_IDS[1])],
        "has_more": False,
        "next_offset": None,
    }
    page.update(overrides)
    return page


def _app(monkeypatch, result):
    service_calls = []

    def service(operator_id, location_id, **kwargs):
        service_calls.append((operator_id, location_id, kwargs))
        return result

    monkeypatch.setattr(
        "services.gateway.operating_pilot_reads.get_location_operating_pilot_own_competency_drafts",
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
        f"/operator/api/operating-pilot/{LOCATION_ID}/my-competency-assessments",
        params={"limit": 2, "offset": 4},
    )


def test_own_competency_openapi_publishes_exact_private_projection(monkeypatch):
    app, _calls = _app(monkeypatch, _page())
    operation = app.openapi()["paths"][
        "/operator/api/operating-pilot/{location_id}/my-competency-assessments"
    ]["get"]
    schema = operation["responses"]["200"]["content"]["application/json"]["schema"]
    assert schema["$ref"].endswith("OperatingPilotOwnCompetencyAssessmentsPage")

    schemas = app.openapi()["components"]["schemas"]
    page_schema = schemas["OperatingPilotOwnCompetencyAssessmentsPage"]
    item_schema = schemas["OperatingPilotOwnCompetencyAssessmentResponse"]
    assert set(page_schema["properties"]) == {
        "location_id", "limit", "offset", "items", "has_more", "next_offset",
    }
    assert page_schema["additionalProperties"] is False
    assert set(item_schema["properties"]) == {
        "draft_id", "competency_key", "current_level", "target_level",
        "evidence_note", "status", "review_reason", "reviewed_at", "created_at",
        "updated_at",
    }
    assert item_schema["additionalProperties"] is False
    assert item_schema["properties"]["competency_key"]["maxLength"] == 120
    assert item_schema["properties"]["status"]["enum"] == [
        "draft", "superseded", "submitted", "rejected", "verified",
    ]


def test_own_competency_response_preserves_private_shape_and_binds_request(monkeypatch):
    page = _page(has_more=True, next_offset=6)
    app, calls = _app(monkeypatch, page)

    with TestClient(app) as client:
        response = _request(client)

    assert response.status_code == 200
    assert response.json() == page
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert calls == [(OPERATOR_ID, LOCATION_ID, {"limit": 2, "offset": 4})]


def test_own_competency_response_accepts_terminal_empty_page(monkeypatch):
    page = _page(items=[])
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
        lambda page: page.update(has_more="false"),
        lambda page: page.update(next_offset=6),
        lambda page: page.update(has_more=True, next_offset=7),
        lambda page: page.update(has_more=True, next_offset=6, items=page["items"][:1]),
        lambda page: page.update(items=[page["items"][1], page["items"][0]]),
        lambda page: page.update(items=[page["items"][0], page["items"][0]]),
        lambda page: page["items"][0].update(status="published"),
        lambda page: page["items"][0].update(competency_key="Bad Key"),
        lambda page: page["items"][0].update(competency_key="x" * 121),
        lambda page: page["items"][0].update(current_level=True),
        lambda page: page["items"][0].update(target_level=2),
        lambda page: page["items"][0].update(evidence_note="x" * 2001),
        lambda page: page["items"][0].update(review_reason="x" * 2001),
        lambda page: page["items"][0].update(reviewed_at="2026-10-28T12:00:00"),
        lambda page: page["items"][0].update(status="rejected", review_reason="  "),
        lambda page: page["items"][0].update(extra="unexpected"),
    ],
)
def test_malformed_own_competency_response_fails_closed(monkeypatch, mutate):
    page = deepcopy(_page())
    mutate(page)
    app, _calls = _app(monkeypatch, page)

    with TestClient(app) as client:
        response = _request(client)

    assert response.status_code == 500
    assert response.json() == {"error": "Own competency history unavailable"}
    assert response.headers["cache-control"] == "no-store"

