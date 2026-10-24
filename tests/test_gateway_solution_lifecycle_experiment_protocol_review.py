"""Independent review and approval contracts for submitted experiment protocols."""

from __future__ import annotations

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
EXPERIMENT_ID = str(uuid4())
REQUEST_ID = str(uuid4())
NOT_FOUND_EXPERIMENT_ID = str(uuid4())
REVIEW_DETAIL = {
    "experiment_id": EXPERIMENT_ID,
    "solution_id": str(uuid4()),
    "solution_name": "Soil restoration protocol",
    "solution_type": "practice",
    "current_stage": "experiment_ready",
    "protocol": {"hypothesis": "Soil health improves under the reviewed treatment."},
    "submitted_at": "2026-10-20T15:00:00+00:00",
    "owner_is_reviewer": False,
    "submitter_is_reviewer": False,
}
APPROVAL = {
    "experiment_id": EXPERIMENT_ID,
    "solution_id": REVIEW_DETAIL["solution_id"],
    "experiment_status": "protocol_approved",
    "approved_at": "2026-10-20T16:00:00+00:00",
    "replayed": False,
}
BODY = {"request_id": REQUEST_ID, "acknowledged": True}


class _PgNotFound(Exception):
    pgcode = "P0002"


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


def _review_context():
    return {
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "solution_lifecycle",
        "action": "review",
    }


def test_protocol_detail_uses_read_only_exact_location_review_context():
    connection = _Connection(REVIEW_DETAIL)
    contexts = []

    def set_context(conn, **kwargs):
        assert conn is connection
        contexts.append(kwargs)

    with patch.object(reads, "set_operator_tenant_context", set_context):
        result = reads.get_location_solution_experiment_protocol_review(
            OPERATOR_ID, LOCATION_ID, EXPERIMENT_ID,
            connection_factory=lambda: connection,
        )

    assert contexts == [_review_context()]
    assert connection.operations[0][0] == "SET TRANSACTION READ ONLY"
    assert "kokonut_security.location_solution_experiment_protocol_review" in connection.operations[-1][0]
    assert connection.operations[-1][1] == (LOCATION_ID, EXPERIMENT_ID)
    assert result == REVIEW_DETAIL
    assert connection.closed and connection.rolled_back and not connection.committed


def test_protocol_detail_rejects_oversized_private_response():
    connection = _Connection({**REVIEW_DETAIL, "protocol": {"detail": "x" * 262_145}})
    with patch.object(reads, "set_operator_tenant_context", lambda *_a, **_k: None):
        with pytest.raises(reads.SolutionLifecycleResponseTooLarge):
            reads.get_location_solution_experiment_protocol_review(
                OPERATOR_ID, LOCATION_ID, EXPERIMENT_ID,
                connection_factory=lambda: connection,
            )
    assert connection.closed and connection.rolled_back


def test_approval_action_uses_exact_review_context_and_bounded_function():
    connection = _Connection(APPROVAL)
    contexts = []

    def set_context(conn, **kwargs):
        assert conn is connection
        contexts.append(kwargs)

    with patch.object(actions, "set_operator_tenant_context", set_context):
        result = actions.approve_location_solution_experiment_protocol(
            OPERATOR_ID, LOCATION_ID, EXPERIMENT_ID, REQUEST_ID, True,
            connection_factory=lambda: connection,
        )

    assert contexts == [_review_context()]
    query, params = connection.operations[-1]
    assert "kokonut_security.approve_location_solution_experiment_protocol" in query
    assert params == (LOCATION_ID, EXPERIMENT_ID, REQUEST_ID, True)
    assert result == APPROVAL
    assert connection.committed and connection.closed and not connection.rolled_back


@pytest.mark.parametrize("acknowledged", [False, None, 1, "true"])
def test_unacknowledged_or_non_boolean_approval_fails_before_database(acknowledged):
    with pytest.raises(actions.SolutionLifecycleActionInvalid, match="acknowledgement"):
        actions.approve_location_solution_experiment_protocol(
            OPERATOR_ID, LOCATION_ID, EXPERIMENT_ID, REQUEST_ID, acknowledged,
            connection_factory=lambda: pytest.fail("invalid approval opened a database"),
        )


def test_approval_action_rolls_back_and_closes_on_tenant_denial():
    connection = _Connection(APPROVAL)

    def deny(*_args, **_kwargs):
        raise TenantContextDenied("denied")

    with patch.object(actions, "set_operator_tenant_context", deny):
        with pytest.raises(TenantContextDenied):
            actions.approve_location_solution_experiment_protocol(
                OPERATOR_ID, LOCATION_ID, EXPERIMENT_ID, REQUEST_ID, True,
                connection_factory=lambda: connection,
            )
    assert connection.rolled_back and connection.closed and not connection.committed


def test_protocol_review_routes_require_exact_location_review_policy():
    path = (
        f"/operator/api/solution-lifecycle/{LOCATION_ID}/experiments/"
        f"{EXPERIMENT_ID}/protocol-review"
    )
    expected = {
        "resource": "solution_lifecycle",
        "action": "review",
        "public": False,
        "location_id": LOCATION_ID,
        "scope_required": True,
        "operator_auth": True,
    }
    for method in ("GET", "POST"):
        assert auth_route_policy(method, path, enabled=True) == expected
    assert auth_route_policy("DELETE", path, enabled=True) is None
    assert auth_route_policy("POST", path, enabled=False) is None
    assert auth_route_policy("GET", path.replace(EXPERIMENT_ID, "not-a-uuid"), enabled=True) is None


def test_protocol_review_routes_are_no_store_strict_and_forward_operator(monkeypatch):
    from services.gateway.solution_lifecycle_routes import register_solution_lifecycle_routes

    calls = []

    def detail(*args, **kwargs):
        if args[2] == NOT_FOUND_EXPERIMENT_ID:
            raise _PgNotFound("not found")
        calls.append(("GET", args, kwargs))
        return REVIEW_DETAIL

    def approve(*args, **kwargs):
        calls.append(("POST", args, kwargs))
        return APPROVAL

    monkeypatch.setattr(reads, "get_location_solution_experiment_protocol_review", detail)
    monkeypatch.setattr(actions, "approve_location_solution_experiment_protocol", approve)
    app = FastAPI()
    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_solution_lifecycle_routes(
        router, object(), run_in_threadpool, SimpleNamespace(Error=_PgNotFound)
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
        f"{EXPERIMENT_ID}/protocol-review"
    )
    with TestClient(app) as client:
        get_response = client.get(path)
        post_response = client.post(path, json=BODY)
        malformed = client.post(path, json={**BODY, "reviewer_party_id": OPERATOR_ID})
        not_found = client.get(path.replace(EXPERIMENT_ID, NOT_FOUND_EXPERIMENT_ID))

    assert get_response.status_code == post_response.status_code == 200
    assert get_response.headers["cache-control"] == "no-store"
    assert post_response.headers["cache-control"] == "no-store"
    assert get_response.json() == REVIEW_DETAIL
    assert post_response.json() == APPROVAL
    assert malformed.status_code == 400
    assert not_found.status_code == 404
    assert calls == [
        ("GET", (OPERATOR_ID, LOCATION_ID, EXPERIMENT_ID), {}),
        ("POST", (OPERATOR_ID, LOCATION_ID, EXPERIMENT_ID, REQUEST_ID, True), {}),
    ]
