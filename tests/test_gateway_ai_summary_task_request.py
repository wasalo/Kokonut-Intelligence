"""Contracts for authenticated operator receipts for registered synthesis tasks."""

from datetime import datetime, timezone
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
CREATED_AT = datetime(2026, 10, 29, 12, 0, tzinfo=timezone.utc)


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
            return (
                REQUEST_ID,
                LOCATION_ID,
                "feedback_synthesis",
                "stakeholder_feedback",
                CREATED_AT,
                False,
            )
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
        "created_at": CREATED_AT,
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
        "created_at": "2026-10-29T12:00:00+00:00",
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


def _task_receipt_app(monkeypatch, writer):
    from services.gateway.ai_summary_draft_routes import register_ai_summary_draft_routes

    monkeypatch.setattr(
        "services.gateway.ai_summary_task_request.create_operator_ai_summary_task_request",
        writer,
    )
    router = APIRouter()

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

    return app


def test_task_receipt_openapi_publishes_registry_and_strict_result_contract(monkeypatch):
    app = _task_receipt_app(monkeypatch, lambda *_args, **_kwargs: {})
    spec = app.openapi()
    operation = spec["paths"][
        "/operator/api/ai-summaries/{location_id}/synthesis-requests"
    ]["post"]
    request_schema = operation["requestBody"]["content"]["application/json"]["schema"]
    response_schema = spec["components"]["schemas"]["AiSummaryTaskReceipt"]

    assert request_schema["additionalProperties"] is False
    assert set(request_schema["required"]) == {"task_key", "summary_type", "request_id"}
    assert set(request_schema["properties"]["task_key"]["enum"]) == set(
        task_requests.TASK_SUMMARY_TYPES
    )
    assert set(request_schema["properties"]["summary_type"]["enum"]) == {
        value for values in task_requests.TASK_SUMMARY_TYPES.values() for value in values
    }
    assert request_schema["properties"]["request_id"]["format"] == "uuid"
    assert response_schema["additionalProperties"] is False
    assert set(response_schema["properties"]) == {
        "request_id", "location_id", "task_key", "summary_type", "created_at",
        "replayed", "status",
    }
    assert operation["responses"]["201"]["content"]["application/json"]["schema"]["$ref"].endswith(
        "AiSummaryTaskReceipt"
    )
    assert {"400", "403", "404", "409", "500", "503"}.issubset(operation["responses"])


@pytest.mark.parametrize(
    "payload",
    [
        {"task_key": "not_registered", "summary_type": "stakeholder_feedback", "request_id": REQUEST_ID},
        {"task_key": "feedback_synthesis", "summary_type": "financial", "request_id": REQUEST_ID},
        {"task_key": "feedback_synthesis", "summary_type": "stakeholder_feedback", "request_id": "bad"},
        {
            "task_key": "feedback_synthesis",
            "summary_type": "stakeholder_feedback",
            "request_id": REQUEST_ID,
            "operator_id": OPERATOR_ID,
        },
    ],
)
def test_invalid_task_receipt_request_is_sanitized_before_dispatch(monkeypatch, payload):
    calls = []

    def writer(*args, **kwargs):
        calls.append((args, kwargs))
        return {}

    app = _task_receipt_app(monkeypatch, writer)
    with TestClient(app) as client:
        response = client.post(
            f"/operator/api/ai-summaries/{LOCATION_ID}/synthesis-requests", json=payload
        )

    assert response.status_code == 400
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {"error": "Synthesis task request is invalid"}
    assert calls == []


@pytest.mark.parametrize("replayed, expected_status", [(False, 201), (True, 200)])
def test_task_receipt_validates_service_result_and_preserves_replay_status(
    monkeypatch, replayed, expected_status
):
    expected = {
        "request_id": REQUEST_ID,
        "location_id": LOCATION_ID,
        "task_key": "feedback_synthesis",
        "summary_type": "stakeholder_feedback",
        "created_at": CREATED_AT,
        "replayed": replayed,
        "status": "authorized",
    }
    calls = []

    def writer(*args, **kwargs):
        calls.append((args, kwargs))
        return expected

    app = _task_receipt_app(monkeypatch, writer)
    with TestClient(app) as client:
        response = client.post(
            f"/operator/api/ai-summaries/{LOCATION_ID}/synthesis-requests",
            json={
                "task_key": "feedback_synthesis",
                "summary_type": "stakeholder_feedback",
                "request_id": REQUEST_ID,
            },
        )

    assert response.status_code == expected_status
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {**expected, "created_at": "2026-10-29T12:00:00+00:00"}
    assert calls[0][0][1] == LOCATION_ID
    assert calls[0][1] == {
        "task_key": "feedback_synthesis",
        "summary_type": "stakeholder_feedback",
        "request_id": REQUEST_ID,
    }


@pytest.mark.parametrize(
    "changes",
    [
        {"location_id": "99999999-9999-4999-8999-999999999999"},
        {"task_key": "financial_resilience_synthesis"},
        {"status": "draft"},
        {"created_at": None},
    ],
)
def test_malformed_or_mismatched_task_receipt_fails_closed(monkeypatch, changes):
    result = {
        "request_id": REQUEST_ID,
        "location_id": LOCATION_ID,
        "task_key": "feedback_synthesis",
        "summary_type": "stakeholder_feedback",
        "created_at": CREATED_AT,
        "replayed": False,
        "status": "authorized",
    }
    result.update(changes)
    app = _task_receipt_app(monkeypatch, lambda *_args, **_kwargs: result)
    with TestClient(app) as client:
        response = client.post(
            f"/operator/api/ai-summaries/{LOCATION_ID}/synthesis-requests",
            json={
                "task_key": "feedback_synthesis",
                "summary_type": "stakeholder_feedback",
                "request_id": REQUEST_ID,
            },
        )

    assert response.status_code == 500
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {"error": "AI summary task request unavailable"}
