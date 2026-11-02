"""Tests for location-scoped business model canvas Kernel reads."""

from copy import deepcopy
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest

from services.common.tenant_context import TenantContextDenied
from services.gateway import business_planning_reads as reads
from services.gateway.operator_auth import auth_route_policy

pytest.importorskip("fastapi")
from fastapi import APIRouter, FastAPI  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

OPERATOR_ID = str(uuid4())
LOCATION_ID = str(uuid4())
COLUMNS = (
    "canvas_id", "canvas_name", "canvas_description", "lifecycle_status",
    "fiscal_year", "schema_version", "version", "health_score", "tags",
    "created_at", "updated_at", "content", "source_system", "source_reference",
)
UPDATED_AT = datetime(2026, 10, 19, 12, 0, tzinfo=timezone.utc)
CONTENT = {
    "key_partners": [{"name": "Local growers"}],
    "value_propositions": [{"claim": "Healthy soil", "evidence_url": "https://example.invalid/evidence/1"}],
    "cost_structure": {"currency": "USD", "items": ["seedlings"]},
}
CANVAS_CONTENT = {
    "key_partners": [{"name": "Local growers"}],
    "key_activities": [],
    "key_resources": [],
    "value_propositions": [{"claim": "Healthy soil", "evidence_url": "https://example.invalid/evidence/1"}],
    "customer_relationships": [],
    "channels": [],
    "customer_segments": [],
    "revenue_streams": [],
    "cost_structure": {"currency": "USD", "items": ["seedlings"]},
}
ROW = (
    str(uuid4()), "Primary Canvas", "Location operating model", "verified",
    2026, "business-model-canvas-v1", 3, 81.5, ["reviewed"], UPDATED_AT,
    UPDATED_AT, CONTENT, "manual", "location-source-17",
)

CANVAS_RESPONSE = {
    "canvas_id": ROW[0],
    "canvas_name": "Primary Canvas",
    "canvas_description": "Location operating model",
    "lifecycle_status": "verified",
    "fiscal_year": 2026,
    "schema_version": "business-model-canvas-v1",
    "version": 3,
    "health_score": 81.5,
    "tags": ["reviewed"],
    "created_at": "2026-10-19T12:00:00+00:00",
    "updated_at": "2026-10-19T12:00:00+00:00",
    "content": CANVAS_CONTENT,
    "source_system": "manual",
    "source_reference": "location-source-17",
}


def _canvas_page(location_id=LOCATION_ID, *, offset=0, canvases=None, has_more=False, next_offset=None):
    return {
        "location_id": location_id,
        "offset": offset,
        "canvases": [deepcopy(CANVAS_RESPONSE)] if canvases is None else canvases,
        "has_more": has_more,
        "next_offset": next_offset,
    }


class _Connection:
    def __init__(self, rows):
        self.rows = rows
        self.operations = []
        self.rolled_back = False
        self.closed = False

    def cursor(self):
        return _Cursor(self)

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


class _Cursor:
    def __init__(self, connection):
        self.connection = connection
        self.description = None

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def execute(self, query, params=None):
        normalized = " ".join(query.split())
        self.connection.operations.append((normalized, params))
        if normalized.startswith("SELECT"):
            self.description = [SimpleNamespace(name=column) for column in COLUMNS]

    def fetchall(self):
        return self.connection.rows


def test_canvas_read_uses_signed_context_and_bounded_projection():
    connection = _Connection([ROW, (*ROW[:0],) + ROW])
    contexts = []

    def set_context(conn, **kwargs):
        assert conn is connection
        contexts.append(kwargs)

    with patch.object(reads, "set_operator_tenant_context", set_context):
        result = reads.list_location_business_model_canvases(
            OPERATOR_ID, LOCATION_ID, limit="1", offset="4",
            connection_factory=lambda: connection,
        )

    assert contexts == [{
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "business_planning",
        "action": "read",
    }]
    assert [query for query, _ in connection.operations[:3]] == [
        "SET TRANSACTION READ ONLY",
        "SET LOCAL statement_timeout = '8s'",
        "SET LOCAL lock_timeout = '2s'",
    ]
    query, params = connection.operations[-1]
    assert "kokonut_security.list_location_business_model_canvases" in query
    assert params == (LOCATION_ID, 2, 4)
    assert result == {
        "location_id": LOCATION_ID,
        "offset": 4,
        "canvases": [dict(zip(COLUMNS, ROW))],
        "has_more": True,
        "next_offset": 5,
    }
    assert result["canvases"][0]["content"] == CONTENT
    assert connection.rolled_back and connection.closed


def test_canvas_read_stops_page_continuation_at_offset_ceiling():
    connection = _Connection([ROW, ROW])
    with patch.object(reads, "set_operator_tenant_context", lambda *_args, **_kwargs: None):
        result = reads.list_location_business_model_canvases(
            OPERATOR_ID,
            LOCATION_ID,
            limit=1,
            offset=10000,
            connection_factory=lambda: connection,
        )

    assert len(result["canvases"]) == 1
    assert result["has_more"] is False
    assert result["next_offset"] is None
    assert connection.rolled_back and connection.closed


