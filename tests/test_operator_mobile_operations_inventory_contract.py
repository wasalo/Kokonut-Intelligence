"""Strict response contract for the private mobile operations inventory."""

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
OTHER_LOCATION_ID = str(uuid4())
SEEN_AT = datetime(2026, 10, 28, 10, tzinfo=timezone.utc).isoformat()
SYNCED_AT = datetime(2026, 10, 28, 9, tzinfo=timezone.utc).isoformat()


def _inventory(**overrides):
    result = {
        "location_id": LOCATION_ID,
        "devices": [
            {
                "device_id": "collector-7",
                "status": "active",
                "last_seen_at": SEEN_AT,
                "last_sync_at": SYNCED_AT,
            }
        ],
        "queue_summary": {
            "device_count": 2,
            "active_device_count": 1,
            "pending_sync_count": 2,
            "synced_record_count": 8,
            "form_review_required_count": 3,
            "ineligible_synced_count": 1,
        },
    }
    return {**result, **overrides}


def _client(monkeypatch, service):
    session = SimpleNamespace(
        session_id=str(uuid4()),
        session_token_hash="e" * 64,
        operator=SimpleNamespace(operator_id=OPERATOR_ID),
    )

    class Provider:
        settings = SimpleNamespace(state_secret="test-only-state-secret-with-at-least-32-bytes")

        def authenticate_request(self, _request):
            return session

        def has_scope(self, operator_id, resource, action, location_id):
            return (
                operator_id == OPERATOR_ID
                and (resource, action) in {
                    ("mobile_device", "read"),
                    ("mobile_collection_review", "read"),
                }
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
    monkeypatch.setattr(
        "services.gateway.operator_mobile_review.get_mobile_operations_inventory", service
    )
    return TestClient(create_app(), cookies={SESSION_COOKIE: "synthetic-session"})


def test_mobile_inventory_returns_exact_source_projection_and_private_cache_headers(monkeypatch):
    calls = []

    def service(*args):
        calls.append(args)
        return _inventory()

    with _client(monkeypatch, service) as client:
        response = client.get(
            f"/operator/api/mobile/locations/{LOCATION_ID}/inventory",
            params={"device_limit": 1},
        )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert "Cookie" in response.headers["vary"]
    assert response.json() == _inventory()
    assert calls == [(OPERATOR_ID, LOCATION_ID, 1)]


@pytest.mark.parametrize(
    "inventory",
    [
        _inventory(secret="must not escape"),
        _inventory(location_id=OTHER_LOCATION_ID),
        _inventory(queue_summary={**_inventory()["queue_summary"], "private": 1}),
        _inventory(
            queue_summary={
                **_inventory()["queue_summary"],
                "active_device_count": 3,
            }
        ),
        _inventory(queue_summary={"pending_sync_count": 1}),
    ],
)
def test_mobile_inventory_rejects_malformed_or_out_of_scope_projection(monkeypatch, inventory):
    with _client(monkeypatch, lambda *_args: inventory) as client:
        response = client.get(
            f"/operator/api/mobile/locations/{LOCATION_ID}/inventory"
        )

    assert response.status_code == 500
    assert response.json() == {"error": "Mobile operations inventory unavailable"}
    assert response.headers["cache-control"] == "no-store"
    assert "Cookie" in response.headers["vary"]
    assert "must not escape" not in response.text


def test_mobile_inventory_preserves_empty_queue_summary_fallback(monkeypatch):
    inventory = {"location_id": LOCATION_ID, "devices": [], "queue_summary": {}}
    with _client(monkeypatch, lambda *_args: inventory) as client:
        response = client.get(
            f"/operator/api/mobile/locations/{LOCATION_ID}/inventory"
        )

    assert response.status_code == 200
    assert response.json() == inventory
    assert response.headers["cache-control"] == "no-store"


def test_mobile_inventory_preserves_tenant_denial(monkeypatch):
    def denied(*_args):
        raise TenantContextDenied("revoked")

    with _client(monkeypatch, denied) as client:
        response = client.get(
            f"/operator/api/mobile/locations/{LOCATION_ID}/inventory"
        )

    assert response.status_code == 403
    assert response.json() == {"error": "Tenant-qualified operator access is required"}
    assert response.headers["cache-control"] == "no-store"
    assert "Cookie" in response.headers["vary"]


def test_mobile_inventory_openapi_declares_exact_strict_projection(monkeypatch):
    with _client(monkeypatch, lambda *_args: _inventory()) as client:
        schema = client.app.openapi()

    operation = schema["paths"][
        "/operator/api/mobile/locations/{location_id}/inventory"
    ]["get"]
    assert operation["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/MobileOperationsInventoryResponse"
    }
    for model in (
        "MobileOperationsInventoryResponse",
        "MobileOperationsDeviceSummaryResponse",
        "MobileOperationsQueueSummaryResponse",
        "MobileOperationsEmptyQueueSummaryResponse",
    ):
        assert schema["components"]["schemas"][model]["additionalProperties"] is False
