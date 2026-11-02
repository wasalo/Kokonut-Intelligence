"""Strict private Gateway contract for own operating-pilot demand reads."""

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
SIGNAL_A = "b0000000-0000-4000-8000-000000000020"
SIGNAL_B = "b0000000-0000-4000-8000-000000000021"
PATH = "/operator/api/operating-pilot/{location_id}/my-demand-signals"


def _signal(signal_id=SIGNAL_A, *, updated_at="2026-10-29T12:00:00+00:00", **updates):
    item = {
        "signal_id": signal_id,
        "work_type": "Soil preparation",
        "period_start": "2026-10-01",
        "period_end": "2026-10-31",
        "required_hours": 40.0,
        "priority": "high",
        "description": "Prepare the northern beds",
        "status": "submitted",
        "created_at": "2026-10-01T08:00:00+00:00",
        "updated_at": updated_at,
    }
    item.update(updates)
    return item


def _page(*, items=None, **updates):
    page = {
        "location_id": LOCATION_ID,
        "items": [
            _signal(SIGNAL_B, updated_at="2026-10-29T13:00:00+00:00"),
            _signal(SIGNAL_A, updated_at="2026-10-29T12:00:00+00:00"),
        ] if items is None else items,
        "limit": 2,
        "offset": 4,
        "has_more": True,
        "next_offset": 6,
        "total": 10,
    }
    page.update(updates)
    return page


