"""Authorization and transaction contract for Comprehensive Status reads."""

from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi import APIRouter, FastAPI
from starlette.testclient import TestClient

from services.common.tenant_context import TenantContextDenied
from services.gateway import comprehensive_status_reads as reads
from services.gateway.operator_auth import auth_route_policy

OPERATOR_ID = str(uuid4())
LOCATION_ID = str(uuid4())


class _Connection:
    autocommit = False

    def __init__(self):
        self.operations = []
        self.rolled_back = 0
        self.closed = False

    def cursor(self):
        return _Cursor(self)

    def rollback(self):
        self.rolled_back += 1

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


def test_read_sets_tenant_context_before_generating_one_location_report():
    connection = _Connection()
    operations = connection.operations
    report = {"report_type": "comprehensive_status", "locations": []}

    def set_context(conn, **kwargs):
        assert conn is connection
        operations.append(("tenant_context", kwargs))

    def generate(conn, **kwargs):
        assert conn is connection
        operations.append(("generate", kwargs))
        return report

    with (
        patch.object(reads, "set_operator_tenant_context", set_context),
        patch("services.export.reports.state.generate_comprehensive_status", generate),
    ):
        result = reads.get_location_comprehensive_status(
            OPERATOR_ID,
            LOCATION_ID,
            period_start="2026-01-01",
            period_end="2026-06-30",
            connection_factory=lambda: connection,
        )

    assert result is report
    assert operations[:3] == [
        ("SET TRANSACTION READ ONLY", None),
        ("SET LOCAL statement_timeout = '8s'", None),
        ("SET LOCAL lock_timeout = '2s'", None),
    ]
    assert operations[3] == (
        "tenant_context",
        {
            "operator_id": OPERATOR_ID,
            "location_id": LOCATION_ID,
            "resource": "comprehensive_status",
            "action": "read",
        },
    )
    assert operations[4] == (
        "generate",
        {
            "location_id": LOCATION_ID,
            "period_start": "2026-01-01",
            "period_end": "2026-06-30",
        },
    )
    assert connection.rolled_back == 1
    assert connection.closed


@pytest.mark.parametrize(
    "kwargs",
    [
        {"operator_id": "bad", "location_id": LOCATION_ID},
        {"operator_id": OPERATOR_ID, "location_id": "bad"},
        {"operator_id": OPERATOR_ID, "location_id": LOCATION_ID, "period_start": "2026-1-1"},
        {"operator_id": OPERATOR_ID, "location_id": LOCATION_ID, "period_end": "not-a-date"},
        {
            "operator_id": OPERATOR_ID,
            "location_id": LOCATION_ID,
            "period_start": "2026-06-01",
            "period_end": "2026-05-31",
        },
    ],
)
def test_invalid_identity_or_period_fails_before_database_access(kwargs):
    with pytest.raises(reads.ComprehensiveStatusReadInvalid):
        reads.get_location_comprehensive_status(
            connection_factory=lambda: pytest.fail("invalid input must fail before DB access"),
            **kwargs,
        )


def test_tenant_denial_prevents_report_generation_and_closes_connection():
    connection = _Connection()

    with (
        patch.object(reads, "set_operator_tenant_context", side_effect=TenantContextDenied("denied")),
        patch("services.export.reports.state.generate_comprehensive_status") as generate,
        pytest.raises(TenantContextDenied),
    ):
        reads.get_location_comprehensive_status(
            OPERATOR_ID,
            LOCATION_ID,
            connection_factory=lambda: connection,
        )

    generate.assert_not_called()
    assert connection.rolled_back == 2
    assert connection.closed


def test_oversized_report_is_rejected_and_connection_is_closed(monkeypatch):
    connection = _Connection()
    monkeypatch.setattr(reads, "MAX_COMPREHENSIVE_STATUS_BYTES", 8)
    monkeypatch.setattr(reads, "set_operator_tenant_context", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        "services.export.reports.state.generate_comprehensive_status",
        lambda *_args, **_kwargs: {"large": "payload"},
    )

    with pytest.raises(reads.ComprehensiveStatusPayloadTooLarge):
        reads.get_location_comprehensive_status(
            OPERATOR_ID,
            LOCATION_ID,
            connection_factory=lambda: connection,
        )

    assert connection.closed


