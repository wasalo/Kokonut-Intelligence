"""Tests for location-scoped coordination governance summaries."""

from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest

from services.common.tenant_context import TenantContextDenied
from services.gateway import coordination_reads as reads
from services.gateway.operator_auth import auth_route_policy

pytest.importorskip("fastapi")
from fastapi import APIRouter, FastAPI  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

OPERATOR_ID = str(uuid4())
LOCATION_ID = str(uuid4())
COLUMNS = (
    "alliance_count", "draft_alliance_count", "proposed_alliance_count",
    "approved_alliance_count", "active_alliance_count", "paused_alliance_count",
    "completed_alliance_count", "dissolved_alliance_count", "rejected_alliance_count",
    "overdue_review_count", "open_conflict_declaration_count",
    "unreviewed_harm_analysis_count", "open_appeal_count", "open_remedy_count",
    "preserved_minority_view_count", "completed_knowledge_exchange_count",
    "open_learning_link_count", "draft_metric_observation_count",
    "rejected_metric_observation_count",
)
ROW = (3, 1, 0, 0, 1, 1, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 2, 1, 1)


class _Connection:
    def __init__(self, row):
        self.row = row
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

    def fetchone(self):
        return self.connection.row


def test_summary_sets_exact_context_and_reads_only_bounded_function():
    connection = _Connection(ROW)
    contexts = []

    def set_context(conn, **kwargs):
        assert conn is connection
        contexts.append(kwargs)

    with patch.object(reads, "set_operator_tenant_context", set_context):
        result = reads.get_location_coordination_governance_summary(
            OPERATOR_ID, LOCATION_ID, connection_factory=lambda: connection,
        )

    assert contexts == [{
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "coordination",
        "action": "read",
    }]
    assert [query for query, _ in connection.operations[:3]] == [
        "SET TRANSACTION READ ONLY",
        "SET LOCAL statement_timeout = '8s'",
        "SET LOCAL lock_timeout = '2s'",
    ]
    assert "kokonut_security.location_coordination_governance_summary" in connection.operations[-1][0]
    assert connection.operations[-1][1] == (LOCATION_ID,)
    assert result == {"location_id": LOCATION_ID, **dict(zip(COLUMNS, ROW))}
    assert connection.rolled_back and connection.closed


@pytest.mark.parametrize("operator_id,location_id", [
    ("not-a-uuid", LOCATION_ID), (OPERATOR_ID, "not-a-uuid"),
])
def test_invalid_identity_fails_before_database_access(operator_id, location_id):
    with pytest.raises(reads.CoordinationReadInvalid):
        reads.get_location_coordination_governance_summary(
            operator_id, location_id,
            connection_factory=lambda: pytest.fail("invalid identity must fail before DB access"),
        )


def test_tenant_denial_rolls_back_without_projection_call():
    connection = _Connection(ROW)

    def deny(*_args, **_kwargs):
        raise TenantContextDenied("denied")

    with patch.object(reads, "set_operator_tenant_context", deny):
        with pytest.raises(TenantContextDenied):
            reads.get_location_coordination_governance_summary(
                OPERATOR_ID, LOCATION_ID, connection_factory=lambda: connection,
            )

    assert not any("location_coordination_governance_summary" in query
                   for query, _ in connection.operations)
    assert connection.rolled_back and connection.closed


def test_summary_output_schema_contains_only_aggregate_governance_fields():
    assert "alliance_count" in COLUMNS
    assert "open_conflict_declaration_count" in COLUMNS
    assert "unreviewed_harm_analysis_count" in COLUMNS
    assert "open_remedy_count" in COLUMNS
    assert "party_id" not in COLUMNS
    assert "description" not in COLUMNS
    assert "evidence" not in COLUMNS


def test_route_policy_requires_exact_location_coordination_read_grant():
    path = f"/operator/api/coordination/{LOCATION_ID}/summary"
    assert auth_route_policy("GET", path, enabled=True) == {
        "resource": "coordination",
        "action": "read",
        "public": False,
        "location_id": LOCATION_ID,
        "scope_required": True,
        "operator_auth": True,
    }
    assert auth_route_policy("POST", path, enabled=True) is None
    assert auth_route_policy("GET", path + "/extra", enabled=True) is None


def test_http_projection_is_no_store_and_operator_authenticated(monkeypatch):
    from services.gateway.coordination_routes import register_coordination_routes

    monkeypatch.setattr(
        "services.gateway.coordination_reads.get_location_coordination_governance_summary",
        lambda *_args, **_kwargs: {"location_id": LOCATION_ID, "alliance_count": 3},
    )
    app = FastAPI()
    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_coordination_routes(router, object(), run_in_threadpool, SimpleNamespace(Error=Exception))
    app.include_router(router)

    @app.middleware("http")
    async def add_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    with TestClient(app) as client:
        response = client.get(f"/operator/api/coordination/{LOCATION_ID}/summary")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert response.json()["alliance_count"] == 3
