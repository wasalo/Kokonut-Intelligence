"""Tests for the location-scoped solution lifecycle Gateway projection."""

from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest

from services.common.tenant_context import TenantContextDenied
from services.gateway import solution_lifecycle_reads as reads
from services.gateway.operator_auth import auth_route_policy

pytest.importorskip("fastapi")
from fastapi import APIRouter, FastAPI  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

OPERATOR_ID = str(uuid4())
LOCATION_ID = str(uuid4())
SUMMARY = {
    "solution_count": 2,
    "stage_counts": {"discovered": 1, "validated": 1},
    "solution_status_counts": {"active": 2},
    "stage_gate_status_counts": {"approved": 1},
    "latest_gate_evaluation_counts": {"passed": 1, "failed": 0},
    "experiment_status_counts": {"active": 1},
    "experiment_result_counts": {"validated": 1},
    "replication_status_counts": {"proposed": 1},
    "funding_decision_counts": {"submitted": 1},
    "adoption_program_status_counts": {"active": 1},
    "configuration_approval_counts": {"approved": 1},
    "adopter_readiness_counts": {"ready": 1},
    "scale_gate_status_counts": {"passed": 1},
    "learning_decision_counts": {"accepted": 1},
    "retirement_status_counts": {"proposed": 1},
}


class _Connection:
    def __init__(self, row=None, *, rows=None, columns=()):
        self.row = row
        self.rows = rows or []
        self.columns = columns
        self.operations = []
        self.rolled_back = False
        self.closed = False

    def cursor(self):
        return _Cursor(self)

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
        row = self.connection.row
        return row if isinstance(row, tuple) else (row,)

    def fetchall(self):
        return self.connection.rows


def test_summary_sets_exact_tenant_context_and_uses_read_only_connection():
    connection = _Connection(SUMMARY)
    contexts = []

    def set_context(conn, **kwargs):
        assert conn is connection
        contexts.append(kwargs)

    with patch.object(reads, "set_operator_tenant_context", set_context):
        result = reads.get_location_solution_lifecycle_summary(
            OPERATOR_ID, LOCATION_ID, connection_factory=lambda: connection,
        )

    assert contexts == [{
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "solution_lifecycle",
        "action": "read",
    }]
    assert [query for query, _ in connection.operations[:3]] == [
        "SET TRANSACTION READ ONLY",
        "SET LOCAL statement_timeout = '8s'",
        "SET LOCAL lock_timeout = '2s'",
    ]
    assert "location_solution_lifecycle_summary" in connection.operations[-1][0]
    assert connection.operations[-1][1] == (LOCATION_ID,)
    assert result == {"location_id": LOCATION_ID, **SUMMARY}
    assert connection.rolled_back and connection.closed


@pytest.mark.parametrize("operator_id,location_id", [
    ("not-a-uuid", LOCATION_ID), (OPERATOR_ID, "not-a-uuid"),
])
def test_invalid_identity_fails_before_database_access(operator_id, location_id):
    with pytest.raises(reads.SolutionLifecycleReadInvalid):
        reads.get_location_solution_lifecycle_summary(
            operator_id, location_id,
            connection_factory=lambda: pytest.fail("invalid identity must fail before DB access"),
        )


def test_tenant_denial_rolls_back_without_projection_call():
    connection = _Connection(SUMMARY)

    def deny(*_args, **_kwargs):
        raise TenantContextDenied("denied")

    with patch.object(reads, "set_operator_tenant_context", deny):
        with pytest.raises(TenantContextDenied):
            reads.get_location_solution_lifecycle_summary(
                OPERATOR_ID, LOCATION_ID, connection_factory=lambda: connection,
            )

    assert not any("location_solution_lifecycle_summary" in query
                   for query, _ in connection.operations)
    assert connection.rolled_back and connection.closed


def test_projection_contract_contains_aggregate_status_only():
    assert "stage_counts" in SUMMARY
    assert "latest_gate_evaluation_counts" in SUMMARY
    assert "experiment_result_counts" in SUMMARY
    assert "funding_decision_counts" in SUMMARY
    assert "scale_gate_status_counts" in SUMMARY
    serialized = str(SUMMARY).lower()
    for private_field in ("party_id", "canonical_key", "rationale", "evidence", "amount"):
        assert private_field not in serialized


def test_route_policy_requires_exact_location_solution_lifecycle_read_grant():
    path = f"/operator/api/solution-lifecycle/{LOCATION_ID}/summary"
    assert auth_route_policy("GET", path, enabled=True) == {
        "resource": "solution_lifecycle",
        "action": "read",
        "public": False,
        "location_id": LOCATION_ID,
        "scope_required": True,
        "operator_auth": True,
    }
    assert auth_route_policy("POST", path, enabled=True) is None
    assert auth_route_policy("GET", path + "/extra", enabled=True) is None


def test_http_projection_is_no_store_and_operator_authenticated(monkeypatch):
    from services.gateway.solution_lifecycle_routes import register_solution_lifecycle_routes

    monkeypatch.setattr(
        "services.gateway.solution_lifecycle_reads.get_location_solution_lifecycle_summary",
        lambda *_args, **_kwargs: {"location_id": LOCATION_ID, **SUMMARY},
    )
    app = FastAPI()
    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_solution_lifecycle_routes(router, object(), run_in_threadpool,
                                        SimpleNamespace(Error=Exception))
    app.include_router(router)

    @app.middleware("http")
    async def add_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    with TestClient(app) as client:
        response = client.get(f"/operator/api/solution-lifecycle/{LOCATION_ID}/summary")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert response.json()["solution_count"] == 2


def test_http_projection_fails_closed_when_oidc_is_disabled(monkeypatch):
    from services.gateway.solution_lifecycle_routes import register_solution_lifecycle_routes

    monkeypatch.setattr(
        "services.gateway.solution_lifecycle_reads.get_location_solution_lifecycle_summary",
        lambda *_args, **_kwargs: pytest.fail("disabled OIDC must not query the projection"),
    )
    app = FastAPI()
    router = APIRouter()
    register_solution_lifecycle_routes(router, None, lambda *_args: None,
                                        SimpleNamespace(Error=Exception))
    app.include_router(router)

    with TestClient(app) as client:
        response = client.get(f"/operator/api/solution-lifecycle/{LOCATION_ID}/summary")

    assert response.status_code == 404
    assert response.headers["cache-control"] == "no-store"


def test_http_projection_maps_tenant_denial_to_forbidden(monkeypatch):
    from services.gateway.solution_lifecycle_routes import register_solution_lifecycle_routes

    def deny(*_args, **_kwargs):
        raise TenantContextDenied("denied")

    monkeypatch.setattr(
        "services.gateway.solution_lifecycle_reads.get_location_solution_lifecycle_summary", deny,
    )
    app = FastAPI()
    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_solution_lifecycle_routes(router, object(), run_in_threadpool,
                                        SimpleNamespace(Error=Exception))
    app.include_router(router)

    @app.middleware("http")
    async def add_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    with TestClient(app) as client:
        response = client.get(f"/operator/api/solution-lifecycle/{LOCATION_ID}/summary")

    assert response.status_code == 403
    assert response.headers["cache-control"] == "no-store"


def test_retirement_candidates_are_exact_origin_bounded_and_keep_safe_fields():
    columns = (
        "solution_id", "solution_name", "solution_type", "current_stage", "solution_status",
    )
    row = (
        "c0000000-0000-4000-8000-000000000001", "Soil cover", "practice",
        "testing", "active",
    )
    connection = _Connection(rows=[row, row, row], columns=columns)
    contexts = []

    def set_context(conn, **kwargs):
        assert conn is connection
        contexts.append(kwargs)

    with patch.object(reads, "set_operator_tenant_context", set_context):
        result = reads.list_location_solution_retirement_candidates(
            OPERATOR_ID, LOCATION_ID, limit="2", offset="5",
            connection_factory=lambda: connection,
        )

    assert contexts == [{
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "solution_lifecycle",
        "action": "read",
    }]
    assert [query for query, _ in connection.operations[:3]] == [
        "SET TRANSACTION READ ONLY",
        "SET LOCAL statement_timeout = '8s'",
        "SET LOCAL lock_timeout = '2s'",
    ]
    assert "list_location_solution_retirement_candidates" in connection.operations[-1][0]
    assert connection.operations[-1][1] == (LOCATION_ID, 3, 5)
    assert result["solutions"] == [dict(zip(columns, row)), dict(zip(columns, row))]
    assert result["has_more"] is True and result["next_offset"] == 7
    assert connection.rolled_back and connection.closed


