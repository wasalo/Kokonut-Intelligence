"""Tests for the location-scoped sequential evidence Gateway projection."""

from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest

from services.common.tenant_context import TenantContextDenied
from services.gateway import sequential_decision_reads as reads
from services.gateway.operator_auth import auth_route_policy

pytest.importorskip("fastapi")
from fastapi import APIRouter, FastAPI  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

OPERATOR_ID = str(uuid4())
LOCATION_ID = str(uuid4())
SUMMARY = {
    "hypothesis_count": 3,
    "hypothesis_status_counts": {"active": 1, "resolved": 1, "draft": 1, "retired": 0},
    "evidence_event_count": 3,
    "evidence_quality_counts": {"verified": 1, "provisional": 1, "rejected": 1},
    "applied_evidence_event_count": 2,
    "posterior_update_count": 2,
    "latest_decision_action_counts": {"continue": 1, "insufficient_evidence": 1},
}
TIMELINE = {
    "limit": 2,
    "offset": 0,
    "items": [
        {
            "hypothesis_sequence": 1,
            "subject_type": "strategy_plan",
            "evidence_sequence": 1,
            "observed_at": "2026-10-01T00:00:00+00:00",
            "ingested_at": "2026-10-01T01:00:00+00:00",
            "evidence_class": "field_observation",
            "quality_status": "verified",
            "posterior_update_sequence": 1,
            "calculation_version": "odds-v1",
            "posterior_updated_at": "2026-10-01T02:00:00+00:00",
        },
        {
            "hypothesis_sequence": 1,
            "subject_type": "strategy_plan",
            "evidence_sequence": 2,
            "observed_at": "2026-10-02T00:00:00+00:00",
            "ingested_at": "2026-10-02T01:00:00+00:00",
            "evidence_class": "monitoring_report",
            "quality_status": "provisional",
            "posterior_update_sequence": None,
            "calculation_version": None,
            "posterior_updated_at": None,
        },
    ],
    "has_more": True,
    "next_offset": 2,
}


class _Connection:
    def __init__(self, row):
        self.row = row
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

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def execute(self, query, params=None):
        self.connection.operations.append((" ".join(query.split()), params))

    def fetchone(self):
        return (self.connection.row,)


def test_summary_sets_exact_tenant_context_and_uses_read_only_connection():
    connection = _Connection(SUMMARY)
    contexts = []

    def set_context(conn, **kwargs):
        assert conn is connection
        contexts.append(kwargs)

    with patch.object(reads, "set_operator_tenant_context", set_context):
        result = reads.get_location_sequential_decision_summary(
            OPERATOR_ID, LOCATION_ID, connection_factory=lambda: connection,
        )

    assert contexts == [{
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "sequential_evidence",
        "action": "read",
    }]
    assert [query for query, _ in connection.operations[:3]] == [
        "SET TRANSACTION READ ONLY",
        "SET LOCAL statement_timeout = '8s'",
        "SET LOCAL lock_timeout = '2s'",
    ]
    assert "location_sequential_decision_summary" in connection.operations[-1][0]
    assert connection.operations[-1][1] == (LOCATION_ID,)
    assert result == {"location_id": LOCATION_ID, **SUMMARY}
    assert connection.rolled_back and connection.closed


@pytest.mark.parametrize("operator_id,location_id", [
    ("not-a-uuid", LOCATION_ID), (OPERATOR_ID, "not-a-uuid"),
])
def test_invalid_identity_fails_before_database_access(operator_id, location_id):
    with pytest.raises(reads.SequentialDecisionReadInvalid):
        reads.get_location_sequential_decision_summary(
            operator_id, location_id,
            connection_factory=lambda: pytest.fail("invalid identity must fail before DB access"),
        )


def test_tenant_denial_rolls_back_without_projection_call():
    connection = _Connection(SUMMARY)

    def deny(*_args, **_kwargs):
        raise TenantContextDenied("denied")

    with patch.object(reads, "set_operator_tenant_context", deny):
        with pytest.raises(TenantContextDenied):
            reads.get_location_sequential_decision_summary(
                OPERATOR_ID, LOCATION_ID, connection_factory=lambda: connection,
            )

    assert not any("location_sequential_decision_summary" in query
                   for query, _ in connection.operations)
    assert connection.rolled_back and connection.closed


