"""Strict private response contract for the operating-pilot resource review queue."""

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
REQUEST_A = "b0000000-0000-4000-8000-000000000021"
REQUEST_B = "b0000000-0000-4000-8000-000000000020"
PATH = "/operator/api/operating-pilot/{location_id}/resource-review-queue"


def _request(request_id=REQUEST_A, *, requested_by="2026-10-29", **updates):
    item = {
        "resource_request_id": request_id,
        "resource_type": "Fencing",
        "description": "Repair the northern fence",
        "urgency": "high",
        "requested_by": requested_by,
    }
    item.update(updates)
    return item


def _page(*, items=None, **updates):
    page = {
        "location_id": LOCATION_ID,
        "items": [
            _request(REQUEST_A, requested_by="2026-10-29"),
            _request(REQUEST_B, requested_by="2026-10-28"),
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
        "services.gateway.operating_pilot_reads.get_location_operating_pilot_resource_review_queue",
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


def test_resource_review_openapi_matches_migration_projection(monkeypatch):
    app, _calls = _route_app(monkeypatch, _page())
    operation = app.openapi()["paths"][PATH]["get"]
    assert operation["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/OperatingPilotResourceReviewQueueResponse"
    }

    schemas = app.openapi()["components"]["schemas"]
    page_schema = schemas["OperatingPilotResourceReviewQueueResponse"]
    item_schema = schemas["OperatingPilotResourceReviewQueueItem"]
    assert set(page_schema["properties"]) == {
        "location_id", "items", "limit", "offset", "has_more", "next_offset", "total"
    }
    assert set(page_schema["required"]) == set(page_schema["properties"])
    assert page_schema["additionalProperties"] is False
    assert set(item_schema["properties"]) == {
        "resource_request_id", "resource_type", "description", "urgency", "requested_by"
    }
    assert set(item_schema["required"]) == set(item_schema["properties"])
    assert item_schema["additionalProperties"] is False
    assert item_schema["properties"]["resource_type"]["pattern"] == (
        r"^[A-Za-z0-9][A-Za-z0-9 _./-]{0,49}$"
    )
    assert item_schema["properties"]["description"]["maxLength"] == 2000
    assert item_schema["properties"]["urgency"]["enum"] == [
        "low", "medium", "high", "critical"
    ]
    parameters = {parameter["name"]: parameter for parameter in operation["parameters"]}
    assert parameters["limit"]["schema"]["minimum"] == 1
    assert parameters["limit"]["schema"]["maximum"] == 50
    assert parameters["offset"]["schema"]["minimum"] == 0
    assert parameters["offset"]["schema"]["maximum"] == 10000

    migration = (
        Path(__file__).resolve().parents[1]
        / "schemas/postgres/571_location_operating_pilot_resource_review_queue.sql"
    ).read_text(encoding="utf-8")
    for field in (
        "resource_request_id", "resource_type", "description", "urgency", "requested_by"
    ):
        assert f"'{field}'" in migration
    assert "ORDER BY requested_by DESC, id DESC" in migration
    assert "'total', (SELECT count(*) FROM eligible)" in migration
    draft_migration = (
        Path(__file__).resolve().parents[1]
        / "schemas/postgres/567_location_operating_pilot_resource_request_draft.sql"
    ).read_text(encoding="utf-8")
    assert "requested_resource_type !~ '^[A-Za-z0-9][A-Za-z0-9 _./-]{0,49}$'" in draft_migration
    assert "char_length(pg_catalog.btrim(requested_description)) NOT BETWEEN 1 AND 2000" in draft_migration


def test_resource_review_binds_location_page_policy_and_redacts_identity(monkeypatch):
    page = _page()
    app, calls = _route_app(monkeypatch, page)
    with TestClient(app) as client:
        response = client.get(
            f"/operator/api/operating-pilot/{LOCATION_ID}/resource-review-queue"
            "?limit=2&offset=4"
        )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert response.json() == page
    assert calls == [((OPERATOR_ID, LOCATION_ID), {"limit": 2, "offset": 4})]
    assert auth_route_policy(
        "GET", f"/operator/api/operating-pilot/{LOCATION_ID}/resource-review-queue", enabled=True
    ) == {
        "resource": "operating_pilot", "action": "review", "public": False,
        "location_id": LOCATION_ID, "scope_required": True, "operator_auth": True,
    }
    assert "requested_by_party_id" not in response.json()["items"][0]
    assert "operator_id" not in response.json()["items"][0]


def test_resource_review_caps_unrequestable_continuation(monkeypatch):
    page = _page(
        items=[
            _request(REQUEST_A, requested_by="2026-10-29"),
            _request(REQUEST_B, requested_by="2026-10-28"),
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
            f"/operator/api/operating-pilot/{LOCATION_ID}/resource-review-queue"
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
        pytest.param(lambda page: page.update(party_id=OPERATOR_ID), id="page-identity-leak"),
        pytest.param(lambda page: page.pop("total"), id="missing-total"),
        pytest.param(lambda page: page.update(total=5), id="wrong-total"),
        pytest.param(lambda page: page.update(next_offset=7), id="wrong-next-offset"),
        pytest.param(lambda page: page.update(has_more=False), id="terminal-with-continuation"),
        pytest.param(lambda page: page.update(items=page["items"][:1]), id="short-page"),
        pytest.param(lambda page: page["items"].reverse(), id="wrong-sql-order"),
        pytest.param(lambda page: page["items"][0].update(resource_request_id="not-a-uuid"), id="bad-id"),
        pytest.param(lambda page: page["items"][0].update(requested_by_party_id=OPERATOR_ID), id="requester-leak"),
        pytest.param(lambda page: page["items"][0].update(receipt_digest="private"), id="receipt-leak"),
        pytest.param(lambda page: page["items"][0].update(resource_type="bad,type"), id="invalid-resource-type"),
        pytest.param(lambda page: page["items"][0].update(resource_type=" "), id="blank-resource-type"),
        pytest.param(lambda page: page["items"][0].update(resource_type="x" * 51), id="long-resource-type"),
        pytest.param(lambda page: page["items"][0].update(description="  padded  "), id="padded-description"),
        pytest.param(lambda page: page["items"][0].update(description=" "), id="blank-description"),
        pytest.param(lambda page: page["items"][0].update(description="private narrative" * 118), id="long-description"),
        pytest.param(lambda page: page["items"][0].update(description="bad\x00text"), id="nul-description"),
        pytest.param(lambda page: page["items"][0].update(urgency="immediate"), id="invalid-urgency"),
        pytest.param(lambda page: page["items"][0].update(requested_by="not-a-date"), id="invalid-date"),
        pytest.param(lambda page: page.update(items=page["items"] + [deepcopy(page["items"][1])]), id="duplicate-id"),
    ],
)
def test_malformed_resource_review_response_is_sanitized_no_store(monkeypatch, mutation):
    page = _page()
    mutation(page)
    app, _calls = _route_app(monkeypatch, page)
    with TestClient(app) as client:
        response = client.get(
            f"/operator/api/operating-pilot/{LOCATION_ID}/resource-review-queue"
            "?limit=2&offset=4"
        )

    assert response.status_code == 500
    assert response.json() == {"error": "Operating resource review queue unavailable"}
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert "private narrative" not in response.text
    assert OPERATOR_ID not in response.text
