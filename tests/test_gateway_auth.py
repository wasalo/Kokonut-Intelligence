"""Focused gateway authorization tests."""

import hashlib
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest

pytest.importorskip("fastapi")
from starlette.testclient import TestClient  # noqa: E402

from services.gateway.app import create_app  # noqa: E402

DATA_STREAM_POST_ID = "33333333-3333-4333-8333-333333333333"


@pytest.fixture(autouse=True)
def isolated_gateway_audit_spool(tmp_path, monkeypatch):
    """Give host-run app tests a private writable journal like the container has."""
    monkeypatch.setenv(
        "KOKONUT_GATEWAY_AUDIT_SPOOL_PATH",
        str(tmp_path / "gateway-audit.sqlite3"),
    )
    monkeypatch.setenv("KOKONUT_GATEWAY_AUDIT_SPOOL_MAX_EVENTS", "1000")
    monkeypatch.setenv("KOKONUT_GATEWAY_AUDIT_SPOOL_ALERT_THRESHOLD", "0")


def test_anonymous_public_read_is_allowed():
    with TestClient(create_app()) as client:
        response = client.get("/api/iri/resolve", params={"iri": "missing"})

    assert response.status_code != 401


def test_anonymous_gateway_health_is_allowed():
    with TestClient(create_app()) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_anonymous_detailed_service_health_is_denied_without_probing(monkeypatch):
    """Only the lightweight liveness route is public; dependency topology is not."""
    from unittest.mock import MagicMock

    monkeypatch.delenv("KOKONUT_API_KEYS", raising=False)
    detailed_health = MagicMock(return_value={"services": []})
    monkeypatch.setattr("services.core.health.overall_health", detailed_health)

    with TestClient(create_app()) as client:
        detailed = client.get("/api/health/services")
        liveness = client.get("/health")

    assert detailed.status_code == 401
    assert detailed.json()["error"] == "Unauthorized"
    detailed_health.assert_not_called()
    assert liveness.status_code == 200
    assert liveness.json()["status"] == "ok"


def _service_health_fixture():
    return {
        "healthy": False,
        "ready": False,
        "version": "0.1.0",
        "git_sha": "abc1234",
        "critical_failures": 1,
        "services": [
            {
                "service": "database",
                "healthy": False,
                "critical": True,
                "message": "PostgreSQL unavailable",
                "latency_ms": 12,
                "checked_at": "2026-10-29T12:00:00+00:00",
                "state": "checked",
            },
            {
                "service": "clickhouse",
                "healthy": True,
                "critical": False,
                "message": "Provider disabled",
                "latency_ms": 0,
                "checked_at": "2026-10-29T12:00:00+00:00",
                "state": "disabled",
            },
            {
                "service": "directus",
                "healthy": True,
                "critical": True,
                "message": "Directus responding",
                "latency_ms": 4,
                "checked_at": "2026-10-29T12:00:00+00:00",
                "state": "checked",
            },
            {
                "service": "forecast_worker",
                "healthy": True,
                "critical": False,
                "message": "No health check defined",
                "latency_ms": 0,
                "checked_at": "2026-10-29T12:00:00+00:00",
                "state": "unmonitored",
            },
        ],
    }


def _configure_service_health_reader(monkeypatch):
    monkeypatch.setenv("KOKONUT_API_KEYS", "health-key:health-reader")
    monkeypatch.setenv(
        "KOKONUT_API_KEY_SCOPES",
        "health-reader:service_health:read",
    )


def test_detailed_service_health_validates_optional_critical_and_provider_states(
    monkeypatch,
):
    _configure_service_health_reader(monkeypatch)
    expected = _service_health_fixture()
    monkeypatch.setattr("services.core.health.overall_health", lambda: expected)

    with TestClient(create_app()) as client:
        response = client.get(
            "/api/health/services",
            headers={"x-api-key": "health-key"},
        )

    assert response.status_code == 200
    assert response.json() == expected
    assert response.headers["cache-control"] == "no-store"
    assert {item["state"] for item in response.json()["services"]} == {
        "checked",
        "disabled",
        "unmonitored",
    }


