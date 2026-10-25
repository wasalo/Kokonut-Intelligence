"""Contracts for pseudonymous, one-time Delphi participant invites."""

from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest

from services.gateway import delphi_participant_invites as invites

pytest.importorskip("fastapi")
from fastapi import APIRouter, FastAPI  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

OPERATOR_ID = str(uuid4())
LOCATION_ID = str(uuid4())
STUDY_ID = str(uuid4())
INVITE_ID = str(uuid4())
NOTICE_ID = str(uuid4())
REQUEST_ID = str(uuid4())


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


def _context(connection, **kwargs):
    connection.context = kwargs


def test_issue_sets_exact_invite_context_and_returns_secret_only_on_first_result():
    connection = _Connection(
        row=(INVITE_ID, LOCATION_ID, STUDY_ID, NOTICE_ID, "v2", "ab" * 32,
             "a1" * 32, None, "pending", False)
    )
    with patch.object(invites, "set_operator_tenant_context", _context):
        result = invites.issue_location_delphi_participant_invite(
            OPERATOR_ID, LOCATION_ID, STUDY_ID,
            lifetime_seconds=86400, request_id=REQUEST_ID,
            connection_factory=lambda: connection,
        )
    query, params = connection.calls[-1]
    assert "issue_location_delphi_participant_invite" in query
    assert params == (LOCATION_ID, STUDY_ID, 86400, REQUEST_ID)
    assert connection.context == {
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "delphi",
        "action": "invite",
    }
    assert result["invite_token"] == "a1" * 32
    assert result["consent_notice_id"] == NOTICE_ID
    assert result["status"] == "pending" and not result["replayed"]
    assert connection.committed and connection.closed


def test_issue_retry_never_returns_the_one_time_secret_again():
    connection = _Connection(
        row=(INVITE_ID, LOCATION_ID, STUDY_ID, NOTICE_ID, "v2", "ab" * 32,
             None, None, "pending", True)
    )
    with patch.object(invites, "set_operator_tenant_context", _context):
        result = invites.issue_location_delphi_participant_invite(
            OPERATOR_ID, LOCATION_ID, STUDY_ID,
            lifetime_seconds=86400, request_id=REQUEST_ID,
            connection_factory=lambda: connection,
        )
    assert result["invite_token"] is None
    assert result["replayed"] is True


@pytest.mark.parametrize("lifetime", [True, 0, 3599, 2_592_001, "86400"])
def test_invalid_lifetime_fails_before_database(lifetime):
    with pytest.raises(invites.DelphiParticipantInviteInvalid):
        invites.issue_location_delphi_participant_invite(
            OPERATOR_ID, LOCATION_ID, STUDY_ID,
            lifetime_seconds=lifetime, request_id=REQUEST_ID,
            connection_factory=lambda: pytest.fail("invalid lifetime opened a connection"),
        )


def test_revoke_sets_exact_revoke_context_and_calls_bounded_function():
    connection = _Connection(row=(INVITE_ID, STUDY_ID, "revoked", None, False))
    with patch.object(invites, "set_operator_tenant_context", _context):
        result = invites.revoke_location_delphi_participant_invite(
            OPERATOR_ID, LOCATION_ID, INVITE_ID,
            request_id=REQUEST_ID, reason_code="token_exposed",
            connection_factory=lambda: connection,
        )
    query, params = connection.calls[-1]
    assert "revoke_location_delphi_participant_invite" in query
    assert params == (LOCATION_ID, INVITE_ID, REQUEST_ID, "token_exposed")
    assert connection.context["action"] == "invite_revoke"
    assert result["status"] == "revoked" and not result["replayed"]
    assert connection.committed and connection.closed


@pytest.mark.parametrize("reason", ["", "free text", "accepted", None])
def test_invalid_revoke_reason_fails_before_database(reason):
    with pytest.raises(invites.DelphiParticipantInviteInvalid):
        invites.revoke_location_delphi_participant_invite(
            OPERATOR_ID, LOCATION_ID, INVITE_ID,
            request_id=REQUEST_ID, reason_code=reason,
            connection_factory=lambda: pytest.fail("invalid reason opened a connection"),
        )


