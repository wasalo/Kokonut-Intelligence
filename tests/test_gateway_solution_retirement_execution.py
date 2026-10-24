"""Exact-location retirement migration, sunset, and post-review contracts."""

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
RETIREMENT_ID = str(uuid4())
REQUEST_ID = str(uuid4())
EVIDENCE = [{"source": "reviewed migration record"}]


class _Connection:
    def __init__(self, row, columns):
        self.row = row
        self.columns = columns
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
        self.description = tuple(SimpleNamespace(name=name) for name in connection.columns)

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def execute(self, query, params=None):
        self.connection.operations.append((" ".join(query.split()), params))

    def fetchone(self):
        return self.connection.row


@pytest.mark.parametrize(
    ("action", "scope_action", "effective_at"),
    [
        ("migration_started", "transition", "2031-04-05T12:30:00+02:00"),
        ("sunset", "transition", None),
        ("post_retirement_review", "review", None),
    ],
)
def test_retirement_transition_sets_exact_context_and_commits_one_receipt(
    action, scope_action, effective_at
):
    columns = (
        "event_id", "retirement_id", "action", "retirement_status",
        "solution_stage", "effective_at", "post_retirement_review_at", "replayed",
    )
    row = (str(uuid4()), RETIREMENT_ID, action, "migration", "active", effective_at, None, False)
    connection = _Connection(row, columns)
    contexts = []

    def set_context(conn, **kwargs):
        assert conn is connection
        contexts.append(kwargs)

    with patch.object(actions, "set_operator_tenant_context", set_context):
        result = actions.transition_location_solution_retirement(
            OPERATOR_ID,
            LOCATION_ID,
            RETIREMENT_ID,
            REQUEST_ID,
            action,
            "  Reviewed retirement execution evidence  ",
            EVIDENCE,
            effective_at,
            True,
            connection_factory=lambda: connection,
        )

    assert contexts == [{
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "solution_lifecycle",
        "action": scope_action,
    }]
    assert "transition_location_solution_retirement" in connection.operations[-1][0]
    assert connection.operations[-1][1] == (
        LOCATION_ID,
        RETIREMENT_ID,
        REQUEST_ID,
        action,
        "Reviewed retirement execution evidence",
        '[{"source":"reviewed migration record"}]',
        "2031-04-05T10:30:00+00:00" if action == "migration_started" else None,
    )
    assert result["action"] == action
    assert connection.committed and connection.closed and not connection.rolled_back


@pytest.mark.parametrize(
    ("action", "effective_at", "acknowledged", "evidence_refs"),
    [
        ("migration_started", "2031-04-05T12:30:00", True, EVIDENCE),
        ("migration_started", None, True, EVIDENCE),
        ("sunset", "2031-04-05T12:30:00Z", True, EVIDENCE),
        ("post_retirement_review", None, False, EVIDENCE),
        ("sunset", None, True, []),
        ("unexpected", None, True, EVIDENCE),
    ],
)
def test_invalid_retirement_transition_fails_before_opening_database(
    action, effective_at, acknowledged, evidence_refs
):
    with pytest.raises(actions.SolutionLifecycleActionInvalid):
        actions.transition_location_solution_retirement(
            OPERATOR_ID,
            LOCATION_ID,
            RETIREMENT_ID,
            REQUEST_ID,
            action,
            "Valid note for a retirement transition",
            evidence_refs,
            effective_at,
            acknowledged,
            connection_factory=lambda: pytest.fail("invalid transition opened a connection"),
        )


@pytest.mark.parametrize(
    ("route_action", "policy_action"),
    [
        ("migration", "transition"),
        ("sunset", "transition"),
        ("post-retirement-review", "review"),
    ],
)
def test_retirement_transition_routes_require_exact_location_grant(route_action, policy_action):
    path = (
        f"/operator/api/solution-lifecycle/{LOCATION_ID}/retirements/"
        f"{RETIREMENT_ID}/{route_action}"
    )
    assert auth_route_policy("POST", path, enabled=True) == {
        "resource": "solution_lifecycle",
        "action": policy_action,
        "public": False,
        "location_id": LOCATION_ID,
        "scope_required": True,
        "operator_auth": True,
    }
    assert auth_route_policy("GET", path, enabled=True) is None
    assert auth_route_policy("POST", path + "/extra", enabled=True) is None


def test_http_retirement_transition_is_no_store_and_rejects_unknown_fields(monkeypatch):
    from services.gateway.solution_lifecycle_routes import register_solution_lifecycle_routes

    calls = []
    result = {"retirement_status": "migration", "replayed": False}
    monkeypatch.setattr(
        actions,
        "transition_location_solution_retirement",
        lambda *args: calls.append(args) or result,
    )
    app = FastAPI()
    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_solution_lifecycle_routes(router, object(), run_in_threadpool, SimpleNamespace(Error=Exception))
    app.include_router(router)

    @app.middleware("http")
    async def add_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    path = (
        f"/operator/api/solution-lifecycle/{LOCATION_ID}/retirements/"
        f"{RETIREMENT_ID}/migration"
    )
    payload = {
        "request_id": REQUEST_ID,
        "note": "Reviewed migration plan and scheduled sunset.",
        "evidence_refs": EVIDENCE,
        "effective_at": "2031-04-05T12:30:00+02:00",
        "acknowledged": True,
    }
    with TestClient(app) as client:
        response = client.post(path, json=payload)
        invalid = client.post(path, json={**payload, "solution_id": RETIREMENT_ID})

    assert response.status_code == 201
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert response.json() == result
    assert calls == [(
        OPERATOR_ID,
        LOCATION_ID,
        RETIREMENT_ID,
        REQUEST_ID,
        "migration_started",
        payload["note"],
        EVIDENCE,
        payload["effective_at"],
        True,
    )]
    assert invalid.status_code == 400
    assert len(calls) == 1


def test_http_retirement_transition_maps_tenant_denial_to_forbidden(monkeypatch):
    from services.gateway.solution_lifecycle_routes import register_solution_lifecycle_routes

    monkeypatch.setattr(
        actions,
        "transition_location_solution_retirement",
        lambda *_args: (_ for _ in ()).throw(TenantContextDenied("denied")),
    )
    app = FastAPI()
    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_solution_lifecycle_routes(router, object(), run_in_threadpool, SimpleNamespace(Error=Exception))
    app.include_router(router)

    @app.middleware("http")
    async def add_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    payload = {
        "request_id": REQUEST_ID,
        "note": "Reviewed migration plan and scheduled sunset.",
        "evidence_refs": EVIDENCE,
        "effective_at": "2031-04-05T12:30:00+02:00",
        "acknowledged": True,
    }
    path = (
        f"/operator/api/solution-lifecycle/{LOCATION_ID}/retirements/"
        f"{RETIREMENT_ID}/migration"
    )
    with TestClient(app) as client:
        response = client.post(path, json=payload)
    assert response.status_code == 403
    assert response.headers["cache-control"] == "no-store"
