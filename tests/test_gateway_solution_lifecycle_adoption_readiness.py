"""Scoped adoption-readiness assessment and independent-review contracts."""

from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest

from services.gateway import solution_lifecycle_actions as actions
from services.gateway.operator_auth import auth_route_policy

pytest.importorskip("fastapi")
from fastapi import APIRouter, FastAPI  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

OPERATOR_ID = str(uuid4())
OTHER_OPERATOR_ID = str(uuid4())
LOCATION_ID = str(uuid4())
SOLUTION_ID = str(uuid4())
ASSESSMENT_ID = str(uuid4())
READINESS_ID = str(uuid4())
REQUEST_ID = str(uuid4())
REVIEW_REQUEST_ID = str(uuid4())

ASSESSMENT = {
    "assessment_id": ASSESSMENT_ID,
    "readiness_id": READINESS_ID,
    "solution_id": SOLUTION_ID,
    "current_level": "4.500",
    "required_level": "4.000",
    "readiness_status": "submitted",
    "assessed_at": "2026-10-20T12:00:00+00:00",
    "replayed": False,
}
QUEUE_ROW = {
    "assessment_id": ASSESSMENT_ID,
    "readiness_id": READINESS_ID,
    "solution_id": SOLUTION_ID,
    "current_level": Decimal("4.500"),
    "required_level": Decimal("4.000"),
    "remediation_plan": None,
    "assessed_at": datetime(2026, 10, 20, 12, tzinfo=timezone.utc),
}
QUEUE_ROW_JSON = {
    **QUEUE_ROW,
    "current_level": 4.5,
    "required_level": 4.0,
    "assessed_at": "2026-10-20T12:00:00+00:00",
}
REVIEW = {
    "assessment_id": ASSESSMENT_ID,
    "readiness_id": READINESS_ID,
    "decision": "ready",
    "readiness_status": "ready",
    "reviewed_at": "2026-10-20T13:00:00+00:00",
    "replayed": False,
}


class _Connection:
    def __init__(self, *, rows=(), result=None, fail=False):
        self.rows = rows
        self.result = result
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


class _Column:
    def __init__(self, name):
        self.name = name

    def __getitem__(self, index):
        if index != 0:
            raise IndexError(index)
        return self.name


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
        if self.connection.fail and "solution_adopter_readiness" in normalized:
            raise RuntimeError("synthetic readiness database failure")
        if "submit_location_solution_adopter_readiness" in normalized:
            self.description = tuple(_Column(key) for key in ASSESSMENT)
        elif "location_solution_adopter_readiness_review_queue" in normalized:
            self.description = tuple(_Column(key) for key in QUEUE_ROW)
        elif "review_location_solution_adopter_readiness" in normalized:
            self.description = tuple(_Column(key) for key in REVIEW)

    def fetchone(self):
        return tuple(self.connection.result.values())

    def fetchall(self):
        return [tuple(row.values()) for row in self.connection.rows]


def test_readiness_assessment_action_sets_create_context_and_commits_exact_values():
    connection = _Connection(result=ASSESSMENT)
    contexts = []

    def set_context(conn, **kwargs):
        assert conn is connection
        contexts.append(kwargs)

    with patch.object(actions, "set_operator_tenant_context", set_context):
        result = actions.submit_location_solution_adopter_readiness(
            OPERATOR_ID, LOCATION_ID, SOLUTION_ID, REQUEST_ID, "4.5000", 4,
            remediation_plan="  Maintain the current water buffer.  ",
            acknowledged=True,
            connection_factory=lambda: connection,
        )

    assert contexts == [{
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "solution_lifecycle",
        "action": "create",
    }]
    assert "kokonut_security.submit_location_solution_adopter_readiness" in connection.operations[-1][0]
    assert connection.operations[-1][1] == (
        LOCATION_ID, SOLUTION_ID, REQUEST_ID, "4.500", "4.000",
        "Maintain the current water buffer.", True,
    )
    assert result == ASSESSMENT
    assert connection.committed and connection.closed and not connection.rolled_back


