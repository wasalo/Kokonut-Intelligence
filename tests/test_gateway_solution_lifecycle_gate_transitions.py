"""Tests for the separately authorized CAP-035 stage transition action."""

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
TRANSITION = {
    "lifecycle_event_id": str(uuid4()),
    "solution_id": str(uuid4()),
    "gate_id": GATE_ID,
    "from_stage": "testing",
    "to_stage": "validated",
    "solution_status": "active",
    "transitioned_at": "2026-10-20T12:00:00+00:00",
    "replayed": False,
}


class _Connection:
    def __init__(self, row=None, fail=False):
        self.row = row
        self.fail = fail
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
            SimpleNamespace(name=key) for key in (connection.row or {}).keys()
        )

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def execute(self, query, params=None):
        self.connection.operations.append((" ".join(query.split()), params))
        if self.connection.fail and "transition_location_solution_gate" in query:
            raise RuntimeError("simulated transition failure")

    def fetchone(self):
        if self.connection.row is None:
            return None
        return tuple(self.connection.row.values())


def test_transition_action_sets_exact_context_then_commits_event_result():
    connection = _Connection(TRANSITION)
    contexts = []

    def set_context(conn, **kwargs):
        assert conn is connection
        contexts.append(kwargs)

    with patch.object(actions, "set_operator_tenant_context", set_context):
        result = actions.transition_location_solution_gate(
            OPERATOR_ID,
            LOCATION_ID,
            GATE_ID,
            REQUEST_ID,
            "Evidence supports validated stage",
            [{"uri": "https://evidence.invalid/field-record"}],
            "Revert to testing if outcomes regress",
            connection_factory=lambda: connection,
        )

    assert contexts == [{
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "solution_lifecycle",
        "action": "transition",
    }]
    query, params = connection.operations[-1]
    assert "kokonut_security.transition_location_solution_gate" in query
    assert params == (
        LOCATION_ID,
        GATE_ID,
        REQUEST_ID,
        "Evidence supports validated stage",
        '[{"uri":"https://evidence.invalid/field-record"}]',
        "Revert to testing if outcomes regress",
    )
    assert result == TRANSITION
    assert connection.committed and connection.closed and not connection.rolled_back


@pytest.mark.parametrize(
    ("rationale", "evidence", "rollback"),
    [
        ("short", [{"uri": "x"}], None),
        ("This is long enough", [], None),
        ("This is long enough", [float("nan")], None),
        ("This is long enough", [{"uri": "x"}], "x" * 4001),
        ("This is long enough", ["x" * 65537], None),
    ],
)
def test_invalid_transition_payload_fails_before_database(rationale, evidence, rollback):
    with pytest.raises(actions.SolutionLifecycleActionInvalid):
        actions.transition_location_solution_gate(
            OPERATOR_ID,
            LOCATION_ID,
            GATE_ID,
            REQUEST_ID,
            rationale,
            evidence,
            rollback,
            connection_factory=lambda: pytest.fail("invalid payload opened a DB connection"),
        )


def test_transition_failure_rolls_back_and_closes_connection():
    connection = _Connection(TRANSITION, fail=True)
    with patch.object(actions, "set_operator_tenant_context", lambda *_a, **_k: None):
        with pytest.raises(RuntimeError, match="simulated transition failure"):
            actions.transition_location_solution_gate(
                OPERATOR_ID, LOCATION_ID, GATE_ID, REQUEST_ID,
                "Evidence supports validated stage", [{"uri": "https://evidence.invalid/x"}],
                connection_factory=lambda: connection,
            )
    assert connection.rolled_back and connection.closed and not connection.committed


def test_transition_route_requires_exact_action_scope_and_csrf_safe_payload(monkeypatch):
    from services.gateway.solution_lifecycle_routes import register_solution_lifecycle_routes

    calls = []

    def transition_action(*args):
        calls.append(args)
        return TRANSITION

    monkeypatch.setattr(actions, "transition_location_solution_gate", transition_action)
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

    path = f"/operator/api/solution-lifecycle/{LOCATION_ID}/gates/{GATE_ID}/transition"
    body = {
        "request_id": REQUEST_ID,
        "rationale": "Evidence supports validated stage",
        "evidence": [{"uri": "https://evidence.invalid/field-record"}],
        "rollback_plan": None,
    }
    with TestClient(app) as client:
        response = client.post(path, json=body)
        invalid = client.post(path, json={**body, "approved": True})
    assert response.status_code == 201
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert response.json() == TRANSITION
    assert invalid.status_code == 400
    assert len(calls) == 1 and calls[0][1:] == (
        LOCATION_ID, GATE_ID, REQUEST_ID, body["rationale"], body["evidence"], None
    )
    assert auth_route_policy("POST", path, enabled=True) == {
        "resource": "solution_lifecycle",
        "action": "transition",
        "public": False,
        "location_id": LOCATION_ID,
        "scope_required": True,
        "operator_auth": True,
    }
    assert auth_route_policy("GET", path, enabled=True) is None


def test_transition_route_fails_closed_without_oidc_or_tenant_grant(monkeypatch):
    from services.gateway.solution_lifecycle_routes import register_solution_lifecycle_routes

    def fail_closed(*_args):
        raise TenantContextDenied("missing transition grant")

    monkeypatch.setattr(actions, "transition_location_solution_gate", fail_closed)
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

    with TestClient(app) as client:
        denied = client.post(
            f"/operator/api/solution-lifecycle/{LOCATION_ID}/gates/{GATE_ID}/transition",
            json={
                "request_id": REQUEST_ID,
                "rationale": "Evidence supports validated stage",
                "evidence": [{"uri": "https://evidence.invalid/field-record"}],
                "rollback_plan": None,
            },
        )
    assert denied.status_code == 403
    assert denied.headers["cache-control"] == "no-store"
