"""Tests for location-scoped solution retirement proposals."""

from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest

from services.common.tenant_context import TenantContextDenied
from services.gateway import solution_lifecycle_actions as actions
from services.gateway.operator_auth import auth_route_policy

pytest.importorskip("fastapi")
from fastapi import APIRouter, FastAPI  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

OPERATOR_ID = str(uuid4())
LOCATION_ID = str(uuid4())
SOLUTION_ID = str(uuid4())
REQUEST_ID = str(uuid4())
EVIDENCE = [{"source": "review"}]
PROPOSAL = {
    "event_id": str(uuid4()),
    "retirement_id": str(uuid4()),
    "retirement_status": "proposed",
    "created_at": "2026-10-19T12:00:00+00:00",
    "replayed": False,
}
PAYLOAD = {
    "request_id": REQUEST_ID,
    "retirement_type": "unsafe",
    "trigger_reason": "A private trigger reason",
    "evidence_refs": EVIDENCE,
    "migration_plan": "A private migration plan",
}


class _Connection:
    def __init__(self, *, fail_query=False):
        self.fail_query = fail_query
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
        self.description = tuple(SimpleNamespace(name=name) for name in PROPOSAL)

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def execute(self, query, params=None):
        self.connection.operations.append((" ".join(query.split()), params))
        if self.connection.fail_query and "propose_location_solution_retirement" in query:
            raise RuntimeError("database proposal failed")

    def fetchone(self):
        return tuple(PROPOSAL.values())


def test_proposal_action_sets_exact_create_context_and_commits_receipt():
    connection = _Connection()
    contexts = []

    def set_context(conn, **kwargs):
        assert conn is connection
        contexts.append(kwargs)

    with patch.object(actions, "set_operator_tenant_context", set_context):
        result = actions.propose_location_solution_retirement(
            OPERATOR_ID, LOCATION_ID, SOLUTION_ID, REQUEST_ID, "unsafe",
            PAYLOAD["trigger_reason"], EVIDENCE, PAYLOAD["migration_plan"],
            connection_factory=lambda: connection,
        )

    assert contexts == [{
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "solution_lifecycle",
        "action": "create",
    }]
    assert connection.operations[:2] == [
        ("SET LOCAL statement_timeout = '8s'", None),
        ("SET LOCAL lock_timeout = '2s'", None),
    ]
    assert "kokonut_security.propose_location_solution_retirement" in connection.operations[-1][0]
    assert connection.operations[-1][1] == (
        LOCATION_ID, SOLUTION_ID, REQUEST_ID, "unsafe", PAYLOAD["trigger_reason"],
        '[{"source":"review"}]', PAYLOAD["migration_plan"], None,
    )
    assert result == PROPOSAL
    assert connection.committed and connection.closed and not connection.rolled_back


@pytest.mark.parametrize("retirement_type, reason, evidence, plan, replacement", [
    ("unknown", "reason", EVIDENCE, "plan", None),
    ("superseded", "reason", EVIDENCE, "plan", None),
    ("unsafe", "  ", EVIDENCE, "plan", None),
    ("unsafe", "reason", EVIDENCE, "", None),
    ("unsafe", "reason", [], "plan", None),
    ("unsafe", "reason", [float("nan")], "plan", None),
])
def test_invalid_proposal_fails_before_database_access(
    retirement_type, reason, evidence, plan, replacement
):
    with pytest.raises(actions.SolutionLifecycleActionInvalid):
        actions.propose_location_solution_retirement(
            OPERATOR_ID, LOCATION_ID, SOLUTION_ID, REQUEST_ID,
            retirement_type, reason, evidence, plan, replacement,
            connection_factory=lambda: pytest.fail("invalid proposal must fail before DB access"),
        )