@pytest.mark.parametrize(
    "mutate",
    [
        lambda payload: payload.update(healthy=True),
        lambda payload: payload.update(ready=True),
        lambda payload: payload.update(critical_failures=0),
        lambda payload: payload["services"].append(payload["services"][0]),
        lambda payload: payload["services"][1].update(state="unknown"),
        lambda payload: payload["services"][0].update(latency_ms=True),
    ],
    ids=["health-aggregate", "readiness-aggregate", "critical-count", "duplicate-service", "invalid-state", "boolean-latency"],
)
def test_detailed_service_health_rejects_inconsistent_or_malformed_output(
    monkeypatch, caplog, mutate
):
    _configure_service_health_reader(monkeypatch)
    result = _service_health_fixture()
    mutate(result)
    result["private_debug"] = "secret-health-marker"
    monkeypatch.setattr("services.core.health.overall_health", lambda: result)

    with TestClient(create_app()) as client:
        response = client.get(
            "/api/health/services",
            headers={"x-api-key": "health-key"},
        )

    assert response.status_code == 500
    assert response.json() == {"error": "Service health unavailable"}
    assert response.headers["cache-control"] == "no-store"
    assert "secret-health-marker" not in response.text
    assert "secret-health-marker" not in caplog.text


def test_detailed_service_health_openapi_declares_exact_response(monkeypatch):
    schema = create_app().openapi()
    operation = schema["paths"]["/api/health/services"]["get"]

    assert operation["responses"]["200"]["content"]["application/json"]["schema"][
        "$ref"
    ].endswith("/ServiceHealthResponse")
    model = schema["components"]["schemas"]["ServiceHealthResponse"]
    assert model["additionalProperties"] is False
    assert set(model["required"]) == {
        "healthy", "ready", "version", "git_sha", "critical_failures", "services"
    }


def test_mobile_upload_cors_requires_allowlisted_origin_and_allows_device_headers(monkeypatch):
    monkeypatch.setenv("KOKONUT_GATEWAY_CORS_ORIGINS", "https://collector.example")
    headers = {
        "Origin": "https://collector.example",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": (
            "content-type,authorization,api-key,x-api-key,capability-token,x-capability-token,"
            "x-csrf-token,x-device-token,x-collection-client-id,x-collection-type,x-form-id,"
            "x-form-version,x-participant-ref,x-collected-at"
        ),
    }
    with TestClient(create_app()) as client:
        allowed = client.options("/api/mobile/media/uploads", headers=headers)
        denied = client.options(
            "/api/mobile/media/uploads",
            headers={**headers, "Origin": "https://attacker.example"},
        )

    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == "https://collector.example"
    allowed_headers = {
        value.strip().lower()
        for value in allowed.headers["access-control-allow-headers"].split(",")
    }
    assert set(headers["Access-Control-Request-Headers"].split(",")) <= allowed_headers
    assert "access-control-allow-origin" not in denied.headers