@pytest.mark.parametrize("limit,offset", [(0, 0), (51, 0), ("2.0", 0), (2, -1), (2, 10001)])
def test_retirement_candidates_reject_invalid_page_before_database_access(limit, offset):
    with pytest.raises(reads.SolutionLifecycleReadInvalid):
        reads.list_location_solution_retirement_candidates(
            OPERATOR_ID, LOCATION_ID, limit=limit, offset=offset,
            connection_factory=lambda: pytest.fail("invalid page opened a connection"),
        )


def test_retirement_candidates_context_denial_rolls_back_without_projection_call():
    connection = _Connection()

    def deny(*_args, **_kwargs):
        raise TenantContextDenied("denied")

    with patch.object(reads, "set_operator_tenant_context", deny):
        with pytest.raises(TenantContextDenied):
            reads.list_location_solution_retirement_candidates(
                OPERATOR_ID, LOCATION_ID, connection_factory=lambda: connection,
            )

    assert not any("list_location_solution_retirement_candidates" in query
                   for query, _ in connection.operations)
    assert connection.rolled_back and connection.closed


def test_http_retirement_candidates_are_no_store_and_operator_authenticated(monkeypatch):
    from services.gateway.solution_lifecycle_routes import register_solution_lifecycle_routes

    monkeypatch.setattr(
        "services.gateway.solution_lifecycle_reads.list_location_solution_retirement_candidates",
        lambda *_args, **_kwargs: {"location_id": LOCATION_ID, "solutions": []},
    )
    app = FastAPI()
    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_solution_lifecycle_routes(router, object(), run_in_threadpool,
                                        SimpleNamespace(Error=Exception))
    app.include_router(router)

    @app.middleware("http")
    async def add_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    with TestClient(app) as client:
        response = client.get(
            f"/operator/api/solution-lifecycle/{LOCATION_ID}/retirement-candidates"
        )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert response.json()["location_id"] == LOCATION_ID


def test_retirement_review_queue_uses_signed_review_scope_and_bounded_page():
    columns = (
        "retirement_id", "solution_id", "solution_name", "retirement_type",
        "retirement_status", "created_at", "proposer_attributed", "is_self_authored",
    )
    row = (
        "d0000000-0000-4000-8000-000000000001",
        "c0000000-0000-4000-8000-000000000001",
        "Soil cover", "unsafe", "proposed", "2026-10-20T12:00:00Z", True, False,
    )
    connection = _Connection(rows=[row, row, row], columns=columns)
    contexts = []

    def set_context(conn, **kwargs):
        assert conn is connection
        contexts.append(kwargs)

    with patch.object(reads, "set_operator_tenant_context", set_context):
        result = reads.list_location_solution_retirement_review_queue(
            OPERATOR_ID, LOCATION_ID, limit="2", offset="4",
            connection_factory=lambda: connection,
        )

    assert contexts == [{
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "solution_lifecycle",
        "action": "review",
    }]
    assert [query for query, _ in connection.operations[:3]] == [
        "SET TRANSACTION READ ONLY",
        "SET LOCAL statement_timeout = '8s'",
        "SET LOCAL lock_timeout = '2s'",
    ]
    assert "list_location_solution_retirement_review_queue" in connection.operations[-1][0]
    assert connection.operations[-1][1] == (LOCATION_ID, 3, 4)
    assert result["retirements"] == [dict(zip(columns, row)), dict(zip(columns, row))]
    assert result["has_more"] is True and result["next_offset"] == 6
    assert connection.rolled_back and connection.closed


@pytest.mark.parametrize("limit,offset", [(0, 0), (51, 0), ("2.0", 0), (2, -1), (2, 10001)])
def test_retirement_review_queue_rejects_invalid_page_before_database_access(limit, offset):
    with pytest.raises(reads.SolutionLifecycleReadInvalid):
        reads.list_location_solution_retirement_review_queue(
            OPERATOR_ID, LOCATION_ID, limit=limit, offset=offset,
            connection_factory=lambda: pytest.fail("invalid page opened a connection"),
        )


def test_retirement_review_queue_context_denial_rolls_back_without_query():
    connection = _Connection()

    def deny(*_args, **_kwargs):
        raise TenantContextDenied("denied")

    with patch.object(reads, "set_operator_tenant_context", deny):
        with pytest.raises(TenantContextDenied):
            reads.list_location_solution_retirement_review_queue(
                OPERATOR_ID, LOCATION_ID, connection_factory=lambda: connection,
            )

    assert not any("list_location_solution_retirement_review_queue" in query
                   for query, _ in connection.operations)
    assert connection.rolled_back and connection.closed


def test_retirement_review_detail_returns_private_proposal_only_after_review_context():
    columns = (
        "retirement_id", "solution_name", "solution_type", "current_stage",
        "solution_status", "retirement_type", "retirement_status", "trigger_reason",
        "evidence_refs", "migration_plan", "replacement_solution_name", "created_at",
        "proposer_attributed", "is_self_authored",
    )
    row = (
        "d0000000-0000-4000-8000-000000000001", "Soil cover", "practice", "testing",
        "active", "unsafe", "proposed", "Observed erosion after planting",
        [{"source": "case-42"}], "Pause rollout and restore cover", None,
        "2026-10-20T12:00:00Z", True, False,
    )
    connection = _Connection(row=row, columns=columns)
    contexts = []

    def set_context(conn, **kwargs):
        assert conn is connection
        contexts.append(kwargs)

    with patch.object(reads, "set_operator_tenant_context", set_context):
        result = reads.get_location_solution_retirement_review_detail(
            OPERATOR_ID, LOCATION_ID, "d0000000-0000-4000-8000-000000000001",
            connection_factory=lambda: connection,
        )

    assert contexts == [{
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "solution_lifecycle",
        "action": "review",
    }]
    assert "get_location_solution_retirement_review_detail" in connection.operations[-1][0]
    assert connection.operations[-1][1] == (LOCATION_ID, "d0000000-0000-4000-8000-000000000001")
    assert result["trigger_reason"] == row[7]
    assert result["evidence_refs"] == row[8]
    assert result["is_self_authored"] is False
    assert "created_by_party_id" not in result and "proposer_party_id" not in result
    assert connection.rolled_back and connection.closed


def test_http_retirement_review_routes_are_no_store_and_oidc_gated(monkeypatch):
    from services.gateway.solution_lifecycle_routes import register_solution_lifecycle_routes

    monkeypatch.setattr(
        "services.gateway.solution_lifecycle_reads.list_location_solution_retirement_review_queue",
        lambda *_args, **_kwargs: {"location_id": LOCATION_ID, "retirements": []},
    )
    monkeypatch.setattr(
        "services.gateway.solution_lifecycle_reads.get_location_solution_retirement_review_detail",
        lambda *_args, **_kwargs: {"location_id": LOCATION_ID, "is_self_authored": False},
    )
    app = FastAPI()
    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_solution_lifecycle_routes(router, object(), run_in_threadpool,
                                        SimpleNamespace(Error=Exception))
    app.include_router(router)

    @app.middleware("http")
    async def add_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    with TestClient(app) as client:
        queue = client.get(f"/operator/api/solution-lifecycle/{LOCATION_ID}/retirements/review")
        detail = client.get(
            f"/operator/api/solution-lifecycle/{LOCATION_ID}/retirements/review/"
            "d0000000-0000-4000-8000-000000000001"
        )

    assert queue.status_code == detail.status_code == 200
    assert queue.headers["cache-control"] == detail.headers["cache-control"] == "no-store"
    assert queue.headers["vary"] == detail.headers["vary"] == "Cookie"


