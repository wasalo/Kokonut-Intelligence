"""Location-scoped funding draft and proposed-tranche Gateway contracts."""

from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest

from services.common.tenant_context import TenantContextDenied
from services.gateway import solution_lifecycle_actions as actions
from services.gateway import solution_lifecycle_reads as reads
from services.gateway.operator_auth import auth_route_policy

pytest.importorskip("fastapi")
from fastapi import APIRouter, FastAPI  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

OPERATOR_ID = str(uuid4())
LOCATION_ID = str(uuid4())
SOLUTION_ID = str(uuid4())
REQUEST_ID = str(uuid4())
RESULT = {
    "funding_case_id": str(uuid4()),
    "decision_status": "draft",
    "tranche_count": 1,
    "created_at": "2026-10-20T12:00:00+00:00",
    "replayed": False,
}
PROPOSAL = {
    "capital_stage": "pilot",
    "funding_instrument": "community_fund",
    "requested_amount": "1000.00",
    "minimum_viable_amount": "500.00",
    "maximum_authorized_amount": "1200.00",
    "currency": "cUSD",
    "risk_adjusted_expected_value": "900.00",
    "public_goods_value": "1100.00",
    "community_share": "100.00",
    "downside_exposure": "250.00",
    "rationale": "Synthetic pilot funding draft",
    "evidence": [{"ref": "synthetic:budget"}],
    "tranches": [{
        "amount": 400,
        "milestone_conditions": {"milestone": "soil baseline reviewed"},
    }],
}
BODY = {"request_id": REQUEST_ID, **PROPOSAL}


class _Connection:
    def __init__(self, row=None, rows=()):
        self.row = row
        self.rows = list(rows)
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
        row = connection.row or (connection.rows[0] if connection.rows else {})
        self.description = tuple(SimpleNamespace(name=key) for key in row)

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def execute(self, query, params=None):
        self.connection.operations.append((" ".join(query.split()), params))

    def fetchone(self):
        if self.connection.row is None:
            return None
        return tuple(self.connection.row.values())

    def fetchall(self):
        return [tuple(row.values()) for row in self.connection.rows]


def test_funding_proposal_sets_exact_create_context_and_commits_draft_only():
    connection = _Connection(RESULT)
    contexts = []

    def set_context(conn, **kwargs):
        assert conn is connection
        contexts.append(kwargs)

    with patch.object(actions, "set_operator_tenant_context", set_context):
        result = actions.propose_location_solution_funding(
            OPERATOR_ID,
            LOCATION_ID,
            SOLUTION_ID,
            REQUEST_ID,
            **PROPOSAL,
            connection_factory=lambda: connection,
        )

    assert contexts == [{
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "solution_lifecycle",
        "action": "create",
    }]
    query, params = connection.operations[-1]
    assert "kokonut_security.propose_location_solution_funding" in query
    assert params == (
        LOCATION_ID, SOLUTION_ID, REQUEST_ID, "pilot", "community_fund",
        "1000.00", "500.00", "1200.00", "cUSD", "900.00", "1100.00",
        "100.00", "250.00", "Synthetic pilot funding draft",
        '[{"ref":"synthetic:budget"}]',
        '[{"amount":400.00,"milestone_conditions":{"milestone":"soil baseline reviewed"}}]',
    )
    assert result == RESULT
    assert connection.committed and connection.closed and not connection.rolled_back


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"capital_stage": "unknown"}, "capital stage"),
        ({"funding_instrument": "crypto"}, "instrument"),
        ({"requested_amount": -1}, "nonnegative"),
        ({"requested_amount": 1.001}, "two decimal places"),
        ({"requested_amount": float("inf")}, "finite amount"),
        ({"minimum_viable_amount": 1201}, "Minimum viable amount cannot exceed"),
        ({"maximum_authorized_amount": 999}, "Maximum authorized amount cannot be below"),
        ({"currency": "bad currency"}, "Currency"),
        ({"rationale": "  "}, "rationale"),
        ({"evidence": {}}, "evidence must be a list"),
        ({"tranches": {}}, "tranches must be a list"),
        ({"tranches": [{"amount": -1, "milestone_conditions": {}}]}, "Tranche amount must be nonnegative"),
        ({"tranches": [{"amount": 1201, "milestone_conditions": {}}]}, "tranche total exceeds"),
        ({"tranches": [{"amount": 1, "milestone_conditions": []}]}, "milestone conditions"),
    ],
)
def test_invalid_funding_proposal_fails_before_database(changes, message):
    payload = {**PROPOSAL, **changes}
    with pytest.raises(actions.SolutionLifecycleActionInvalid, match=message):
        actions.propose_location_solution_funding(
            OPERATOR_ID,
            LOCATION_ID,
            SOLUTION_ID,
            REQUEST_ID,
            **payload,
            connection_factory=lambda: pytest.fail("invalid proposal must fail before DB"),
        )


