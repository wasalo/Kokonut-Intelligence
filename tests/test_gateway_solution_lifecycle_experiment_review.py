"""Exact-location, independently attributed experiment result review contracts."""

from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest

from services.common.tenant_context import TenantContextDenied
from services.gateway import solution_lifecycle_actions as actions
from services.gateway import solution_lifecycle_reads as reads
from services.gateway.operator_auth import auth_route_policy

pytest.importorskip("fastapi")
from fastapi import APIRouter, FastAPI  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

OPERATOR_ID = str(uuid4())
LOCATION_ID = str(uuid4())
EXPERIMENT_ID = str(uuid4())
REQUEST_ID = str(uuid4())
REVIEW_DETAIL = {
    "experiment_id": EXPERIMENT_ID,
    "solution_id": str(uuid4()),
    "solution_name": "Soil restoration protocol",
    "solution_type": "practice",
    "current_stage": "testing",
    "protocol": {"hypothesis": "Measured soil health improves"},
    "latest_analysis": {"decision": "benefit"},
    "observations": [{"metric_key": "soil_organic_matter", "arm": "treatment"}],
    "observation_count": 1,
    "observations_truncated": False,
}
REVIEW_RESULT = {
    "experiment_id": EXPERIMENT_ID,
    "outcome": "validated",
    "reviewed_at": "2026-10-20T12:00:00+00:00",
    "replayed": False,
}
PAYLOAD = {
    "request_id": REQUEST_ID,
    "outcome": "validated",
    "primary_results": {"yield_delta": 0.2},
    "secondary_results": {},
    "limitations": "Small sample",
    "evidence": [{"ref": "field-study:run-1"}],
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
            SimpleNamespace(name=key) for key in (connection.row or {}).keys()
        )

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def execute(self, query, params=None):
        self.connection.operations.append((" ".join(query.split()), params))

    def fetchone(self):
        if self.connection.row is None:
            return None
        return tuple(self.connection.row.values())


def test_experiment_review_detail_uses_signed_review_context_and_read_only_connection():
    connection = _Connection(REVIEW_DETAIL)
    contexts = []

    def set_context(conn, **kwargs):
        assert conn is connection
        contexts.append(kwargs)

    with patch.object(reads, "set_operator_tenant_context", set_context):
        result = reads.get_location_solution_experiment_review(
            OPERATOR_ID,
            LOCATION_ID,
            EXPERIMENT_ID,
            connection_factory=lambda: connection,
        )

    assert contexts == [{
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "solution_lifecycle",
        "action": "review",
    }]
    assert connection.operations[0][0] == "SET TRANSACTION READ ONLY"
    assert "kokonut_security.location_solution_experiment_review" in connection.operations[-1][0]
    assert connection.operations[-1][1] == (LOCATION_ID, EXPERIMENT_ID)
    assert result == REVIEW_DETAIL
    assert connection.closed and connection.rolled_back and not connection.committed


def test_experiment_review_detail_rejects_oversized_private_payload():
    connection = _Connection({**REVIEW_DETAIL, "observations": ["x" * 262_145]})
    with patch.object(reads, "set_operator_tenant_context", lambda *_a, **_k: None):
        with pytest.raises(reads.SolutionLifecycleResponseTooLarge):
            reads.get_location_solution_experiment_review(
                OPERATOR_ID,
                LOCATION_ID,
                EXPERIMENT_ID,
                connection_factory=lambda: connection,
            )
    assert connection.closed and connection.rolled_back


def test_experiment_review_action_sets_review_context_and_commits_result():
    connection = _Connection(REVIEW_RESULT)
    contexts = []

    def set_context(conn, **kwargs):
        assert conn is connection
        contexts.append(kwargs)

    with patch.object(actions, "set_operator_tenant_context", set_context):
        result = actions.review_location_solution_experiment(
            OPERATOR_ID,
            LOCATION_ID,
            EXPERIMENT_ID,
            REQUEST_ID,
            "validated",
            PAYLOAD["primary_results"],
            PAYLOAD["secondary_results"],
            PAYLOAD["limitations"],
            PAYLOAD["evidence"],
            connection_factory=lambda: connection,
        )

    assert contexts == [{
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "solution_lifecycle",
        "action": "review",
    }]
    assert "kokonut_security.review_location_solution_experiment" in connection.operations[-1][0]
    assert connection.operations[-1][1] == (
        LOCATION_ID,
        EXPERIMENT_ID,
        REQUEST_ID,
        "validated",
        '{"yield_delta":0.2}',
        "{}",
        "Small sample",
        '[{"ref":"field-study:run-1"}]',
    )
    assert result == REVIEW_RESULT
    assert connection.committed and connection.closed and not connection.rolled_back


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"outcome": "unknown"}, "outcome"),
        ({"primary_results": []}, "JSON objects"),
        ({"secondary_results": {"invalid": float("nan")}}, "JSON data"),
        ({"evidence": {}}, "list of at most 100"),
    ],
)
def test_invalid_experiment_review_fails_before_database(kwargs, message):
    values = {
        "outcome": "validated",
        "primary_results": {},
        "secondary_results": {},
        "evidence": [],
    }
    values.update(kwargs)
    with pytest.raises(actions.SolutionLifecycleActionInvalid, match=message):
        actions.review_location_solution_experiment(
            OPERATOR_ID,
            LOCATION_ID,
            EXPERIMENT_ID,
            REQUEST_ID,
            values["outcome"],
            values["primary_results"],
            values["secondary_results"],
            None,
            values["evidence"],
            connection_factory=lambda: pytest.fail("invalid input must fail before DB"),
        )


