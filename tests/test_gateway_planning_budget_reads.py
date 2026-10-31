"""Tests for the location-scoped Kernel planning budget projection."""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest

from services.common.tenant_context import TenantContextDenied
from services.gateway import planning_budget_reads as reads
from services.gateway.operator_auth import auth_route_policy

pytest.importorskip("fastapi")
from fastapi import APIRouter, FastAPI  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

OPERATOR_ID = str(uuid4())
LOCATION_ID = str(uuid4())
PLAN_ID = str(uuid4())
COLUMNS = (
    "financial_plan_id", "plan_status", "currency", "period_start", "period_end",
    "has_objective", "budget_line_count", "planned_amount", "verified_expense_amount",
    "budget_variance", "nonmatching_currency_expense_count", "planning_scenario_count",
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
        plan_id, "active", "USD", date(2026, 1, 1), date(2026, 12, 31), True,
        3, Decimal("1200.00"), Decimal("475.25"), Decimal("724.75"), 1, 2,
    )


def _http_projection(location_id=LOCATION_ID, *, offset=0, plans=None, has_more=False, next_offset=None):
    return {
        "location_id": location_id,
        "offset": offset,
        "plans": plans if plans is not None else [{
            "financial_plan_id": PLAN_ID,
            "plan_status": "active",
            "currency": "USD",
            "period_start": date(2026, 1, 1),
            "period_end": date(2026, 12, 31),
            "has_objective": True,
            "budget_line_count": 3,
            "planned_amount": Decimal("1200.00"),
            "verified_expense_amount": Decimal("475.25"),
            "budget_variance": Decimal("724.75"),
            "nonmatching_currency_expense_count": 1,
            "planning_scenario_count": 2,
        }],
        "has_more": has_more,
        "next_offset": next_offset,
    }


def test_budget_read_sets_exact_context_and_calls_the_bounded_projection():
    connection = _Connection([_row(), _row(str(uuid4()))])
    contexts = []

    def set_context(conn, **kwargs):
        assert conn is connection
        contexts.append(kwargs)

    with patch.object(reads, "set_operator_tenant_context", set_context):
        result = reads.list_location_budget_summaries(
            OPERATOR_ID,
            LOCATION_ID,
            limit="1",
            offset="4",
            connection_factory=lambda: connection,
        )

    assert contexts == [{
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "planning_budget",
        "action": "read",
    }]
    assert [query for query, _ in connection.operations[:3]] == [
        "SET TRANSACTION READ ONLY",
        "SET LOCAL statement_timeout = '8s'",
        "SET LOCAL lock_timeout = '2s'",
    ]
    assert connection.operations[-1] == (
        "SELECT * FROM kokonut_security.list_location_budget_summaries( %s::uuid, %s::integer, %s::integer )",
        (LOCATION_ID, 2, 4),
    )
    assert result == {
        "location_id": LOCATION_ID,
        "offset": 4,
        "plans": [dict(zip(COLUMNS, _row()))],
        "has_more": True,
        "next_offset": 5,
    }
    assert connection.rolled_back and connection.closed


@pytest.mark.parametrize("kwargs", [
    {"limit": "0"},
    {"limit": "51"},
    {"limit": "many"},
    {"limit": True},
    {"offset": "-1"},
    {"offset": "10001"},
    {"offset": "1.2"},
])
def test_invalid_page_inputs_fail_before_database_access(kwargs):
    with pytest.raises(reads.PlanningBudgetReadInvalid):
        reads.list_location_budget_summaries(
            OPERATOR_ID,
            LOCATION_ID,
            connection_factory=lambda: pytest.fail("invalid input must fail before DB access"),
            **kwargs,
        )


@pytest.mark.parametrize("operator_id,location_id", [
    ("not-a-uuid", LOCATION_ID),
    (OPERATOR_ID, "not-a-uuid"),
])
def test_invalid_identity_fails_before_database_access(operator_id, location_id):
    with pytest.raises(reads.PlanningBudgetReadInvalid):
        reads.list_location_budget_summaries(
            operator_id,
            location_id,
            connection_factory=lambda: pytest.fail("invalid identity must fail before DB access"),
        )


