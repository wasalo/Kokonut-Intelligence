"""Tests for private, independently reviewed location gate approval."""

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
GATE_ID = str(uuid4())
REQUEST_ID = str(uuid4())
APPROVAL = {
    "gate_id": GATE_ID,
    "gate_status": "approved",
    "approved_at": "2026-10-20T12:00:00+00:00",
    "replayed": False,
}
REVIEW = {
    "gate_id": GATE_ID,
    "from_stage": "testing",
    "to_stage": "validated",
    "requires_human_approval": True,
    "gate_status": "draft",
    "evaluation_passed": True,
    "observed": {"experiments": 2},
    "evidence": [{"uri": "https://evidence.invalid/reviewed"}],
    "evaluated_at": "2026-10-19T12:00:00+00:00",
}


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
            SimpleNamespace(name=key) for key in (connection.row or {}).keys()
        )

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


def test_gate_review_read_uses_exact_review_context_and_closes_read_only():
    connection = _Connection(REVIEW)
    contexts = []

    def set_context(conn, **kwargs):
        assert conn is connection
        contexts.append(kwargs)

    with patch.object(reads, "set_operator_tenant_context", set_context):
        result = reads.get_location_solution_gate_review(
            OPERATOR_ID, LOCATION_ID, GATE_ID, connection_factory=lambda: connection
        )

    assert contexts == [{
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "solution_lifecycle",
        "action": "review",
    }]
    assert connection.operations[0][0] == "SET TRANSACTION READ ONLY"
    assert "kokonut_security.location_solution_gate_review" in connection.operations[-1][0]
    assert result == REVIEW
    assert connection.closed and connection.rolled_back and not connection.committed


def test_gate_review_private_payload_is_size_bounded():
    oversized = {**REVIEW, "evidence": ["x" * 262_145]}
    connection = _Connection(oversized)
    with patch.object(reads, "set_operator_tenant_context", lambda *_a, **_k: None):
        with pytest.raises(reads.SolutionLifecycleResponseTooLarge):
            reads.get_location_solution_gate_review(
                OPERATOR_ID, LOCATION_ID, GATE_ID,
                connection_factory=lambda: connection,
            )
    assert connection.closed and connection.rolled_back


def test_gate_approval_sets_review_context_and_commits_receipt_result():
    connection = _Connection(APPROVAL)
    contexts = []

    def set_context(conn, **kwargs):
        assert conn is connection
        contexts.append(kwargs)

    with patch.object(actions, "set_operator_tenant_context", set_context):
        result = actions.approve_location_solution_gate(
            OPERATOR_ID, LOCATION_ID, GATE_ID, REQUEST_ID,
            connection_factory=lambda: connection,
        )

    assert contexts == [{
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "solution_lifecycle",
        "action": "review",
    }]
    assert "kokonut_security.approve_location_solution_gate" in connection.operations[-1][0]
    assert connection.operations[-1][1] == (LOCATION_ID, GATE_ID, REQUEST_ID)
    assert result == APPROVAL
    assert connection.committed and connection.closed and not connection.rolled_back


def test_invalid_approval_identifiers_fail_before_connection():
    with pytest.raises(actions.SolutionLifecycleActionInvalid):
        actions.approve_location_solution_gate(
            OPERATOR_ID, LOCATION_ID, "bad-gate", REQUEST_ID,
            connection_factory=lambda: pytest.fail("invalid gate must fail before DB"),
        )


def test_gate_review_and_approval_routes_require_exact_review_policy():
    review_path = f"/operator/api/solution-lifecycle/{LOCATION_ID}/gates/{GATE_ID}/review"
    approve_path = f"/operator/api/solution-lifecycle/{LOCATION_ID}/gates/{GATE_ID}/approve"
    for method, path in (("GET", review_path), ("POST", approve_path)):
        assert auth_route_policy(method, path, enabled=True) == {
            "resource": "solution_lifecycle",
            "action": "review",
            "public": False,
            "location_id": LOCATION_ID,
            "scope_required": True,
            "operator_auth": True,
        }
    assert auth_route_policy("POST", review_path, enabled=True) is None
    assert auth_route_policy("GET", approve_path, enabled=True) is None


def _app(provider, monkeypatch, read_action, approve_action):
    from services.gateway.solution_lifecycle_routes import register_solution_lifecycle_routes

    monkeypatch.setattr(reads, "get_location_solution_gate_review", read_action)
    monkeypatch.setattr(actions, "approve_location_solution_gate", approve_action)
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


def test_review_route_is_no_store_and_omits_reviewer_identity(monkeypatch):
    app = _app(object(), monkeypatch, lambda *_a, **_k: REVIEW, lambda *_a, **_k: APPROVAL)
    path = f"/operator/api/solution-lifecycle/{LOCATION_ID}/gates/{GATE_ID}/review"
    with TestClient(app) as client:
        response = client.get(path)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert response.json() == REVIEW
    assert "evaluated_by_party_id" not in response.json()


@pytest.mark.parametrize(
    ("result", "expected_status"), [(APPROVAL, 201), ({**APPROVAL, "replayed": True}, 200)]
)
def test_approval_route_handles_first_write_and_idempotent_retry(monkeypatch, result, expected_status):
    app = _app(object(), monkeypatch, lambda *_a, **_k: REVIEW, lambda *_a, **_k: result)
    path = f"/operator/api/solution-lifecycle/{LOCATION_ID}/gates/{GATE_ID}/approve"
    with TestClient(app) as client:
        response = client.post(path, json={"request_id": REQUEST_ID})
        invalid = client.post(path, json={"request_id": REQUEST_ID, "status": "approved"})
    assert response.status_code == expected_status
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == result
    assert invalid.status_code == 400


def test_gate_review_and_approval_fail_closed_without_oidc(monkeypatch):
    app = _app(
        None, monkeypatch,
        lambda *_a, **_k: pytest.fail("OIDC-disabled review must not call read"),
        lambda *_a, **_k: pytest.fail("OIDC-disabled approval must not call action"),
    )
    with TestClient(app) as client:
        review = client.get(f"/operator/api/solution-lifecycle/{LOCATION_ID}/gates/{GATE_ID}/review")
        approve = client.post(
            f"/operator/api/solution-lifecycle/{LOCATION_ID}/gates/{GATE_ID}/approve",
            json={"request_id": REQUEST_ID},
        )
    assert review.status_code == 404 and approve.status_code == 404
    assert review.headers["cache-control"] == "no-store"
    assert approve.headers["cache-control"] == "no-store"


def test_approval_tenant_denial_maps_to_forbidden(monkeypatch):
    app = _app(
        object(), monkeypatch,
        lambda *_a, **_k: REVIEW,
        lambda *_a, **_k: (_ for _ in ()).throw(TenantContextDenied("denied")),
    )
    with TestClient(app) as client:
        response = client.post(
            f"/operator/api/solution-lifecycle/{LOCATION_ID}/gates/{GATE_ID}/approve",
            json={"request_id": REQUEST_ID},
        )
    assert response.status_code == 403
