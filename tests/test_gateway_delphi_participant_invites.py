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


def test_list_invites_uses_signed_location_scope_and_safe_bounded_projection():
    projection = {
        "location_id": LOCATION_ID,
        "study_id": STUDY_ID,
        "invites": [{
            "invite_id": INVITE_ID,
            "study_id": STUDY_ID,
            "notice_version": "v2",
            "status": "pending",
            "created_at": "2026-10-25T12:00:00+00:00",
            "expires_at": "2026-10-26T12:00:00+00:00",
        }],
        "has_more": False,
        "limit": 20,
        "offset": 0,
    }
    connection = _Connection(row=(projection,))
    with patch.object(invites, "set_operator_tenant_context", _context):
        result = invites.list_location_delphi_participant_invites(
            OPERATOR_ID,
            LOCATION_ID,
            STUDY_ID,
            limit="20",
            offset="0",
            connection_factory=lambda: connection,
        )
    query, params = connection.calls[-1]
    assert "list_location_delphi_participant_invites" in query
    assert params == (LOCATION_ID, STUDY_ID, 20, 0)
    assert connection.context == {
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "delphi",
        "action": "invite",
    }
    assert result == projection
    assert "invite_token" not in str(result) and "token_digest" not in str(result)
    assert connection.committed and connection.closed


def test_list_invites_closes_unaddressable_continuation_at_offset_ceiling():
    projection = {
        "location_id": LOCATION_ID,
        "study_id": STUDY_ID,
        "invites": [],
        "has_more": True,
        "limit": 50,
        "offset": 10000,
    }
    connection = _Connection(row=(projection,))
    with patch.object(invites, "set_operator_tenant_context", _context):
        result = invites.list_location_delphi_participant_invites(
            OPERATOR_ID,
            LOCATION_ID,
            STUDY_ID,
            limit=50,
            offset=10000,
            connection_factory=lambda: connection,
        )

    assert result["has_more"] is False
    assert result["offset"] == 10000
    assert connection.committed and connection.closed


@pytest.mark.parametrize("field,value", [("limit", "51"), ("limit", True), ("offset", "10001"), ("offset", "-1")])
def test_invalid_invite_page_fails_before_database(field, value):
    arguments = {field: value}
    with pytest.raises(invites.DelphiParticipantInviteInvalid):
        invites.list_location_delphi_participant_invites(
            OPERATOR_ID,
            LOCATION_ID,
            STUDY_ID,
            connection_factory=lambda: pytest.fail("invalid page opened a connection"),
            **arguments,
        )


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
        "expires_at": "2026-10-26T12:00:00Z",
        "status": "pending",
        "replayed": False,
    }

    async def run_in_threadpool(func, *args, **kwargs):
        assert func is invites.issue_location_delphi_participant_invite
        assert args == (OPERATOR_ID, LOCATION_ID, STUDY_ID)
        assert kwargs == {"lifetime_seconds": 86400, "request_id": REQUEST_ID}
        return expected

    app = _app(object(), run_in_threadpool)
    operation = app.openapi()["paths"][
        "/operator/api/delphi/{location_id}/studies/{study_id}/invites"
    ]["post"]
    assert operation["responses"]["201"]["content"]["application/json"]["schema"][
        "$ref"
    ].endswith("ParticipantInviteCreateResponse")
    assert operation["responses"]["200"]["content"]["application/json"]["schema"][
        "$ref"
    ].endswith("ParticipantInviteCreateResponse")
    response = TestClient(app).post(
        f"/operator/api/delphi/{LOCATION_ID}/studies/{STUDY_ID}/invites",
        json={"request_id": REQUEST_ID, "lifetime_seconds": 86400},
    )
    assert response.status_code == 201 and response.json() == expected
    assert response.headers["cache-control"] == "no-store"


