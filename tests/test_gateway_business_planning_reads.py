"""Tests for location-scoped business model canvas Kernel reads."""

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
ROW = (
    str(uuid4()), "Primary Canvas", "Location operating model", "verified",
    2026, "business-model-canvas-v1", 3, 81.5, ["reviewed"], UPDATED_AT,
    UPDATED_AT, CONTENT, "manual", "location-source-17",
)


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
    assert auth_route_policy("POST", path, enabled=True) is None
    assert auth_route_policy("GET", path + "/extra", enabled=True) is None


def test_http_projection_is_no_store_and_requires_operator_session(monkeypatch):
    from services.gateway.business_planning_routes import register_business_planning_routes

    monkeypatch.setattr(
        "services.gateway.business_planning_reads.list_location_business_model_canvases",
        lambda *_args, **_kwargs: {"location_id": LOCATION_ID, "canvases": []},
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
