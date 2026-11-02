"""Exact-location draft promotion-gate creation contracts."""

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
SOLUTION_ID = str(uuid4())
REQUEST_ID = str(uuid4())
CREATED = {
    "gate_id": str(uuid4()),
    "solution_id": SOLUTION_ID,
    "from_stage": "testing",
    "to_stage": "validated",
    "gate_criterion": "Independent measurements support the success claim.",
    "required_evidence_maturity": 4,
    "required_experiment_count": 2,
    "minimum_evaluation_count": 1,
    "requires_human_approval": True,
    "gate_status": "draft",
    "gate_created_at": "2026-10-20T12:00:00+00:00",
    "replayed": False,
}
BODY = {
    "request_id": REQUEST_ID,
    "to_stage": "validated",
    "criterion": "Independent measurements support the success claim.",
    "required_evidence_maturity": 4,
    "required_experiment_count": 2,
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
        result = actions.create_location_solution_gate(
            OPERATOR_ID, LOCATION_ID, SOLUTION_ID, REQUEST_ID,
            BODY["to_stage"], BODY["criterion"],
            BODY["required_evidence_maturity"],
            BODY["required_experiment_count"], BODY["acknowledged"],
            connection_factory=lambda: connection,
        )

    assert contexts == [{
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "solution_lifecycle",
        "action": "create",
    }]
    query, params = connection.operations[-1]
    assert "kokonut_security.create_location_solution_gate" in query
    assert params == (
        LOCATION_ID, SOLUTION_ID, REQUEST_ID, "validated",
        BODY["criterion"], 4, 2, True,
    )
    assert result == CREATED
    assert connection.committed and connection.closed and not connection.rolled_back


@pytest.mark.parametrize(
    "overrides",
    [
        {"to_stage": "paused"},
        {"criterion": "short"},
        {"criterion": "\x00 invalid criterion"},
        {"required_evidence_maturity": True},
        {"required_evidence_maturity": 7},
        {"required_experiment_count": True},
        {"required_experiment_count": 101},
        {"acknowledged": False},
    ],
)
def test_invalid_gate_definition_fails_before_database(overrides):
    payload = {**BODY, **overrides}
    with pytest.raises(actions.SolutionLifecycleActionInvalid):
        actions.create_location_solution_gate(
            OPERATOR_ID, LOCATION_ID, SOLUTION_ID, payload["request_id"],
            payload["to_stage"], payload["criterion"],
            payload.get("required_evidence_maturity"),
            payload["required_experiment_count"], payload["acknowledged"],
            connection_factory=lambda: pytest.fail("invalid gate definition opened a database"),
        )


def test_gate_create_action_rolls_back_and_closes_on_tenant_denial():
    connection = _Connection(CREATED)

    def deny(*_args, **_kwargs):
        raise TenantContextDenied("denied")

    with patch.object(actions, "set_operator_tenant_context", deny):
        with pytest.raises(TenantContextDenied):
            actions.create_location_solution_gate(
                OPERATOR_ID, LOCATION_ID, SOLUTION_ID, REQUEST_ID,
                "validated", BODY["criterion"], 4, 2, True,
                connection_factory=lambda: connection,
            )
    assert connection.rolled_back and connection.closed and not connection.committed


def test_gate_create_route_requires_exact_scoped_create_policy():
    path = f"/operator/api/solution-lifecycle/{LOCATION_ID}/solutions/{SOLUTION_ID}/gates"
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


def test_gate_create_route_is_strict_no_store_and_forwards_operator(monkeypatch):
    from services.gateway import solution_lifecycle_actions
    from services.gateway.solution_lifecycle_routes import register_solution_lifecycle_routes

    calls = []

    def create(*args, **kwargs):
        calls.append((args, kwargs))
        return CREATED

    monkeypatch.setattr(solution_lifecycle_actions, "create_location_solution_gate", create)
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

    path = f"/operator/api/solution-lifecycle/{LOCATION_ID}/solutions/{SOLUTION_ID}/gates"
    with TestClient(app) as client:
        response = client.post(path, json=BODY)
        malformed = client.post(path, json={**BODY, "status": "approved"})

    assert response.status_code == 201
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == CREATED
    assert malformed.status_code == 400
    assert calls == [(
        (
            OPERATOR_ID, LOCATION_ID, SOLUTION_ID, REQUEST_ID, "validated",
            BODY["criterion"], 4, 2, True,
        ),
        {},
    )]


def _gate_route_app(monkeypatch, result):
    from services.gateway import solution_lifecycle_actions
    from services.gateway.solution_lifecycle_routes import register_solution_lifecycle_routes

    calls = []
    result_holder = {"value": result}

    def create(*args, **kwargs):
        calls.append((args, kwargs))
        return result_holder["value"]

    monkeypatch.setattr(solution_lifecycle_actions, "create_location_solution_gate", create)
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

    return app, calls, result_holder


def test_gate_create_route_documents_exact_request_and_response_contract(monkeypatch):
    from services.gateway.solution_lifecycle_routes import (
        SolutionLifecycleGateCreateResponse,
    )

    app, _calls, _result_holder = _gate_route_app(monkeypatch, CREATED)
    path = (
        "/operator/api/solution-lifecycle/{location_id}/solutions/{solution_id}/gates"
    )
    operation = app.openapi()["paths"][path]["post"]
    schema = app.openapi()["components"]["schemas"][
        "SolutionLifecycleGateCreateResponse"
    ]

    assert set(SolutionLifecycleGateCreateResponse.model_fields) == set(CREATED)
    assert schema["additionalProperties"] is False
    assert operation["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith(
        "/SolutionLifecycleGateCreateResponse"
    )
    assert operation["responses"]["201"]["content"]["application/json"]["schema"]["$ref"].endswith(
        "/SolutionLifecycleGateCreateResponse"
    )
    assert operation["responses"]["201"]["headers"]["Cache-Control"]["schema"]["example"] == "no-store"
    request_schema = operation["requestBody"]["content"]["application/json"]["schema"]
    assert request_schema["additionalProperties"] is False
    assert set(request_schema["properties"]) == set(BODY)
    assert schema["properties"]["minimum_evaluation_count"]["const"] == 1
    assert schema["properties"]["requires_human_approval"]["const"] is True


def test_gate_create_route_returns_draft_and_replay_receipts(monkeypatch):
    replayed = {**CREATED, "gate_status": "approved", "replayed": True}
    app, calls, result_holder = _gate_route_app(monkeypatch, CREATED)
    path = f"/operator/api/solution-lifecycle/{LOCATION_ID}/solutions/{SOLUTION_ID}/gates"
    with TestClient(app) as client:
        created = client.post(path, json=BODY)
        result_holder["value"] = replayed
        replay = client.post(path, json=BODY)

    assert created.status_code == 201
    assert created.json() == CREATED
    assert created.headers["cache-control"] == "no-store"
    assert replay.status_code == 200
    assert replay.json() == replayed
    assert replay.headers["cache-control"] == "no-store"
    assert len(calls) == 2


@pytest.mark.parametrize(
    "override",
    [
        {"extra_internal": "must not leak"},
        {"solution_id": str(uuid4())},
        {"gate_criterion": "A different criterion from the request."},
        {"gate_status": "approved"},
        {"from_stage": "investment_ready"},
        {"requires_human_approval": False},
        {"minimum_evaluation_count": 2},
        {"gate_criterion": "🧪" * 1001},
    ],
)
def test_gate_create_route_sanitizes_malformed_action_result(monkeypatch, override):
    result = {**CREATED, **override}
    app, _calls, _result_holder = _gate_route_app(monkeypatch, result)
    path = f"/operator/api/solution-lifecycle/{LOCATION_ID}/solutions/{SOLUTION_ID}/gates"

    with TestClient(app) as client:
        response = client.post(path, json=BODY)

    assert response.status_code == 500
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {"error": "Location solution gate creation unavailable"}


def test_gate_create_route_rejects_malformed_uuid_before_service(monkeypatch):
    app, calls, _result_holder = _gate_route_app(monkeypatch, CREATED)
    path = f"/operator/api/solution-lifecycle/{LOCATION_ID}/solutions/not-a-uuid/gates"

    with TestClient(app) as client:
        response = client.post(path, json=BODY)

    assert response.status_code == 400
    assert response.headers["cache-control"] == "no-store"
    assert calls == []
