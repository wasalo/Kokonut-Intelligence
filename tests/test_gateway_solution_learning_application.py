"""Tests for the scoped accepted-learning application boundary."""

from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest

pytest.importorskip("fastapi")
from fastapi import APIRouter, FastAPI  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

from services.common.tenant_context import TenantContextDenied
from services.gateway import solution_lifecycle_actions as actions
from services.gateway import solution_lifecycle_reads as reads
from services.gateway.operator_auth import auth_route_policy

OPERATOR_ID = str(uuid4())
LOCATION_ID = str(uuid4())
LEARNING_ID = str(uuid4())
REQUEST_ID = str(uuid4())
APPLICATION = {
    "application_id": str(uuid4()),
    "learning_record_id": LEARNING_ID,
    "decision_status": "applied",
    "applied_to_version": "handbook-v2",
    "applied_by_party_id": str(uuid4()),
    "applied_at": "2026-10-20T14:00:00+00:00",
    "replayed": False,
}
ITEM = {
    "learning_record_id": LEARNING_ID,
    "solution_name": "Synthetic solution",
    "solution_type": "practice",
    "lesson_type": "context_transfer",
    "finding": "Local training improved participation.",
    "recommended_action": "Adapt the training calendar.",
    "confidence": "high",
    "transferability": "medium",
    "affected_assumptions": [{"assumption": "seasonal availability"}],
    "affected_metrics": [{"metric": "attendance_rate"}],
    "evidence": [{"evidence_ref": "synthetic://learning/2"}],
    "reviewed_at": "2026-10-20T13:00:00+00:00",
    "is_reviewed_by_current_actor": False,
}


class _Connection:
    def __init__(self, *, columns=(), rows=(), fail=False):
        self.columns = tuple(columns)
        self.rows = list(rows)
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
        self.description = tuple(SimpleNamespace(name=name) for name in connection.columns)

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def execute(self, query, params=None):
        self.connection.operations.append((" ".join(query.split()), params))
        if self.connection.fail and "apply_location_solution_learning" in query:
            raise RuntimeError("synthetic failure")

    def fetchone(self):
        return self.connection.rows[0] if self.connection.rows else None

    def fetchall(self):
        return list(self.connection.rows)


def _queue_path():
    return f"/operator/api/solution-lifecycle/{LOCATION_ID}/learning/application"


def _apply_path():
    return f"/operator/api/solution-lifecycle/{LOCATION_ID}/learning/{LEARNING_ID}/apply"


def _application_app(monkeypatch, *, provider=object(), queue=None, apply=None):
    from services.gateway.solution_lifecycle_routes import register_solution_lifecycle_routes

    monkeypatch.setattr(
        reads,
        "list_location_solution_learning_applications",
        queue or (lambda *_args, **_kwargs: {"location_id": LOCATION_ID, "learning": [ITEM], "has_more": False}),
    )
    monkeypatch.setattr(
        actions,
        "apply_location_solution_learning",
        apply or (lambda *_args, **_kwargs: APPLICATION),
    )
    app = FastAPI()
    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_solution_lifecycle_routes(router, provider, run_in_threadpool, SimpleNamespace(Error=Exception))
    app.include_router(router)

    @app.middleware("http")
    async def add_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    return app


def test_application_queue_uses_exact_apply_context_and_read_only_transaction():
    connection = _Connection(columns=ITEM.keys(), rows=[tuple(ITEM.values())])
    contexts = []
    with patch.object(reads, "set_operator_tenant_context", lambda conn, **kwargs: contexts.append((conn, kwargs))):
        result = reads.list_location_solution_learning_applications(
            OPERATOR_ID, LOCATION_ID, limit="5", offset="10",
            connection_factory=lambda: connection,
        )

    assert result == {
        "location_id": LOCATION_ID,
        "offset": 10,
        "learning": [ITEM],
        "has_more": False,
        "next_offset": None,
    }
    assert contexts == [(connection, {
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "solution_lifecycle",
        "action": "apply",
    })]
    assert connection.operations[0][0] == "SET TRANSACTION READ ONLY"
    assert connection.operations[-1][1] == (LOCATION_ID, 6, 10)
    assert connection.closed and connection.rolled_back and not connection.committed


