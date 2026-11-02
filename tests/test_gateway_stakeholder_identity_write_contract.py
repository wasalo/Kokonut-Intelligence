"""Focused HTTP and OpenAPI contracts for stakeholder identity writes."""

from types import SimpleNamespace

import pytest

pytest.importorskip("fastapi")
from fastapi import APIRouter, FastAPI  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

LOCATION_ID = "11111111-1111-4111-8111-111111111111"
OPERATOR_ID = "22222222-2222-4222-8222-222222222222"
PROFILE_ID = "33333333-3333-4333-8333-333333333333"
PARTY_ID = "44444444-4444-4444-8444-444444444444"
CASE_ID = "55555555-5555-4555-8555-555555555555"
REQUEST_ID = "66666666-6666-4666-8666-666666666666"
REVIEWER_ID = "77777777-7777-4777-8777-777777777777"
CREATED_AT = "2026-10-29T12:30:00+00:00"


def _app(monkeypatch, *, proposal_result=None, decision_result=None):
    from services.gateway import stakeholder_identity
    from services.gateway.stakeholder_identity_routes import register_stakeholder_identity_routes

    calls = []

    def propose(*args):
        calls.append(("proposal", args))
        return proposal_result or {
            "case_id": CASE_ID,
            "case_status": "proposed",
            "created_at": CREATED_AT,
        }

    def decide(*args):
        calls.append(("decision", args))
        return decision_result or {
            "case_id": CASE_ID,
            "case_status": "approved",
            "reviewer_operator_id": OPERATOR_ID,
            "created_at": CREATED_AT,
        }

    monkeypatch.setattr(stakeholder_identity, "propose_location_party_identity", propose)
    monkeypatch.setattr(stakeholder_identity, "decide_location_party_identity", decide)

    async def run_inline(function, *args, **kwargs):
        return function(*args, **kwargs)

    import psycopg2

    router = APIRouter()
    register_stakeholder_identity_routes(router, object(), run_inline, psycopg2)
    app = FastAPI()
    app.include_router(router)

    @app.middleware("http")
    async def install_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    return app, calls


def _proposal_body(**overrides):
    body = {
        "source_profile_id": PROFILE_ID,
        "candidate_party_id": PARTY_ID,
        "request_id": REQUEST_ID,
        "match_method": "verified_document",
        "evidence_code": "document_review",
        "confidence": 0.875,
    }
    body.update(overrides)
    return body


def _decision_body(**overrides):
    body = {
        "request_id": REQUEST_ID,
        "decision": "approve",
        "reason_code": "match_confirmed",
    }
    body.update(overrides)
    return body


def test_write_openapi_contracts_are_strict_and_document_errors(monkeypatch):
    app, _calls = _app(monkeypatch)
    spec = app.openapi()
    path = "/operator/api/stakeholder-identity/{location_id}/cases"
    proposal = spec["paths"][path]["post"]
    decision = spec["paths"][path + "/{case_id}/decision"]["post"]
    proposal_schema = proposal["requestBody"]["content"]["application/json"]["schema"]
    decision_schema = decision["requestBody"]["content"]["application/json"]["schema"]

    assert proposal_schema["additionalProperties"] is False
    assert set(proposal_schema["required"]) == {
        "source_profile_id", "candidate_party_id", "request_id", "match_method",
        "evidence_code", "confidence",
    }
    assert proposal_schema["properties"]["match_method"]["enum"] == [
        "manual", "exact_identifier", "verified_document", "community_review"
    ]
    assert proposal_schema["properties"]["evidence_code"]["enum"] == [
        "verified_identifier", "document_review", "participant_confirmation", "community_review"
    ]
    confidence = proposal_schema["properties"]["confidence"]
    assert confidence["minimum"] == 0
    assert confidence["maximum"] == 1
    assert confidence["multipleOf"] == 0.0001

    assert decision_schema["additionalProperties"] is False
    assert set(decision_schema["required"]) == {"request_id", "decision", "reason_code"}
    assert decision_schema["properties"]["decision"]["enum"] == ["approve", "reject"]
    assert decision_schema["properties"]["reason_code"]["enum"] == [
        "match_confirmed", "insufficient_evidence", "conflicting_identity", "source_not_eligible"
    ]
    schemas = spec["components"]["schemas"]
    proposal_response = schemas["IdentityCaseProposalResponse"]
    decision_response = schemas["IdentityCaseDecisionResponse"]
    assert proposal_response["additionalProperties"] is False
    assert set(proposal_response["properties"]) == {"case_id", "case_status", "created_at"}
    assert decision_response["additionalProperties"] is False
    assert set(decision_response["properties"]) == {
        "case_id", "case_status", "created_at", "reviewer_operator_id"
    }
    assert decision_response["properties"]["case_status"]["enum"] == ["approved", "rejected"]
    assert proposal["responses"]["201"]["content"]["application/json"]["schema"]["$ref"].endswith(
        "IdentityCaseProposalResponse"
    )
    assert decision["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith(
        "IdentityCaseDecisionResponse"
    )
    assert {"400", "403", "404", "409", "500", "503"}.issubset(proposal["responses"])


