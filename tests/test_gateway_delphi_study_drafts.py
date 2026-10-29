"""Focused contracts for location-scoped Delphi study draft creation."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest

from services.common.tenant_context import TenantContextDenied
from services.gateway import delphi_study_drafts as drafts

pytest.importorskip("fastapi")
from fastapi import APIRouter, FastAPI  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

OPERATOR_ID = str(uuid4())
LOCATION_ID = str(uuid4())
STUDY_ID = str(uuid4())
REQUEST_ID = str(uuid4())
CREATED_AT = datetime(2026, 10, 25, 12, 0, tzinfo=timezone.utc)


class _Connection:
    def __init__(self, one=None):
        self.one = one
        self.operations = []
        self.events = []
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

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def execute(self, query, params=None):
        normalized = " ".join(query.split())
        self.connection.operations.append((normalized, params))
        self.connection.events.append(normalized)

    def fetchone(self):
        return self.connection.one


def _set_context(connection, **kwargs):
    connection.events.append("SIGNED_CONTEXT")
    connection.context = kwargs


def _arguments(**overrides):
    result = {
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "request_id": REQUEST_ID,
        "title": "  Drought resilience  ",
        "description": "  Explore water policy  ",
        "variation": "real_time",
        "facilitator_type": "agent",
        "stopping_criteria": None,
    }
    result.update(overrides)
    return result


def test_study_draft_uses_signed_context_then_commits_one_bounded_request():
    connection = _Connection(
        one=(STUDY_ID, "Drought resilience", "draft", CREATED_AT, False)
    )
    with patch.object(drafts, "set_operator_tenant_context", _set_context):
        result = drafts.create_location_delphi_study_draft(
            **_arguments(), connection_factory=lambda: connection
        )

    call_index = next(
        index for index, event in enumerate(connection.events)
        if "create_location_delphi_study_draft" in event
    )
    assert connection.events.index("SIGNED_CONTEXT") < call_index
    assert connection.context == {
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "delphi",
        "action": "draft",
    }
    query, params = connection.operations[-1]
    assert "create_location_delphi_study_draft" in query
    assert params[0:5] == (
        LOCATION_ID,
        "Drought resilience",
        "Explore water policy",
        "real_time",
        "agent",
    )
    assert '"min_participants": 3' in params[5]
    assert params[6] == REQUEST_ID
    assert result == {
        "study_id": STUDY_ID,
        "location_id": LOCATION_ID,
        "title": "Drought resilience",
        "status": "draft",
        "created_at": CREATED_AT,
        "replayed": False,
    }
    assert connection.committed and connection.rolled_back and connection.closed


def test_study_draft_replay_is_reported_without_changing_request_identity():
    connection = _Connection(
        one=(STUDY_ID, "Drought resilience", "draft", CREATED_AT, True)
    )
    with patch.object(drafts, "set_operator_tenant_context", _set_context):
        result = drafts.create_location_delphi_study_draft(
            **_arguments(), connection_factory=lambda: connection
        )
    assert result["replayed"] is True
    assert result["study_id"] == STUDY_ID
    assert connection.committed and connection.closed


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("operator_id", "bad"),
        ("location_id", "bad"),
        ("request_id", "bad"),
        ("title", "  "),
        ("title", "x" * 256),
        ("description", "x" * 4001),
        ("variation", "unsupported"),
        ("facilitator_type", "unsupported"),
        ("stopping_criteria", {"unreviewed": 1}),
        ("stopping_criteria", {"min_participants": True}),
        ("stopping_criteria", {"max_duration_hours": 0}),
        ("stopping_criteria", {"min_participants": 2}),
        ("stopping_criteria", {"iqr_threshold": 3}),
    ],
)
def test_invalid_study_draft_fails_before_database(field, value):
    with pytest.raises(drafts.DelphiStudyDraftInvalid):
        drafts.create_location_delphi_study_draft(
            **_arguments(**{field: value}),
            connection_factory=lambda: pytest.fail("invalid draft opened a connection"),
        )


def test_database_failure_rolls_back_and_closes_study_draft_connection():
    class _FailingCursor(_Cursor):
        def execute(self, query, params=None):
            if "create_location_delphi_study_draft" in query:
                raise RuntimeError("synthetic database failure")
            super().execute(query, params)

    class _FailingConnection(_Connection):
        def cursor(self):
            return _FailingCursor(self)

    connection = _FailingConnection()
    with patch.object(drafts, "set_operator_tenant_context", _set_context):
        with pytest.raises(RuntimeError, match="synthetic database failure"):
            drafts.create_location_delphi_study_draft(
                **_arguments(), connection_factory=lambda: connection
            )
    assert not connection.committed
    assert connection.rolled_back and connection.closed


def _make_app(provider, run_in_threadpool, psycopg2_errors=None):
    from services.gateway.delphi_study_draft_routes import (
        register_delphi_study_draft_routes,
    )

    app = FastAPI()
    router = APIRouter()

    @app.middleware("http")
    async def bind_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    register_delphi_study_draft_routes(
        router,
        provider,
        run_in_threadpool,
        psycopg2_errors or __import__("psycopg2"),
    )
    app.include_router(router)
    return app


def test_study_draft_route_uses_session_identity_and_private_no_store_response(monkeypatch):
    calls = []
    expected = {
        "study_id": STUDY_ID,
        "location_id": LOCATION_ID,
        "title": "Drought",
        "status": "draft",
        "created_at": CREATED_AT.isoformat().replace("+00:00", "Z"),
        "replayed": False,
    }
    service_result = {**expected, "created_at": CREATED_AT}

    async def run_in_threadpool(func, *args, **kwargs):
        calls.append((func, args, kwargs))
        return service_result

    client = TestClient(_make_app(object(), run_in_threadpool))
    response = client.post(
        f"/operator/api/delphi/{LOCATION_ID}/studies",
        json={"request_id": REQUEST_ID, "title": "Drought"},
    )
    assert response.status_code == 201 and response.json() == expected
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert calls[0][1] == (OPERATOR_ID, LOCATION_ID)
    assert calls[0][2] == {
        "request_id": REQUEST_ID,
        "title": "Drought",
        "description": None,
        "variation": "real_time",
        "facilitator_type": "agent",
        "stopping_criteria": None,
    }


def test_study_draft_route_reports_exact_retry_as_replay():
    async def run_in_threadpool(*_args, **_kwargs):
        return {
            "study_id": STUDY_ID,
            "location_id": LOCATION_ID,
            "title": "Drought",
            "status": "draft",
            "created_at": CREATED_AT,
            "replayed": True,
        }

    response = TestClient(_make_app(object(), run_in_threadpool)).post(
        f"/operator/api/delphi/{LOCATION_ID}/studies",
        json={"request_id": REQUEST_ID, "title": "Drought"},
    )
    assert response.status_code == 200
    assert response.json() == {
        "study_id": STUDY_ID,
        "location_id": LOCATION_ID,
        "title": "Drought",
        "status": "draft",
        "created_at": CREATED_AT.isoformat().replace("+00:00", "Z"),
        "replayed": True,
    }


@pytest.mark.parametrize(
    "service_result",
    [
        {"study_id": STUDY_ID, "location_id": LOCATION_ID, "title": "Drought"},
        {
            "study_id": STUDY_ID,
            "location_id": LOCATION_ID,
            "title": "Drought",
            "status": "open",
            "created_at": CREATED_AT,
            "replayed": False,
        },
        {
            "study_id": STUDY_ID,
            "location_id": str(uuid4()),
            "title": "Drought",
            "status": "draft",
            "created_at": CREATED_AT,
            "replayed": False,
        },
        {
            "study_id": STUDY_ID,
            "location_id": LOCATION_ID,
            "title": "Drought",
            "status": "draft",
            "created_at": CREATED_AT,
            "replayed": False,
            "private_internal": "must not leak",
        },
    ],
)
def test_study_draft_route_rejects_malformed_service_response(service_result):
    async def run_in_threadpool(*_args, **_kwargs):
        return service_result

    response = TestClient(_make_app(object(), run_in_threadpool)).post(
        f"/operator/api/delphi/{LOCATION_ID}/studies",
        json={"request_id": REQUEST_ID, "title": "Drought"},
    )

    assert response.status_code == 500
    assert response.json() == {"error": "Delphi study draft unavailable"}
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert "private_internal" not in response.text


def test_study_draft_route_openapi_declares_create_and_replay_contracts():
    async def run_in_threadpool(*_args, **_kwargs):
        pytest.fail("OpenAPI inspection must not call the service")

    operation = _make_app(object(), run_in_threadpool).openapi()["paths"][
        "/operator/api/delphi/{location_id}/studies"
    ]["post"]
    response_schema = operation["responses"]["201"]["content"]["application/json"]["schema"]
    replay_schema = operation["responses"]["200"]["content"]["application/json"]["schema"]
    assert response_schema == replay_schema
    schema = _make_app(object(), run_in_threadpool).openapi()["components"]["schemas"][
        response_schema["$ref"].rsplit("/", 1)[1]
    ]
    assert set(schema["properties"]) == {
        "study_id", "location_id", "title", "status", "created_at", "replayed"
    }
    assert schema["additionalProperties"] is False


@pytest.mark.parametrize(
    "payload",
    [
        {"request_id": REQUEST_ID},
        {"title": "Drought"},
        {"request_id": REQUEST_ID, "title": "Drought", "status": "open"},
    ],
)
def test_study_draft_route_rejects_missing_or_extra_fields_before_service(payload):
    async def run_in_threadpool(*_args, **_kwargs):
        pytest.fail("invalid payload must not invoke the service")

    response = TestClient(_make_app(object(), run_in_threadpool)).post(
        f"/operator/api/delphi/{LOCATION_ID}/studies", json=payload
    )
    assert response.status_code == 400
    assert response.headers["cache-control"] == "no-store"


def test_study_draft_route_fails_closed_when_oidc_is_disabled():
    async def run_in_threadpool(*_args, **_kwargs):
        pytest.fail("OIDC-disabled request must not reach service")

    response = TestClient(_make_app(None, run_in_threadpool)).post(
        f"/operator/api/delphi/{LOCATION_ID}/studies",
        json={"request_id": REQUEST_ID, "title": "Drought"},
    )
    assert response.status_code == 404
    assert response.headers["cache-control"] == "no-store"


def test_study_draft_route_maps_scope_denial_to_private_forbidden():
    async def run_in_threadpool(*_args, **_kwargs):
        raise TenantContextDenied("private tenant details")

    response = TestClient(_make_app(object(), run_in_threadpool)).post(
        f"/operator/api/delphi/{LOCATION_ID}/studies",
        json={"request_id": REQUEST_ID, "title": "Drought"},
    )
    assert response.status_code == 403
    assert "private tenant details" not in response.text


@pytest.mark.parametrize(("pgcode", "status"), [("42501", 403), ("22023", 409)])
def test_study_draft_route_maps_database_errors_without_details(pgcode, status):
    class _DatabaseError(Exception):
        pass

    async def run_in_threadpool(*_args, **_kwargs):
        error = _DatabaseError("private database text")
        error.pgcode = pgcode
        raise error

    response = TestClient(
        _make_app(object(), run_in_threadpool, SimpleNamespace(Error=_DatabaseError))
    ).post(
        f"/operator/api/delphi/{LOCATION_ID}/studies",
        json={"request_id": REQUEST_ID, "title": "Drought"},
    )
    assert response.status_code == status
    assert "private database text" not in response.text
    assert response.headers["cache-control"] == "no-store"