def test_funding_target_read_uses_same_connection_and_signed_read_context():
    row = {
        "solution_id": SOLUTION_ID,
        "solution_name": "Soil restoration",
        "solution_type": "practice",
        "current_stage": "testing",
        "solution_status": "active",
    }
    connection = _Connection(rows=[row])
    contexts = []
    with patch.object(
        reads,
        "set_operator_tenant_context",
        lambda conn, **kwargs: contexts.append((conn, kwargs)),
    ):
        result = reads.list_location_solution_funding_targets(
            OPERATOR_ID, LOCATION_ID, limit=1, connection_factory=lambda: connection
        )
    assert contexts == [(connection, {
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "solution_lifecycle",
        "action": "read",
    })]
    assert connection.operations[0][0] == "SET TRANSACTION READ ONLY"
    assert "kokonut_security.list_location_solution_funding_targets" in connection.operations[-1][0]
    assert result["solutions"] == [row]
    assert connection.closed and connection.rolled_back and not connection.committed


def test_funding_routes_have_exact_read_and_create_location_policies():
    target_path = f"/operator/api/solution-lifecycle/{LOCATION_ID}/funding/targets"
    proposal_path = f"/operator/api/solution-lifecycle/{LOCATION_ID}/solutions/{SOLUTION_ID}/funding"
    assert auth_route_policy("GET", target_path, enabled=True) == {
        "resource": "solution_lifecycle", "action": "read", "public": False,
        "location_id": LOCATION_ID, "scope_required": True, "operator_auth": True,
    }
    assert auth_route_policy("POST", proposal_path, enabled=True) == {
        "resource": "solution_lifecycle", "action": "create", "public": False,
        "location_id": LOCATION_ID, "scope_required": True, "operator_auth": True,
    }
    assert auth_route_policy("PATCH", proposal_path, enabled=True) is None


def _app(provider, monkeypatch, proposal_action):
    from services.gateway.solution_lifecycle_routes import register_solution_lifecycle_routes

    monkeypatch.setattr(reads, "list_location_solution_funding_targets", lambda *_a, **_k: {"solutions": []})
    monkeypatch.setattr(actions, "propose_location_solution_funding", proposal_action)
    app = FastAPI()
    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_solution_lifecycle_routes(router, provider, run_in_threadpool, SimpleNamespace(Error=Exception))
    app.include_router(router)
    return app


def test_funding_draft_route_returns_created_with_no_store(monkeypatch):
    app = _app(object(), monkeypatch, lambda *_args, **_kwargs: RESULT)

    @app.middleware("http")
    async def operator_context(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    path = f"/operator/api/solution-lifecycle/{LOCATION_ID}/solutions/{SOLUTION_ID}/funding"
    with TestClient(app) as client:
        response = client.post(path, json=BODY)
    assert response.status_code == 201
    assert response.json() == RESULT
    assert response.headers["cache-control"] == "no-store"


def test_funding_proposal_tenant_denial_maps_to_forbidden(monkeypatch):
    app = _app(
        object(), monkeypatch,
        lambda *_a, **_k: (_ for _ in ()).throw(TenantContextDenied("denied")),
    )

    @app.middleware("http")
    async def operator_context(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    path = f"/operator/api/solution-lifecycle/{LOCATION_ID}/solutions/{SOLUTION_ID}/funding"
    with TestClient(app) as client:
        response = client.post(path, json=BODY)
    assert response.status_code == 403
    assert response.headers["cache-control"] == "no-store"
