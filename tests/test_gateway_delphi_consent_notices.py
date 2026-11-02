"""Contracts for versioned, independently reviewed Delphi consent notices."""

from datetime import datetime, timezone
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
CREATED_AT = datetime(2026, 10, 28, 12, 0, tzinfo=timezone.utc)


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


@pytest.mark.parametrize(("offset", "limit", "expected"), [(9999, 1, True), (10000, 1, False)])
def test_review_queue_has_more_only_when_another_page_is_addressable(offset, limit, expected):
    rows = [
        (
            str(uuid4()),
            str(uuid4()),
            "Study",
            "v1",
            "Participation is voluntary.",
            "ab" * 32,
            CREATED_AT,
            True,
            [],
            ["questionnaire_responses"],
        )
        for _ in range(2)
    ]
    connection = _Connection(rows=rows)

    with patch.object(notices, "set_operator_tenant_context", _context):
        result = notices.list_location_delphi_consent_notices(
            REVIEWER_ID,
            LOCATION_ID,
            limit=limit,
            offset=offset,
            connection_factory=lambda: connection,
        )

    assert result["has_more"] is expected


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
        "created_at": "2026-10-28T12:00:00Z",
        "replayed": False,
    }
    service_result = {**expected, "created_at": CREATED_AT}

    async def run_in_threadpool(func, *args, **kwargs):
        calls.append((func, args, kwargs))
        return service_result

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


