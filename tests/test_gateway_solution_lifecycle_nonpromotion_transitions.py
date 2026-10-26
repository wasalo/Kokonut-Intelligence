"""Tests for exact-location non-promotion solution stage transitions."""

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
TRANSITION = {
    "lifecycle_event_id": str(uuid4()),
    "solution_id": SOLUTION_ID,
    "from_stage": "testing",
    "to_stage": "pilot_active",
    "solution_status": "active",
    "transitioned_at": "2026-10-20T12:00:00+00:00",
    "replayed": False,
}


class _Connection:
    def __init__(self, row=None, rows=None, columns=()):
        self.row = row
        self.rows = rows or []
        self.operations = []
        self.committed = False
        self.rolled_back = False
        self.closed = False
        self.columns = columns

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
        names = tuple(connection.row or {})
        if not names:
            names = connection.columns
        self.description = tuple(SimpleNamespace(name=name) for name in names)

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
        return self.connection.rows


def test_action_sets_exact_transition_context_and_commits_receipt():
    connection = _Connection(TRANSITION)
    contexts = []

    def set_context(conn, **kwargs):
        assert conn is connection
        contexts.append(kwargs)

    with patch.object(actions, "set_operator_tenant_context", set_context):
        result = actions.transition_location_solution_stage(
            OPERATOR_ID, LOCATION_ID, SOLUTION_ID, "testing", "pilot_active",
            REQUEST_ID, "Field evidence supports the pilot stage", [{"uri": "evidence:1"}],
            "Return to testing if safety or efficacy regresses", True,
            connection_factory=lambda: connection,
        )

    assert contexts == [{
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "solution_lifecycle",
        "action": "transition",
    }]
    query, params = connection.operations[-1]
    assert "kokonut_security.transition_location_solution_stage" in query
    assert params == (
        LOCATION_ID, SOLUTION_ID, "testing", "pilot_active", REQUEST_ID,
        "Field evidence supports the pilot stage", '[{"uri":"evidence:1"}]',
        "Return to testing if safety or efficacy regresses", True,
    )
    assert result == TRANSITION
    assert connection.committed and connection.closed and not connection.rolled_back


@pytest.mark.parametrize(
    ("from_stage", "to_stage", "acknowledged", "rationale", "evidence", "rollback"),
    [
        ("unknown", "pilot_active", True, "Valid rationale text", [{"uri": "x"}], None),
        ("testing", "validated", True, "Valid rationale text", [{"uri": "x"}], None),
        ("testing", "retired", True, "Valid rationale text", [{"uri": "x"}], None),
        ("testing", "superseded", True, "Valid rationale text", [{"uri": "x"}], None),
        ("testing", "testing", True, "Valid rationale text", [{"uri": "x"}], None),
        ("testing", "pilot_active", False, "Valid rationale text", [{"uri": "x"}], None),
        ("testing", "pilot_active", True, "short", [{"uri": "x"}], None),
        ("testing", "pilot_active", True, "Valid rationale text", [], None),
        ("testing", "pilot_active", True, "Valid rationale text", [float("nan")], None),
        ("testing", "pilot_active", True, "Valid rationale text", [{"uri": "x"}], "x" * 4001),
        ("testing", "pilot_active", True, "Valid rationale text", ["x" * 65537], None),
    ],
)
def test_invalid_transition_fails_before_database(
    from_stage, to_stage, acknowledged, rationale, evidence, rollback
):
    with pytest.raises(actions.SolutionLifecycleActionInvalid):
        actions.transition_location_solution_stage(
            OPERATOR_ID, LOCATION_ID, SOLUTION_ID, from_stage, to_stage, REQUEST_ID,
            rationale, evidence, rollback, acknowledged,
            connection_factory=lambda: pytest.fail("invalid transition opened a DB connection"),
        )


def test_transition_failure_rolls_back_and_closes_connection():
    connection = _Connection(TRANSITION)

    def fail(*_args, **_kwargs):
        raise RuntimeError("synthetic transition failure")

    with patch.object(actions, "set_operator_tenant_context", fail):
        with pytest.raises(RuntimeError, match="synthetic transition failure"):
            actions.transition_location_solution_stage(
                OPERATOR_ID, LOCATION_ID, SOLUTION_ID, "testing", "pilot_active",
                REQUEST_ID, "Field evidence supports the pilot stage", [{"uri": "evidence:1"}],
                acknowledged=True, connection_factory=lambda: connection,
            )
    assert connection.rolled_back and connection.closed and not connection.committed


