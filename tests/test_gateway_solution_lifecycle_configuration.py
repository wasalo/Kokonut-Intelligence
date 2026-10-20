"""Exact-location configuration drafts and independent review contracts."""

import json
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest

from services.gateway import solution_lifecycle_actions as actions

pytest.importorskip("fastapi")
from fastapi import APIRouter, FastAPI  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

OPERATOR_ID = str(uuid4())
LOCATION_ID = str(uuid4())
SOLUTION_ID = str(uuid4())
CONFIGURATION_ID = str(uuid4())
REQUEST_ID = str(uuid4())
BODY = {
    "request_id": REQUEST_ID,
    "solution_id": SOLUTION_ID,
    "invariant_components": {"water_buffer": "preserve"},
    "configurable_components": {"crop_mix": ["plantain", "cacao"]},
    "prohibited_components": {"chemical_runoff": "prohibited"},
    "local_assumptions": {"soil_type": "clay loam"},
    "comparability_class": "partially_comparable",
    "evidence_impact": "Local soil and water evidence informs performance comparison.",
    "acknowledged": True,
}
CREATED = {
    "configuration_id": CONFIGURATION_ID,
    "solution_id": SOLUTION_ID,
    "version": 2,
    "approval_status": "draft",
    "proposed_at": "2026-10-20T12:00:00+00:00",
    "replayed": False,
}
DRAFT = {
    "configuration_id": CONFIGURATION_ID,
    "solution_id": SOLUTION_ID,
    "version": 2,
    "comparability_class": "partially_comparable",
    "evidence_impact": BODY["evidence_impact"],
    "proposed_at": "2026-10-20T12:00:00+00:00",
}
SUBMITTED = {
    "configuration_id": CONFIGURATION_ID,
    "solution_id": SOLUTION_ID,
    "version": 2,
    "approval_status": "submitted",
    "submitted_at": "2026-10-20T12:30:00+00:00",
    "replayed": False,
}
REVIEWED = {
    "configuration_id": CONFIGURATION_ID,
    "solution_id": SOLUTION_ID,
    "decision": "approved",
    "approval_status": "approved",
    "reviewed_at": "2026-10-20T13:00:00+00:00",
    "replayed": False,
}
REVIEW_QUEUE_ROW = {
    "configuration_id": CONFIGURATION_ID,
    "solution_id": SOLUTION_ID,
    "version": 2,
    "invariant_components": BODY["invariant_components"],
    "configurable_components": BODY["configurable_components"],
    "prohibited_components": BODY["prohibited_components"],
    "local_assumptions": BODY["local_assumptions"],
    "comparability_class": "partially_comparable",
    "evidence_impact": BODY["evidence_impact"],
    "submitted_at": "2026-10-20T12:30:00+00:00",
}


class _Column:
    def __init__(self, name):
        self.name = name

    def __getitem__(self, index):
        if index != 0:
            raise IndexError(index)
        return self.name


class _Connection:
    def __init__(self, *, result=None, rows=(), fail=False):
        self.result = result
        self.rows = rows
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
        self.description = ()

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def execute(self, query, params=None):
        normalized = " ".join(query.split())
        self.connection.operations.append((normalized, params))
        if self.connection.fail and "kokonut_security." in normalized:
            raise RuntimeError("synthetic configuration database failure")
        result = self.connection.result
        if result is not None:
            self.description = tuple(_Column(key) for key in result)
        elif self.connection.rows:
            self.description = tuple(_Column(key) for key in self.connection.rows[0])

    def fetchone(self):
        return tuple(self.connection.result.values())

    def fetchall(self):
        return [tuple(row.values()) for row in self.connection.rows]


def test_configuration_encoder_accepts_bounded_json_objects_and_normalizes_text():
    encoded = actions._encode_location_solution_configuration(
        BODY["invariant_components"], BODY["configurable_components"],
        BODY["prohibited_components"], BODY["local_assumptions"],
        BODY["comparability_class"], f" {BODY['evidence_impact']} ",
    )
    assert json.loads(encoded[0]) == BODY["invariant_components"]
    assert json.loads(encoded[1]) == BODY["configurable_components"]
    assert encoded[4:] == (BODY["comparability_class"], BODY["evidence_impact"])


