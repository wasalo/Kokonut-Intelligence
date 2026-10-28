"""Strict runtime and OpenAPI contract for the report-review queue."""

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
REPORT_ID = str(uuid4())
CREATED_AT = datetime(2026, 10, 28, 11, 30, tzinfo=timezone.utc).isoformat()


def _report(**overrides):
    result = {
        "id": REPORT_ID,
        "report_name": "Farm summary",
        "report_type": "farm_summary",
        "status": "submitted",
        "period_start": "2026-10-01",
        "period_end": "2026-10-27",
        "snapshot_hash": "a" * 64,
        "created_at": CREATED_AT,
        "location_name": "Kokonut Genesis",
    }
    return {**result, **overrides}


def _client(monkeypatch, service):
    session = SimpleNamespace(
        session_id=str(uuid4()),
        session_token_hash="a" * 64,
        operator=SimpleNamespace(operator_id=OPERATOR_ID),
    )

    class Provider:
        settings = SimpleNamespace(state_secret="test-only-state-secret-with-at-least-32-bytes")

        def authenticate_request(self, _request):
            return session

        def has_scope(self, operator_id, resource, action, location_id):
            return (
                operator_id == OPERATOR_ID
                and resource == "report_snapshot_review"
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
    monkeypatch.setattr("services.gateway.operator_review.list_submitted_reports", service)
    return TestClient(create_app(), cookies={SESSION_COOKIE: "synthetic-session"})


def test_report_queue_returns_exact_submitted_summary_and_private_cache_headers(monkeypatch):
    calls = []

    def service(*args):
        calls.append(args)
        return [_report()]

    with _client(monkeypatch, service) as client:
        response = client.get("/operator/api/report-review-queue", params={"location_id": LOCATION_ID})

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert "Cookie" in response.headers["vary"]
    assert response.json() == {"data": [_report()], "location_id": LOCATION_ID}
    assert calls == [(OPERATOR_ID, LOCATION_ID, 50)]


@pytest.mark.parametrize(
    "report",
    [
        _report(report_data={"private": "must not escape"}),
        _report(status="draft"),
        _report(period_start=123),
        _report(location_name=42),
    ],
)
def test_report_queue_rejects_invalid_source_projection_without_leaking_data(monkeypatch, report):
    with _client(monkeypatch, lambda *_args: [report]) as client:
        response = client.get(
            "/operator/api/report-review-queue", params={"location_id": LOCATION_ID}
        )

    assert response.status_code == 500
    assert response.json() == {"error": "Report review queue unavailable"}
    assert response.headers["cache-control"] == "no-store"
    assert "Cookie" in response.headers["vary"]
    assert "must not escape" not in response.text


def test_report_queue_preserves_tenant_denial(monkeypatch):
    def denied(*_args):
        raise TenantContextDenied("unqualified owner")

    with _client(monkeypatch, denied) as client:
        response = client.get(
            "/operator/api/report-review-queue", params={"location_id": LOCATION_ID}
        )

    assert response.status_code == 403
    assert response.json() == {"error": "Tenant-qualified operator access is required"}
    assert response.headers["cache-control"] == "no-store"
    assert "Cookie" in response.headers["vary"]


def test_report_queue_openapi_declares_exact_strict_projection(monkeypatch):
    with _client(monkeypatch, lambda *_args: []) as client:
        schema = client.app.openapi()

    operation = schema["paths"]["/operator/api/report-review-queue"]["get"]
    assert operation["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/ReportReviewQueueResponse"
    }
    for model in ("ReportReviewQueueResponse", "SubmittedReportSummaryResponse"):
        assert schema["components"]["schemas"][model]["additionalProperties"] is False
    assert schema["components"]["schemas"]["SubmittedReportSummaryResponse"][
        "properties"
    ]["status"]["const"] == "submitted"
