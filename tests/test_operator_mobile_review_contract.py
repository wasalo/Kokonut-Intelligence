"""Strict route/OpenAPI contract for the mobile collection review queue."""

import json
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError

pytest.importorskip("fastapi")
from starlette.testclient import TestClient  # noqa: E402

from services.common.tenant_context import TenantContextDenied  # noqa: E402
from services.gateway.app import create_app  # noqa: E402
from services.gateway.mobile_collection_review_responses import (  # noqa: E402
    MobileCollectionReviewDetailResponse,
)
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


def _detail(**overrides):
    event = {
        "id": str(uuid4()),
        "actor_operator_id": OPERATOR_ID,
        "decision": "reviewed",
        "reason": "Compared with the field sheet",
        "evidence": [{"source": "field_sheet", "basis": "Date and quantity match"}],
        "created_at": SYNCED_AT,
    }
    return {
        **_collection(),
        "consent_policy_status": "required",
        "photo_count": 1,
        "payload": {"observed_quantity_kg": 12, "custom_form_field": {"notes": "checked"}},
        "review_events": [event],
        **overrides,
    }


def _client(monkeypatch, service, detail_service=None):
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
                and action in {"read", "read_detail"}
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
    monkeypatch.setattr(
        "services.gateway.operator_mobile_review.get_mobile_collection",
        detail_service or (lambda *_args: None),
    )
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


def test_mobile_collection_detail_returns_exact_bound_flexible_payload(monkeypatch):
    calls = []
    detail = _detail()

    def service(*args):
        calls.append(args)
        return detail

    with _client(monkeypatch, lambda *_args: [], service) as client:
        response = client.get(
            f"/operator/api/mobile-collection-review-queue/{COLLECTION_ID}",
            params={"location_id": LOCATION_ID},
        )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert "Cookie" in response.headers["vary"]
    expected = MobileCollectionReviewDetailResponse.model_validate({"data": detail}).model_dump(
        mode="json"
    )
    assert response.json() == expected
    assert set(response.json()["data"]) == set(_collection()) | {
        "consent_policy_status",
        "photo_count",
        "payload",
        "review_events",
    }
    assert response.json()["data"]["payload"]["custom_form_field"] == {"notes": "checked"}
    assert calls == [(OPERATOR_ID, COLLECTION_ID, LOCATION_ID)]


@pytest.mark.parametrize(
    "detail",
    [
        _detail(id=str(uuid4())),
        _detail(location_id=str(uuid4())),
        _detail(unexpected="private marker"),
        _detail(review_events=[{**_detail()["review_events"][0], "decision": "published"}]),
        _detail(review_events=[{**_detail()["review_events"][0], "reason": " "}]),
        _detail(
            review_events=[
                {
                    **_detail()["review_events"][0],
                    "created_at": "2026-10-28T11:00:00",
                }
            ]
        ),
        _detail(
            review_events=[
                {
                    **_detail()["review_events"][0],
                    "evidence": [{"source": "field_sheet", "basis": " "}],
                }
            ]
        ),
        _detail(review_events=[_detail()["review_events"][0]] * 21),
        _detail(
            review_events=[
                {
                    **_detail()["review_events"][0],
                    "evidence": [
                        {"source": "field_sheet", "basis": "checked"}
                    ] * 21,
                }
            ]
        ),
        _detail(payload={"private_marker": "x" * 524289}),
    ],
)
def test_mobile_collection_detail_rejects_invalid_scope_or_unbounded_shape(monkeypatch, detail):
    with _client(monkeypatch, lambda *_args: [], lambda *_args: detail) as client:
        response = client.get(
            f"/operator/api/mobile-collection-review-queue/{COLLECTION_ID}",
            params={"location_id": LOCATION_ID},
        )

    assert response.status_code == 500
    assert response.json() == {"error": "Mobile collection review detail unavailable"}
    assert response.headers["cache-control"] == "no-store"
    assert "Cookie" in response.headers["vary"]
    assert "private_marker" not in response.text


def test_mobile_collection_detail_maps_service_payload_limit_to_sanitized_413(monkeypatch):
    from services.gateway.operator_mobile_review import MobileCollectionPayloadTooLarge

    def too_large(*_args):
        raise MobileCollectionPayloadTooLarge("private collection content")

    with _client(monkeypatch, lambda *_args: [], too_large) as client:
        response = client.get(
            f"/operator/api/mobile-collection-review-queue/{COLLECTION_ID}",
            params={"location_id": LOCATION_ID},
        )

    assert response.status_code == 413
    assert response.json() == {"error": "Collection exceeds the console read limit"}
    assert response.headers["cache-control"] == "no-store"
    assert "Cookie" in response.headers["vary"]
    assert "private collection content" not in response.text


def test_mobile_collection_detail_accepts_exact_serialized_payload_limit():
    max_bytes = 524288
    exact_payload = {"x": "a" * (max_bytes - len('{"x": ""}'))}
    detail = MobileCollectionReviewDetailResponse.model_validate(
        {"data": _detail(payload=exact_payload)}
    )
    serialized_size = len(
        json.dumps(detail.data.payload, ensure_ascii=False, allow_nan=False).encode("utf-8")
    )
    assert serialized_size == max_bytes

    with pytest.raises(ValidationError):
        MobileCollectionReviewDetailResponse.model_validate(
            {"data": _detail(payload={"x": "a" * (max_bytes - len('{"x": ""}')) + "a"})}
        )


def test_mobile_collection_detail_openapi_declares_strict_nested_contract(monkeypatch):
    with _client(monkeypatch, lambda *_args: []) as client:
        schema = client.app.openapi()

    operation = schema["paths"][
        "/operator/api/mobile-collection-review-queue/{collection_id}"
    ]["get"]
    assert operation["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/MobileCollectionReviewDetailResponse"
    }
    for model in (
        "MobileCollectionReviewDetailResponse",
        "MobileCollectionReviewDetailResponseData",
        "MobileCollectionReviewEventResponse",
        "MobileCollectionReviewEvidenceResponse",
    ):
        assert schema["components"]["schemas"][model]["additionalProperties"] is False
