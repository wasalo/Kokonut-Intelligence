"""Contracts for versioned, independently reviewed Delphi consent notices."""

from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest

from services.gateway import delphi_consent_notices as notices

pytest.importorskip("fastapi")
from fastapi import APIRouter, FastAPI  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

OPERATOR_ID = str(uuid4())
REVIEWER_ID = str(uuid4())
LOCATION_ID = str(uuid4())
STUDY_ID = str(uuid4())
NOTICE_ID = str(uuid4())
REQUEST_ID = str(uuid4())


class _Connection:
    def __init__(self, row=None, rows=None):
        self.row = row
        self.rows = rows or []
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

    def fetchall(self):
        return self.connection.rows


def _context(connection, **kwargs):
    connection.context = kwargs


def test_submit_uses_exact_location_draft_context_and_private_retry_function():
    connection = _Connection(
        row=(NOTICE_ID, LOCATION_ID, STUDY_ID, "v1.0", "submitted", "ab" * 32, None, False)
    )
    with patch.object(notices, "set_operator_tenant_context", _context):
        result = notices.submit_location_delphi_consent_notice(
            OPERATOR_ID,
            LOCATION_ID,
            STUDY_ID,
            version="v1.0",
            notice_text="Participation is voluntary.",
            collection_scopes=["questionnaire_responses", "minority_reports"],
            request_id=REQUEST_ID,
            connection_factory=lambda: connection,
        )
    query, params = connection.calls[-1]
    assert "submit_location_delphi_consent_notice_scoped" in query
    assert params == (
        LOCATION_ID,
        STUDY_ID,
        "v1.0",
        "Participation is voluntary.",
        ["questionnaire_responses", "minority_reports"],
        REQUEST_ID,
    )
    assert connection.context == {
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "delphi",
        "action": "consent_draft",
    }
    assert result["status"] == "submitted" and result["replayed"] is False
    assert result["notice_digest"] == "ab" * 32
    assert connection.committed and connection.rolled_back and connection.closed


@pytest.mark.parametrize(
    ("version", "text"),
    [("bad version", "Notice"), ("v1", "  "), ("v" * 41, "Notice")],
)
def test_submit_invalid_notice_fails_before_database(version, text):
    with pytest.raises(notices.DelphiConsentNoticeInvalid):
        notices.submit_location_delphi_consent_notice(
            OPERATOR_ID,
            LOCATION_ID,
            STUDY_ID,
            version=version,
            notice_text=text,
            collection_scopes=["questionnaire_responses"],
            request_id=REQUEST_ID,
            connection_factory=lambda: pytest.fail("invalid notice opened a connection"),
        )


@pytest.mark.parametrize(
    "scopes",
    [[], ["minority_reports"], ["unknown"], ["questionnaire_responses", "questionnaire_responses"]],
)
def test_submit_invalid_activity_scope_fails_before_database(scopes):
    with pytest.raises(notices.DelphiConsentNoticeInvalid):
        notices.submit_location_delphi_consent_notice(
            OPERATOR_ID,
            LOCATION_ID,
            STUDY_ID,
            version="v1",
            notice_text="Participation is voluntary.",
            collection_scopes=scopes,
            request_id=REQUEST_ID,
            connection_factory=lambda: pytest.fail("invalid activity scope opened a connection"),
        )


def test_review_queue_sets_consent_review_context_and_bounds_rows():
    connection = _Connection(
        rows=[
            (
                NOTICE_ID,
                STUDY_ID,
                "Water resilience",
                "v1",
                "Participation is voluntary.",
                "ab" * 32,
                None,
                False,
                ["self_review"],
                ["questionnaire_responses", "minority_reports"],
            )
        ]
    )
    with patch.object(notices, "set_operator_tenant_context", _context):
        result = notices.list_location_delphi_consent_notices(
            REVIEWER_ID,
            LOCATION_ID,
            limit="25",
            offset="0",
            connection_factory=lambda: connection,
        )
    query, params = connection.calls[-1]
    assert "list_location_delphi_consent_notices_scoped" in query
    assert params == (LOCATION_ID, 26, 0)
    assert connection.context["action"] == "consent_review"
    assert result["notices"] == [
        {
            "notice_id": NOTICE_ID,
            "study_id": STUDY_ID,
            "study_title": "Water resilience",
            "version": "v1",
            "notice_text": "Participation is voluntary.",
            "notice_digest": "ab" * 32,
            "created_at": None,
            "review_ready": False,
            "blocked_reasons": ["self_review"],
            "collection_scopes": ["questionnaire_responses", "minority_reports"],
        }
    ]
    assert connection.closed


