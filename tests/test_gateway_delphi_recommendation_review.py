"""Focused contracts for location-scoped human review of Delphi drafts."""

from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest

from services.common.tenant_context import TenantContextDenied
from services.gateway import delphi_recommendation_review as review

pytest.importorskip("fastapi")
from fastapi import APIRouter, FastAPI  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

OPERATOR_ID = str(uuid4())
LOCATION_ID = str(uuid4())
RECOMMENDATION_ID = str(uuid4())
REQUEST_ID = str(uuid4())


class _Connection:
    def __init__(self, rows=(), one=None):
        self.rows = list(rows)
        self.one = one
        self.operations = []
        self.events = []
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
        normalized = " ".join(query.split())
        self.connection.operations.append((normalized, params))
        self.connection.events.append(normalized)

    def fetchall(self):
        return self.connection.rows

    def fetchone(self):
        return self.connection.one


def _set_context(connection, **kwargs):
    connection.events.append("SIGNED_CONTEXT")
    connection.context = kwargs


def test_review_queue_sets_exact_signed_scope_before_query_and_cleans_up():
    row = (
        RECOMMENDATION_ID,
        str(uuid4()),
        "Soil priorities",
        "closed",
        "Reviewed summary",
        "Increase perennial cover",
        None,
        True,
        [],
    )
    connection = _Connection([row])
    with patch.object(review, "set_operator_tenant_context", _set_context):
        result = review.list_location_delphi_recommendation_reviews(
            OPERATOR_ID,
            LOCATION_ID,
            connection_factory=lambda: connection,
        )

    query_index = next(
        index for index, event in enumerate(connection.events)
        if "list_location_delphi_recommendation_reviews" in event
    )
    assert connection.events.index("SIGNED_CONTEXT") < query_index
    assert connection.context == {
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "delphi",
        "action": "review",
    }
    assert result["recommendations"][0]["recommendation_text"] == "Increase perennial cover"
    assert result["recommendations"][0]["blocked_reasons"] == []
    assert connection.rolled_back and connection.closed
    assert not connection.committed


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("operator_id", "bad"),
        ("location_id", "bad"),
        ("limit", 0),
        ("limit", 51),
        ("limit", "1.2"),
        ("limit", True),
        ("offset", -1),
        ("offset", 10001),
        ("offset", "1.2"),
        ("offset", False),
    ],
)
def test_invalid_review_queue_request_fails_before_database(field, value):
    arguments = {
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "limit": 50,
        "offset": 0,
    }
    arguments[field] = value
    with pytest.raises(review.DelphiReviewInvalid):
        review.list_location_delphi_recommendation_reviews(
            **arguments,
            connection_factory=lambda: pytest.fail("invalid request opened a connection"),
        )


@pytest.mark.parametrize(
    ("decision", "reason_code"),
    [
        ("accept", "approved_after_review"),
        ("approve", "privacy_concern"),
        ("reject", "approved_after_review"),
        ("reject", "free-text reason"),
    ],
)
def test_invalid_decision_fails_before_database(decision, reason_code):
    with pytest.raises(review.DelphiReviewInvalid):
        review.decide_location_delphi_recommendation(
            OPERATOR_ID,
            LOCATION_ID,
            RECOMMENDATION_ID,
            decision=decision,
            request_id=REQUEST_ID,
            reason_code=reason_code,
            connection_factory=lambda: pytest.fail("invalid decision opened a connection"),
        )


def test_human_decision_uses_signed_scope_and_commits_only_after_database_decision():
    row = (str(uuid4()), RECOMMENDATION_ID, str(uuid4()), "approve", "approved", None)
    connection = _Connection(one=row)
    with patch.object(review, "set_operator_tenant_context", _set_context):
        result = review.decide_location_delphi_recommendation(
            OPERATOR_ID,
            LOCATION_ID,
            RECOMMENDATION_ID,
            decision="approve",
            request_id=REQUEST_ID,
            reason_code="approved_after_review",
            connection_factory=lambda: connection,
        )
    decision_query = next(
        params for query, params in connection.operations
        if "decide_location_delphi_recommendation" in query
    )
    assert decision_query == (
        LOCATION_ID,
        RECOMMENDATION_ID,
        "approve",
        REQUEST_ID,
        "approved_after_review",
    )
    assert connection.events.index("SIGNED_CONTEXT") < next(
        index for index, event in enumerate(connection.events)
        if "decide_location_delphi_recommendation" in event
    )
    assert connection.committed and connection.closed
    assert result["decision"] == "approve" and result["status"] == "approved"


def test_tenant_denial_rolls_back_and_never_invokes_review_function():
    connection = _Connection()
    with patch.object(
        review,
        "set_operator_tenant_context",
        side_effect=TenantContextDenied("missing review grant"),
    ):
        with pytest.raises(TenantContextDenied):
            review.decide_location_delphi_recommendation(
                OPERATOR_ID,
                LOCATION_ID,
                RECOMMENDATION_ID,
                decision="reject",
                request_id=REQUEST_ID,
                reason_code="insufficient_evidence",
                connection_factory=lambda: connection,
            )
    assert connection.rolled_back and connection.closed
    assert not any(
        "decide_location_delphi_recommendation" in query
        for query, _params in connection.operations
    )


def _make_app(provider, funcs, run_in_threadpool):
    from services.gateway.delphi_recommendation_review_routes import (
        register_delphi_recommendation_review_routes,
    )

    app = FastAPI()
    router = APIRouter()

    @app.middleware("http")
    async def bind_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    register_delphi_recommendation_review_routes(
        router, provider, run_in_threadpool, __import__("psycopg2")
    )
    app.include_router(router)
    return app


def test_review_routes_are_no_store_and_pass_actor_and_location():
    async def run_in_threadpool(func, *args, **kwargs):
        return funcs[func](*args, **kwargs)

    expected = {"location_id": LOCATION_ID, "recommendations": [], "has_more": False}
    funcs = {review.list_location_delphi_recommendation_reviews: lambda *_a, **_k: expected}
    client = TestClient(_make_app(object(), funcs, run_in_threadpool))
    response = client.get(f"/operator/api/delphi/{LOCATION_ID}/recommendations")
    assert response.status_code == 200
    assert response.json() == expected
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"


def test_decision_route_rejects_extra_or_non_string_fields():
    async def run_in_threadpool(*_args, **_kwargs):
        pytest.fail("invalid payload must not invoke decision service")

    client = TestClient(_make_app(object(), {}, run_in_threadpool))
    response = client.post(
        f"/operator/api/delphi/{LOCATION_ID}/recommendations/{RECOMMENDATION_ID}/decision",
        json={
            "decision": "reject",
            "request_id": REQUEST_ID,
            "reason_code": "other",
            "private_feedback": "unexpected",
        },
    )
    assert response.status_code == 400
    assert response.headers["cache-control"] == "no-store"


def test_routes_fail_closed_when_oidc_is_disabled():
    async def run_in_threadpool(*_args, **_kwargs):
        pytest.fail("OIDC-disabled request must not reach service")

    client = TestClient(_make_app(None, {}, run_in_threadpool))
    response = client.get(f"/operator/api/delphi/{LOCATION_ID}/recommendations")
    assert response.status_code == 404
    assert response.headers["cache-control"] == "no-store"
