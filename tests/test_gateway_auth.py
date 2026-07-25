"""Focused gateway authorization tests."""

from unittest.mock import patch

import pytest

pytest.importorskip("fastapi")
from starlette.testclient import TestClient  # noqa: E402

from services.gateway.app import create_app  # noqa: E402


def test_anonymous_public_read_is_allowed():
    with TestClient(create_app()) as client:
        response = client.get("/api/iri/resolve", params={"iri": "missing"})

    assert response.status_code != 401


def test_anonymous_write_is_denied():
    with TestClient(create_app()) as client:
        response = client.post("/api/data-stream/post", json={"location_id": "location-1"})

    assert response.status_code == 401
    assert response.json()["error"] == "Unauthorized"


def test_authenticated_write_uses_verified_actor(monkeypatch):
    monkeypatch.setenv("KOKONUT_API_KEYS", "secret-key:verified-caller")
    monkeypatch.setenv("KOKONUT_API_KEY_SCOPES", "verified-caller:data_stream_post:create")
    with patch("services.data_stream.post.create_post", return_value="post-1") as create_post:
        with TestClient(create_app()) as client:
            response = client.post(
                "/api/data-stream/post",
                headers={"x-api-key": "secret-key"},
                json={
                    "location_id": "location-1",
                    "title": "Report",
                    "created_by": "spoofed-actor",
                },
            )

    assert response.status_code == 201
    assert response.json() == {"post_id": "post-1"}
    assert create_post.call_args.kwargs["created_by"] == "verified-caller"


def test_unscoped_api_key_is_denied(monkeypatch):
    monkeypatch.setenv("KOKONUT_API_KEYS", "secret-key:verified-caller")
    with TestClient(create_app()) as client:
        response = client.post(
            "/api/data-stream/post",
            headers={"x-api-key": "secret-key"},
            json={"location_id": "location-1", "title": "Report"},
        )

    assert response.status_code == 403
    assert response.json()["reason"] == "api_key_scope_denied"


def test_capability_uses_route_resource_and_action():
    with patch("services.security.capabilities.CapabilityManager.verify") as verify:
        verify.return_value = {"holder": "field-agent"}
        with TestClient(create_app()) as client:
            with patch("services.data_stream.post.create_post", return_value="post-1"):
                response = client.post(
                    "/api/data-stream/post",
                    headers={"x-capability-token": "token"},
                    json={"location_id": "location-1"},
                )

    assert response.status_code == 201
    verify.assert_called_once_with(
        "token",
        resource="data_stream_post",
        action="create",
        location_id="location-1",
    )


def test_strict_scope_denies_two_part_scope(monkeypatch):
    """In strict mode, a 2-part scope must not match a location-specific request."""
    monkeypatch.setenv("KOKONUT_API_KEYS", "secret-key:my-service")
    monkeypatch.setenv("KOKONUT_API_KEY_SCOPES", "my-service:data_stream_post:create")
    monkeypatch.setenv("KOKONUT_STRICT_LOCATION_SCOPE", "true")
    with patch("services.data_stream.post.create_post", return_value="post-1"):
        with TestClient(create_app()) as client:
            response = client.post(
                "/api/data-stream/post",
                headers={"x-api-key": "secret-key"},
                json={"location_id": "location-1", "title": "Report"},
            )

    assert response.status_code == 403
    assert response.json()["reason"] == "api_key_scope_denied"


def test_strict_scope_allows_three_part_scope(monkeypatch):
    """In strict mode, a 3-part scope matching the location is allowed."""
    monkeypatch.setenv("KOKONUT_API_KEYS", "secret-key:my-service")
    monkeypatch.setenv(
        "KOKONUT_API_KEY_SCOPES", "my-service:data_stream_post:create:location-1"
    )
    monkeypatch.setenv("KOKONUT_STRICT_LOCATION_SCOPE", "true")
    with patch("services.data_stream.post.create_post", return_value="post-1"):
        with TestClient(create_app()) as client:
            response = client.post(
                "/api/data-stream/post",
                headers={"x-api-key": "secret-key"},
                json={"location_id": "location-1", "title": "Report"},
            )

    assert response.status_code == 201


def test_strict_scope_allows_wildcard_location(monkeypatch):
    """In strict mode, a scope with wildcard location matches any location."""
    monkeypatch.setenv("KOKONUT_API_KEYS", "secret-key:my-service")
    monkeypatch.setenv(
        "KOKONUT_API_KEY_SCOPES", "my-service:data_stream_post:create:*"
    )
    monkeypatch.setenv("KOKONUT_STRICT_LOCATION_SCOPE", "true")
    with patch("services.data_stream.post.create_post", return_value="post-1"):
        with TestClient(create_app()) as client:
            response = client.post(
                "/api/data-stream/post",
                headers={"x-api-key": "secret-key"},
                json={"location_id": "location-1", "title": "Report"},
            )

    assert response.status_code == 201


def test_strict_scope_off_allows_two_part_scope(monkeypatch):
    """Without strict mode, a 2-part scope still matches any location (backward compat)."""
    monkeypatch.setenv("KOKONUT_API_KEYS", "secret-key:my-service")
    monkeypatch.setenv("KOKONUT_API_KEY_SCOPES", "my-service:data_stream_post:create")
    monkeypatch.setenv("KOKONUT_STRICT_LOCATION_SCOPE", "false")
    with patch("services.data_stream.post.create_post", return_value="post-1"):
        with TestClient(create_app()) as client:
            response = client.post(
                "/api/data-stream/post",
                headers={"x-api-key": "secret-key"},
                json={"location_id": "location-1", "title": "Report"},
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
