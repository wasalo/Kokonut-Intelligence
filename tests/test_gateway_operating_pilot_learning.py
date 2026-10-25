"""Private, bounded CAP-037 learning-plan history regressions."""

from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest

from services.common.tenant_context import TenantContextDenied
from services.gateway import operating_pilot_reads as reads
from services.gateway.operator_auth import auth_route_policy

pytest.importorskip("fastapi")
from fastapi import APIRouter, FastAPI  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

OPERATOR_ID = str(uuid4())
LOCATION_ID = str(uuid4())


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


def test_own_learning_plans_use_read_only_exact_tenant_context_and_cleanup():
    page = {"items": [{"title": "Private goal"}], "has_more": False}
    connection = _Connection(page)
    contexts = []

    def set_context(conn, **kwargs):
        assert conn is connection
        contexts.append(kwargs)

    with patch.object(reads, "set_operator_tenant_context", set_context):
        result = reads.get_location_operating_pilot_own_learning_plans(
            OPERATOR_ID,
            LOCATION_ID,
            limit=7,
            offset=14,
            connection_factory=lambda: connection,
        )

    assert contexts == [{
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "operating_pilot",
        "action": "read_own",
    }]
    assert [query for query, _ in connection.operations[:3]] == [
        "SET TRANSACTION READ ONLY",
        "SET LOCAL statement_timeout = '8s'",
        "SET LOCAL lock_timeout = '2s'",
    ]
    assert "location_operating_pilot_own_learning_plans" in connection.operations[-1][0]
    assert connection.operations[-1][1] == (LOCATION_ID, 7, 14)
    assert result == {"location_id": LOCATION_ID, **page}
    assert connection.rolled_back and connection.closed


@pytest.mark.parametrize("limit,offset", [
    (0, 0), (51, 0), (True, 0), (25, -1), (25, 10001), (25, False),
])
def test_own_learning_plans_reject_invalid_page_before_database_access(limit, offset):
    with pytest.raises(reads.OperatingPilotReadInvalid):
        reads.get_location_operating_pilot_own_learning_plans(
            OPERATOR_ID,
            LOCATION_ID,
            limit=limit,
            offset=offset,
            connection_factory=lambda: pytest.fail("invalid page must fail before DB access"),
        )


def test_own_learning_plans_tenant_denial_rolls_back_without_projection():
    connection = _Connection({})

    def deny(*_args, **_kwargs):
        raise TenantContextDenied("denied")

    with patch.object(reads, "set_operator_tenant_context", deny):
        with pytest.raises(TenantContextDenied):
            reads.get_location_operating_pilot_own_learning_plans(
                OPERATOR_ID,
                LOCATION_ID,
                connection_factory=lambda: connection,
            )
    assert not any(
        "location_operating_pilot_own_learning_plans" in query
        for query, _ in connection.operations
    )
    assert connection.rolled_back and connection.closed


def test_learning_plan_history_policy_is_exact_location_and_read_own_only():
    path = f"/operator/api/operating-pilot/{LOCATION_ID}/my-learning-plans"
    assert auth_route_policy("GET", path, enabled=True) == {
        "resource": "operating_pilot",
        "action": "read_own",
        "public": False,
        "location_id": LOCATION_ID,
        "scope_required": True,
        "operator_auth": True,
    }
    assert auth_route_policy("POST", path, enabled=True) is None
    assert auth_route_policy("GET", path, enabled=False) is None


def test_http_own_learning_plans_are_no_store_and_paginated(monkeypatch):
    from services.gateway.operating_pilot_routes import register_operating_pilot_routes

    calls = []
    page = {"location_id": LOCATION_ID, "items": [], "has_more": False}
    monkeypatch.setattr(
        "services.gateway.operating_pilot_reads.get_location_operating_pilot_own_learning_plans",
        lambda *args, **kwargs: calls.append((args, kwargs)) or page,
    )
    app = FastAPI()
    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_operating_pilot_routes(
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
        response = client.get(
            f"/operator/api/operating-pilot/{LOCATION_ID}/my-learning-plans?limit=7&offset=14"
        )
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert response.json() == page
    assert calls == [((OPERATOR_ID, LOCATION_ID), {"limit": 7, "offset": 14})]


def test_http_learning_plans_fail_closed_when_oidc_is_disabled(monkeypatch):
    from services.gateway.operating_pilot_routes import register_operating_pilot_routes

    monkeypatch.setattr(
        "services.gateway.operating_pilot_reads.get_location_operating_pilot_own_learning_plans",
        lambda *_args, **_kwargs: pytest.fail("disabled OIDC must not query private plans"),
    )
    app = FastAPI()
    router = APIRouter()
    register_operating_pilot_routes(router, None, lambda *_args: None,
                                    SimpleNamespace(Error=Exception))
    app.include_router(router)
    with TestClient(app) as client:
        response = client.get(
            f"/operator/api/operating-pilot/{LOCATION_ID}/my-learning-plans"
        )
    assert response.status_code == 404
    assert response.headers["cache-control"] == "no-store"


def test_own_coaching_history_uses_coach_scope_and_read_only_transaction():
    page = {"items": [{"focus": "Private synthetic coaching"}], "has_more": False}
    connection = _Connection(page)
    contexts = []

    with patch.object(
        reads,
        "set_operator_tenant_context",
        lambda conn, **kwargs: contexts.append((conn, kwargs)),
    ):
        result = reads.get_location_operating_pilot_own_coaching_sessions(
            OPERATOR_ID, LOCATION_ID, limit=5, offset=10,
            connection_factory=lambda: connection,
        )

    assert contexts == [(connection, {
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "operating_pilot",
        "action": "coach",
    })]
    assert [query for query, _ in connection.operations[:3]] == [
        "SET TRANSACTION READ ONLY",
        "SET LOCAL statement_timeout = '8s'",
        "SET LOCAL lock_timeout = '2s'",
    ]
    assert "location_operating_pilot_own_coaching_sessions" in connection.operations[-1][0]
    assert connection.operations[-1][1] == (LOCATION_ID, 5, 10)
    assert result == {"location_id": LOCATION_ID, **page}
    assert connection.rolled_back and connection.closed


def test_coaching_history_route_is_private_no_store_and_coach_grant_gated(monkeypatch):
    from services.gateway.operating_pilot_routes import register_operating_pilot_routes

    page = {"location_id": LOCATION_ID, "items": [], "has_more": False}
    calls = []
    monkeypatch.setattr(
        "services.gateway.operating_pilot_reads.get_location_operating_pilot_own_coaching_sessions",
        lambda *args, **kwargs: calls.append((args, kwargs)) or page,
    )
    app = FastAPI()
    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_operating_pilot_routes(
        router, object(), run_in_threadpool, SimpleNamespace(Error=Exception)
    )
    app.include_router(router)

    @app.middleware("http")
    async def add_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    path = f"/operator/api/operating-pilot/{LOCATION_ID}/my-coaching-sessions"
    with TestClient(app) as client:
        response = client.get(f"{path}?limit=5&offset=10")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert response.json() == page
    assert calls == [((OPERATOR_ID, LOCATION_ID), {"limit": 5, "offset": 10})]
    assert auth_route_policy("GET", path, enabled=True) == {
        "resource": "operating_pilot",
        "action": "coach",
        "public": False,
        "location_id": LOCATION_ID,
        "scope_required": True,
        "operator_auth": True,
    }
    assert auth_route_policy("POST", path, enabled=True) is None