def test_http_retirement_review_detail_maps_missing_item_to_not_found(monkeypatch):
    from services.gateway.solution_lifecycle_routes import register_solution_lifecycle_routes

    def missing(*_args, **_kwargs):
        raise reads.SolutionLifecycleReviewNotFound("missing")

    monkeypatch.setattr(
        "services.gateway.solution_lifecycle_reads.get_location_solution_retirement_review_detail",
        missing,
    )
    app = FastAPI()
    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_solution_lifecycle_routes(router, object(), run_in_threadpool,
                                        SimpleNamespace(Error=Exception))
    app.include_router(router)

    @app.middleware("http")
    async def add_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    with TestClient(app) as client:
        response = client.get(
            f"/operator/api/solution-lifecycle/{LOCATION_ID}/retirements/review/"
            "d0000000-0000-4000-8000-000000000001"
        )

    assert response.status_code == 404
    assert response.headers["cache-control"] == "no-store"


def test_gate_list_uses_signed_context_bounded_page_and_returns_no_raw_evidence():
    columns = (
        "solution_id", "solution_name", "solution_type", "current_stage",
        "solution_status", "gate_id", "from_stage", "to_stage",
        "required_evidence_maturity", "required_experiment_count",
        "requires_human_approval", "gate_status", "gate_created_at",
        "latest_evaluation_passed", "latest_evaluated_at",
    )
    row = (
        "c0000000-0000-4000-8000-000000000001", "Soil cover", "practice",
        "testing", "active", "e0000000-0000-4000-8000-000000000001",
        "testing", "validated", 3, 2, True, "ready", "2026-10-18T00:00:00Z",
        True, "2026-10-19T00:00:00Z",
    )
    connection = _Connection(rows=[row, row, row], columns=columns)
    contexts = []

    def set_context(conn, **kwargs):
        assert conn is connection
        contexts.append(kwargs)

    with patch.object(reads, "set_operator_tenant_context", set_context):
        result = reads.list_location_solution_gates(
            OPERATOR_ID, LOCATION_ID, limit="2", offset="5",
            connection_factory=lambda: connection,
        )

    assert contexts == [{
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "solution_lifecycle",
        "action": "read",
    }]
    assert [query for query, _ in connection.operations[:3]] == [
        "SET TRANSACTION READ ONLY",
        "SET LOCAL statement_timeout = '8s'",
        "SET LOCAL lock_timeout = '2s'",
    ]
    assert "list_location_solution_gates" in connection.operations[-1][0]
    assert connection.operations[-1][1] == (LOCATION_ID, 3, 5)
    assert len(result["gates"]) == 2
    assert result["has_more"] is True
    assert result["next_offset"] == 7
    assert "latest_evaluation_passed" in result["gates"][0]
    assert not {"evidence", "observed", "evaluated_by_party_id"}.intersection(
        result["gates"][0]
    )
    assert connection.rolled_back and connection.closed


@pytest.mark.parametrize("limit,offset", [(0, 0), (51, 0), ("2.0", 0), (2, -1), (2, 10001)])
def test_gate_list_rejects_invalid_page_before_database_access(limit, offset):
    with pytest.raises(reads.SolutionLifecycleReadInvalid):
        reads.list_location_solution_gates(
            OPERATOR_ID, LOCATION_ID, limit=limit, offset=offset,
            connection_factory=lambda: pytest.fail("invalid page opened a connection"),
        )


def test_gate_list_context_denial_rolls_back_without_projection_call():
    connection = _Connection()

    def deny(*_args, **_kwargs):
        raise TenantContextDenied("denied")

    with patch.object(reads, "set_operator_tenant_context", deny):
        with pytest.raises(TenantContextDenied):
            reads.list_location_solution_gates(
                OPERATOR_ID, LOCATION_ID, connection_factory=lambda: connection,
            )

    assert not any("list_location_solution_gates" in query
                   for query, _params in connection.operations)
    assert connection.rolled_back and connection.closed


def test_experiment_list_uses_signed_context_bounded_page_and_private_field_allowlist():
    columns = (
        "solution_id", "solution_name", "solution_type", "current_stage",
        "solution_status", "experiment_id", "protocol_version", "experiment_status",
        "duration_days", "primary_metric_count", "secondary_metric_count",
        "experiment_created_at", "experiment_updated_at", "started_at", "completed_at",
        "latest_result_outcome", "latest_result_reviewed_at",
    )
    row = (
        "c0000000-0000-4000-8000-000000000001", "Soil cover", "practice",
        "testing", "active", "f0000000-0000-4000-8000-000000000001",
        "v2", "completed", 42, 2, 1, "2026-10-18T00:00:00Z",
        "2026-10-19T00:00:00Z", "2026-10-01T00:00:00Z",
        "2026-10-18T00:00:00Z", "validated", "2026-10-19T00:00:00Z",
    )
    connection = _Connection(rows=[row, row, row], columns=columns)
    contexts = []

    def set_context(conn, **kwargs):
        assert conn is connection
        contexts.append(kwargs)

    with patch.object(reads, "set_operator_tenant_context", set_context):
        result = reads.list_location_solution_experiments(
            OPERATOR_ID, LOCATION_ID, limit="2", offset="5",
            connection_factory=lambda: connection,
        )

    assert contexts == [{
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "solution_lifecycle",
        "action": "read",
    }]
    assert [query for query, _ in connection.operations[:3]] == [
        "SET TRANSACTION READ ONLY",
        "SET LOCAL statement_timeout = '8s'",
        "SET LOCAL lock_timeout = '2s'",
    ]
    assert "list_location_solution_experiments" in connection.operations[-1][0]
    assert connection.operations[-1][1] == (LOCATION_ID, 3, 5)
    assert len(result["experiments"]) == 2
    assert result["has_more"] is True
    assert result["next_offset"] == 7
    assert result["experiments"][0]["latest_result_outcome"] == "validated"
    assert not {
        "hypothesis", "baseline_definition", "treatment_definition", "observations",
        "raw_results", "evidence", "reviewed_by_party_id", "owner_party_id",
    }.intersection(result["experiments"][0])
    assert connection.rolled_back and connection.closed


@pytest.mark.parametrize("limit,offset", [(0, 0), (51, 0), ("2.0", 0), (2, -1), (2, 10001)])
def test_experiment_list_rejects_invalid_page_before_database_access(limit, offset):
    with pytest.raises(reads.SolutionLifecycleReadInvalid):
        reads.list_location_solution_experiments(
            OPERATOR_ID, LOCATION_ID, limit=limit, offset=offset,
            connection_factory=lambda: pytest.fail("invalid page opened a connection"),
        )


def test_experiment_list_context_denial_rolls_back_without_projection_call():
    connection = _Connection()

    def deny(*_args, **_kwargs):
        raise TenantContextDenied("denied")

    with patch.object(reads, "set_operator_tenant_context", deny):
        with pytest.raises(TenantContextDenied):
            reads.list_location_solution_experiments(
                OPERATOR_ID, LOCATION_ID, connection_factory=lambda: connection,
            )

    assert not any("list_location_solution_experiments" in query
                   for query, _ in connection.operations)
    assert connection.rolled_back and connection.closed


