"""Contract checks for versioned business canvas metadata editing."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi import APIRouter, FastAPI
from starlette.testclient import TestClient

from services.common.tenant_context import TenantContextDenied
from services.gateway import business_planning_metadata as metadata
from services.gateway.operator_auth import auth_route_policy

OPERATOR_ID = str(uuid4())
LOCATION_ID = str(uuid4())
CANVAS_ID = str(uuid4())
REQUEST_ID = str(uuid4())
UPDATED_AT = "2026-10-19T12:00:00+00:00"


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
        return self.connection.row


class _Connection:
    def __init__(self, row):
        self.row = row
        self.operations = []
        self.commits = 0
        self.rollbacks = 0
        self.closed = False

    def cursor(self):
        return _Cursor(self)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed = True


def _payload(**overrides):
    result = {
        "request_id": REQUEST_ID,
        "expected_version": 2,
        "expected_updated_at": UPDATED_AT,
        "change_reason": "Align canvas title and reporting year",
        "canvas_name": "  Terra Viva plan  ",
        "description": None,
        "fiscal_year": 2027,
        "tags": [" planning ", "Farm Design"],
    }
    result.update(overrides)
    return result


def test_metadata_edit_sets_signed_update_context_and_calls_bounded_function():
    updated_at = datetime(2026, 10, 19, 12, 5, tzinfo=timezone.utc)
    connection = _Connection((CANVAS_ID, "draft", 3, updated_at, False))
    context_calls = []

    def set_context(conn, **kwargs):
        assert conn is connection
        context_calls.append(kwargs)
        connection.operations.append(("tenant_context", kwargs))

    with patch.object(metadata, "set_operator_tenant_context", set_context):
        result = metadata.update_location_business_model_canvas_metadata(
            OPERATOR_ID,
            LOCATION_ID,
            CANVAS_ID,
            _payload(),
            connection_factory=lambda: connection,
        )

    assert result == {
        "location_id": LOCATION_ID,
        "canvas_id": CANVAS_ID,
        "status": "draft",
        "version": 3,
        "updated_at": updated_at,
        "replayed": False,
        "changed_fields": ["canvas_name", "description", "fiscal_year", "tags"],
    }
    assert context_calls == [
        {
            "operator_id": OPERATOR_ID,
            "location_id": LOCATION_ID,
            "resource": "business_planning",
            "action": "update",
        }
    ]
    assert connection.operations[2][0] == "tenant_context"
    query, params = connection.operations[3]
    assert "update_location_business_model_canvas_metadata" in query
    assert params == (
        LOCATION_ID,
        CANVAS_ID,
        REQUEST_ID,
        2,
        datetime(2026, 10, 19, 12, 0, tzinfo=timezone.utc),
        '{"canvas_name":"Terra Viva plan","description":null,"fiscal_year":2027,"tags":["planning","Farm Design"]}',
        "Align canvas title and reporting year",
    )
    assert connection.commits == 1
    assert connection.closed


@pytest.mark.parametrize(
    "changes",
    [
        {"canvas_name": "  "},
        {"canvas_name": 42},
        {"canvas_name": "x" * 256},
        {"description": 4},
        {"description": "x" * 4001},
        {"fiscal_year": True},
        {"fiscal_year": 1899},
        {"fiscal_year": 2201},
        {"tags": "planning"},
        {"tags": ["same", " SAME "]},
        {"tags": [""]},
        {"unreviewed": "value"},
    ],
)
def test_invalid_metadata_fails_before_opening_connection(changes):
    with pytest.raises(metadata.BusinessPlanningWriteInvalid):
        metadata.update_location_business_model_canvas_metadata(
            OPERATOR_ID,
            LOCATION_ID,
            CANVAS_ID,
            _payload(**changes),
            connection_factory=lambda: pytest.fail("invalid metadata opened a connection"),
        )


def test_metadata_patch_requires_at_least_one_editable_field():
    body = {key: value for key, value in _payload().items() if key in {
        "request_id", "expected_version", "expected_updated_at", "change_reason"
    }}
    with pytest.raises(metadata.BusinessPlanningWriteInvalid):
        metadata._normalize_metadata_payload(body)


def test_context_denial_rolls_back_and_closes_without_writer_call(monkeypatch):
    connection = _Connection(None)

    def deny(*_args, **_kwargs):
        raise TenantContextDenied("denied")

    monkeypatch.setattr(metadata, "set_operator_tenant_context", deny)
    with pytest.raises(TenantContextDenied):
        metadata.update_location_business_model_canvas_metadata(
            OPERATOR_ID,
            LOCATION_ID,
            CANVAS_ID,
            _payload(),
            connection_factory=lambda: connection,
        )

    assert all(
        "update_location_business_model_canvas_metadata" not in query
        for query, _params in connection.operations
        if isinstance(query, str)
    )
    assert connection.commits == 0
    assert connection.rollbacks == 2
    assert connection.closed


def test_metadata_route_has_exact_location_update_policy():
    path = f"/operator/api/business-planning/{LOCATION_ID}/canvases/{CANVAS_ID}/metadata"
    assert auth_route_policy("PATCH", path, enabled=True) == {
        "resource": "business_planning",
        "action": "update",
        "public": False,
        "location_id": LOCATION_ID,
        "scope_required": True,
        "operator_auth": True,
    }
    assert auth_route_policy("GET", path, enabled=True) is None


def _app(monkeypatch, metadata_update, *, provider=object()):
    from services.gateway.business_planning_edit_routes import register_business_planning_edit_routes

    monkeypatch.setattr(
        "services.gateway.business_planning_metadata.update_location_business_model_canvas_metadata",
        metadata_update,
    )
    app = FastAPI()
    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_business_planning_edit_routes(
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


def test_metadata_patch_route_returns_no_store_result(monkeypatch):
    result = {
        "location_id": LOCATION_ID,
        "canvas_id": CANVAS_ID,
        "status": "draft",
        "version": 3,
        "updated_at": UPDATED_AT,
        "replayed": False,
        "changed_fields": ["canvas_name"],
    }
    app = _app(monkeypatch, lambda *_args, **_kwargs: result)
    with TestClient(app) as client:
        response = client.patch(
            f"/operator/api/business-planning/{LOCATION_ID}/canvases/{CANVAS_ID}/metadata",
            json=_payload(canvas_name="Updated name"),
        )
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert response.json()["changed_fields"] == ["canvas_name"]


def test_metadata_route_rejects_non_object_and_oidc_disabled(monkeypatch):
    path = f"/operator/api/business-planning/{LOCATION_ID}/canvases/{CANVAS_ID}/metadata"
    app = _app(monkeypatch, lambda *_args, **_kwargs: pytest.fail("unexpected metadata write"))
    with TestClient(app) as client:
        invalid = client.patch(path, json=[])
    assert invalid.status_code == 400

    disabled = _app(
        monkeypatch,
        lambda *_args, **_kwargs: pytest.fail("unexpected metadata write"),
        provider=None,
    )
    with TestClient(disabled) as client:
        absent = client.patch(path, json=_payload())
    assert absent.status_code == 404
