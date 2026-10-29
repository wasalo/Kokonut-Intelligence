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


def _client(monkeypatch, service, detail_service=None):
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
    monkeypatch.setattr(
        "services.gateway.operator_review.get_submitted_report",
        detail_service or (lambda *_args: None),
    )
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


def _report_detail(**overrides):
    return {
        **_report(),
        "report_data": {"summary": "Reviewed fixture", "counts": {"harvests": 3}},
        **overrides,
    }


def test_submitted_report_detail_returns_exact_bounded_private_projection(monkeypatch):
    calls = []

    def service(*args):
        calls.append(args)
        return _report_detail()

    with _client(monkeypatch, lambda *_args: [], detail_service=service) as client:
        response = client.get(
            f"/operator/api/report-review-queue/{REPORT_ID}",
            params={"location_id": LOCATION_ID},
        )

    assert response.status_code == 200
    assert response.json() == {"data": _report_detail()}
    assert response.headers["cache-control"] == "no-store"
    assert "Cookie" in response.headers["vary"]
    assert calls == [(OPERATOR_ID, REPORT_ID, LOCATION_ID)]


@pytest.mark.parametrize(
    "report",
    [
        _report_detail(id=str(uuid4())),
        _report_detail(status="verified"),
        _report_detail(report_size=10),
        _report_detail(report_data=[]),
        _report_detail(report_data={"large": "x" * (512 * 1024 + 1)}),
    ],
)
def test_submitted_report_detail_rejects_malformed_or_oversized_projection(monkeypatch, report):
    with _client(
        monkeypatch, lambda *_args: [], detail_service=lambda *_args: report
    ) as client:
        response = client.get(
            f"/operator/api/report-review-queue/{REPORT_ID}",
            params={"location_id": LOCATION_ID},
        )

    assert response.status_code == 500
    assert response.json() == {"error": "Report review service unavailable"}
    assert response.headers["cache-control"] == "no-store"
    assert "Cookie" in response.headers["vary"]
    assert "large" not in response.text


def test_unmatched_report_detail_path_fails_closed_before_service(monkeypatch):
    def service(*_args):
        pytest.fail("invalid report identifier must fail before service dispatch")

    with _client(monkeypatch, lambda *_args: [], detail_service=service) as client:
        response = client.get(
            "/operator/api/report-review-queue/not-a-uuid",
            params={"location_id": LOCATION_ID},
        )

    # The Gateway catch-all policy rejects a malformed report UUID before the
    # route is selected, so the private handler never gets to validate it.
    assert response.status_code == 401


def test_invalid_report_location_fails_before_service_and_is_private(monkeypatch):
    def service(*_args):
        pytest.fail("invalid location identifier must fail before service dispatch")

    with _client(monkeypatch, lambda *_args: [], detail_service=service) as client:
        response = client.get(
            f"/operator/api/report-review-queue/{REPORT_ID}",
            params={"location_id": "not-a-uuid"},
        )

    # Authorization evaluates tenant scope before the handler's UUID parser.
    # The invalid location is therefore denied without disclosing its value.
    assert response.status_code == 403
    assert response.headers["cache-control"] == "no-store"
    assert "not-a-uuid" not in response.text


def test_submitted_report_detail_not_found_and_too_large_are_private(monkeypatch):
    from services.gateway.operator_review import ReportPayloadTooLarge

    with _client(monkeypatch, lambda *_args: [], detail_service=lambda *_args: None) as client:
        missing = client.get(
            f"/operator/api/report-review-queue/{REPORT_ID}",
            params={"location_id": LOCATION_ID},
        )
    with _client(
        monkeypatch,
        lambda *_args: [],
        detail_service=lambda *_args: (_ for _ in ()).throw(ReportPayloadTooLarge()),
    ) as client:
        oversized = client.get(
            f"/operator/api/report-review-queue/{REPORT_ID}",
            params={"location_id": LOCATION_ID},
        )

    assert missing.status_code == 404
    assert missing.headers["cache-control"] == "no-store"
    assert oversized.status_code == 413
    assert oversized.headers["cache-control"] == "no-store"
    assert "Cookie" in oversized.headers["vary"]


def test_submitted_report_detail_rejects_deeply_nested_json_safely(monkeypatch):
    nested = {}
    cursor = nested
    for _ in range(1100):
        child = {}
        cursor["next"] = child
        cursor = child

    with _client(
        monkeypatch,
        lambda *_args: [],
        detail_service=lambda *_args: _report_detail(report_data=nested),
    ) as client:
        response = client.get(
            f"/operator/api/report-review-queue/{REPORT_ID}",
            params={"location_id": LOCATION_ID},
        )

    assert response.status_code == 500
    assert response.json() == {"error": "Report review service unavailable"}
    assert response.headers["cache-control"] == "no-store"


def test_report_detail_openapi_declares_strict_bounded_schema(monkeypatch):
    with _client(monkeypatch, lambda *_args: []) as client:
        schema = client.app.openapi()

    operation = schema["paths"][
        "/operator/api/report-review-queue/{report_id}"
    ]["get"]
    assert operation["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/SubmittedReportDetailResponse"
    }
    assert operation["responses"]["413"]["headers"]["Cache-Control"]["schema"][
        "example"
    ] == "no-store"
    components = schema["components"]["schemas"]
    assert components["SubmittedReportDetailResponse"]["additionalProperties"] is False
    assert components["SubmittedReportDetail"]["additionalProperties"] is False
    assert components["SubmittedReportDetail"]["properties"]["report_data"]["type"] == "object"
