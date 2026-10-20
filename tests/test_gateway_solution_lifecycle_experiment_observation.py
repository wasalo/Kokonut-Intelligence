"""Consent-aware, exact-location experiment observation capture contracts."""

from __future__ import annotations

import json
from decimal import Decimal
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
PARTICIPANT_LINK_ID = str(uuid4())
OBSERVATION = {
    "observation_id": str(uuid4()),
    "experiment_id": EXPERIMENT_ID,
    "metric_key": "water.reliability",
    "observed_at": "2026-10-20T16:30:00+00:00",
    "replayed": False,
}
BODY = {
    "request_id": REQUEST_ID,
    "metric_key": "water.reliability",
    "value": 1.25,
    "arm": "treatment",
    "adverse_event": False,
    "evidence": {"evidence_refs": [str(uuid4())]},
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


def _capture(connection, *, connection_factory=None, **overrides):
    evidence = {"evidence_refs": ["eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee"]}
    arguments = {
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "experiment_id": EXPERIMENT_ID,
        "request_id": REQUEST_ID,
        "metric_key": "water.reliability",
        "value": Decimal("1.250"),
        "arm": "treatment",
        "unit_ref": None,
        "adverse_event": False,
        "evidence": evidence,
        "participant_link_id": PARTICIPANT_LINK_ID,
        "acknowledged": True,
    }
    arguments.update(overrides)
    return actions.record_location_solution_experiment_observation(
        **arguments,
        connection_factory=connection_factory or (lambda: connection),
    )


def test_capture_action_sets_collect_context_and_calls_bounded_function():
    connection = _Connection(OBSERVATION)
    evidence = {"evidence_refs": ["eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee"]}
    contexts = []

    def set_context(conn, **kwargs):
        assert conn is connection
        contexts.append(kwargs)

    with patch.object(actions, "set_operator_tenant_context", set_context):
        result = _capture(connection, value=Decimal("1.250"), evidence=evidence)

    assert contexts == [{
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "solution_lifecycle",
        "action": "collect",
    }]
    query, params = connection.operations[-1]
    assert "kokonut_security.capture_location_solution_experiment_observation" in query
    assert params == (
        LOCATION_ID,
        EXPERIMENT_ID,
        REQUEST_ID,
        "water.reliability",
        "1.250",
        "treatment",
        None,
        False,
        json.dumps(evidence, separators=(",", ":")),
        PARTICIPANT_LINK_ID,
        True,
    )
    assert result == OBSERVATION
    assert connection.committed and connection.closed and not connection.rolled_back


@pytest.mark.parametrize(
    "overrides, message",
    [
        ({"metric_key": "not a metric"}, "metric key"),
        ({"value": True}, "finite number"),
        ({"value": float("inf")}, "finite number"),
        ({"value": Decimal("1000000000001")}, "supported range"),
        ({"value": None, "adverse_event": False}, "adverse event"),
        ({"arm": []}, "arm"),
        ({"arm": "control"}, "arm"),
        ({"unit_ref": "not valid"}, "opaque identifier"),
        ({"adverse_event": "false"}, "Adverse-event flag"),
        ({"evidence": "participant name"}, "JSON object or array"),
        ({"evidence": {"bad": float("nan")}}, "JSON values"),
        ({"evidence": {"detail": "x" * 65537}}, "64 KiB limit"),
        ({"participant_link_id": "not-a-uuid"}, "participant link"),
        ({"acknowledged": 1}, "acknowledgement"),
    ],
)
def test_invalid_observation_fails_before_database(overrides, message):
    with pytest.raises(actions.SolutionLifecycleActionInvalid, match=message):
        _capture(
            None,
            **overrides,
            connection_factory=lambda: pytest.fail("invalid observation opened a database"),
        )


def test_missing_value_is_allowed_only_for_acknowledged_adverse_event():
    connection = _Connection(OBSERVATION)
    with patch.object(actions, "set_operator_tenant_context"):
        _capture(connection, value=None, adverse_event=True)
    assert connection.committed


def test_capture_action_rolls_back_and_closes_on_tenant_denial():
    connection = _Connection(OBSERVATION)

    def deny(*_args, **_kwargs):
        raise TenantContextDenied("denied")

    with patch.object(actions, "set_operator_tenant_context", deny):
        with pytest.raises(TenantContextDenied):
            _capture(connection)
    assert connection.rolled_back and connection.closed and not connection.committed


def test_observation_route_requires_exact_collect_policy():
    path = (
        f"/operator/api/solution-lifecycle/{LOCATION_ID}/experiments/"
        f"{EXPERIMENT_ID}/observations"
    )
    assert auth_route_policy("POST", path, enabled=True) == {
        "resource": "solution_lifecycle",
        "action": "collect",
        "public": False,
        "location_id": LOCATION_ID,
        "scope_required": True,
        "operator_auth": True,
    }
    assert auth_route_policy("GET", path, enabled=True) is None
    assert auth_route_policy("POST", path, enabled=False) is None


def test_observation_route_is_strict_no_store_and_forwards_operator(monkeypatch):
    from services.gateway.solution_lifecycle_routes import register_solution_lifecycle_routes

    calls = []

    def capture(*args, **kwargs):
        calls.append((args, kwargs))
        return OBSERVATION

    monkeypatch.setattr(actions, "record_location_solution_experiment_observation", capture)
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
        f"/operator/api/solution-lifecycle/{LOCATION_ID}/experiments/"
        f"{EXPERIMENT_ID}/observations"
    )
    with TestClient(app) as client:
        response = client.post(path, json=BODY)
        malformed = client.post(path, json={**BODY, "recorded_by_party_id": OPERATOR_ID})

    assert response.status_code == 201
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == OBSERVATION
    assert malformed.status_code == 400
    assert calls == [((OPERATOR_ID, LOCATION_ID, EXPERIMENT_ID, REQUEST_ID,
                       "water.reliability", 1.25, "treatment", None, False,
                       BODY["evidence"], None, True), {})]
