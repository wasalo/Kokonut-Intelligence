"""Strict route/OpenAPI contract for the mobile collection review queue."""

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

pytest.importorskip("fastapi")
from starlette.testclient import TestClient  # noqa: E402

from services.common.tenant_context import TenantContextDenied  # noqa: E402
from services.gateway.app import create_app  # noqa: E402
from services.gateway.operator_auth import SESSION_COOKIE  # noqa: E402

OPERATOR_ID = str(uuid4())
LOCATION_ID = str(uuid4())
COLLECTION_ID = str(uuid4())
FORM_REVISION_ID = str(uuid4())
COLLECTED_AT = datetime(2026, 10, 28, 10, tzinfo=timezone.utc).isoformat()
SYNCED_AT = datetime(2026, 10, 28, 11, tzinfo=timezone.utc).isoformat()


def _collection(**overrides):
    result = {
        "id": COLLECTION_ID,
        "location_id": LOCATION_ID,
        "form_id": "field_activity",
        "form_version": "2.1.0",
        "collection_type": "farm_activity",
        "collected_at": COLLECTED_AT,
        "synced_at": SYNCED_AT,
        "form_validation_status": "active",
        "consent_validation_status": "granted",
        "form_review_required": True,
        "form_revision_id": FORM_REVISION_ID,
        "form_name": "Field Activity",
        "form_revision_status": "active",
        "eligible_for_use": False,
        "eligibility_reason": "review_required",
        "review_state": "pending_review",
    }
    return {**result, **overrides}


def _client(monkeypatch, service):
    session = SimpleNamespace(
        session_id=str(uuid4()),
        session_token_hash="b" * 64,
        operator=SimpleNamespace(operator_id=OPERATOR_ID),
    )

    class Provider:
        settings = SimpleNamespace(state_secret="test-only-state-secret-with-at-least-32-bytes")

        def authenticate_request(self, _request):
            return session

        def has_scope(self, operator_id, resource, action, location_id):
            return (
                operator_id == OPERATOR_ID
                and resource == "mobile_collection_review"
                and action == "read"
                and location_id == LOCATION_ID
            )

    class InMemoryAudit:
        def __init__(self):
            pass

        def replay_pending(self, _limit=100):
            return 0

        def log(self, **_event):
            return None

        def capture_status(self):
            return "ok"

    monkeypatch.setattr("services.gateway.operator_auth.create_provider", lambda: Provider())
    monkeypatch.setattr("services.gateway.audit.GatewayAudit", InMemoryAudit)
    monkeypatch.setattr("services.gateway.operator_mobile_review.list_mobile_collections", service)
    return TestClient(create_app(), cookies={SESSION_COOKIE: "synthetic-session"})


def test_mobile_collection_queue_returns_exact_scoped_summary_and_no_store_headers(monkeypatch):
    calls = []

    def service(*args):
        calls.append(args)
        return [_collection()]

    with _client(monkeypatch, service) as client:
        response = client.get(
            "/operator/api/mobile-collection-review-queue",
            params={"location_id": LOCATION_ID},
        )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert "Cookie" in response.headers["vary"]
    assert response.json() == {"data": [_collection()], "location_id": LOCATION_ID}
    assert calls == [(OPERATOR_ID, LOCATION_ID, 50)]
    assert "payload" not in response.json()["data"][0]
    assert "participant_id" not in response.json()["data"][0]


@pytest.mark.parametrize(
    "collection",
    [
        _collection(payload={"participant": "must not escape"}),
        _collection(location_id=str(uuid4())),
        _collection(form_validation_status="unknown"),
        _collection(review_state="blocked_by_eligibility"),
        _collection(eligible_for_use=True, eligibility_reason="eligible"),
        _collection(eligible_for_use=False, eligibility_reason="eligible"),
        _collection(form_review_required=False, eligible_for_use=True, review_state="blocked_by_eligibility"),
    ],
)
def test_mobile_collection_queue_rejects_malformed_or_out_of_scope_rows(monkeypatch, collection):
    with _client(monkeypatch, lambda *_args: [collection]) as client:
        response = client.get(
            "/operator/api/mobile-collection-review-queue",
            params={"location_id": LOCATION_ID},
        )

    assert response.status_code == 500
    assert response.json() == {"error": "Mobile collection review queue unavailable"}
    assert response.headers["cache-control"] == "no-store"
    assert "Cookie" in response.headers["vary"]
    assert "must not escape" not in response.text


def test_mobile_collection_queue_preserves_tenant_denial(monkeypatch):
    def denied(*_args):
        raise TenantContextDenied("revoked")

    with _client(monkeypatch, denied) as client:
        response = client.get(
            "/operator/api/mobile-collection-review-queue",
            params={"location_id": LOCATION_ID},
        )

    assert response.status_code == 403
    assert response.json() == {"error": "Tenant-qualified operator access is required"}
    assert response.headers["cache-control"] == "no-store"
    assert "Cookie" in response.headers["vary"]


def test_mobile_collection_queue_openapi_declares_strict_exact_projection(monkeypatch):
    with _client(monkeypatch, lambda *_args: []) as client:
        schema = client.app.openapi()

    operation = schema["paths"]["/operator/api/mobile-collection-review-queue"]["get"]
    assert operation["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/MobileCollectionReviewQueueResponse"
    }
    for model in (
        "MobileCollectionReviewQueueResponse",
        "MobileCollectionReviewSummaryResponse",
    ):
        assert schema["components"]["schemas"][model]["additionalProperties"] is False
