"""Tests for attributed, location-scoped solution gate evaluations."""

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
GATE_ID = str(uuid4())
REQUEST_ID = str(uuid4())
OBSERVED = {"validated_experiments": 2}
EVIDENCE = [{"source": "reviewed-field-record"}]
RESULT = {
    "evaluation_id": str(uuid4()),
    "gate_id": GATE_ID,
    "passed": True,
    "evaluated_at": "2026-10-20T12:00:00+00:00",
    "replayed": False,
}
PAYLOAD = {
    "request_id": REQUEST_ID,
    "passed": True,
    "observed": OBSERVED,
    "evidence": EVIDENCE,
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
        self.description = tuple(SimpleNamespace(name=name) for name in RESULT)

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def execute(self, query, params=None):
        self.connection.operations.append((" ".join(query.split()), params))
        if self.connection.fail_query and "record_location_solution_gate_evaluation" in query:
            raise RuntimeError("database gate evaluation failed")

    def fetchone(self):
        return tuple(RESULT.values())


def test_gate_evaluation_sets_exact_create_context_and_commits_idempotent_result():
    connection = _Connection()
    contexts = []

    def set_context(conn, **kwargs):
        assert conn is connection
        contexts.append(kwargs)

    with patch.object(actions, "set_operator_tenant_context", set_context):
        result = actions.record_location_solution_gate_evaluation(
            OPERATOR_ID, LOCATION_ID, GATE_ID, REQUEST_ID, True,
            OBSERVED, EVIDENCE, connection_factory=lambda: connection,
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
    query, params = connection.operations[-1]
    assert "kokonut_security.record_location_solution_gate_evaluation" in query
    assert params == (
        LOCATION_ID, GATE_ID, REQUEST_ID, True,
        '{"validated_experiments":2}', '[{"source":"reviewed-field-record"}]',
    )
    assert result == RESULT
    assert connection.committed and connection.closed and not connection.rolled_back


@pytest.mark.parametrize(
    ("passed", "observed", "evidence"),
    [
        (1, OBSERVED, EVIDENCE),
        (True, [], EVIDENCE),
        (True, OBSERVED, []),
        (True, OBSERVED, [float("nan")]),
        (True, {"value": float("inf")}, EVIDENCE),
        (True, OBSERVED, ["x" * 70000]),
        (True, {"value": "x" * 70000}, EVIDENCE),
    ],
)
def test_invalid_gate_evaluation_fails_before_database_access(passed, observed, evidence):
    with pytest.raises(actions.SolutionLifecycleActionInvalid):
        actions.record_location_solution_gate_evaluation(
            OPERATOR_ID, LOCATION_ID, GATE_ID, REQUEST_ID, passed,
            observed, evidence,
            connection_factory=lambda: pytest.fail("invalid evaluation must fail before DB access"),
        )


def test_gate_evaluation_action_failure_rolls_back_and_closes_connection():
    connection = _Connection(fail_query=True)
    with patch.object(actions, "set_operator_tenant_context", lambda *_args, **_kwargs: None):
        with pytest.raises(RuntimeError, match="database gate evaluation failed"):
            actions.record_location_solution_gate_evaluation(
                OPERATOR_ID, LOCATION_ID, GATE_ID, REQUEST_ID, True,
                OBSERVED, EVIDENCE, connection_factory=lambda: connection,
            )
    assert connection.rolled_back and connection.closed and not connection.committed


def test_gate_evaluation_route_policy_requires_exact_create_grant():
    path = f"/operator/api/solution-lifecycle/{LOCATION_ID}/gates/{GATE_ID}/evaluations"
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


def _route_app(provider, monkeypatch, action):
    from services.gateway.solution_lifecycle_routes import register_solution_lifecycle_routes

    monkeypatch.setattr(actions, "record_location_solution_gate_evaluation", action)
    app = FastAPI()
    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_solution_lifecycle_routes(
        router, provider, run_in_threadpool, SimpleNamespace(Error=Exception)
    )
    app.include_router(router)

    @app.middleware("http")
    async def add_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    return app


def test_gate_evaluation_route_is_no_store_and_rejects_extra_fields(monkeypatch):
    calls = []

    def evaluate(*args, **kwargs):
        calls.append((args, kwargs))
        return RESULT

    app = _route_app(object(), monkeypatch, evaluate)
    path = f"/operator/api/solution-lifecycle/{LOCATION_ID}/gates/{GATE_ID}/evaluations"
    with TestClient(app) as client:
        response = client.post(path, json=PAYLOAD)
        invalid = client.post(path, json={**PAYLOAD, "status": "approved"})

    assert response.status_code == 201
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert response.json() == RESULT
    assert len(calls) == 1
    assert calls[0][0] == (
        OPERATOR_ID, LOCATION_ID, GATE_ID, REQUEST_ID,
        True, OBSERVED, EVIDENCE,
    )
    assert invalid.status_code == 400


def test_gate_evaluation_retry_route_returns_success_without_duplicate_status(monkeypatch):
    result = {**RESULT, "replayed": True}
    app = _route_app(object(), monkeypatch, lambda *_args, **_kwargs: result)
    path = f"/operator/api/solution-lifecycle/{LOCATION_ID}/gates/{GATE_ID}/evaluations"
    with TestClient(app) as client:
        response = client.post(path, json=PAYLOAD)
    assert response.status_code == 200
    assert response.json()["replayed"] is True


def test_gate_evaluation_route_fails_closed_without_oidc(monkeypatch):
    app = _route_app(
        None, monkeypatch,
        lambda *_args, **_kwargs: pytest.fail("OIDC-disabled evaluation must not call action"),
    )
    path = f"/operator/api/solution-lifecycle/{LOCATION_ID}/gates/{GATE_ID}/evaluations"
    with TestClient(app) as client:
        response = client.post(path, json=PAYLOAD)
    assert response.status_code == 404
    assert response.headers["cache-control"] == "no-store"


def test_gate_evaluation_route_maps_tenant_denial_to_forbidden(monkeypatch):
    app = _route_app(
        object(), monkeypatch,
        lambda *_args, **_kwargs: (_ for _ in ()).throw(TenantContextDenied("denied")),
    )
    path = f"/operator/api/solution-lifecycle/{LOCATION_ID}/gates/{GATE_ID}/evaluations"
    with TestClient(app) as client:
        response = client.post(path, json=PAYLOAD)
    assert response.status_code == 403
    assert response.headers["cache-control"] == "no-store"
