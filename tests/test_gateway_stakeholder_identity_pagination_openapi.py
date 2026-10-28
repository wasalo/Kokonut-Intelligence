"""Route-level pagination bounds for the stakeholder identity review queue."""

from types import SimpleNamespace

import pytest

pytest.importorskip("fastapi")
from fastapi import APIRouter, FastAPI  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

LOCATION_ID = "11111111-1111-4111-8111-111111111111"
OPERATOR_ID = "22222222-2222-4222-8222-222222222222"


def _app(monkeypatch, calls, result=None):
    from services.gateway.stakeholder_identity_routes import register_stakeholder_identity_routes

    def list_cases(*args, **kwargs):
        calls.append((args, kwargs))
        return result or {"location_id": LOCATION_ID, "items": [], "next_cursor": None}

    monkeypatch.setattr(
        "services.gateway.stakeholder_identity.list_location_party_identity_cases",
        list_cases,
    )
    import psycopg2

    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_stakeholder_identity_routes(router, object(), run_in_threadpool, psycopg2)
    app = FastAPI()
    app.include_router(router)

    @app.middleware("http")
    async def add_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    return app


def test_stakeholder_identity_limit_is_bounded_in_openapi(monkeypatch):
    calls = []
    app = _app(monkeypatch, calls)

    operation = app.openapi()["paths"]["/operator/api/stakeholder-identity/{location_id}/cases"]["get"]
    limit = next(parameter for parameter in operation["parameters"] if parameter["name"] == "limit")

    assert limit["schema"] == {
        "type": "integer",
        "maximum": 50,
        "minimum": 1,
        "default": 50,
        "title": "Limit",
    }


def test_stakeholder_identity_openapi_exposes_strict_private_page_contract(monkeypatch):
    app = _app(monkeypatch, [])
    operation = app.openapi()["paths"][
        "/operator/api/stakeholder-identity/{location_id}/cases"
    ]["get"]
    schemas = app.openapi()["components"]["schemas"]
    response_schema = schemas["IdentityReviewPage"]
    case_schema = schemas["IdentityReviewCase"]

    assert operation["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/IdentityReviewPage"
    }
    assert response_schema["additionalProperties"] is False
    assert response_schema["properties"]["items"]["maxItems"] == 50
    assert case_schema["additionalProperties"] is False
    assert case_schema["properties"]["match_method"]["enum"] == [
        "manual", "exact_identifier", "verified_document", "community_review"
    ]
    assert case_schema["properties"]["evidence_code"]["enum"] == [
        "verified_identifier", "document_review", "participant_confirmation", "community_review"
    ]
    assert not {
        "source_profile_id", "raw_feedback", "reviewer_operator_id"
    }.intersection(case_schema["properties"])
    assert operation["responses"]["500"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/IdentityReviewError"
    }


def test_stakeholder_identity_route_returns_valid_request_bound_page_no_store(monkeypatch):
    case_id = "33333333-3333-4333-8333-333333333333"
    created_at = "2026-10-28T12:00:00+00:00"
    result = {
        "location_id": LOCATION_ID,
        "items": [{
            "case_id": case_id,
            "candidate_party_id": "44444444-4444-4444-8444-444444444444",
            "candidate_name": "Canonical party",
            "source_label": "Private source",
            "match_method": "verified_document",
            "evidence_code": "document_review",
            "confidence": 0.9,
            "created_at": created_at,
        }],
        "next_cursor": {"created_at": created_at, "case_id": case_id},
    }
    calls = []
    app = _app(monkeypatch, calls, result)

    with TestClient(app) as client:
        response = client.get(
            f"/operator/api/stakeholder-identity/{LOCATION_ID}/cases",
            params={
                "limit": 1,
                "cursor_created_at": "2026-10-28T13:00:00+00:00",
                "cursor_case_id": "55555555-5555-4555-8555-555555555555",
            },
        )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["location_id"] == LOCATION_ID
    assert response.json()["next_cursor"]["case_id"] == case_id
    assert calls[0][1]["limit"] == 1
    assert calls[0][1]["cursor_created_at"] == "2026-10-28T13:00:00+00:00"
    assert calls[0][1]["cursor_case_id"] == "55555555-5555-4555-8555-555555555555"


@pytest.mark.parametrize(
    "result",
    [
        {"location_id": "55555555-5555-4555-8555-555555555555", "items": [], "next_cursor": None},
        {"location_id": LOCATION_ID, "items": [], "next_cursor": {
            "created_at": "2026-10-28T12:00:00+00:00",
            "case_id": "33333333-3333-4333-8333-333333333333",
        }},
        {"location_id": LOCATION_ID, "items": [{"source_profile_id": "private"}], "next_cursor": None},
    ],
)
def test_stakeholder_identity_malformed_or_private_service_page_fails_closed_no_store(
    monkeypatch, result
):
    calls = []
    app = _app(monkeypatch, calls, result)

    with TestClient(app) as client:
        response = client.get(f"/operator/api/stakeholder-identity/{LOCATION_ID}/cases")

    assert response.status_code == 500
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {"error": "Identity review queue unavailable"}


@pytest.mark.parametrize("limit", [0, 51])
def test_invalid_limit_fails_before_service_access(monkeypatch, limit):
    calls = []
    app = _app(monkeypatch, calls)

    with TestClient(app) as client:
        response = client.get(
            f"/operator/api/stakeholder-identity/{LOCATION_ID}/cases",
            params={"limit": limit},
        )

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["query", "limit"]
    assert calls == []