def test_funding_list_uses_signed_context_bounded_page_and_omits_financial_details():
    columns = (
        "solution_id", "solution_name", "solution_type", "current_stage",
        "solution_status", "funding_case_id", "capital_stage", "funding_instrument",
        "currency", "decision_status", "case_created_at", "case_approved_at",
        "tranche_id", "tranche_number", "tranche_status", "tranche_approved_at",
        "tranche_released_at",
    )
    row = (
        "c0000000-0000-4000-8000-000000000001", "Soil cover", "practice",
        "funded", "active", "f3000000-0000-4000-8000-000000000001",
        "pilot", "grant", "USD", "approved", "2026-10-18T00:00:00Z",
        "2026-10-19T00:00:00Z", "f3100000-0000-4000-8000-000000000001",
        1, "released", "2026-10-19T00:00:00Z", "2026-10-20T00:00:00Z",
    )
    connection = _Connection(rows=[row, row, row], columns=columns)
    contexts = []

    def set_context(conn, **kwargs):
        assert conn is connection
        contexts.append(kwargs)

    with patch.object(reads, "set_operator_tenant_context", set_context):
        result = reads.list_location_solution_funding(
            OPERATOR_ID, LOCATION_ID, limit="2", offset="5",
            connection_factory=lambda: connection,
        )

    assert contexts == [{
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "solution_lifecycle",
        "action": "read",
    }]
    assert [query for query, _ in connection.operations[:3]] == [
        "SET TRANSACTION READ ONLY",
        "SET LOCAL statement_timeout = '8s'",
        "SET LOCAL lock_timeout = '2s'",
    ]
    assert "list_location_solution_funding" in connection.operations[-1][0]
    assert connection.operations[-1][1] == (LOCATION_ID, 3, 5)
    assert len(result["funding"]) == 2
    assert result["has_more"] is True
    assert result["next_offset"] == 7
    assert result["funding"][0]["tranche_status"] == "released"
    assert not {
        "amount", "requested_amount", "rationale", "evidence", "milestone_conditions",
        "approved_by_party_id", "released_by_party_id", "released_amount",
    }.intersection(result["funding"][0])
    assert connection.rolled_back and connection.closed


@pytest.mark.parametrize("limit,offset", [(0, 0), (51, 0), ("2.0", 0), (2, -1), (2, 10001)])
def test_funding_list_rejects_invalid_page_before_database_access(limit, offset):
    with pytest.raises(reads.SolutionLifecycleReadInvalid):
        reads.list_location_solution_funding(
            OPERATOR_ID, LOCATION_ID, limit=limit, offset=offset,
            connection_factory=lambda: pytest.fail("invalid page opened a connection"),
        )


def test_funding_list_context_denial_rolls_back_without_projection_call():
    connection = _Connection()

    def deny(*_args, **_kwargs):
        raise TenantContextDenied("denied")

    with patch.object(reads, "set_operator_tenant_context", deny):
        with pytest.raises(TenantContextDenied):
            reads.list_location_solution_funding(
                OPERATOR_ID, LOCATION_ID, connection_factory=lambda: connection,
            )

    assert not any("list_location_solution_funding" in query
                   for query, _ in connection.operations)
    assert connection.rolled_back and connection.closed


def test_adoption_list_uses_signed_context_bounded_page_and_suppressed_adopter_count():
    columns = (
        "solution_id", "solution_name", "solution_type", "current_stage",
        "solution_status", "program_id", "program_status", "program_created_at",
        "program_updated_at", "consented_adopter_reference_count",
    )
    row = (
        "c0000000-0000-4000-8000-000000000001", "Soil cover", "practice",
        "adopting", "active", "f4000000-0000-4000-8000-000000000001",
        "active", "2026-10-18T00:00:00Z", "2026-10-19T00:00:00Z", 5,
    )
    connection = _Connection(rows=[row, row, row], columns=columns)
    contexts = []

    def set_context(conn, **kwargs):
        assert conn is connection
        contexts.append(kwargs)

    with patch.object(reads, "set_operator_tenant_context", set_context):
        result = reads.list_location_solution_adoption(
            OPERATOR_ID, LOCATION_ID, limit="2", offset="5",
            connection_factory=lambda: connection,
        )

    assert contexts == [{
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "solution_lifecycle",
        "action": "read",
    }]
    assert [query for query, _ in connection.operations[:3]] == [
        "SET TRANSACTION READ ONLY",
        "SET LOCAL statement_timeout = '8s'",
        "SET LOCAL lock_timeout = '2s'",
    ]
    assert "list_location_solution_adoption" in connection.operations[-1][0]
    assert connection.operations[-1][1] == (LOCATION_ID, 3, 5)
    assert len(result["programs"]) == 2
    assert result["has_more"] is True
    assert result["next_offset"] == 7
    assert result["programs"][0]["consented_adopter_reference_count"] == 5
    assert not {
        "adopter_ref", "event_type", "observed_at", "fidelity_score", "support_required",
        "outcome", "evidence", "recorded_by_party_id", "cohort_id",
    }.intersection(result["programs"][0])
    assert connection.rolled_back and connection.closed


@pytest.mark.parametrize("limit,offset", [(0, 0), (51, 0), ("2.0", 0), (2, -1), (2, 10001)])
def test_adoption_list_rejects_invalid_page_before_database_access(limit, offset):
    with pytest.raises(reads.SolutionLifecycleReadInvalid):
        reads.list_location_solution_adoption(
            OPERATOR_ID, LOCATION_ID, limit=limit, offset=offset,
            connection_factory=lambda: pytest.fail("invalid page opened a connection"),
        )


def test_adoption_list_context_denial_rolls_back_without_projection_call():
    connection = _Connection()

    def deny(*_args, **_kwargs):
        raise TenantContextDenied("denied")

    with patch.object(reads, "set_operator_tenant_context", deny):
        with pytest.raises(TenantContextDenied):
            reads.list_location_solution_adoption(
                OPERATOR_ID, LOCATION_ID, connection_factory=lambda: connection,
            )

    assert not any("list_location_solution_adoption" in query
                   for query, _ in connection.operations)
    assert connection.rolled_back and connection.closed


def test_adoption_event_summary_uses_signed_context_and_returns_only_coarse_counts():
    columns = (
        "program_id", "engagement_reference_count", "commitment_reference_count",
        "use_reference_count", "advocacy_reference_count",
        "paused_or_abandoned_reference_count", "breakdown_suppressed",
    )
    program_id = "f4000000-0000-4000-8000-000000000001"
    connection = _Connection(
        row=(program_id, 8, 5, 6, 0, 0, False),
        columns=columns,
    )
    contexts = []

    def set_context(conn, **kwargs):
        assert conn is connection
        contexts.append(kwargs)

    with patch.object(reads, "set_operator_tenant_context", set_context):
        result = reads.get_location_solution_adoption_event_summary(
            OPERATOR_ID, LOCATION_ID, program_id,
            connection_factory=lambda: connection,
        )

    assert contexts == [{
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "solution_lifecycle",
        "action": "read",
    }]
    assert [query for query, _ in connection.operations[:3]] == [
        "SET TRANSACTION READ ONLY",
        "SET LOCAL statement_timeout = '8s'",
        "SET LOCAL lock_timeout = '2s'",
    ]
    assert "get_location_solution_adoption_event_summary" in connection.operations[-1][0]
    assert connection.operations[-1][1] == (LOCATION_ID, program_id)
    assert result == {
        "location_id": LOCATION_ID,
        "program_id": program_id,
        "engagement_reference_count": 8,
        "commitment_reference_count": 5,
        "use_reference_count": 6,
        "advocacy_reference_count": 0,
        "paused_or_abandoned_reference_count": 0,
        "breakdown_suppressed": False,
    }
    assert not {"adopter_ref", "cohort_id", "event_type", "observed_at", "evidence"}.intersection(result)
    assert connection.rolled_back and connection.closed


@pytest.mark.parametrize("location_id,program_id", [
    ("not-a-uuid", "f4000000-0000-4000-8000-000000000001"),
    (LOCATION_ID, "bad-program-id"),
])
def test_adoption_event_summary_rejects_invalid_ids_before_database_access(location_id, program_id):
    with pytest.raises(reads.SolutionLifecycleReadInvalid):
        reads.get_location_solution_adoption_event_summary(
            OPERATOR_ID, location_id, program_id,
            connection_factory=lambda: pytest.fail("invalid IDs opened a connection"),
        )