@pytest.mark.parametrize(
    "current,required,plan,acknowledged",
    [
        (True, 1, None, True),
        (float("nan"), 1, None, True),
        (1000, 1, None, True),
        (1.0001, 1, None, True),
        (1, 1, "x" * 4001, True),
        (1, 1, None, False),
    ],
)
def test_invalid_readiness_assessment_fails_before_database_access(current, required, plan, acknowledged):
    with pytest.raises(actions.SolutionLifecycleActionInvalid):
        actions.submit_location_solution_adopter_readiness(
            OPERATOR_ID, LOCATION_ID, SOLUTION_ID, REQUEST_ID, current, required,
            remediation_plan=plan,
            acknowledged=acknowledged,
            connection_factory=lambda: pytest.fail("invalid assessment must fail before DB access"),
        )


def test_readiness_queue_sets_review_context_bounds_page_and_uses_same_connection():
    rows = [QUEUE_ROW, {**QUEUE_ROW, "assessment_id": str(uuid4())},
            {**QUEUE_ROW, "assessment_id": str(uuid4())}]
    connection = _Connection(rows=rows)
    contexts = []
    with patch.object(actions, "set_operator_tenant_context", lambda conn, **kwargs: contexts.append((conn, kwargs))):
        result = actions.get_location_solution_adopter_readiness_review_queue(
            OTHER_OPERATOR_ID, LOCATION_ID, limit=2, offset=5,
            connection_factory=lambda: connection,
        )
    assert contexts == [(connection, {
        "operator_id": OTHER_OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "solution_lifecycle",
        "action": "review",
    })]
    assert "location_solution_adopter_readiness_review_queue" in connection.operations[-1][0]
    assert connection.operations[-1][1] == (LOCATION_ID, 3, 5)
    assert result == {
        "assessments": rows[:2], "has_more": True, "next_offset": 7,
    }
    assert connection.committed and connection.closed and not connection.rolled_back


@pytest.mark.parametrize("limit,offset", [(0, 0), (101, 0), (25, -1), (25, 10001), (True, 0)])
def test_invalid_readiness_queue_page_fails_before_database_access(limit, offset):
    with pytest.raises(actions.SolutionLifecycleActionInvalid):
        actions.get_location_solution_adopter_readiness_review_queue(
            OPERATOR_ID, LOCATION_ID, limit=limit, offset=offset,
            connection_factory=lambda: pytest.fail("invalid page must fail before DB access"),
        )


@pytest.mark.parametrize(
    "decision,note,acknowledged",
    [
        ("approved", "Independent review.", True),
        ("ready", "  ", True),
        ("ready", "x" * 2001, True),
        ("ready", "🪴" * 1200, True),
        ("ready", "Independent review.", False),
    ],
)
def test_invalid_readiness_review_fails_before_database_access(decision, note, acknowledged):
    with pytest.raises(actions.SolutionLifecycleActionInvalid):
        actions.review_location_solution_adopter_readiness(
            OTHER_OPERATOR_ID, LOCATION_ID, ASSESSMENT_ID, REVIEW_REQUEST_ID,
            decision, note, acknowledged=acknowledged,
            connection_factory=lambda: pytest.fail("invalid review must fail before DB access"),
        )


def test_readiness_review_action_uses_review_context_and_rolls_back_failure():
    connection = _Connection(result=REVIEW, fail=True)
    contexts = []
    with patch.object(actions, "set_operator_tenant_context", lambda conn, **kwargs: contexts.append((conn, kwargs))):
        with pytest.raises(RuntimeError, match="synthetic readiness database failure"):
            actions.review_location_solution_adopter_readiness(
                OTHER_OPERATOR_ID, LOCATION_ID, ASSESSMENT_ID, REVIEW_REQUEST_ID,
                "ready", " Independently checked the required level. ",
                acknowledged=True,
                connection_factory=lambda: connection,
            )
    assert contexts == [(connection, {
        "operator_id": OTHER_OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "solution_lifecycle",
        "action": "review",
    })]
    assert connection.operations[-1][1] == (
        LOCATION_ID, ASSESSMENT_ID, REVIEW_REQUEST_ID,
        "ready", "Independently checked the required level.", True,
    )
    assert connection.rolled_back and connection.closed and not connection.committed


