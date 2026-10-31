"""Route-level contract for stakeholder trust pagination bounds."""

from types import SimpleNamespace

import pytest

pytest.importorskip("fastapi")
from fastapi import FastAPI  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

LOCATION_ID = "11111111-1111-4111-8111-111111111111"
PARTY_ID = "22222222-2222-4222-8222-222222222222"


def _app(service_calls, result=None):
    from services.gateway.stakeholder_trust_routes import register_stakeholder_trust_routes

    class FakePostgresError(Exception):
        pass

    async def run_inline(function, *args, **kwargs):
        service_calls.append((function, args, kwargs))
        return result or {
            "location_id": LOCATION_ID,
            "party_id": PARTY_ID,
            "evidence": [],
            "next_cursor": None,
        }

    app = FastAPI()

    @app.middleware("http")
    async def attach_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id="00000000-0000-0000-0000-000000000001")
        )
        return await call_next(request)

    register_stakeholder_trust_routes(
        app.router,
        SimpleNamespace(),
        run_inline,
        SimpleNamespace(Error=FakePostgresError),
    )
    return app


def test_stakeholder_trust_openapi_publishes_service_page_bounds():
    app = _app([])
    operation = app.openapi()["paths"][
        "/operator/api/stakeholder-trust/{location_id}/parties/{party_id}/identity-evidence"
    ]["get"]
    limit = next(parameter for parameter in operation["parameters"] if parameter["name"] == "limit")

    assert limit["schema"]["type"] == "integer"
    assert limit["schema"]["default"] == 50
    assert limit["schema"]["minimum"] == 1
    assert limit["schema"]["maximum"] == 50


def test_stakeholder_trust_openapi_exposes_strict_location_evidence_contract():
    app = _app([])
    operation = app.openapi()["paths"][
        "/operator/api/stakeholder-trust/{location_id}/parties/{party_id}/identity-evidence"
    ]["get"]
    schemas = app.openapi()["components"]["schemas"]
    page_schema = schemas["StakeholderTrustEvidencePage"]
    evidence_schema = schemas["StakeholderIdentityTrustEvidence"]

    assert operation["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/StakeholderTrustEvidencePage"
    }
    assert page_schema["additionalProperties"] is False
    assert page_schema["properties"]["evidence"]["maxItems"] == 50
    assert evidence_schema["additionalProperties"] is False
    assert evidence_schema["properties"]["dimension"]["const"] == "identity"
    assert evidence_schema["properties"]["direction"]["const"] == "supporting"
    assert not {
        "source_profile_id", "reviewer_operator_id", "raw_feedback", "global_score", "score"
    }.intersection(evidence_schema["properties"])
    assert operation["responses"]["500"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/StakeholderTrustError"
    }


def test_stakeholder_trust_page_is_bound_to_path_ids_and_cursor():
    calls = []
    evidence_id = "33333333-3333-4333-8333-333333333333"
    reviewed_at = "2026-10-28T12:00:00+00:00"
    app = _app(calls, {
        "location_id": LOCATION_ID,
        "party_id": PARTY_ID,
        "evidence": [{
            "evidence_id": evidence_id,
            "dimension": "identity",
            "direction": "supporting",
            "evidence_code": "document_review",
            "match_method": "verified_document",
            "confidence": 0.9,
            "reviewed_at": reviewed_at,
        }],
        "next_cursor": {"reviewed_at": reviewed_at, "evidence_id": evidence_id},
    })
    path = (
        f"/operator/api/stakeholder-trust/{LOCATION_ID}/parties/{PARTY_ID}/identity-evidence"
    )

    with TestClient(app) as client:
        response = client.get(path, params={
            "limit": 1,
            "cursor_reviewed_at": "2026-10-28T13:00:00+00:00",
            "cursor_evidence_id": "55555555-5555-4555-8555-555555555555",
        })

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {
        "location_id": LOCATION_ID,
        "party_id": PARTY_ID,
        "evidence": [{
            "evidence_id": evidence_id,
            "dimension": "identity",
            "direction": "supporting",
            "evidence_code": "document_review",
            "match_method": "verified_document",
            "confidence": 0.9,
            "reviewed_at": reviewed_at,
        }],
        "next_cursor": {"reviewed_at": reviewed_at, "evidence_id": evidence_id},
    }
    assert calls[0][2]["limit"] == 1
    assert calls[0][2]["cursor_reviewed_at"] == "2026-10-28T13:00:00+00:00"
    assert calls[0][2]["cursor_evidence_id"] == "55555555-5555-4555-8555-555555555555"


@pytest.mark.parametrize(
    "result",
    [
        {"location_id": "33333333-3333-4333-8333-333333333333", "party_id": PARTY_ID,
         "evidence": [], "next_cursor": None},
        {"location_id": LOCATION_ID, "party_id": "33333333-3333-4333-8333-333333333333",
         "evidence": [], "next_cursor": None},
        {"location_id": LOCATION_ID, "party_id": PARTY_ID, "evidence": [],
         "next_cursor": None, "global_score": 0.8},
    ],
)
def test_stakeholder_trust_rejects_mismatched_or_private_projection_no_store(result):
    service_calls = []
    app = _app(service_calls, result)

    with TestClient(app) as client:
        response = client.get(
            f"/operator/api/stakeholder-trust/{LOCATION_ID}/parties/{PARTY_ID}/identity-evidence"
        )

    assert response.status_code == 500
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {"error": "Stakeholder trust evidence unavailable"}


@pytest.mark.parametrize("limit", [0, 51, -1, "not-a-number"])
def test_invalid_stakeholder_trust_limit_fails_before_service(limit):
    service_calls = []
    app = _app(service_calls)

    with TestClient(app) as client:
        response = client.get(
            "/operator/api/stakeholder-trust/location/parties/party/identity-evidence",
            params={"limit": limit},
        )

    assert response.status_code == 422
    assert service_calls == []
