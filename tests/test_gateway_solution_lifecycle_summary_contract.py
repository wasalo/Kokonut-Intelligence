"""Strict response-contract checks for the location lifecycle summary."""

from copy import deepcopy
from types import SimpleNamespace

import pytest

pytest.importorskip("fastapi")
from fastapi import APIRouter, FastAPI  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

from services.common.tenant_context import TenantContextDenied
from services.gateway.operator_auth import auth_route_policy

LOCATION_ID = "00000000-0000-4000-8000-000000000001"
OTHER_LOCATION_ID = "00000000-0000-4000-8000-000000000002"
OPERATOR_ID = "00000000-0000-4000-8000-000000000003"

_STAGE_KEYS = (
    "discovered", "triaged", "framed", "experiment_ready", "testing", "validated",
    "investment_ready", "funded", "pilot_active", "adoption_ready", "adopting",
    "scaled", "maintained", "paused", "superseded", "retired", "failed",
)
_STATUS_KEYS = ("active", "paused", "retired", "superseded")
_GATE_KEYS = ("draft", "ready", "approved", "failed", "retired")
_EXPERIMENT_STATUS_KEYS = (
    "draft", "submitted", "protocol_approved", "baseline_ready", "active", "paused",
    "completed", "results_review", "validated", "invalidated", "inconclusive",
    "requires_replication",
)
_EXPERIMENT_RESULT_KEYS = ("validated", "invalidated", "inconclusive", "requires_replication")
_REPLICATION_KEYS = ("proposed", "approved", "active", "completed", "failed")
_FUNDING_KEYS = ("draft", "submitted", "approved", "rejected", "closed")
_ADOPTION_KEYS = (
    "draft", "community_review", "enablement_ready", "launch", "onboarding", "active",
    "paused", "assessed", "expand", "redesign", "retired",
)
_CONFIGURATION_KEYS = ("draft", "submitted", "approved", "rejected")
_READINESS_KEYS = ("not_ready", "remediating", "ready", "expired")
_SCALE_GATE_KEYS = ("pending", "passed", "failed", "waived")
_LEARNING_KEYS = ("proposed", "accepted", "rejected", "applied")
_RETIREMENT_KEYS = (
    "proposed", "impact_review", "approved", "migration", "sunset", "completed",
    "rejected",
)


def _counts(keys, values=None):
    return {**dict.fromkeys(keys, 0), **(values or {})}


def _summary(location_id=LOCATION_ID):
    return {
        "location_id": location_id,
        "solution_count": 2,
        "stage_counts": _counts(_STAGE_KEYS, {"discovered": 1, "validated": 1}),
        "solution_status_counts": _counts(_STATUS_KEYS, {"active": 2}),
        "stage_gate_status_counts": _counts(_GATE_KEYS, {"approved": 1}),
        "latest_gate_evaluation_counts": {"passed": 1, "failed": 0},
        "experiment_status_counts": _counts(_EXPERIMENT_STATUS_KEYS, {"active": 1}),
        "experiment_result_counts": _counts(_EXPERIMENT_RESULT_KEYS, {"validated": 1}),
        "replication_status_counts": _counts(_REPLICATION_KEYS, {"proposed": 1}),
        "funding_decision_counts": _counts(_FUNDING_KEYS, {"submitted": 1}),
        "adoption_program_status_counts": _counts(_ADOPTION_KEYS, {"active": 1}),
        "configuration_approval_counts": _counts(_CONFIGURATION_KEYS, {"approved": 1}),
        "adopter_readiness_counts": _counts(_READINESS_KEYS, {"ready": 1}),
        "scale_gate_status_counts": _counts(_SCALE_GATE_KEYS, {"passed": 1}),
        "learning_decision_counts": _counts(_LEARNING_KEYS, {"accepted": 1}),
        "retirement_status_counts": _counts(_RETIREMENT_KEYS, {"proposed": 1}),
    }


def _app(monkeypatch, result, *, provider=object()):
    from services.gateway.solution_lifecycle_routes import register_solution_lifecycle_routes

    monkeypatch.setattr(
        "services.gateway.solution_lifecycle_reads.get_location_solution_lifecycle_summary",
        result if callable(result) else lambda *_args, **_kwargs: result,
    )
    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_solution_lifecycle_routes(
        router, provider, run_in_threadpool, SimpleNamespace(Error=Exception)
    )
    app = FastAPI()
    app.include_router(router)

    @app.middleware("http")
    async def add_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    return app


