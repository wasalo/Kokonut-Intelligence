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
        return (self.connection.row,)

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
