"""Exact-location solution creation and route authorization contracts."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest

from services.common.tenant_context import TenantContextDenied
from services.gateway import solution_lifecycle_actions as actions
from services.gateway.operator_auth import auth_route_policy

pytest.importorskip("fastapi")
from fastapi import APIRouter, FastAPI  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

OPERATOR_ID = str(uuid4())
LOCATION_ID = str(uuid4())
REQUEST_ID = str(uuid4())
CREATED = {
    "solution_id": str(uuid4()),
    "lifecycle_event_id": str(uuid4()),
    "canonical_key": "water.harvesting.v1",
    "solution_name": "Water harvesting practice",
    "solution_type": "practice",
    "current_stage": "discovered",
    "solution_status": "active",
    "created_at": "2026-10-20T12:00:00+00:00",
    "replayed": False,
}
ROUTE_CREATED = {
    **CREATED,
    "created_at": datetime(2026, 10, 20, 12, 0, tzinfo=timezone.utc),
}
BODY = {
    "request_id": REQUEST_ID,
    "canonical_key": "water.harvesting.v1",
    "name": "Water harvesting practice",
    "solution_type": "practice",
    "problem_statement": "Seasonal runoff is lost before it can support dry-season production.",
    "theory_of_change": "Small earthworks slow runoff and improve infiltration.",
    "baseline_alternative": "Current practice drains the plot.",
    "risk_class": "medium",
    "reversibility": "high",
    "rationale": "Record a location-originated candidate for governed discovery.",
    "evidence": [{"source": "field-note:reviewed"}],
    "acknowledged": True,
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
            SimpleNamespace(name=name) for name in (connection.row or {})
        )

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def execute(self, query, params=None):
        self.connection.operations.append((" ".join(query.split()), params))

    def fetchone(self):
        return tuple(self.connection.row.values()) if self.connection.row else None


def test_create_action_sets_exact_create_context_and_calls_bounded_function():
    connection = _Connection(CREATED)
    contexts = []

    def set_context(conn, **kwargs):
        assert conn is connection
        contexts.append(kwargs)

    with patch.object(actions, "set_operator_tenant_context", set_context):
        result = actions.create_location_solution(
            OPERATOR_ID,
            LOCATION_ID,
            REQUEST_ID,
            BODY["canonical_key"],
            BODY["name"],
            BODY["solution_type"],
            BODY["problem_statement"],
            BODY["rationale"],
            BODY["evidence"],
            theory_of_change=BODY["theory_of_change"],
            baseline_alternative=BODY["baseline_alternative"],
            risk_class=BODY["risk_class"],
            reversibility=BODY["reversibility"],
            acknowledged=True,
            connection_factory=lambda: connection,
        )

    assert contexts == [{
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "solution_lifecycle",
        "action": "create",
    }]
    query, params = connection.operations[-1]
    assert "kokonut_security.create_location_solution" in query
    assert params == (
        LOCATION_ID,
        REQUEST_ID,
        BODY["canonical_key"],
        BODY["name"],
        BODY["solution_type"],
        BODY["problem_statement"],
        BODY["theory_of_change"],
        BODY["baseline_alternative"],
        BODY["risk_class"],
        BODY["reversibility"],
        BODY["rationale"],
        '[{"source":"field-note:reviewed"}]',
        True,
    )
    assert result == CREATED
    assert connection.committed and connection.closed and not connection.rolled_back


@pytest.mark.parametrize(
    "overrides",
    [
        {"canonical_key": "Bad Key"},
        {"solution_type": []},
        {"risk_class": {}},
        {"reversibility": None},
        {"name": " "},
        {"problem_statement": "\x00"},
        {"evidence": [float("nan")]},
        {"acknowledged": False},
    ],
)
def test_invalid_create_input_fails_before_opening_database(overrides):
    payload = {**BODY, **overrides}
    with pytest.raises(actions.SolutionLifecycleActionInvalid):
        actions.create_location_solution(
            OPERATOR_ID,
            LOCATION_ID,
            payload["request_id"],
            payload["canonical_key"],
            payload["name"],
            payload["solution_type"],
            payload["problem_statement"],
            payload["rationale"],
            payload["evidence"],
            risk_class=payload["risk_class"],
            reversibility=payload["reversibility"],
            acknowledged=payload["acknowledged"],
            connection_factory=lambda: pytest.fail("invalid input opened a database"),
        )


def test_action_rolls_back_and_closes_on_tenant_denial():
    connection = _Connection(CREATED)

    def deny(*_args, **_kwargs):
        raise TenantContextDenied("denied")

    with patch.object(actions, "set_operator_tenant_context", deny):
        with pytest.raises(TenantContextDenied):
            actions.create_location_solution(
                OPERATOR_ID, LOCATION_ID, REQUEST_ID, BODY["canonical_key"],
                BODY["name"], BODY["solution_type"], BODY["problem_statement"],
                BODY["rationale"], BODY["evidence"], acknowledged=True,
                connection_factory=lambda: connection,
            )
    assert connection.rolled_back and connection.closed and not connection.committed


def test_create_route_requires_exact_scoped_create_policy():
    path = f"/operator/api/solution-lifecycle/{LOCATION_ID}/solutions"
    assert auth_route_policy("POST", path, enabled=True) == {
        "resource": "solution_lifecycle",
        "action": "create",
        "public": False,
        "location_id": LOCATION_ID,
        "scope_required": True,
        "operator_auth": True,
    }
    assert auth_route_policy("GET", path, enabled=True) is None
    assert auth_route_policy("POST", path, enabled=False) is None


def test_create_route_is_no_store_strict_and_forwards_authenticated_operator(monkeypatch):
    from services.gateway import solution_lifecycle_actions
    from services.gateway.solution_lifecycle_routes import register_solution_lifecycle_routes

    calls = []

    def create(*args, **kwargs):
        calls.append((args, kwargs))
        return ROUTE_CREATED

    monkeypatch.setattr(solution_lifecycle_actions, "create_location_solution", create)
    app = FastAPI()
    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_solution_lifecycle_routes(
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
        response = client.post(
            f"/operator/api/solution-lifecycle/{LOCATION_ID}/solutions", json=BODY
        )
        malformed = client.post(
            f"/operator/api/solution-lifecycle/{LOCATION_ID}/solutions",
            json={**BODY, "owner_party_id": str(uuid4())},
        )
    assert response.status_code == 201
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert response.json() == CREATED
    assert malformed.status_code == 400
    assert calls == [(
        (
            OPERATOR_ID, LOCATION_ID, REQUEST_ID, BODY["canonical_key"],
            BODY["name"], BODY["solution_type"], BODY["problem_statement"],
            BODY["rationale"], BODY["evidence"],
        ),
        {
            "theory_of_change": BODY["theory_of_change"],
            "baseline_alternative": BODY["baseline_alternative"],
            "risk_class": BODY["risk_class"],
            "reversibility": BODY["reversibility"],
            "acknowledged": True,
        },
    )]


def test_create_route_documents_exact_request_and_migration_504_response_contract():
    from services.gateway.solution_lifecycle_routes import register_solution_lifecycle_routes

    app = FastAPI()
    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_solution_lifecycle_routes(
        router, object(), run_in_threadpool, SimpleNamespace(Error=Exception)
    )
    app.include_router(router)

    with TestClient(app) as client:
        schema = client.get("/openapi.json").json()

    operation = schema["paths"][
        "/operator/api/solution-lifecycle/{location_id}/solutions"
    ]["post"]
    request_schema = operation["requestBody"]["content"]["application/json"]["schema"]
    assert set(request_schema["properties"]) == set(BODY)
    assert request_schema["additionalProperties"] is False
    assert set(request_schema["required"]) == {
        "request_id", "canonical_key", "name", "solution_type",
        "problem_statement", "rationale", "evidence", "acknowledged",
    }
    assert request_schema["properties"]["canonical_key"]["pattern"] == (
        "^[a-z0-9][a-z0-9._:-]{1,159}$"
    )

    expected_response_fields = {
        "solution_id", "lifecycle_event_id", "canonical_key", "solution_name",
        "solution_type", "current_stage", "solution_status", "created_at", "replayed",
    }
    for status in ("200", "201"):
        response_schema = operation["responses"][status]["content"][
            "application/json"
        ]["schema"]
        component_name = response_schema["$ref"].rsplit("/", 1)[1]
        response_schema = schema["components"]["schemas"][component_name]
        assert set(response_schema["properties"]) == expected_response_fields
        assert set(response_schema["required"]) == expected_response_fields
        assert response_schema["additionalProperties"] is False
        assert operation["responses"][status]["headers"]["Cache-Control"]["schema"]["example"] == "no-store"
        assert operation["responses"][status]["headers"]["Vary"]["schema"]["example"] == "Cookie"
    assert operation["responses"]["500"]["headers"]["Cache-Control"]["schema"]["example"] == "no-store"


def test_create_route_returns_200_for_a_valid_idempotent_replay(monkeypatch):
    from services.gateway import solution_lifecycle_actions
    from services.gateway.solution_lifecycle_routes import register_solution_lifecycle_routes

    monkeypatch.setattr(
        solution_lifecycle_actions,
        "create_location_solution",
        lambda *_args, **_kwargs: {**ROUTE_CREATED, "replayed": True},
    )
    app = FastAPI()
    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_solution_lifecycle_routes(
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
        response = client.post(
            f"/operator/api/solution-lifecycle/{LOCATION_ID}/solutions", json=BODY
        )
    assert response.status_code == 200
    assert response.json() == {**CREATED, "replayed": True}
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"


def test_create_response_binding_matches_postgres_btrim_for_unicode_whitespace(monkeypatch):
    from services.gateway import solution_lifecycle_actions
    from services.gateway.solution_lifecycle_routes import register_solution_lifecycle_routes

    submitted_name = "\u00a0Solution Name\u00a0"
    monkeypatch.setattr(
        solution_lifecycle_actions,
        "create_location_solution",
        lambda *_args, **_kwargs: {
            **ROUTE_CREATED,
            "solution_name": submitted_name,
        },
    )
    app = FastAPI()
    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_solution_lifecycle_routes(
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
        response = client.post(
            f"/operator/api/solution-lifecycle/{LOCATION_ID}/solutions",
            json={**BODY, "name": submitted_name},
        )

    assert response.status_code == 201
    assert response.json()["solution_name"] == submitted_name


def test_create_route_rejects_invalid_location_before_service_access(monkeypatch):
    from services.gateway import solution_lifecycle_actions
    from services.gateway.solution_lifecycle_routes import register_solution_lifecycle_routes

    calls = []
    monkeypatch.setattr(
        solution_lifecycle_actions,
        "create_location_solution",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )
    app = FastAPI()
    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_solution_lifecycle_routes(
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
        response = client.post(
            "/operator/api/solution-lifecycle/not-a-uuid/solutions", json=BODY
        )
    assert response.status_code == 400
    assert response.headers["cache-control"] == "no-store"
    assert calls == []


@pytest.mark.parametrize(
    "overrides",
    [
        {"extra": "must not leak"},
        {"solution_id": "not-a-uuid"},
        {"created_at": "not-a-timestamp"},
        {"current_stage": "approved"},
        {"solution_status": "published"},
        {"replayed": "false"},
        {"canonical_key": "other.solution"},
        {"solution_name": "another solution"},
        {"solution_type": "policy"},
    ],
)
def test_create_route_sanitizes_malformed_or_unbound_service_results(monkeypatch, overrides):
    from services.gateway import solution_lifecycle_actions
    from services.gateway.solution_lifecycle_routes import register_solution_lifecycle_routes

    monkeypatch.setattr(
        solution_lifecycle_actions,
        "create_location_solution",
        lambda *_args, **_kwargs: {**ROUTE_CREATED, **overrides},
    )
    app = FastAPI()
    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_solution_lifecycle_routes(
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
        response = client.post(
            f"/operator/api/solution-lifecycle/{LOCATION_ID}/solutions", json=BODY
        )
    assert response.status_code == 500
    assert response.json() == {"error": "Location solution creation unavailable"}
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert "must not leak" not in response.text


def test_create_route_fails_closed_without_oidc():
    from services.gateway.solution_lifecycle_routes import register_solution_lifecycle_routes

    app = FastAPI()
    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_solution_lifecycle_routes(
        router, None, run_in_threadpool, SimpleNamespace(Error=Exception)
    )
    app.include_router(router)
    with TestClient(app) as client:
        response = client.post(
            f"/operator/api/solution-lifecycle/{LOCATION_ID}/solutions", json=BODY
        )
    assert response.status_code == 404
