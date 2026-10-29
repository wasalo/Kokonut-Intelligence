"""Strict request/response contract for tenant-scoped Data Stream draft creation."""

from unittest.mock import Mock

import pytest

pytest.importorskip("fastapi")
from starlette.testclient import TestClient  # noqa: E402

from services.data_stream.post import VALID_POST_TYPES  # noqa: E402
from services.gateway.app import create_app  # noqa: E402
from services.gateway.data_stream_models import DataStreamPostType  # noqa: E402

LOCATION_ID = "11111111-1111-4111-8111-111111111111"
POST_ID = "33333333-3333-4333-8333-333333333333"


def _client(monkeypatch, tmp_path):
    monkeypatch.setenv("KOKONUT_API_KEYS", "writer-key:writer")
    monkeypatch.setenv("KOKONUT_API_KEY_SCOPES", "writer:data_stream_post:create")
    monkeypatch.setenv(
        "KOKONUT_GATEWAY_AUDIT_SPOOL_PATH",
        str(tmp_path / "gateway-audit.sqlite3"),
    )
    return TestClient(create_app())


def test_create_post_openapi_matches_source_types_and_exact_success_shape(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    schema = client.app.openapi()
    operation = schema["paths"]["/api/data-stream/post"]["post"]
    request_schema_ref = operation["requestBody"]["content"]["application/json"]["schema"]["$ref"]
    response_schema_ref = operation["responses"]["201"]["content"]["application/json"]["schema"]["$ref"]
    schemas = schema["components"]["schemas"]
    request_schema = schemas[request_schema_ref.rsplit("/", 1)[-1]]
    response_schema = schemas[response_schema_ref.rsplit("/", 1)[-1]]

    assert operation["operationId"] == "createDataStreamPost"
    assert request_schema["additionalProperties"] is False
    assert set(request_schema["properties"]) == {
        "location_id", "post_type", "title", "content", "expires_at"
    }
    assert request_schema["required"] == ["location_id", "title"]
    assert set(request_schema["properties"]["post_type"]["enum"]) == VALID_POST_TYPES
    assert set(DataStreamPostType.__args__) == VALID_POST_TYPES
    assert response_schema["additionalProperties"] is False
    assert set(response_schema["properties"]) == {"post_id"}
    assert "422" in operation["responses"]


def test_private_standard_routes_document_alternative_gateway_credentials(
    monkeypatch, tmp_path
):
    app = _client(monkeypatch, tmp_path).app
    schema = app.openapi()
    expected_security = [
        {"GatewayApiKey": []},
        {"GatewayCapabilityToken": []},
    ]
    schemes = schema["components"]["securitySchemes"]

    assert schemes["GatewayApiKey"] == {
        "type": "apiKey",
        "in": "header",
        "name": "x-api-key",
        "description": "Scoped Gateway service API key.",
    }
    assert schemes["GatewayCapabilityToken"] == {
        "type": "apiKey",
        "in": "header",
        "name": "x-capability-token",
        "description": "Resource-scoped Gateway capability token.",
    }
    protected_operations = (
        ("/api/data-stream/post", "post"),
        ("/api/data-stream/posts", "get"),
        ("/api/data-stream/posts/{post_id}/files", "get"),
        ("/api/data-stream/posts/{post_id}/attestation", "get"),
        ("/api/health/services", "get"),
    )
    for path, method in protected_operations:
        assert schema["paths"][path][method]["security"] == expected_security

    public_or_self_authenticated = (
        ("/api/drivers", "get"),
        ("/health", "get"),
        ("/api/mobile/sync", "post"),
    )
    for path, method in public_or_self_authenticated:
        assert "security" not in schema["paths"][path][method]


def test_create_post_returns_only_the_draft_identifier_and_passes_allowlisted_input(
    monkeypatch, tmp_path
):
    create = Mock(return_value={"id": POST_ID})
    monkeypatch.setattr(
        "services.gateway.data_stream.create_gateway_data_stream_post", create
    )
    with _client(monkeypatch, tmp_path) as client:
        response = client.post(
            "/api/data-stream/post",
            headers={"x-api-key": "writer-key"},
            json={"location_id": LOCATION_ID, "title": "Field note"},
        )

    assert response.status_code == 201
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {"post_id": POST_ID}
    assert create.call_args.args[0] == {
        "location_id": LOCATION_ID,
        "post_type": "monitoring_report",
        "title": "Field note",
        "content": "",
        "expires_at": None,
    }
    assert create.call_args.args[1]["resource"] == "data_stream_post"
    assert create.call_args.args[1]["action"] == "create"
    assert "created_by" not in create.call_args.args[0]


@pytest.mark.parametrize(
    "body",
    [
        {"location_id": LOCATION_ID},
        {"location_id": LOCATION_ID, "title": "x" * 256},
        {"location_id": LOCATION_ID, "title": "Field note", "post_type": "unknown"},
        {"location_id": LOCATION_ID, "title": "Field note", "content": []},
        {
            "location_id": LOCATION_ID,
            "title": "Field note",
            "expires_at": "2026-11-01T12:00:00",
        },
        {"location_id": LOCATION_ID, "title": "Field note", "expires_at": 1_798_742_400},
        {"location_id": LOCATION_ID, "title": "Field note", "created_by": POST_ID},
        {"location_id": "not-a-uuid", "title": "Field note"},
    ],
)
def test_invalid_or_untrusted_create_fields_fail_before_service_access(monkeypatch, tmp_path, body):
    create = Mock()
    monkeypatch.setattr(
        "services.gateway.data_stream.create_gateway_data_stream_post", create
    )
    with _client(monkeypatch, tmp_path) as client:
        response = client.post(
            "/api/data-stream/post",
            headers={"x-api-key": "writer-key"},
            json=body,
        )

    assert response.status_code == 422
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {"error": "Data Stream post request is invalid"}
    assert "created_by" not in response.text
    create.assert_not_called()


def test_malformed_service_identifier_fails_closed_without_leaking_result(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "services.gateway.data_stream.create_gateway_data_stream_post",
        lambda *_args: {"id": "not-a-uuid", "private": "secret"},
    )
    with _client(monkeypatch, tmp_path) as client:
        response = client.post(
            "/api/data-stream/post",
            headers={"x-api-key": "writer-key"},
            json={"location_id": LOCATION_ID, "title": "Field note"},
        )

    assert response.status_code == 500
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {"error": "Data Stream post creation unavailable"}
    assert "secret" not in response.text
