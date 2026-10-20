"""Linked revision workflow for independently redesigned adoption programs."""

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
PROGRAM_ID = str(uuid4())
REVISION_ID = str(uuid4())
REQUEST_ID = str(uuid4())
PROGRAM = {
    "program_id": PROGRAM_ID,
    "solution_id": str(uuid4()),
    "solution_name": "Synthetic solution",
    "adoption_pathway": "Original pathway",
    "local_adaptation_policy": "Keep safeguards",
    "next_revision_number": 2,
    "reviewed_at": "2026-10-20T12:00:00+00:00",
}
REVISED = {
    "program_id": REVISION_ID,
    "prior_program_id": PROGRAM_ID,
    "solution_id": PROGRAM["solution_id"],
    "revision_number": 2,
    "program_status": "draft",
    "created_at": "2026-10-20T12:00:00+00:00",
    "replayed": False,
}


class _Column(tuple):
    @property
    def name(self):
        return self[0]


class _Connection:
    def __init__(self, rows=None, result=None):
        self.rows = rows or []
        self.result = result or REVISED
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
        self.result = connection.result
        self.description = tuple(_Column((name,)) for name in self.result)

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def execute(self, query, params=None):
        normalized = " ".join(query.split())
        self.connection.operations.append((normalized, params))
        if "location_solution_adoption_program_redesigns" in normalized:
            self.description = tuple(_Column((name,)) for name in PROGRAM)
        elif "revise_location_solution_adoption_program" in normalized:
            self.description = tuple(_Column((name,)) for name in self.connection.result)

    def fetchone(self):
        return tuple(self.connection.result.values())

    def fetchall(self):
        return self.connection.rows


def test_redesign_list_uses_create_context_bounded_lookahead_and_safe_mapping():
    connection = _Connection(rows=[tuple(PROGRAM.values()), tuple(PROGRAM.values())])
    contexts = []
    with patch.object(actions, "set_operator_tenant_context", lambda conn, **kwargs: contexts.append(kwargs)):
        result = actions.list_location_solution_adoption_program_redesigns(
            OPERATOR_ID, LOCATION_ID, limit=1, offset=25,
            connection_factory=lambda: connection,
        )

    assert contexts == [{
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "solution_lifecycle",
        "action": "create",
    }]
    query, params = connection.operations[-1]
    assert "location_solution_adoption_program_redesigns" in query
    assert params == (LOCATION_ID, 1, 25)
    assert result == {"programs": [PROGRAM], "next_offset": 26, "has_more": True}
    assert connection.committed and connection.closed and not connection.rolled_back


@pytest.mark.parametrize("limit,offset", [(0, 0), (51, 0), (25, -1), (25, 10001), (True, 0)])
def test_redesign_list_invalid_page_fails_before_database_access(limit, offset):
    with pytest.raises(actions.SolutionLifecycleActionInvalid):
        actions.list_location_solution_adoption_program_redesigns(
            OPERATOR_ID, LOCATION_ID, limit=limit, offset=offset,
            connection_factory=lambda: pytest.fail("invalid page must fail before DB access"),
        )


def test_revision_uses_exact_create_context_and_records_retryable_function_call():
    connection = _Connection(result=REVISED)
    contexts = []
    with patch.object(actions, "set_operator_tenant_context", lambda conn, **kwargs: contexts.append(kwargs)):
        result = actions.revise_location_solution_adoption_program(
            OPERATOR_ID, LOCATION_ID, PROGRAM_ID, REQUEST_ID,
            "  Revised pathway  ",
            local_adaptation_policy="  Keep safeguards  ",
            acknowledged=True,
            connection_factory=lambda: connection,
        )

    assert contexts[0]["action"] == "create" and contexts[0]["location_id"] == LOCATION_ID
    query, params = connection.operations[-1]
    assert "revise_location_solution_adoption_program" in query
    assert params == (LOCATION_ID, PROGRAM_ID, REQUEST_ID, "Revised pathway", "Keep safeguards", True)
    assert result == REVISED
    assert connection.committed and connection.closed and not connection.rolled_back


@pytest.mark.parametrize("changes", [
    {"adoption_pathway": " "},
    {"adoption_pathway": "x" * 2001},
    {"local_adaptation_policy": "x" * 4001},
    {"acknowledged": False},
])
def test_revision_invalid_payload_fails_before_database_access(changes):
    payload = {
        "adoption_pathway": "A replacement pathway",
        "local_adaptation_policy": None,
        "acknowledged": True,
    }
    payload.update(changes)
    with pytest.raises(actions.SolutionLifecycleActionInvalid):
        actions.revise_location_solution_adoption_program(
            OPERATOR_ID, LOCATION_ID, PROGRAM_ID, REQUEST_ID,
            payload["adoption_pathway"],
            local_adaptation_policy=payload["local_adaptation_policy"],
            acknowledged=payload["acknowledged"],
            connection_factory=lambda: pytest.fail("invalid revision must fail before DB access"),
        )


