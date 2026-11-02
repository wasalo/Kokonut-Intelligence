"""Strict private response contract for the operating-pilot demand review queue."""

from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

pytest.importorskip("fastapi")
from fastapi import APIRouter, FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from services.gateway.operating_pilot_routes import register_operating_pilot_routes
from services.gateway.operator_auth import auth_route_policy

LOCATION_ID = "b0000000-0000-4000-8000-000000000001"
OTHER_LOCATION = "b0000000-0000-4000-8000-000000000099"
OPERATOR_ID = "b0000000-0000-4000-8000-000000000002"
SIGNAL_A = "b0000000-0000-4000-8000-000000000021"
SIGNAL_B = "b0000000-0000-4000-8000-000000000020"
PATH = "/operator/api/operating-pilot/{location_id}/demand-review-queue"


def _signal(signal_id=SIGNAL_A, *, updated_at="2026-10-29T12:00:00+00:00", **updates):
    item = {
        "signal_id": signal_id,
        "work_type": "Soil preparation",
        "period_start": "2026-10-01",
        "period_end": "2026-10-31",
        "required_hours": 40.0,
        "priority": "high",
        "status": "submitted",
        "updated_at": updated_at,
    }
    item.update(updates)
    return item


def _page(*, items=None, **updates):
    page = {
        "location_id": LOCATION_ID,
        "items": [
            _signal(SIGNAL_A, updated_at="2026-10-29T13:00:00+00:00"),
            _signal(SIGNAL_B, updated_at="2026-10-29T12:00:00+00:00"),
        ] if items is None else items,
        "limit": 2,
        "offset": 4,
        "has_more": True,
        "next_offset": 6,
        "total": 10,
    }
    page.update(updates)
    return page


