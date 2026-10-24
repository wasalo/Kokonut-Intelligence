"""Tests for private, independent review of location replication proposals."""

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
REPLICATION_ID = str(uuid4())
REQUEST_ID = str(uuid4())
DECISION = {
    "request_id": REQUEST_ID,
    "decision": "approved",
    "review_reason": None,
    "acknowledged": True,
}
REVIEW_RESULT = {
    "event_id": str(uuid4()),
    "replication_id": REPLICATION_ID,
    "decision": "approved",
    "reviewed_at": "2026-10-20T12:00:00+00:00",
    "replayed": False,
}
QUEUE_ITEM = {
    "replication_id": REPLICATION_ID,
    "solution_name": "Synthetic solution",
    "solution_type": "agroforestry",
    "solution_stage": "validated",
    "source_experiment_validated": True,
    "source_result_reviewed": True,
    "created_at": "2026-10-20T11:00:00+00:00",
    "proposer_attributed": True,
    "is_self_authored": False,
}
DETAIL = {
    "replication_id": REPLICATION_ID,
    "solution_name": "Synthetic solution",
    "solution_type": "agroforestry",
    "solution_stage": "validated",
    "replication_status": "proposed",
    "target_context": "A different block on this farm",
    "adaptation_required": "Adjust shade-tree spacing",
    "replication_protocol": {"steps": ["prepare", "observe"]},
    "source_experiment_id": str(uuid4()),
    "source_experiment_status": "validated",
    "source_result_outcome": "validated",
    "source_result_reviewed_at": "2026-10-19T00:00:00+00:00",
    "created_at": "2026-10-20T11:00:00+00:00",
    "proposer_attributed": True,
    "is_self_authored": False,
}


class _Connection:
    def __init__(self, columns, rows=(), fail_query=False):
        self.columns = columns
        self.rows = list(rows)
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
        self.description = tuple(SimpleNamespace(name=name) for name in connection.columns)

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def execute(self, query, params=None):
        self.connection.operations.append((" ".join(query.split()), params))
        if self.connection.fail_query and "review_location_solution_replication" in query:
            raise RuntimeError("database replication review failed")

    def fetchone(self):
        if self.connection.rows:
            return tuple(self.connection.rows[0].values())
        return tuple(REVIEW_RESULT.values())

    def fetchall(self):
        return [tuple(row.values()) for row in self.connection.rows]


def test_replication_review_sets_exact_review_context_and_commits():
    connection = _Connection(REVIEW_RESULT)
    contexts = []

    def set_context(conn, **kwargs):
        assert conn is connection
        contexts.append(kwargs)

    with patch.object(actions, "set_operator_tenant_context", set_context):
        result = actions.review_location_solution_replication(
            OPERATOR_ID,
            LOCATION_ID,
            REPLICATION_ID,
            REQUEST_ID,
            "approved",
            None,
            True,
            connection_factory=lambda: connection,
        )

    assert contexts == [{
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "solution_lifecycle",
        "action": "review",
    }]
    assert connection.operations[:2] == [
        ("SET LOCAL statement_timeout = '8s'", None),
        ("SET LOCAL lock_timeout = '2s'", None),
    ]
    query, params = connection.operations[-1]
    assert "kokonut_security.review_location_solution_replication" in query
    assert params == (LOCATION_ID, REPLICATION_ID, REQUEST_ID, "approved", None, True)
    assert result == REVIEW_RESULT
    assert connection.committed and connection.closed and not connection.rolled_back


@pytest.mark.parametrize(
    ("decision", "reason", "acknowledged"),
    [
        ([], None, True),
        ("unknown", None, True),
        ("rejected", "short", True),
        ("approved", " ", True),
        ("approved", None, False),
    ],
)
def test_invalid_replication_review_fails_before_database_access(decision, reason, acknowledged):
    with pytest.raises(actions.SolutionLifecycleActionInvalid):
        actions.review_location_solution_replication(
            OPERATOR_ID,
            LOCATION_ID,
            REPLICATION_ID,
            REQUEST_ID,
            decision,
            reason,
            acknowledged,
            connection_factory=lambda: pytest.fail("invalid review must fail before database access"),
        )


def test_replication_review_failure_rolls_back_and_closes():
    connection = _Connection(REVIEW_RESULT, fail_query=True)
    with patch.object(actions, "set_operator_tenant_context", lambda *_args, **_kwargs: None):
        with pytest.raises(RuntimeError, match="database replication review failed"):
            actions.review_location_solution_replication(
                OPERATOR_ID,
                LOCATION_ID,
                REPLICATION_ID,
                REQUEST_ID,
                "approved",
                None,
                True,
                connection_factory=lambda: connection,
            )
    assert connection.rolled_back and connection.closed and not connection.committed


