"""Contract checks for signed, versioned business canvas edits."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi import APIRouter, FastAPI
from starlette.testclient import TestClient

from services.common.tenant_context import TenantContextDenied
from services.gateway import business_planning_edits as edits
from services.gateway import business_planning_reads as reads
from services.gateway.operator_auth import auth_route_policy

OPERATOR_ID = str(uuid4())
LOCATION_ID = str(uuid4())
CANVAS_ID = str(uuid4())
REQUEST_ID = str(uuid4())
EXPECTED_UPDATED_AT = "2026-10-19T12:00:00+00:00"


class _Column:
    def __init__(self, name):
        self.name = name


class _Connection:
    def __init__(self, *, one=None, all_rows=None, description=()):
        self.operations = []
        self.one = one
        self.all_rows = all_rows or []
        self.description = description
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


class _Cursor:
    def __init__(self, connection):
        self.connection = connection
        self.description = tuple(_Column(name) for name in connection.description)

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def execute(self, query, params=None):
        self.connection.operations.append((" ".join(query.split()), params))

    def fetchone(self):
        return self.connection.one

    def fetchall(self):
        return self.connection.all_rows


def _payload(**overrides):
    result = {
        "request_id": REQUEST_ID,
        "expected_version": 1,
        "expected_updated_at": EXPECTED_UPDATED_AT,
        "items": [{"name": "Local growers"}],
        "change_reason": "Reviewed with the farm team",
    }
    result.update(overrides)
    return result


def _version_page(*, location_id=LOCATION_ID, canvas_id=CANVAS_ID, offset=0, versions=None, has_more=False):
    return {
        "location_id": location_id,
        "canvas_id": canvas_id,
        "offset": offset,
        "versions": [] if versions is None else versions,
        "has_more": has_more,
        "next_offset": offset + 5 if has_more else None,
    }


def _version_item():
    return {
        "canvas_id": CANVAS_ID,
        "version": 2,
        "snapshot": {
            "canvas_name": "Primary Canvas",
            "description": "Location operating model",
            "fiscal_year": 2026,
            "tags": ["reviewed"],
            "blocks": {
                "key_partners": [],
                "key_activities": [],
                "key_resources": [],
                "value_propositions": [],
                "customer_relationships": [],
                "channels": [],
                "customer_segments": [],
                "revenue_streams": [],
                "cost_structure": {},
            },
        },
        "change_reason": "Initial review",
        "changed_at": "2026-10-19T12:05:00+00:00",
        "is_current": True,
    }


def test_block_edit_establishes_signed_update_context_and_commits_one_function_call():
    updated_at = datetime(2026, 10, 19, 12, 5, tzinfo=timezone.utc)
    connection = _Connection(
        one=(CANVAS_ID, "draft", 2, updated_at, False),
    )
    context_calls = []

    def set_context(conn, **kwargs):
        assert conn is connection
        context_calls.append(kwargs)
        connection.operations.append(("tenant_context", kwargs))

    with patch.object(edits, "set_operator_tenant_context", set_context):
        result = edits.update_location_business_model_canvas_block(
            OPERATOR_ID,
            LOCATION_ID,
            CANVAS_ID,
            "key_partners",
            _payload(),
            connection_factory=lambda: connection,
        )

    assert result == {
        "location_id": LOCATION_ID,
        "canvas_id": CANVAS_ID,
        "block_name": "key_partners",
        "status": "draft",
        "version": 2,
        "updated_at": updated_at,
        "replayed": False,
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
    assert "update_location_business_model_canvas_block" in query
    assert params == (
        LOCATION_ID,
        CANVAS_ID,
        REQUEST_ID,
        1,
        datetime(2026, 10, 19, 12, 0, tzinfo=timezone.utc),
        "key_partners",
        '[{"name":"Local growers"}]',
        "Reviewed with the farm team",
    )
    assert connection.commits == 1
    assert connection.closed


@pytest.mark.parametrize(
    ("block_name", "payload"),
    [
        ("unknown", _payload()),
        ("key_partners", _payload(extra=True)),
        ("key_partners", _payload(expected_version=True)),
        ("key_partners", _payload(expected_version=0)),
        ("key_partners", _payload(expected_updated_at="2026-10-19T12:00:00")),
        ("key_partners", _payload(items={"name": "not an array"})),
        ("cost_structure", _payload(items=["not an object"])),
        ("key_partners", _payload(items=["bad\x00value"])),
        ("key_partners", _payload(items=[float("nan")])),
        ("key_partners", _payload(change_reason="  ")),
    ],
)
def test_invalid_edit_payload_fails_before_opening_connection(block_name, payload):
    with pytest.raises(edits.BusinessPlanningWriteInvalid):
        edits.update_location_business_model_canvas_block(
            OPERATOR_ID,
            LOCATION_ID,
            CANVAS_ID,
            block_name,
            payload,
            connection_factory=lambda: pytest.fail("invalid edit opened a connection"),
        )


def test_edit_context_denial_rolls_back_without_calling_writer(monkeypatch):
    connection = _Connection()
    monkeypatch.setattr(edits, "set_operator_tenant_context", lambda *_a, **_k: None)

    def deny(*_args, **_kwargs):
        raise TenantContextDenied("denied")

    monkeypatch.setattr(edits, "set_operator_tenant_context", deny)
    with pytest.raises(TenantContextDenied):
        edits.update_location_business_model_canvas_block(
            OPERATOR_ID,
            LOCATION_ID,
            CANVAS_ID,
            "key_partners",
            _payload(),
            connection_factory=lambda: connection,
        )

    assert all("update_location_business_model_canvas_block" not in query for query, _ in connection.operations)
    assert connection.commits == 0
    assert connection.rollbacks == 2
    assert connection.closed


def test_version_read_sets_read_context_and_bounds_history_page():
    columns = ("canvas_id", "version", "snapshot", "change_reason", "changed_at", "is_current")
    connection = _Connection(
        all_rows=[(CANVAS_ID, 2, {"blocks": {}}, None, "2026-10-19T12:05:00Z", True)],
        description=columns,
    )
    context_calls = []

    def set_context(conn, **kwargs):
        assert conn is connection
        context_calls.append(kwargs)

    with patch.object(reads, "set_operator_tenant_context", set_context):
        result = reads.list_location_business_model_canvas_versions(
            OPERATOR_ID,
            LOCATION_ID,
            CANVAS_ID,
            limit="5",
            offset="0",
            connection_factory=lambda: connection,
        )

    assert result["versions"] == [dict(zip(columns, connection.all_rows[0]))]
    assert result["has_more"] is False
    assert context_calls == [
        {
            "operator_id": OPERATOR_ID,
            "location_id": LOCATION_ID,
            "resource": "business_planning",
            "action": "read",
        }
    ]
    assert connection.operations[3][1] == (LOCATION_ID, CANVAS_ID, 6, 0)
    assert connection.rollbacks == 1
    assert connection.closed


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"location_id": "bad"}, "location"),
        ({"canvas_id": "bad"}, "canvas"),
        ({"limit": "6"}, "Limit"),
        ({"offset": "10001"}, "Offset"),
    ],
)
def test_invalid_version_read_fails_before_connection(kwargs, message):
    args = {"location_id": LOCATION_ID, "canvas_id": CANVAS_ID, **kwargs}
    with pytest.raises(reads.BusinessPlanningReadInvalid, match=message):
        reads.list_location_business_model_canvas_versions(
            OPERATOR_ID,
            **args,
            connection_factory=lambda: pytest.fail("invalid history request opened a connection"),
        )


def test_history_page_size_is_bounded(monkeypatch):
    connection = _Connection(all_rows=[])
    monkeypatch.setattr(reads, "_MAX_VERSION_RESPONSE_BYTES", 1)
    monkeypatch.setattr(reads, "set_operator_tenant_context", lambda *_a, **_k: None)
    with pytest.raises(reads.BusinessPlanningHistoryTooLarge):
        reads.list_location_business_model_canvas_versions(
            OPERATOR_ID,
            LOCATION_ID,
            CANVAS_ID,
            connection_factory=lambda: connection,
        )
    assert connection.closed


def test_new_business_planning_routes_have_exact_read_and_update_policies():
    versions_path = (
        f"/operator/api/business-planning/{LOCATION_ID}/canvases/{CANVAS_ID}/versions"
    )
    block_path = (
        f"/operator/api/business-planning/{LOCATION_ID}/canvases/{CANVAS_ID}/blocks/key_partners"
    )
    assert auth_route_policy("GET", versions_path, enabled=True) == {
        "resource": "business_planning",
        "action": "read",
        "public": False,
        "location_id": LOCATION_ID,
        "scope_required": True,
        "operator_auth": True,
    }
    assert auth_route_policy("PATCH", block_path, enabled=True) == {
        "resource": "business_planning",
        "action": "update",
        "public": False,
        "location_id": LOCATION_ID,
        "scope_required": True,
        "operator_auth": True,
    }
    assert auth_route_policy("PUT", block_path, enabled=True) is None
    assert auth_route_policy("PATCH", block_path.replace("key_partners", "not-valid"), enabled=True) is None


def _app(monkeypatch, *, write=None, history=None, provider=object()):
    from services.gateway.business_planning_edit_routes import register_business_planning_edit_routes

    if write is not None:
        monkeypatch.setattr(
            "services.gateway.business_planning_edits.update_location_business_model_canvas_block",
            write,
        )
    if history is not None:
        monkeypatch.setattr(
            "services.gateway.business_planning_reads.list_location_business_model_canvas_versions",
            history,
        )
    app = FastAPI()
    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_business_planning_edit_routes(router, provider, run_in_threadpool, SimpleNamespace(Error=Exception))
    app.include_router(router)

    @app.middleware("http")
    async def add_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    return app


def test_patch_route_returns_no_store_draft_edit(monkeypatch):
    monkeypatch_payload = {
        "location_id": LOCATION_ID,
        "canvas_id": CANVAS_ID,
        "block_name": "key_partners",
        "status": "draft",
        "version": 2,
        "updated_at": EXPECTED_UPDATED_AT,
        "replayed": False,
    }
    app = _app(monkeypatch, write=lambda *_a, **_k: monkeypatch_payload)
    with TestClient(app) as client:
        response = client.patch(
            f"/operator/api/business-planning/{LOCATION_ID}/canvases/{CANVAS_ID}/blocks/key_partners",
            json=_payload(),
        )
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert response.json()["version"] == 2


def test_patch_route_maps_invalid_body_and_tenant_denial(monkeypatch):
    app = _app(monkeypatch, write=lambda *_a, **_k: (_ for _ in ()).throw(TenantContextDenied("denied")))
    with TestClient(app) as client:
        denied = client.patch(
            f"/operator/api/business-planning/{LOCATION_ID}/canvases/{CANVAS_ID}/blocks/key_partners",
            json=_payload(),
        )
        invalid = client.patch(
            f"/operator/api/business-planning/{LOCATION_ID}/canvases/{CANVAS_ID}/blocks/key_partners",
            json=[],
        )
    assert denied.status_code == 403
    assert denied.headers["cache-control"] == "no-store"
    assert invalid.status_code == 400


def test_versions_route_returns_no_store_and_oidc_disabled_404(monkeypatch):
    app = _app(
        monkeypatch,
        history=lambda *_a, **_k: _version_page(versions=[_version_item()]),
    )
    path = f"/operator/api/business-planning/{LOCATION_ID}/canvases/{CANVAS_ID}/versions"
    with TestClient(app) as client:
        response = client.get(path)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["versions"][0]["version"] == 2
    app_disabled = _app(monkeypatch, provider=None)
    with TestClient(app_disabled) as client:
        disabled = client.get(path)
    assert disabled.status_code == 404
    assert disabled.headers["cache-control"] == "no-store"


@pytest.mark.parametrize(
    "mutate",
    [
        lambda result: result["versions"][0].update(created_by=OPERATOR_ID),
        lambda result: result["versions"][0]["snapshot"].update(private_metadata={"secret": True}),
        lambda result: result.update(canvas_id=str(uuid4())),
        lambda result: result["versions"][0].update(canvas_id=str(uuid4())),
        lambda result: result.update(offset=1),
        lambda result: result.update(has_more=True),
    ],
)
def test_versions_route_rejects_malformed_or_mismatched_projection(monkeypatch, mutate):
    result = _version_page(versions=[_version_item()])
    mutate(result)
    app = _app(monkeypatch, history=lambda *_a, **_k: result)
    path = f"/operator/api/business-planning/{LOCATION_ID}/canvases/{CANVAS_ID}/versions"

    with TestClient(app) as client:
        response = client.get(path)

    assert response.status_code == 500
    assert response.json() == {"error": "Business canvas history unavailable"}
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"


def test_versions_route_publishes_service_bounds_and_rejects_invalid_pages(monkeypatch):
    calls = []
    app = _app(
        monkeypatch,
        history=lambda *args, **kwargs: calls.append((args, kwargs))
        or _version_page(),
    )
    path = f"/operator/api/business-planning/{LOCATION_ID}/canvases/{CANVAS_ID}/versions"
    operation = app.openapi()["paths"][
        "/operator/api/business-planning/{location_id}/canvases/{canvas_id}/versions"
    ]["get"]
    assert operation["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/BusinessCanvasVersionHistoryPage"
    }
    assert app.openapi()["components"]["schemas"][
        "BusinessCanvasVersionHistoryPage"
    ]["additionalProperties"] is False
    parameters = {parameter["name"]: parameter for parameter in operation["parameters"]}

    assert parameters["limit"]["schema"] == {
        "type": "integer",
        "minimum": 1,
        "maximum": 5,
        "default": 5,
        "title": "Limit",
    }
    assert parameters["offset"]["schema"] == {
        "type": "integer",
        "minimum": 0,
        "maximum": 10000,
        "default": 0,
        "title": "Offset",
    }

    with TestClient(app) as client:
        for query in ("limit=0", "limit=6", "offset=-1", "offset=10001"):
            response = client.get(f"{path}?{query}")
            assert response.status_code == 422

    assert calls == []


@pytest.mark.parametrize(
    ("offset", "expected_more"),
    [(9995, True), (9996, False)],
)
def test_version_read_stops_continuation_at_supported_offset_ceiling(
    monkeypatch, offset, expected_more
):
    columns = ("canvas_id", "version", "snapshot", "change_reason", "changed_at", "is_current")
    connection = _Connection(
        all_rows=[
            (CANVAS_ID, version, {"blocks": {}}, None, "2026-10-19T12:05:00Z", version == 6)
            for version in range(6, 0, -1)
        ],
        description=columns,
    )
    monkeypatch.setattr(reads, "set_operator_tenant_context", lambda *_a, **_k: None)

    result = reads.list_location_business_model_canvas_versions(
        OPERATOR_ID,
        LOCATION_ID,
        CANVAS_ID,
        limit=5,
        offset=offset,
        connection_factory=lambda: connection,
    )

    assert len(result["versions"]) == 5
    assert result["has_more"] is expected_more
    assert result["next_offset"] == (offset + 5 if expected_more else None)
