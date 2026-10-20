"""Exact-location adoption-program draft creation contracts."""

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
    "program_id": str(uuid4()),
    "solution_id": SOLUTION_ID,
    "program_status": "draft",
    "created_at": "2026-10-20T12:00:00+00:00",
    "replayed": False,
    "consent_policy": {
        "data_category": "solution_adoption_participation",
        "purpose": "Track voluntary participation",
        "consent_version": "1.0",
    },
}
CREATE_ROW = {key: value for key, value in CREATED.items() if key != "consent_policy"}
POLICY_ROW = {
    "program_id": CREATED["program_id"],
    "consent_purpose": "Track voluntary participation",
    "consent_version": "1.0",
    "configured_at": "2026-10-20T12:00:00+00:00",
    "replayed": False,
}
BODY = {
    "request_id": REQUEST_ID,
    "solution_id": SOLUTION_ID,
    "adoption_pathway": "Community-led training and field support",
    "local_adaptation_policy": "Preserve water safety invariants.",
    "consent_purpose": "Track voluntary participation",
    "consent_version": "1.0",
    "acknowledged": True,
}


class _Connection:
    def __init__(self, *, fail_query=False):
        self.fail_query = fail_query
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
        self.description = tuple(SimpleNamespace(name=name) for name in CREATE_ROW)
        self.result = CREATE_ROW

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def execute(self, query, params=None):
        self.connection.operations.append((" ".join(query.split()), params))
        if self.connection.fail_query and "create_location_solution_adoption_program" in query:
            raise RuntimeError("database adoption draft failed")
        if "configure_location_solution_adoption_consent_policy" in query:
            self.result = POLICY_ROW
            self.description = tuple(SimpleNamespace(name=name) for name in POLICY_ROW)

    def fetchone(self):
        return tuple(self.result.values())


def test_adoption_program_action_uses_exact_create_context_and_commits_draft():
    connection = _Connection()
    contexts = []

    def set_context(conn, **kwargs):
        assert conn is connection
        contexts.append(kwargs)

    with patch.object(actions, "set_operator_tenant_context", set_context):
        result = actions.create_location_solution_adoption_program(
            OPERATOR_ID, LOCATION_ID, SOLUTION_ID, REQUEST_ID,
            BODY["adoption_pathway"],
            consent_purpose=BODY["consent_purpose"],
            consent_version=BODY["consent_version"],
            local_adaptation_policy=BODY["local_adaptation_policy"],
            acknowledged=True,
            connection_factory=lambda: connection,
        )

    assert contexts == [{
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "solution_lifecycle",
        "action": "create",
    }]
    assert connection.operations[:2] == [
        ("SET LOCAL statement_timeout = '8s'", None),
        ("SET LOCAL lock_timeout = '2s'", None),
    ]
    assert "kokonut_security.create_location_solution_adoption_program" in connection.operations[-2][0]
    assert connection.operations[-2][1] == (
        LOCATION_ID, SOLUTION_ID, REQUEST_ID, BODY["adoption_pathway"],
        BODY["local_adaptation_policy"], True,
    )
    assert "configure_location_solution_adoption_consent_policy" in connection.operations[-1][0]
    assert connection.operations[-1][1] == (
        LOCATION_ID, CREATED["program_id"], REQUEST_ID,
        BODY["consent_purpose"], BODY["consent_version"], True,
    )
    assert result == CREATED
    assert connection.committed and connection.closed and not connection.rolled_back


@pytest.mark.parametrize(
    "changes",
    [
        {"adoption_pathway": " "},
        {"adoption_pathway": "x" * 2001},
        {"local_adaptation_policy": "x" * 4001},
        {"acknowledged": False},
    ],
)
def test_invalid_adoption_program_fails_before_database_access(changes):
    payload = {**BODY, **changes}
    with pytest.raises(actions.SolutionLifecycleActionInvalid):
        actions.create_location_solution_adoption_program(
            OPERATOR_ID, LOCATION_ID, payload["solution_id"],
            payload["request_id"], payload["adoption_pathway"],
            consent_purpose=payload["consent_purpose"],
            consent_version=payload["consent_version"],
            local_adaptation_policy=payload.get("local_adaptation_policy"),
            acknowledged=payload["acknowledged"],
            connection_factory=lambda: pytest.fail("invalid draft must fail before DB access"),
        )


