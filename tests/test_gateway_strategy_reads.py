"""Tests for the location-scoped Kernel strategy read projection."""

from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest

from services.common.tenant_context import TenantContextDenied
from services.gateway import strategy_reads as reads
from services.gateway.operator_auth import auth_route_policy

pytest.importorskip("fastapi")
from fastapi import APIRouter, FastAPI  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

OPERATOR_ID = str(uuid4())
LOCATION_ID = str(uuid4())
PLAN_ID = str(uuid4())
UPDATED_AT = datetime(2026, 10, 19, 12, 0, tzinfo=timezone.utc)
COLUMNS = (
    "strategy_plan_id", "plan_name", "version", "plan_status", "visibility",
    "planning_horizon_start", "planning_horizon_end", "updated_at", "cascade_mode",
    "cascade_status", "has_parent_strategy", "objective_count", "initiative_count",
    "completed_initiative_count", "investment_case_count", "recommended_investment_count",
    "open_coherence_finding_count", "blocking_finding_count", "structural_gate_status",
    "open_review_task_count", "submitted_allocation_count", "approved_allocation_count",
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


def _row(plan_id=PLAN_ID):
    return (
        plan_id, "Water resilience strategy", 2, "active", "limited",
        date(2026, 1, 1), date(2030, 12, 31), UPDATED_AT, "adapted", "aligned", True,
        4, 6, 2, 3, 1, 1, 0, "ready", 2, 1, 1,
    )


def test_summary_read_sets_signed_context_and_calls_the_bounded_projection():
    connection = _Connection([_row(), _row(str(uuid4()))])
    contexts = []

    def set_context(conn, **kwargs):
        assert conn is connection
        contexts.append(kwargs)

    with patch.object(reads, "set_operator_tenant_context", set_context):
        result = reads.list_location_strategy_plan_summaries(
            OPERATOR_ID,
            LOCATION_ID,
            limit="1",
            offset="7",
            connection_factory=lambda: connection,
        )

    assert contexts == [{
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "strategy",
        "action": "read",
    }]
    assert [query for query, _ in connection.operations[:3]] == [
        "SET TRANSACTION READ ONLY",
        "SET LOCAL statement_timeout = '8s'",
        "SET LOCAL lock_timeout = '2s'",
    ]
    query, params = connection.operations[-1]
    assert "kokonut_security.list_location_strategy_plan_summaries" in query
    assert params == (LOCATION_ID, 2, 7)
    assert result["location_id"] == LOCATION_ID
    assert result["offset"] == 7
    assert result["has_more"] is True
    assert result["next_offset"] == 8
    assert result["plans"] == [dict(zip(COLUMNS, _row()))]
    assert connection.rolled_back and connection.closed


@pytest.mark.parametrize("kwargs", [
    {"limit": "0"},
    {"limit": "101"},
    {"limit": "many"},
    {"limit": True},
    {"offset": "-1"},
    {"offset": "10001"},
    {"offset": "1.2"},
])
def test_invalid_page_inputs_fail_before_database_access(kwargs):
    with pytest.raises(reads.StrategyReadInvalid):
        reads.list_location_strategy_plan_summaries(
            OPERATOR_ID,
            LOCATION_ID,
            connection_factory=lambda: pytest.fail("invalid input must fail before DB access"),
            **kwargs,
        )


def test_invalid_identity_fails_before_database_access():
    with pytest.raises(reads.StrategyReadInvalid):
        reads.list_location_strategy_plan_summaries(
            OPERATOR_ID,
            "not-a-uuid",
            connection_factory=lambda: pytest.fail("invalid input must fail before DB access"),
        )


def test_tenant_denial_does_not_call_projection_and_closes_transaction():
    connection = _Connection([])

    def deny(*_args, **_kwargs):
        raise TenantContextDenied("denied")

    with patch.object(reads, "set_operator_tenant_context", deny):
        with pytest.raises(TenantContextDenied):
            reads.list_location_strategy_plan_summaries(
                OPERATOR_ID,
                LOCATION_ID,
                connection_factory=lambda: connection,
            )

    assert not any("list_location_strategy_plan_summaries" in query for query, _ in connection.operations)
    assert connection.rolled_back and connection.closed


def test_projection_allowlist_excludes_free_text_identity_and_private_amounts():
    forbidden = {
        "diagnosis_summary", "guiding_policy", "theory_of_change", "cascade_rationale",
        "rationale", "decision_note", "party_id", "created_by_party_id", "estimated_cost",
    }
    assert not forbidden.intersection(COLUMNS)
    assert "structural_gate_status" in COLUMNS
    assert "has_parent_strategy" in COLUMNS


def test_route_policy_requires_exact_location_strategy_read_grant():
    path = f"/operator/api/strategy/{LOCATION_ID}/plans"
    assert auth_route_policy("GET", path, enabled=True) == {
        "resource": "strategy",
        "action": "read",
        "public": False,
        "location_id": LOCATION_ID,
        "scope_required": True,
        "operator_auth": True,
    }
    assert auth_route_policy("POST", path, enabled=True) is None
    assert auth_route_policy("GET", path + "/extra", enabled=True) is None


def test_http_projection_is_no_store_and_does_not_claim_execution_authority(monkeypatch):
    from services.gateway.strategy_routes import register_strategy_routes

    location = LOCATION_ID
    monkeypatch.setattr(
        "services.gateway.strategy_reads.list_location_strategy_plan_summaries",
        lambda *_args, **_kwargs: {"location_id": location, "plans": [], "has_more": False},
    )
    router_app = FastAPI()
    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_strategy_routes(router, object(), run_in_threadpool, SimpleNamespace(Error=Exception))
    router_app.include_router(router)

    @router_app.middleware("http")
    async def add_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    with TestClient(router_app) as client:
        response = client.get(f"/operator/api/strategy/{LOCATION_ID}/plans")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["location_id"] == LOCATION_ID
    assert "execution_authorized" not in response.json()
