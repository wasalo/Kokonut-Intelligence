"""Scoped experiment completion requires fresh terminal primary-metric analyses."""

from __future__ import annotations

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
EXPERIMENT_ID = str(uuid4())
REQUEST_ID = str(uuid4())
COMPLETION = {
    "experiment_id": EXPERIMENT_ID,
    "status": "completed",
    "completion_basis": "sequential_threshold",
    "completed_at": "2026-10-20T16:30:00+00:00",
    "replayed": False,
}
BODY = {"request_id": REQUEST_ID, "acknowledged": True}


class _Connection:
    def __init__(self, row=None):
        self.row = row
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
        self.description = tuple(
            SimpleNamespace(name=name) for name in (connection.row or {})
        )

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def execute(self, query, params=None):
        self.connection.operations.append((" ".join(query.split()), params))

    def fetchone(self):
        return tuple(self.connection.row.values()) if self.connection.row else None


def test_completion_action_sets_transition_context_and_repeatable_read():
    connection = _Connection(COMPLETION)
    contexts = []

    def set_context(conn, **kwargs):
        assert conn is connection
        contexts.append(kwargs)

    with patch.object(actions, "set_operator_tenant_context", set_context):
        result = actions.complete_location_solution_experiment(
            OPERATOR_ID, LOCATION_ID, EXPERIMENT_ID, REQUEST_ID, True,
            connection_factory=lambda: connection,
        )

    assert contexts == [{
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "solution_lifecycle",
        "action": "transition",
    }]
    assert connection.operations[0][0] == "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ"
    query, params = connection.operations[-1]
    assert "kokonut_security.complete_location_solution_experiment" in query
    assert params == (LOCATION_ID, EXPERIMENT_ID, REQUEST_ID, True)
    assert result == COMPLETION
    assert connection.committed and connection.closed and not connection.rolled_back


@pytest.mark.parametrize(
    "kwargs, message",
    [
        ({"acknowledged": False}, "acknowledgement"),
        ({"acknowledged": 1}, "acknowledgement"),
        ({"experiment_id": "bad"}, "experiment"),
        ({"request_id": "bad"}, "request"),
    ],
)
def test_invalid_completion_fails_before_database(kwargs, message):
    values = {
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "experiment_id": EXPERIMENT_ID,
        "request_id": REQUEST_ID,
        "acknowledged": True,
    }
    values.update(kwargs)
    with pytest.raises(actions.SolutionLifecycleActionInvalid, match=message):
        actions.complete_location_solution_experiment(
            **values,
            connection_factory=lambda: pytest.fail("invalid completion opened a database"),
        )


def test_completion_rolls_back_and_closes_after_tenant_denial():
    connection = _Connection(COMPLETION)

    def deny(*_args, **_kwargs):
        raise TenantContextDenied("denied")

    with patch.object(actions, "set_operator_tenant_context", deny):
        with pytest.raises(TenantContextDenied):
            actions.complete_location_solution_experiment(
                OPERATOR_ID, LOCATION_ID, EXPERIMENT_ID, REQUEST_ID, True,
                connection_factory=lambda: connection,
            )
    assert connection.rolled_back and connection.closed and not connection.committed


def test_completion_route_requires_exact_scoped_transition_policy():
    path = f"/operator/api/solution-lifecycle/{LOCATION_ID}/experiments/{EXPERIMENT_ID}/complete"
    assert auth_route_policy("POST", path, enabled=True) == {
        "resource": "solution_lifecycle",
        "action": "transition",
        "public": False,
        "location_id": LOCATION_ID,
        "scope_required": True,
        "operator_auth": True,
    }
    assert auth_route_policy("GET", path, enabled=True) is None
    assert auth_route_policy("POST", path, enabled=False) is None


def test_completion_route_is_strict_no_store_and_forwards_operator(monkeypatch):
    from services.gateway.solution_lifecycle_routes import register_solution_lifecycle_routes

    calls = []

    def complete(*args, **kwargs):
        calls.append((args, kwargs))
        return COMPLETION

    monkeypatch.setattr(actions, "complete_location_solution_experiment", complete)
    app = FastAPI()
    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_solution_lifecycle_routes(
        router, object(), run_in_threadpool, SimpleNamespace(Error=Exception)
    )
    app.include_router(router)

    @app.middleware("http")
    async def add_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    path = f"/operator/api/solution-lifecycle/{LOCATION_ID}/experiments/{EXPERIMENT_ID}/complete"
    with TestClient(app) as client:
        response = client.post(path, json=BODY)
        malformed = client.post(path, json={**BODY, "completion_basis": "benefit"})

    assert response.status_code == 201
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == COMPLETION
    assert malformed.status_code == 400
    assert calls == [((OPERATOR_ID, LOCATION_ID, EXPERIMENT_ID, REQUEST_ID, True), {})]
