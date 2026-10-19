"""Tests for location-scoped business architecture Kernel projections."""

from datetime import date
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest

from services.common.tenant_context import TenantContextDenied
from services.gateway import business_architecture_reads as reads
from services.gateway.operator_auth import auth_route_policy

pytest.importorskip("fastapi")
from fastapi import APIRouter, FastAPI  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

OPERATOR_ID = str(uuid4())
LOCATION_ID = str(uuid4())
ROADMAP_ID = str(uuid4())
REQUIREMENT_ID = str(uuid4())
MAPPING_COLUMNS = (
    "roadmap_id", "roadmap_name", "roadmap_status", "planning_horizon_start",
    "planning_horizon_end", "requirement_id", "requirement_title", "need_type",
    "priority", "requirement_status", "capability_name", "value_stream_name",
    "strategy_perspective",
)
MISSION_COLUMNS = ("statement_type", "statement_text", "effective_date", "review_date")


class _Connection:
    def __init__(self, missions, mappings):
        self.rows = {"missions": missions, "mappings": mappings}
        self.operations = []
        self.result_key = None
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
        if "list_location_business_architecture_missions" in normalized:
            self.connection.result_key = "missions"
            columns = MISSION_COLUMNS
        elif "list_location_business_architecture_mappings" in normalized:
            self.connection.result_key = "mappings"
            columns = MAPPING_COLUMNS
        else:
            self.connection.result_key = None
            columns = ()
        if self.connection.result_key:
            self.description = [SimpleNamespace(name=column) for column in columns]

    def fetchall(self):
        return self.connection.rows[self.connection.result_key]


def _mapping_row(roadmap_id=ROADMAP_ID, requirement_id=REQUIREMENT_ID):
    return (
        roadmap_id, "Farm operating model", "active", date(2026, 1, 1),
        date(2026, 12, 31), requirement_id, "Protect soil and water", "sustainability",
        1, "validated", "Soil stewardship", "Regenerative production", "internal_process",
    )


def test_summary_uses_signed_context_and_bounded_read_functions():
    mission = ("mission", "Restore living soils with our community.", date(2026, 1, 1), date(2027, 1, 1))
    connection = _Connection([mission], [_mapping_row(), _mapping_row(str(uuid4()), str(uuid4()))])
    contexts = []

    def set_context(conn, **kwargs):
        assert conn is connection
        contexts.append(kwargs)

    with patch.object(reads, "set_operator_tenant_context", set_context):
        result = reads.get_location_business_architecture_summary(
            OPERATOR_ID, LOCATION_ID, limit="1", offset="5",
            connection_factory=lambda: connection,
        )

    assert contexts == [{
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "business_architecture",
        "action": "read",
    }]
    assert [query for query, _ in connection.operations[:3]] == [
        "SET TRANSACTION READ ONLY",
        "SET LOCAL statement_timeout = '8s'",
        "SET LOCAL lock_timeout = '2s'",
    ]
    assert "list_location_business_architecture_missions" in connection.operations[-2][0]
    assert "list_location_business_architecture_mappings" in connection.operations[-1][0]
    assert connection.operations[-1][1] == (LOCATION_ID, 2, 5)
    assert result == {
        "location_id": LOCATION_ID,
        "offset": 5,
        "missions": [dict(zip(MISSION_COLUMNS, mission))],
        "mappings": [dict(zip(MAPPING_COLUMNS, _mapping_row()))],
        "has_more": True,
        "next_offset": 6,
    }
    assert connection.rolled_back and connection.closed


@pytest.mark.parametrize("kwargs", [
    {"limit": "0"}, {"limit": "51"}, {"limit": "many"}, {"limit": True},
    {"offset": "-1"}, {"offset": "10001"}, {"offset": "1.2"},
])
def test_invalid_page_input_fails_before_database_access(kwargs):
    with pytest.raises(reads.BusinessArchitectureReadInvalid):
        reads.get_location_business_architecture_summary(
            OPERATOR_ID, LOCATION_ID,
            connection_factory=lambda: pytest.fail("invalid input must fail before DB access"),
            **kwargs,
        )


@pytest.mark.parametrize("operator_id,location_id", [
    ("not-a-uuid", LOCATION_ID), (OPERATOR_ID, "not-a-uuid"),
])
def test_invalid_identity_fails_before_database_access(operator_id, location_id):
    with pytest.raises(reads.BusinessArchitectureReadInvalid):
        reads.get_location_business_architecture_summary(
            operator_id, location_id,
            connection_factory=lambda: pytest.fail("invalid identity must fail before DB access"),
        )


def test_tenant_denial_rolls_back_without_projection_calls():
    connection = _Connection([], [])

    def deny(*_args, **_kwargs):
        raise TenantContextDenied("denied")

    with patch.object(reads, "set_operator_tenant_context", deny):
        with pytest.raises(TenantContextDenied):
            reads.get_location_business_architecture_summary(
                OPERATOR_ID, LOCATION_ID, connection_factory=lambda: connection,
            )

    assert not any("kokonut_security.list_location_business_architecture_" in query
                   for query, _ in connection.operations)
    assert connection.rolled_back and connection.closed


def test_route_policy_requires_exact_location_business_architecture_read_grant():
    path = f"/operator/api/business-architecture/{LOCATION_ID}/summary"
    assert auth_route_policy("GET", path, enabled=True) == {
        "resource": "business_architecture",
        "action": "read",
        "public": False,
        "location_id": LOCATION_ID,
        "scope_required": True,
        "operator_auth": True,
    }
    assert auth_route_policy("POST", path, enabled=True) is None
    assert auth_route_policy("GET", path + "/extra", enabled=True) is None


def test_http_projection_is_no_store_and_requires_operator_session(monkeypatch):
    from services.gateway.business_architecture_routes import register_business_architecture_routes

    monkeypatch.setattr(
        "services.gateway.business_architecture_reads.get_location_business_architecture_summary",
        lambda *_args, **_kwargs: {"location_id": LOCATION_ID, "missions": [], "mappings": []},
    )
    app = FastAPI()
    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_business_architecture_routes(
        router, object(), run_in_threadpool, SimpleNamespace(Error=Exception)
    )
    app.include_router(router)

    @app.middleware("http")
    async def add_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    with TestClient(app) as client:
        response = client.get(f"/operator/api/business-architecture/{LOCATION_ID}/summary")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert response.json()["location_id"] == LOCATION_ID
