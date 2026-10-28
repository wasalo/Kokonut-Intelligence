"""Strict private response contract for own capacity profiles."""

from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import APIRouter, FastAPI
from starlette.testclient import TestClient

from services.gateway.operating_pilot_routes import register_operating_pilot_routes

LOCATION_ID = str(uuid4())
OPERATOR_ID = str(uuid4())


def _profile(**overrides):
    profile = {
        "profile_id": str(uuid4()),
        "period_start": "2026-01-01",
        "period_end": "2026-01-31",
        "available_hours": 24.0,
        "committed_hours": 8.0,
        "protected_hours": 4.0,
        "notes": "My private capacity note",
        "source": "self_reported",
        "status": "draft",
        "created_at": "2026-10-28T10:00:00Z",
        "updated_at": "2026-10-28T10:00:00Z",
    }
    profile.update(overrides)
    return profile


def _page(**overrides):
    page = {
        "location_id": LOCATION_ID,
        "limit": 1,
        "offset": 4,
        "items": [_profile()],
        "has_more": False,
        "next_offset": None,
    }
    page.update(overrides)
    return page


def _app(monkeypatch, result):
    from unittest.mock import Mock

    service = Mock(return_value=result)
    monkeypatch.setattr(
        "services.gateway.operating_pilot_reads.get_location_operating_pilot_own_capacity_profiles",
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

    return app, service


def test_own_capacity_openapi_publishes_exact_private_projection(monkeypatch):
    app, _service = _app(monkeypatch, _page())
    operation = app.openapi()["paths"][
        "/operator/api/operating-pilot/{location_id}/my-capacity-profiles"
    ]["get"]
    schema = operation["responses"]["200"]["content"]["application/json"]["schema"]
    assert schema["$ref"].endswith("OperatingPilotOwnCapacityProfilesPage")

    item = app.openapi()["components"]["schemas"][
        "OperatingPilotOwnCapacityProfileResponse"
    ]
    assert set(item["properties"]) == {
        "profile_id",
        "period_start",
        "period_end",
        "available_hours",
        "committed_hours",
        "protected_hours",
        "notes",
        "source",
        "status",
        "created_at",
        "updated_at",
    }
    assert item["additionalProperties"] is False


def test_own_capacity_response_keeps_private_wire_shape_and_request_binding(monkeypatch):
    page = _page(has_more=True, next_offset=5)
    app, service = _app(monkeypatch, page)

    with TestClient(app) as client:
        response = client.get(
            f"/operator/api/operating-pilot/{LOCATION_ID}/my-capacity-profiles",
            params={"limit": 1, "offset": 4},
        )

    assert response.status_code == 200
    assert response.json() == page
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    service.assert_called_once_with(OPERATOR_ID, LOCATION_ID, limit=1, offset=4)


@pytest.mark.parametrize(
    "page,limit,offset",
    [
        (_page(location_id=str(uuid4())), 1, 4),
        (_page(limit=2), 1, 4),
        (_page(offset=3), 1, 4),
        (_page(items=[_profile(party_id=str(uuid4()))]), 1, 4),
        (_page(items=[_profile(status="unknown")]), 1, 4),
        (_page(items=[_profile(available_hours=-1.0)]), 1, 4),
        (_page(items=[_profile(committed_hours=21.0, protected_hours=4.0)]), 1, 4),
        (_page(has_more=True, next_offset=6), 1, 4),
        (_page(has_more=False, next_offset=5), 1, 4),
        (_page(items=[_profile(), _profile()]), 1, 4),
    ],
)
def test_own_capacity_rejects_invalid_projection_or_page_binding(monkeypatch, page, limit, offset):
    app, _service = _app(monkeypatch, page)

    with TestClient(app) as client:
        response = client.get(
            f"/operator/api/operating-pilot/{LOCATION_ID}/my-capacity-profiles",
            params={"limit": limit, "offset": offset},
        )

    assert response.status_code == 500
    assert response.json() == {"error": "Own operating capacity read unavailable"}
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"