def test_proposal_action_failure_rolls_back_and_closes_connection():
    connection = _Connection(fail_query=True)
    with patch.object(actions, "set_operator_tenant_context", lambda *_args, **_kwargs: None):
        with pytest.raises(RuntimeError, match="database proposal failed"):
            actions.propose_location_solution_retirement(
                OPERATOR_ID, LOCATION_ID, SOLUTION_ID, REQUEST_ID, "unsafe",
                PAYLOAD["trigger_reason"], EVIDENCE, PAYLOAD["migration_plan"],
                connection_factory=lambda: connection,
            )
    assert connection.rolled_back and connection.closed and not connection.committed


def test_proposal_route_policy_requires_exact_create_grant():
    path = (
        f"/operator/api/solution-lifecycle/{LOCATION_ID}/solutions/"
        f"{SOLUTION_ID}/retirements"
    )
    assert auth_route_policy("POST", path, enabled=True) == {
        "resource": "solution_lifecycle",
        "action": "create",
        "public": False,
        "location_id": LOCATION_ID,
        "scope_required": True,
        "operator_auth": True,
    }
    assert auth_route_policy("GET", path, enabled=True) is None
    assert auth_route_policy("POST", path + "/extra", enabled=True) is None


def test_http_proposal_route_is_no_store_and_rejects_unrecognized_fields(monkeypatch):
    from services.gateway.solution_lifecycle_routes import register_solution_lifecycle_routes

    calls = []

    def propose(*args):
        calls.append(args)
        return PROPOSAL

    monkeypatch.setattr(actions, "propose_location_solution_retirement", propose)
    app = FastAPI()
    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_solution_lifecycle_routes(router, object(), run_in_threadpool,
                                        SimpleNamespace(Error=Exception))
    app.include_router(router)

    @app.middleware("http")
    async def add_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    path = (
        f"/operator/api/solution-lifecycle/{LOCATION_ID}/solutions/"
        f"{SOLUTION_ID}/retirements"
    )
    with TestClient(app) as client:
        response = client.post(path, json=PAYLOAD)
        invalid = client.post(path, json={**PAYLOAD, "created_by_party_id": OPERATOR_ID})

    assert response.status_code == 201
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert response.json() == PROPOSAL
    assert calls == [(
        OPERATOR_ID, LOCATION_ID, SOLUTION_ID, REQUEST_ID, "unsafe",
        PAYLOAD["trigger_reason"], EVIDENCE, PAYLOAD["migration_plan"], None,
    )]
    assert invalid.status_code == 400
    assert len(calls) == 1


def test_proposal_route_fails_closed_without_oidc():
    from services.gateway.solution_lifecycle_routes import register_solution_lifecycle_routes

    app = FastAPI()
    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        pytest.fail("OIDC-disabled proposal must not call the action")

    register_solution_lifecycle_routes(router, None, run_in_threadpool,
                                        SimpleNamespace(Error=Exception))
    app.include_router(router)
    path = (
        f"/operator/api/solution-lifecycle/{LOCATION_ID}/solutions/"
        f"{SOLUTION_ID}/retirements"
    )
    with TestClient(app) as client:
        response = client.post(path, json=PAYLOAD)
    assert response.status_code == 404
    assert response.headers["cache-control"] == "no-store"


def test_proposal_route_maps_tenant_denial_to_forbidden(monkeypatch):
    from services.gateway.solution_lifecycle_routes import register_solution_lifecycle_routes

    monkeypatch.setattr(
        actions, "propose_location_solution_retirement",
        lambda *_args: (_ for _ in ()).throw(TenantContextDenied("denied")),
    )
    app = FastAPI()
    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_solution_lifecycle_routes(router, object(), run_in_threadpool,
                                        SimpleNamespace(Error=Exception))
    app.include_router(router)

    @app.middleware("http")
    async def add_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    path = (
        f"/operator/api/solution-lifecycle/{LOCATION_ID}/solutions/"
        f"{SOLUTION_ID}/retirements"
    )
    with TestClient(app) as client:
        response = client.post(path, json=PAYLOAD)
    assert response.status_code == 403
    assert response.headers["cache-control"] == "no-store"