def test_mobile_upload_success_has_credentialed_cors_for_device_auth(monkeypatch):
    monkeypatch.setenv("KOKONUT_GATEWAY_CORS_ORIGINS", "https://collector.example")
    provider = SimpleNamespace(
        settings=SimpleNamespace(state_secret="test-state-secret-with-at-least-32-bytes")
    )
    monkeypatch.setattr("services.gateway.operator_auth.create_provider", lambda: provider)
    policy_connection = MagicMock()
    write_connection = MagicMock()
    monkeypatch.setattr(
        "services.mobile.api.get_db",
        MagicMock(side_effect=[policy_connection, write_connection]),
    )
    monkeypatch.setattr(
        "services.mobile.api._device_for_token",
        lambda token: ("device-id", "user-id", "11111111-1111-4111-8111-111111111111")
        if token == "synthetic-device-token"
        else None,
    )
    monkeypatch.setattr("services.mobile.api.set_mobile_device_tenant_context", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("services.mobile.api._validate_media_upload_policy", lambda *_args, **_kwargs: None)
    media_store = SimpleNamespace(put_private=MagicMock(), delete_private=MagicMock())
    monkeypatch.setattr("services.mobile.api.get_media_store", lambda: media_store)

    with TestClient(create_app()) as client:
        response = client.post(
            "/api/mobile/media/uploads",
            content=b"\xff\xd8\xffsynthetic-jpeg",
            headers={
                "Origin": "https://collector.example",
                "Content-Type": "image/jpeg",
                "X-Device-Token": "synthetic-device-token",
                "X-Collection-Client-ID": "synthetic-client-id",
            },
        )

    assert response.status_code == 201, response.text
    assert response.headers["access-control-allow-origin"] == "https://collector.example"
    assert response.headers["access-control-allow-credentials"] == "true"
    assert response.headers["vary"] == "Origin"
    assert response.json()["size_bytes"] == len(b"\xff\xd8\xffsynthetic-jpeg")
    media_store.put_private.assert_called_once()
    policy_connection.commit.assert_called_once()
    write_connection.commit.assert_called_once()


def test_gateway_cors_preflight_allows_scoped_enrollment_revocation(monkeypatch):
    monkeypatch.setenv("KOKONUT_GATEWAY_CORS_ORIGINS", "https://admin.example")
    with TestClient(create_app()) as client:
        response = client.options(
            "/api/mobile/locations/11111111-1111-4111-8111-111111111111/enrollments/22222222-2222-4222-8222-222222222222",
            headers={
                "Origin": "https://admin.example",
                "Access-Control-Request-Method": "DELETE",
                "Access-Control-Request-Headers": "authorization",
            },
        )

    assert response.status_code == 200
    assert "DELETE" in response.headers["access-control-allow-methods"]


def test_gateway_cors_is_closed_when_no_origin_allowlist_is_configured(monkeypatch):
    monkeypatch.delenv("KOKONUT_GATEWAY_CORS_ORIGINS", raising=False)
    with TestClient(create_app()) as client:
        response = client.options(
            "/api/mobile/media/uploads",
            headers={
                "Origin": "https://attacker.example",
                "Access-Control-Request-Method": "POST",
            },
        )

    assert "access-control-allow-origin" not in response.headers


def test_gateway_cors_does_not_trust_wildcard_configuration(monkeypatch):
    monkeypatch.setenv("KOKONUT_GATEWAY_CORS_ORIGINS", "*")
    with TestClient(create_app()) as client:
        response = client.options(
            "/api/mobile/media/uploads",
            headers={
                "Origin": "https://attacker.example",
                "Access-Control-Request-Method": "POST",
            },
        )

    assert "access-control-allow-origin" not in response.headers


def test_legacy_directus_cors_setting_does_not_enable_gateway_origins(monkeypatch):
    monkeypatch.setenv("CORS_ORIGIN", "https://directus.example")
    monkeypatch.delenv("KOKONUT_GATEWAY_CORS_ORIGINS", raising=False)

    with TestClient(create_app()) as client:
        response = client.options(
            "/api/mobile/media/uploads",
            headers={
                "Origin": "https://directus.example",
                "Access-Control-Request-Method": "POST",
            },
        )

    assert "access-control-allow-origin" not in response.headers


def test_gateway_rejects_oversized_request_before_route_parsing():
    body = b'{"device_id":"' + b"x" * 8_000_001 + b'"}'
    with TestClient(create_app()) as client:
        response = client.post(
            "/api/mobile/register",
            headers={"content-type": "application/json"},
            content=body,
        )

    assert response.status_code == 413


def test_gateway_rejects_media_upload_over_2mb_before_route_auth():
    body = b"\xff\xd8\xff" + b"x" * (2_000_001 - 3)
    with TestClient(create_app()) as client:
        response = client.post(
            "/api/mobile/media/uploads",
            headers={"content-type": "image/jpeg"},
            content=body,
        )

    assert response.status_code == 413


def test_gateway_audits_oversized_body_without_raw_credential(monkeypatch):
    credential = "test-only-field-collector-key"
    records = []
    monkeypatch.setattr(
        "services.gateway.audit.GatewayAudit.log",
        lambda self, **record: records.append(record),
    )
    body = b"x" * 8_000_001
    with TestClient(create_app()) as client:
        response = client.post(
            "/api/mobile/register",
            headers={"content-type": "application/json", "x-api-key": credential},
            content=body,
        )

    assert response.status_code == 413
    assert records[0]["reason"] == "request_body_too_large"
    assert records[0]["status_code"] == 413
    assert credential not in repr(records)


def test_gateway_rate_limit_is_audited_and_returns_retry_after(monkeypatch):
    records = []

    class DenyAllLimiter:
        def __init__(self):
            pass

        def check(self, caller):
            return False

        def retry_after(self, caller):
            return 9

    monkeypatch.setattr("services.gateway.rate_limiter.RateLimiter", DenyAllLimiter)
    monkeypatch.setattr(
        "services.gateway.audit.GatewayAudit.log",
        lambda self, **record: records.append(record),
    )
    with TestClient(create_app()) as client:
        response = client.get("/health")

    assert response.status_code == 429
    assert response.headers["retry-after"] == "9"
    assert records[0]["reason"] == "rate_limited"
    assert records[0]["status_code"] == 429


def test_anonymous_write_is_denied():
    with TestClient(create_app()) as client:
        response = client.post("/api/data-stream/post", json={"location_id": "location-1"})

    assert response.status_code == 401
    assert response.json()["error"] == "Unauthorized"


def test_authenticated_write_passes_verified_middleware_context(monkeypatch):
    monkeypatch.setenv("KOKONUT_API_KEYS", "secret-key:verified-caller")
    monkeypatch.setenv("KOKONUT_API_KEY_SCOPES", "verified-caller:data_stream_post:create")
    location_id = "11111111-1111-4111-8111-111111111111"
    with patch(
        "services.gateway.data_stream.create_gateway_data_stream_post",
        return_value={"id": DATA_STREAM_POST_ID},
    ) as create_post:
        with TestClient(create_app()) as client:
            response = client.post(
                "/api/data-stream/post",
                headers={"x-api-key": "secret-key"},
                json={
                    "location_id": location_id,
                    "title": "Report",
                },
            )

    assert response.status_code == 201
    assert response.json() == {"post_id": DATA_STREAM_POST_ID}
    assert response.headers["cache-control"] == "no-store"
    assert create_post.call_args.args[0] == {
        "location_id": location_id,
        "post_type": "monitoring_report",
        "title": "Report",
        "content": "",
        "expires_at": None,
    }
    assert create_post.call_args.args[1] == {
        "resource": "data_stream_post",
        "action": "create",
        "location_id": location_id,
        "credential_type": "api_key",
        "credential_hash": hashlib.sha256(b"secret-key").hexdigest(),
    }


def test_data_stream_post_search_requires_location_read_scope(monkeypatch):
    location_id = "11111111-1111-4111-8111-111111111111"
    other_location_id = "44444444-4444-4444-8444-444444444444"
    monkeypatch.setenv("KOKONUT_API_KEYS", "reader-key:reader")
    monkeypatch.setenv(
        "KOKONUT_API_KEY_SCOPES",
        f"reader:data_stream_post:read:{location_id}",
    )
    with patch(
        "services.gateway.data_stream.list_gateway_data_stream_posts",
        return_value=[
            {
                "id": UUID("33333333-3333-4333-8333-333333333333"),
                "location_id": UUID(location_id),
                "post_type": "field_update",
                "title": "Field note",
                "content": "soil cover",
                "visibility": "private",
                "status": "verified",
                "is_anchored": False,
                "attestation_uid": None,
                "chain": None,
                "anchored_at": None,
                "content_hash": None,
                "created_at": None,
                "created_by": None,
                "expires_at": None,
                "search_rank": 1.0,
            }
        ],
    ) as list_posts:
        with TestClient(create_app()) as client:
            response = client.get(
                "/api/data-stream/posts",
                headers={"x-api-key": "reader-key"},
                params={"location_id": location_id, "q": "soil cover"},
            )
            denied = client.get(
                "/api/data-stream/posts",
                headers={"x-api-key": "reader-key"},
                params={"location_id": other_location_id},
            )

    assert response.status_code == 200
    assert response.json() == {
        "data": [
            {
                "id": "33333333-3333-4333-8333-333333333333",
                "location_id": location_id,
                "post_type": "field_update",
                "title": "Field note",
                "content": "soil cover",
                "visibility": "private",
                "status": "verified",
                "is_anchored": False,
                "attestation_uid": None,
                "chain": None,
                "anchored_at": None,
                "content_hash": None,
                "created_at": None,
                "created_by": None,
                "expires_at": None,
                "search_rank": 1.0,
            }
        ]
    }
    assert response.headers["cache-control"] == "no-store"
    assert list_posts.call_count == 1
    assert list_posts.call_args.args == (
        location_id,
        {
            "resource": "data_stream_post",
            "action": "read",
            "location_id": location_id,
            "credential_type": "api_key",
            "credential_hash": hashlib.sha256(b"reader-key").hexdigest(),
        },
    )
    assert list_posts.call_args.kwargs["query_text"] == "soil cover"
    assert denied.status_code == 403
    assert denied.headers["cache-control"] == "no-store"


def test_data_stream_file_and_attestation_routes_use_separate_read_scopes(monkeypatch):
    location_id = "11111111-1111-4111-8111-111111111111"
    post_id = "33333333-3333-4333-8333-333333333333"
    monkeypatch.setenv("KOKONUT_API_KEYS", "reader-key:reader")
    monkeypatch.setenv(
        "KOKONUT_API_KEY_SCOPES",
        ",".join(
            [
                f"reader:data_stream_file:read:{location_id}",
                f"reader:data_stream_proof:read:{location_id}",
            ]
        ),
    )
    with (
        patch(
            "services.gateway.data_stream.list_gateway_data_stream_files",
            return_value=[
                {
                    "id": UUID("22222222-2222-4222-8222-222222222222"),
                    "post_id": UUID(post_id),
                    "file_name": "field-note.jpg",
                    "file_description": None,
                    "file_credit": None,
                    "media_type": "image",
                    "file_size_bytes": 1024,
                    "mime_type": "image/jpeg",
                    "latitude": None,
                    "longitude": None,
                    "sort_order": 0,
                    "status": "verified",
                    "visibility": "private",
                    "created_at": None,
                    "created_by": None,
                    "updated_at": None,
                    "updated_by": None,
                }
            ],
        ) as list_files,
        patch(
            "services.gateway.data_stream.get_gateway_data_stream_attestation",
            return_value={
                "post_id": UUID(post_id),
                "location_id": UUID(location_id),
                "post_content_hash": None,
                "is_anchored": False,
                "attestation_uid": None,
                "chain": "celo",
                "anchored_at": None,
                "request_status": "confirmed",
                "tx_hash": None,
                "block_number": None,
                "confirmed_at": None,
                "request_created_at": None,
            },
        ) as read_attestation,
    ):
        with TestClient(create_app()) as client:
            files = client.get(
                f"/api/data-stream/posts/{post_id}/files",
                headers={"x-api-key": "reader-key"},
                params={"location_id": location_id, "limit": 12, "offset": 24},
            )
            proof = client.get(
                f"/api/data-stream/posts/{post_id}/attestation",
                headers={"x-api-key": "reader-key"},
                params={"location_id": location_id},
            )

    assert files.status_code == 200
    assert files.json() == {
        "data": [
            {
                "id": "22222222-2222-4222-8222-222222222222",
                "post_id": post_id,
                "file_name": "field-note.jpg",
                "file_description": None,
                "file_credit": None,
                "media_type": "image",
                "file_size_bytes": 1024,
                "mime_type": "image/jpeg",
                "latitude": None,
                "longitude": None,
                "sort_order": 0,
                "status": "verified",
                "visibility": "private",
                "created_at": None,
                "created_by": None,
                "updated_at": None,
                "updated_by": None,
            }
        ]
    }
    assert files.headers["cache-control"] == "no-store"
    assert proof.status_code == 200
    assert proof.json() == {
        "data": {
            "post_id": post_id,
            "location_id": location_id,
            "post_content_hash": None,
            "is_anchored": False,
            "attestation_uid": None,
            "chain": "celo",
            "anchored_at": None,
            "request_status": "confirmed",
            "tx_hash": None,
            "block_number": None,
            "confirmed_at": None,
            "request_created_at": None,
        }
    }
    assert proof.headers["cache-control"] == "no-store"
    assert list_files.call_args.args[1] == location_id
    assert list_files.call_args.args[2]["resource"] == "data_stream_file"
    assert list_files.call_args.kwargs == {"limit": 12, "offset": 24}
    assert read_attestation.call_args.args[1] == location_id
    assert read_attestation.call_args.args[2]["resource"] == "data_stream_proof"


def test_data_stream_file_route_publishes_and_enforces_pagination_bounds(monkeypatch):
    from services.gateway.app import create_app

    schema = create_app().openapi()
    operation = schema["paths"]["/api/data-stream/posts/{post_id}/files"]["get"]
    parameters = {parameter["name"]: parameter for parameter in operation["parameters"]}
    assert parameters["limit"]["schema"]["minimum"] == 1
    assert parameters["limit"]["schema"]["maximum"] == 100
    assert parameters["limit"]["schema"]["default"] == 50
    assert parameters["offset"]["schema"]["minimum"] == 0
    assert parameters["offset"]["schema"]["maximum"] == 5000

    location_id = "11111111-1111-4111-8111-111111111111"
    post_id = "33333333-3333-4333-8333-333333333333"
    monkeypatch.setenv("KOKONUT_API_KEYS", "reader-key:reader")
    monkeypatch.setenv(
        "KOKONUT_API_KEY_SCOPES",
        f"reader:data_stream_file:read:{location_id}",
    )
    with patch(
        "services.gateway.data_stream.list_gateway_data_stream_files",
        return_value=[],
    ) as list_files:
        with TestClient(create_app()) as client:
            response = client.get(
                f"/api/data-stream/posts/{post_id}/files",
                headers={"x-api-key": "reader-key"},
                params={"location_id": location_id, "limit": 101},
            )

    assert response.status_code == 422
    list_files.assert_not_called()


def test_database_tenant_denial_returns_forbidden(monkeypatch):
    from services.common.tenant_context import TenantContextDenied

    monkeypatch.setenv("KOKONUT_API_KEYS", "secret-key:verified-caller")
    monkeypatch.setenv("KOKONUT_API_KEY_SCOPES", "verified-caller:data_stream_post:create")
    with patch(
        "services.gateway.data_stream.create_gateway_data_stream_post",
        side_effect=TenantContextDenied("stale owner scope"),
    ):
        with TestClient(create_app()) as client:
            response = client.post(
                "/api/data-stream/post",
                headers={"x-api-key": "secret-key"},
                json={
                    "location_id": "11111111-1111-4111-8111-111111111111",
                    "title": "Report",
                },
            )

    assert response.status_code == 403
    assert response.json() == {"error": "Tenant access denied"}


def test_unscoped_api_key_is_denied(monkeypatch):
    monkeypatch.setenv("KOKONUT_API_KEYS", "secret-key:verified-caller")
    with TestClient(create_app()) as client:
        response = client.post(
            "/api/data-stream/post",
            headers={"x-api-key": "secret-key"},
            json={
                "location_id": "11111111-1111-4111-8111-111111111111",
                "title": "Report",
            },
        )

    assert response.status_code == 403
    assert response.json()["reason"] == "api_key_scope_denied"


def test_capability_uses_route_resource_and_action():
    with patch("services.security.capabilities.CapabilityManager.verify") as verify:
        verify.return_value = {"holder": "field-agent"}
        with TestClient(create_app()) as client:
            with patch(
                "services.gateway.data_stream.create_gateway_data_stream_post",
                return_value={"id": DATA_STREAM_POST_ID},
            ):
                response = client.post(
                    "/api/data-stream/post",
                    headers={"x-capability-token": "token"},
                    json={"location_id": "11111111-1111-4111-8111-111111111111", "title": "Report"},
                )

    assert response.status_code == 201
    verify.assert_called_once_with(
        "token",
        resource="data_stream_post",
        action="create",
        location_id="11111111-1111-4111-8111-111111111111",
    )


def test_capability_auth_propagates_only_a_hash_for_database_revalidation():
    import hashlib

    from services.gateway.auth import verify_request

    with patch("services.security.capabilities.CapabilityManager.verify", return_value={"holder": "field-agent", "token_id": "token-id"}):
        result = verify_request(
            _FakeRequest({"x-capability-token": "opaque-capability"}),
            resource="mobile_device",
            action="revoke",
            location_id="loc-99",
        )

    assert result["authenticated"] is True
    assert result["credential_type"] == "capability_token"
    assert result["credential_hash"] == hashlib.sha256(b"opaque-capability").hexdigest()
    assert "opaque-capability" not in str(result)


def test_strict_scope_denies_two_part_scope(monkeypatch):
    """In strict mode, a 2-part scope must not match a location-specific request."""
    monkeypatch.setenv("KOKONUT_API_KEYS", "secret-key:my-service")
    monkeypatch.setenv("KOKONUT_API_KEY_SCOPES", "my-service:data_stream_post:create")
    monkeypatch.setenv("KOKONUT_STRICT_LOCATION_SCOPE", "true")
    with patch("services.gateway.data_stream.create_gateway_data_stream_post", return_value={"id": DATA_STREAM_POST_ID}):
        with TestClient(create_app()) as client:
            response = client.post(
                "/api/data-stream/post",
                headers={"x-api-key": "secret-key"},
                json={"location_id": "11111111-1111-4111-8111-111111111111", "title": "Report"},
            )

    assert response.status_code == 403
    assert response.json()["reason"] == "api_key_scope_denied"


def test_strict_scope_allows_three_part_scope(monkeypatch):
    """In strict mode, a 3-part scope matching the location is allowed."""
    monkeypatch.setenv("KOKONUT_API_KEYS", "secret-key:my-service")
    monkeypatch.setenv(
        "KOKONUT_API_KEY_SCOPES",
        "my-service:data_stream_post:create:11111111-1111-4111-8111-111111111111",
    )
    monkeypatch.setenv("KOKONUT_STRICT_LOCATION_SCOPE", "true")
    with patch("services.gateway.data_stream.create_gateway_data_stream_post", return_value={"id": DATA_STREAM_POST_ID}):
        with TestClient(create_app()) as client:
            response = client.post(
                "/api/data-stream/post",
                headers={"x-api-key": "secret-key"},
                json={"location_id": "11111111-1111-4111-8111-111111111111", "title": "Report"},
            )

    assert response.status_code == 201


def test_strict_scope_allows_wildcard_location(monkeypatch):
    """In strict mode, a scope with wildcard location matches any location."""
    monkeypatch.setenv("KOKONUT_API_KEYS", "secret-key:my-service")
    monkeypatch.setenv(
        "KOKONUT_API_KEY_SCOPES", "my-service:data_stream_post:create:*"
    )
    monkeypatch.setenv("KOKONUT_STRICT_LOCATION_SCOPE", "true")
    with patch("services.gateway.data_stream.create_gateway_data_stream_post", return_value={"id": DATA_STREAM_POST_ID}):
        with TestClient(create_app()) as client:
            response = client.post(
                "/api/data-stream/post",
                headers={"x-api-key": "secret-key"},
                json={"location_id": "11111111-1111-4111-8111-111111111111", "title": "Report"},
            )

    assert response.status_code == 201


def test_strict_scope_off_allows_two_part_scope(monkeypatch):
    """Without strict mode, a 2-part scope still matches any location (backward compat)."""
    monkeypatch.setenv("KOKONUT_API_KEYS", "secret-key:my-service")
    monkeypatch.setenv("KOKONUT_API_KEY_SCOPES", "my-service:data_stream_post:create")
    monkeypatch.setenv("KOKONUT_STRICT_LOCATION_SCOPE", "false")
    with patch("services.gateway.data_stream.create_gateway_data_stream_post", return_value={"id": DATA_STREAM_POST_ID}):
        with TestClient(create_app()) as client:
            response = client.post(
                "/api/data-stream/post",
                headers={"x-api-key": "secret-key"},
                json={"location_id": "11111111-1111-4111-8111-111111111111", "title": "Report"},
            )

    assert response.status_code == 201


def test_scope_checked_returned_on_success(monkeypatch):
    """Auth result includes scope_checked when a scope matches."""
    monkeypatch.setenv("KOKONUT_API_KEYS", "secret-key:my-service")
    monkeypatch.setenv(
        "KOKONUT_API_KEY_SCOPES", "my-service:data_stream_post:create:loc-99"
    )
    from services.gateway.auth import verify_request

    with patch("services.common.database.get_db"):
        result = verify_request(
            _FakeRequest({"x-api-key": "secret-key"}),
            resource="data_stream_post",
            action="create",
            location_id="loc-99",
        )

    assert result["authenticated"] is True
    assert result["scope_checked"] == "data_stream_post:create:loc-99"
    assert result["credential_type"] == "api_key"
    assert result["credential_hash"] == __import__("hashlib").sha256(
        b"secret-key"
    ).hexdigest()
    assert "secret-key" not in result["credential_hash"]


def test_scope_checked_none_on_denial(monkeypatch):
    """Auth result includes scope_checked=None when no scope matches."""
    monkeypatch.setenv("KOKONUT_API_KEYS", "secret-key:my-service")
    monkeypatch.setenv(
        "KOKONUT_API_KEY_SCOPES", "my-service:data_stream_post:create:loc-99"
    )
    from services.gateway.auth import verify_request

    with patch("services.common.database.get_db"):
        result = verify_request(
            _FakeRequest({"x-api-key": "secret-key"}),
            resource="data_stream_post",
            action="create",
            location_id="loc-other",
        )

    assert result["authenticated"] is False
    assert result["scope_checked"] is None


class _FakeRequest:
    """Minimal request stub for unit-testing verify_request directly."""

    def __init__(self, headers: dict):
        self.headers = headers
