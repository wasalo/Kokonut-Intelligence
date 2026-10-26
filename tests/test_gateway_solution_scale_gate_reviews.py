"""Tenant-scoped scale-gate assessment and independent-review contract."""

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
ASSESSMENT_ID = str(uuid4())
REQUEST_ID = str(uuid4())


class _Connection:
    def __init__(self, *, row=None, rows=None, columns=()):
        self.row = row
        self.rows = rows or []
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
        self.description = tuple(
            SimpleNamespace(name=name) for name in connection.columns
        )

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def execute(self, query, params=None):
        self.connection.operations.append((" ".join(query.split()), params))

    def fetchone(self):
        return self.connection.row

    def fetchall(self):
        return self.connection.rows


def test_scale_gate_submission_sets_create_context_and_commits_pending_receipt():
    columns = ("assessment_id", "gate_id", "assessment_status", "passed", "created_at", "replayed")
    row = (ASSESSMENT_ID, GATE_ID, "pending", True, "2026-10-20T12:00:00Z", False)
    connection = _Connection(row=row, columns=columns)
    contexts = []

    def set_context(conn, **kwargs):
        assert conn is connection
        contexts.append(kwargs)

    with patch.object(actions, "set_operator_tenant_context", set_context):
        result = actions.submit_location_solution_scale_gate_assessment(
            OPERATOR_ID, LOCATION_ID, GATE_ID, REQUEST_ID, "12.5", 8,
            None, [{"source": "reviewed report"}], True,
            connection_factory=lambda: connection,
        )

    assert contexts == [{
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "solution_lifecycle",
        "action": "create",
    }]
    assert "submit_location_solution_scale_gate_assessment" in connection.operations[-1][0]
    assert connection.operations[-1][1] == (
        LOCATION_ID, GATE_ID, REQUEST_ID, "12.5", 8, None, '[{"source":"reviewed report"}]'
    )
    assert result["assessment_status"] == "pending"
    assert connection.committed and connection.closed


@pytest.mark.parametrize(
    "kwargs",
    [
        {"measured_value": ""},
        {"sample_size": True},
        {"sample_size": 0},
        {"reported_pass": "yes"},
        {"evidence_refs": []},
        {"acknowledged": False},
    ],
)
def test_scale_gate_submission_rejects_invalid_payload_before_database(kwargs):
    values = {
        "measured_value": "4.2",
        "sample_size": 4,
        "reported_pass": True,
        "evidence_refs": [{"source": "evidence"}],
        "acknowledged": True,
    }
    values.update(kwargs)
    with pytest.raises(actions.SolutionLifecycleActionInvalid):
        actions.submit_location_solution_scale_gate_assessment(
            OPERATOR_ID, LOCATION_ID, GATE_ID, REQUEST_ID,
            values["measured_value"], values["sample_size"],
            values["reported_pass"], values["evidence_refs"],
            values["acknowledged"],
            connection_factory=lambda: pytest.fail("invalid payload opened a connection"),
        )


def test_scale_gate_review_sets_review_context_and_commits_decision():
    columns = ("assessment_id", "gate_id", "assessment_status", "gate_status", "reviewed_at", "replayed")
    row = (ASSESSMENT_ID, GATE_ID, "approved", "passed", "2026-10-20T12:00:00Z", False)
    connection = _Connection(row=row, columns=columns)
    contexts = []

    with patch.object(
        actions,
        "set_operator_tenant_context",
        lambda conn, **kwargs: contexts.append((conn, kwargs)),
    ):
        result = actions.review_location_solution_scale_gate_assessment(
            OPERATOR_ID, LOCATION_ID, ASSESSMENT_ID, REQUEST_ID,
            "accepted", "Evidence reviewed", True,
            connection_factory=lambda: connection,
        )

    assert contexts == [(connection, {
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "solution_lifecycle",
        "action": "review",
    })]
    assert "review_location_solution_scale_gate_assessment" in connection.operations[-1][0]
    assert connection.operations[-1][1] == (
        LOCATION_ID, ASSESSMENT_ID, REQUEST_ID, "accepted", "Evidence reviewed"
    )
    assert result["gate_status"] == "passed"
    assert connection.committed and connection.closed


@pytest.mark.parametrize(
    "decision,reason,acknowledged",
    [("bad", None, True), ("rejected", "short", True), ("accepted", None, False)],
)
def test_scale_gate_review_rejects_invalid_decision_before_database(
    decision, reason, acknowledged
):
    with pytest.raises(actions.SolutionLifecycleActionInvalid):
        actions.review_location_solution_scale_gate_assessment(
            OPERATOR_ID, LOCATION_ID, ASSESSMENT_ID, REQUEST_ID,
            decision, reason, acknowledged,
            connection_factory=lambda: pytest.fail("invalid decision opened a connection"),
        )


def test_scale_gate_target_list_uses_create_context_and_bounded_read_only_query():
    columns = ("scale_gate_id", "gate_type", "gate_status")
    row = (GATE_ID, "safety", "pending")
    connection = _Connection(rows=[row], columns=columns)
    contexts = []

    with patch.object(
        reads,
        "set_operator_tenant_context",
        lambda conn, **kwargs: contexts.append((conn, kwargs)),
    ):
        result = reads.list_location_solution_scale_gate_assessment_targets(
            OPERATOR_ID, LOCATION_ID, limit="10", offset="5",
            connection_factory=lambda: connection,
        )

    assert contexts == [(connection, {
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "solution_lifecycle",
        "action": "create",
    })]
    assert connection.operations[:3] == [
        ("SET TRANSACTION READ ONLY", None),
        ("SET LOCAL statement_timeout = '8s'", None),
        ("SET LOCAL lock_timeout = '2s'", None),
    ]
    assert "list_location_solution_scale_gate_assessment_targets" in connection.operations[-1][0]
    assert connection.operations[-1][1] == (LOCATION_ID, 11, 5)
    assert result["targets"] == [dict(zip(columns, row))]
    assert connection.rolled_back and connection.closed