def test_summary_route_publishes_complete_closed_openapi_projection(monkeypatch):
    app = _app(monkeypatch, _summary())
    openapi = app.openapi()
    path = "/operator/api/solution-lifecycle/{location_id}/summary"
    operation = openapi["paths"][path]["get"]
    response_schema = operation["responses"]["200"]["content"]["application/json"][
        "schema"
    ]
    assert response_schema["$ref"].endswith("/SolutionLifecycleSummaryResponse")

    schema = openapi["components"]["schemas"]["SolutionLifecycleSummaryResponse"]
    assert set(schema["properties"]) == set(_summary())
    assert schema["additionalProperties"] is False
    count_set_schema = openapi["components"]["schemas"]["SolutionLifecycleStageCounts"]
    assert set(count_set_schema["properties"]) == set(_STAGE_KEYS)
    assert count_set_schema["additionalProperties"] is False


def test_summary_route_returns_location_bound_aggregate_with_private_headers(monkeypatch):
    expected = _summary()
    app = _app(monkeypatch, expected)
    path = f"/operator/api/solution-lifecycle/{LOCATION_ID}/summary"
    with TestClient(app) as client:
        response = client.get(path)

    assert response.status_code == 200
    assert response.json() == expected
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"


def _mutate_wrong_location(payload):
    payload["location_id"] = OTHER_LOCATION_ID


def _mutate_missing_fixed_count(payload):
    del payload["experiment_status_counts"]["protocol_approved"]


def _mutate_extra_nested_field(payload):
    payload["stage_counts"]["unexpected"] = 0


def _mutate_negative_count(payload):
    payload["stage_gate_status_counts"]["approved"] = -1


def _mutate_float_count(payload):
    payload["solution_count"] = 2.0


def _mutate_stage_total(payload):
    payload["stage_counts"]["discovered"] = 0


def _mutate_status_total(payload):
    payload["solution_status_counts"]["active"] = 1


@pytest.mark.parametrize(
    "mutate",
    [
        _mutate_wrong_location,
        _mutate_missing_fixed_count,
        _mutate_extra_nested_field,
        _mutate_negative_count,
        _mutate_float_count,
        _mutate_stage_total,
        _mutate_status_total,
    ],
    ids=[
        "wrong-location", "missing-enumerated-count", "extra-nested-field",
        "negative-count", "non-integer-count", "inconsistent-stage-total",
        "inconsistent-status-total",
    ],
)
def test_summary_route_rejects_malformed_projection_with_generic_no_store_error(
    monkeypatch, mutate
):
    payload = deepcopy(_summary())
    mutate(payload)
    app = _app(monkeypatch, payload)
    path = f"/operator/api/solution-lifecycle/{LOCATION_ID}/summary"
    with TestClient(app) as client:
        response = client.get(path)

    assert response.status_code == 500
    assert response.json() == {"error": "Solution lifecycle summary unavailable"}
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"


def test_summary_route_preserves_exact_location_auth_and_oidc_denial(monkeypatch):
    from services.gateway.solution_lifecycle_routes import register_solution_lifecycle_routes

    path = f"/operator/api/solution-lifecycle/{LOCATION_ID}/summary"
    assert auth_route_policy("GET", path, enabled=True) == {
        "resource": "solution_lifecycle",
        "action": "read",
        "public": False,
        "location_id": LOCATION_ID,
        "scope_required": True,
        "operator_auth": True,
    }

    def denied(*_args, **_kwargs):
        raise TenantContextDenied("private detail")

    app = _app(monkeypatch, denied)
    with TestClient(app) as client:
        response = client.get(path)
    assert response.status_code == 403
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {
        "error": "Tenant-qualified solution lifecycle access is required"
    }

    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_solution_lifecycle_routes(
        router, None, run_in_threadpool, SimpleNamespace(Error=Exception)
    )
    disabled = FastAPI()
    disabled.include_router(router)
    with TestClient(disabled) as client:
        response = client.get(path)
    assert response.status_code == 404
    assert response.headers["cache-control"] == "no-store"