def test_adoption_program_action_rolls_back_and_closes_on_query_failure():
    connection = _Connection(fail_query=True)
    with patch.object(actions, "set_operator_tenant_context", lambda *_args, **_kwargs: None):
        with pytest.raises(RuntimeError, match="database adoption draft failed"):
            actions.create_location_solution_adoption_program(
                OPERATOR_ID, LOCATION_ID, SOLUTION_ID, REQUEST_ID,
                BODY["adoption_pathway"], consent_purpose=BODY["consent_purpose"],
                consent_version=BODY["consent_version"], acknowledged=True,
                connection_factory=lambda: connection,
            )
    assert connection.rolled_back and connection.closed and not connection.committed


def test_adoption_program_route_policy_requires_exact_location_create():
    path = f"/operator/api/solution-lifecycle/{LOCATION_ID}/adoption/programs"
    assert auth_route_policy("POST", path, enabled=True) == {
        "resource": "solution_lifecycle",
        "action": "create",
        "public": False,
        "location_id": LOCATION_ID,
        "scope_required": True,
        "operator_auth": True,
    }
    assert auth_route_policy("GET", path, enabled=True) is None
    assert auth_route_policy("POST", path + "/extra", enabled=True) is None


def test_adoption_consent_and_event_routes_have_explicit_create_and_collect_grants():
    base_path = f"/operator/api/solution-lifecycle/{LOCATION_ID}/adoption/programs"
    consent_path = f"{base_path}/00000000-0000-4000-8000-000000000001/consent-policy"
    event_path = f"{base_path}/00000000-0000-4000-8000-000000000001/events"
    assert auth_route_policy("POST", consent_path, enabled=True) == {
        "resource": "solution_lifecycle", "action": "create", "public": False,
        "location_id": LOCATION_ID, "scope_required": True, "operator_auth": True,
    }
    assert auth_route_policy("POST", event_path, enabled=True) == {
        "resource": "solution_lifecycle", "action": "collect", "public": False,
        "location_id": LOCATION_ID, "scope_required": True, "operator_auth": True,
    }
    assert auth_route_policy("GET", event_path, enabled=True) is None


def test_adoption_event_action_hashes_reference_and_uses_collect_context():
    import hashlib

    participant_ref = "opaque-participant-reference-that-is-long-enough-123456"
    event_result = {
        "event_id": str(uuid4()), "program_id": CREATED["program_id"],
        "event_type": "aware", "observed_at": "2026-10-20T12:00:00+00:00",
        "replayed": False,
    }

    class EventCursor(_Cursor):
        def execute(self, query, params=None):
            super().execute(query, params)
            if "capture_location_solution_adoption_event" in query:
                self.result = event_result
                self.description = tuple(SimpleNamespace(name=name) for name in event_result)

    class EventConnection(_Connection):
        def cursor(self):
            return EventCursor(self)

    connection = EventConnection()
    contexts = []
    with patch.object(actions, "set_operator_tenant_context", lambda _conn, **kwargs: contexts.append(kwargs)):
        result = actions.record_location_solution_adoption_event(
            OPERATOR_ID, LOCATION_ID, CREATED["program_id"], REQUEST_ID,
            participant_ref, "aware", fidelity_score=72.5, acknowledged=True,
            connection_factory=lambda: connection,
        )

    assert contexts[0]["action"] == "collect"
    query, params = connection.operations[-1]
    assert "capture_location_solution_adoption_event" in query
    assert params == (
        LOCATION_ID, CREATED["program_id"], REQUEST_ID,
        hashlib.sha256(participant_ref.encode()).hexdigest(), "aware", "72.500", True,
    )
    assert participant_ref not in repr(params)
    assert result == event_result
    assert connection.committed and connection.closed and not connection.rolled_back


@pytest.mark.parametrize("changes", [
    {"participant_ref": "too-short"},
    {"event_type": "unreviewed"},
    {"fidelity_score": True},
    {"acknowledged": False},
])
def test_invalid_adoption_event_fails_before_database_access(changes):
    payload = {
        "participant_ref": "opaque-participant-reference-that-is-long-enough-123456",
        "event_type": "aware", "fidelity_score": None, "acknowledged": True,
    }
    payload.update(changes)
    with pytest.raises(actions.SolutionLifecycleActionInvalid):
        actions.record_location_solution_adoption_event(
            OPERATOR_ID, LOCATION_ID, CREATED["program_id"], REQUEST_ID,
            payload["participant_ref"], payload["event_type"],
            fidelity_score=payload["fidelity_score"], acknowledged=payload["acknowledged"],
            connection_factory=lambda: pytest.fail("invalid event must fail before DB access"),
        )