def test_scale_gate_review_queue_and_detail_require_review_context():
    queue_columns = ("assessment_id", "gate_id", "evaluator_conflict")
    queue = _Connection(rows=[(ASSESSMENT_ID, GATE_ID, False)], columns=queue_columns)
    detail_columns = ("assessment_id", "gate_id", "evidence_refs")
    detail = _Connection(row=(ASSESSMENT_ID, GATE_ID, [{"source": "review"}]), columns=detail_columns)
    contexts = []

    with patch.object(
        reads,
        "set_operator_tenant_context",
        lambda conn, **kwargs: contexts.append((conn, kwargs)),
    ):
        result = reads.list_location_solution_scale_gate_review_queue(
            OPERATOR_ID, LOCATION_ID, connection_factory=lambda: queue
        )
        record = reads.get_location_solution_scale_gate_review_detail(
            OPERATOR_ID, LOCATION_ID, ASSESSMENT_ID, connection_factory=lambda: detail
        )

    assert result["assessments"][0]["evaluator_conflict"] is False
    assert record["evidence_refs"] == [{"source": "review"}]
    assert [context[1]["action"] for context in contexts] == ["review", "review"]
    assert "list_location_solution_scale_gate_review_queue" in queue.operations[-1][0]
    assert "get_location_solution_scale_gate_review_detail" in detail.operations[-1][0]


def test_scale_gate_invalid_page_and_context_denial_fail_before_projection():
    with pytest.raises(reads.SolutionLifecycleReadInvalid):
        reads.list_location_solution_scale_gate_review_queue(
            OPERATOR_ID, LOCATION_ID, limit="1.0",
            connection_factory=lambda: pytest.fail("invalid page opened a connection"),
        )

    connection = _Connection()
    with patch.object(
        reads, "set_operator_tenant_context", side_effect=TenantContextDenied("denied")
    ):
        with pytest.raises(TenantContextDenied):
            reads.list_location_solution_scale_gate_review_queue(
                OPERATOR_ID, LOCATION_ID, connection_factory=lambda: connection
            )
    assert not any("list_location_solution_scale_gate_review_queue" in query
                   for query, _ in connection.operations)
    assert connection.rolled_back and connection.closed


@pytest.mark.parametrize(
    "method,suffix,action",
    [
        ("GET", "/scale-gates/assessment-targets", "create"),
        ("POST", f"/scale-gates/{GATE_ID}/evaluations", "create"),
        ("GET", "/scale-gates/review", "review"),
        ("GET", f"/scale-gates/review/{ASSESSMENT_ID}", "review"),
        ("POST", f"/scale-gates/review/{ASSESSMENT_ID}", "review"),
    ],
)
def test_scale_gate_routes_require_exact_location_operator_policy(method, suffix, action):
    policy = auth_route_policy(
        method,
        f"/operator/api/solution-lifecycle/{LOCATION_ID}{suffix}",
        enabled=True,
    )
    assert policy == {
        "resource": "solution_lifecycle",
        "action": action,
        "public": False,
        "location_id": LOCATION_ID,
        "scope_required": True,
        "operator_auth": True,
    }
    assert auth_route_policy(method, f"/operator/api/solution-lifecycle/{LOCATION_ID}{suffix}/extra", enabled=True) is None


def test_scale_gate_submit_http_route_is_no_store_and_oidc_disabled_fails_closed(monkeypatch):
    result = {
        "assessment_id": ASSESSMENT_ID,
        "gate_id": GATE_ID,
        "assessment_status": "pending",
        "passed": True,
        "replayed": False,
    }
    monkeypatch.setattr(
        "services.gateway.solution_lifecycle_actions.submit_location_solution_scale_gate_assessment",
        lambda *_args, **_kwargs: result,
    )
    app = FastAPI()
    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    from services.gateway.solution_lifecycle_routes import register_solution_lifecycle_routes

    register_solution_lifecycle_routes(router, object(), run_in_threadpool, SimpleNamespace(Error=Exception))
    app.include_router(router)

    @app.middleware("http")
    async def add_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    path = f"/operator/api/solution-lifecycle/{LOCATION_ID}/scale-gates/{GATE_ID}/evaluations"
    payload = {
        "request_id": REQUEST_ID,
        "measured_value": "3.2",
        "sample_size": 4,
        "reported_pass": True,
        "evidence_refs": [{"source": "report"}],
        "acknowledged": True,
    }
    with TestClient(app) as client:
        response = client.post(path, json=payload)
    assert response.status_code == 201
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"

    disabled_router = APIRouter()
    disabled = FastAPI()
    register_solution_lifecycle_routes(disabled_router, None, run_in_threadpool, SimpleNamespace(Error=Exception))
    disabled.include_router(disabled_router)
    with TestClient(disabled) as client:
        response = client.post(path, json=payload)
    assert response.status_code == 404
    assert response.headers["cache-control"] == "no-store"