def test_tenant_denial_rolls_back_and_never_calls_projection():
    connection = _Connection([])

    def deny(*_args, **_kwargs):
        raise TenantContextDenied("denied")

    with patch.object(reads, "set_operator_tenant_context", deny):
        with pytest.raises(TenantContextDenied):
            reads.list_location_budget_summaries(
                OPERATOR_ID,
                LOCATION_ID,
                connection_factory=lambda: connection,
            )

    assert not any("list_location_budget_summaries" in query for query, _ in connection.operations)
    assert connection.rolled_back and connection.closed


def test_projection_contract_excludes_plan_labels_categories_and_financial_facts():
    forbidden = {
        "name", "objective_id", "category", "notes", "description", "vendor",
        "counterparty", "transaction_id", "financial_transaction_id", "amount_usd",
        "scenario_name", "assumptions", "evidence_urls",
    }
    assert not forbidden.intersection(COLUMNS)
    assert "budget_variance" in COLUMNS
    assert "nonmatching_currency_expense_count" in COLUMNS
    assert "planning_scenario_count" in COLUMNS


def test_route_policy_requires_exact_location_planning_budget_grant():
    path = f"/operator/api/planning/{LOCATION_ID}/budgets"
    assert auth_route_policy("GET", path, enabled=True) == {
        "resource": "planning_budget",
        "action": "read",
        "public": False,
        "location_id": LOCATION_ID,
        "scope_required": True,
        "operator_auth": True,
    }
    assert auth_route_policy("POST", path, enabled=True) is None
    assert auth_route_policy("GET", path + "/extra", enabled=True) is None


def test_http_budget_projection_is_no_store_and_location_scoped(monkeypatch):
    from services.gateway.planning_budget_routes import register_planning_budget_routes

    monkeypatch.setattr(
        "services.gateway.planning_budget_reads.list_location_budget_summaries",
        lambda *_args, **_kwargs: _http_projection(),
    )
    app = FastAPI()
    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_planning_budget_routes(router, object(), run_in_threadpool, SimpleNamespace(Error=Exception))
    app.include_router(router)

    @app.middleware("http")
    async def add_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    with TestClient(app) as client:
        response = client.get(f"/operator/api/planning/{LOCATION_ID}/budgets")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert response.json()["location_id"] == LOCATION_ID
    assert response.json()["plans"][0]["financial_plan_id"] == PLAN_ID
    assert response.json()["plans"][0]["planned_amount"] == 1200.0


def test_budget_read_stops_pagination_at_offset_ceiling():
    connection = _Connection([_row(), _row(str(uuid4()))])
    with patch.object(reads, "set_operator_tenant_context", lambda *_args, **_kwargs: None):
        result = reads.list_location_budget_summaries(
            OPERATOR_ID,
            LOCATION_ID,
            limit=1,
            offset=10_000,
            connection_factory=lambda: connection,
        )

    assert len(result["plans"]) == 1
    assert result["offset"] == 10_000
    assert result["has_more"] is False
    assert result["next_offset"] is None
    assert connection.closed


@pytest.mark.parametrize(
    "mutate",
    [
        lambda result: result["plans"][0].update(private_metadata={"secret": True}),
        lambda result: result["plans"][0].update(plan_status="unrecognized"),
        lambda result: result["plans"][0].update(budget_line_count=True),
        lambda result: result["plans"][0].update(period_end=date(2025, 1, 1)),
        lambda result: result.update(location_id=str(uuid4())),
        lambda result: result.update(offset=1),
        lambda result: result.update(has_more=True, next_offset=24),
    ],
)
def test_http_budget_projection_rejects_malformed_or_mismatched_data(monkeypatch, mutate):
    from services.gateway.planning_budget_routes import register_planning_budget_routes

    result = _http_projection()
    mutate(result)
    monkeypatch.setattr(
        "services.gateway.planning_budget_reads.list_location_budget_summaries",
        lambda *_args, **_kwargs: result,
    )
    app = FastAPI()
    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_planning_budget_routes(router, object(), run_in_threadpool, SimpleNamespace(Error=Exception))
    app.include_router(router)

    @app.middleware("http")
    async def add_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    with TestClient(app) as client:
        response = client.get(f"/operator/api/planning/{LOCATION_ID}/budgets")

    assert response.status_code == 500
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert response.json() == {"error": "Planning budget read unavailable"}
