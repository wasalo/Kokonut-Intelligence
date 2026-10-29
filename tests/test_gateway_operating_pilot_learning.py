"""Private, bounded CAP-037 learning-plan history regressions."""

from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest

from services.common.tenant_context import TenantContextDenied
from services.gateway import operating_pilot_reads as reads
from services.gateway.operator_auth import auth_route_policy

pytest.importorskip("fastapi")
from fastapi import APIRouter, FastAPI  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

OPERATOR_ID = str(uuid4())
LOCATION_ID = str(uuid4())


class _Connection:
    def __init__(self, row):
        self.row = row
        self.operations = []
        self.rolled_back = False
        self.closed = False

    def cursor(self):
        return _Cursor(self)

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


class _Cursor:
    def __init__(self, connection):
        self.connection = connection

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def execute(self, query, params=None):
        self.connection.operations.append((" ".join(query.split()), params))

    def fetchone(self):
        return (self.connection.row,)


def _own_learning_plan_page(*, location_id=LOCATION_ID, limit=7, offset=14, items=None):
    item = {
        "learning_plan_id": str(uuid4()),
        "title": "Private synthetic goal",
        "competency_goals": [{"competency": "soil_observation"}],
        "support_requested": ["mentor time"],
        "target_date": "2026-12-01",
        "status": "draft",
        "review_decision": None,
        "review_reason": None,
        "reviewed_at": None,
        "created_at": "2026-10-28T12:00:00+00:00",
        "updated_at": "2026-10-28T12:00:00+00:00",
    }
    return {
        "location_id": location_id,
        "limit": limit,
        "offset": offset,
        "items": [item] if items is None else items,
        "has_more": False,
        "next_offset": None,
    }


def _own_learning_plan_http_app(monkeypatch, result):
    from services.gateway.operating_pilot_routes import register_operating_pilot_routes

    calls = []
    monkeypatch.setattr(
        "services.gateway.operating_pilot_reads.get_location_operating_pilot_own_learning_plans",
        lambda *args, **kwargs: calls.append((args, kwargs)) or result,
    )
    app = FastAPI()
    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_operating_pilot_routes(
        router, object(), run_in_threadpool, SimpleNamespace(Error=Exception)
    )
    app.include_router(router)

    @app.middleware("http")
    async def add_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    return app, calls


def test_own_learning_plans_use_read_only_exact_tenant_context_and_cleanup():
    page = {"items": [{"title": "Private goal"}], "has_more": False}
    connection = _Connection(page)
    contexts = []

    def set_context(conn, **kwargs):
        assert conn is connection
        contexts.append(kwargs)

    with patch.object(reads, "set_operator_tenant_context", set_context):
        result = reads.get_location_operating_pilot_own_learning_plans(
            OPERATOR_ID,
            LOCATION_ID,
            limit=7,
            offset=14,
            connection_factory=lambda: connection,
        )

    assert contexts == [{
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "operating_pilot",
        "action": "read_own",
    }]
    assert [query for query, _ in connection.operations[:3]] == [
        "SET TRANSACTION READ ONLY",
        "SET LOCAL statement_timeout = '8s'",
        "SET LOCAL lock_timeout = '2s'",
    ]
    assert "location_operating_pilot_own_learning_plans" in connection.operations[-1][0]
    assert connection.operations[-1][1] == (LOCATION_ID, 7, 14)
    assert result == {"location_id": LOCATION_ID, **page}
    assert connection.rolled_back and connection.closed


@pytest.mark.parametrize("limit,offset", [
    (0, 0), (51, 0), (True, 0), (25, -1), (25, 10001), (25, False),
])
def test_own_learning_plans_reject_invalid_page_before_database_access(limit, offset):
    with pytest.raises(reads.OperatingPilotReadInvalid):
        reads.get_location_operating_pilot_own_learning_plans(
            OPERATOR_ID,
            LOCATION_ID,
            limit=limit,
            offset=offset,
            connection_factory=lambda: pytest.fail("invalid page must fail before DB access"),
        )


def test_own_learning_plans_tenant_denial_rolls_back_without_projection():
    connection = _Connection({})

    def deny(*_args, **_kwargs):
        raise TenantContextDenied("denied")

    with patch.object(reads, "set_operator_tenant_context", deny):
        with pytest.raises(TenantContextDenied):
            reads.get_location_operating_pilot_own_learning_plans(
                OPERATOR_ID,
                LOCATION_ID,
                connection_factory=lambda: connection,
            )
    assert not any(
        "location_operating_pilot_own_learning_plans" in query
        for query, _ in connection.operations
    )
    assert connection.rolled_back and connection.closed


