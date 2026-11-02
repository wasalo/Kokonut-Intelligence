"""Tests for independent exact-location learning proposal review."""

from datetime import datetime, timezone
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
QUEUE_ITEM = {
    "learning_record_id": LEARNING_ID,
    "solution_name": "Synthetic solution",
    "solution_type": "practice",
    "solution_stage": "validated",
    "lesson_type": "context_transfer",
    "confidence": "high",
    "transferability": "medium",
    "created_at": "2026-10-20T12:00:00+00:00",
    "is_self_authored": False,
    "is_self_starter": False,
    "is_initial_approver": False,
    "is_completion_reviewer": False,
    "is_source_owner": False,
    "is_source_approver": False,
    "is_source_result_reviewer": False,
}
DETAIL = {
    "location_id": LOCATION_ID,
    **QUEUE_ITEM,
    "created_at": datetime(2026, 10, 20, 12, 0, tzinfo=timezone.utc),
    "finding": "A locally tailored training schedule improved participation.",
    "affected_assumptions": [{"assumption": "seasonal availability"}],
    "affected_metrics": [{"metric": "attendance_rate"}],
    "recommended_action": "Adapt the training calendar to local planting cycles.",
    "evidence": [{"evidence_ref": "synthetic://learning/1"}],
    "source_is_current": True,
}
RESULT = {
    "event_id": str(uuid4()),
    "learning_record_id": LEARNING_ID,
    "decision": "accepted",
    "reviewed_at": "2026-10-20T13:00:00+00:00",
    "replayed": False,
}


class _Connection:
    def __init__(self, columns=(), rows=(), *, fail=False):
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
        if self.connection.fail and "review_location_solution_learning" in query:
            raise RuntimeError("database learning review failed")

    def fetchone(self):
        return self.connection.rows[0] if self.connection.rows else None

    def fetchall(self):
        return list(self.connection.rows)


def _queue_path():
    return f"/operator/api/solution-lifecycle/{LOCATION_ID}/learning/review"


def _detail_path():
    return f"/operator/api/solution-lifecycle/{LOCATION_ID}/learning/{LEARNING_ID}/review"


def _app(monkeypatch, *, provider=object(), queue=None, detail=None, review=None):
    from services.gateway.solution_lifecycle_routes import register_solution_lifecycle_routes

    monkeypatch.setattr(
        reads,
        "list_location_solution_learning_review_queue",
        queue or (lambda *_args, **_kwargs: {"items": [QUEUE_ITEM], "has_more": False}),
    )
    monkeypatch.setattr(
        reads,
        "get_location_solution_learning_review_detail",
        detail or (lambda *_args, **_kwargs: DETAIL),
    )
    monkeypatch.setattr(actions, "review_location_solution_learning", review or (lambda *_args, **_kwargs: RESULT))
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


def test_learning_review_reads_use_exact_context_and_read_only_transactions():
    queue_connection = _Connection(columns=QUEUE_ITEM.keys(), rows=[tuple(QUEUE_ITEM.values())])
    detail_connection = _Connection(columns=DETAIL.keys(), rows=[tuple(DETAIL.values())])
    contexts = []

    def set_context(connection, **kwargs):
        contexts.append((connection, kwargs))

    with patch.object(reads, "set_operator_tenant_context", set_context):
        queue = reads.list_location_solution_learning_review_queue(
            OPERATOR_ID, LOCATION_ID, connection_factory=lambda: queue_connection
        )
        detail = reads.get_location_solution_learning_review_detail(
            OPERATOR_ID, LOCATION_ID, LEARNING_ID,
            connection_factory=lambda: detail_connection,
        )

    assert queue["items"] == [QUEUE_ITEM]
    assert detail == {"location_id": LOCATION_ID, **DETAIL}
    for connection, kwargs in contexts:
        assert kwargs == {
            "operator_id": OPERATOR_ID,
            "location_id": LOCATION_ID,
            "resource": "solution_lifecycle",
            "action": "review",
        }
        assert connection.operations[0][0] == "SET TRANSACTION READ ONLY"
        assert connection.closed and connection.rolled_back and not connection.committed
    assert "list_location_solution_learning_review_queue" in queue_connection.operations[-1][0]
    assert "get_location_solution_learning_review_detail" in detail_connection.operations[-1][0]


def test_learning_review_action_sets_review_context_and_commits():
    connection = _Connection(columns=RESULT.keys(), rows=[tuple(RESULT.values())])
    contexts = []

    with patch.object(actions, "set_operator_tenant_context", lambda conn, **kwargs: contexts.append((conn, kwargs))):
        result = actions.review_location_solution_learning(
            OPERATOR_ID, LOCATION_ID, LEARNING_ID, REQUEST_ID, "accepted",
            "Reviewed the source evidence and transfer limits.", True,
            connection_factory=lambda: connection,
        )

    assert result == RESULT
    assert contexts == [(connection, {
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "solution_lifecycle",
        "action": "review",
    })]
    assert connection.operations[:2] == [
        ("SET LOCAL statement_timeout = '8s'", None),
        ("SET LOCAL lock_timeout = '2s'", None),
    ]
    assert connection.operations[-1][1] == (
        LOCATION_ID, LEARNING_ID, REQUEST_ID, "accepted",
        "Reviewed the source evidence and transfer limits.", True,
    )
    assert connection.committed and connection.closed and not connection.rolled_back


