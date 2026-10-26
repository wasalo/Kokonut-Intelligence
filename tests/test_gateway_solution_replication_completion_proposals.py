"""Protected private completion-report proposal path for CAP-035 replications."""

from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest

pytest.importorskip("fastapi")
from fastapi import APIRouter, FastAPI  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

from services.common.tenant_context import TenantContextDenied
from services.gateway import solution_lifecycle_actions as actions
from services.gateway.operator_auth import auth_route_policy

OPERATOR_ID = str(uuid4())
LOCATION_ID = str(uuid4())
REPLICATION_ID = str(uuid4())
REQUEST_ID = str(uuid4())
RESULT = {
    "proposal_id": str(uuid4()),
    "replication_id": REPLICATION_ID,
    "decision_status": "proposed",
    "created_at": "2026-10-20T12:00:00+00:00",
    "replayed": False,
}


class _Connection:
    def __init__(self, row=None, *, fail=False):
        self.row = row or RESULT
        self.fail = fail
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
        self.description = tuple(SimpleNamespace(name=name) for name in connection.row)

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def execute(self, query, params=None):
        self.connection.operations.append((" ".join(query.split()), params))
        if self.connection.fail and "propose_location_solution_replication_completion" in query:
            raise RuntimeError("database completion proposal failed")

    def fetchone(self):
        return tuple(self.connection.row.values())


def _valid_action(connection_factory):
    return actions.propose_location_solution_replication_completion(
        OPERATOR_ID,
        LOCATION_ID,
        REPLICATION_ID,
        REQUEST_ID,
        "successful",
        3,
        "The local replication met its measured objectives.",
        [{"evidence_ref": "synthetic://replication/1"}],
        acknowledged=True,
        connection_factory=connection_factory,
    )


def test_completion_proposal_sets_exact_submit_context_and_commits():
    connection = _Connection()
    contexts = []

    def set_context(conn, **kwargs):
        contexts.append((conn, kwargs))

    with patch.object(actions, "set_operator_tenant_context", set_context):
        result = _valid_action(lambda: connection)

    assert result == RESULT
    assert contexts == [(
        connection,
        {
            "operator_id": OPERATOR_ID,
            "location_id": LOCATION_ID,
            "resource": "solution_lifecycle",
            "action": "submit",
        },
    )]
    assert connection.operations[:2] == [
        ("SET LOCAL statement_timeout = '8s'", None),
        ("SET LOCAL lock_timeout = '2s'", None),
    ]
    query, params = connection.operations[2]
    assert "kokonut_security.propose_location_solution_replication_completion" in query
    assert params == (
        LOCATION_ID,
        REPLICATION_ID,
        REQUEST_ID,
        "successful",
        3,
        "The local replication met its measured objectives.",
        '[{"evidence_ref":"synthetic://replication/1"}]',
    )
    assert connection.committed and connection.closed and not connection.rolled_back


@pytest.mark.parametrize(
    "operator_id, location_id, replication_id, request_id, outcome, maturity, summary, evidence, acknowledged",
    [
        ("bad", LOCATION_ID, REPLICATION_ID, REQUEST_ID, "successful", 3, "A sufficient summary.", [], True),
        (OPERATOR_ID, LOCATION_ID, REPLICATION_ID, REQUEST_ID, [], 3, "A sufficient summary.", [], True),
        (OPERATOR_ID, LOCATION_ID, REPLICATION_ID, REQUEST_ID, "unknown", 3, "A sufficient summary.", [], True),
        (OPERATOR_ID, LOCATION_ID, REPLICATION_ID, REQUEST_ID, "successful", True, "A sufficient summary.", [], True),
        (OPERATOR_ID, LOCATION_ID, REPLICATION_ID, REQUEST_ID, "successful", 7, "A sufficient summary.", [], True),
        (OPERATOR_ID, LOCATION_ID, REPLICATION_ID, REQUEST_ID, "successful", 3, "short", [], True),
        (OPERATOR_ID, LOCATION_ID, REPLICATION_ID, REQUEST_ID, "successful", 3, "A sufficient summary.", {}, True),
        (OPERATOR_ID, LOCATION_ID, REPLICATION_ID, REQUEST_ID, "successful", 3, "A sufficient summary.", [float("nan")], True),
        (OPERATOR_ID, LOCATION_ID, REPLICATION_ID, REQUEST_ID, "successful", 3, "A sufficient summary.", [], False),
    ],
)
def test_invalid_completion_proposal_fails_before_database(
    operator_id, location_id, replication_id, request_id,
    outcome, maturity, summary, evidence, acknowledged,
):
    with pytest.raises(actions.SolutionLifecycleActionInvalid):
        actions.propose_location_solution_replication_completion(
            operator_id,
            location_id,
            replication_id,
            request_id,
            outcome,
            maturity,
            summary,
            evidence,
            acknowledged=acknowledged,
            connection_factory=lambda: pytest.fail("invalid input opened a database connection"),
        )


