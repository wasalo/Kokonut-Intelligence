"""In-process OIDC adapter and operator-session route contract checks."""

from __future__ import annotations

import hashlib
import hmac
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402
from starlette.responses import RedirectResponse  # noqa: E402

from services.gateway.operator_auth import (  # noqa: E402
    CSRF_COOKIE,
    SESSION_COOKIE,
    OperatorPrincipal,
    OperatorSession,
)

_SESSION_TOKEN = "synthetic-opaque-session-token"
_CSRF_TOKEN = "synthetic-csrf-token"
_SESSION_HASH = "a" * 64
_LOCATION_ID = "11111111-1111-4111-8111-111111111111"


class _FakeOIDCClient:
    def __init__(self):
        self.token = {
            "userinfo": {
                "iss": "https://identity.example.test",
                "sub": "operator-subject-1",
                "name": "Synthetic Operator",
                "email": "operator@example.test",
            }
        }
        self.login_session = None

    async def authorize_redirect(self, request, *, redirect_uri):
        self.login_session = dict(request.session)
        request.session["synthetic_oidc_state"] = "synthetic-state"
        request.session["synthetic_pkce_verifier"] = "synthetic-verifier"
        self.redirect_uri = redirect_uri
        return RedirectResponse(
            "https://identity.example.test/authorize?state=synthetic-state",
            status_code=302,
        )

    async def authorize_access_token(self, request):
        state = parse_qs(urlsplit(str(request.url)).query).get("state", [None])[0]
        if state != request.session.get("synthetic_oidc_state"):
            raise ValueError("synthetic OIDC state mismatch")
        return self.token


class _FakeOIDCProvider:
    def __init__(self):
        self.settings = SimpleNamespace(
            issuer="https://identity.example.test",
            state_secret="synthetic-state-secret-with-at-least-32-bytes",
            redirect_uri="https://kernel.example.test/operator/auth/callback",
            session_ttl_seconds=1200,
        )
        self.client = _FakeOIDCClient()
        self.created_claims = []
        self.revoked_sessions = []
        self.active = False
        self.operator = OperatorPrincipal(
            operator_id="22222222-2222-4222-8222-222222222222",
            issuer="https://identity.example.test",
            subject="operator-subject-1",
            display_name="Synthetic Operator",
            email="operator@example.test",
        )
        self.session = OperatorSession(
            session_id="session-id-1",
            csrf_token_hash=hashlib.sha256(_CSRF_TOKEN.encode()).hexdigest(),
            operator=self.operator,
            session_token_hash=_SESSION_HASH,
        )

    def create_session(self, claims):
        self.created_claims.append(dict(claims))
        issuer = claims.get("iss")
        subject = claims.get("sub")
        if (
            issuer != self.settings.issuer
            or not isinstance(subject, str)
            or not subject
            or len(subject) > 255
            or subject == "unprovisioned-subject"
        ):
            return None
        self.active = True
        return self.operator, _SESSION_TOKEN, _CSRF_TOKEN

    def authenticate_request(self, request):
        if self.active and request.cookies.get(SESSION_COOKIE) == _SESSION_TOKEN:
            return self.session
        return None

    def csrf_valid(self, request, session):
        supplied = request.headers.get("X-CSRF-Token", "")
        cookie = request.cookies.get(CSRF_COOKIE, "")
        return hmac.compare_digest(supplied, cookie) and hmac.compare_digest(
            hashlib.sha256(cookie.encode()).hexdigest(), session.csrf_token_hash
        )

    def has_scope(self, operator_id, resource, action, location_id):
        return operator_id == self.operator.operator_id and location_id == _LOCATION_ID

    def list_scopes(self, operator_id):
        assert operator_id == self.operator.operator_id
        return [
            {
                "resource": "mobile_device",
                "action": "read",
                "location_id": _LOCATION_ID,
            }
        ]

    def revoke_session(self, session_id):
        self.revoked_sessions.append(session_id)
        self.active = False