def test_readiness_routes_have_exact_location_grants_and_no_public_fallback():
    cases = [
        ("POST", f"/operator/api/solution-lifecycle/{LOCATION_ID}/adoption/readiness", "create"),
        ("GET", f"/operator/api/solution-lifecycle/{LOCATION_ID}/adoption/readiness/review-queue", "review"),
        ("POST", f"/operator/api/solution-lifecycle/{LOCATION_ID}/adoption/readiness/{ASSESSMENT_ID}/review", "review"),
    ]
    for method, path, action in cases:
        assert auth_route_policy(method, path, enabled=True) == {
            "resource": "solution_lifecycle",
            "action": action,
            "public": False,
            "location_id": LOCATION_ID,
            "scope_required": True,
            "operator_auth": True,
        }
        assert auth_route_policy(method, path, enabled=False) is None
    assert auth_route_policy("POST", f"/operator/api/solution-lifecycle/{LOCATION_ID}/adoption/readiness/extra", enabled=True) is None


def test_readiness_http_routes_use_no_store_exact_payload_and_review_grant(monkeypatch):
    from services.gateway.solution_lifecycle_routes import register_solution_lifecycle_routes

    calls = []
    monkeypatch.setattr(actions, "submit_location_solution_adopter_readiness", lambda *args, **kwargs: calls.append(("submit", args, kwargs)) or ASSESSMENT)
    monkeypatch.setattr(actions, "get_location_solution_adopter_readiness_review_queue", lambda *args, **kwargs: calls.append(("queue", args, kwargs)) or {"assessments": [QUEUE_ROW], "has_more": False, "next_offset": None})
    monkeypatch.setattr(actions, "review_location_solution_adopter_readiness", lambda *args, **kwargs: calls.append(("review", args, kwargs)) or REVIEW)
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

    with TestClient(app) as client:
        submitted = client.post(
            f"/operator/api/solution-lifecycle/{LOCATION_ID}/adoption/readiness",
            json={"request_id": REQUEST_ID, "solution_id": SOLUTION_ID,
                  "current_level": 4.5, "required_level": 4, "acknowledged": True},
        )
        queued = client.get(
            f"/operator/api/solution-lifecycle/{LOCATION_ID}/adoption/readiness/review-queue?limit=1&offset=20"
        )
        reviewed = client.post(
            f"/operator/api/solution-lifecycle/{LOCATION_ID}/adoption/readiness/{ASSESSMENT_ID}/review",
            json={"request_id": REVIEW_REQUEST_ID, "decision": "ready",
                  "review_note": "Independent review.", "acknowledged": True},
        )
        invalid = client.post(
            f"/operator/api/solution-lifecycle/{LOCATION_ID}/adoption/readiness",
            json={"request_id": REQUEST_ID, "solution_id": SOLUTION_ID,
                  "current_level": 4.5, "required_level": 4, "acknowledged": True,
                  "readiness_status": "ready"},
        )

    for response in (submitted, queued, reviewed):
        assert response.headers["cache-control"] == "no-store"
        assert response.headers["vary"] == "Cookie"
    assert submitted.status_code == 201 and submitted.json() == ASSESSMENT
    assert queued.status_code == 200 and queued.json() == {
        "location_id": LOCATION_ID,
        "limit": 1,
        "offset": 20,
        "assessments": [QUEUE_ROW_JSON],
        "has_more": False,
        "next_offset": None,
        "offset_limited": False,
    }
    assert reviewed.status_code == 201 and reviewed.json() == REVIEW
    assert invalid.status_code == 400
    assert [call[0] for call in calls] == ["submit", "queue", "review"]
    assert calls[1][1] == (OPERATOR_ID, LOCATION_ID)
    assert calls[1][2] == {"limit": 1, "offset": 20}