@pytest.mark.parametrize(
    "changes",
    [
        {"invariant_components": []},
        {"invariant_components": {"bulk": "x" * 65536}},
        {"configurable_components": {"crop": float("nan")}},
        {"local_assumptions": {"nested": ["bad\x00text"]}},
        {"invariant_components": {"bad": "\ud800"}},
        {"invariant_components": {"same": True}, "configurable_components": {"same": False}},
        {"prohibited_components": {"same": True}, "configurable_components": {"same": False}},
        {"comparability_class": "unknown"},
        {"evidence_impact": " "},
        {"evidence_impact": "x" * 4001},
        {"acknowledged": False},
    ],
)
def test_invalid_configuration_draft_fails_before_database_access(changes):
    payload = {**BODY, **changes}
    with pytest.raises(actions.SolutionLifecycleActionInvalid):
        actions.create_location_solution_configuration_draft(
            OPERATOR_ID, LOCATION_ID, payload["solution_id"], payload["request_id"],
            payload["invariant_components"], payload["configurable_components"],
            payload["prohibited_components"], payload["local_assumptions"],
            payload["comparability_class"], payload["evidence_impact"],
            acknowledged=payload["acknowledged"],
            connection_factory=lambda: pytest.fail("invalid draft must fail before database access"),
        )


def test_configuration_draft_action_sets_exact_create_context_and_commits():
    connection = _Connection(result=CREATED)
    contexts = []
    with patch.object(actions, "set_operator_tenant_context", lambda conn, **kwargs: contexts.append((conn, kwargs))):
        result = actions.create_location_solution_configuration_draft(
            OPERATOR_ID, LOCATION_ID, SOLUTION_ID, REQUEST_ID,
            BODY["invariant_components"], BODY["configurable_components"],
            BODY["prohibited_components"], BODY["local_assumptions"],
            BODY["comparability_class"], BODY["evidence_impact"],
            acknowledged=True, connection_factory=lambda: connection,
        )
    assert contexts == [(connection, {
        "operator_id": OPERATOR_ID, "location_id": LOCATION_ID,
        "resource": "solution_lifecycle", "action": "create",
    })]
    assert connection.operations[:2] == [
        ("SET LOCAL statement_timeout = '8s'", None),
        ("SET LOCAL lock_timeout = '2s'", None),
    ]
    query, params = connection.operations[-1]
    assert "create_location_solution_configuration_draft" in query
    assert params[:3] == (LOCATION_ID, SOLUTION_ID, REQUEST_ID)
    assert json.loads(params[3]) == BODY["invariant_components"]
    assert params[-3:] == (BODY["comparability_class"], BODY["evidence_impact"], True)
    assert result == CREATED
    assert connection.committed and connection.closed and not connection.rolled_back


@pytest.mark.parametrize(
    ("function", "sql_name", "action", "result", "rows", "kwargs", "expected_params"),
    [
        (
            actions.get_location_solution_configuration_drafts,
            "location_solution_configuration_drafts", "submit", None, [DRAFT],
            {"limit": 2, "offset": 7}, (LOCATION_ID, 3, 7),
        ),
        (
            actions.get_location_solution_configuration_review_queue,
            "location_solution_configuration_review_queue", "review", None, [REVIEW_QUEUE_ROW],
            {"limit": 1, "offset": 3}, (LOCATION_ID, 2, 3),
        ),
    ],
)
def test_configuration_queue_actions_use_exact_context_and_bounded_paging(
    function, sql_name, action, result, rows, kwargs, expected_params,
):
    connection = _Connection(rows=rows)
    contexts = []
    with patch.object(actions, "set_operator_tenant_context", lambda conn, **values: contexts.append((conn, values))):
        result = function(OPERATOR_ID, LOCATION_ID, **kwargs, connection_factory=lambda: connection)
    assert contexts == [(connection, {
        "operator_id": OPERATOR_ID, "location_id": LOCATION_ID,
        "resource": "solution_lifecycle", "action": action,
    })]
    assert sql_name in connection.operations[-1][0]
    assert connection.operations[-1][1] == expected_params
    assert connection.committed and connection.closed and not connection.rolled_back
    assert result["has_more"] is False