def _app(provider, run_in_threadpool, errors=None):
    from services.gateway.delphi_participant_invite_routes import (
        register_delphi_participant_invite_routes,
    )

    app = FastAPI()
    router = APIRouter()

    @app.middleware("http")
    async def bind_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    register_delphi_participant_invite_routes(
        router, provider, run_in_threadpool, errors or __import__("psycopg2")
    )
    app.include_router(router)
    return app


def test_issue_route_returns_token_once_with_no_store():
    expected = {
        "invite_id": INVITE_ID,
        "location_id": LOCATION_ID,
        "study_id": STUDY_ID,
        "consent_notice_id": NOTICE_ID,
        "consent_notice_version": "v2",
        "consent_notice_digest": "ab" * 32,
        "invite_token": "a1" * 32,
        "expires_at": "2026-10-26T12:00:00+00:00",
        "status": "pending",
        "replayed": False,
    }

    async def run_in_threadpool(func, *args, **kwargs):
        assert func is invites.issue_location_delphi_participant_invite
        assert args == (OPERATOR_ID, LOCATION_ID, STUDY_ID)
        assert kwargs == {"lifetime_seconds": 86400, "request_id": REQUEST_ID}
        return expected

    response = TestClient(_app(object(), run_in_threadpool)).post(
        f"/operator/api/delphi/{LOCATION_ID}/studies/{STUDY_ID}/invites",
        json={"request_id": REQUEST_ID, "lifetime_seconds": 86400},
    )
    assert response.status_code == 201 and response.json() == expected
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize(
    "payload",
    [
        {"request_id": REQUEST_ID, "lifetime_seconds": True},
        {"request_id": REQUEST_ID, "lifetime_seconds": "86400"},
        {"request_id": REQUEST_ID, "lifetime_seconds": 86400, "email": "person@example.test"},
    ],
)
def test_issue_route_rejects_invalid_or_identity_linked_fields(payload):
    async def run_in_threadpool(*_args, **_kwargs):
        pytest.fail("invalid invite payload reached the service")

    response = TestClient(_app(object(), run_in_threadpool)).post(
        f"/operator/api/delphi/{LOCATION_ID}/studies/{STUDY_ID}/invites", json=payload
    )
    assert response.status_code == 400


def test_revoke_route_forwards_fixed_reason_and_request_id():
    expected = {
        "invite_id": INVITE_ID,
        "study_id": STUDY_ID,
        "status": "revoked",
        "revoked_at": "2026-10-25T12:00:00+00:00",
        "replayed": False,
    }

    async def run_in_threadpool(func, *args, **kwargs):
        assert func is invites.revoke_location_delphi_participant_invite
        assert args == (OPERATOR_ID, LOCATION_ID, INVITE_ID)
        assert kwargs == {"request_id": REQUEST_ID, "reason_code": "token_exposed"}
        return expected

    response = TestClient(_app(object(), run_in_threadpool)).post(
        f"/operator/api/delphi/{LOCATION_ID}/invites/{INVITE_ID}/revoke",
        json={"request_id": REQUEST_ID, "reason_code": "token_exposed"},
    )
    assert response.status_code == 200 and response.json() == expected
    assert response.headers["cache-control"] == "no-store"


def test_invite_routes_fail_closed_when_oidc_is_disabled():
    async def run_in_threadpool(*_args, **_kwargs):
        pytest.fail("OIDC-disabled request reached service")

    client = TestClient(_app(None, run_in_threadpool))
    issue = client.post(
        f"/operator/api/delphi/{LOCATION_ID}/studies/{STUDY_ID}/invites",
        json={"request_id": REQUEST_ID, "lifetime_seconds": 86400},
    )
    revoke = client.post(
        f"/operator/api/delphi/{LOCATION_ID}/invites/{INVITE_ID}/revoke",
        json={"request_id": REQUEST_ID, "reason_code": "token_exposed"},
    )
    assert issue.status_code == revoke.status_code == 404
