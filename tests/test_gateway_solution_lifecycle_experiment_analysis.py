"""Protocol-bound exact-location sequential analysis contracts."""

from __future__ import annotations

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
EXPERIMENT_ID = str(uuid4())
REQUEST_ID = str(uuid4())
ANALYSIS = {
    "analysis_run_id": str(uuid4()),
    "experiment_id": EXPERIMENT_ID,
    "metric_key": "water.reliability",
    "benefit_direction": "higher",
    "minimum_sample": 4,
    "baseline_count": 4,
    "treatment_count": 4,
    "baseline_mean": 20.0,
    "treatment_mean": 27.0,
    "effect_estimate": 7.0,
    "standard_error": 1.25,
    "lower_bound": 4.55,
    "upper_bound": 9.45,
    "posterior_probability_benefit": 0.9999,
    "adverse_event_count": 0,
    "benefit_threshold": 0.0,
    "posterior_threshold": 0.9,
    "safety_event_limit": 1,
    "source_observation_count": 8,
    "analysis_as_of": "2026-10-20T16:30:00+00:00",
    "decision": "benefit",
    "stopping_reason": "posterior benefit probability reached threshold",
    "analysis_version": "sequential-v2-consent",
    "created_at": "2026-10-20T16:30:00+00:00",
    "replayed": False,
}
BODY = {
    "request_id": REQUEST_ID,
    "metric_key": "water.reliability",
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


def test_analysis_action_sets_exact_context_repeatable_read_and_calls_bounded_function():
    connection = _Connection(ANALYSIS)
    contexts = []

    def set_context(conn, **kwargs):
        assert conn is connection
        contexts.append(kwargs)

    with patch.object(actions, "set_operator_tenant_context", set_context):
        result = actions.analyze_location_solution_experiment(
            OPERATOR_ID, LOCATION_ID, EXPERIMENT_ID, REQUEST_ID,
            "water.reliability", True, connection_factory=lambda: connection,
        )

    assert contexts == [{
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "solution_lifecycle",
        "action": "analyze",
    }]
    assert connection.operations[0][0] == "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ"
    query, params = connection.operations[-1]
    assert "kokonut_security.analyze_location_solution_experiment" in query
    assert params == (LOCATION_ID, EXPERIMENT_ID, REQUEST_ID, "water.reliability", True)
    assert result == ANALYSIS
    assert connection.committed and connection.closed and not connection.rolled_back


@pytest.mark.parametrize(
    "kwargs, message",
    [
        ({"metric_key": "not a metric"}, "metric key"),
        ({"metric_key": []}, "metric key"),
        ({"acknowledged": False}, "acknowledgement"),
        ({"acknowledged": 1}, "acknowledgement"),
        ({"experiment_id": "bad"}, "experiment"),
        ({"request_id": "bad"}, "request"),
    ],
)
def test_invalid_analysis_fails_before_database(kwargs, message):
    values = {
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "experiment_id": EXPERIMENT_ID,
        "request_id": REQUEST_ID,
        "metric_key": "water.reliability",
        "acknowledged": True,
    }
    values.update(kwargs)
    with pytest.raises(actions.SolutionLifecycleActionInvalid, match=message):
        actions.analyze_location_solution_experiment(
            **values,
            connection_factory=lambda: pytest.fail("invalid analysis opened a database"),
        )


def test_analysis_rolls_back_and_closes_after_tenant_denial():
    connection = _Connection(ANALYSIS)

    def deny(*_args, **_kwargs):
        raise TenantContextDenied("denied")

    with patch.object(actions, "set_operator_tenant_context", deny):
        with pytest.raises(TenantContextDenied):
            actions.analyze_location_solution_experiment(
                OPERATOR_ID, LOCATION_ID, EXPERIMENT_ID, REQUEST_ID,
                "water.reliability", True, connection_factory=lambda: connection,
            )
    assert connection.rolled_back and connection.closed and not connection.committed


def test_analysis_route_requires_exact_scoped_analyze_policy():
    path = f"/operator/api/solution-lifecycle/{LOCATION_ID}/experiments/{EXPERIMENT_ID}/analyze"
    assert auth_route_policy("POST", path, enabled=True) == {
        "resource": "solution_lifecycle",
        "action": "analyze",
        "public": False,
        "location_id": LOCATION_ID,
        "scope_required": True,
        "operator_auth": True,
    }
    assert auth_route_policy("GET", path, enabled=True) is None
    assert auth_route_policy("POST", path, enabled=False) is None


def test_analysis_route_is_strict_no_store_and_forwards_operator(monkeypatch):
    from services.gateway.solution_lifecycle_routes import register_solution_lifecycle_routes

    calls = []

    def analyze(*args, **kwargs):
        calls.append((args, kwargs))
        return ANALYSIS

    monkeypatch.setattr(actions, "analyze_location_solution_experiment", analyze)
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

    path = f"/operator/api/solution-lifecycle/{LOCATION_ID}/experiments/{EXPERIMENT_ID}/analyze"
    with TestClient(app) as client:
        response = client.post(path, json=BODY)
        malformed = client.post(path, json={**BODY, "posterior_threshold": 0.99})

    assert response.status_code == 201
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == ANALYSIS
    assert malformed.status_code == 400
    assert calls == [((OPERATOR_ID, LOCATION_ID, EXPERIMENT_ID, REQUEST_ID, "water.reliability", True), {})]
