"""Protected exact-location activation of approved replications."""

from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest

pytest.importorskip("fastapi")
from fastapi import APIRouter, FastAPI  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

from services.common.tenant_context import TenantContextDenied
from services.gateway import solution_lifecycle_actions as actions
from services.gateway.operator_auth import auth_route_policy

OPERATOR_ID = str(uuid4())
LOCATION_ID = str(uuid4())
REPLICATION_ID = str(uuid4())
REQUEST_ID = str(uuid4())
RESULT = {
    "event_id": str(uuid4()),
    "replication_id": REPLICATION_ID,
    "replication_status": "active",
    "started_at": "2026-10-20T12:00:00+00:00",
    "replayed": False,
}


class _Connection:
    def __init__(self, row=None, *, fail=False):
        self.row = row or RESULT
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
            SimpleNamespace(name=name) for name in connection.row
        )

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def execute(self, query, params=None):
        self.connection.operations.append((" ".join(query.split()), params))
        if self.connection.fail and "activate_location_solution_replication" in query:
            raise RuntimeError("database activation failed")

    def fetchone(self):
        return tuple(self.connection.row.values())


def test_activation_sets_exact_transition_context_and_commits():
    connection = _Connection()
    contexts = []

    def set_context(conn, **kwargs):
        contexts.append((conn, kwargs))

    with patch.object(actions, "set_operator_tenant_context", set_context):
        result = actions.activate_location_solution_replication(
            OPERATOR_ID,
            LOCATION_ID,
            REPLICATION_ID,
            REQUEST_ID,
            True,
            connection_factory=lambda: connection,
        )

    assert result == RESULT
    assert contexts == [(
        connection,
        {
            "operator_id": OPERATOR_ID,
            "location_id": LOCATION_ID,
            "resource": "solution_lifecycle",
            "action": "transition",
        },
    )]
    assert "SET LOCAL statement_timeout = '8s'" in connection.operations[0][0]
    assert "SET LOCAL lock_timeout = '2s'" in connection.operations[1][0]
    query, params = connection.operations[2]
    assert "kokonut_security.activate_location_solution_replication" in query
    assert params == (LOCATION_ID, REPLICATION_ID, REQUEST_ID, True)
    assert connection.committed and connection.closed and not connection.rolled_back


@pytest.mark.parametrize(
    "operator_id, location_id, replication_id, request_id, acknowledged",
    [
        ("bad", LOCATION_ID, REPLICATION_ID, REQUEST_ID, True),
        (OPERATOR_ID, "bad", REPLICATION_ID, REQUEST_ID, True),
        (OPERATOR_ID, LOCATION_ID, "bad", REQUEST_ID, True),
        (OPERATOR_ID, LOCATION_ID, REPLICATION_ID, "bad", True),
        (OPERATOR_ID, LOCATION_ID, REPLICATION_ID, REQUEST_ID, 1),
    ],
)
def test_activation_invalid_input_fails_before_database(
    operator_id, location_id, replication_id, request_id, acknowledged
):
    with pytest.raises(actions.SolutionLifecycleActionInvalid):
        actions.activate_location_solution_replication(
            operator_id,
            location_id,
            replication_id,
            request_id,
            acknowledged,
            connection_factory=lambda: pytest.fail("database opened for invalid input"),
        )


def test_activation_database_failure_rolls_back_and_closes():
    connection = _Connection(fail=True)
    with patch.object(actions, "set_operator_tenant_context"):
        with pytest.raises(RuntimeError, match="database activation failed"):
            actions.activate_location_solution_replication(
                OPERATOR_ID,
                LOCATION_ID,
                REPLICATION_ID,
                REQUEST_ID,
                True,
                connection_factory=lambda: connection,
            )
    assert connection.rolled_back and connection.closed and not connection.committed


def test_activation_route_policy_requires_exact_transition_grant():
    path = f"/operator/api/solution-lifecycle/{LOCATION_ID}/replications/{REPLICATION_ID}/start"
    assert auth_route_policy("POST", path, enabled=True) == {
        "resource": "solution_lifecycle",
        "action": "transition",
        "public": False,
        "location_id": LOCATION_ID,
        "scope_required": True,
        "operator_auth": True,
    }
    assert auth_route_policy("GET", path, enabled=True) is None
    assert auth_route_policy("POST", path + "/extra", enabled=True) is None


def _app(monkeypatch, *, provider=object(), action=None):
    from services.gateway.solution_lifecycle_routes import register_solution_lifecycle_routes

    calls = []

    def activated(*args, **kwargs):
        calls.append((args, kwargs))
        if action:
            return action(*args, **kwargs)
        return RESULT

    monkeypatch.setattr(actions, "activate_location_solution_replication", activated)
    app = FastAPI()
    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_solution_lifecycle_routes(router, provider, run_in_threadpool, SimpleNamespace(Error=Exception))
    app.include_router(router)

    @app.middleware("http")
    async def add_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(operator=SimpleNamespace(operator_id=OPERATOR_ID))
        return await call_next(request)

    return app, calls


def test_activation_route_is_no_store_and_accepts_only_acknowledged_request(monkeypatch):
    app, calls = _app(monkeypatch)
    path = f"/operator/api/solution-lifecycle/{LOCATION_ID}/replications/{REPLICATION_ID}/start"
    with TestClient(app) as client:
        started = client.post(path, json={"request_id": REQUEST_ID, "acknowledged": True})
        invalid = client.post(path, json={"request_id": REQUEST_ID, "acknowledged": True, "result": "successful"})
    assert started.status_code == 201 and started.json() == RESULT
    assert invalid.status_code == 400
    assert started.headers["cache-control"] == "no-store"
    assert started.headers["vary"] == "Cookie"
    assert calls == [((OPERATOR_ID, LOCATION_ID, REPLICATION_ID, REQUEST_ID, True), {})]


def test_activation_route_fails_closed_when_oidc_disabled_or_tenant_denied(monkeypatch):
    path = f"/operator/api/solution-lifecycle/{LOCATION_ID}/replications/{REPLICATION_ID}/start"
    app, _ = _app(monkeypatch, provider=None)
    with TestClient(app) as client:
        disabled = client.post(path, json={"request_id": REQUEST_ID, "acknowledged": True})
    assert disabled.status_code == 404 and disabled.headers["cache-control"] == "no-store"

    def deny(*_args, **_kwargs):
        raise TenantContextDenied("denied")

    app, _ = _app(monkeypatch, action=deny)
    with TestClient(app) as client:
        denied = client.post(path, json={"request_id": REQUEST_ID, "acknowledged": True})
    assert denied.status_code == 403 and denied.headers["cache-control"] == "no-store"
