"""Contracts for authenticated, location-scoped AI-summary draft generation."""

from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest

from services.common.tenant_context import TenantContextDenied
from services.gateway import ai_summary_draft as drafts

pytest.importorskip("fastapi")
from fastapi import APIRouter, FastAPI  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

OPERATOR_ID = str(uuid4())
LOCATION_ID = str(uuid4())
REQUEST_ID = str(uuid4())
SUMMARY_ID = str(uuid4())


class _Connection:
    def __init__(self, *, existing=None, created=None):
        self.existing = existing
        self.created = created
        self.events = []
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

    def __exit__(self, *_exc):
        return False

    def execute(self, query, params=None):
        normalized = " ".join(query.split())
        self.connection.operations.append((normalized, params))
        self.connection.events.append(normalized)
        self.query = normalized

    def fetchone(self):
        if "get_location_ai_summary_draft_request" in self.query:
            return self.connection.existing
        if "create_location_ai_summary_draft" in self.query:
            return self.connection.created
        return None


def _set_context(connection, **kwargs):
    connection.events.append("SIGNED_CONTEXT")
    connection.context = kwargs


def _built_summary(*_args):
    return {
        "content": "Synthetic summary",
        "source_tables": ["farm_activity"],
        "summary_type": "operations",
    }


def test_create_sets_scope_before_lookup_generation_and_write_then_commits():
    connection = _Connection(
        created=(SUMMARY_ID, "Synthetic summary", ["farm_activity"], "rules-v1", None, "draft", False)
    )
    with (
        patch.object(drafts, "set_operator_tenant_context", _set_context),
        patch.object(drafts, "assert_agent_action_allowed") as safety,
        patch("services.gateway.ai_summary_draft.build_summary", side_effect=_built_summary) as build,
    ):
        result = drafts.create_operator_ai_summary_draft(
            OPERATOR_ID,
            LOCATION_ID,
            summary_type="operations",
            request_id=REQUEST_ID,
            connection_factory=lambda: connection,
        )

    lookup = next(i for i, event in enumerate(connection.events)
                  if "get_location_ai_summary_draft_request" in event)
    create = next(i for i, event in enumerate(connection.events)
                  if "create_location_ai_summary_draft" in event)
    assert connection.events.index("SIGNED_CONTEXT") < lookup < create
    build.assert_called_once_with(connection, LOCATION_ID, "operations")
    safety.assert_called_once_with(
        "create",
        "ai_summary",
        {"status": "draft", "created_by": OPERATOR_ID, "location_id": LOCATION_ID},
    )
    assert connection.context == {
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "ai_summary",
        "action": "draft",
    }
    assert result["summary_id"] == SUMMARY_ID
    assert result["resulting_status"] == "draft"
    assert result["replayed"] is False
    assert connection.committed and connection.rolled_back and connection.closed


def test_exact_retry_returns_prior_draft_without_regenerating():
    connection = _Connection(
        existing=(SUMMARY_ID, "Original summary", ["farm_activity"], "rules-v1", None, "verified")
    )
    with (
        patch.object(drafts, "set_operator_tenant_context", _set_context),
        patch("services.gateway.ai_summary_draft.build_summary") as build,
    ):
        result = drafts.create_operator_ai_summary_draft(
            OPERATOR_ID,
            LOCATION_ID,
            summary_type="operations",
            request_id=REQUEST_ID,
            connection_factory=lambda: connection,
        )

    build.assert_not_called()
    assert not any("create_location_ai_summary_draft" in event for event in connection.events)
    assert result["content"] == "Original summary"
    assert result["resulting_status"] == "verified"
    assert result["replayed"] is True
    assert connection.committed and connection.closed


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("operator_id", "bad"),
        ("location_id", "bad"),
        ("request_id", "bad"),
        ("summary_type", "unsupported"),
    ],
)
def test_invalid_draft_request_fails_before_database(field, value):
    arguments = {
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "summary_type": "operations",
        "request_id": REQUEST_ID,
        "connection_factory": lambda: pytest.fail("invalid request opened a connection"),
    }
    arguments[field] = value
    with pytest.raises(drafts.AiSummaryDraftInvalid):
        drafts.create_operator_ai_summary_draft(**arguments)


def test_tenant_denial_rolls_back_and_closes_without_generating(monkeypatch):
    connection = _Connection()
    monkeypatch.setattr(
        drafts,
        "set_operator_tenant_context",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(TenantContextDenied("denied")),
    )
    monkeypatch.setattr(
        "services.gateway.ai_summary_draft.build_summary",
        lambda *_args: pytest.fail("tenant denial must precede data reads"),
    )
    with pytest.raises(TenantContextDenied):
        drafts.create_operator_ai_summary_draft(
            OPERATOR_ID,
            LOCATION_ID,
            summary_type="operations",
            request_id=REQUEST_ID,
            connection_factory=lambda: connection,
        )
    assert connection.rolled_back and connection.closed
    assert all("get_location_ai_summary_draft_request" not in query
               and "create_location_ai_summary_draft" not in query
               for query, _params in connection.operations)


def test_draft_route_is_oidc_only_and_returns_no_store_json(monkeypatch):
    from services.gateway.ai_summary_draft_routes import register_ai_summary_draft_routes

    router = APIRouter()
    provider = object()
    expected = {
        "summary_id": SUMMARY_ID,
        "location_id": LOCATION_ID,
        "summary_type": "operations",
        "content": "Synthetic summary",
        "source_tables": ["farm_activity"],
        "model_version": "rules-v1",
        "created_at": None,
        "resulting_status": "draft",
        "replayed": False,
    }
    monkeypatch.setattr(
        "services.gateway.ai_summary_draft.create_operator_ai_summary_draft",
        lambda *_args, **_kwargs: expected,
    )

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_ai_summary_draft_routes(router, provider, run_in_threadpool, __import__("psycopg2"))
    app = FastAPI()
    app.include_router(router)

    @app.middleware("http")
    async def add_operator_session(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    response = TestClient(app).post(
        f"/operator/api/ai-summaries/{LOCATION_ID}/drafts",
        json={"summary_type": "operations", "request_id": REQUEST_ID},
    )
    assert response.status_code == 201
    assert response.json()["resulting_status"] == "draft"
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"


def test_retry_response_uses_success_status(monkeypatch):
    from services.gateway.ai_summary_draft_routes import register_ai_summary_draft_routes

    router = APIRouter()

    async def run_in_threadpool(*_args, **_kwargs):
        return {"summary_id": SUMMARY_ID, "resulting_status": "draft", "replayed": True}

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
        f"/operator/api/ai-summaries/{LOCATION_ID}/drafts",
        json={"summary_type": "operations", "request_id": REQUEST_ID},
    )
    assert response.status_code == 200


def test_gateway_error_and_invalid_body_are_fail_closed():
    from services.gateway.ai_summary_draft_routes import register_ai_summary_draft_routes

    router = APIRouter()

    async def run_in_threadpool(*_args, **_kwargs):
        raise AssertionError("invalid body must not dispatch work")

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
        f"/operator/api/ai-summaries/{LOCATION_ID}/drafts",
        json={"summary_type": "operations", "request_id": REQUEST_ID, "extra": True},
    )
    assert response.status_code == 400
    assert response.headers["cache-control"] == "no-store"