def test_create_notice_route_reports_replay_after_later_notice_review():
    service_result = {
        "notice_id": NOTICE_ID,
        "location_id": LOCATION_ID,
        "study_id": STUDY_ID,
        "version": "v1",
        "status": "approved",
        "notice_digest": "ab" * 32,
        "created_at": CREATED_AT,
        "replayed": True,
    }

    async def run_in_threadpool(*_args, **_kwargs):
        return service_result

    response = TestClient(_app(object(), run_in_threadpool)).post(
        f"/operator/api/delphi/{LOCATION_ID}/studies/{STUDY_ID}/consent-notices",
        json={
            "request_id": REQUEST_ID,
            "version": "v1",
            "notice_text": "A notice.",
            "collection_scopes": ["questionnaire_responses"],
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        **service_result,
        "created_at": CREATED_AT.isoformat().replace("+00:00", "Z"),
    }
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"


@pytest.mark.parametrize(
    "service_result",
    [
        {"notice_id": NOTICE_ID},
        {
            "notice_id": NOTICE_ID,
            "location_id": LOCATION_ID,
            "study_id": STUDY_ID,
            "version": "v1",
            "status": "submitted",
            "notice_digest": "invalid",
            "created_at": CREATED_AT,
            "replayed": False,
        },
        {
            "notice_id": NOTICE_ID,
            "location_id": LOCATION_ID,
            "study_id": STUDY_ID,
            "version": "v1",
            "status": "approved",
            "notice_digest": "ab" * 32,
            "created_at": CREATED_AT,
            "replayed": False,
        },
        {
            "notice_id": NOTICE_ID,
            "location_id": str(uuid4()),
            "study_id": STUDY_ID,
            "version": "v1",
            "status": "submitted",
            "notice_digest": "ab" * 32,
            "created_at": CREATED_AT,
            "replayed": False,
            "private_internal": "must not leak",
        },
    ],
)
def test_create_notice_route_sanitizes_malformed_service_response(service_result):
    async def run_in_threadpool(*_args, **_kwargs):
        return service_result

    response = TestClient(_app(object(), run_in_threadpool)).post(
        f"/operator/api/delphi/{LOCATION_ID}/studies/{STUDY_ID}/consent-notices",
        json={
            "request_id": REQUEST_ID,
            "version": "v1",
            "notice_text": "A notice.",
            "collection_scopes": ["questionnaire_responses"],
        },
    )

    assert response.status_code == 500
    assert response.json() == {"error": "Delphi consent notice service unavailable"}
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert "private_internal" not in response.text


def test_consent_create_and_decision_openapi_publish_exact_response_fields():
    async def run_in_threadpool(*_args, **_kwargs):
        pytest.fail("OpenAPI inspection must not call the service")

    app = _app(object(), run_in_threadpool)
    schema_doc = app.openapi()
    paths = schema_doc["paths"]
    create = paths[
        "/operator/api/delphi/{location_id}/studies/{study_id}/consent-notices"
    ]["post"]
    decision = paths[
        "/operator/api/delphi/{location_id}/consent-notices/{notice_id}/decision"
    ]["post"]

    def properties(operation, status):
        ref = operation["responses"][status]["content"]["application/json"]["schema"]["$ref"]
        component = schema_doc["components"]["schemas"][ref.rsplit("/", 1)[1]]
        assert component["additionalProperties"] is False
        return set(component["properties"])

    assert properties(create, "201") == {
        "notice_id", "location_id", "study_id", "version", "status",
        "notice_digest", "created_at", "replayed",
    }
    assert properties(create, "200") == properties(create, "201")
    assert properties(decision, "200") == {
        "decision_id", "notice_id", "study_id", "decision", "status",
        "decided_at", "replayed",
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
        "decided_at": CREATED_AT.isoformat().replace("+00:00", "Z"),
        "replayed": False,
    }
    service_result = {**expected, "decided_at": CREATED_AT}

    async def run_in_threadpool(func, *args, **kwargs):
        calls.append((func, args, kwargs))
        return service_result

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


@pytest.mark.parametrize(
    "service_result",
    [
        {"decision_id": REQUEST_ID},
        {
            "decision_id": REQUEST_ID,
            "notice_id": NOTICE_ID,
            "study_id": STUDY_ID,
            "decision": "approve",
            "status": "rejected",
            "decided_at": CREATED_AT,
            "replayed": False,
        },
        {
            "decision_id": REQUEST_ID,
            "notice_id": str(uuid4()),
            "study_id": STUDY_ID,
            "decision": "approve",
            "status": "approved",
            "decided_at": CREATED_AT,
            "replayed": False,
            "private_internal": "must not leak",
        },
    ],
)
def test_consent_decision_route_sanitizes_malformed_service_response(service_result):
    async def run_in_threadpool(*_args, **_kwargs):
        return service_result

    response = TestClient(_app(object(), run_in_threadpool)).post(
        f"/operator/api/delphi/{LOCATION_ID}/consent-notices/{NOTICE_ID}/decision",
        json={
            "decision": "approve",
            "request_id": REQUEST_ID,
            "reason_code": "approved_after_independent_review",
        },
    )

    assert response.status_code == 500
    assert response.json() == {"error": "Delphi consent notice service unavailable"}
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert "private_internal" not in response.text


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
    assert operation["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith(
        "ConsentNoticeReviewPage"
    )
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


def _valid_review_page(**overrides):
    result = {
        "location_id": LOCATION_ID,
        "offset": 0,
        "notices": [
            {
                "notice_id": NOTICE_ID,
                "study_id": STUDY_ID,
                "study_title": "Water resilience",
                "version": "v1.0",
                "notice_text": "Participation is voluntary.",
                "notice_digest": "ab" * 32,
                "created_at": CREATED_AT,
                "review_ready": False,
                "blocked_reasons": ["self_review"],
                "collection_scopes": ["questionnaire_responses"],
            }
        ],
        "has_more": False,
    }
    result.update(overrides)
    return result


def test_consent_notice_list_validates_and_returns_private_projection():
    calls = []

    async def run_in_threadpool(func, *args, **kwargs):
        calls.append((func, args, kwargs))
        return _valid_review_page()

    response = TestClient(_app(object(), run_in_threadpool)).get(
        f"/operator/api/delphi/{LOCATION_ID}/consent-notices"
    )

    assert response.status_code == 200
    assert response.json()["notices"][0]["notice_text"] == "Participation is voluntary."
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert calls[0][1] == (OPERATOR_ID, LOCATION_ID)
    assert calls[0][2] == {"limit": 50, "offset": 0}


@pytest.mark.parametrize(
    "projection",
    [
        _valid_review_page(location_id=str(uuid4())),
        _valid_review_page(notices=[{"notice_id": NOTICE_ID}]),
        _valid_review_page(
            notices=[
                {
                    **_valid_review_page()["notices"][0],
                    "participant_ref_id": str(uuid4()),
                }
            ]
        ),
        _valid_review_page(
            notices=[
                {
                    **_valid_review_page()["notices"][0],
                    "review_ready": True,
                }
            ]
        ),
    ],
)
def test_consent_notice_list_rejects_mismatched_or_private_projection(projection):
    async def run_in_threadpool(*_args, **_kwargs):
        return projection

    response = TestClient(_app(object(), run_in_threadpool)).get(
        f"/operator/api/delphi/{LOCATION_ID}/consent-notices"
    )

    assert response.status_code == 500
    assert response.headers["cache-control"] == "no-store"
    assert "participant_ref_id" not in response.text


def test_consent_notice_list_enforces_request_pagination_binding():
    async def run_in_threadpool(_func, _operator_id, location_id, **kwargs):
        return _valid_review_page(
            location_id=location_id,
            offset=kwargs["offset"],
            notices=[],
            has_more=True,
        )

    response = TestClient(_app(object(), run_in_threadpool)).get(
        f"/operator/api/delphi/{LOCATION_ID}/consent-notices?limit=2&offset=9"
    )

    assert response.status_code == 500
    assert response.headers["cache-control"] == "no-store"