def test_configuration_submission_and_review_actions_share_transaction_context():
    cases = [
        (
            actions.submit_location_solution_configuration, SUBMITTED,
            (OPERATOR_ID, LOCATION_ID, CONFIGURATION_ID, REQUEST_ID),
            {"acknowledged": True}, "submit_location_solution_configuration", "submit",
        ),
        (
            actions.review_location_solution_configuration, REVIEWED,
            (OPERATOR_ID, LOCATION_ID, CONFIGURATION_ID, REQUEST_ID, "approved", "Evidence reviewed."),
            {"acknowledged": True}, "review_location_solution_configuration", "review",
        ),
    ]
    for function, expected, args, kwargs, sql_name, action in cases:
        connection = _Connection(result=expected)
        contexts = []
        with patch.object(actions, "set_operator_tenant_context", lambda conn, **values: contexts.append((conn, values))):
            result = function(*args, **kwargs, connection_factory=lambda: connection)
        assert contexts == [(connection, {
            "operator_id": OPERATOR_ID, "location_id": LOCATION_ID,
            "resource": "solution_lifecycle", "action": action,
        })]
        assert sql_name in connection.operations[-1][0]
        assert result == expected
        assert connection.committed and connection.closed and not connection.rolled_back


def test_configuration_action_rolls_back_and_closes_after_database_failure():
    connection = _Connection(result=CREATED, fail=True)
    with patch.object(actions, "set_operator_tenant_context", lambda *_args, **_kwargs: None):
        with pytest.raises(RuntimeError, match="synthetic configuration database failure"):
            actions.create_location_solution_configuration_draft(
                OPERATOR_ID, LOCATION_ID, SOLUTION_ID, REQUEST_ID,
                BODY["invariant_components"], BODY["configurable_components"],
                BODY["prohibited_components"], BODY["local_assumptions"],
                BODY["comparability_class"], BODY["evidence_impact"],
                acknowledged=True, connection_factory=lambda: connection,
            )
    assert connection.rolled_back and connection.closed and not connection.committed


def test_configuration_http_routes_require_exact_fields_and_return_no_store(monkeypatch):
    from services.gateway.solution_lifecycle_routes import register_solution_lifecycle_routes

    calls = []

    def create(*args, **kwargs):
        calls.append(("create", args, kwargs))
        return CREATED

    def submit(*args, **kwargs):
        calls.append(("submit", args, kwargs))
        return SUBMITTED

    def review(*args, **kwargs):
        calls.append(("review", args, kwargs))
        return REVIEWED

    monkeypatch.setattr(actions, "create_location_solution_configuration_draft", create)
    monkeypatch.setattr(actions, "submit_location_solution_configuration", submit)
    monkeypatch.setattr(actions, "review_location_solution_configuration", review)
    app = FastAPI()
    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_solution_lifecycle_routes(router, object(), run_in_threadpool, SimpleNamespace(Error=Exception))
    app.include_router(router)

    @app.middleware("http")
    async def add_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(operator=SimpleNamespace(operator_id=OPERATOR_ID))
        return await call_next(request)

    base = f"/operator/api/solution-lifecycle/{LOCATION_ID}/adoption/configurations"
    with TestClient(app) as client:
        created = client.post(base, json=BODY)
        rejected = client.post(base, json={**BODY, "approved_by_party_id": OPERATOR_ID})
        submitted = client.post(f"{base}/{CONFIGURATION_ID}/submit", json={"request_id": REQUEST_ID, "acknowledged": True})
        reviewed = client.post(f"{base}/{CONFIGURATION_ID}/review", json={
            "request_id": REQUEST_ID, "decision": "approved", "review_note": "Evidence reviewed.", "acknowledged": True,
        })

    assert created.status_code == 201
    assert created.headers["cache-control"] == "no-store"
    assert created.headers["vary"] == "Cookie"
    assert created.json() == CREATED
    assert rejected.status_code == 400
    assert submitted.status_code == 201 and submitted.headers["cache-control"] == "no-store"
    assert reviewed.status_code == 201 and reviewed.headers["cache-control"] == "no-store"
    assert [call[0] for call in calls] == ["create", "submit", "review"]