def test_revision_rolls_back_and_closes_on_database_failure():
    class FailingConnection(_Connection):
        def cursor(self):
            cursor = super().cursor()
            cursor.execute = lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("revision failed"))
            return cursor

    connection = FailingConnection()
    with patch.object(actions, "set_operator_tenant_context", lambda *_args, **_kwargs: None):
        with pytest.raises(RuntimeError, match="revision failed"):
            actions.revise_location_solution_adoption_program(
                OPERATOR_ID, LOCATION_ID, PROGRAM_ID, REQUEST_ID,
                "Revised pathway", acknowledged=True,
                connection_factory=lambda: connection,
            )
    assert connection.rolled_back and connection.closed and not connection.committed


def test_revision_routes_require_exact_create_grants_and_leave_unknown_paths_protected():
    expected = {
        ("GET", f"/operator/api/solution-lifecycle/{LOCATION_ID}/adoption/programs/redesigns"),
        ("POST", f"/operator/api/solution-lifecycle/{LOCATION_ID}/adoption/programs/{PROGRAM_ID}/revise"),
    }
    for method, path in expected:
        assert auth_route_policy(method, path, enabled=True) == {
            "resource": "solution_lifecycle", "action": "create", "public": False,
            "location_id": LOCATION_ID, "scope_required": True, "operator_auth": True,
        }
    assert auth_route_policy(
        "POST", f"/operator/api/solution-lifecycle/{LOCATION_ID}/adoption/programs/{PROGRAM_ID}/unknown",
        enabled=True,
    ) is None


def test_revision_http_routes_enforce_allowlist_and_tenant_denial(monkeypatch):
    from services.gateway.solution_lifecycle_routes import register_solution_lifecycle_routes

    calls = []
    monkeypatch.setattr(
        actions, "list_location_solution_adoption_program_redesigns",
        lambda *args, **kwargs: {"programs": [PROGRAM], "next_offset": 1, "has_more": False},
    )
    monkeypatch.setattr(
        actions, "revise_location_solution_adoption_program",
        lambda *args, **kwargs: calls.append((args, kwargs)) or REVISED,
    )
    app = FastAPI()
    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_solution_lifecycle_routes(router, object(), run_in_threadpool, SimpleNamespace(Error=Exception))
    app.include_router(router)

    @app.middleware("http")
    async def add_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(operator=SimpleNamespace(operator_id=OPERATOR_ID))
        return await call_next(request)

    list_path = f"/operator/api/solution-lifecycle/{LOCATION_ID}/adoption/programs/redesigns"
    revise_path = f"/operator/api/solution-lifecycle/{LOCATION_ID}/adoption/programs/{PROGRAM_ID}/revise"
    with TestClient(app) as client:
        listed = client.get(list_path)
        revised = client.post(revise_path, json={
            "request_id": REQUEST_ID,
            "adoption_pathway": "Revised pathway",
            "local_adaptation_policy": "Keep safeguards",
            "acknowledged": True,
        })
        invalid = client.post(revise_path, json={
            "request_id": REQUEST_ID, "adoption_pathway": "Revised pathway",
            "acknowledged": True, "program_status": "launch",
        })
    assert listed.status_code == 200 and listed.headers["cache-control"] == "no-store"
    assert listed.json()["programs"] == [PROGRAM]
    assert revised.status_code == 201 and revised.json() == REVISED
    assert revised.headers["cache-control"] == "no-store" and len(calls) == 1
    assert invalid.status_code == 400 and len(calls) == 1

    monkeypatch.setattr(
        actions, "revise_location_solution_adoption_program",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(TenantContextDenied("denied")),
    )
    denied_app = FastAPI()
    denied_router = APIRouter()
    register_solution_lifecycle_routes(
        denied_router, object(), run_in_threadpool, SimpleNamespace(Error=Exception)
    )
    denied_app.include_router(denied_router)

    @denied_app.middleware("http")
    async def add_denied_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(operator=SimpleNamespace(operator_id=OPERATOR_ID))
        return await call_next(request)

    with TestClient(denied_app) as client:
        denied = client.post(revise_path, json={
            "request_id": REQUEST_ID, "adoption_pathway": "Revised pathway",
            "acknowledged": True,
        })
    assert denied.status_code == 403