def _route_app(monkeypatch, result, *, provider=object()):
    calls = []

    def reader(*args, **kwargs):
        calls.append((args, kwargs))
        return deepcopy(result)

    monkeypatch.setattr(
        "services.gateway.operating_pilot_reads.get_location_operating_pilot_demand_review_queue",
        reader,
    )
    app = FastAPI()
    router = APIRouter()

    async def run_inline(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_operating_pilot_routes(
        router, provider, run_inline, SimpleNamespace(Error=Exception)
    )
    app.include_router(router)

    @app.middleware("http")
    async def add_operator_session(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    return app, calls


def test_demand_review_openapi_matches_exact_migration_projection(monkeypatch):
    app, _calls = _route_app(monkeypatch, _page())
    operation = app.openapi()["paths"][PATH]["get"]
    assert operation["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/OperatingPilotDemandReviewQueueResponse"
    }

    schemas = app.openapi()["components"]["schemas"]
    page_schema = schemas["OperatingPilotDemandReviewQueueResponse"]
    item_schema = schemas["OperatingPilotDemandReviewQueueItem"]
    assert set(page_schema["properties"]) == {
        "location_id", "items", "limit", "offset", "has_more", "next_offset", "total"
    }
    assert set(page_schema["required"]) == set(page_schema["properties"])
    assert page_schema["additionalProperties"] is False
    assert set(item_schema["properties"]) == {
        "signal_id", "work_type", "period_start", "period_end", "required_hours",
        "priority", "status", "updated_at",
    }
    assert set(item_schema["required"]) == set(item_schema["properties"])
    assert item_schema["additionalProperties"] is False
    assert item_schema["properties"]["status"]["const"] == "submitted"
    assert item_schema["properties"]["required_hours"]["multipleOf"] == 0.01
    parameters = {parameter["name"]: parameter for parameter in operation["parameters"]}
    assert parameters["limit"]["schema"]["minimum"] == 1
    assert parameters["limit"]["schema"]["maximum"] == 50
    assert parameters["offset"]["schema"]["minimum"] == 0
    assert parameters["offset"]["schema"]["maximum"] == 10000

    migration = (
        Path(__file__).resolve().parents[1]
        / "schemas/postgres/560_location_operating_pilot_demand_review_queue.sql"
    ).read_text(encoding="utf-8")
    for field in (
        "signal_id", "work_type", "period_start", "period_end", "required_hours",
        "priority", "status", "updated_at",
    ):
        assert f"'{field}'" in migration
    assert "ORDER BY updated_at DESC, id DESC" in migration
    assert "'total', (SELECT count(*) FROM eligible)" in migration


def test_demand_review_binds_location_page_policy_and_preserves_redaction(monkeypatch):
    page = _page()
    app, calls = _route_app(monkeypatch, page)
    with TestClient(app) as client:
        response = client.get(
            f"/operator/api/operating-pilot/{LOCATION_ID}/demand-review-queue"
            "?limit=2&offset=4"
        )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert response.json() == page
    assert calls == [((OPERATOR_ID, LOCATION_ID), {"limit": 2, "offset": 4})]
    assert auth_route_policy(
        "GET", f"/operator/api/operating-pilot/{LOCATION_ID}/demand-review-queue", enabled=True
    ) == {
        "resource": "operating_pilot", "action": "review", "public": False,
        "location_id": LOCATION_ID, "scope_required": True, "operator_auth": True,
    }


def test_demand_review_caps_unrequestable_continuation(monkeypatch):
    page = _page(
        items=[
            _signal(SIGNAL_A, updated_at="2026-10-29T13:00:00+00:00"),
            _signal(SIGNAL_B, updated_at="2026-10-29T12:00:00+00:00"),
        ],
        limit=2,
        offset=10000,
        has_more=True,
        next_offset=10002,
        total=10003,
    )
    app, _calls = _route_app(monkeypatch, page)
    with TestClient(app) as client:
        response = client.get(
            f"/operator/api/operating-pilot/{LOCATION_ID}/demand-review-queue"
            "?limit=2&offset=10000"
        )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["has_more"] is False
    assert response.json()["next_offset"] is None
    assert response.json()["total"] == 10003


@pytest.mark.parametrize(
    "mutation",
    [
        pytest.param(lambda page: page.update(location_id=OTHER_LOCATION), id="wrong-location"),
        pytest.param(lambda page: page.update(limit=3), id="wrong-limit"),
        pytest.param(lambda page: page.update(offset=3), id="wrong-offset"),
        pytest.param(lambda page: page.update(private_reviewer_id=OPERATOR_ID), id="identity-leak"),
        pytest.param(lambda page: page.pop("total"), id="missing-total"),
        pytest.param(lambda page: page.update(total=5), id="wrong-total"),
        pytest.param(lambda page: page.update(next_offset=7), id="wrong-next-offset"),
        pytest.param(lambda page: page.update(has_more=False), id="terminal-with-continuation"),
        pytest.param(lambda page: page.update(items=page["items"][:1]), id="short-page"),
        pytest.param(lambda page: page["items"].reverse(), id="wrong-sql-order"),
        pytest.param(lambda page: page["items"][0].update(signal_id="not-a-uuid"), id="bad-id"),
        pytest.param(lambda page: page["items"][0].update(party_id=OPERATOR_ID), id="party-leak"),
        pytest.param(lambda page: page["items"][0].update(description="private narrative"), id="narrative-leak"),
        pytest.param(lambda page: page["items"][0].update(status="draft"), id="wrong-status"),
        pytest.param(lambda page: page["items"][0].update(priority="urgent"), id="bad-priority"),
        pytest.param(lambda page: page["items"][0].update(work_type="bad,type"), id="bad-work-type"),
        pytest.param(lambda page: page["items"][0].update(required_hours=-1), id="negative-hours"),
        pytest.param(lambda page: page["items"][0].update(required_hours=100000.01), id="hours-over-bound"),
        pytest.param(lambda page: page["items"][0].update(required_hours=40.001), id="hours-over-precision"),
        pytest.param(lambda page: page["items"][0].update(period_end="2026-09-30"), id="reversed-period"),
        pytest.param(lambda page: page["items"][0].update(period_end="2027-10-03"), id="period-over-bound"),
        pytest.param(lambda page: page["items"][0].update(updated_at="2026-10-29T13:00:00"), id="naive-timestamp"),
        pytest.param(lambda page: page.update(items=page["items"] + [deepcopy(page["items"][1])]), id="duplicate-id"),
    ],
)
def test_malformed_demand_review_response_is_sanitized_no_store(monkeypatch, mutation):
    page = _page()
    mutation(page)
    app, _calls = _route_app(monkeypatch, page)
    with TestClient(app) as client:
        response = client.get(
            f"/operator/api/operating-pilot/{LOCATION_ID}/demand-review-queue"
            "?limit=2&offset=4"
        )

    assert response.status_code == 500
    assert response.json() == {"error": "Operating demand review queue unavailable"}
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert "private narrative" not in response.text
    assert OPERATOR_ID not in response.text