def test_adoption_event_summary_context_denial_rolls_back_without_projection_call():
    connection = _Connection()

    def deny(*_args, **_kwargs):
        raise TenantContextDenied("denied")

    with patch.object(reads, "set_operator_tenant_context", deny):
        with pytest.raises(TenantContextDenied):
            reads.get_location_solution_adoption_event_summary(
                OPERATOR_ID, LOCATION_ID, "f4000000-0000-4000-8000-000000000001",
                connection_factory=lambda: connection,
            )

    assert not any("get_location_solution_adoption_event_summary" in query
                   for query, _ in connection.operations)
    assert connection.rolled_back and connection.closed


def test_adoption_event_summary_hides_database_not_found_as_scoped_record_not_found():
    class _MissingProgram(Exception):
        pgcode = "P0002"

    class _MissingCursor(_Cursor):
        def execute(self, query, params=None):
            super().execute(query, params)
            if "get_location_solution_adoption_event_summary" in query:
                raise _MissingProgram("not found")

    class _MissingConnection(_Connection):
        def cursor(self):
            return _MissingCursor(self)

    connection = _MissingConnection()
    with patch.object(reads, "set_operator_tenant_context"):
        with pytest.raises(reads.SolutionLifecycleRecordNotFound):
            reads.get_location_solution_adoption_event_summary(
                OPERATOR_ID, LOCATION_ID, "f4000000-0000-4000-8000-000000000001",
                connection_factory=lambda: connection,
            )
    assert connection.rolled_back and connection.closed


def test_gate_route_policy_uses_the_exact_solution_location_read_grant():
    path = f"/operator/api/solution-lifecycle/{LOCATION_ID}/gates"
    assert auth_route_policy("GET", path, enabled=True) == {
        "resource": "solution_lifecycle",
        "action": "read",
        "public": False,
        "location_id": LOCATION_ID,
        "scope_required": True,
        "operator_auth": True,
    }
    assert auth_route_policy("POST", path, enabled=True) is None
    assert auth_route_policy("GET", path + "/extra", enabled=True) is None


def test_experiment_route_policy_uses_the_exact_solution_location_read_grant():
    path = f"/operator/api/solution-lifecycle/{LOCATION_ID}/experiments"
    assert auth_route_policy("GET", path, enabled=True) == {
        "resource": "solution_lifecycle",
        "action": "read",
        "public": False,
        "location_id": LOCATION_ID,
        "scope_required": True,
        "operator_auth": True,
    }
    assert auth_route_policy("POST", path, enabled=True) is None
    assert auth_route_policy("GET", path + "/extra", enabled=True) is None


def test_funding_route_policy_uses_the_exact_solution_location_read_grant():
    path = f"/operator/api/solution-lifecycle/{LOCATION_ID}/funding"
    assert auth_route_policy("GET", path, enabled=True) == {
        "resource": "solution_lifecycle",
        "action": "read",
        "public": False,
        "location_id": LOCATION_ID,
        "scope_required": True,
        "operator_auth": True,
    }
    assert auth_route_policy("POST", path, enabled=True) is None
    assert auth_route_policy("GET", path + "/extra", enabled=True) is None


def test_adoption_route_policy_uses_the_exact_solution_location_read_grant():
    path = f"/operator/api/solution-lifecycle/{LOCATION_ID}/adoption"
    assert auth_route_policy("GET", path, enabled=True) == {
        "resource": "solution_lifecycle",
        "action": "read",
        "public": False,
        "location_id": LOCATION_ID,
        "scope_required": True,
        "operator_auth": True,
    }
    assert auth_route_policy("POST", path, enabled=True) is None
    assert auth_route_policy("GET", path + "/extra", enabled=True) is None


def test_gate_http_route_is_no_store_and_oidc_disabled_fails_closed(monkeypatch):
    from services.gateway.solution_lifecycle_routes import register_solution_lifecycle_routes

    gate = {
        "solution_id": "c0000000-0000-4000-8000-000000000001",
        "solution_name": "Soil cover",
        "gate_id": "e0000000-0000-4000-8000-000000000001",
        "gate_status": "ready",
    }
    monkeypatch.setattr(
        "services.gateway.solution_lifecycle_reads.list_location_solution_gates",
        lambda *_args, **_kwargs: {
            "location_id": LOCATION_ID, "offset": 0, "gates": [gate],
            "has_more": False, "next_offset": None,
        },
    )
    app = FastAPI()
    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_solution_lifecycle_routes(router, object(), run_in_threadpool,
                                        SimpleNamespace(Error=Exception))
    app.include_router(router)

    @app.middleware("http")
    async def add_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    path = f"/operator/api/solution-lifecycle/{LOCATION_ID}/gates"
    with TestClient(app) as client:
        response = client.get(path, params={"limit": "10"})
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert response.json()["gates"][0]["gate_status"] == "ready"

    disabled = FastAPI()
    disabled_router = APIRouter()
    register_solution_lifecycle_routes(disabled_router, None, run_in_threadpool,
                                        SimpleNamespace(Error=Exception))
    disabled.include_router(disabled_router)
    with TestClient(disabled) as client:
        no_oidc = client.get(path)
    assert no_oidc.status_code == 404
    assert no_oidc.headers["cache-control"] == "no-store"


def test_experiment_http_route_is_no_store_and_oidc_disabled_fails_closed(monkeypatch):
    from services.gateway.solution_lifecycle_routes import register_solution_lifecycle_routes

    experiment = {
        "solution_id": "c0000000-0000-4000-8000-000000000001",
        "experiment_id": "f0000000-0000-4000-8000-000000000001",
        "experiment_status": "completed",
        "latest_result_outcome": "validated",
    }
    monkeypatch.setattr(
        "services.gateway.solution_lifecycle_reads.list_location_solution_experiments",
        lambda *_args, **_kwargs: {
            "location_id": LOCATION_ID, "offset": 0, "experiments": [experiment],
            "has_more": False, "next_offset": None,
        },
    )
    app = FastAPI()
    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_solution_lifecycle_routes(router, object(), run_in_threadpool,
                                        SimpleNamespace(Error=Exception))
    app.include_router(router)

    @app.middleware("http")
    async def add_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    path = f"/operator/api/solution-lifecycle/{LOCATION_ID}/experiments"
    with TestClient(app) as client:
        response = client.get(path, params={"limit": "10"})
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert response.json()["experiments"][0]["latest_result_outcome"] == "validated"

    disabled = FastAPI()
    disabled_router = APIRouter()
    register_solution_lifecycle_routes(disabled_router, None, run_in_threadpool,
                                        SimpleNamespace(Error=Exception))
    disabled.include_router(disabled_router)
    with TestClient(disabled) as client:
        no_oidc = client.get(path)
    assert no_oidc.status_code == 404
    assert no_oidc.headers["cache-control"] == "no-store"


def test_funding_http_route_is_no_store_and_oidc_disabled_fails_closed(monkeypatch):
    from services.gateway.solution_lifecycle_routes import register_solution_lifecycle_routes

    funding_row = {
        "solution_id": "c0000000-0000-4000-8000-000000000001",
        "funding_case_id": "f3000000-0000-4000-8000-000000000001",
        "decision_status": "approved",
        "tranche_status": "released",
    }
    monkeypatch.setattr(
        "services.gateway.solution_lifecycle_reads.list_location_solution_funding",
        lambda *_args, **_kwargs: {
            "location_id": LOCATION_ID, "offset": 0, "funding": [funding_row],
            "has_more": False, "next_offset": None,
        },
    )
    app = FastAPI()
    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_solution_lifecycle_routes(router, object(), run_in_threadpool,
                                        SimpleNamespace(Error=Exception))
    app.include_router(router)

    @app.middleware("http")
    async def add_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    path = f"/operator/api/solution-lifecycle/{LOCATION_ID}/funding"
    with TestClient(app) as client:
        response = client.get(path, params={"limit": "10"})
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert response.json()["funding"][0]["tranche_status"] == "released"

    disabled = FastAPI()
    disabled_router = APIRouter()
    register_solution_lifecycle_routes(disabled_router, None, run_in_threadpool,
                                        SimpleNamespace(Error=Exception))
    disabled.include_router(disabled_router)
    with TestClient(disabled) as client:
        no_oidc = client.get(path)
    assert no_oidc.status_code == 404
    assert no_oidc.headers["cache-control"] == "no-store"