def test_experiment_review_routes_require_exact_location_review_policy():
    path = f"/operator/api/solution-lifecycle/{LOCATION_ID}/experiments/{EXPERIMENT_ID}/review"
    expected = {
        "resource": "solution_lifecycle",
        "action": "review",
        "public": False,
        "location_id": LOCATION_ID,
        "scope_required": True,
        "operator_auth": True,
    }
    for method in ("GET", "POST"):
        assert auth_route_policy(method, path, enabled=True) == expected
    assert auth_route_policy("DELETE", path, enabled=True) is None
    assert auth_route_policy("POST", path, enabled=False) is None


def _app(provider, monkeypatch, read_action, review_action):
    from services.gateway.solution_lifecycle_routes import register_solution_lifecycle_routes

    monkeypatch.setattr(reads, "get_location_solution_experiment_review", read_action)
    monkeypatch.setattr(actions, "review_location_solution_experiment", review_action)
    app = FastAPI()
    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_solution_lifecycle_routes(
        router, provider, run_in_threadpool, SimpleNamespace(Error=Exception)
    )
    app.include_router(router)

    @app.middleware("http")
    async def add_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    return app


def test_experiment_review_detail_route_is_no_store_and_hides_identity(monkeypatch):
    app = _app(object(), monkeypatch, lambda *_a, **_k: REVIEW_DETAIL, lambda *_a, **_k: REVIEW_RESULT)
    path = f"/operator/api/solution-lifecycle/{LOCATION_ID}/experiments/{EXPERIMENT_ID}/review"
    with TestClient(app) as client:
        response = client.get(path)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert response.json() == REVIEW_DETAIL
    assert "reviewed_by_party_id" not in response.json()


@pytest.mark.parametrize(
    ("result", "expected_status"),
    [(REVIEW_RESULT, 201), ({**REVIEW_RESULT, "replayed": True}, 200)],
)
def test_experiment_review_post_handles_first_write_and_idempotent_retry(
    monkeypatch, result, expected_status
):
    app = _app(object(), monkeypatch, lambda *_a, **_k: REVIEW_DETAIL, lambda *_a, **_k: result)
    path = f"/operator/api/solution-lifecycle/{LOCATION_ID}/experiments/{EXPERIMENT_ID}/review"
    with TestClient(app) as client:
        response = client.post(path, json=PAYLOAD)
        invalid = client.post(path, json={**PAYLOAD, "unreviewed_by": "caller"})
    assert response.status_code == expected_status
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == result
    assert invalid.status_code == 400


def test_experiment_review_routes_fail_closed_without_oidc(monkeypatch):
    app = _app(
        None,
        monkeypatch,
        lambda *_a, **_k: pytest.fail("OIDC-disabled review must not call read"),
        lambda *_a, **_k: pytest.fail("OIDC-disabled review must not call action"),
    )
    path = f"/operator/api/solution-lifecycle/{LOCATION_ID}/experiments/{EXPERIMENT_ID}/review"
    with TestClient(app) as client:
        read_response = client.get(path)
        write_response = client.post(path, json=PAYLOAD)
    assert read_response.status_code == write_response.status_code == 404
    assert read_response.headers["cache-control"] == write_response.headers["cache-control"] == "no-store"


def test_experiment_review_action_tenant_denial_maps_to_forbidden(monkeypatch):
    app = _app(
        object(), monkeypatch, lambda *_a, **_k: REVIEW_DETAIL,
        lambda *_a, **_k: (_ for _ in ()).throw(TenantContextDenied("denied")),
    )
    path = f"/operator/api/solution-lifecycle/{LOCATION_ID}/experiments/{EXPERIMENT_ID}/review"
    with TestClient(app) as client:
        response = client.post(path, json=PAYLOAD)
    assert response.status_code == 403