def test_learning_plan_history_policy_is_exact_location_and_read_own_only():
    path = f"/operator/api/operating-pilot/{LOCATION_ID}/my-learning-plans"
    assert auth_route_policy("GET", path, enabled=True) == {
        "resource": "operating_pilot",
        "action": "read_own",
        "public": False,
        "location_id": LOCATION_ID,
        "scope_required": True,
        "operator_auth": True,
    }
    assert auth_route_policy("POST", path, enabled=True) is None
    assert auth_route_policy("GET", path, enabled=False) is None


def test_http_own_learning_plans_are_no_store_and_paginated(monkeypatch):
    page = _own_learning_plan_page()
    app, calls = _own_learning_plan_http_app(monkeypatch, page)

    with TestClient(app) as client:
        response = client.get(
            f"/operator/api/operating-pilot/{LOCATION_ID}/my-learning-plans?limit=7&offset=14"
        )
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    body = response.json()
    assert body["location_id"] == LOCATION_ID
    assert body["limit"] == 7
    assert body["offset"] == 14
    assert body["has_more"] is False
    assert body["next_offset"] is None
    assert body["items"][0]["learning_plan_id"] == page["items"][0]["learning_plan_id"]
    assert body["items"][0]["competency_goals"] == page["items"][0]["competency_goals"]
    assert body["items"][0]["support_requested"] == page["items"][0]["support_requested"]
    assert body["items"][0]["target_date"] == "2026-12-01"
    assert body["items"][0]["status"] == "draft"
    assert body["items"][0]["review_decision"] is None
    assert body["items"][0]["review_reason"] is None
    assert calls == [((OPERATOR_ID, LOCATION_ID), {"limit": 7, "offset": 14})]


@pytest.mark.parametrize(
    "mutate",
    [
        pytest.param(lambda page: page["items"][0].pop("title"), id="missing-field"),
        pytest.param(lambda page: page["items"][0].update(party_id=str(uuid4())), id="extra-field"),
        pytest.param(lambda page: page.update(location_id=str(uuid4())), id="wrong-location"),
        pytest.param(lambda page: page.update(limit=8), id="wrong-limit"),
        pytest.param(lambda page: page.update(offset=13), id="wrong-offset"),
        pytest.param(lambda page: page.update(unexpected="private"), id="extra-page-field"),
    ],
)
def test_http_own_learning_plans_reject_malformed_or_mismatched_provider_page(
    monkeypatch, mutate
):
    page = _own_learning_plan_page()
    mutate(page)
    app, _calls = _own_learning_plan_http_app(monkeypatch, page)

    with TestClient(app) as client:
        response = client.get(
            f"/operator/api/operating-pilot/{LOCATION_ID}/my-learning-plans?limit=7&offset=14"
        )

    assert response.status_code == 500
    assert response.json() == {"error": "Own learning-plan history unavailable"}
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"


@pytest.mark.parametrize(
    "review, expected_status",
    [
        pytest.param(
            {"review_decision": "approved", "review_reason": None,
             "reviewed_at": "2026-10-28T13:00:00+00:00"},
            200,
            id="approved-without-feedback",
        ),
        pytest.param(
            {"review_decision": "rejected", "review_reason": "Add field evidence",
             "reviewed_at": "2026-10-28T13:00:00+00:00"},
            200,
            id="rejected-with-owner-feedback",
        ),
        pytest.param(
            {"review_decision": "approved", "review_reason": "unexpected",
             "reviewed_at": "2026-10-28T13:00:00+00:00"},
            500,
            id="approved-with-reason",
        ),
        pytest.param(
            {"review_decision": "rejected", "review_reason": None,
             "reviewed_at": "2026-10-28T13:00:00+00:00"},
            500,
            id="rejected-without-reason",
        ),
        pytest.param(
            {"review_decision": None, "review_reason": "orphan feedback",
             "reviewed_at": None},
            500,
            id="feedback-without-decision",
        ),
        pytest.param(
            {"review_decision": "approved", "review_reason": None,
             "reviewed_at": None},
            500,
            id="decision-without-timestamp",
        ),
    ],
)
def test_http_own_learning_plans_validate_review_metadata(monkeypatch, review, expected_status):
    page = _own_learning_plan_page()
    page["items"][0].update(review)
    app, _calls = _own_learning_plan_http_app(monkeypatch, page)

    with TestClient(app) as client:
        response = client.get(
            f"/operator/api/operating-pilot/{LOCATION_ID}/my-learning-plans?limit=7&offset=14"
        )

    assert response.status_code == expected_status
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    if expected_status == 200:
        assert response.json()["items"][0]["review_decision"] == review["review_decision"]
    else:
        assert response.json() == {"error": "Own learning-plan history unavailable"}