def test_review_decision_sets_independent_review_context_and_calls_bounded_function():
    connection = _Connection(row=(REQUEST_ID, NOTICE_ID, STUDY_ID, "approve", "approved", None, False))
    with patch.object(notices, "set_operator_tenant_context", _context):
        result = notices.decide_location_delphi_consent_notice(
            REVIEWER_ID,
            LOCATION_ID,
            NOTICE_ID,
            decision="approve",
            request_id=REQUEST_ID,
            reason_code="approved_after_independent_review",
            connection_factory=lambda: connection,
        )
    query, params = connection.calls[-1]
    assert "decide_location_delphi_consent_notice" in query
    assert params == (
        LOCATION_ID,
        NOTICE_ID,
        "approve",
        REQUEST_ID,
        "approved_after_independent_review",
    )
    assert connection.context["operator_id"] == REVIEWER_ID
    assert connection.context["action"] == "consent_review"
    assert result["status"] == "approved" and result["replayed"] is False
    assert connection.committed and connection.closed


@pytest.mark.parametrize(
    ("limit", "offset"), [(0, 0), (51, 0), (10, -1), (1, 10001), (None, 0)]
)
def test_review_queue_bounds_fail_before_database(limit, offset):
    with pytest.raises(notices.DelphiConsentNoticeInvalid):
        notices.list_location_delphi_consent_notices(
            REVIEWER_ID,
            LOCATION_ID,
            limit=limit,
            offset=offset,
            connection_factory=lambda: pytest.fail("invalid page opened a connection"),
        )


@pytest.mark.parametrize(
    ("decision", "reason"),
    [("approve", "other"), ("reject", "approved_after_independent_review"),
     ("approve", None), (None, "other"), ("publish", "other")],
)
def test_decision_reason_allowlist_fails_before_database(decision, reason):
    with pytest.raises(notices.DelphiConsentNoticeInvalid):
        notices.decide_location_delphi_consent_notice(
            REVIEWER_ID,
            LOCATION_ID,
            NOTICE_ID,
            decision=decision,
            request_id=REQUEST_ID,
            reason_code=reason,
            connection_factory=lambda: pytest.fail("invalid decision opened a connection"),
        )


def _app(provider, run_in_threadpool, errors=None):
    from services.gateway.delphi_consent_notice_routes import (
        register_delphi_consent_notice_routes,
    )

    app = FastAPI()
    router = APIRouter()

    @app.middleware("http")
    async def bind_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    register_delphi_consent_notice_routes(
        router, provider, run_in_threadpool, errors or __import__("psycopg2")
    )
    app.include_router(router)
    return app


def test_create_notice_route_requires_exact_fields_and_returns_private_response():
    calls = []
    expected = {
        "notice_id": NOTICE_ID,
        "location_id": LOCATION_ID,
        "study_id": STUDY_ID,
        "version": "v1",
        "status": "submitted",
        "notice_digest": "ab" * 32,
        "created_at": "2026-10-25T12:00:00+00:00",
        "replayed": False,
        "collection_scopes": ["questionnaire_responses"],
    }

    async def run_in_threadpool(func, *args, **kwargs):
        calls.append((func, args, kwargs))
        return expected

    response = TestClient(_app(object(), run_in_threadpool)).post(
        f"/operator/api/delphi/{LOCATION_ID}/studies/{STUDY_ID}/consent-notices",
        json={
            "request_id": REQUEST_ID,
            "version": "v1",
            "notice_text": "A notice.",
            "collection_scopes": ["questionnaire_responses"],
        },
    )
    assert response.status_code == 201 and response.json() == expected
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert calls[0][1] == (OPERATOR_ID, LOCATION_ID, STUDY_ID)
    assert calls[0][2] == {
        "version": "v1",
        "notice_text": "A notice.",
        "collection_scopes": ["questionnaire_responses"],
        "request_id": REQUEST_ID,
    }