def test_issue_replay_is_bound_and_never_reveals_token_again():
    expected = {
        "invite_id": INVITE_ID,
        "location_id": LOCATION_ID,
        "study_id": STUDY_ID,
        "consent_notice_id": NOTICE_ID,
        "consent_notice_version": "v2",
        "consent_notice_digest": "ab" * 32,
        "invite_token": None,
        "expires_at": "2026-10-26T12:00:00Z",
        "status": "pending",
        "replayed": True,
    }

    async def run_in_threadpool(*_args, **_kwargs):
        return expected

    response = TestClient(_app(object(), run_in_threadpool)).post(
        f"/operator/api/delphi/{LOCATION_ID}/studies/{STUDY_ID}/invites",
        json={"request_id": REQUEST_ID, "lifetime_seconds": 86400},
    )
    assert response.status_code == 200
    assert response.json() == expected
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize(
    "result_update",
    [
        {"location_id": str(uuid4())},
        {"study_id": str(uuid4())},
        {"replayed": True},
        {"extra_private_field": "must-not-leak"},
    ],
)
def test_issue_route_sanitizes_malformed_or_mismatched_success(result_update):
    result = {
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
    result.update(result_update)

    async def run_in_threadpool(*_args, **_kwargs):
        return result

    response = TestClient(_app(object(), run_in_threadpool)).post(
        f"/operator/api/delphi/{LOCATION_ID}/studies/{STUDY_ID}/invites",
        json={"request_id": REQUEST_ID, "lifetime_seconds": 86400},
    )
    assert response.status_code == 503
    assert response.json() == {"error": "Delphi invite service unavailable"}
    assert response.headers["cache-control"] == "no-store"
    assert "must-not-leak" not in response.text
    assert "a1" not in response.text


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
        "revoked_at": "2026-10-25T12:00:00Z",
        "replayed": False,
    }

    async def run_in_threadpool(func, *args, **kwargs):
        assert func is invites.revoke_location_delphi_participant_invite
        assert args == (OPERATOR_ID, LOCATION_ID, INVITE_ID)
        assert kwargs == {"request_id": REQUEST_ID, "reason_code": "token_exposed"}
        return expected

    app = _app(object(), run_in_threadpool)
    schema = app.openapi()["paths"][
        "/operator/api/delphi/{location_id}/invites/{invite_id}/revoke"
    ]["post"]["responses"]["200"]["content"]["application/json"]["schema"]
    assert schema["$ref"].endswith("ParticipantInviteRevokeResponse")
    response = TestClient(app).post(
        f"/operator/api/delphi/{LOCATION_ID}/invites/{INVITE_ID}/revoke",
        json={"request_id": REQUEST_ID, "reason_code": "token_exposed"},
    )
    assert response.status_code == 200 and response.json() == expected
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize(
    "result_update",
    [
        {"invite_id": str(uuid4())},
        {"status": "pending"},
        {"private_token": "must-not-leak"},
    ],
)
def test_revoke_route_sanitizes_malformed_or_mismatched_success(result_update):
    result = {
        "invite_id": INVITE_ID,
        "study_id": STUDY_ID,
        "status": "revoked",
        "revoked_at": "2026-10-25T12:00:00+00:00",
        "replayed": False,
    }
    result.update(result_update)

    async def run_in_threadpool(*_args, **_kwargs):
        return result

    response = TestClient(_app(object(), run_in_threadpool)).post(
        f"/operator/api/delphi/{LOCATION_ID}/invites/{INVITE_ID}/revoke",
        json={"request_id": REQUEST_ID, "reason_code": "token_exposed"},
    )
    assert response.status_code == 503
    assert response.json() == {"error": "Delphi invite service unavailable"}
    assert response.headers["cache-control"] == "no-store"
    assert "must-not-leak" not in response.text
    assert "private_token" not in response.text


def test_list_route_forwards_location_study_and_page_without_caching():
    expected = {
        "location_id": LOCATION_ID,
        "study_id": STUDY_ID,
        "invites": [],
        "has_more": False,
        "limit": 25,
        "offset": 50,
    }

    async def run_in_threadpool(func, *args, **kwargs):
        assert func is invites.list_location_delphi_participant_invites
        assert args == (OPERATOR_ID, LOCATION_ID, STUDY_ID)
        assert kwargs == {"limit": 25, "offset": 50}
        return expected

    response = TestClient(_app(object(), run_in_threadpool)).get(
        f"/operator/api/delphi/{LOCATION_ID}/studies/{STUDY_ID}/invites?limit=25&offset=50"
    )
    assert response.status_code == 200 and response.json() == expected
    assert response.headers["cache-control"] == "no-store"


