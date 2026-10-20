"""Exact-location experiment protocol draft creation contracts."""

from __future__ import annotations

import json
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
PROTOCOL = {
    "hypothesis": "The revised water protocol improves dry-season reliability.",
    "null_hypothesis": "The revised protocol has no material effect.",
    "baseline_definition": "Current location water practice over the same season.",
    "treatment_definition": "Use the proposed water retention protocol.",
    "comparator_definition": "Compare matched field units where feasible.",
    "unit_of_analysis": "A field unit observed for one growing season.",
    "sample_plan": {"minimum_sample": 8, "sampling_note": "Synthetic acceptance plan."},
    "primary_metric_keys": ["water.reliability"],
    "secondary_metric_keys": ["soil.moisture"],
    "minimum_detectable_effect": 0.1,
    "confidence_target": 0.95,
    "duration_days": 180,
    "stopping_rules": {"safety": "pause for an adverse event"},
    "rollback_plan": "Restore the prior practice after review if safety or reliability declines.",
    "safety_boundaries": {"no_participant_identity": True},
    "consent_requirements": {
        "participant_consent_required": True,
        "purpose": "Participation in the water reliability experiment.",
        "consent_version": "v1",
    },
}
BODY = {"request_id": REQUEST_ID, "protocol": PROTOCOL, "acknowledged": True}
CREATED = {
    "experiment_id": str(uuid4()),
    "solution_id": SOLUTION_ID,
    "protocol_version": "v1",
    "experiment_status": "draft",
    "experiment_created_at": "2026-10-20T12:00:00+00:00",
    "replayed": False,
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
        result = actions.create_location_solution_experiment(
            OPERATOR_ID, LOCATION_ID, SOLUTION_ID, REQUEST_ID, PROTOCOL, True,
            connection_factory=lambda: connection,
        )

    assert contexts == [{
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "solution_lifecycle",
        "action": "create",
    }]
    query, params = connection.operations[-1]
    assert "kokonut_security.create_location_solution_experiment" in query
    assert params[:3] == (LOCATION_ID, SOLUTION_ID, REQUEST_ID)
    assert json.loads(params[3]) == PROTOCOL
    assert params[4] is True
    assert result == CREATED
    assert connection.committed and connection.closed and not connection.rolled_back


@pytest.mark.parametrize(
    "overrides",
    [
        {"hypothesis": ""},
        {"unit_of_analysis": "x" * 256},
        {"sample_plan": []},
        {"primary_metric_keys": ["invalid key"]},
        {"primary_metric_keys": ["water", "water"]},
        {"primary_metric_keys": ["shared"], "secondary_metric_keys": ["shared"]},
        {"confidence_target": 0.49},
        {"duration_days": True},
        {"consent_requirements": {}},
        {"consent_requirements": {"participant_consent_required": 1}},
        {"consent_requirements": {"participant_consent_required": False}},
        {"consent_requirements": {
            "participant_consent_required": False,
            "non_personal_basis": [],
        }},
        {"consent_requirements": {
            "participant_consent_required": True,
            "purpose": "Participation in the experiment.",
        }},
        {"consent_requirements": {
            "participant_consent_required": True,
            "purpose": "Participation in the experiment.",
            "consent_version": "invalid version",
        }},
        {"unexpected": "field"},
    ],
)
def test_invalid_protocol_fails_before_database(overrides):
    protocol = {**PROTOCOL, **overrides}
    with pytest.raises(actions.SolutionLifecycleActionInvalid):
        actions.create_location_solution_experiment(
            OPERATOR_ID, LOCATION_ID, SOLUTION_ID, REQUEST_ID, protocol, True,
            connection_factory=lambda: pytest.fail("invalid protocol opened a database"),
        )


def test_missing_acknowledgement_fails_before_database():
    with pytest.raises(actions.SolutionLifecycleActionInvalid, match="acknowledgement"):
        actions.create_location_solution_experiment(
            OPERATOR_ID, LOCATION_ID, SOLUTION_ID, REQUEST_ID, PROTOCOL, False,
            connection_factory=lambda: pytest.fail("unacknowledged draft opened a database"),
        )


def test_non_personal_experiment_requires_explicit_basis_and_preserves_policy():
    connection = _Connection(CREATED)
    protocol = {
        **PROTOCOL,
        "consent_requirements": {
            "participant_consent_required": False,
            "non_personal_basis": "environmental_measurement",
        },
    }

    with patch.object(actions, "set_operator_tenant_context"):
        actions.create_location_solution_experiment(
            OPERATOR_ID, LOCATION_ID, SOLUTION_ID, REQUEST_ID, protocol, True,
            connection_factory=lambda: connection,
        )

    query, params = connection.operations[-1]
    assert "kokonut_security.create_location_solution_experiment" in query
    assert json.loads(params[3])["consent_requirements"] == protocol["consent_requirements"]


def test_experiment_action_rolls_back_and_closes_on_tenant_denial():
    connection = _Connection(CREATED)

    def deny(*_args, **_kwargs):
        raise TenantContextDenied("denied")

    with patch.object(actions, "set_operator_tenant_context", deny):
        with pytest.raises(TenantContextDenied):
            actions.create_location_solution_experiment(
                OPERATOR_ID, LOCATION_ID, SOLUTION_ID, REQUEST_ID, PROTOCOL, True,
                connection_factory=lambda: connection,
            )
    assert connection.rolled_back and connection.closed and not connection.committed


def test_experiment_create_route_requires_exact_scoped_create_policy():
    path = (
        f"/operator/api/solution-lifecycle/{LOCATION_ID}/solutions/"
        f"{SOLUTION_ID}/experiments"
    )
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


def test_experiment_create_route_is_strict_no_store_and_forwards_operator(monkeypatch):
    from services.gateway import solution_lifecycle_actions
    from services.gateway.solution_lifecycle_routes import register_solution_lifecycle_routes

    calls = []

    def create(*args, **kwargs):
        calls.append((args, kwargs))
        return CREATED

    monkeypatch.setattr(
        solution_lifecycle_actions, "create_location_solution_experiment", create
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

    path = (
        f"/operator/api/solution-lifecycle/{LOCATION_ID}/solutions/"
        f"{SOLUTION_ID}/experiments"
    )
    with TestClient(app) as client:
        response = client.post(path, json=BODY)
        malformed = client.post(path, json={**BODY, "owner_party_id": OPERATOR_ID})

    assert response.status_code == 201
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == CREATED
    assert malformed.status_code == 400
    assert calls == [((OPERATOR_ID, LOCATION_ID, SOLUTION_ID, REQUEST_ID, PROTOCOL, True), {})]