def test_route_policy_requires_exact_location_comprehensive_status_read():
    path = f"/operator/api/comprehensive-status/{LOCATION_ID}"
    assert auth_route_policy("GET", path, enabled=True) == {
        "resource": "comprehensive_status",
        "action": "read",
        "public": False,
        "location_id": LOCATION_ID,
        "scope_required": True,
        "operator_auth": True,
    }
    assert auth_route_policy("POST", path, enabled=True) is None
    assert auth_route_policy("GET", path + "/all", enabled=True) is None


def test_http_route_is_no_store_and_requires_operator_session(monkeypatch):
    from services.gateway.comprehensive_status_routes import register_comprehensive_status_routes

    monkeypatch.setattr(
        "services.gateway.comprehensive_status_reads.get_location_comprehensive_status",
        lambda *_args, **_kwargs: {
            "report_type": "comprehensive_status",
            "locations": [{"location_id": LOCATION_ID}],
        },
    )
    app = FastAPI()
    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_comprehensive_status_routes(
        router, object(), run_in_threadpool, SimpleNamespace(Error=Exception)
    )
    app.include_router(router)

    @app.middleware("http")
    async def add_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    with TestClient(app) as client:
        response = client.get(f"/operator/api/comprehensive-status/{LOCATION_ID}")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert response.json()["report_type"] == "comprehensive_status"


def test_http_route_returns_404_when_oidc_is_disabled():
    from services.gateway.comprehensive_status_routes import register_comprehensive_status_routes

    app = FastAPI()
    router = APIRouter()

    async def run_in_threadpool(*_args, **_kwargs):
        pytest.fail("disabled OIDC must not invoke the read service")

    register_comprehensive_status_routes(
        router, None, run_in_threadpool, SimpleNamespace(Error=Exception)
    )
    app.include_router(router)
    with TestClient(app) as client:
        response = client.get(f"/operator/api/comprehensive-status/{LOCATION_ID}")

    assert response.status_code == 404
    assert response.headers["cache-control"] == "no-store"


def test_http_route_maps_tenant_grant_denial_to_no_store_403(monkeypatch):
    from services.gateway.comprehensive_status_routes import register_comprehensive_status_routes

    def deny(*_args, **_kwargs):
        raise TenantContextDenied("denied")

    monkeypatch.setattr(
        "services.gateway.comprehensive_status_reads.get_location_comprehensive_status", deny
    )
    app = FastAPI()
    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_comprehensive_status_routes(
        router, object(), run_in_threadpool, SimpleNamespace(Error=Exception)
    )
    app.include_router(router)

    @app.middleware("http")
    async def add_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    with TestClient(app) as client:
        response = client.get(f"/operator/api/comprehensive-status/{LOCATION_ID}")

    assert response.status_code == 403
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {
        "error": "A tenant-qualified Comprehensive Status read grant is required"
    }


def test_http_route_caps_final_encoded_response(monkeypatch):
    from services.gateway.comprehensive_status_routes import register_comprehensive_status_routes

    monkeypatch.setattr(reads, "MAX_COMPREHENSIVE_STATUS_BYTES", 8)
    monkeypatch.setattr(
        "services.gateway.comprehensive_status_reads.get_location_comprehensive_status",
        lambda *_args, **_kwargs: {"large": "payload"},
    )
    app = FastAPI()
    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_comprehensive_status_routes(
        router, object(), run_in_threadpool, SimpleNamespace(Error=Exception)
    )
    app.include_router(router)

    @app.middleware("http")
    async def add_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    with TestClient(app) as client:
        response = client.get(f"/operator/api/comprehensive-status/{LOCATION_ID}")

    assert response.status_code == 413
    assert response.headers["cache-control"] == "no-store"