def test_list_route_publishes_service_pagination_bounds_in_openapi():
    async def run_in_threadpool(*_args, **_kwargs):
        return {
            "location_id": LOCATION_ID,
            "study_id": STUDY_ID,
            "invites": [],
            "has_more": False,
            "limit": 50,
            "offset": 0,
        }

    app = _app(object(), run_in_threadpool)
    operation = app.openapi()["paths"][
        "/operator/api/delphi/{location_id}/studies/{study_id}/invites"
    ]["get"]
    parameters = {parameter["name"]: parameter["schema"] for parameter in operation["parameters"]}

    assert parameters["limit"] == {
        "type": "integer",
        "maximum": 50,
        "minimum": 1,
        "default": 50,
        "title": "Limit",
    }
    assert parameters["offset"] == {
        "type": "integer",
        "maximum": 10000,
        "minimum": 0,
        "default": 0,
        "title": "Offset",
    }
    response_schema = operation["responses"]["200"]["content"]["application/json"]["schema"]
    assert response_schema["$ref"].endswith("ParticipantInviteListResponse")


def test_list_route_validates_jsonb_wire_values_and_request_binding():
    expected = {
        "location_id": LOCATION_ID,
        "study_id": STUDY_ID,
        "invites": [{
            "invite_id": INVITE_ID,
            "study_id": STUDY_ID,
            "notice_version": "v2",
            "status": "pending",
            "created_at": "2026-10-25T12:00:00+00:00",
            "expires_at": "2026-10-26T12:00:00+00:00",
        }],
        "has_more": False,
        "limit": 50,
        "offset": 0,
    }

    async def run_in_threadpool(*_args, **_kwargs):
        return expected

    response = TestClient(_app(object(), run_in_threadpool)).get(
        f"/operator/api/delphi/{LOCATION_ID}/studies/{STUDY_ID}/invites"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["location_id"] == LOCATION_ID
    assert payload["study_id"] == STUDY_ID
    assert payload["invites"][0]["invite_id"] == INVITE_ID
    assert payload["invites"][0]["created_at"].startswith("2026-10-25T12:00:00")
    assert payload["invites"][0]["expires_at"].startswith("2026-10-26T12:00:00")
    assert payload["has_more"] is False and payload["limit"] == 50 and payload["offset"] == 0
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"


@pytest.mark.parametrize(
    "projection",
    [
        {"location_id": str(uuid4())},
        {"study_id": str(uuid4())},
        {"invites": [{
            "invite_id": INVITE_ID,
            "study_id": STUDY_ID,
            "notice_version": "v2",
            "status": "pending",
            "created_at": "2026-10-25T12:00:00+00:00",
            "expires_at": "2026-10-26T12:00:00+00:00",
            "invite_token": "must-not-leak",
        }]},
        {"invites": [{
            "invite_id": INVITE_ID,
            "study_id": str(uuid4()),
            "notice_version": "v2",
            "status": "pending",
            "created_at": "2026-10-25T12:00:00+00:00",
            "expires_at": "2026-10-26T12:00:00+00:00",
        }]},
        {"invites": [{
            "invite_id": INVITE_ID,
            "study_id": STUDY_ID,
            "notice_version": "v2",
            "status": "pending",
            "created_at": "2026-10-25T12:00:00",
            "expires_at": "2026-10-26T12:00:00+00:00",
        }]},
        {"has_more": True, "invites": []},
    ],
)
def test_list_route_rejects_mismatched_or_unbounded_projection(projection):
    valid = {
        "location_id": LOCATION_ID,
        "study_id": STUDY_ID,
        "invites": [],
        "has_more": False,
        "limit": 50,
        "offset": 0,
    }
    valid.update(projection)

    async def run_in_threadpool(*_args, **_kwargs):
        return valid

    response = TestClient(_app(object(), run_in_threadpool)).get(
        f"/operator/api/delphi/{LOCATION_ID}/studies/{STUDY_ID}/invites"
    )

    assert response.status_code == 500
    assert response.json() == {"error": "Delphi invite service unavailable"}
    assert "must-not-leak" not in response.text
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize(
    ("parameter", "value"),
    [("limit", 0), ("limit", 51), ("offset", -1), ("offset", 10001)],
)
def test_invalid_list_pagination_fails_before_service_access(parameter, value):
    async def run_in_threadpool(*_args, **_kwargs):
        pytest.fail("invalid pagination reached the invite service")

    client = TestClient(_app(object(), run_in_threadpool))
    response = client.get(
        f"/operator/api/delphi/{LOCATION_ID}/studies/{STUDY_ID}/invites",
        params={parameter: value},
    )

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["query", parameter]


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
    queue = client.get(
        f"/operator/api/delphi/{LOCATION_ID}/studies/{STUDY_ID}/invites"
    )
    assert issue.status_code == revoke.status_code == queue.status_code == 404
