"""Tests for draft-only, location-scoped solution replication proposals."""

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
RESULT = {
    "event_id": str(uuid4()),
    "replication_id": str(uuid4()),
    "replication_status": "proposed",
    "created_at": "2026-10-20T12:00:00+00:00",
    "replayed": False,
}
PAYLOAD = {
    "request_id": REQUEST_ID,
    "source_experiment_id": EXPERIMENT_ID,
    "target_context": "A synthetic target context",
    "adaptation_required": "A bounded local adaptation",
    "replication_protocol": {"steps": ["prepare", "observe"]},
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
        if self.connection.fail_query and "propose_location_solution_replication" in query:
            raise RuntimeError("database replication proposal failed")

    def fetchone(self):
        return tuple(RESULT.values())


def test_replication_proposal_sets_exact_create_context_and_commits_receipt():
    connection = _Connection()
    contexts = []
    protocol = {"steps": ["prepare", "observe"]}

    def set_context(conn, **kwargs):
        assert conn is connection
        contexts.append(kwargs)

    with patch.object(actions, "set_operator_tenant_context", set_context):
        result = actions.propose_location_solution_replication(
            OPERATOR_ID,
            LOCATION_ID,
            EXPERIMENT_ID,
            REQUEST_ID,
            PAYLOAD["target_context"],
            PAYLOAD["adaptation_required"],
            protocol,
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
    query, params = connection.operations[-1]
    assert "kokonut_security.propose_location_solution_replication" in query
    assert params == (
        LOCATION_ID,
        EXPERIMENT_ID,
        REQUEST_ID,
        PAYLOAD["target_context"],
        PAYLOAD["adaptation_required"],
        '{"steps":["prepare","observe"]}',
    )
    assert result == RESULT
    assert connection.committed and connection.closed and not connection.rolled_back


@pytest.mark.parametrize(
    ("target_context", "adaptation", "protocol"),
    [
        (" ", None, {}),
        ("x" * 2001, None, {}),
        ("context", " ", {}),
        ("context", "x" * 4001, {}),
        ("context", None, []),
        ("context", None, {"nonfinite": float("nan")}),
        ("context", None, {"large": "x" * 65536}),
    ],
)
def test_invalid_replication_proposal_fails_before_database_access(
    target_context, adaptation, protocol
):
    with pytest.raises(actions.SolutionLifecycleActionInvalid):
        actions.propose_location_solution_replication(
            OPERATOR_ID,
            LOCATION_ID,
            EXPERIMENT_ID,
            REQUEST_ID,
            target_context,
            adaptation,
            protocol,
            connection_factory=lambda: pytest.fail("invalid proposal must fail before DB access"),
        )


def test_replication_proposal_action_failure_rolls_back_and_closes_connection():
    connection = _Connection(fail_query=True)
    with patch.object(actions, "set_operator_tenant_context", lambda *_args, **_kwargs: None):
        with pytest.raises(RuntimeError, match="database replication proposal failed"):
            actions.propose_location_solution_replication(
                OPERATOR_ID,
                LOCATION_ID,
                EXPERIMENT_ID,
                REQUEST_ID,
                PAYLOAD["target_context"],
                PAYLOAD["adaptation_required"],
                PAYLOAD["replication_protocol"],
                connection_factory=lambda: connection,
            )
    assert connection.rolled_back and connection.closed and not connection.committed


def test_replication_proposal_route_policy_requires_exact_create_grant():
    path = f"/operator/api/solution-lifecycle/{LOCATION_ID}/replications"
    assert auth_route_policy("POST", path, enabled=True) == {
        "resource": "solution_lifecycle",
        "action": "create",
        "public": False,
        "location_id": LOCATION_ID,
        "scope_required": True,
        "operator_auth": True,
    }
    assert auth_route_policy("GET", path, enabled=True)["action"] == "read"
    assert auth_route_policy("POST", path + "/extra", enabled=True) is None


def _replication_app(monkeypatch, provider=object(), action=None):
    from services.gateway.solution_lifecycle_routes import register_solution_lifecycle_routes

    if action is not None:
        monkeypatch.setattr(actions, "propose_location_solution_replication", action)
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


def test_replication_proposal_route_is_no_store_and_rejects_unknown_fields(monkeypatch):
    calls = []

    def propose(*args, **kwargs):
        calls.append((args, kwargs))
        return RESULT

    app = _replication_app(monkeypatch, action=propose)
    path = f"/operator/api/solution-lifecycle/{LOCATION_ID}/replications"
    with TestClient(app) as client:
        response = client.post(path, json=PAYLOAD)
        invalid = client.post(path, json={**PAYLOAD, "status": "approved"})

    assert response.status_code == 201
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert response.json() == RESULT
    assert len(calls) == 1
    assert calls[0][0] == (
        OPERATOR_ID,
        LOCATION_ID,
        EXPERIMENT_ID,
        REQUEST_ID,
        PAYLOAD["target_context"],
        PAYLOAD["adaptation_required"],
        PAYLOAD["replication_protocol"],
    )
    assert calls[0][1] == {}
    assert invalid.status_code == 400


def test_replication_proposal_route_fails_closed_without_oidc(monkeypatch):
    app = _replication_app(
        monkeypatch,
        provider=None,
        action=lambda *_args, **_kwargs: pytest.fail("OIDC-disabled route must not call action"),
    )
    path = f"/operator/api/solution-lifecycle/{LOCATION_ID}/replications"
    with TestClient(app) as client:
        response = client.post(path, json=PAYLOAD)
    assert response.status_code == 404
    assert response.headers["cache-control"] == "no-store"


def test_replication_proposal_route_maps_tenant_denial_to_forbidden(monkeypatch):
    def deny(*_args, **_kwargs):
        raise TenantContextDenied("denied")

    app = _replication_app(monkeypatch, action=deny)
    path = f"/operator/api/solution-lifecycle/{LOCATION_ID}/replications"
    with TestClient(app) as client:
        response = client.post(path, json=PAYLOAD)
    assert response.status_code == 403
    assert response.headers["cache-control"] == "no-store"