def test_projection_contract_contains_only_aggregate_status_and_count_fields():
    assert "evidence_quality_counts" in SUMMARY
    assert "applied_evidence_event_count" in SUMMARY
    assert "posterior_update_count" in SUMMARY
    assert "latest_decision_action_counts" in SUMMARY
    private_fields = ("statement", "source_ref", "event_id", "likelihood", "probability", "party_id")
    assert not any(field in " ".join(SUMMARY).lower() for field in private_fields)


def test_route_policy_requires_exact_location_sequential_evidence_read_grant():
    path = f"/operator/api/sequential-evidence/{LOCATION_ID}/summary"
    assert auth_route_policy("GET", path, enabled=True) == {
        "resource": "sequential_evidence",
        "action": "read",
        "public": False,
        "location_id": LOCATION_ID,
        "scope_required": True,
        "operator_auth": True,
    }
    assert auth_route_policy("POST", path, enabled=True) is None
    assert auth_route_policy("GET", path + "/extra", enabled=True) is None


def test_timeline_sets_read_only_tenant_context_and_bounded_page():
    connection = _Connection(TIMELINE)
    contexts = []

    def set_context(conn, **kwargs):
        assert conn is connection
        contexts.append(kwargs)

    with patch.object(reads, "set_operator_tenant_context", set_context):
        result = reads.list_location_sequential_evidence_timeline(
            OPERATOR_ID, LOCATION_ID, limit="2", offset="0",
            connection_factory=lambda: connection,
        )

    assert contexts == [{
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "sequential_evidence",
        "action": "read",
    }]
    assert [query for query, _ in connection.operations[:3]] == [
        "SET TRANSACTION READ ONLY",
        "SET LOCAL statement_timeout = '8s'",
        "SET LOCAL lock_timeout = '2s'",
    ]
    assert "location_sequential_evidence_timeline" in connection.operations[-1][0]
    assert connection.operations[-1][1] == (LOCATION_ID, 2, 0)
    assert result == {"location_id": LOCATION_ID, **TIMELINE}
    assert connection.rolled_back and connection.closed


@pytest.mark.parametrize(("limit", "offset"), [
    (0, 0), (51, 0), ("1.5", 0), (1, -1), (1, 10001), (True, 0),
])
def test_invalid_timeline_page_fails_before_database_access(limit, offset):
    with pytest.raises(reads.SequentialDecisionReadInvalid):
        reads.list_location_sequential_evidence_timeline(
            OPERATOR_ID, LOCATION_ID, limit=limit, offset=offset,
            connection_factory=lambda: pytest.fail("invalid page must fail before DB access"),
        )


def test_timeline_response_size_limit_rolls_back_and_closes():
    oversized = {**TIMELINE, "items": [{"field": "x" * reads._MAX_RESPONSE_BYTES}]}
    connection = _Connection(oversized)
    with patch.object(reads, "set_operator_tenant_context", lambda *_args, **_kwargs: None):
        with pytest.raises(reads.SequentialDecisionResponseTooLarge):
            reads.list_location_sequential_evidence_timeline(
                OPERATOR_ID, LOCATION_ID, connection_factory=lambda: connection,
            )
    assert connection.rolled_back and connection.closed


def test_timeline_route_policy_requires_exact_location_read_grant():
    path = f"/operator/api/sequential-evidence/{LOCATION_ID}/events"
    assert auth_route_policy("GET", path, enabled=True) == {
        "resource": "sequential_evidence",
        "action": "read",
        "public": False,
        "location_id": LOCATION_ID,
        "scope_required": True,
        "operator_auth": True,
    }
    assert auth_route_policy("POST", path, enabled=True) is None
    assert auth_route_policy("GET", path + "/extra", enabled=True) is None