def test_replication_review_route_policies_are_exact_and_review_scoped():
    queue_path = f"/operator/api/solution-lifecycle/{LOCATION_ID}/replications/review"
    detail_path = f"{queue_path.removesuffix('/review')}/{REPLICATION_ID}/review"
    for method, path in [("GET", queue_path), ("GET", detail_path), ("POST", detail_path)]:
        assert auth_route_policy(method, path, enabled=True) == {
            "resource": "solution_lifecycle",
            "action": "review",
            "public": False,
            "location_id": LOCATION_ID,
            "scope_required": True,
            "operator_auth": True,
        }
    assert auth_route_policy("DELETE", detail_path, enabled=True) is None
    assert auth_route_policy("POST", detail_path + "/extra", enabled=True) is None


def _app(monkeypatch, *, provider=object(), review=None, queue=None, detail=None):
    from services.gateway.solution_lifecycle_routes import register_solution_lifecycle_routes

    monkeypatch.setattr(actions, "review_location_solution_replication", review or (lambda *_a, **_k: REVIEW_RESULT))
    monkeypatch.setattr(reads, "list_location_solution_replication_review_queue", queue or (lambda *_a, **_k: {"items": [QUEUE_ITEM]}))
    monkeypatch.setattr(reads, "get_location_solution_replication_review_detail", detail or (lambda *_a, **_k: DETAIL))
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

    return app


def test_review_queue_detail_and_decision_are_no_store_and_strict(monkeypatch):
    calls = []

    def review(*args, **kwargs):
        calls.append((args, kwargs))
        return REVIEW_RESULT

    app = _app(monkeypatch, review=review)
    queue_path = f"/operator/api/solution-lifecycle/{LOCATION_ID}/replications/review"
    detail_path = f"{queue_path.removesuffix('/review')}/{REPLICATION_ID}/review"
    with TestClient(app) as client:
        queue = client.get(queue_path)
        detail = client.get(detail_path)
        decision = client.post(detail_path, json=DECISION)
        invalid = client.post(detail_path, json={**DECISION, "status": "active"})

    for response in (queue, detail, decision, invalid):
        assert response.headers["cache-control"] == "no-store"
        assert response.headers["vary"] == "Cookie"
    assert queue.status_code == 200 and queue.json()["items"] == [QUEUE_ITEM]
    assert detail.status_code == 200 and detail.json() == DETAIL
    assert decision.status_code == 200 and decision.json() == REVIEW_RESULT
    assert invalid.status_code == 400
    assert calls == [((OPERATOR_ID, LOCATION_ID, REPLICATION_ID, REQUEST_ID, "approved", None, True), {})]


def test_replication_review_routes_fail_closed_without_oidc_or_on_tenant_denial(monkeypatch):
    detail_path = f"/operator/api/solution-lifecycle/{LOCATION_ID}/replications/{REPLICATION_ID}/review"
    app = _app(monkeypatch, provider=None)
    with TestClient(app) as client:
        disabled = client.get(detail_path)
    assert disabled.status_code == 404 and disabled.headers["cache-control"] == "no-store"

    def deny(*_args, **_kwargs):
        raise TenantContextDenied("denied")

    app = _app(monkeypatch, review=deny)
    with TestClient(app) as client:
        denied = client.post(detail_path, json=DECISION)
    assert denied.status_code == 403 and denied.headers["cache-control"] == "no-store"


def test_replication_review_read_helpers_use_exact_review_context_and_cleanup():
    queue_connection = _Connection(QUEUE_ITEM, [QUEUE_ITEM])
    detail_connection = _Connection(DETAIL, [DETAIL])
    contexts = []

    def set_context(connection, **kwargs):
        contexts.append((connection, kwargs))

    with patch.object(reads, "set_operator_tenant_context", set_context):
        queue = reads.list_location_solution_replication_review_queue(
            OPERATOR_ID,
            LOCATION_ID,
            limit="1",
            connection_factory=lambda: queue_connection,
        )
        detail = reads.get_location_solution_replication_review_detail(
            OPERATOR_ID,
            LOCATION_ID,
            REPLICATION_ID,
            connection_factory=lambda: detail_connection,
        )

    expected_context = {
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "solution_lifecycle",
        "action": "review",
    }
    assert [context for _, context in contexts] == [expected_context, expected_context]
    assert queue["items"] == [QUEUE_ITEM] and not queue["has_more"]
    assert detail == DETAIL
    assert "SET TRANSACTION READ ONLY" in queue_connection.operations[0][0]
    assert queue_connection.rolled_back and queue_connection.closed
    assert detail_connection.rolled_back and detail_connection.closed