class _AllowRateLimiter:
    def check(self, _key):
        return True

    def retry_after(self, _key):
        return 0


def _client(monkeypatch, tmp_path, provider):
    monkeypatch.setenv(
        "KOKONUT_GATEWAY_AUDIT_SPOOL_PATH",
        str(tmp_path / "operator-oidc-audit.sqlite3"),
    )
    monkeypatch.setenv("KOKONUT_API_KEYS", "")
    monkeypatch.setenv("KOKONUT_API_KEY_SCOPES", "")

    from services.gateway.audit import GatewayAudit

    monkeypatch.setattr(GatewayAudit, "_write_record", lambda _self, _event: None)

    import services.gateway.operator_auth as operator_auth

    monkeypatch.setattr(operator_auth, "create_provider", lambda: provider)
    from services.gateway.app import create_app

    return TestClient(
        create_app(rate_limiter=_AllowRateLimiter()),
        base_url="https://kernel.example.test",
        follow_redirects=False,
    )


def _login(client):
    response = client.get("/operator/auth/login")
    assert response.status_code == 302
    return response


def test_oidc_login_session_and_logout_use_opaque_cookie_contract(
    monkeypatch, tmp_path
):
    provider = _FakeOIDCProvider()
    with _client(monkeypatch, tmp_path, provider) as client:
        login = _login(client)
        assert provider.client.login_session == {}
        assert provider.client.redirect_uri == provider.settings.redirect_uri
        assert parse_qs(urlsplit(login.headers["location"]).query)["state"] == [
            "synthetic-state"
        ]

        callback = client.get(
            "/operator/auth/callback?code=synthetic-code&state=synthetic-state"
        )
        assert callback.status_code == 303
        assert callback.headers["location"] == "/operator/"
        assert provider.created_claims == [provider.client.token["userinfo"]]
        assert client.cookies.get(SESSION_COOKIE) == _SESSION_TOKEN
        assert client.cookies.get(CSRF_COOKIE) == _CSRF_TOKEN
        assert "HttpOnly" in callback.headers["set-cookie"]
        assert "Secure" in callback.headers["set-cookie"]
        assert _SESSION_TOKEN not in callback.text

        session = client.get("/operator/auth/session")
        assert session.status_code == 200
        assert session.headers["cache-control"] == "no-store"
        assert session.headers["vary"] == "Cookie"
        assert session.json()["scopes"][0]["location_id"] == _LOCATION_ID

        logout = client.post(
            "/operator/auth/logout",
            headers={"X-CSRF-Token": _CSRF_TOKEN},
        )
        assert logout.status_code == 200
        assert provider.revoked_sessions == ["session-id-1"]
        assert client.get("/operator/auth/session").status_code == 401


@pytest.mark.parametrize(
    ("userinfo", "expected_status"),
    [
        (None, 401),
        ({}, 403),
        (
            {"iss": "https://identity.example.test", "sub": "unprovisioned-subject"},
            403,
        ),
    ],
)
def test_oidc_callback_fails_closed_without_verified_provisioned_identity(
    monkeypatch, tmp_path, userinfo, expected_status
):
    provider = _FakeOIDCProvider()
    provider.client.token = {"userinfo": userinfo}
    with _client(monkeypatch, tmp_path, provider) as client:
        _login(client)
        response = client.get(
            "/operator/auth/callback?code=synthetic-code&state=synthetic-state"
        )

    assert response.status_code == expected_status
    assert _SESSION_TOKEN not in response.headers.get("set-cookie", "")
    assert _SESSION_TOKEN not in response.text


def test_oidc_logout_rejects_missing_csrf_without_revoking_session(monkeypatch, tmp_path):
    provider = _FakeOIDCProvider()
    with _client(monkeypatch, tmp_path, provider) as client:
        _login(client)
        client.get("/operator/auth/callback?code=synthetic-code&state=synthetic-state")
        response = client.post("/operator/auth/logout")

    assert response.status_code == 403
    assert response.json()["reason"] == "csrf_validation_failed"
    assert provider.revoked_sessions == []