def test_timeline_route_is_no_store_and_forwards_pagination(monkeypatch):
    from services.gateway.sequential_decision_routes import register_sequential_decision_routes

    calls = []

    def timeline(*args, **kwargs):
        calls.append((args, kwargs))
        return {"location_id": LOCATION_ID, **TIMELINE}

    monkeypatch.setattr(
        "services.gateway.sequential_decision_reads.list_location_sequential_evidence_timeline",
        timeline,
    )
    app = FastAPI()
    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_sequential_decision_routes(router, object(), run_in_threadpool,
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
            f"/operator/api/sequential-evidence/{LOCATION_ID}/events?limit=2&offset=0"
        )
        invalid_limit_low = client.get(
            f"/operator/api/sequential-evidence/{LOCATION_ID}/events?limit=0"
        )
        invalid_limit_high = client.get(
            f"/operator/api/sequential-evidence/{LOCATION_ID}/events?limit=51"
        )
        invalid_offset_low = client.get(
            f"/operator/api/sequential-evidence/{LOCATION_ID}/events?offset=-1"
        )
        invalid_offset_high = client.get(
            f"/operator/api/sequential-evidence/{LOCATION_ID}/events?offset=10001"
        )
        invalid_integer = client.get(
            f"/operator/api/sequential-evidence/{LOCATION_ID}/events?limit=abc"
        )

    openapi = app.openapi()
    event_operation = openapi["paths"]["/operator/api/sequential-evidence/{location_id}/events"]["get"]
    parameters = {parameter["name"]: parameter for parameter in event_operation["parameters"]}
    assert parameters["limit"]["schema"]["minimum"] == 1
    assert parameters["limit"]["schema"]["maximum"] == 50
    assert parameters["limit"]["schema"]["default"] == 25
    assert parameters["offset"]["schema"]["minimum"] == 0
    assert parameters["offset"]["schema"]["maximum"] == 10000
    assert parameters["offset"]["schema"]["default"] == 0

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert response.json()["items"] == TIMELINE["items"]
    assert calls == [
        ((OPERATOR_ID, LOCATION_ID), {"limit": 2, "offset": 0}),
    ]
    assert invalid_limit_low.status_code == 422
    assert invalid_limit_high.status_code == 422
    assert invalid_offset_low.status_code == 422
    assert invalid_offset_high.status_code == 422
    assert invalid_integer.status_code == 422


def test_timeline_route_fails_closed_without_oidc(monkeypatch):
    from services.gateway.sequential_decision_routes import register_sequential_decision_routes

    monkeypatch.setattr(
        "services.gateway.sequential_decision_reads.list_location_sequential_evidence_timeline",
        lambda *_args, **_kwargs: pytest.fail("OIDC-disabled timeline must not query data"),
    )
    app = FastAPI()
    router = APIRouter()
    register_sequential_decision_routes(router, None, lambda *_args: None,
                                        SimpleNamespace(Error=Exception))
    app.include_router(router)

    with TestClient(app) as client:
        response = client.get(f"/operator/api/sequential-evidence/{LOCATION_ID}/events")

    assert response.status_code == 404
    assert response.headers["cache-control"] == "no-store"


def test_http_projection_is_no_store_and_operator_authenticated(monkeypatch):
    from services.gateway.sequential_decision_routes import register_sequential_decision_routes

    monkeypatch.setattr(
        "services.gateway.sequential_decision_reads.get_location_sequential_decision_summary",
        lambda *_args, **_kwargs: {"location_id": LOCATION_ID, **SUMMARY},
    )
    app = FastAPI()
    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_sequential_decision_routes(router, object(), run_in_threadpool,
                                        SimpleNamespace(Error=Exception))
    app.include_router(router)

    @app.middleware("http")
    async def add_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    with TestClient(app) as client:
        response = client.get(f"/operator/api/sequential-evidence/{LOCATION_ID}/summary")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert response.json()["hypothesis_count"] == 3


def test_http_projection_fails_closed_when_oidc_is_disabled(monkeypatch):
    from services.gateway.sequential_decision_routes import register_sequential_decision_routes

    monkeypatch.setattr(
        "services.gateway.sequential_decision_reads.get_location_sequential_decision_summary",
        lambda *_args, **_kwargs: pytest.fail("disabled OIDC must not query the projection"),
    )
    app = FastAPI()
    router = APIRouter()
    register_sequential_decision_routes(router, None, lambda *_args: None,
                                        SimpleNamespace(Error=Exception))
    app.include_router(router)

    with TestClient(app) as client:
        response = client.get(f"/operator/api/sequential-evidence/{LOCATION_ID}/summary")

    assert response.status_code == 404
    assert response.headers["cache-control"] == "no-store"


def test_http_projection_maps_tenant_denial_to_forbidden(monkeypatch):
    from services.gateway.sequential_decision_routes import register_sequential_decision_routes

    def deny(*_args, **_kwargs):
        raise TenantContextDenied("denied")

    monkeypatch.setattr(
        "services.gateway.sequential_decision_reads.get_location_sequential_decision_summary", deny,
    )
    app = FastAPI()
    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_sequential_decision_routes(router, object(), run_in_threadpool,
                                        SimpleNamespace(Error=Exception))
    app.include_router(router)

    @app.middleware("http")
    async def add_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    with TestClient(app) as client:
        response = client.get(f"/operator/api/sequential-evidence/{LOCATION_ID}/summary")

    assert response.status_code == 403
    assert response.headers["cache-control"] == "no-store"
