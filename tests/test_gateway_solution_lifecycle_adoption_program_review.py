"""Exact-location adoption-program submission and independent-review contracts."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest

from services.common.tenant_context import TenantContextDenied
from services.gateway import solution_lifecycle_actions as actions
from services.gateway.operator_auth import auth_route_policy

pytest.importorskip("fastapi")
from fastapi import APIRouter, FastAPI  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

OPERATOR_ID = str(uuid4())
LOCATION_ID = str(uuid4())
PROGRAM_ID = str(uuid4())
REQUEST_ID = str(uuid4())
SUBMITTED = {
    "program_id": PROGRAM_ID,
    "solution_id": str(uuid4()),
    "program_status": "community_review",
    "submitted_at": "2026-10-20T12:00:00+00:00",
    "replayed": False,
}
REVIEWED = {
    "program_id": PROGRAM_ID,
    "solution_id": SUBMITTED["solution_id"],
    "program_status": "enablement_ready",
    "decision": "enablement_ready",
    "reviewed_at": "2026-10-20T12:00:00+00:00",
    "replayed": False,
}


class _Column(tuple):
    @property
    def name(self):
        return self[0]


class _Connection:
    def __init__(self, *, fail_query=False, rows=None):
        self.fail_query = fail_query
        self.rows = rows or []
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
        self.result = SUBMITTED
        self.description = tuple(_Column((name,)) for name in self.result)

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def execute(self, query, params=None):
        self.connection.operations.append((" ".join(query.split()), params))
        if "review_location_solution_adoption_program" in query:
            self.result = REVIEWED
            self.description = tuple(_Column((name,)) for name in self.result)
        if self.connection.fail_query and "solution_adoption_program" in query:
            raise RuntimeError("database adoption-program action failed")

    def fetchone(self):
        return tuple(self.result.values())

    def fetchall(self):
        return self.connection.rows


def test_program_submission_sets_submit_context_and_commits_receipt():
    connection = _Connection()
    contexts = []

    def set_context(conn, **kwargs):
        assert conn is connection
        contexts.append(kwargs)

    with patch.object(actions, "set_operator_tenant_context", set_context):
        result = actions.submit_location_solution_adoption_program(
            OPERATOR_ID, LOCATION_ID, PROGRAM_ID, REQUEST_ID,
            acknowledged=True, connection_factory=lambda: connection,
        )

    assert contexts == [{
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "solution_lifecycle",
        "action": "submit",
    }]
    assert "submit_location_solution_adoption_program" in connection.operations[-1][0]
    assert connection.operations[-1][1] == (LOCATION_ID, PROGRAM_ID, REQUEST_ID, True)
    assert result == SUBMITTED
    assert connection.committed and connection.closed and not connection.rolled_back


def test_program_submission_requires_acknowledgement_before_database_access():
    with pytest.raises(actions.SolutionLifecycleActionInvalid, match="acknowledgement"):
        actions.submit_location_solution_adoption_program(
            OPERATOR_ID, LOCATION_ID, PROGRAM_ID, REQUEST_ID,
            acknowledged=False,
            connection_factory=lambda: pytest.fail("invalid submission must fail before DB access"),
        )


def test_program_submission_rolls_back_and_closes_on_database_failure():
    connection = _Connection(fail_query=True)
    with patch.object(actions, "set_operator_tenant_context", lambda *_a, **_k: None):
        with pytest.raises(RuntimeError, match="database adoption-program action failed"):
            actions.submit_location_solution_adoption_program(
                OPERATOR_ID, LOCATION_ID, PROGRAM_ID, REQUEST_ID,
                acknowledged=True, connection_factory=lambda: connection,
            )
    assert connection.rolled_back and connection.closed and not connection.committed


@pytest.mark.parametrize("getter,action,key", [
    (actions.get_location_solution_adoption_program_drafts, "submit", "drafts"),
    (actions.get_location_solution_adoption_program_review_queue, "review", "programs"),
])
def test_program_pages_use_exact_context_and_bounded_lookahead(getter, action, key):
    connection = _Connection(rows=[("row-1",), ("row-2",)])
    contexts = []
    with patch.object(actions, "set_operator_tenant_context", lambda conn, **kwargs: contexts.append(kwargs)):
        result = getter(
            OPERATOR_ID, LOCATION_ID, limit=1, offset=25,
            connection_factory=lambda: connection,
        )
    assert contexts[0]["action"] == action
    assert contexts[0]["location_id"] == LOCATION_ID
    assert connection.operations[-1][1] == (LOCATION_ID, 2, 25)
    assert result[key] == [{"program_id": "row-1"}]
    assert result["has_more"] is True and result["next_offset"] == 26
    assert connection.committed and connection.closed


@pytest.mark.parametrize("changes", [
    {"decision": "launch"},
    {"review_note": " "},
    {"review_note": "x" * 2001},
    {"acknowledged": False},
])
def test_program_review_invalid_input_fails_before_database_access(changes):
    payload = {"decision": "enablement_ready", "review_note": "Independent assessment", "acknowledged": True}
    payload.update(changes)
    with pytest.raises(actions.SolutionLifecycleActionInvalid):
        actions.review_location_solution_adoption_program(
            OPERATOR_ID, LOCATION_ID, PROGRAM_ID, REQUEST_ID,
            payload["decision"], payload["review_note"],
            acknowledged=payload["acknowledged"],
            connection_factory=lambda: pytest.fail("invalid review must fail before DB access"),
        )


def test_program_review_uses_exact_review_context_and_commits():
    connection = _Connection()
    contexts = []
    with patch.object(actions, "set_operator_tenant_context", lambda conn, **kwargs: contexts.append(kwargs)):
        result = actions.review_location_solution_adoption_program(
            OPERATOR_ID, LOCATION_ID, PROGRAM_ID, REQUEST_ID,
            "enablement_ready", "Pathway preserves the agreed safeguards.",
            acknowledged=True, connection_factory=lambda: connection,
        )
    assert contexts[0]["action"] == "review"
    assert contexts[0]["location_id"] == LOCATION_ID
    assert connection.operations[-1][1] == (
        LOCATION_ID, PROGRAM_ID, REQUEST_ID, "enablement_ready",
        "Pathway preserves the agreed safeguards.", True,
    )
    assert result == REVIEWED
    assert connection.committed and connection.closed


def test_adoption_program_review_routes_require_exact_grants():
    expected = {
        ("GET", f"/operator/api/solution-lifecycle/{LOCATION_ID}/adoption/programs/drafts"): "submit",
        ("POST", f"/operator/api/solution-lifecycle/{LOCATION_ID}/adoption/programs/{PROGRAM_ID}/submit"): "submit",
        ("GET", f"/operator/api/solution-lifecycle/{LOCATION_ID}/adoption/programs/review-queue"): "review",
        ("POST", f"/operator/api/solution-lifecycle/{LOCATION_ID}/adoption/programs/{PROGRAM_ID}/review"): "review",
    }
    for (method, path), action in expected.items():
        assert auth_route_policy(method, path, enabled=True) == {
            "resource": "solution_lifecycle", "action": action, "public": False,
            "location_id": LOCATION_ID, "scope_required": True, "operator_auth": True,
        }
    assert auth_route_policy("GET", f"/operator/api/solution-lifecycle/{LOCATION_ID}/adoption/programs/unmatched", enabled=True) is None


def test_adoption_program_review_http_routes_reject_extra_fields_and_disable_without_oidc(monkeypatch):
    from services.gateway.solution_lifecycle_routes import register_solution_lifecycle_routes

    calls = []
    monkeypatch.setattr(
        actions, "submit_location_solution_adoption_program",
        lambda *args, **kwargs: calls.append((args, kwargs)) or SUBMITTED,
    )
    app = FastAPI()
    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_solution_lifecycle_routes(router, object(), run_in_threadpool, SimpleNamespace(Error=Exception))
    app.include_router(router)

    @app.middleware("http")
    async def add_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    path = f"/operator/api/solution-lifecycle/{LOCATION_ID}/adoption/programs/{PROGRAM_ID}/submit"
    with TestClient(app) as client:
        response = client.post(path, json={"request_id": REQUEST_ID, "acknowledged": True})
        invalid = client.post(path, json={"request_id": REQUEST_ID, "acknowledged": True, "program_status": "launch"})
    assert response.status_code == 201 and response.headers["cache-control"] == "no-store"
    assert response.json() == SUBMITTED
    assert invalid.status_code == 400 and len(calls) == 1

    disabled_app = FastAPI()
    disabled_router = APIRouter()
    register_solution_lifecycle_routes(
        disabled_router, None,
        lambda *_a, **_k: pytest.fail("OIDC-disabled route must not call the action"),
        SimpleNamespace(Error=Exception),
    )
    disabled_app.include_router(disabled_router)
    with TestClient(disabled_app) as client:
        disabled = client.post(path, json={"request_id": REQUEST_ID, "acknowledged": True})
    assert disabled.status_code == 404 and disabled.headers["cache-control"] == "no-store"


def test_program_review_http_maps_tenant_denial_to_forbidden(monkeypatch):
    from services.gateway.solution_lifecycle_routes import register_solution_lifecycle_routes

    monkeypatch.setattr(
        actions, "review_location_solution_adoption_program",
        lambda *_a, **_k: (_ for _ in ()).throw(TenantContextDenied("denied")),
    )
    app = FastAPI()
    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_solution_lifecycle_routes(router, object(), run_in_threadpool, SimpleNamespace(Error=Exception))
    app.include_router(router)

    @app.middleware("http")
    async def add_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    path = f"/operator/api/solution-lifecycle/{LOCATION_ID}/adoption/programs/{PROGRAM_ID}/review"
    with TestClient(app) as client:
        response = client.post(path, json={
            "request_id": REQUEST_ID, "decision": "redesign",
            "review_note": "Add a maintenance path.", "acknowledged": True,
        })
    assert response.status_code == 403
    assert response.headers["cache-control"] == "no-store"


def _adoption_review_item(program_id=None):
    return {
        "program_id": str(program_id or uuid4()),
        "solution_id": str(uuid4()),
        "solution_name": "Community seed library",
        "program_status": "community_review",
        "adoption_pathway": "Facilitated seed exchange with seasonal follow-up.",
        "local_adaptation_policy": None,
        "submitted_at": datetime(2026, 10, 20, 12, 0, tzinfo=timezone.utc),
        "consent_data_category": "solution_adoption_participation",
        "consent_purpose": "Assess adoption readiness with the participant's consent",
        "consent_version": "v1.0",
    }


def _adoption_review_queue_app(monkeypatch, result):
    from services.gateway.solution_lifecycle_routes import register_solution_lifecycle_routes

    monkeypatch.setattr(
        actions,
        "get_location_solution_adoption_program_review_queue",
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


def test_adoption_program_review_queue_openapi_and_request_page_binding(monkeypatch):
    result = {"programs": [_adoption_review_item()], "has_more": False, "next_offset": None}
    app = _adoption_review_queue_app(monkeypatch, result)
    path = f"/operator/api/solution-lifecycle/{LOCATION_ID}/adoption/programs/review-queue"
    operation = app.openapi()["paths"][path.replace(LOCATION_ID, "{location_id}")]["get"]
    schemas = app.openapi()["components"]["schemas"]
    assert operation["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/SolutionAdoptionProgramReviewQueueResponse"
    }
    page_schema = schemas["SolutionAdoptionProgramReviewQueueResponse"]
    item_schema = schemas["SolutionAdoptionProgramReviewQueueItemResponse"]
    assert set(page_schema["properties"]) == {
        "location_id", "limit", "offset", "programs", "has_more", "next_offset",
        "offset_limited",
    }
    assert page_schema["additionalProperties"] is False
    assert set(item_schema["properties"]) == {
        "program_id", "solution_id", "solution_name", "program_status",
        "adoption_pathway", "local_adaptation_policy", "submitted_at",
        "consent_data_category", "consent_purpose", "consent_version",
    }
    assert item_schema["additionalProperties"] is False
    assert item_schema["properties"]["program_status"]["const"] == "community_review"
    assert item_schema["properties"]["consent_data_category"]["anyOf"][0]["const"] == "solution_adoption_participation"
    assert item_schema["properties"]["consent_version"]["anyOf"][0]["pattern"] == r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,29}$"
    with TestClient(app) as client:
        response = client.get(path, params={"limit": 1, "offset": 4})
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    body = response.json()
    assert (body["location_id"], body["limit"], body["offset"]) == (LOCATION_ID, 1, 4)
    assert body["programs"][0]["program_status"] == "community_review"
    assert body["offset_limited"] is False


@pytest.mark.parametrize(
    "mutate",
    [
        lambda result: result.update(private_reviewer_id=OPERATOR_ID),
        lambda result: result["programs"][0].update(program_status="enablement_ready"),
        lambda result: result["programs"][0].update(consent_purpose=None),
        lambda result: result["programs"][0].update(consent_data_category="unbounded_data"),
        lambda result: result["programs"][0].update(consent_version="bad version"),
        lambda result: result["programs"][0].update(submitted_at=datetime(2026, 10, 20)),
        lambda result: result.update(next_offset=7),
        lambda result: result["programs"].append(dict(result["programs"][0])),
    ],
)
def test_adoption_program_review_queue_rejects_malformed_service_output_no_store(
    monkeypatch, mutate
):
    item = _adoption_review_item()
    result = {"programs": [item], "has_more": False, "next_offset": None}
    mutate(result)
    app = _adoption_review_queue_app(monkeypatch, result)
    path = f"/operator/api/solution-lifecycle/{LOCATION_ID}/adoption/programs/review-queue"
    with TestClient(app) as client:
        response = client.get(path, params={"limit": 1, "offset": 0})
    assert response.status_code == 500
    assert response.json() == {"error": "Solution adoption program review queue unavailable"}
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert "Community seed library" not in response.text
    assert "consent_purpose" not in response.text


def test_adoption_program_review_queue_caps_unrequestable_continuation(monkeypatch):
    programs = [_adoption_review_item() for _ in range(10)]
    programs.sort(key=lambda item: (item["submitted_at"], item["program_id"]))
    result = {
        "programs": programs,
        "has_more": True,
        "next_offset": 10005,
    }
    app = _adoption_review_queue_app(monkeypatch, result)
    path = f"/operator/api/solution-lifecycle/{LOCATION_ID}/adoption/programs/review-queue"
    with TestClient(app) as client:
        response = client.get(path, params={"limit": 10, "offset": 9995})
    assert response.status_code == 200
    body = response.json()
    assert body["programs"]
    assert body["has_more"] is False
    assert body["next_offset"] is None
    assert body["offset_limited"] is True


def _adoption_program_draft_item(program_id=None, *, created_at=None, consent=True):
    item = {
        "program_id": str(program_id or uuid4()),
        "solution_id": str(uuid4()),
        "solution_name": "Community seed library",
        "program_status": "draft",
        "adoption_pathway": "Facilitated seed exchange with seasonal follow-up.",
        "local_adaptation_policy": None,
        "created_at": created_at or datetime(2026, 10, 20, 12, 0, tzinfo=timezone.utc),
        "consent_data_category": "solution_adoption_participation" if consent else None,
        "consent_purpose": "Assess adoption readiness with the participant's consent" if consent else None,
        "consent_version": "v1.0" if consent else None,
    }
    return item


def _adoption_program_drafts_app(monkeypatch, result, calls=None):
    from services.gateway.solution_lifecycle_routes import register_solution_lifecycle_routes

    def get_drafts(*args, **kwargs):
        if calls is not None:
            calls.append((args, kwargs))
        return result

    monkeypatch.setattr(actions, "get_location_solution_adoption_program_drafts", get_drafts)
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


def test_adoption_program_drafts_openapi_and_request_page_binding(monkeypatch):
    first = _adoption_program_draft_item(
        uuid4(), created_at=datetime(2026, 10, 21, 12, 0, tzinfo=timezone.utc)
    )
    second = _adoption_program_draft_item(
        uuid4(), created_at=datetime(2026, 10, 20, 12, 0, tzinfo=timezone.utc), consent=False
    )
    result = {"drafts": [first, second], "has_more": False, "next_offset": None}
    calls = []
    app = _adoption_program_drafts_app(monkeypatch, result, calls)
    path = f"/operator/api/solution-lifecycle/{LOCATION_ID}/adoption/programs/drafts"
    schema_path = "/operator/api/solution-lifecycle/{location_id}/adoption/programs/drafts"
    schemas = app.openapi()["components"]["schemas"]
    operation = app.openapi()["paths"][schema_path]["get"]
    assert operation["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/SolutionAdoptionProgramDraftPageResponse"
    }
    page_schema = schemas["SolutionAdoptionProgramDraftPageResponse"]
    item_schema = schemas["SolutionAdoptionProgramDraftItemResponse"]
    item_fields = {
        "program_id", "solution_id", "solution_name", "program_status",
        "adoption_pathway", "local_adaptation_policy", "created_at",
        "consent_data_category", "consent_purpose", "consent_version",
    }
    assert set(item_schema["properties"]) == item_fields
    assert set(item_schema["required"]) == item_fields
    assert item_schema["additionalProperties"] is False
    assert item_schema["properties"]["program_status"]["const"] == "draft"
    assert item_schema["properties"]["consent_data_category"]["anyOf"][0]["const"] == "solution_adoption_participation"
    assert {"type": "null"} in item_schema["properties"]["consent_data_category"]["anyOf"]
    assert {"type": "null"} in item_schema["properties"]["consent_purpose"]["anyOf"]
    assert {"type": "null"} in item_schema["properties"]["consent_version"]["anyOf"]
    assert item_schema["properties"]["consent_version"]["anyOf"][0]["pattern"] == r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,29}$"
    assert set(page_schema["properties"]) == {
        "location_id", "limit", "offset", "drafts", "has_more", "next_offset",
        "offset_limited",
    }
    assert set(page_schema["required"]) == set(page_schema["properties"])
    assert page_schema["additionalProperties"] is False

    with TestClient(app) as client:
        response = client.get(path, params={"limit": 2, "offset": 4})
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    body = response.json()
    assert (body["location_id"], body["limit"], body["offset"]) == (LOCATION_ID, 2, 4)
    assert set(body["drafts"][0]) == item_fields
    assert body["drafts"][0]["program_status"] == "draft"
    assert body["drafts"][1]["consent_data_category"] is None
    assert body["offset_limited"] is False
    assert calls == [((OPERATOR_ID, LOCATION_ID), {"limit": 2, "offset": 4})]


def test_adoption_program_drafts_follow_migration_created_at_and_id_order(monkeypatch):
    timestamp = datetime(2026, 10, 21, 12, 0, tzinfo=timezone.utc)
    drafts = [
        _adoption_program_draft_item(UUID(int=2), created_at=timestamp),
        _adoption_program_draft_item(UUID(int=3), created_at=timestamp),
        _adoption_program_draft_item(
            UUID(int=4), created_at=timestamp - timedelta(seconds=1)
        ),
    ]
    app = _adoption_program_drafts_app(
        monkeypatch, {"drafts": drafts, "has_more": False, "next_offset": None}
    )
    path = f"/operator/api/solution-lifecycle/{LOCATION_ID}/adoption/programs/drafts"
    with TestClient(app) as client:
        response = client.get(path, params={"limit": 3, "offset": 0})
    assert response.status_code == 200
    assert [item["program_id"] for item in response.json()["drafts"]] == [
        str(UUID(int=2)), str(UUID(int=3)), str(UUID(int=4)),
    ]


@pytest.mark.parametrize(
    "mutate",
    [
        lambda result: result.update(private_creator_id=OPERATOR_ID),
        lambda result: result["drafts"][0].update(program_status="submitted"),
        lambda result: result["drafts"][0].update(consent_purpose=None),
        lambda result: result["drafts"][0].update(consent_data_category="unbounded_data"),
        lambda result: result["drafts"][0].update(consent_version="bad version"),
        lambda result: result["drafts"][0].update(created_at=datetime(2026, 10, 20)),
        lambda result: result.update(next_offset=7),
        lambda result: result["drafts"].append(dict(result["drafts"][0])),
        lambda result: result["drafts"].reverse(),
    ],
)
def test_adoption_program_drafts_reject_malformed_service_output_no_store(monkeypatch, mutate):
    result = {
        "drafts": [
            _adoption_program_draft_item(
                UUID("00000000-0000-0000-0000-000000000001"),
                created_at=datetime(2026, 10, 21, 12, 0, tzinfo=timezone.utc),
            ),
            _adoption_program_draft_item(
                UUID("00000000-0000-0000-0000-000000000002"),
                created_at=datetime(2026, 10, 20, 12, 0, tzinfo=timezone.utc),
            ),
        ],
        "has_more": False,
        "next_offset": None,
    }
    mutate(result)
    app = _adoption_program_drafts_app(monkeypatch, result)
    path = f"/operator/api/solution-lifecycle/{LOCATION_ID}/adoption/programs/drafts"
    with TestClient(app) as client:
        response = client.get(path, params={"limit": 2, "offset": 0})
    assert response.status_code == 500
    assert response.json() == {"error": "Solution adoption program drafts unavailable"}
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert "Community seed library" not in response.text
    assert "consent_purpose" not in response.text


def test_adoption_program_drafts_caps_unrequestable_continuation(monkeypatch):
    drafts = [
        _adoption_program_draft_item(
            UUID(int=index),
            created_at=datetime(2026, 10, 21, 12, 0, tzinfo=timezone.utc)
            - timedelta(minutes=index),
        )
        for index in range(1, 11)
    ]
    result = {"drafts": drafts, "has_more": True, "next_offset": 10005}
    calls = []
    app = _adoption_program_drafts_app(monkeypatch, result, calls)
    path = f"/operator/api/solution-lifecycle/{LOCATION_ID}/adoption/programs/drafts"
    with TestClient(app) as client:
        response = client.get(path, params={"limit": 10, "offset": 9995})
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    body = response.json()
    assert (body["location_id"], body["limit"], body["offset"]) == (LOCATION_ID, 10, 9995)
    assert len(body["drafts"]) == 10
    assert body["has_more"] is False
    assert body["next_offset"] is None
    assert body["offset_limited"] is True
    assert calls == [((OPERATOR_ID, LOCATION_ID), {"limit": 10, "offset": 9995})]


def test_adoption_program_drafts_reject_offset_above_cap_before_service_call(monkeypatch):
    calls = []
    app = _adoption_program_drafts_app(
        monkeypatch,
        {"drafts": [], "has_more": False, "next_offset": None},
        calls,
    )
    path = f"/operator/api/solution-lifecycle/{LOCATION_ID}/adoption/programs/drafts"
    with TestClient(app) as client:
        response = client.get(path, params={"offset": 10001})
    assert response.status_code == 422
    assert "less than or equal to 10000" in response.text.lower()
    assert calls == []