def _readiness_queue_app(monkeypatch, result):
    from services.gateway.solution_lifecycle_routes import register_solution_lifecycle_routes

    monkeypatch.setattr(
        actions,
        "get_location_solution_adopter_readiness_review_queue",
        lambda *_args, **_kwargs: result,
    )
    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_solution_lifecycle_routes(
        router, object(), run_in_threadpool, SimpleNamespace(Error=Exception)
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


def test_readiness_queue_openapi_declares_exact_strict_page_and_item_contract():
    from services.gateway.solution_lifecycle_routes import register_solution_lifecycle_routes

    router = APIRouter()

    async def run_in_threadpool(*_args, **_kwargs):
        pytest.fail("OpenAPI inspection must not invoke the queue action")

    register_solution_lifecycle_routes(
        router, object(), run_in_threadpool, SimpleNamespace(Error=Exception)
    )
    app = FastAPI()
    app.include_router(router)
    openapi = app.openapi()
    operation = openapi["paths"][
        "/operator/api/solution-lifecycle/{location_id}/adoption/readiness/review-queue"
    ]["get"]
    page_ref = operation["responses"]["200"]["content"]["application/json"]["schema"]["$ref"]
    page_name = page_ref.rsplit("/", 1)[-1]
    page = openapi["components"]["schemas"][page_name]
    assert list(page["properties"]) == [
        "location_id", "limit", "offset", "assessments", "has_more",
        "next_offset", "offset_limited",
    ]
    assert page["additionalProperties"] is False
    item_ref = page["properties"]["assessments"]["items"]["$ref"]
    item_name = item_ref.rsplit("/", 1)[-1]
    item = openapi["components"]["schemas"][item_name]
    assert list(item["properties"]) == list(QUEUE_ROW)
    assert item["additionalProperties"] is False


@pytest.mark.parametrize("result", [
    {
        "assessments": [QUEUE_ROW], "has_more": False, "next_offset": None,
        "sensitive": "must not leak",
    },
    {
        "assessments": [{**QUEUE_ROW, "current_level": Decimal("1000")}],
        "has_more": False, "next_offset": None,
    },
    {
        "assessments": [{**QUEUE_ROW, "remediation_plan": "x" * 4001}],
        "has_more": False, "next_offset": None,
    },
])
def test_readiness_queue_rejects_malformed_output_with_sanitized_no_store_error(
    monkeypatch, result
):
    app = _readiness_queue_app(monkeypatch, result)
    path = f"/operator/api/solution-lifecycle/{LOCATION_ID}/adoption/readiness/review-queue"

    with TestClient(app) as client:
        response = client.get(path, params={"limit": 1, "offset": 0})

    assert response.status_code == 500
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {
        "error": "Solution adoption readiness review queue unavailable"
    }
    assert "must not leak" not in response.text and ASSESSMENT_ID not in response.text


@pytest.mark.parametrize("assessments", [
    [QUEUE_ROW, QUEUE_ROW],
    [
        {**QUEUE_ROW, "assessment_id": "00000000-0000-4000-8000-000000000001"},
        {**QUEUE_ROW, "assessment_id": "00000000-0000-4000-8000-000000000002"},
    ],
])
def test_readiness_queue_rejects_duplicate_or_out_of_order_items(monkeypatch, assessments):
    app = _readiness_queue_app(monkeypatch, {
        "assessments": assessments, "has_more": False, "next_offset": None,
    })
    path = f"/operator/api/solution-lifecycle/{LOCATION_ID}/adoption/readiness/review-queue"

    with TestClient(app) as client:
        response = client.get(path, params={"limit": 2, "offset": 0})

    assert response.status_code == 500
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {
        "error": "Solution adoption readiness review queue unavailable"
    }


def test_readiness_queue_stops_continuation_at_offset_cap(monkeypatch):
    app = _readiness_queue_app(monkeypatch, {
        "assessments": [QUEUE_ROW], "has_more": True, "next_offset": 10001,
    })
    path = f"/operator/api/solution-lifecycle/{LOCATION_ID}/adoption/readiness/review-queue"

    with TestClient(app) as client:
        response = client.get(path, params={"limit": 1, "offset": 10000})

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {
        "location_id": LOCATION_ID,
        "limit": 1,
        "offset": 10000,
        "assessments": [QUEUE_ROW_JSON],
        "has_more": False,
        "next_offset": None,
        "offset_limited": True,
    }


def test_readiness_routes_fail_closed_without_oidc():
    from services.gateway.solution_lifecycle_routes import register_solution_lifecycle_routes

    app = FastAPI()
    router = APIRouter()

    async def run_in_threadpool(*_args, **_kwargs):
        pytest.fail("OIDC-disabled readiness route must not invoke actions")

    register_solution_lifecycle_routes(router, None, run_in_threadpool, SimpleNamespace(Error=Exception))
    app.include_router(router)
    with TestClient(app) as client:
        response = client.get(f"/operator/api/solution-lifecycle/{LOCATION_ID}/adoption/readiness/review-queue")
    assert response.status_code == 404