@pytest.mark.parametrize("kwargs", [
    {"limit": "0"}, {"limit": "51"}, {"limit": "many"}, {"limit": True},
    {"offset": "-1"}, {"offset": "10001"}, {"offset": "1.2"},
])
def test_invalid_page_input_fails_before_database_access(kwargs):
    with pytest.raises(reads.BusinessPlanningReadInvalid):
        reads.list_location_business_model_canvases(
            OPERATOR_ID, LOCATION_ID,
            connection_factory=lambda: pytest.fail("invalid input must fail before DB access"),
            **kwargs,
        )


@pytest.mark.parametrize("operator_id,location_id", [
    ("not-a-uuid", LOCATION_ID), (OPERATOR_ID, "not-a-uuid"),
])
def test_invalid_identity_fails_before_database_access(operator_id, location_id):
    with pytest.raises(reads.BusinessPlanningReadInvalid):
        reads.list_location_business_model_canvases(
            operator_id, location_id,
            connection_factory=lambda: pytest.fail("invalid identity must fail before DB access"),
        )


def test_tenant_denial_rolls_back_without_projection_call():
    connection = _Connection([])

    def deny(*_args, **_kwargs):
        raise TenantContextDenied("denied")

    with patch.object(reads, "set_operator_tenant_context", deny):
        with pytest.raises(TenantContextDenied):
            reads.list_location_business_model_canvases(
                OPERATOR_ID, LOCATION_ID, connection_factory=lambda: connection,
            )

    assert not any("list_location_business_model_canvases" in query
                   for query, _ in connection.operations)
    assert connection.rolled_back and connection.closed


def test_route_policy_requires_exact_location_business_planning_read_grant():
    path = f"/operator/api/business-planning/{LOCATION_ID}/canvases"
    assert auth_route_policy("GET", path, enabled=True) == {
        "resource": "business_planning",
        "action": "read",
        "public": False,
        "location_id": LOCATION_ID,
        "scope_required": True,
        "operator_auth": True,
    }
    assert auth_route_policy("POST", path, enabled=True) == {
        "resource": "business_planning",
        "action": "create",
        "public": False,
        "location_id": LOCATION_ID,
        "scope_required": True,
        "operator_auth": True,
    }
    assert auth_route_policy("GET", path + "/extra", enabled=True) is None


def test_http_projection_is_no_store_and_requires_operator_session(monkeypatch):
    from services.gateway.business_planning_routes import register_business_planning_routes

    monkeypatch.setattr(
        "services.gateway.business_planning_reads.list_location_business_model_canvases",
        lambda *_args, **_kwargs: _canvas_page(),
    )
    app = FastAPI()
    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_business_planning_routes(router, object(), run_in_threadpool, SimpleNamespace(Error=Exception))
    app.include_router(router)

    @app.middleware("http")
    async def add_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    with TestClient(app) as client:
        response = client.get(f"/operator/api/business-planning/{LOCATION_ID}/canvases")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert response.json()["location_id"] == LOCATION_ID
    assert response.json()["canvases"][0]["content"] == CANVAS_CONTENT
    assert response.json()["canvases"][0]["source_reference"] == "location-source-17"
    schema = app.openapi()["paths"][
        "/operator/api/business-planning/{location_id}/canvases"
    ]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
    assert schema["$ref"].endswith("BusinessCanvasListResponse")


@pytest.mark.parametrize(
    "mutate",
    [
        lambda result: result.update(private_metadata={"secret": True}),
        lambda result: result["canvases"][0].update(created_by=OPERATOR_ID),
        lambda result: result["canvases"][0]["content"].update(private_block={"secret": True}),
        lambda result: result["canvases"][0].update(lifecycle_status="unknown"),
        lambda result: result.update(location_id=str(uuid4())),
        lambda result: result.update(offset=1),
        lambda result: result.update(next_offset=25, has_more=False),
    ],
)
def test_http_projection_rejects_malformed_or_unrequested_fields_without_leaking(monkeypatch, mutate):
    from services.gateway.business_planning_routes import register_business_planning_routes

    result = _canvas_page()
    mutate(result)
    monkeypatch.setattr(
        "services.gateway.business_planning_reads.list_location_business_model_canvases",
        lambda *_args, **_kwargs: result,
    )
    app = FastAPI()
    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_business_planning_routes(router, object(), run_in_threadpool, SimpleNamespace(Error=Exception))
    app.include_router(router)

    @app.middleware("http")
    async def add_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    with TestClient(app) as client:
        response = client.get(f"/operator/api/business-planning/{LOCATION_ID}/canvases")

    assert response.status_code == 500
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert response.json() == {"error": "Business planning read unavailable"}
    assert "secret" not in response.text