def test_completion_proposal_failure_rolls_back_and_closes():
    connection = _Connection(fail=True)
    with patch.object(actions, "set_operator_tenant_context"):
        with pytest.raises(RuntimeError, match="database completion proposal failed"):
            _valid_action(lambda: connection)
    assert connection.rolled_back and connection.closed and not connection.committed


def test_completion_proposal_route_policy_requires_exact_submit_grant():
    path = (
        f"/operator/api/solution-lifecycle/{LOCATION_ID}/replications/"
        f"{REPLICATION_ID}/completion-proposals"
    )
    assert auth_route_policy("POST", path, enabled=True) == {
        "resource": "solution_lifecycle",
        "action": "submit",
        "public": False,
        "location_id": LOCATION_ID,
        "scope_required": True,
        "operator_auth": True,
    }
    assert auth_route_policy("GET", path, enabled=True) is None
    assert auth_route_policy("POST", path + "/extra", enabled=True) is None


def _app(monkeypatch, *, provider=object(), action=None):
    from services.gateway.solution_lifecycle_routes import register_solution_lifecycle_routes

    calls = []

    def propose(*args, **kwargs):
        calls.append((args, kwargs))
        if action:
            return action(*args, **kwargs)
        return RESULT

    monkeypatch.setattr(actions, "propose_location_solution_replication_completion", propose)
    app = FastAPI()
    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_solution_lifecycle_routes(router, provider, run_in_threadpool, SimpleNamespace(Error=Exception))
    app.include_router(router)

    @app.middleware("http")
    async def add_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(operator=SimpleNamespace(operator_id=OPERATOR_ID))
        return await call_next(request)

    return app, calls


def test_completion_proposal_route_is_no_store_and_accepts_only_bounded_fields(monkeypatch):
    app, calls = _app(monkeypatch)
    path = (
        f"/operator/api/solution-lifecycle/{LOCATION_ID}/replications/"
        f"{REPLICATION_ID}/completion-proposals"
    )
    payload = {
        "request_id": REQUEST_ID,
        "outcome": "successful",
        "evidence_maturity": 3,
        "outcome_summary": "The local replication met its measured objectives.",
        "evidence": [{"evidence_ref": "synthetic://replication/1"}],
        "acknowledged": True,
    }
    with TestClient(app) as client:
        submitted = client.post(path, json=payload)
        invalid = client.post(path, json={**payload, "status": "completed"})
    assert submitted.status_code == 201 and submitted.json() == RESULT
    assert invalid.status_code == 400
    assert submitted.headers["cache-control"] == "no-store"
    assert submitted.headers["vary"] == "Cookie"
    assert calls == [((OPERATOR_ID, LOCATION_ID, REPLICATION_ID, REQUEST_ID,
                      "successful", 3, payload["outcome_summary"], payload["evidence"]),
                     {"acknowledged": True})]


def test_completion_proposal_route_fails_closed_when_oidc_disabled_or_tenant_denied(monkeypatch):
    path = (
        f"/operator/api/solution-lifecycle/{LOCATION_ID}/replications/"
        f"{REPLICATION_ID}/completion-proposals"
    )
    payload = {
        "request_id": REQUEST_ID,
        "outcome": "successful",
        "evidence_maturity": 3,
        "outcome_summary": "The local replication met its measured objectives.",
        "evidence": [],
        "acknowledged": True,
    }
    app, _ = _app(monkeypatch, provider=None)
    with TestClient(app) as client:
        disabled = client.post(path, json=payload)
    assert disabled.status_code == 404 and disabled.headers["cache-control"] == "no-store"

    def deny(*_args, **_kwargs):
        raise TenantContextDenied("denied")

    app, _ = _app(monkeypatch, action=deny)
    with TestClient(app) as client:
        denied = client.post(path, json=payload)
    assert denied.status_code == 403 and denied.headers["cache-control"] == "no-store"