def test_adoption_http_route_is_no_store_and_oidc_disabled_fails_closed(monkeypatch):
    from services.gateway.solution_lifecycle_routes import register_solution_lifecycle_routes

    program = {
        "solution_id": "c0000000-0000-4000-8000-000000000001",
        "program_id": "f4000000-0000-4000-8000-000000000001",
        "program_status": "active",
        "consented_adopter_reference_count": None,
    }
    monkeypatch.setattr(
        "services.gateway.solution_lifecycle_reads.list_location_solution_adoption",
        lambda *_args, **_kwargs: {
            "location_id": LOCATION_ID, "offset": 0, "programs": [program],
            "has_more": False, "next_offset": None,
        },
    )
    app = FastAPI()
    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_solution_lifecycle_routes(router, object(), run_in_threadpool,
                                        SimpleNamespace(Error=Exception))
    app.include_router(router)

    @app.middleware("http")
    async def add_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    path = f"/operator/api/solution-lifecycle/{LOCATION_ID}/adoption"
    with TestClient(app) as client:
        response = client.get(path, params={"limit": "10"})
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert response.json()["programs"][0]["consented_adopter_reference_count"] is None

    disabled = FastAPI()
    disabled_router = APIRouter()
    register_solution_lifecycle_routes(disabled_router, None, run_in_threadpool,
                                        SimpleNamespace(Error=Exception))
    disabled.include_router(disabled_router)
    with TestClient(disabled) as client:
        no_oidc = client.get(path)
    assert no_oidc.status_code == 404
    assert no_oidc.headers["cache-control"] == "no-store"


def test_adoption_event_summary_http_route_is_no_store_and_oidc_disabled_fails_closed(monkeypatch):
    from services.gateway.solution_lifecycle_routes import register_solution_lifecycle_routes

    program_id = "f4000000-0000-4000-8000-000000000001"
    summary = {
        "location_id": LOCATION_ID,
        "program_id": program_id,
        "engagement_reference_count": None,
        "commitment_reference_count": None,
        "use_reference_count": None,
        "advocacy_reference_count": None,
        "paused_or_abandoned_reference_count": None,
        "breakdown_suppressed": True,
    }
    missing_program = False

    def lookup_summary(*_args, **_kwargs):
        if missing_program:
            raise reads.SolutionLifecycleRecordNotFound("missing")
        return summary

    monkeypatch.setattr(
        "services.gateway.solution_lifecycle_reads.get_location_solution_adoption_event_summary",
        lookup_summary,
    )
    app = FastAPI()
    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_solution_lifecycle_routes(router, object(), run_in_threadpool,
                                        SimpleNamespace(Error=Exception))
    app.include_router(router)

    @app.middleware("http")
    async def add_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    path = f"/operator/api/solution-lifecycle/{LOCATION_ID}/adoption/{program_id}/events"
    with TestClient(app) as client:
        response = client.get(path)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert response.json() == summary
    assert "adopter_ref" not in response.json()

    missing_program = True
    with TestClient(app) as client:
        missing = client.get(path)
    assert missing.status_code == 404
    assert missing.headers["cache-control"] == "no-store"

    disabled = FastAPI()
    disabled_router = APIRouter()
    register_solution_lifecycle_routes(disabled_router, None, run_in_threadpool,
                                        SimpleNamespace(Error=Exception))
    disabled.include_router(disabled_router)
    with TestClient(disabled) as client:
        no_oidc = client.get(path)
    assert no_oidc.status_code == 404
    assert no_oidc.headers["cache-control"] == "no-store"


def test_scale_gate_list_uses_signed_context_bounded_page_and_allowlisted_status():
    columns = (
        "solution_id", "solution_name", "solution_type", "current_stage",
        "solution_status", "scale_gate_id", "gate_type", "gate_status",
        "has_human_approval", "approved_at",
    )
    row = (
        "c0000000-0000-4000-8000-000000000001", "Soil cover", "practice",
        "scaled", "active", "a1000000-0000-4000-8000-000000000001",
        "safety", "passed", True, "2026-10-19T00:00:00Z",
    )
    connection = _Connection(rows=[row, row, row], columns=columns)
    contexts = []

    def set_context(conn, **kwargs):
        assert conn is connection
        contexts.append(kwargs)

    with patch.object(reads, "set_operator_tenant_context", set_context):
        result = reads.list_location_solution_scale_gates(
            OPERATOR_ID, LOCATION_ID, limit="2", offset="5",
            connection_factory=lambda: connection,
        )

    assert contexts == [{
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "solution_lifecycle",
        "action": "read",
    }]
    assert [query for query, _ in connection.operations[:3]] == [
        "SET TRANSACTION READ ONLY",
        "SET LOCAL statement_timeout = '8s'",
        "SET LOCAL lock_timeout = '2s'",
    ]
    assert "list_location_solution_scale_gates" in connection.operations[-1][0]
    assert connection.operations[-1][1] == (LOCATION_ID, 3, 5)
    assert len(result["scale_gates"]) == 2
    assert result["has_more"] is True
    assert result["next_offset"] == 7
    assert result["scale_gates"][0]["has_human_approval"] is True
    assert not {
        "requirement", "threshold", "threshold_numeric", "measured_value",
        "evidence_refs", "approved_by_party_id", "metric_key",
    }.intersection(result["scale_gates"][0])
    assert connection.rolled_back and connection.closed


@pytest.mark.parametrize("limit,offset", [(0, 0), (51, 0), ("2.0", 0), (2, -1), (2, 10001)])
def test_scale_gate_list_rejects_invalid_page_before_database_access(limit, offset):
    with pytest.raises(reads.SolutionLifecycleReadInvalid):
        reads.list_location_solution_scale_gates(
            OPERATOR_ID, LOCATION_ID, limit=limit, offset=offset,
            connection_factory=lambda: pytest.fail("invalid page opened a connection"),
        )


def test_scale_gate_context_denial_rolls_back_without_projection_call():
    connection = _Connection()

    def deny(*_args, **_kwargs):
        raise TenantContextDenied("denied")

    with patch.object(reads, "set_operator_tenant_context", deny):
        with pytest.raises(TenantContextDenied):
            reads.list_location_solution_scale_gates(
                OPERATOR_ID, LOCATION_ID, connection_factory=lambda: connection,
            )

    assert not any("list_location_solution_scale_gates" in query
                   for query, _ in connection.operations)
    assert connection.rolled_back and connection.closed


def test_scale_gate_route_policy_uses_exact_solution_location_read_grant():
    path = f"/operator/api/solution-lifecycle/{LOCATION_ID}/scale-gates"
    assert auth_route_policy("GET", path, enabled=True) == {
        "resource": "solution_lifecycle",
        "action": "read",
        "public": False,
        "location_id": LOCATION_ID,
        "scope_required": True,
        "operator_auth": True,
    }
    assert auth_route_policy("POST", path, enabled=True) is None
    assert auth_route_policy("GET", path + "/extra", enabled=True) is None


def test_scale_gate_http_route_is_no_store_and_oidc_disabled_fails_closed(monkeypatch):
    from services.gateway.solution_lifecycle_routes import register_solution_lifecycle_routes

    gate = {
        "solution_id": "c0000000-0000-4000-8000-000000000001",
        "scale_gate_id": "a1000000-0000-4000-8000-000000000001",
        "gate_type": "safety",
        "gate_status": "passed",
        "has_human_approval": False,
    }
    monkeypatch.setattr(
        "services.gateway.solution_lifecycle_reads.list_location_solution_scale_gates",
        lambda *_args, **_kwargs: {
            "location_id": LOCATION_ID, "offset": 0, "scale_gates": [gate],
            "has_more": False, "next_offset": None,
        },
    )
    app = FastAPI()
    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_solution_lifecycle_routes(router, object(), run_in_threadpool,
                                        SimpleNamespace(Error=Exception))
    app.include_router(router)

    @app.middleware("http")
    async def add_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    path = f"/operator/api/solution-lifecycle/{LOCATION_ID}/scale-gates"
    with TestClient(app) as client:
        response = client.get(path, params={"limit": "10"})
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert response.json()["scale_gates"][0]["has_human_approval"] is False

    disabled = FastAPI()
    disabled_router = APIRouter()
    register_solution_lifecycle_routes(disabled_router, None, run_in_threadpool,
                                        SimpleNamespace(Error=Exception))
    disabled.include_router(disabled_router)
    with TestClient(disabled) as client:
        no_oidc = client.get(path)
    assert no_oidc.status_code == 404
    assert no_oidc.headers["cache-control"] == "no-store"