def test_target_read_sets_read_context_paginates_and_closes_transaction():
    columns = (
        "solution_id", "solution_name", "solution_type", "current_stage",
        "solution_status", "updated_at",
    )
    row = (SOLUTION_ID, "Soil cover", "practice", "testing", "active", "2026-10-20T00:00:00Z")
    connection = _Connection(rows=[row, row, row], columns=columns)
    contexts = []

    def set_context(conn, **kwargs):
        assert conn is connection
        contexts.append(kwargs)

    with patch.object(reads, "set_operator_tenant_context", set_context):
        result = reads.list_location_solution_stage_transition_targets(
            OPERATOR_ID, LOCATION_ID, limit="2", offset="5",
            connection_factory=lambda: connection,
        )

    assert contexts == [{
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "solution_lifecycle",
        "action": "read",
    }]
    assert connection.operations[-1] == (
        "SELECT * FROM kokonut_security.list_location_solution_stage_transition_targets( %s::uuid, %s::integer, %s::integer )",
        (LOCATION_ID, 3, 5),
    )
    assert len(result["solutions"]) == 2
    assert result["has_more"] is True and result["next_offset"] == 7
    assert connection.rolled_back and connection.closed


@pytest.mark.parametrize("limit,offset", [(0, 0), (51, 0), (2, -1), (2, 10001)])
def test_target_read_rejects_invalid_page_before_database(limit, offset):
    with pytest.raises(reads.SolutionLifecycleReadInvalid):
        reads.list_location_solution_stage_transition_targets(
            OPERATOR_ID, LOCATION_ID, limit=limit, offset=offset,
            connection_factory=lambda: pytest.fail("invalid page opened a DB connection"),
        )


def test_target_read_context_denial_does_not_call_projection():
    connection = _Connection()

    def deny(*_args, **_kwargs):
        raise TenantContextDenied("missing location read grant")

    with patch.object(reads, "set_operator_tenant_context", deny):
        with pytest.raises(TenantContextDenied):
            reads.list_location_solution_stage_transition_targets(
                OPERATOR_ID, LOCATION_ID, connection_factory=lambda: connection
            )
    assert not any("list_location_solution_stage_transition_targets" in query
                   for query, _params in connection.operations)
    assert connection.rolled_back and connection.closed


def test_route_policy_has_only_exact_scoped_read_and_transition_actions():
    read_path = f"/operator/api/solution-lifecycle/{LOCATION_ID}/stage-transition-targets"
    write_path = f"/operator/api/solution-lifecycle/{LOCATION_ID}/solutions/{SOLUTION_ID}/stage-transition"
    assert auth_route_policy("GET", read_path, enabled=True) == {
        "resource": "solution_lifecycle", "action": "read", "public": False,
        "location_id": LOCATION_ID, "scope_required": True, "operator_auth": True,
    }
    assert auth_route_policy("POST", write_path, enabled=True) == {
        "resource": "solution_lifecycle", "action": "transition", "public": False,
        "location_id": LOCATION_ID, "scope_required": True, "operator_auth": True,
    }
    assert auth_route_policy("GET", write_path, enabled=True) is None
    assert auth_route_policy("POST", read_path, enabled=True) is None


def test_transition_route_requires_exact_payload_and_returns_no_store(monkeypatch):
    from services.gateway.solution_lifecycle_routes import register_solution_lifecycle_routes

    calls = []

    def transition_action(*args):
        calls.append(args)
        return TRANSITION

    monkeypatch.setattr(actions, "transition_location_solution_stage", transition_action)
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

    path = f"/operator/api/solution-lifecycle/{LOCATION_ID}/solutions/{SOLUTION_ID}/stage-transition"
    body = {
        "request_id": REQUEST_ID,
        "expected_from_stage": "testing",
        "to_stage": "pilot_active",
        "rationale": "Field evidence supports the pilot stage",
        "evidence": [{"uri": "evidence:1"}],
        "rollback_plan": None,
        "acknowledged": True,
    }
    with TestClient(app) as client:
        response = client.post(path, json=body)
        invalid = client.post(path, json={**body, "approved_by": "operator"})
    assert response.status_code == 201
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == TRANSITION
    assert invalid.status_code == 400
    assert len(calls) == 1 and calls[0][1:] == (
        LOCATION_ID, SOLUTION_ID, "testing", "pilot_active", REQUEST_ID,
        body["rationale"], body["evidence"], None, True,
    )


def test_target_read_route_is_no_store_and_scoped(monkeypatch):
    from services.gateway.solution_lifecycle_routes import register_solution_lifecycle_routes

    calls = []
    expected = {"location_id": LOCATION_ID, "offset": 0, "solutions": [], "has_more": False, "next_offset": None}

    def target_reader(*args, **kwargs):
        calls.append((args, kwargs))
        return expected

    monkeypatch.setattr(reads, "list_location_solution_stage_transition_targets", target_reader)
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

    with TestClient(app) as client:
        response = client.get(
            f"/operator/api/solution-lifecycle/{LOCATION_ID}/stage-transition-targets?limit=10&offset=2"
        )
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == expected
    assert calls == [((OPERATOR_ID, LOCATION_ID), {"limit": "10", "offset": "2"})]
