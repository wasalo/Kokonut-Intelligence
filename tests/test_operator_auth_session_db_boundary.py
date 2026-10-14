"""The OIDC provider uses a separate, narrow database principal for sessions."""

from hashlib import sha256
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

pytest.importorskip("fastapi")

from services.gateway import operator_auth  # noqa: E402

OPERATOR_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
ISSUER = "https://identity.example"


def _provider():
    provider = object.__new__(operator_auth.OIDCOperatorProvider)
    provider.settings = SimpleNamespace(
        issuer=ISSUER,
        session_ttl_seconds=1800,
        operator_auth_user="kokonut_operator_auth",
        operator_auth_password="test-secret-do-not-print-" * 2,
    )
    return provider


def _connection(row):
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = row
    return connection, cursor


def test_create_session_uses_function_and_never_returns_secret_hashes(monkeypatch):
    connection, cursor = _connection(
        (
            "session-id",
            OPERATOR_ID,
            ISSUER,
            "operator-subject",
            "Field operator",
            "operator@example.test",
        )
    )
    connections = []
    monkeypatch.setattr(
        operator_auth,
        "_get_operator_auth_db",
        lambda settings: (connections.append(settings) or connection),
    )

    result = _provider().create_session(
        {
            "iss": ISSUER,
            "sub": "operator-subject",
            "name": "Field operator",
            "email": "operator@example.test",
            "email_verified": True,
        }
    )

    assert result is not None
    principal, session_token, csrf_token = result
    assert principal.operator_id == OPERATOR_ID
    assert session_token and csrf_token
    assert len(connections) == 1
    assert connections[0].operator_auth_user == "kokonut_operator_auth"
    statement, params = cursor.execute.call_args.args
    assert "kokonut_security.create_operator_session" in statement
    assert "FROM operator_session" not in statement
    assert "UPDATE operator_session" not in statement
    assert params[0:2] == (ISSUER, "operator-subject")
    assert params[4] == sha256(session_token.encode()).hexdigest()
    assert params[5] == sha256(csrf_token.encode()).hexdigest()
    assert session_token not in params and csrf_token not in params
    connection.commit.assert_called_once()
    connection.close.assert_called_once()


def test_authenticate_uses_bounded_function_with_cookie_digest(monkeypatch):
    connection, cursor = _connection(
        (
            "session-id",
            "c" * 64,
            OPERATOR_ID,
            ISSUER,
            "operator-subject",
            "Field operator",
            None,
        )
    )
    monkeypatch.setattr(operator_auth, "_get_operator_auth_db", lambda _settings: connection)
    bearer = "browser-only-session-value"
    request = SimpleNamespace(cookies={operator_auth.SESSION_COOKIE: bearer})

    session = _provider().authenticate_request(request)

    assert session is not None
    assert session.session_id == "session-id"
    assert session.operator.operator_id == OPERATOR_ID
    assert session.session_token_hash == sha256(bearer.encode()).hexdigest()
    statement, params = cursor.execute.call_args.args
    assert "kokonut_security.authenticate_operator_session" in statement
    assert "FROM operator_session" not in statement
    assert "UPDATE operator_session" not in statement
    assert params == (sha256(bearer.encode()).hexdigest(),)
    connection.commit.assert_called_once()
    connection.close.assert_called_once()


def test_revoke_uses_bounded_function_on_operator_auth_connection(monkeypatch):
    connection, cursor = _connection(None)
    provider = _provider()
    operator_auth_settings = provider.settings
    connections = []
    monkeypatch.setattr(
        operator_auth,
        "_get_operator_auth_db",
        lambda settings: (connections.append(settings) or connection),
    )

    provider.revoke_session("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")

    statement, params = cursor.execute.call_args.args
    assert "kokonut_security.revoke_operator_session" in statement
    assert "UPDATE operator_session" not in statement
    assert params == ("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",)
    assert connections[0] is operator_auth_settings
    connection.commit.assert_called_once()
    connection.close.assert_called_once()


def test_oidc_configuration_requires_distinct_operator_auth_credentials(monkeypatch):
    required = {
        "KOKONUT_OPERATOR_OIDC_ENABLED": "true",
        "KOKONUT_OPERATOR_OIDC_ISSUER": ISSUER,
        "KOKONUT_OPERATOR_OIDC_CLIENT_ID": "kernel-test",
        "KOKONUT_OPERATOR_OIDC_CLIENT_SECRET": "oidc-client-secret",
        "KOKONUT_OPERATOR_OIDC_REDIRECT_URI": "https://localhost:8448/operator/auth/callback",
        "KOKONUT_OPERATOR_OIDC_STATE_SECRET": "s" * 32,
        "KOKONUT_OPERATOR_AUTH_USER": "kokonut_operator_auth",
        "KOKONUT_OPERATOR_AUTH_PASSWORD": "auth-role-secret-that-is-distinct-123456",
        "PG_PASSWORD": "application-role-secret-1234567890",
        "POSTGRES_PASSWORD": "database-owner-secret-1234567890",
        "KOKONUT_RUNTIME_PASSWORD": "application-role-secret-1234567890",
    }
    for key, value in required.items():
        monkeypatch.setenv(key, value)

    settings = operator_auth.OIDCSettings.from_env()
    assert settings is not None
    assert settings.operator_auth_user == "kokonut_operator_auth"
    assert "auth-role-secret" not in repr(settings)

    monkeypatch.setenv(
        "KOKONUT_OPERATOR_AUTH_PASSWORD",
        required["PG_PASSWORD"],
    )
    with pytest.raises(operator_auth.OperatorAuthConfigurationError, match="must differ"):
        operator_auth.OIDCSettings.from_env()

    monkeypatch.delenv("KOKONUT_OPERATOR_AUTH_PASSWORD")
    with pytest.raises(operator_auth.OperatorAuthConfigurationError, match="required settings"):
        operator_auth.OIDCSettings.from_env()
