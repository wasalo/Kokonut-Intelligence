"""Strict private Gateway contract for the learning-plan activation queue."""

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
PLAN_A = "b0000000-0000-4000-8000-000000000021"
PLAN_B = "b0000000-0000-4000-8000-000000000020"
PATH = "/operator/api/operating-pilot/{location_id}/learning-plan-activation-queue"


def _plan(plan_id=PLAN_A, *, submitted_at="2026-10-24T12:00:00+00:00", **updates):
    item = {
        "learning_plan_id": plan_id,
        "title": "Build soil observation skills",
        "competency_goals": ["soil sampling", {"level": 2}],
        "support_requested": ["field mentor"],
        "target_date": "2027-03-31",
        "status": "submitted",
        "submitted_at": submitted_at,
        "approved_at": "2026-10-24T13:00:00+00:00",
    }
    item.update(updates)
    return item


def _page(*, items=None, **updates):
    page = {
        "location_id": LOCATION_ID,
        "items": [
            _plan(PLAN_A, submitted_at="2026-10-24T12:00:00+00:00"),
            _plan(PLAN_B, submitted_at="2026-10-23T12:00:00+00:00"),
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
        "services.gateway.operating_pilot_reads.get_location_operating_pilot_learning_plan_activation_queue",
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


def test_learning_plan_activation_queue_openapi_and_migration_projection(monkeypatch):
    app, _calls = _route_app(monkeypatch, _page())
    operation = app.openapi()["paths"][PATH]["get"]
    assert operation["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/OperatingPilotLearningPlanActivationQueueResponse"
    }

    schemas = app.openapi()["components"]["schemas"]
    page_schema = schemas["OperatingPilotLearningPlanActivationQueueResponse"]
    item_schema = schemas["OperatingPilotLearningPlanActivationQueueItem"]
    assert set(page_schema["properties"]) == {
        "location_id", "items", "limit", "offset", "has_more", "next_offset", "total"
    }
    assert set(page_schema["required"]) == set(page_schema["properties"])
    assert page_schema["additionalProperties"] is False
    assert set(item_schema["properties"]) == {
        "learning_plan_id", "title", "competency_goals", "support_requested",
        "target_date", "status", "submitted_at", "approved_at",
    }
    assert set(item_schema["required"]) == set(item_schema["properties"])
    assert item_schema["additionalProperties"] is False
    parameters = {parameter["name"]: parameter for parameter in operation["parameters"]}
    assert parameters["limit"]["schema"]["minimum"] == 1
    assert parameters["limit"]["schema"]["maximum"] == 50
    assert parameters["offset"]["schema"]["minimum"] == 0
    assert parameters["offset"]["schema"]["maximum"] == 10000

    migration = (
        Path(__file__).resolve().parents[1]
        / "schemas/postgres/629_location_operating_pilot_learning_plan_activation.sql"
    ).read_text(encoding="utf-8")
    for field in (
        "learning_plan_id", "title", "competency_goals", "support_requested",
        "target_date", "status", "submitted_at", "approved_at",
    ):
        assert f"'{field}'" in migration
    assert "plan.status = 'submitted'" in migration
    assert "decision.decision = 'approved'" in migration
    assert "plan.party_id <> actor_party_id" in migration
    assert "NOT EXISTS" in migration
    assert "ORDER BY updated_at DESC, id DESC" in migration
    assert "requested_offset NOT BETWEEN 0 AND 10000" in migration


def test_learning_plan_activation_queue_binds_page_and_exact_activate_grant(monkeypatch):
    page = _page()
    app, calls = _route_app(monkeypatch, page)
    with TestClient(app) as client:
        response = client.get(
            f"/operator/api/operating-pilot/{LOCATION_ID}/learning-plan-activation-queue"
            "?limit=2&offset=4"
        )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert response.json() == page
    assert calls == [((OPERATOR_ID, LOCATION_ID), {"limit": 2, "offset": 4})]
    assert auth_route_policy(
        "GET",
        f"/operator/api/operating-pilot/{LOCATION_ID}/learning-plan-activation-queue",
        enabled=True,
    ) == {
        "resource": "operating_pilot", "action": "activate", "public": False,
        "location_id": LOCATION_ID, "scope_required": True, "operator_auth": True,
    }
    assert "party_id" not in response.json()["items"][0]
    assert "review_reason" not in response.json()["items"][0]


def test_learning_plan_activation_queue_caps_continuation(monkeypatch):
    page = _page(
        offset=10000,
        has_more=True,
        next_offset=10002,
        total=10002,
    )
    app, _calls = _route_app(monkeypatch, page)
    with TestClient(app) as client:
        response = client.get(
            f"/operator/api/operating-pilot/{LOCATION_ID}/learning-plan-activation-queue"
            "?limit=2&offset=10000"
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
        pytest.param(lambda page: page.pop("total"), id="missing-total"),
        pytest.param(lambda page: page.update(total=5), id="row-count-mismatch"),
        pytest.param(lambda page: page.update(next_offset=7), id="wrong-next-offset"),
        pytest.param(lambda page: page.update(has_more=False), id="terminal-with-continuation"),
        pytest.param(lambda page: page.update(items=page["items"][:1]), id="short-page"),
        pytest.param(lambda page: page["items"][0].update(learning_plan_id="not-a-uuid"), id="bad-plan-id"),
        pytest.param(lambda page: page["items"][0].update(party_id=OPERATOR_ID), id="identity-leak"),
        pytest.param(lambda page: page["items"][0].update(status="active"), id="wrong-status"),
        pytest.param(lambda page: page["items"][0].update(title="  padded  "), id="padded-title"),
        pytest.param(lambda page: page["items"][0].update(title="x" * 256), id="long-title"),
        pytest.param(lambda page: page["items"][0].update(target_date="not-a-date"), id="bad-target-date"),
        pytest.param(lambda page: page["items"][0].update(submitted_at="2026-10-24T12:00:00"), id="naive-submission"),
        pytest.param(lambda page: page["items"][0].update(approved_at="2026-10-24T11:00:00+00:00"), id="approval-before-submission"),
        pytest.param(lambda page: page["items"][0].update(competency_goals=["x" * 8001]), id="oversized-json-field"),
        pytest.param(lambda page: page.update(items=page["items"] + [deepcopy(page["items"][1])]), id="duplicate-plan-id"),
    ],
)
def test_malformed_learning_plan_activation_queue_is_sanitized_no_store(monkeypatch, mutation):
    page = _page()
    mutation(page)
    app, _calls = _route_app(monkeypatch, page)
    with TestClient(app) as client:
        response = client.get(
            f"/operator/api/operating-pilot/{LOCATION_ID}/learning-plan-activation-queue"
            "?limit=2&offset=4"
        )

    assert response.status_code == 503
    assert response.json() == {"error": "Operating learning-plan activation queue unavailable"}
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert response.headers["retry-after"] == "30"
    assert "private" not in response.text
    assert OPERATOR_ID not in response.text
