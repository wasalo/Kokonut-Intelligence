"""Contracts for pseudonymous Delphi participant consent and withdrawal."""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from services.gateway import delphi_participant_acceptance as acceptance

pytest.importorskip("fastapi")
from fastapi import APIRouter, FastAPI  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

INVITE_TOKEN = "a1" * 32
NOTICE_DIGEST = "b2" * 32
SESSION_TOKEN = "c3" * 32
CSRF_TOKEN = "d4" * 32
REQUEST_ID = str(uuid4())
NOW = datetime(2026, 10, 25, 12, 0, tzinfo=timezone.utc)


class _Connection:
    def __init__(self, row=None):
        self.row = row
        self.calls = []
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def cursor(self):
        return _Cursor(self)

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


class _Cursor:
    def __init__(self, connection):
        self.connection = connection

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def execute(self, query, params=None):
        self.connection.calls.append((" ".join(query.split()), params))

    def fetchone(self):
        return self.connection.row


def test_preview_calls_only_bounded_function_and_closes_connection():
    connection = _Connection((
        "Watershed priorities",
        "v3",
        "Notice text",
        NOTICE_DIGEST,
        NOW,
        ["questionnaire_responses", "minority_reports"],
    ))
    result = acceptance.preview_location_delphi_participant_invite(
        INVITE_TOKEN, connection_factory=lambda: connection
    )
    query, params = connection.calls[-1]
    assert "preview_location_delphi_participant_invite" in query
    assert params == (INVITE_TOKEN,)
    assert result == {
        "study_title": "Watershed priorities",
        "notice_version": "v3",
        "notice_text": "Notice text",
        "notice_digest": NOTICE_DIGEST,
        "expires_at": NOW,
        "collection_scopes": ["questionnaire_responses", "minority_reports"],
    }
    assert connection.committed and connection.rolled_back and connection.closed


def test_acceptance_forwards_exact_notice_and_client_generated_digest_only_session_tokens():
    connection = _Connection(("accepted", "v3", NOTICE_DIGEST, NOW, NOW, False))
    result = acceptance.accept_location_delphi_participant_invite(
        INVITE_TOKEN,
        NOTICE_DIGEST,
        SESSION_TOKEN,
        CSRF_TOKEN,
        REQUEST_ID,
        accepted=True,
        connection_factory=lambda: connection,
    )
    query, params = connection.calls[-1]
    assert "accept_location_delphi_participant_invite" in query
    assert params == (INVITE_TOKEN, NOTICE_DIGEST, SESSION_TOKEN, CSRF_TOKEN, REQUEST_ID, True)
    assert result["status"] == "accepted" and result["replayed"] is False
    assert connection.committed and connection.closed


def test_withdrawal_uses_only_session_capability_csrf_and_request_id():
    connection = _Connection(("withdrawn", NOW, True))
    result = acceptance.withdraw_location_delphi_participant(
        SESSION_TOKEN,
        CSRF_TOKEN,
        REQUEST_ID,
        connection_factory=lambda: connection,
    )
    query, params = connection.calls[-1]
    assert "withdraw_location_delphi_participant" in query
    assert params == (SESSION_TOKEN, CSRF_TOKEN, REQUEST_ID)
    assert result == {"status": "withdrawn", "withdrawn_at": NOW, "replayed": True}
    assert connection.committed and connection.closed


@pytest.mark.parametrize(
    ("method", "values"),
    [
        ("preview", {"invite_token": "short"}),
        ("accept", {"invite_token": "bad"}),
        ("accept", {"invite_token": INVITE_TOKEN, "notice_digest": "bad"}),
        ("accept", {"invite_token": INVITE_TOKEN, "notice_digest": NOTICE_DIGEST,
                     "session_token": SESSION_TOKEN, "csrf_token": CSRF_TOKEN,
                     "request_id": REQUEST_ID, "accepted": False}),
        ("accept", {"invite_token": INVITE_TOKEN, "notice_digest": NOTICE_DIGEST,
                     "session_token": SESSION_TOKEN, "csrf_token": SESSION_TOKEN,
                     "request_id": REQUEST_ID, "accepted": True}),
        ("withdraw", {"session_token": SESSION_TOKEN, "csrf_token": "bad",
                       "request_id": REQUEST_ID}),
    ],
)
def test_invalid_capability_or_consent_fails_before_database(method, values):
    def factory():
        pytest.fail("invalid participant request opened a connection")

    with pytest.raises(acceptance.DelphiParticipantAcceptanceInvalid):
        if method == "preview":
            acceptance.preview_location_delphi_participant_invite(
                values["invite_token"], connection_factory=factory
            )
        elif method == "accept":
            values.setdefault("notice_digest", NOTICE_DIGEST)
            values.setdefault("session_token", SESSION_TOKEN)
            values.setdefault("csrf_token", CSRF_TOKEN)
            values.setdefault("request_id", REQUEST_ID)
            values.setdefault("accepted", True)
            acceptance.accept_location_delphi_participant_invite(
                values["invite_token"], values["notice_digest"], values["session_token"],
                values["csrf_token"], values["request_id"], accepted=values["accepted"],
                connection_factory=factory,
            )
        else:
            acceptance.withdraw_location_delphi_participant(
                values["session_token"], values["csrf_token"], values["request_id"],
                connection_factory=factory,
            )


def _app(run_in_threadpool):
    from services.gateway.delphi_participant_routes import register_delphi_participant_routes

    app = FastAPI()
    router = APIRouter()
    register_delphi_participant_routes(router, run_in_threadpool, __import__("psycopg2"))
    app.include_router(router, prefix="/api")
    return app


