"""Strict response contract for the private farm-activity intake queue."""

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
COLLECTED_AT = datetime(2026, 10, 28, 10, tzinfo=timezone.utc).isoformat()
SYNCED_AT = datetime(2026, 10, 28, 11, tzinfo=timezone.utc).isoformat()


def _row(**overrides):
    result = {
        "id": COLLECTION_ID,
        "location_id": LOCATION_ID,
        "form_id": "farm_activity_v1",
        "form_version": "1.2.0",
        "collected_at": COLLECTED_AT,
        "synced_at": SYNCED_AT,
        "activity_type": "weeding",
        "activity_date": "2026-10-27",
        "eligible_for_use": True,
    }
    return {**result, **overrides}


def _client(monkeypatch, service):
    session = SimpleNamespace(
        session_id=str(uuid4()),
        session_token_hash="d" * 64,
        operator=SimpleNamespace(operator_id=OPERATOR_ID),
    )

    class Provider:
        settings = SimpleNamespace(state_secret="test-only-state-secret-with-at-least-32-bytes")

        def authenticate_request(self, _request):
            return session

        def has_scope(self, operator_id, resource, action, location_id):
            return (
                operator_id == OPERATOR_ID
                and resource == "farm_activity"
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
    monkeypatch.setattr(
        "services.gateway.farm_activity_workflow.list_farm_activity_intake", service
    )
    return TestClient(create_app(), cookies={SESSION_COOKIE: "synthetic-session"})


def test_intake_queue_returns_exact_scoped_summary_and_no_store_headers(monkeypatch):
    calls = []

    def service(*args):
        calls.append(args)
        return [_row()]

    with _client(monkeypatch, service) as client:
        response = client.get(
            "/operator/api/farm-activity-intake-queue",
            params={"location_id": LOCATION_ID},
        )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert "Cookie" in response.headers["vary"]
    assert response.json() == {"data": [_row()], "location_id": LOCATION_ID}
    assert calls == [(OPERATOR_ID, LOCATION_ID, 50)]
    assert "payload" not in response.json()["data"][0]
    assert "description" not in response.json()["data"][0]


@pytest.mark.parametrize(
    "row",
    [
        _row(payload={"secret": "must not escape"}),
        _row(location_id=str(uuid4())),
        _row(form_id="another_form"),
        _row(eligible_for_use=False),
        _row(activity_date=42),
    ],
)
def test_intake_queue_rejects_out_of_scope_or_malformed_projection(monkeypatch, row):
    with _client(monkeypatch, lambda *_args: [row]) as client:
        response = client.get(
            "/operator/api/farm-activity-intake-queue",
            params={"location_id": LOCATION_ID},
        )

    assert response.status_code == 500
    assert response.json() == {"error": "Farm activity intake service unavailable"}
    assert response.headers["cache-control"] == "no-store"
    assert "Cookie" in response.headers["vary"]
    assert "must not escape" not in response.text


def test_intake_queue_preserves_tenant_denial(monkeypatch):
    def denied(*_args):
        raise TenantContextDenied("revoked")

    with _client(monkeypatch, denied) as client:
        response = client.get(
            "/operator/api/farm-activity-intake-queue",
            params={"location_id": LOCATION_ID},
        )

    assert response.status_code == 403
    assert response.json() == {"error": "Tenant-qualified operator access is required"}
    assert response.headers["cache-control"] == "no-store"
    assert "Cookie" in response.headers["vary"]


def test_intake_queue_openapi_declares_strict_exact_projection(monkeypatch):
    with _client(monkeypatch, lambda *_args: []) as client:
        schema = client.app.openapi()

    operation = schema["paths"]["/operator/api/farm-activity-intake-queue"]["get"]
    assert operation["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/FarmActivityIntakeQueueResponse"
    }
    for model in ("FarmActivityIntakeQueueResponse", "FarmActivityIntakeSummaryResponse"):
        assert schema["components"]["schemas"][model]["additionalProperties"] is False