@pytest.mark.parametrize("violation", ["duplicate", "ascending"])
def test_http_own_learning_plans_reject_duplicate_or_out_of_order_items(
    monkeypatch, violation
):
    first = _own_learning_plan_page()["items"][0]
    second = {**first, "learning_plan_id": str(uuid4())}
    if violation == "duplicate":
        second["learning_plan_id"] = first["learning_plan_id"]
    else:
        first["learning_plan_id"] = "00000000-0000-4000-8000-000000000001"
        second["learning_plan_id"] = "00000000-0000-4000-8000-000000000002"
    page = _own_learning_plan_page(items=[first, second])
    app, _calls = _own_learning_plan_http_app(monkeypatch, page)

    with TestClient(app) as client:
        response = client.get(
            f"/operator/api/operating-pilot/{LOCATION_ID}/my-learning-plans?limit=7&offset=14"
        )

    assert response.status_code == 500
    assert response.json() == {"error": "Own learning-plan history unavailable"}
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"


@pytest.mark.parametrize(
    "continuation, expected_status",
    [
        pytest.param("valid", 200, id="full-page-with-continuation"),
        pytest.param("short", 500, id="short-page-with-continuation"),
        pytest.param("wrong-offset", 500, id="wrong-continuation-offset"),
        pytest.param("terminal-offset", 500, id="terminal-page-with-continuation"),
    ],
)
def test_http_own_learning_plans_validate_continuation_page_contract(
    monkeypatch, continuation, expected_status
):
    first = _own_learning_plan_page()["items"][0]
    second = {
        **first,
        "learning_plan_id": "00000000-0000-4000-8000-000000000001",
        "created_at": "2026-10-27T12:00:00+00:00",
        "updated_at": "2026-10-27T12:00:00+00:00",
    }
    first["learning_plan_id"] = "00000000-0000-4000-8000-000000000002"
    page = _own_learning_plan_page(limit=2, items=[first, second])
    page["has_more"] = continuation != "terminal-offset"
    page["next_offset"] = 16 if continuation != "wrong-offset" else 15
    if continuation == "short":
        page["items"] = [first]
    app, _calls = _own_learning_plan_http_app(monkeypatch, page)

    with TestClient(app) as client:
        response = client.get(
            f"/operator/api/operating-pilot/{LOCATION_ID}/my-learning-plans?limit=2&offset=14"
        )

    assert response.status_code == expected_status
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    if expected_status == 200:
        assert response.json()["has_more"] is True
        assert len(response.json()["items"]) == 2
        assert response.json()["next_offset"] == 16
    else:
        assert response.json() == {"error": "Own learning-plan history unavailable"}


def test_http_learning_plans_fail_closed_when_oidc_is_disabled(monkeypatch):
    from services.gateway.operating_pilot_routes import register_operating_pilot_routes

    monkeypatch.setattr(
        "services.gateway.operating_pilot_reads.get_location_operating_pilot_own_learning_plans",
        lambda *_args, **_kwargs: pytest.fail("disabled OIDC must not query private plans"),
    )
    app = FastAPI()
    router = APIRouter()
    register_operating_pilot_routes(router, None, lambda *_args: None,
                                    SimpleNamespace(Error=Exception))
    app.include_router(router)
    with TestClient(app) as client:
        response = client.get(
            f"/operator/api/operating-pilot/{LOCATION_ID}/my-learning-plans"
        )
    assert response.status_code == 404
    assert response.headers["cache-control"] == "no-store"


def test_own_coaching_history_uses_coach_scope_and_read_only_transaction():
    page = {"items": [{"focus": "Private synthetic coaching"}], "has_more": False}
    connection = _Connection(page)
    contexts = []

    with patch.object(
        reads,
        "set_operator_tenant_context",
        lambda conn, **kwargs: contexts.append((conn, kwargs)),
    ):
        result = reads.get_location_operating_pilot_own_coaching_sessions(
            OPERATOR_ID, LOCATION_ID, limit=5, offset=10,
            connection_factory=lambda: connection,
        )

    assert contexts == [(connection, {
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "operating_pilot",
        "action": "coach",
    })]
    assert [query for query, _ in connection.operations[:3]] == [
        "SET TRANSACTION READ ONLY",
        "SET LOCAL statement_timeout = '8s'",
        "SET LOCAL lock_timeout = '2s'",
    ]
    assert "location_operating_pilot_own_coaching_sessions" in connection.operations[-1][0]
    assert connection.operations[-1][1] == (LOCATION_ID, 5, 10)
    assert result == {"location_id": LOCATION_ID, **page}
    assert connection.rolled_back and connection.closed


