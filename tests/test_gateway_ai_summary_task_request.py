"""Contracts for authenticated operator receipts for registered synthesis tasks."""

from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest

from services.common.tenant_context import TenantContextDenied
from services.gateway import ai_summary_task_request as task_requests

pytest.importorskip("fastapi")
from fastapi import APIRouter, FastAPI  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

OPERATOR_ID = str(uuid4())
LOCATION_ID = str(uuid4())
REQUEST_ID = str(uuid4())


class _Connection:
    def __init__(self):
        self.operations = []
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
        self.query = ""

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, query, params=None):
        self.query = " ".join(query.split())
        self.connection.operations.append((self.query, params))

    def fetchone(self):
        if "create_location_ai_summary_operator_task_request" in self.query:
            return (REQUEST_ID, LOCATION_ID, "feedback_synthesis", "stakeholder_feedback", None, False)
        return None


def test_receipt_sets_operator_scope_then_calls_bounded_function_and_commits():
    connection = _Connection()
    with patch.object(task_requests, "set_operator_tenant_context") as set_context:
        result = task_requests.create_operator_ai_summary_task_request(
            OPERATOR_ID,
            LOCATION_ID,
            task_key="feedback_synthesis",
            summary_type="stakeholder_feedback",
            request_id=REQUEST_ID,
            connection_factory=lambda: connection,
        )

    set_context.assert_called_once_with(
        connection,
        operator_id=OPERATOR_ID,
        location_id=LOCATION_ID,
        resource="ai_summary",
        action="draft",
    )
    query, params = connection.operations[-1]
    assert "create_location_ai_summary_operator_task_request" in query
    assert params == (LOCATION_ID, "feedback_synthesis", "stakeholder_feedback", REQUEST_ID)
    assert result == {
        "request_id": REQUEST_ID,
        "location_id": LOCATION_ID,
        "task_key": "feedback_synthesis",
        "summary_type": "stakeholder_feedback",
        "created_at": None,
        "replayed": False,
        "status": "authorized",
    }
    assert connection.committed and connection.rolled_back and connection.closed


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("operator_id", "bad"),
        ("location_id", "bad"),
        ("request_id", "bad"),
        ("task_key", "unregistered_task"),
        ("summary_type", "financial"),
    ],
)
def test_invalid_task_receipt_fails_before_connecting(field, value):
    kwargs = {
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "task_key": "feedback_synthesis",
        "summary_type": "stakeholder_feedback",
        "request_id": REQUEST_ID,
        "connection_factory": lambda: pytest.fail("invalid task request connected to PostgreSQL"),
    }
    kwargs[field] = value
    with pytest.raises(task_requests.AiSummaryTaskRequestInvalid):
        task_requests.create_operator_ai_summary_task_request(**kwargs)


def test_operator_scope_denial_rolls_back_and_closes_before_request_function():
    connection = _Connection()
    with patch.object(
        task_requests,
        "set_operator_tenant_context",
        side_effect=TenantContextDenied("denied"),
    ):
        with pytest.raises(TenantContextDenied):
            task_requests.create_operator_ai_summary_task_request(
                OPERATOR_ID,
                LOCATION_ID,
                task_key="feedback_synthesis",
                summary_type="stakeholder_feedback",
                request_id=REQUEST_ID,
                connection_factory=lambda: connection,
            )
    assert connection.rolled_back and connection.closed
    assert not any("create_location_ai_summary_operator_task_request" in q
                   for q, _params in connection.operations)


def test_task_receipt_route_is_oidc_only_no_store_and_returns_only_receipt(monkeypatch):
    from services.gateway.ai_summary_draft_routes import register_ai_summary_draft_routes

    router = APIRouter()
    expected = {
        "request_id": REQUEST_ID,
        "location_id": LOCATION_ID,
        "task_key": "feedback_synthesis",
        "summary_type": "stakeholder_feedback",
        "created_at": None,
        "replayed": False,
        "status": "authorized",
    }
    monkeypatch.setattr(
        "services.gateway.ai_summary_task_request.create_operator_ai_summary_task_request",
        lambda *_args, **_kwargs: expected,
    )

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_ai_summary_draft_routes(router, object(), run_in_threadpool, __import__("psycopg2"))
    app = FastAPI()
    app.include_router(router)

    @app.middleware("http")
    async def add_operator_session(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    response = TestClient(app).post(
        f"/operator/api/ai-summaries/{LOCATION_ID}/synthesis-requests",
        json={
            "task_key": "feedback_synthesis",
            "summary_type": "stakeholder_feedback",
            "request_id": REQUEST_ID,
        },
    )
    assert response.status_code == 201
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert response.json() == expected


def test_task_receipt_route_rejects_extra_fields_without_dispatch():
    from services.gateway.ai_summary_draft_routes import register_ai_summary_draft_routes

    router = APIRouter()
    calls = []

    async def run_in_threadpool(function, *args, **kwargs):
        calls.append((function, args, kwargs))
        return {}

    register_ai_summary_draft_routes(router, object(), run_in_threadpool, __import__("psycopg2"))
    app = FastAPI()
    app.include_router(router)

    @app.middleware("http")
    async def add_operator_session(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    response = TestClient(app).post(
        f"/operator/api/ai-summaries/{LOCATION_ID}/synthesis-requests",
        json={
            "task_key": "feedback_synthesis",
            "summary_type": "stakeholder_feedback",
            "request_id": REQUEST_ID,
            "operator_id": OPERATOR_ID,
        },
    )
    assert response.status_code == 400
    assert calls == []