@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        ("post", f"/operator/api/delphi/{LOCATION_ID}/studies/{STUDY_ID}/consent-notices", {"request_id": REQUEST_ID}),
        ("post", f"/operator/api/delphi/{LOCATION_ID}/consent-notices/{NOTICE_ID}/decision", {"decision": "approve", "request_id": REQUEST_ID}),
    ],
)
def test_routes_reject_malformed_notice_payloads_before_service(method, path, payload):
    async def run_in_threadpool(*_args, **_kwargs):
        pytest.fail("malformed notice payload reached the service")

    response = getattr(TestClient(_app(object(), run_in_threadpool)), method)(path, json=payload)
    assert response.status_code == 400
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize(
    "scopes",
    [None, "questionnaire_responses", ["questionnaire_responses", 4]],
)
def test_notice_route_rejects_malformed_activity_scope_before_service(scopes):
    async def run_in_threadpool(*_args, **_kwargs):
        pytest.fail("malformed activity scope reached the service")

    response = TestClient(_app(object(), run_in_threadpool)).post(
        f"/operator/api/delphi/{LOCATION_ID}/studies/{STUDY_ID}/consent-notices",
        json={
            "request_id": REQUEST_ID,
            "version": "v1",
            "notice_text": "A notice.",
            "collection_scopes": scopes,
        },
    )
    assert response.status_code == 400
    assert response.headers["cache-control"] == "no-store"


def test_review_decision_route_uses_session_and_no_store():
    calls = []
    expected = {
        "decision_id": REQUEST_ID,
        "notice_id": NOTICE_ID,
        "study_id": STUDY_ID,
        "decision": "approve",
        "status": "approved",
        "decided_at": "2026-10-25T12:00:00+00:00",
        "replayed": False,
    }

    async def run_in_threadpool(func, *args, **kwargs):
        calls.append((func, args, kwargs))
        return expected

    response = TestClient(_app(object(), run_in_threadpool)).post(
        f"/operator/api/delphi/{LOCATION_ID}/consent-notices/{NOTICE_ID}/decision",
        json={
            "decision": "approve",
            "request_id": REQUEST_ID,
            "reason_code": "approved_after_independent_review",
        },
    )
    assert response.status_code == 200 and response.json() == expected
    assert calls[0][1] == (OPERATOR_ID, LOCATION_ID, NOTICE_ID)
    assert calls[0][2] == {
        "decision": "approve",
        "request_id": REQUEST_ID,
        "reason_code": "approved_after_independent_review",
    }
    assert response.headers["cache-control"] == "no-store"


def test_notice_routes_are_hidden_when_oidc_is_disabled():
    async def run_in_threadpool(*_args, **_kwargs):
        pytest.fail("OIDC-disabled notice route reached its service")

    response = TestClient(_app(None, run_in_threadpool)).get(
        f"/operator/api/delphi/{LOCATION_ID}/consent-notices"
    )
    assert response.status_code == 404
    assert response.headers["cache-control"] == "no-store"


def test_database_scope_denial_is_mapped_without_database_details():
    class _DatabaseError(Exception):
        pgcode = "42501"

    async def run_in_threadpool(*_args, **_kwargs):
        raise _DatabaseError("private scope details")

    response = TestClient(_app(object(), run_in_threadpool, SimpleNamespace(Error=_DatabaseError))).get(
        f"/operator/api/delphi/{LOCATION_ID}/consent-notices"
    )
    assert response.status_code == 403
    assert "private scope details" not in response.text


def test_consent_notice_list_openapi_publishes_service_page_bounds():
    async def run_in_threadpool(*_args, **_kwargs):
        pytest.fail("OpenAPI inspection reached the consent notice service")

    operation = _app(object(), run_in_threadpool).openapi()["paths"][
        "/operator/api/delphi/{location_id}/consent-notices"
    ]["get"]
    parameters = {
        parameter["name"]: parameter["schema"]
        for parameter in operation["parameters"]
        if parameter["in"] == "query"
    }

    assert parameters["limit"] == {
        "type": "integer",
        "minimum": 1,
        "maximum": 50,
        "default": 50,
        "title": "Limit",
    }
    assert parameters["offset"] == {
        "type": "integer",
        "minimum": 0,
        "maximum": 10000,
        "default": 0,
        "title": "Offset",
    }


@pytest.mark.parametrize(
    "query",
    ["limit=0", "limit=51", "offset=-1", "offset=10001", "limit=invalid"],
)
def test_consent_notice_list_rejects_invalid_page_before_service(query):
    async def run_in_threadpool(*_args, **_kwargs):
        pytest.fail("invalid consent-notice pagination reached the service")

    response = TestClient(_app(object(), run_in_threadpool)).get(
        f"/operator/api/delphi/{LOCATION_ID}/consent-notices?{query}"
    )

    assert response.status_code == 422
