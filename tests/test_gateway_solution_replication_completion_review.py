"""Tests for independent CAP-035 completion-report review."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest

pytest.importorskip("fastapi")
from fastapi import APIRouter, FastAPI  # noqa: E402
from fastapi.encoders import jsonable_encoder  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

from services.common.tenant_context import TenantContextDenied
from services.gateway import solution_lifecycle_actions as actions
from services.gateway import solution_lifecycle_reads as reads
from services.gateway.operator_auth import auth_route_policy

OPERATOR_ID = str(uuid4())
LOCATION_ID = str(uuid4())
REPLICATION_ID = str(uuid4())
PROPOSAL_ID = str(uuid4())
REQUEST_ID = str(uuid4())
QUEUE_ITEM = {
    "proposal_id": PROPOSAL_ID,
    "replication_id": REPLICATION_ID,
    "solution_name": "Synthetic solution",
    "solution_type": "agroforestry",
    "solution_stage": "validated",
    "outcome": "mixed",
    "evidence_maturity": 4,
    "created_at": "2026-10-20T12:00:00+00:00",
    "is_self_authored": False,
    "is_self_started": False,
    "is_initial_approver": False,
}
DETAIL = {
    **QUEUE_ITEM,
    "solution_type": "practice",
    "replication_status": "active",
    "outcome_summary": "Synthetic report summary meets the minimum length.",
    "evidence": [{"evidence_ref": "synthetic://completion/1"}],
    "created_at": datetime(2026, 10, 20, 12, tzinfo=timezone.utc),
    "source_is_current": True,
    "is_source_owner": False,
    "is_source_approver": False,
    "is_source_result_reviewer": False,
}
RESULT = {
    "event_id": str(uuid4()),
    "proposal_id": PROPOSAL_ID,
    "replication_id": REPLICATION_ID,
    "decision": "accepted",
    "replication_status": "completed",
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
        self.description = tuple(
            SimpleNamespace(name=name) for name in connection.columns
        )

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def execute(self, query, params=None):
        self.connection.operations.append((" ".join(query.split()), params))
        if self.connection.fail and "review_location_solution_replication_completion" in query:
            raise RuntimeError("database completion review failed")

    def fetchone(self):
        return self.connection.rows[0] if self.connection.rows else None

    def fetchall(self):
        return list(self.connection.rows)


def _completion_detail_path():
    return (
        f"/operator/api/solution-lifecycle/{LOCATION_ID}/replications/"
        f"{REPLICATION_ID}/completion-proposals/{PROPOSAL_ID}/review"
    )


def _app(monkeypatch, *, provider=object(), queue=None, detail=None, review=None):
    from services.gateway.solution_lifecycle_routes import register_solution_lifecycle_routes

    monkeypatch.setattr(
        reads,
        "list_location_solution_replication_completion_review_queue",
        queue or (lambda *_args, **_kwargs: {"items": [QUEUE_ITEM], "has_more": False}),
    )
    monkeypatch.setattr(
        reads,
        "get_location_solution_replication_completion_review_detail",
        detail or (lambda *_args, **_kwargs: DETAIL),
    )
    monkeypatch.setattr(
        actions,
        "review_location_solution_replication_completion",
        review or (lambda *_args, **_kwargs: RESULT),
    )
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


def test_completion_review_reads_use_exact_context_and_read_only_transaction():
    queue_connection = _Connection(
        columns=QUEUE_ITEM.keys(), rows=[tuple(QUEUE_ITEM.values())]
    )
    detail_connection = _Connection(
        columns=DETAIL.keys(), rows=[tuple(DETAIL.values())]
    )
    contexts = []

    def set_context(connection, **kwargs):
        contexts.append((connection, kwargs))

    with patch.object(reads, "set_operator_tenant_context", set_context):
        queue = reads.list_location_solution_replication_completion_review_queue(
            OPERATOR_ID, LOCATION_ID, connection_factory=lambda: queue_connection
        )
        detail = reads.get_location_solution_replication_completion_review_detail(
            OPERATOR_ID,
            LOCATION_ID,
            REPLICATION_ID,
            PROPOSAL_ID,
            connection_factory=lambda: detail_connection,
        )

    assert queue["items"] == [QUEUE_ITEM]
    assert detail == DETAIL
    for connection, kwargs in contexts:
        assert kwargs == {
            "operator_id": OPERATOR_ID,
            "location_id": LOCATION_ID,
            "resource": "solution_lifecycle",
            "action": "review",
        }
        assert connection.operations[0][0] == "SET TRANSACTION READ ONLY"
        assert connection.closed and connection.rolled_back and not connection.committed
    assert "list_location_solution_replication_completion_review_queue" in queue_connection.operations[-1][0]
    assert "get_location_solution_replication_completion_review_detail" in detail_connection.operations[-1][0]
    assert detail_connection.operations[-1][1] == (LOCATION_ID, REPLICATION_ID, PROPOSAL_ID)


def test_completion_review_action_sets_review_context_and_commits():
    connection = _Connection(columns=RESULT.keys(), rows=[tuple(RESULT.values())])
    contexts = []

    def set_context(conn, **kwargs):
        contexts.append((conn, kwargs))

    with patch.object(actions, "set_operator_tenant_context", set_context):
        result = actions.review_location_solution_replication_completion(
            OPERATOR_ID,
            LOCATION_ID,
            REPLICATION_ID,
            PROPOSAL_ID,
            REQUEST_ID,
            "accepted",
            None,
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
            "action": "review",
        },
    )]
    assert connection.operations[:2] == [
        ("SET LOCAL statement_timeout = '8s'", None),
        ("SET LOCAL lock_timeout = '2s'", None),
    ]
    assert connection.operations[-1][1] == (
        LOCATION_ID, REPLICATION_ID, PROPOSAL_ID, REQUEST_ID,
        "accepted", None, True,
    )
    assert connection.committed and connection.closed and not connection.rolled_back


@pytest.mark.parametrize(
    "decision,reason,acknowledged",
    [
        ("unknown", None, True),
        ("rejected", "short", True),
        ("accepted", " ", True),
        ("accepted", None, False),
    ],
)
def test_invalid_completion_review_fails_before_database(decision, reason, acknowledged):
    with pytest.raises(actions.SolutionLifecycleActionInvalid):
        actions.review_location_solution_replication_completion(
            OPERATOR_ID, LOCATION_ID, REPLICATION_ID, PROPOSAL_ID,
            REQUEST_ID, decision, reason, acknowledged,
            connection_factory=lambda: pytest.fail("invalid review opened a database connection"),
        )


def test_completion_review_failure_rolls_back_and_closes():
    connection = _Connection(columns=RESULT.keys(), rows=[tuple(RESULT.values())], fail=True)
    with patch.object(actions, "set_operator_tenant_context"):
        with pytest.raises(RuntimeError, match="database completion review failed"):
            actions.review_location_solution_replication_completion(
                OPERATOR_ID, LOCATION_ID, REPLICATION_ID, PROPOSAL_ID,
                REQUEST_ID, "accepted", None, True,
                connection_factory=lambda: connection,
            )
    assert connection.rolled_back and connection.closed and not connection.committed


def test_completion_review_routes_have_exact_review_policy():
    queue_path = (
        f"/operator/api/solution-lifecycle/{LOCATION_ID}/replications/"
        "completion-review"
    )
    detail_path = _completion_detail_path()
    expected = {
        "resource": "solution_lifecycle",
        "action": "review",
        "public": False,
        "location_id": LOCATION_ID,
        "scope_required": True,
        "operator_auth": True,
    }
    assert auth_route_policy("GET", queue_path, enabled=True) == expected
    for method in ("GET", "POST"):
        assert auth_route_policy(method, detail_path, enabled=True) == expected
    assert auth_route_policy("DELETE", detail_path, enabled=True) is None
    assert auth_route_policy("POST", detail_path + "/extra", enabled=True) is None


def test_completion_review_routes_are_no_store_and_reject_extra_fields(monkeypatch):
    calls = []

    def review(*args, **kwargs):
        calls.append((args, kwargs))
        return RESULT

    app = _app(monkeypatch, review=review)
    queue_path = (
        f"/operator/api/solution-lifecycle/{LOCATION_ID}/replications/"
        "completion-review"
    )
    detail_path = _completion_detail_path()
    payload = {"request_id": REQUEST_ID, "decision": "accepted", "acknowledged": True}
    with TestClient(app) as client:
        queue = client.get(queue_path)
        detail = client.get(detail_path)
        decision = client.post(detail_path, json=payload)
        invalid = client.post(detail_path, json={**payload, "status": "completed"})

    for response in (queue, detail, decision, invalid):
        assert response.headers["cache-control"] == "no-store"
        assert response.headers["vary"] == "Cookie"
    assert queue.status_code == 200, queue.text
    assert queue.json()["items"] == [QUEUE_ITEM]
    assert detail.status_code == 200 and detail.json() == jsonable_encoder(DETAIL)
    assert decision.status_code == 200 and decision.json() == RESULT
    assert invalid.status_code == 400
    assert calls == [((OPERATOR_ID, LOCATION_ID, REPLICATION_ID, PROPOSAL_ID,
                       REQUEST_ID, "accepted", None, True), {})]


def test_completion_review_routes_fail_closed_without_oidc_or_tenant_context(monkeypatch):
    path = _completion_detail_path()
    app = _app(monkeypatch, provider=None)
    with TestClient(app) as client:
        disabled = client.get(path)
    assert disabled.status_code == 404

    def deny(*_args, **_kwargs):
        raise TenantContextDenied("denied")

    app = _app(monkeypatch, review=deny)
    with TestClient(app) as client:
        denied = client.post(
            path,
            json={"request_id": REQUEST_ID, "decision": "accepted", "acknowledged": True},
        )
    assert denied.status_code == 403


def test_completion_review_detail_has_exact_openapi_projection_and_binds_path_ids(monkeypatch):
    calls = []

    def detail(*args):
        calls.append(args)
        return {**DETAIL, "source_is_current": None}

    app = _app(monkeypatch, detail=detail)
    path = _completion_detail_path()
    with TestClient(app) as client:
        response = client.get(path)

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert response.json() == jsonable_encoder({**DETAIL, "source_is_current": None})
    assert set(response.json()) == {
        "proposal_id",
        "replication_id",
        "solution_name",
        "solution_type",
        "solution_stage",
        "replication_status",
        "outcome",
        "evidence_maturity",
        "outcome_summary",
        "evidence",
        "created_at",
        "is_self_authored",
        "is_self_started",
        "is_initial_approver",
        "source_is_current",
        "is_source_owner",
        "is_source_approver",
        "is_source_result_reviewer",
    }
    assert calls == [(OPERATOR_ID, LOCATION_ID, REPLICATION_ID, PROPOSAL_ID)]

    openapi_path = (
        "/operator/api/solution-lifecycle/{location_id}/replications/"
        "{replication_id}/completion-proposals/{proposal_id}/review"
    )
    operation = app.openapi()["paths"][openapi_path]["get"]
    response_schema = operation["responses"]["200"]["content"]["application/json"]["schema"]
    schema_name = response_schema["$ref"].rsplit("/", 1)[-1]
    response_model_schema = app.openapi()["components"]["schemas"][schema_name]
    assert set(response_model_schema["properties"]) == set(response.json())
    assert response_model_schema["additionalProperties"] is False


@pytest.mark.parametrize(
    "changes",
    [
        {"proposal_id": str(uuid4())},
        {"replication_id": str(uuid4())},
        {"solution_type": "agroforestry"},
        {"replication_status": "completed"},
        {"outcome": "unknown"},
        {"evidence_maturity": 7},
        {"outcome_summary": "too short"},
        {"outcome_summary": "x" * 4001},
        {"evidence": {}},
        {"evidence": ["x"] * 101},
        {"evidence": ["x" * 65535]},
        {"evidence": [{"value": float("nan")}]},
        {"is_source_owner": "false"},
        {"unexpected_private_field": "private reviewer data"},
    ],
)
def test_completion_review_detail_sanitizes_malformed_service_results(monkeypatch, changes):
    malformed = {**DETAIL, **changes}
    app = _app(monkeypatch, detail=lambda *_args: malformed)
    with TestClient(app) as client:
        response = client.get(_completion_detail_path())

    assert response.status_code == 500
    assert response.json() == {
        "error": "Replication completion review detail unavailable"
    }
    assert "private reviewer data" not in response.text
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
