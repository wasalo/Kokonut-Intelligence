"""OIDC operator authorization for Field Collector administration."""

from dataclasses import dataclass
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

pytest.importorskip("fastapi")
from starlette.testclient import TestClient  # noqa: E402

from services.gateway import operator_auth  # noqa: E402
from services.gateway.app import create_app  # noqa: E402

LOCATION_ID = "11111111-1111-4111-8111-111111111111"
OPERATOR_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"


@dataclass(frozen=True)
class _Principal:
    operator_id: str = OPERATOR_ID
    issuer: str = "https://identity.example"
    subject: str = "operator-subject"
    display_name: str | None = "Field reviewer"
    email: str | None = None


@dataclass(frozen=True)
class _Session:
    session_id: str = "session-id"
    csrf_token_hash: str = "not-used-by-fake"
    operator: _Principal = _Principal()


class _FakeProvider:
    def __init__(self, *, allowed=True):
        self.allowed = allowed
        self.session = _Session()
        self.settings = SimpleNamespace(state_secret="test-state-secret-with-at-least-32-bytes")

    def authenticate_request(self, request):
        if request.cookies.get(operator_auth.SESSION_COOKIE) == "valid-session":
            return self.session
        return None

    def csrf_valid(self, request, _session):
        return (
            request.cookies.get(operator_auth.CSRF_COOKIE) == "valid-csrf"
            and request.headers.get("x-csrf-token") == "valid-csrf"
        )

    def has_scope(self, operator_id, resource, action, location_id):
        return (
            self.allowed
            and operator_id == OPERATOR_ID
            and resource == "mobile_device"
            and action == "enroll"
            and location_id == LOCATION_ID
        )

    def list_scopes(self, _operator_id):
        return []

    def revoke_session(self, _session_id):
        return None


def test_operator_mobile_routes_require_location_scoped_actions():
    create_policy = operator_auth.auth_route_policy(
        "POST",
        f"/operator/api/mobile/locations/{LOCATION_ID}/enrollments",
        enabled=True,
    )
    revoke_enrollment_policy = operator_auth.auth_route_policy(
        "DELETE",
        f"/operator/api/mobile/locations/{LOCATION_ID}/enrollments/22222222-2222-4222-8222-222222222222",
        enabled=True,
    )
    revoke_device_policy = operator_auth.auth_route_policy(
        "POST",
        f"/operator/api/mobile/locations/{LOCATION_ID}/devices/field-phone/revoke",
        enabled=True,
    )

    assert create_policy["resource"] == "mobile_device"
    assert create_policy["action"] == "enroll"
    assert create_policy["location_id"] == LOCATION_ID
    assert revoke_enrollment_policy["action"] == "revoke"
    assert revoke_device_policy["action"] == "revoke"
    assert operator_auth.auth_route_policy(
        "POST",
        f"/operator/api/mobile/locations/{LOCATION_ID}/enrollments",
        enabled=False,
    ) is None


@pytest.mark.parametrize(
    ("session", "scope", "csrf", "status"),
    [
        (False, True, True, 401),
        (True, False, True, 403),
        (True, True, False, 403),
        (True, True, True, 201),
    ],
)
def test_oidc_operator_can_issue_enrollment_only_with_session_scope_and_csrf(
    monkeypatch, session, scope, csrf, status
):
    provider = _FakeProvider(allowed=scope)
    monkeypatch.setattr(operator_auth, "create_provider", lambda: provider)
    connection = MagicMock()
    cursor = connection.cursor.return_value
    cursor.fetchone.return_value = (
        "33333333-3333-4333-8333-333333333333",
        "2030-01-01T00:00:00+00:00",
    )
    monkeypatch.setattr("services.mobile.api.get_db", lambda: connection)
    audit_records = []
    monkeypatch.setattr(
        "services.gateway.audit.GatewayAudit.reserve_mutation",
        lambda _self: "test-reservation",
    )
    monkeypatch.setattr(
        "services.gateway.audit.GatewayAudit.release_mutation",
        lambda _self, _reservation: None,
    )
    monkeypatch.setattr(
        "services.gateway.audit.GatewayAudit.log",
        lambda _self, **record: audit_records.append(record),
    )

    headers = {}
    with TestClient(create_app()) as client:
        if session:
            client.cookies.set(
                operator_auth.SESSION_COOKIE,
                "valid-session",
                path=operator_auth.SESSION_COOKIE_PATH,
            )
        if csrf:
            client.cookies.set(
                operator_auth.CSRF_COOKIE,
                "valid-csrf",
                path=operator_auth.SESSION_COOKIE_PATH,
            )
            headers["X-CSRF-Token"] = "valid-csrf"
        response = client.post(
            f"/operator/api/mobile/locations/{LOCATION_ID}/enrollments",
            headers=headers,
            json={"user_id": "collector-17", "expires_in_minutes": 60},
        )

    assert response.status_code == status, response.text
    if status == 201:
        assert response.headers["cache-control"] == "no-store"
        assert len(response.json()["enrollment_code"]) >= 32
        assert cursor.execute.call_args.args[1][1:4] == (
            "collector-17",
            LOCATION_ID,
            f"operator:{OPERATOR_ID}",
        )
        connection.commit.assert_called_once()
        assert audit_records[-1]["caller"] == f"operator:{OPERATOR_ID}"
        assert audit_records[-1]["location_id"] == LOCATION_ID
    else:
        connection.cursor.assert_not_called()
        connection.commit.assert_not_called()