def test_valid_proposal_and_independent_decision_return_exact_no_store_contract(monkeypatch):
    app, calls = _app(monkeypatch)
    with TestClient(app) as client:
        proposal = client.post(
            f"/operator/api/stakeholder-identity/{LOCATION_ID}/cases",
            json=_proposal_body(),
        )
        decision = client.post(
            f"/operator/api/stakeholder-identity/{LOCATION_ID}/cases/{CASE_ID}/decision",
            json=_decision_body(),
        )

    assert proposal.status_code == 201
    assert proposal.headers["cache-control"] == "no-store"
    assert proposal.json() == {
        "case_id": CASE_ID,
        "case_status": "proposed",
        "created_at": CREATED_AT,
    }
    assert decision.status_code == 200
    assert decision.headers["cache-control"] == "no-store"
    assert decision.json() == {
        "case_id": CASE_ID,
        "case_status": "approved",
        "reviewer_operator_id": OPERATOR_ID,
        "created_at": CREATED_AT,
    }
    assert calls == [
        (
            "proposal",
            (
                OPERATOR_ID, LOCATION_ID, PROFILE_ID, PARTY_ID, REQUEST_ID,
                "verified_document", "document_review", 0.875,
            ),
        ),
        (
            "decision",
            (OPERATOR_ID, LOCATION_ID, CASE_ID, REQUEST_ID, "approve", "match_confirmed"),
        ),
    ]


@pytest.mark.parametrize(
    "override",
    [
        {"source_profile_id": "not-a-uuid"},
        {"match_method": "unsupported"},
        {"evidence_code": "free_text"},
        {"confidence": 1.0001},
        {"confidence": 0.12345},
        {"confidence": "0.7"},
        {"raw_feedback": "private participant statement"},
    ],
)
def test_invalid_proposal_is_sanitized_and_rejected_before_service(monkeypatch, override):
    app, calls = _app(monkeypatch)
    with TestClient(app) as client:
        response = client.post(
            f"/operator/api/stakeholder-identity/{LOCATION_ID}/cases",
            json=_proposal_body(**override),
        )

    assert response.status_code == 400
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {"error": "Identity request is invalid"}
    assert calls == []


@pytest.mark.parametrize(
    "override",
    [
        {"request_id": "not-a-uuid"},
        {"decision": "defer"},
        {"reason_code": "free_text"},
        {"participant_id": "spoofed"},
    ],
)
def test_invalid_decision_is_sanitized_and_rejected_before_service(monkeypatch, override):
    app, calls = _app(monkeypatch)
    with TestClient(app) as client:
        response = client.post(
            f"/operator/api/stakeholder-identity/{LOCATION_ID}/cases/{CASE_ID}/decision",
            json=_decision_body(**override),
        )

    assert response.status_code == 400
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {"error": "Identity request is invalid"}
    assert calls == []


@pytest.mark.parametrize(
    ("path", "result", "body"),
    [
        (
            f"/operator/api/stakeholder-identity/{LOCATION_ID}/cases",
            {"case_id": "not-a-uuid", "case_status": "proposed", "created_at": CREATED_AT},
            _proposal_body(),
        ),
        (
            f"/operator/api/stakeholder-identity/{LOCATION_ID}/cases/{CASE_ID}/decision",
            {
                "case_id": CASE_ID,
                "case_status": "approved",
                "reviewer_operator_id": REVIEWER_ID,
                "created_at": "not-a-timestamp",
            },
            _decision_body(),
        ),
        (
            f"/operator/api/stakeholder-identity/{LOCATION_ID}/cases/{CASE_ID}/decision",
            {
                "case_id": CASE_ID,
                "case_status": "proposed",
                "reviewer_operator_id": REVIEWER_ID,
                "created_at": CREATED_AT,
            },
            _decision_body(),
        ),
    ],
)
def test_malformed_service_result_fails_closed_without_leaking_details(monkeypatch, path, result, body):
    if path.endswith("/decision"):
        app, _calls = _app(monkeypatch, decision_result=result)
    else:
        app, _calls = _app(monkeypatch, proposal_result=result)

    with TestClient(app) as client:
        response = client.post(path, json=body)

    assert response.status_code == 500
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["error"] in {
        "Identity proposal unavailable", "Identity decision unavailable"
    }