def test_coaching_history_route_is_private_no_store_and_coach_grant_gated(monkeypatch):
    from services.gateway.operating_pilot_routes import register_operating_pilot_routes

    page = {"location_id": LOCATION_ID, "items": [], "has_more": False}
    calls = []
    monkeypatch.setattr(
        "services.gateway.operating_pilot_reads.get_location_operating_pilot_own_coaching_sessions",
        lambda *args, **kwargs: calls.append((args, kwargs)) or page,
    )
    app = FastAPI()
    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_operating_pilot_routes(
        router, object(), run_in_threadpool, SimpleNamespace(Error=Exception)
    )
    app.include_router(router)

    @app.middleware("http")
    async def add_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    path = f"/operator/api/operating-pilot/{LOCATION_ID}/my-coaching-sessions"
    with TestClient(app) as client:
        response = client.get(f"{path}?limit=5&offset=10")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert response.json() == page
    assert calls == [((OPERATOR_ID, LOCATION_ID), {"limit": 5, "offset": 10})]
    assert auth_route_policy("GET", path, enabled=True) == {
        "resource": "operating_pilot",
        "action": "coach",
        "public": False,
        "location_id": LOCATION_ID,
        "scope_required": True,
        "operator_auth": True,
    }
    assert auth_route_policy("POST", path, enabled=True) is None


def test_coaching_participants_use_read_only_exact_tenant_context_and_cleanup():
    page = {"items": [{"participant_id": str(uuid4()), "display_name": "Consented participant"}], "has_more": False}
    connection = _Connection(page)
    contexts = []

    with patch.object(
        reads,
        "set_operator_tenant_context",
        lambda conn, **kwargs: contexts.append((conn, kwargs)),
    ):
        result = reads.get_location_operating_pilot_coaching_participants(
            OPERATOR_ID,
            LOCATION_ID,
            search="  participant  ",
            limit=7,
            offset=14,
            connection_factory=lambda: connection,
        )

    assert contexts == [(connection, {
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "operating_pilot",
        "action": "coach",
    })]
    assert [query for query, _ in connection.operations[:3]] == [
        "SET TRANSACTION READ ONLY",
        "SET LOCAL statement_timeout = '8s'",
        "SET LOCAL lock_timeout = '2s'",
    ]
    assert "location_operating_pilot_coaching_participants" in connection.operations[-1][0]
    assert connection.operations[-1][1] == (LOCATION_ID, "participant", 7, 14)
    assert result == {"location_id": LOCATION_ID, **page}
    assert connection.rolled_back and connection.closed


@pytest.mark.parametrize("search", ["x" * 81, "bad\nsearch", 1, [], {}])
def test_coaching_participants_reject_invalid_search_before_database_access(search):
    with pytest.raises(reads.OperatingPilotReadInvalid):
        reads.get_location_operating_pilot_coaching_participants(
            OPERATOR_ID,
            LOCATION_ID,
            search=search,
            connection_factory=lambda: pytest.fail("invalid search must fail before DB access"),
        )


def test_coaching_participant_route_is_private_no_store_and_coach_grant_gated(monkeypatch):
    from services.gateway.operating_pilot_routes import register_operating_pilot_routes

    page = {"location_id": LOCATION_ID, "items": [], "has_more": False}
    calls = []
    monkeypatch.setattr(
        "services.gateway.operating_pilot_reads.get_location_operating_pilot_coaching_participants",
        lambda *args, **kwargs: calls.append((args, kwargs)) or page,
    )
    app = FastAPI()
    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_operating_pilot_routes(
        router, object(), run_in_threadpool, SimpleNamespace(Error=Exception)
    )
    app.include_router(router)

    @app.middleware("http")
    async def add_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    path = f"/operator/api/operating-pilot/{LOCATION_ID}/coaching-participants"
    with TestClient(app) as client:
        response = client.get(f"{path}?q=seed&limit=7&offset=14")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert response.json() == page
    assert calls == [((OPERATOR_ID, LOCATION_ID), {"search": "seed", "limit": 7, "offset": 14})]
    assert auth_route_policy("GET", path, enabled=True) == {
        "resource": "operating_pilot",
        "action": "coach",
        "public": False,
        "location_id": LOCATION_ID,
        "scope_required": True,
        "operator_auth": True,
    }
    assert auth_route_policy("POST", path, enabled=True) is None