def test_replication_list_uses_signed_context_bounded_page_and_allowlisted_status():
    columns = (
        "solution_id", "solution_name", "solution_type", "current_stage",
        "solution_status", "replication_id", "replication_status",
        "replication_result", "evidence_maturity", "has_review",
        "replication_created_at", "completed_at",
    )
    row = (
        "c0000000-0000-4000-8000-000000000001", "Soil cover", "practice",
        "replicating", "active", "a2000000-0000-4000-8000-000000000001",
        "completed", "successful", 3, True,
        "2026-10-12T00:00:00Z", "2026-10-19T00:00:00Z",
    )
    connection = _Connection(rows=[row, row, row], columns=columns)
    contexts = []

    def set_context(conn, **kwargs):
        assert conn is connection
        contexts.append(kwargs)

    with patch.object(reads, "set_operator_tenant_context", set_context):
        result = reads.list_location_solution_replications(
            OPERATOR_ID, LOCATION_ID, limit="2", offset="5",
            connection_factory=lambda: connection,
        )

    assert contexts == [{
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "solution_lifecycle",
        "action": "read",
    }]
    assert [query for query, _ in connection.operations[:3]] == [
        "SET TRANSACTION READ ONLY",
        "SET LOCAL statement_timeout = '8s'",
        "SET LOCAL lock_timeout = '2s'",
    ]
    assert "list_location_solution_replications" in connection.operations[-1][0]
    assert connection.operations[-1][1] == (LOCATION_ID, 3, 5)
    assert len(result["replications"]) == 2
    assert result["has_more"] is True
    assert result["next_offset"] == 7
    assert result["replications"][0]["has_review"] is True
    assert not {
        "source_experiment_id", "target_context", "context_similarity",
        "adaptation_required", "replication_protocol", "evidence",
        "reviewed_by_party_id",
    }.intersection(result["replications"][0])
    assert connection.rolled_back and connection.closed


@pytest.mark.parametrize("limit,offset", [(0, 0), (51, 0), ("2.0", 0), (2, -1), (2, 10001)])
def test_replication_list_rejects_invalid_page_before_database_access(limit, offset):
    with pytest.raises(reads.SolutionLifecycleReadInvalid):
        reads.list_location_solution_replications(
            OPERATOR_ID, LOCATION_ID, limit=limit, offset=offset,
            connection_factory=lambda: pytest.fail("invalid page opened a connection"),
        )


def test_replication_context_denial_rolls_back_without_projection_call():
    connection = _Connection()

    def deny(*_args, **_kwargs):
        raise TenantContextDenied("denied")

    with patch.object(reads, "set_operator_tenant_context", deny):
        with pytest.raises(TenantContextDenied):
            reads.list_location_solution_replications(
                OPERATOR_ID, LOCATION_ID, connection_factory=lambda: connection,
            )

    assert not any("list_location_solution_replications" in query
                   for query, _ in connection.operations)
    assert connection.rolled_back and connection.closed


def test_replication_route_policy_uses_exact_solution_location_read_grant():
    path = f"/operator/api/solution-lifecycle/{LOCATION_ID}/replications"
    assert auth_route_policy("GET", path, enabled=True) == {
        "resource": "solution_lifecycle",
        "action": "read",
        "public": False,
        "location_id": LOCATION_ID,
        "scope_required": True,
        "operator_auth": True,
    }
    assert auth_route_policy("POST", path, enabled=True) is None
    assert auth_route_policy("GET", path + "/extra", enabled=True) is None


def test_replication_http_route_is_no_store_and_oidc_disabled_fails_closed(monkeypatch):
    from services.gateway.solution_lifecycle_routes import register_solution_lifecycle_routes

    replication = {
        "solution_id": "c0000000-0000-4000-8000-000000000001",
        "replication_id": "a2000000-0000-4000-8000-000000000001",
        "replication_status": "completed",
        "replication_result": "successful",
        "has_review": True,
    }
    monkeypatch.setattr(
        "services.gateway.solution_lifecycle_reads.list_location_solution_replications",
        lambda *_args, **_kwargs: {
            "location_id": LOCATION_ID, "offset": 0, "replications": [replication],
            "has_more": False, "next_offset": None,
        },
    )
    app = FastAPI()
    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_solution_lifecycle_routes(router, object(), run_in_threadpool,
                                        SimpleNamespace(Error=Exception))
    app.include_router(router)

    @app.middleware("http")
    async def add_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    path = f"/operator/api/solution-lifecycle/{LOCATION_ID}/replications"
    with TestClient(app) as client:
        response = client.get(path, params={"limit": "10"})
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert response.json()["replications"][0]["replication_result"] == "successful"

    disabled = FastAPI()
    disabled_router = APIRouter()
    register_solution_lifecycle_routes(disabled_router, None, run_in_threadpool,
                                        SimpleNamespace(Error=Exception))
    disabled.include_router(disabled_router)
    with TestClient(disabled) as client:
        no_oidc = client.get(path)
    assert no_oidc.status_code == 404
    assert no_oidc.headers["cache-control"] == "no-store"


def test_learning_list_uses_signed_context_bounded_page_and_allowlisted_status():
    columns = (
        "solution_id", "solution_name", "solution_type", "current_stage",
        "solution_status", "learning_record_id", "lesson_type", "confidence",
        "transferability", "decision_status", "created_at",
    )
    row = (
        "c0000000-0000-4000-8000-000000000001", "Soil cover", "practice",
        "replicating", "active", "a3000000-0000-4000-8000-000000000001",
        "validated_assumption", "high", "medium", "accepted",
        "2026-10-19T00:00:00Z",
    )
    connection = _Connection(rows=[row, row, row], columns=columns)
    contexts = []

    def set_context(conn, **kwargs):
        assert conn is connection
        contexts.append(kwargs)

    with patch.object(reads, "set_operator_tenant_context", set_context):
        result = reads.list_location_solution_learning(
            OPERATOR_ID, LOCATION_ID, limit="2", offset="5",
            connection_factory=lambda: connection,
        )

    assert contexts == [{
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "solution_lifecycle",
        "action": "read",
    }]
    assert [query for query, _ in connection.operations[:3]] == [
        "SET TRANSACTION READ ONLY",
        "SET LOCAL statement_timeout = '8s'",
        "SET LOCAL lock_timeout = '2s'",
    ]
    assert "list_location_solution_learning" in connection.operations[-1][0]
    assert connection.operations[-1][1] == (LOCATION_ID, 3, 5)
    assert len(result["learning"]) == 2
    assert result["has_more"] is True
    assert result["next_offset"] == 7
    assert result["learning"][0]["decision_status"] == "accepted"
    assert not {
        "source_replication_id", "finding", "recommended_action",
        "affected_assumptions", "affected_metrics", "evidence", "owner_party_id",
    }.intersection(result["learning"][0])
    assert connection.rolled_back and connection.closed


@pytest.mark.parametrize("limit,offset", [(0, 0), (51, 0), ("2.0", 0), (2, -1), (2, 10001)])
def test_learning_list_rejects_invalid_page_before_database_access(limit, offset):
    with pytest.raises(reads.SolutionLifecycleReadInvalid):
        reads.list_location_solution_learning(
            OPERATOR_ID, LOCATION_ID, limit=limit, offset=offset,
            connection_factory=lambda: pytest.fail("invalid page opened a connection"),
        )


