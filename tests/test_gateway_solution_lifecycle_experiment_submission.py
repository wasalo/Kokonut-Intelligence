"""Exact-location owner submission of experiment protocol drafts."""

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
SUBMISSION = {
    "experiment_id": EXPERIMENT_ID,
    "solution_id": str(uuid4()),
    "experiment_status": "submitted",
    "submitted_at": "2026-10-20T15:00:00+00:00",
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


def test_submission_action_sets_submit_context_and_calls_bounded_function():
    connection = _Connection(SUBMISSION)
    contexts = []

    def set_context(conn, **kwargs):
        assert conn is connection
        contexts.append(kwargs)

    with patch.object(actions, "set_operator_tenant_context", set_context):
        result = actions.submit_location_solution_experiment_protocol(
            OPERATOR_ID, LOCATION_ID, EXPERIMENT_ID, REQUEST_ID, True,
            connection_factory=lambda: connection,
        )

    assert contexts == [{
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "solution_lifecycle",
        "action": "submit",
    }]
    query, params = connection.operations[-1]
    assert "kokonut_security.submit_location_solution_experiment_protocol" in query
    assert params == (LOCATION_ID, EXPERIMENT_ID, REQUEST_ID, True)
    assert result == SUBMISSION
    assert connection.committed and connection.closed and not connection.rolled_back


def test_unacknowledged_submission_fails_before_database():
    with pytest.raises(actions.SolutionLifecycleActionInvalid, match="acknowledgement"):
        actions.submit_location_solution_experiment_protocol(
            OPERATOR_ID, LOCATION_ID, EXPERIMENT_ID, REQUEST_ID, False,
            connection_factory=lambda: pytest.fail("unacknowledged submission opened a database"),
        )


def test_submission_action_rolls_back_and_closes_on_tenant_denial():
    connection = _Connection(SUBMISSION)

    def deny(*_args, **_kwargs):
        raise TenantContextDenied("denied")

    with patch.object(actions, "set_operator_tenant_context", deny):
        with pytest.raises(TenantContextDenied):
            actions.submit_location_solution_experiment_protocol(
                OPERATOR_ID, LOCATION_ID, EXPERIMENT_ID, REQUEST_ID, True,
                connection_factory=lambda: connection,
            )
    assert connection.rolled_back and connection.closed and not connection.committed


def test_experiment_submission_route_requires_exact_submit_policy():
    path = (
        f"/operator/api/solution-lifecycle/{LOCATION_ID}/experiments/"
        f"{EXPERIMENT_ID}/submit"
    )
    assert auth_route_policy("POST", path, enabled=True) == {
        "resource": "solution_lifecycle",
        "action": "submit",
        "public": False,
        "location_id": LOCATION_ID,
        "scope_required": True,
        "operator_auth": True,
    }
    assert auth_route_policy("GET", path, enabled=True) is None
    assert auth_route_policy("POST", path, enabled=False) is None


def test_submission_route_is_strict_no_store_and_forwards_operator(monkeypatch):
    from services.gateway import solution_lifecycle_actions
    from services.gateway.solution_lifecycle_routes import register_solution_lifecycle_routes

    calls = []

    def submit(*args, **kwargs):
        calls.append((args, kwargs))
        return SUBMISSION

    monkeypatch.setattr(
        solution_lifecycle_actions,
        "submit_location_solution_experiment_protocol",
        submit,
    )
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

    path = (
        f"/operator/api/solution-lifecycle/{LOCATION_ID}/experiments/"
        f"{EXPERIMENT_ID}/submit"
    )
    with TestClient(app) as client:
        response = client.post(path, json=BODY)
        malformed = client.post(path, json={**BODY, "owner_party_id": OPERATOR_ID})

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == SUBMISSION
    assert malformed.status_code == 400
    assert calls == [((OPERATOR_ID, LOCATION_ID, EXPERIMENT_ID, REQUEST_ID, True), {})]