def test_preview_response_is_private_and_never_echoes_invite_token():
    expected = {
        "study_title": "Watershed priorities",
        "notice_version": "v3",
        "notice_text": "Notice text",
        "notice_digest": NOTICE_DIGEST,
        "expires_at": NOW,
        "collection_scopes": ["questionnaire_responses", "minority_reports"],
    }

    async def run_in_threadpool(func, *args, **_kwargs):
        assert func is acceptance.preview_location_delphi_participant_invite
        assert args == (INVITE_TOKEN,)
        return expected

    client = TestClient(_app(run_in_threadpool), base_url="https://testserver")
    response = client.post("/api/participation/delphi/preview", json={"invite_token": INVITE_TOKEN})
    assert response.status_code == 200
    assert response.json() == {**expected, "expires_at": NOW.isoformat()}
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert INVITE_TOKEN not in response.text


def test_accept_sets_secure_http_only_session_cookie_without_echoing_tokens():
    expected = {
        "status": "accepted",
        "notice_version": "v3",
        "accepted_at": NOW,
        "session_expires_at": NOW,
        "replayed": False,
    }

    async def run_in_threadpool(func, *args, **kwargs):
        assert func is acceptance.accept_location_delphi_participant_invite
        assert args == (INVITE_TOKEN, NOTICE_DIGEST, SESSION_TOKEN, CSRF_TOKEN, REQUEST_ID)
        assert kwargs == {"accepted": True}
        return expected

    response = TestClient(_app(run_in_threadpool), base_url="https://testserver").post(
        "/api/participation/delphi/accept",
        json={
            "invite_token": INVITE_TOKEN,
            "notice_digest": NOTICE_DIGEST,
            "session_token": SESSION_TOKEN,
            "csrf_token": CSRF_TOKEN,
            "request_id": REQUEST_ID,
            "accepted": True,
        },
    )
    assert response.status_code == 201
    assert SESSION_TOKEN not in response.text and CSRF_TOKEN not in response.text
    cookies = response.headers.get_list("set-cookie")
    assert any("kokonut_delphi_participant_session=" in cookie and "HttpOnly" in cookie
               and "Secure" in cookie and "SameSite=strict" in cookie for cookie in cookies)
    assert any("kokonut_delphi_participant_csrf=" in cookie and "HttpOnly" not in cookie
               and "Secure" in cookie and "SameSite=strict" in cookie for cookie in cookies)
    assert response.headers["cache-control"] == "no-store"


def test_accept_route_requires_literal_consent_and_exact_fields():
    async def run_in_threadpool(*_args, **_kwargs):
        pytest.fail("invalid acceptance reached the service")

    client = TestClient(_app(run_in_threadpool), base_url="https://testserver")
    payload = {
        "invite_token": INVITE_TOKEN,
        "notice_digest": NOTICE_DIGEST,
        "session_token": SESSION_TOKEN,
        "csrf_token": CSRF_TOKEN,
        "request_id": REQUEST_ID,
        "accepted": False,
    }
    response = client.post("/api/participation/delphi/accept", json=payload)
    assert response.status_code == 400
    payload["accepted"] = True
    payload["email"] = "participant@example.test"
    assert client.post("/api/participation/delphi/accept", json=payload).status_code == 400


def test_withdraw_requires_double_submit_csrf_and_clears_cookies():
    calls = []

    async def run_in_threadpool(func, *args, **_kwargs):
        calls.append((func, args))
        return {"status": "withdrawn", "withdrawn_at": NOW, "replayed": False}

    client = TestClient(_app(run_in_threadpool), base_url="https://testserver")
    client.cookies.set("kokonut_delphi_participant_session", SESSION_TOKEN,
                       path="/api/participation/delphi")
    client.cookies.set("kokonut_delphi_participant_csrf", CSRF_TOKEN,
                       path="/api/participation/delphi")
    denied = client.post("/api/participation/delphi/withdraw", json={"request_id": REQUEST_ID})
    assert denied.status_code == 403 and calls == []

    response = client.post(
        "/api/participation/delphi/withdraw",
        json={"request_id": REQUEST_ID},
        headers={"x-kokonut-csrf": CSRF_TOKEN},
    )
    assert response.status_code == 200 and response.json()["status"] == "withdrawn"
    assert calls == [(acceptance.withdraw_location_delphi_participant,
                      (SESSION_TOKEN, CSRF_TOKEN, REQUEST_ID))]
    cookies = response.headers.get_list("set-cookie")
    assert any("kokonut_delphi_participant_session=" in cookie and "Max-Age=0" in cookie
               for cookie in cookies)
    assert any("kokonut_delphi_participant_csrf=" in cookie and "Max-Age=0" in cookie
               for cookie in cookies)


def test_withdraw_csrf_mismatch_never_reaches_service():
    async def run_in_threadpool(*_args, **_kwargs):
        pytest.fail("CSRF mismatch reached service")

    client = TestClient(_app(run_in_threadpool), base_url="https://testserver")
    client.cookies.set("kokonut_delphi_participant_session", SESSION_TOKEN,
                       path="/api/participation/delphi")
    client.cookies.set("kokonut_delphi_participant_csrf", CSRF_TOKEN,
                       path="/api/participation/delphi")
    response = client.post(
        "/api/participation/delphi/withdraw",
        json={"request_id": REQUEST_ID},
        headers={"x-kokonut-csrf": "e5" * 32},
    )
    assert response.status_code == 403