def test_learning_context_denial_rolls_back_without_projection_call():
    connection = _Connection()

    def deny(*_args, **_kwargs):
        raise TenantContextDenied("denied")

    with patch.object(reads, "set_operator_tenant_context", deny):
        with pytest.raises(TenantContextDenied):
            reads.list_location_solution_learning(
                OPERATOR_ID, LOCATION_ID, connection_factory=lambda: connection,
            )

    assert not any("list_location_solution_learning" in query
                   for query, _ in connection.operations)
    assert connection.rolled_back and connection.closed


def test_learning_route_policy_uses_exact_solution_location_read_grant():
    path = f"/operator/api/solution-lifecycle/{LOCATION_ID}/learning"
    assert auth_route_policy("GET", path, enabled=True) == {
        "resource": "solution_lifecycle",
        "action": "read",
        "public": False,
        "location_id": LOCATION_ID,
        "scope_required": True,
        "operator_auth": True,
    }
    assert auth_route_policy("POST", path, enabled=True) is None
    assert auth_route_policy("GET", path + "/extra", enabled=True) is None


def test_learning_http_route_is_no_store_and_oidc_disabled_fails_closed(monkeypatch):
    from services.gateway.solution_lifecycle_routes import register_solution_lifecycle_routes

    learning = {
        "solution_id": "c0000000-0000-4000-8000-000000000001",
        "learning_record_id": "a3000000-0000-4000-8000-000000000001",
        "lesson_type": "validated_assumption",
        "decision_status": "accepted",
    }
    monkeypatch.setattr(
        "services.gateway.solution_lifecycle_reads.list_location_solution_learning",
        lambda *_args, **_kwargs: {
            "location_id": LOCATION_ID, "offset": 0, "learning": [learning],
            "has_more": False, "next_offset": None,
        },
    )
    app = FastAPI()
    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_solution_lifecycle_routes(router, object(), run_in_threadpool,
                                        SimpleNamespace(Error=Exception))
    app.include_router(router)

    @app.middleware("http")
    async def add_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    path = f"/operator/api/solution-lifecycle/{LOCATION_ID}/learning"
    with TestClient(app) as client:
        response = client.get(path, params={"limit": "10"})
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert response.json()["learning"][0]["decision_status"] == "accepted"

    disabled = FastAPI()
    disabled_router = APIRouter()
    register_solution_lifecycle_routes(disabled_router, None, run_in_threadpool,
                                        SimpleNamespace(Error=Exception))
    disabled.include_router(disabled_router)
    with TestClient(disabled) as client:
        no_oidc = client.get(path)
    assert no_oidc.status_code == 404
    assert no_oidc.headers["cache-control"] == "no-store"


def test_retirement_list_uses_signed_context_bounded_page_and_allowlisted_status():
    columns = (
        "solution_id", "solution_name", "solution_type", "current_stage",
        "solution_status", "retirement_id", "retirement_type", "retirement_status",
        "has_human_approval", "approved_at", "effective_at",
        "post_retirement_review_at", "created_at",
    )
    row = (
        "c0000000-0000-4000-8000-000000000001", "Soil cover", "practice",
        "retiring", "active", "a4000000-0000-4000-8000-000000000001",
        "superseded", "approved", True, "2026-10-16T00:00:00Z",
        "2026-10-20T00:00:00Z", "2027-01-20", "2026-10-15T00:00:00Z",
    )
    connection = _Connection(rows=[row, row, row], columns=columns)
    contexts = []

    def set_context(conn, **kwargs):
        assert conn is connection
        contexts.append(kwargs)

    with patch.object(reads, "set_operator_tenant_context", set_context):
        result = reads.list_location_solution_retirements(
            OPERATOR_ID, LOCATION_ID, limit="2", offset="5",
            connection_factory=lambda: connection,
        )

    assert contexts == [{
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "solution_lifecycle",
        "action": "read",
    }]
    assert [query for query, _ in connection.operations[:3]] == [
        "SET TRANSACTION READ ONLY",
        "SET LOCAL statement_timeout = '8s'",
        "SET LOCAL lock_timeout = '2s'",
    ]
    assert "list_location_solution_retirements" in connection.operations[-1][0]
    assert connection.operations[-1][1] == (LOCATION_ID, 3, 5)
    assert len(result["retirements"]) == 2
    assert result["has_more"] is True
    assert result["next_offset"] == 7
    assert result["retirements"][0]["has_human_approval"] is True
    assert not {
        "trigger_reason", "evidence_refs", "affected_users", "dependent_solutions",
        "replacement_solution_id", "migration_plan", "residual_risk",
        "data_preservation_plan", "compensation_or_remedy_plan", "approved_by_party_id",
    }.intersection(result["retirements"][0])
    assert connection.rolled_back and connection.closed


@pytest.mark.parametrize("limit,offset", [(0, 0), (51, 0), ("2.0", 0), (2, -1), (2, 10001)])
def test_retirement_list_rejects_invalid_page_before_database_access(limit, offset):
    with pytest.raises(reads.SolutionLifecycleReadInvalid):
        reads.list_location_solution_retirements(
            OPERATOR_ID, LOCATION_ID, limit=limit, offset=offset,
            connection_factory=lambda: pytest.fail("invalid page opened a connection"),
        )


def test_retirement_context_denial_rolls_back_without_projection_call():
    connection = _Connection()

    def deny(*_args, **_kwargs):
        raise TenantContextDenied("denied")

    with patch.object(reads, "set_operator_tenant_context", deny):
        with pytest.raises(TenantContextDenied):
            reads.list_location_solution_retirements(
                OPERATOR_ID, LOCATION_ID, connection_factory=lambda: connection,
            )

    assert not any("list_location_solution_retirements" in query
                   for query, _ in connection.operations)
    assert connection.rolled_back and connection.closed


def test_retirement_route_policy_uses_exact_solution_location_read_grant():
    path = f"/operator/api/solution-lifecycle/{LOCATION_ID}/retirements"
    assert auth_route_policy("GET", path, enabled=True) == {
        "resource": "solution_lifecycle",
        "action": "read",
        "public": False,
        "location_id": LOCATION_ID,
        "scope_required": True,
        "operator_auth": True,
    }
    assert auth_route_policy("POST", path, enabled=True) is None
    assert auth_route_policy("GET", path + "/extra", enabled=True) is None


def test_retirement_http_route_is_no_store_and_oidc_disabled_fails_closed(monkeypatch):
    from services.gateway.solution_lifecycle_routes import register_solution_lifecycle_routes

    retirement = {
        "solution_id": "c0000000-0000-4000-8000-000000000001",
        "retirement_id": "a4000000-0000-4000-8000-000000000001",
        "retirement_type": "superseded",
        "retirement_status": "approved",
        "has_human_approval": True,
    }
    monkeypatch.setattr(
        "services.gateway.solution_lifecycle_reads.list_location_solution_retirements",
        lambda *_args, **_kwargs: {
            "location_id": LOCATION_ID, "offset": 0, "retirements": [retirement],
            "has_more": False, "next_offset": None,
        },
    )
    app = FastAPI()
    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_solution_lifecycle_routes(router, object(), run_in_threadpool,
                                        SimpleNamespace(Error=Exception))
    app.include_router(router)

    @app.middleware("http")
    async def add_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    path = f"/operator/api/solution-lifecycle/{LOCATION_ID}/retirements"
    with TestClient(app) as client:
        response = client.get(path, params={"limit": "10"})
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert response.json()["retirements"][0]["has_human_approval"] is True

    disabled = FastAPI()
    disabled_router = APIRouter()
    register_solution_lifecycle_routes(disabled_router, None, run_in_threadpool,
                                        SimpleNamespace(Error=Exception))
    disabled.include_router(disabled_router)
    with TestClient(disabled) as client:
        no_oidc = client.get(path)
    assert no_oidc.status_code == 404
    assert no_oidc.headers["cache-control"] == "no-store"