@pytest.mark.parametrize("limit,offset", [("0", "0"), ("51", "0"), ("1.5", "0"), ("1", "10001")])
def test_invalid_application_queue_paging_fails_before_database(limit, offset):
    with pytest.raises(reads.SolutionLifecycleReadInvalid):
        reads.list_location_solution_learning_applications(
            OPERATOR_ID, LOCATION_ID, limit=limit, offset=offset,
            connection_factory=lambda: pytest.fail("invalid paging opened a database connection"),
        )


def test_apply_action_uses_signed_context_and_commits_the_bounded_function_result():
    connection = _Connection(columns=APPLICATION.keys(), rows=[tuple(APPLICATION.values())])
    contexts = []
    with patch.object(actions, "set_operator_tenant_context", lambda conn, **kwargs: contexts.append((conn, kwargs))):
        result = actions.apply_location_solution_learning(
            OPERATOR_ID, LOCATION_ID, LEARNING_ID, REQUEST_ID,
            "  handbook-v2  ", True, connection_factory=lambda: connection,
        )

    assert result == APPLICATION
    assert contexts == [(connection, {
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "solution_lifecycle",
        "action": "apply",
    })]
    assert connection.operations[-1][1] == (
        LOCATION_ID, LEARNING_ID, REQUEST_ID, "handbook-v2", True,
    )
    assert connection.committed and connection.closed and not connection.rolled_back


@pytest.mark.parametrize("version,acknowledged", [(" ", True), ("x" * 81, True), ("v2", False)])
def test_invalid_application_fails_before_database(version, acknowledged):
    with pytest.raises(actions.SolutionLifecycleActionInvalid):
        actions.apply_location_solution_learning(
            OPERATOR_ID, LOCATION_ID, LEARNING_ID, REQUEST_ID, version, acknowledged,
            connection_factory=lambda: pytest.fail("invalid application opened a database connection"),
        )


def test_apply_action_rolls_back_and_closes_on_database_error():
    connection = _Connection(fail=True)
    with patch.object(actions, "set_operator_tenant_context"):
        with pytest.raises(RuntimeError, match="synthetic failure"):
            actions.apply_location_solution_learning(
                OPERATOR_ID, LOCATION_ID, LEARNING_ID, REQUEST_ID,
                "handbook-v2", True, connection_factory=lambda: connection,
            )
    assert connection.rolled_back and connection.closed and not connection.committed


def test_application_routes_require_exact_location_apply_policy():
    assert auth_route_policy("GET", _queue_path(), enabled=True) == {
        "resource": "solution_lifecycle", "action": "apply", "public": False,
        "location_id": LOCATION_ID, "scope_required": True, "operator_auth": True,
    }
    assert auth_route_policy("POST", _apply_path(), enabled=True) == {
        "resource": "solution_lifecycle", "action": "apply", "public": False,
        "location_id": LOCATION_ID, "scope_required": True, "operator_auth": True,
    }
    assert auth_route_policy("GET", _apply_path(), enabled=True) is None
    assert auth_route_policy("POST", _apply_path(), enabled=False) is None


def test_application_routes_render_no_store_and_validate_payload(monkeypatch):
    calls = []
    app = _application_app(
        monkeypatch,
        apply=lambda *args, **kwargs: calls.append((args, kwargs)) or APPLICATION,
    )
    with TestClient(app) as client:
        queue = client.get(_queue_path())
        invalid = client.post(_apply_path(), json={"request_id": REQUEST_ID})
        assert invalid.status_code == 400 and not calls
        applied = client.post(_apply_path(), json={
            "request_id": REQUEST_ID,
            "applied_to_version": "handbook-v2",
            "acknowledged": True,
        })

    assert queue.status_code == 200 and queue.json()["learning"] == [ITEM]
    assert queue.headers["Cache-Control"] == "no-store"
    assert applied.status_code == 201 and applied.json() == APPLICATION
    assert applied.headers["Cache-Control"] == "no-store"
    assert calls[0][0] == (
        OPERATOR_ID, LOCATION_ID, LEARNING_ID, REQUEST_ID, "handbook-v2", True,
    )


def test_application_route_maps_missing_scope_to_forbidden(monkeypatch):
    app = _application_app(
        monkeypatch,
        apply=lambda *_args, **_kwargs: (_ for _ in ()).throw(TenantContextDenied("missing")),
    )
    with TestClient(app) as client:
        response = client.post(_apply_path(), json={
            "request_id": REQUEST_ID,
            "applied_to_version": "handbook-v2",
            "acknowledged": True,
        })
    assert response.status_code == 403