@pytest.mark.parametrize("changes", [
    {"consent_purpose": " "},
    {"consent_version": "bad version"},
])
def test_invalid_adoption_consent_policy_fails_before_database_access(changes):
    payload = {**BODY, **changes}
    with pytest.raises(actions.SolutionLifecycleActionInvalid):
        actions.create_location_solution_adoption_program(
            OPERATOR_ID, LOCATION_ID, payload["solution_id"], payload["request_id"],
            payload["adoption_pathway"], consent_purpose=payload["consent_purpose"],
            consent_version=payload["consent_version"], acknowledged=True,
            connection_factory=lambda: pytest.fail("invalid policy must fail before DB access"),
        )


def test_adoption_program_http_route_is_no_store_and_rejects_extra_fields(monkeypatch):
    from services.gateway.solution_lifecycle_routes import register_solution_lifecycle_routes

    calls = []

    def create(*args, **kwargs):
        calls.append((args, kwargs))
        return CREATED

    monkeypatch.setattr(actions, "create_location_solution_adoption_program", create)
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

    path = f"/operator/api/solution-lifecycle/{LOCATION_ID}/adoption/programs"
    with TestClient(app) as client:
        response = client.post(path, json=BODY)
        invalid = client.post(path, json={**BODY, "created_by_party_id": OPERATOR_ID})

    assert response.status_code == 201
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert response.json() == CREATED
    assert calls == [((OPERATOR_ID, LOCATION_ID, SOLUTION_ID, REQUEST_ID,
                       BODY["adoption_pathway"]), {
                           "consent_purpose": BODY["consent_purpose"],
                           "consent_version": BODY["consent_version"],
                           "local_adaptation_policy": BODY["local_adaptation_policy"],
                           "acknowledged": True,
                       })]
    assert invalid.status_code == 400
    assert len(calls) == 1


def test_adoption_event_http_route_is_collect_scoped_no_store_and_allowlisted(monkeypatch):
    from services.gateway.solution_lifecycle_routes import register_solution_lifecycle_routes

    event_result = {
        "event_id": str(uuid4()), "program_id": CREATED["program_id"],
        "event_type": "aware", "observed_at": "2026-10-20T12:00:00+00:00",
        "replayed": False,
    }
    calls = []
    monkeypatch.setattr(
        actions, "record_location_solution_adoption_event",
        lambda *args, **kwargs: calls.append((args, kwargs)) or event_result,
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
        f"/operator/api/solution-lifecycle/{LOCATION_ID}/adoption/programs/"
        f"{CREATED['program_id']}/events"
    )
    body = {
        "request_id": REQUEST_ID,
        "participant_ref": "opaque-participant-reference-that-is-long-enough-123456",
        "event_type": "aware", "fidelity_score": 72.5, "acknowledged": True,
    }
    with TestClient(app) as client:
        response = client.post(path, json=body)
        invalid = client.post(path, json={**body, "recorded_by_party_id": OPERATOR_ID})

    assert response.status_code == 201 and response.json() == event_result
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert calls == [((OPERATOR_ID, LOCATION_ID, CREATED["program_id"], REQUEST_ID,
                       body["participant_ref"], "aware"), {
                           "fidelity_score": 72.5, "acknowledged": True,
                       })]
    assert invalid.status_code == 400 and len(calls) == 1


def test_adoption_program_http_route_fails_closed_without_oidc():
    from services.gateway.solution_lifecycle_routes import register_solution_lifecycle_routes

    app = FastAPI()
    router = APIRouter()

    async def run_in_threadpool(*_args, **_kwargs):
        pytest.fail("OIDC-disabled route must not invoke the action")

    register_solution_lifecycle_routes(
        router, None, run_in_threadpool, SimpleNamespace(Error=Exception)
    )
    app.include_router(router)
    path = f"/operator/api/solution-lifecycle/{LOCATION_ID}/adoption/programs"
    with TestClient(app) as client:
        response = client.post(path, json=BODY)
    assert response.status_code == 404
    assert response.headers["cache-control"] == "no-store"


def test_adoption_program_http_route_maps_tenant_denial_to_forbidden(monkeypatch):
    from services.gateway.solution_lifecycle_routes import register_solution_lifecycle_routes

    monkeypatch.setattr(
        actions, "create_location_solution_adoption_program",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(TenantContextDenied("denied")),
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

    path = f"/operator/api/solution-lifecycle/{LOCATION_ID}/adoption/programs"
    with TestClient(app) as client:
        response = client.post(path, json=BODY)
    assert response.status_code == 403
    assert response.headers["cache-control"] == "no-store"