def _route_app(monkeypatch, result):
    calls = []

    def reader(*args, **kwargs):
        calls.append((args, kwargs))
        return deepcopy(result)

    monkeypatch.setattr(
        "services.gateway.operating_pilot_reads.get_location_operating_pilot_own_demand_signals",
        reader,
    )
    app = FastAPI()
    router = APIRouter()

    async def run_inline(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_operating_pilot_routes(
        router, object(), run_inline, SimpleNamespace(Error=Exception)
    )
    app.include_router(router)

    @app.middleware("http")
    async def add_operator_session(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    return app, calls


def test_own_demand_openapi_publishes_exact_migration_backed_models(monkeypatch):
    app, _calls = _route_app(monkeypatch, _page())
    operation = app.openapi()["paths"][PATH]["get"]
    page_ref = operation["responses"]["200"]["content"]["application/json"]["schema"]
    assert page_ref == {"$ref": "#/components/schemas/OperatingPilotOwnDemandSignalsPage"}

    schemas = app.openapi()["components"]["schemas"]
    page = schemas["OperatingPilotOwnDemandSignalsPage"]
    item = schemas["OperatingPilotOwnDemandSignalItem"]
    assert set(page["properties"]) == {
        "location_id", "items", "limit", "offset", "has_more", "next_offset", "total"
    }
    assert set(page["required"]) == set(page["properties"])
    assert page["additionalProperties"] is False
    assert set(item["properties"]) == {
        "signal_id", "work_type", "period_start", "period_end", "required_hours",
        "priority", "description", "status", "created_at", "updated_at",
    }
    assert set(item["required"]) == set(item["properties"])
    assert item["additionalProperties"] is False


def test_own_demand_contract_matches_migration_projection_and_order():
    migration = (
        Path(__file__).resolve().parents[1]
        / "schemas/postgres/561_location_own_operating_pilot_demand.sql"
    ).read_text(encoding="utf-8")
    for field in (
        "signal_id", "work_type", "period_start", "period_end", "required_hours",
        "priority", "description", "status", "created_at", "updated_at",
    ):
        assert f"'{field}'" in migration
    assert "ORDER BY updated_at DESC, id DESC" in migration
    assert "'total', (SELECT count(*) FROM eligible)" in migration


def test_own_demand_binds_path_and_page_preserving_private_policy(monkeypatch):
    page = _page()
    app, calls = _route_app(monkeypatch, page)
    with TestClient(app) as client:
        response = client.get(
            f"/operator/api/operating-pilot/{LOCATION_ID}/my-demand-signals"
            "?limit=2&offset=4"
        )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert response.json() == page
    assert calls == [((OPERATOR_ID, LOCATION_ID), {"limit": 2, "offset": 4})]
    assert auth_route_policy(
        "GET", f"/operator/api/operating-pilot/{LOCATION_ID}/my-demand-signals", enabled=True
    ) == {
        "resource": "operating_pilot", "action": "read_own", "public": False,
        "location_id": LOCATION_ID, "scope_required": True, "operator_auth": True,
    }


def test_own_demand_caps_continuation_at_gateway_offset_limit(monkeypatch):
    page = {
        "location_id": LOCATION_ID,
        "items": [_signal()],
        "limit": 1,
        "offset": 10000,
        "has_more": True,
        "next_offset": 10001,
        "total": 10002,
    }
    app, _calls = _route_app(monkeypatch, page)
    with TestClient(app) as client:
        response = client.get(
            f"/operator/api/operating-pilot/{LOCATION_ID}/my-demand-signals"
            "?limit=1&offset=10000"
        )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["has_more"] is False
    assert response.json()["next_offset"] is None
    assert response.json()["total"] == 10002


@pytest.mark.parametrize(
    "mutation",
    [
        pytest.param(lambda page: page.update(location_id=OTHER_LOCATION), id="wrong-location"),
        pytest.param(lambda page: page.update(limit=3), id="wrong-limit"),
        pytest.param(lambda page: page.update(offset=3), id="wrong-offset"),
        pytest.param(lambda page: page.update(extra="private"), id="extra-page-field"),
        pytest.param(lambda page: page.pop("total"), id="missing-page-field"),
        pytest.param(lambda page: page.update(total=5), id="has-more-disagrees-with-total"),
        pytest.param(lambda page: page.update(next_offset=7), id="wrong-next-offset"),
        pytest.param(lambda page: page.update(has_more=False), id="terminal-page-with-next-offset"),
        pytest.param(lambda page: page.update(items=page["items"][:1]), id="short-continuation"),
        pytest.param(lambda page: page["items"].reverse(), id="wrong-sql-order"),
        pytest.param(lambda page: page["items"][0].update(signal_id="not-a-uuid"), id="bad-signal-id"),
        pytest.param(lambda page: page["items"][0].update(private_party_id=OPERATOR_ID), id="identity-leak"),
        pytest.param(lambda page: page["items"][0].update(status="unknown"), id="bad-status"),
        pytest.param(lambda page: page["items"][0].update(priority="urgent"), id="bad-priority"),
        pytest.param(lambda page: page["items"][0].update(required_hours=100000.01), id="hours-over-bound"),
        pytest.param(lambda page: page["items"][0].update(required_hours=-1), id="negative-hours"),
        pytest.param(lambda page: page["items"][0].update(required_hours=40.001), id="hours-over-precision"),
        pytest.param(lambda page: page["items"][0].update(period_end="2026-09-30"), id="reversed-period"),
        pytest.param(lambda page: page["items"][0].update(period_end="2028-10-01"), id="period-over-bound"),
        pytest.param(lambda page: page["items"][0].update(updated_at="2026-10-29T13:00:00"), id="naive-timestamp"),
        pytest.param(lambda page: page["items"][0].update(created_at="2026-10-01T08:00:00"), id="naive-created-at"),
        pytest.param(lambda page: page["items"][0].update(description="x" * 2001), id="long-description"),
        pytest.param(lambda page: page["items"][0].update(work_type=" "), id="blank-work-type"),
        pytest.param(lambda page: page["items"][0].update(work_type="x" * 51), id="long-work-type"),
        pytest.param(lambda page: page.update(items=page["items"] + [page["items"][1]]), id="duplicate-id"),
    ],
)
def test_malformed_own_demand_response_is_sanitized_no_store(monkeypatch, mutation):
    page = _page()
    mutation(page)
    app, _calls = _route_app(monkeypatch, page)
    with TestClient(app) as client:
        response = client.get(
            f"/operator/api/operating-pilot/{LOCATION_ID}/my-demand-signals"
            "?limit=2&offset=4"
        )

    assert response.status_code == 500
    assert response.json() == {"error": "Own operating demand read unavailable"}
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert "private" not in response.text
