"""HTTP/OpenAPI contracts for the operator-only report export API."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

pytest.importorskip("fastapi")
from starlette.testclient import TestClient  # noqa: E402

from services.gateway.app import create_app  # noqa: E402
from services.gateway.operator_auth import auth_route_policy  # noqa: E402
from services.gateway.report_exports import (
    ReportExportArtifact,  # noqa: E402
    ReportExportConflict,  # noqa: E402
)

OPERATOR_ID = str(uuid4())
LOCATION_ID = str(uuid4())
SNAPSHOT_ID = str(uuid4())
REQUEST_ID = str(uuid4())
IDEMPOTENCY_KEY = str(uuid4())
CREATED_AT = datetime(2026, 10, 28, 12, 0, tzinfo=timezone.utc)


def _summary(**overrides):
    return {
        "request_id": REQUEST_ID,
        "snapshot_id": SNAPSHOT_ID,
        "location_id": LOCATION_ID,
        "status": "pending",
        "attempt_count": 0,
        "artifact_size": None,
        "created_at": CREATED_AT,
        "updated_at": CREATED_AT,
        "completed_at": None,
        "last_error_class": None,
        **overrides,
    }


def _client(monkeypatch, tmp_path, *, scopes=None, csrf=True):
    session = SimpleNamespace(
        session_id=str(uuid4()),
        session_token_hash="a" * 64,
        csrf_token_hash="b" * 64,
        operator=SimpleNamespace(operator_id=OPERATOR_ID),
    )
    checked_scopes = []
    allowed = set(scopes or {
        ("report_snapshot_export", "create"),
        ("report_snapshot_export", "read"),
        ("report_snapshot_export", "download"),
    })

    class Provider:
        settings = SimpleNamespace(state_secret="test-only-state-secret-with-at-least-32-bytes")

        def authenticate_request(self, _request):
            return session

        def has_scope(self, operator_id, resource, action, location_id):
            checked_scopes.append((operator_id, resource, action, location_id))
            return (resource, action) in allowed and location_id == LOCATION_ID

        def csrf_valid(self, _request, _session):
            return csrf

    class InMemoryAudit:
        def __init__(self):
            pass

        def replay_pending(self, _limit=100):
            return 0

        def log(self, **_event):
            return None

        def capture_status(self):
            return "ok"

        def reserve_mutation(self):
            return object()

        def release_mutation(self, _reservation):
            return None

    class RateLimiter:
        def check(self, _caller):
            return True

        def retry_after(self, _caller):
            return 0

    monkeypatch.setenv("KOKONUT_GATEWAY_AUDIT_SPOOL_PATH", str(tmp_path / "audit.sqlite3"))
    monkeypatch.setenv("KOKONUT_API_KEYS", "")
    monkeypatch.setenv("KOKONUT_API_KEY_SCOPES", "")
    monkeypatch.setenv("KOKONUT_OPERATOR_OIDC_ENABLED", "true")
    monkeypatch.setattr("services.gateway.operator_auth.create_provider", lambda: Provider())
    monkeypatch.setattr("services.gateway.audit.GatewayAudit", InMemoryAudit)
    return TestClient(create_app(rate_limiter=RateLimiter())), checked_scopes


def _assert_no_store(response):
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["pragma"] == "no-cache"
    assert "Cookie" in response.headers["vary"]
    assert response.headers["x-content-type-options"] == "nosniff"


def test_create_route_is_strict_scoped_idempotent_and_no_store(monkeypatch, tmp_path):
    calls = []

    def create(*args):
        calls.append(args)
        return {"request_id": REQUEST_ID, "status": "pending", "created_at": CREATED_AT}

    monkeypatch.setattr("services.gateway.report_exports.request_report_export", create)
    client, checked_scopes = _client(monkeypatch, tmp_path)
    with client:
        response = client.post(
            "/operator/api/report-exports",
            params={"location_id": LOCATION_ID},
            json={
                "report_snapshot_id": SNAPSHOT_ID,
                "idempotency_key": IDEMPOTENCY_KEY,
            },
        )

    assert response.status_code == 202
    _assert_no_store(response)
    assert response.json() == {
        "request_id": REQUEST_ID,
        "status": "pending",
        "created_at": CREATED_AT.isoformat(),
    }
    assert calls == [(OPERATOR_ID, LOCATION_ID, SNAPSHOT_ID, IDEMPOTENCY_KEY)]
    assert (OPERATOR_ID, "report_snapshot_export", "create", LOCATION_ID) in checked_scopes


def test_create_rejects_extra_fields_and_all_validation_responses_are_private(monkeypatch, tmp_path):
    client, _ = _client(monkeypatch, tmp_path)
    with client:
        response = client.post(
            "/operator/api/report-exports",
            params={"location_id": LOCATION_ID},
            json={
                "report_snapshot_id": SNAPSHOT_ID,
                "idempotency_key": IDEMPOTENCY_KEY,
                "file_url": "https://must-not-be-accepted.invalid/private",
            },
        )

    assert response.status_code == 422
    _assert_no_store(response)
    assert "must-not-be-accepted.invalid" not in response.text


def test_create_malformed_uuids_return_sanitized_no_store_error(monkeypatch, tmp_path):
    called = False

    def create(*_args):
        nonlocal called
        called = True
        return {"request_id": REQUEST_ID, "status": "pending", "created_at": CREATED_AT}

    monkeypatch.setattr("services.gateway.report_exports.request_report_export", create)
    client, _ = _client(monkeypatch, tmp_path)
    with client:
        response = client.post(
            "/operator/api/report-exports",
            params={"location_id": LOCATION_ID},
            json={"report_snapshot_id": "not-a-uuid", "idempotency_key": IDEMPOTENCY_KEY},
        )

    assert response.status_code == 422
    _assert_no_store(response)
    assert response.json() == {"error": "Report export request is invalid"}
    assert "not-a-uuid" not in response.text
    assert not called


def test_create_requires_csrf_before_service_call(monkeypatch, tmp_path):
    called = False

    def create(*_args):
        nonlocal called
        called = True
        return {"request_id": REQUEST_ID, "status": "pending", "created_at": CREATED_AT}

    monkeypatch.setattr("services.gateway.report_exports.request_report_export", create)
    client, _ = _client(monkeypatch, tmp_path, csrf=False)
    with client:
        response = client.post(
            "/operator/api/report-exports",
            params={"location_id": LOCATION_ID},
            json={"report_snapshot_id": SNAPSHOT_ID, "idempotency_key": IDEMPOTENCY_KEY},
        )

    assert response.status_code == 403
    _assert_no_store(response)
    assert not called


def test_create_maps_idempotency_collision_to_private_conflict(monkeypatch, tmp_path):
    def create(*_args):
        raise ReportExportConflict("This idempotency key is already bound to another request")

    monkeypatch.setattr("services.gateway.report_exports.request_report_export", create)
    client, _ = _client(monkeypatch, tmp_path)
    with client:
        response = client.post(
            "/operator/api/report-exports",
            params={"location_id": LOCATION_ID},
            json={"report_snapshot_id": SNAPSHOT_ID, "idempotency_key": IDEMPOTENCY_KEY},
        )

    assert response.status_code == 409
    _assert_no_store(response)
    assert response.json() == {
        "error": "This idempotency key is already bound to another request"
    }


def test_create_denies_separate_missing_export_grant(monkeypatch, tmp_path):
    called = False

    def create(*_args):
        nonlocal called
        called = True
        return {"request_id": REQUEST_ID, "status": "pending", "created_at": CREATED_AT}

    monkeypatch.setattr("services.gateway.report_exports.request_report_export", create)
    client, checked_scopes = _client(
        monkeypatch, tmp_path, scopes={("report_snapshot_review", "read")}
    )
    with client:
        response = client.post(
            "/operator/api/report-exports",
            params={"location_id": LOCATION_ID},
            json={"report_snapshot_id": SNAPSHOT_ID, "idempotency_key": IDEMPOTENCY_KEY},
        )

    assert response.status_code == 403
    _assert_no_store(response)
    assert not called
    assert (OPERATOR_ID, "report_snapshot_export", "create", LOCATION_ID) in checked_scopes


def test_list_and_detail_return_strict_status_projection_without_artifact_keys(
    monkeypatch, tmp_path
):
    summary = _summary()
    monkeypatch.setattr(
        "services.gateway.report_exports.list_report_exports", lambda *_args: [summary]
    )
    monkeypatch.setattr(
        "services.gateway.report_exports.get_report_export", lambda *_args: summary
    )
    client, checked_scopes = _client(monkeypatch, tmp_path)
    params = {"location_id": LOCATION_ID, "limit": "7"}
    with client:
        listed = client.get("/operator/api/report-exports", params=params)
        detail = client.get(
            f"/operator/api/report-exports/{REQUEST_ID}",
            params={"location_id": LOCATION_ID},
        )

    assert listed.status_code == 200
    assert detail.status_code == 200
    _assert_no_store(listed)
    _assert_no_store(detail)
    assert listed.json()["data"] == [
        {**summary, "created_at": CREATED_AT.isoformat(),
         "updated_at": CREATED_AT.isoformat()}
    ]
    assert detail.json()["data"]["request_id"] == REQUEST_ID
    assert "artifact_id" not in listed.text and "artifact_id" not in detail.text
    assert (OPERATOR_ID, "report_snapshot_export", "read", LOCATION_ID) in checked_scopes


def test_list_rejects_cross_location_projection_as_sanitized_error(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "services.gateway.report_exports.list_report_exports",
        lambda *_args: [_summary(location_id=str(uuid4()))],
    )
    client, _ = _client(monkeypatch, tmp_path)
    with client:
        response = client.get(
            "/operator/api/report-exports", params={"location_id": LOCATION_ID}
        )
    assert response.status_code == 500
    _assert_no_store(response)
    assert "location" not in response.text.lower()


def test_list_rejects_unprojected_storage_metadata(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "services.gateway.report_exports.list_report_exports",
        lambda *_args: [_summary(artifact_id="private-object-key")],
    )
    client, _ = _client(monkeypatch, tmp_path)
    with client:
        response = client.get(
            "/operator/api/report-exports", params={"location_id": LOCATION_ID}
        )

    assert response.status_code == 500
    _assert_no_store(response)
    assert "private-object-key" not in response.text


def test_candidate_list_is_read_grant_scoped_strict_paginated_and_no_store(monkeypatch, tmp_path):
    candidate = {
        "snapshot_id": SNAPSHOT_ID,
        "location_id": LOCATION_ID,
        "report_name": "Synthetic impact report",
        "report_type": "impact",
        "status": "verified",
        "period_start": None,
        "period_end": None,
        "snapshot_hash": "a" * 64,
        "created_at": CREATED_AT,
    }
    calls = []

    def list_candidates(*args):
        calls.append(args)
        return {
            "location_id": LOCATION_ID,
            "limit": 2,
            "offset": 4,
            "has_more": True,
            "data": [candidate],
        }

    monkeypatch.setattr(
        "services.gateway.report_exports.list_exportable_report_snapshots", list_candidates
    )
    client, checked_scopes = _client(monkeypatch, tmp_path)
    with client:
        response = client.get(
            "/operator/api/report-export-snapshots",
            params={"location_id": LOCATION_ID, "limit": 2, "offset": 4},
        )

    assert response.status_code == 200
    _assert_no_store(response)
    assert response.json() == {
        "location_id": LOCATION_ID,
        "limit": 2,
        "offset": 4,
        "has_more": True,
        "data": [{**candidate, "created_at": CREATED_AT.isoformat()}],
    }
    assert calls == [(OPERATOR_ID, LOCATION_ID, 2, 4)]
    assert (OPERATOR_ID, "report_snapshot_export", "read", LOCATION_ID) in checked_scopes
    assert auth_route_policy("GET", "/operator/api/report-export-snapshots", enabled=True) == {
        "resource": "report_snapshot_export",
        "action": "read",
        "public": False,
        "location_id": None,
        "scope_required": True,
        "operator_auth": True,
    }
    assert auth_route_policy("POST", "/operator/api/report-export-snapshots", enabled=True) is None


def test_candidate_list_rejects_cross_location_and_unprojected_rows(monkeypatch, tmp_path):
    candidate = {
        "snapshot_id": SNAPSHOT_ID,
        "location_id": str(uuid4()),
        "report_name": "Synthetic impact report",
        "report_type": "impact",
        "status": "verified",
        "period_start": None,
        "period_end": None,
        "snapshot_hash": "a" * 64,
        "created_at": CREATED_AT,
    }
    monkeypatch.setattr(
        "services.gateway.report_exports.list_exportable_report_snapshots",
        lambda *_args: {
            "location_id": LOCATION_ID, "limit": 25, "offset": 0,
            "has_more": False, "data": [candidate],
        },
    )
    client, _ = _client(monkeypatch, tmp_path)
    with client:
        response = client.get(
            "/operator/api/report-export-snapshots", params={"location_id": LOCATION_ID}
        )
    assert response.status_code == 500
    _assert_no_store(response)
    assert "report_name" not in response.text


def test_candidate_list_requires_its_independent_read_grant(monkeypatch, tmp_path):
    called = False

    def list_candidates(*_args):
        nonlocal called
        called = True
        return {"location_id": LOCATION_ID, "limit": 25, "offset": 0, "has_more": False, "data": []}

    monkeypatch.setattr(
        "services.gateway.report_exports.list_exportable_report_snapshots", list_candidates
    )
    client, checked_scopes = _client(
        monkeypatch,
        tmp_path,
        scopes={("report_snapshot_export", "create"), ("report_snapshot_export", "download")},
    )
    with client:
        response = client.get(
            "/operator/api/report-export-snapshots", params={"location_id": LOCATION_ID}
        )
    assert response.status_code == 403
    _assert_no_store(response)
    assert not called
    assert (OPERATOR_ID, "report_snapshot_export", "read", LOCATION_ID) in checked_scopes


def test_candidate_list_validation_errors_remain_sanitized_and_private(monkeypatch, tmp_path):
    client, _ = _client(monkeypatch, tmp_path)
    with client:
        response = client.get(
            "/operator/api/report-export-snapshots",
            params={"location_id": LOCATION_ID, "limit": 51},
        )
    assert response.status_code == 422
    _assert_no_store(response)
    assert response.json() == {"error": "Report export request is invalid"}
    assert "detail" not in response.text


def test_artifact_route_returns_only_verified_bytes_and_safe_filename(monkeypatch, tmp_path):
    content = b'{"summary":"safe"}'
    artifact = ReportExportArtifact(request_id=UUID(REQUEST_ID), content=content)
    monkeypatch.setattr(
        "services.gateway.report_exports.download_report_export", lambda *_args: artifact
    )
    client, checked_scopes = _client(monkeypatch, tmp_path)
    with client:
        response = client.get(
            f"/operator/api/report-exports/{REQUEST_ID}/artifact",
            params={"location_id": LOCATION_ID},
        )

    assert response.status_code == 200
    _assert_no_store(response)
    assert response.headers["content-type"] == "application/json"
    assert response.headers["content-disposition"] == (
        f'attachment; filename="kokonut-report-{REQUEST_ID}.json"'
    )
    assert response.content == content
    assert "file_url" not in response.text
    assert (OPERATOR_ID, "report_snapshot_export", "download", LOCATION_ID) in checked_scopes


def test_report_export_openapi_exposes_only_strict_request_fields(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "services.gateway.report_exports.list_report_exports", lambda *_args: []
    )
    client, _ = _client(monkeypatch, tmp_path)
    with client:
        schema = client.app.openapi()

    create = schema["paths"]["/operator/api/report-exports"]["post"]
    body_ref = create["requestBody"]["content"]["application/json"]["schema"]["$ref"]
    body_model = body_ref.rsplit("/", 1)[1]
    body_schema = schema["components"]["schemas"][body_model]
    assert body_schema["additionalProperties"] is False
    assert set(body_schema["properties"]) == {"report_snapshot_id", "idempotency_key"}
    assert body_schema["required"] == ["report_snapshot_id", "idempotency_key"]
    create_response = create["responses"]["202"]["content"]["application/json"]["schema"]
    assert create_response["$ref"].endswith("ReportExportCreateResponse")
    assert schema["components"]["schemas"]["ReportExportCreateResponse"][
        "additionalProperties"
    ] is False

    list_response = schema["paths"]["/operator/api/report-exports"]["get"][
        "responses"
    ]["200"]["content"]["application/json"]["schema"]
    detail_response = schema["paths"]["/operator/api/report-exports/{request_id}"]["get"][
        "responses"
    ]["200"]["content"]["application/json"]["schema"]
    assert list_response["$ref"].endswith("ReportExportListResponse")
    assert detail_response["$ref"].endswith("ReportExportDetailResponse")
    assert schema["components"]["schemas"]["ReportExportListResponse"][
        "additionalProperties"
    ] is False
    assert schema["components"]["schemas"]["ReportExportDetailResponse"][
        "additionalProperties"
    ] is False
    candidate_list = schema["paths"]["/operator/api/report-export-snapshots"]["get"][
        "responses"
    ]["200"]["content"]["application/json"]["schema"]
    assert candidate_list["$ref"].endswith("ReportExportCandidateListResponse")
    candidate_schema = schema["components"]["schemas"]["ReportExportCandidateListResponse"]
    assert candidate_schema["additionalProperties"] is False
    assert set(candidate_schema["properties"]) == {
        "location_id", "limit", "offset", "has_more", "data"
    }
    assert schema["components"]["schemas"]["ReportExportCandidate"][
        "additionalProperties"
    ] is False