@pytest.mark.parametrize(
    "decision,reason,acknowledged",
    [("unknown", None, True), ("rejected", "short", True), ("accepted", " ", True), ("accepted", None, False)],
)
def test_invalid_learning_review_fails_before_database(decision, reason, acknowledged):
    with pytest.raises(actions.SolutionLifecycleActionInvalid):
        actions.review_location_solution_learning(
            OPERATOR_ID, LOCATION_ID, LEARNING_ID, REQUEST_ID,
            decision, reason, acknowledged,
            connection_factory=lambda: pytest.fail("invalid review opened a database connection"),
        )


def test_learning_review_action_failure_rolls_back_and_closes():
    connection = _Connection(fail=True)
    with patch.object(actions, "set_operator_tenant_context"):
        with pytest.raises(RuntimeError, match="database learning review failed"):
            actions.review_location_solution_learning(
                OPERATOR_ID, LOCATION_ID, LEARNING_ID, REQUEST_ID,
                "accepted", None, True, connection_factory=lambda: connection,
            )
    assert connection.rolled_back and connection.closed and not connection.committed


def test_learning_review_routes_have_exact_review_policy():
    expected = {
        "resource": "solution_lifecycle",
        "action": "review",
        "public": False,
        "location_id": LOCATION_ID,
        "scope_required": True,
        "operator_auth": True,
    }
    assert auth_route_policy("GET", _queue_path(), enabled=True) == expected
    for method in ("GET", "POST"):
        assert auth_route_policy(method, _detail_path(), enabled=True) == expected
    assert auth_route_policy("DELETE", _detail_path(), enabled=True) is None
    assert auth_route_policy("POST", _detail_path() + "/extra", enabled=True) is None


def test_learning_review_routes_are_no_store_and_reject_extra_fields(monkeypatch):
    calls = []
    app = _app(monkeypatch, review=lambda *args, **kwargs: calls.append((args, kwargs)) or RESULT)
    payload = {"request_id": REQUEST_ID, "decision": "accepted", "acknowledged": True}
    with TestClient(app) as client:
        queue = client.get(_queue_path())
        detail = client.get(_detail_path())
        decision = client.post(_detail_path(), json=payload)
        invalid = client.post(_detail_path(), json={**payload, "status": "applied"})
    for response in (queue, detail, decision, invalid):
        assert response.headers["cache-control"] == "no-store"
        assert response.headers["vary"] == "Cookie"
    assert queue.status_code == 200 and queue.json()["items"] == [QUEUE_ITEM]
    assert detail.status_code == 200
    assert detail.json() == {**DETAIL, "created_at": "2026-10-20T12:00:00+00:00"}
    assert decision.status_code == 201 and decision.json() == RESULT
    assert invalid.status_code == 400
    assert calls == [((OPERATOR_ID, LOCATION_ID, LEARNING_ID, REQUEST_ID, "accepted", None, True), {})]


def test_learning_review_detail_openapi_declares_the_strict_private_projection(monkeypatch):
    app = _app(monkeypatch)
    path = "/operator/api/solution-lifecycle/{location_id}/learning/{learning_record_id}/review"
    operation = app.openapi()["paths"][path]
    schema_ref = operation["get"]["responses"]["200"]["content"]["application/json"]["schema"]["$ref"]
    assert schema_ref == "#/components/schemas/SolutionLifecycleLearningReviewDetailResponse"
    schema = app.openapi()["components"]["schemas"]["SolutionLifecycleLearningReviewDetailResponse"]
    assert schema["additionalProperties"] is False
    assert {
        "location_id", "learning_record_id", "finding", "recommended_action",
        "affected_assumptions", "affected_metrics", "evidence", "source_is_current",
    }.issubset(schema["required"])


@pytest.mark.parametrize(
    "mutate",
    [
        lambda value: value.update(operator_id=OPERATOR_ID),
        lambda value: value.update(location_id=str(uuid4())),
        lambda value: value.update(learning_record_id=str(uuid4())),
        lambda value: value.update(confidence="certain"),
        lambda value: value.pop("finding"),
    ],
)
def test_learning_review_detail_rejects_malformed_or_mismatched_service_output(monkeypatch, mutate):
    malformed = dict(DETAIL)
    mutate(malformed)
    app = _app(monkeypatch, detail=lambda *_args, **_kwargs: malformed)

    with TestClient(app) as client:
        response = client.get(_detail_path())

    assert response.status_code == 500
    assert response.json() == {"error": "Solution learning review detail unavailable"}
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert OPERATOR_ID not in response.text


def test_learning_review_routes_fail_closed_without_oidc_or_tenant_context(monkeypatch):
    app = _app(monkeypatch, provider=None)
    with TestClient(app) as client:
        disabled = client.get(_queue_path())
    assert disabled.status_code == 404

    def deny(*_args, **_kwargs):
        raise TenantContextDenied("denied")

    app = _app(monkeypatch, review=deny)
    with TestClient(app) as client:
        denied = client.post(
            _detail_path(),
            json={"request_id": REQUEST_ID, "decision": "accepted", "acknowledged": True},
        )
    assert denied.status_code == 403
