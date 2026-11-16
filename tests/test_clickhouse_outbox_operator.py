from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import UUID

import pytest

pytest.importorskip("fastapi")
from starlette.testclient import TestClient

from services.gateway import clickhouse_outbox_operator, operator_auth
from services.gateway.app import create_app
from services.gateway.audit import GatewayAudit

_OUTBOX_ID = UUID("33333333-3333-4333-8333-333333333338")
_OPERATOR_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
_SESSION_HASH = "a" * 64


class _Provider:
    def __init__(self, capabilities=(), *, authenticated=True):
        self.capabilities = set(capabilities)
        self.authenticated = authenticated
        self.checked_capabilities = []
        self.session = SimpleNamespace(
            session_id="session-id",
            csrf_token_hash="unused-by-fake",
            session_token_hash=_SESSION_HASH,
            operator=SimpleNamespace(operator_id=_OPERATOR_ID),
        )
        self.settings = SimpleNamespace(state_secret="test-state-secret-with-at-least-32-bytes")

    def authenticate_request(self, request):
        if self.authenticated and request.cookies.get(operator_auth.SESSION_COOKIE) == "valid-session":
            return self.session
        return None

    def has_global_capability(self, session_token_hash, capability):
        self.checked_capabilities.append((session_token_hash, capability))
        return capability in self.capabilities

    def has_scope(self, *_args):
        return False

    def csrf_valid(self, request, _session):
        return (
            request.cookies.get(operator_auth.CSRF_COOKIE) == "valid-csrf"
            and request.headers.get("x-csrf-token") == "valid-csrf"
        )

    def list_scopes(self, _operator_id):
        return []

    def revoke_session(self, _session_id):
        return None


def _app(monkeypatch, provider):
    monkeypatch.setattr(operator_auth, "create_provider", lambda: provider)
    monkeypatch.setattr(GatewayAudit, "log", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(GatewayAudit, "reserve_mutation", lambda _self: "reservation")
    monkeypatch.setattr(GatewayAudit, "release_mutation", lambda *_args: None)
    monkeypatch.setattr(GatewayAudit, "replay_pending", lambda *_args: 0)
    monkeypatch.setattr(GatewayAudit, "capture_status", lambda _self: "ok")
    return create_app()


def _set_session(client, *, csrf=False):
    client.cookies.set(operator_auth.SESSION_COOKIE, "valid-session")
    if csrf:
        client.cookies.set(operator_auth.CSRF_COOKIE, "valid-csrf")


def _assert_private(response):
    assert response.headers["cache-control"] == "no-store"
    assert "cookie" in response.headers["vary"].lower()
    assert response.headers["x-content-type-options"] == "nosniff"


def test_list_dead_letters_uses_the_dedicated_operator_database_login(monkeypatch):
    provider = _Provider({"clickhouse_outbox:read"})
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = ({"items": [], "capabilities": {"replay": False}},)
    monkeypatch.setattr(
        clickhouse_outbox_operator, "_operator_action_connection", lambda: connection
    )

    with TestClient(_app(monkeypatch, provider)) as client:
        _set_session(client)
        response = client.get("/operator/api/clickhouse-outbox/dead-letters")

    assert response.status_code == 200, response.text
    _assert_private(response)
    assert provider.checked_capabilities == [(_SESSION_HASH, "clickhouse_outbox:read")]
    cursor.execute.assert_called_once_with(
        "SELECT kokonut_security.list_clickhouse_outbox_operator_dead_letters(%s, %s)",
        (_SESSION_HASH, 50),
    )
    connection.close.assert_called_once()


@pytest.mark.parametrize(
    ("action", "capability", "expected_audit_action"),
    [
        ("replay", "clickhouse_outbox:replay", "replay"),
        ("resolve", "clickhouse_outbox:resolve", "resolve"),
        ("discard", "clickhouse_outbox:discard", "discard"),
    ],
)
def test_dead_letter_actions_require_capability_csrf_and_reason(
    monkeypatch, action, capability, expected_audit_action
):
    provider = _Provider({capability})
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = ({"id": str(_OUTBOX_ID), "action": expected_audit_action},)
    monkeypatch.setattr(
        clickhouse_outbox_operator, "_operator_action_connection", lambda: connection
    )

    with TestClient(_app(monkeypatch, provider)) as client:
        _set_session(client, csrf=True)
        response = client.post(
            f"/operator/api/clickhouse-outbox/dead-letters/{_OUTBOX_ID}/{action}",
            headers={"X-CSRF-Token": "valid-csrf"},
            json={"reason": "Reviewed by operator"},
        )

    assert response.status_code == 200, response.text
    _assert_private(response)
    assert provider.checked_capabilities == [(_SESSION_HASH, capability)]
    cursor.execute.assert_called_once_with(
        "SELECT kokonut_security.transition_clickhouse_outbox_operator_dead_letter(%s, %s, %s, %s)",
        (_SESSION_HASH, _OUTBOX_ID, action, "Reviewed by operator"),
    )
    connection.close.assert_called_once()


def test_missing_global_capability_denies_before_opening_operator_connection(monkeypatch):
    provider = _Provider()
    monkeypatch.setattr(
        clickhouse_outbox_operator,
        "_operator_action_connection",
        lambda: pytest.fail("a denied action must not open the operator database login"),
    )

    with TestClient(_app(monkeypatch, provider)) as client:
        _set_session(client, csrf=True)
        response = client.post(
            f"/operator/api/clickhouse-outbox/dead-letters/{_OUTBOX_ID}/discard",
            headers={"X-CSRF-Token": "valid-csrf"},
            json={"reason": "Reviewed"},
        )

    assert response.status_code == 403
    _assert_private(response)
    assert response.json() == {"error": "Unauthorized", "reason": "operator_global_capability_denied"}


def test_unauthenticated_outbox_request_is_private_and_does_not_connect(monkeypatch):
    provider = _Provider(authenticated=False)
    monkeypatch.setattr(
        clickhouse_outbox_operator,
        "_operator_action_connection",
        lambda: pytest.fail("unauthenticated requests must not open the operator database login"),
    )

    with TestClient(_app(monkeypatch, provider)) as client:
        response = client.get("/operator/api/clickhouse-outbox/dead-letters")

    assert response.status_code == 401
    _assert_private(response)


def test_invalid_outbox_body_returns_generic_private_validation_error(monkeypatch):
    provider = _Provider({"clickhouse_outbox:replay"})
    monkeypatch.setattr(
        clickhouse_outbox_operator,
        "_operator_action_connection",
        lambda: pytest.fail("invalid request bodies must not open the operator database login"),
    )

    with TestClient(_app(monkeypatch, provider)) as client:
        _set_session(client, csrf=True)
        response = client.post(
            f"/operator/api/clickhouse-outbox/dead-letters/{_OUTBOX_ID}/replay",
            headers={"X-CSRF-Token": "valid-csrf"},
            json={"reason": "private malformed input", "extra": "do not echo"},
        )

    assert response.status_code == 422
    _assert_private(response)
    assert response.json() == {"error": "ClickHouse outbox request is invalid"}
