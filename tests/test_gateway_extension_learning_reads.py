"""Extension-learning operator reads stay location-scoped and aggregate-only."""

from types import SimpleNamespace

import pytest

pytest.importorskip("fastapi")
from fastapi import APIRouter, FastAPI  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

from services.common.tenant_context import TenantContextDenied
from services.gateway.extension_learning_reads import (
    get_location_extension_learning_summary,
    list_location_extension_modules,
)
from services.gateway.operator_auth import auth_route_policy

LOCATION_ID = "11111111-1111-4111-8111-111111111111"
OPERATOR_ID = "22222222-2222-4222-8222-222222222222"


class _Cursor:
    def __init__(self, connection):
        self.connection = connection
        self.description = []
        self.rows = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, query, params=None):
        self.connection.queries.append((query, params))
        if "FROM learning_progress" in query:
            columns = ("module_category", "progress_status", "enrollment_count")
            rows = (("soil_health", "completed", 4),)
        elif "FROM content_delivery" in query:
            columns = ("delivery_channel", "delivery_status", "delivery_count")
            rows = (("mobile_app", "delivered", 4),)
        elif "FROM skill_assessment" in query:
            columns = ("assessment_type", "assessment_count", "scored_assessment_count")
            rows = (("post_test", 3, 3),)
        elif "FROM peer_network AS pn" in query:
            columns = ("network_type", "network_status", "network_count", "active_member_count")
            rows = (("learning_group", "active", 1, 4),)
        elif "FROM extension_module" in query:
            columns = (
                "id", "module_name", "category", "difficulty", "content_type",
                "duration_minutes", "language",
            )
            rows = (
                ("33333333-3333-4333-8333-333333333333", "Compost", "soil_health", "beginner", "guide", 20, "en"),
                ("44444444-4444-4444-8444-444444444444", "Water", "water_management", "intermediate", "video", 30, "es"),
            )
        else:
            self.description, self.rows = [], []
            return
        self.description = [(name,) for name in columns]
        self.rows = rows

    def fetchall(self):
        return self.rows


class _Connection:
    def __init__(self):
        self.queries = []
        self.rollback_count = 0
        self.closed = False

    def cursor(self):
        return _Cursor(self)

    def rollback(self):
        self.rollback_count += 1

    def close(self):
        self.closed = True


def test_summary_sets_context_before_location_queries_and_omits_private_fields(monkeypatch):
    connection = _Connection()
    order = []
    original_execute = _Cursor.execute

    def execute(self, query, params=None):
        order.append("query")
        original_execute(self, query, params)

    def set_context(*args, **kwargs):
        order.append("context")
        assert kwargs == {
            "operator_id": OPERATOR_ID,
            "location_id": LOCATION_ID,
            "resource": "extension_learning",
            "action": "read",
        }

    monkeypatch.setattr(_Cursor, "execute", execute)
    monkeypatch.setattr(
        "services.gateway.extension_learning_reads.set_operator_tenant_context",
        set_context,
    )

    result = get_location_extension_learning_summary(
        OPERATOR_ID, LOCATION_ID, connection_factory=lambda: connection
    )

    assert order[:4] == ["query", "query", "query", "context"]
    data_queries = [query for query, _ in connection.queries if "FROM " in query]
    assert len(data_queries) == 4
    assert all(query.count("%s::uuid") >= 1 for query in data_queries)
    assert data_queries[-1].count("%s::uuid") == 2
    assert result["learning_progress"] == [
        {"module_category": "soil_health", "progress_status": "completed", "enrollment_count": 4}
    ]
    assert result["peer_networks"][0]["active_member_count"] == 4
    assert "farmer_name" not in str(result)
    assert "assessor_name" not in str(result)
    assert "notes" not in str(result)
    assert "error_message" not in str(result)
    assert "metadata" not in str(result)
    assert connection.closed
    assert connection.rollback_count == 1


def test_invalid_scope_fails_before_connecting():
    called = False

    def connect():
        nonlocal called
        called = True
        raise AssertionError("database connection must not open")

    with pytest.raises(ValueError, match="Invalid location identifier"):
        get_location_extension_learning_summary(OPERATOR_ID, "bad", connection_factory=connect)
    assert not called


def test_public_active_module_catalog_is_filtered_and_paginated_without_content_payloads(monkeypatch):
    connection = _Connection()
    monkeypatch.setattr(
        "services.gateway.extension_learning_reads.set_operator_tenant_context",
        lambda *_args, **_kwargs: None,
    )

    result = list_location_extension_modules(
        OPERATOR_ID,
        LOCATION_ID,
        category="soil_health",
        difficulty="beginner",
        content_type="guide",
        limit=1,
        offset=2,
        connection_factory=lambda: connection,
    )

    query, params = next((query, params) for query, params in connection.queries if "FROM extension_module" in query)
    assert "is_public IS TRUE" in query
    assert "status = 'active'" in query
    assert "content_url" not in query
    assert "description" not in query
    assert "tags" not in query
    assert "metadata" not in query
    assert params == ("soil_health", "soil_health", "beginner", "beginner", "guide", "guide", 2, 2)
    assert result["has_more"] is True
    assert result["items"] == [
        {
            "id": "33333333-3333-4333-8333-333333333333",
            "module_name": "Compost",
            "category": "soil_health",
            "difficulty": "beginner",
            "content_type": "guide",
            "duration_minutes": 20,
            "language": "en",
        }
    ]
    assert connection.closed


def test_invalid_catalog_filter_fails_before_connecting():
    called = False

    def connect():
        nonlocal called
        called = True
        raise AssertionError("database connection must not open")

    with pytest.raises(ValueError, match="Unsupported module category"):
        list_location_extension_modules(
            OPERATOR_ID, LOCATION_ID, category="arbitrary", connection_factory=connect
        )
    assert not called


def test_exact_extension_learning_route_policy():
    path = f"/operator/api/extension-learning/{LOCATION_ID}/summary"

    assert auth_route_policy("GET", path, enabled=True) == {
        "resource": "extension_learning",
        "action": "read",
        "public": False,
        "location_id": LOCATION_ID,
        "scope_required": True,
        "operator_auth": True,
    }
    assert auth_route_policy("POST", path, enabled=True) is None
    assert auth_route_policy("GET", f"{path}/extra", enabled=True) is None
    assert auth_route_policy(
        "GET", f"/operator/api/extension-learning/{LOCATION_ID}/modules", enabled=True
    ) == auth_route_policy("GET", path, enabled=True)


def _summary_payload(location_id=LOCATION_ID):
    return {
        "location_id": location_id,
        "learning_progress": [{
            "module_category": "soil_health",
            "progress_status": "completed",
            "enrollment_count": 4,
        }],
        "content_delivery": [{
            "delivery_channel": "mobile_app",
            "delivery_status": "delivered",
            "delivery_count": 4,
        }],
        "assessments": [{
            "assessment_type": "post_test",
            "assessment_count": 3,
            "scored_assessment_count": 3,
        }],
        "peer_networks": [{
            "network_type": "learning_group",
            "network_status": "active",
            "network_count": 1,
            "active_member_count": 4,
        }],
    }


def _module_page(location_id=LOCATION_ID):
    return {
        "location_id": location_id,
        "items": [{
            "id": "33333333-3333-4333-8333-333333333333",
            "module_name": "Compost",
            "category": "soil_health",
            "difficulty": "beginner",
            "content_type": "guide",
            "duration_minutes": 20,
            "language": "en",
        }],
        "limit": 25,
        "offset": 0,
        "has_more": False,
    }


def test_http_route_is_no_store_and_uses_operator_identity(monkeypatch):
    from services.gateway.extension_learning_routes import register_extension_learning_routes

    monkeypatch.setattr(
        "services.gateway.extension_learning_reads.get_location_extension_learning_summary",
        lambda _operator_id, location_id: _summary_payload(location_id),
    )
    monkeypatch.setattr(
        "services.gateway.extension_learning_reads.list_location_extension_modules",
        lambda _operator_id, location_id, **_kwargs: _module_page(location_id),
    )
    app = FastAPI()
    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_extension_learning_routes(router, object(), run_in_threadpool, SimpleNamespace(Error=Exception))
    app.include_router(router)

    @app.middleware("http")
    async def add_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    with TestClient(app) as client:
        response = client.get(f"/operator/api/extension-learning/{LOCATION_ID}/summary")
        modules = client.get(
            f"/operator/api/extension-learning/{LOCATION_ID}/modules?category=soil_health"
        )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert response.json() == _summary_payload()
    assert modules.status_code == 200
    assert modules.headers["cache-control"] == "no-store"
    assert modules.json() == _module_page()


def test_extension_learning_success_response_schemas_are_published_and_strict():
    from services.gateway.extension_learning_routes import register_extension_learning_routes

    app = FastAPI()
    router = APIRouter()

    async def run_in_threadpool(*_args, **_kwargs):
        return {}

    register_extension_learning_routes(router, object(), run_in_threadpool, SimpleNamespace(Error=Exception))
    app.include_router(router)
    schemas = app.openapi()["components"]["schemas"]
    paths = app.openapi()["paths"]
    assert paths[
        "/operator/api/extension-learning/{location_id}/modules"
    ]["get"]["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/ExtensionModulePage"
    }
    assert paths[
        "/operator/api/extension-learning/{location_id}/summary"
    ]["get"]["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/ExtensionLearningSummary"
    }
    for name in (
        "ExtensionModulePage", "ExtensionModuleItem", "ExtensionLearningSummary",
        "LearningProgressGroup", "ContentDeliveryGroup", "SkillAssessmentGroup",
        "PeerNetworkGroup",
    ):
        assert schemas[name]["additionalProperties"] is False
    assert schemas["ExtensionLearningSummary"]["properties"]["learning_progress"]["maxItems"] == 55
    assert schemas["ExtensionLearningSummary"]["properties"]["content_delivery"]["maxItems"] == 48
    assert schemas["ExtensionLearningSummary"]["properties"]["peer_networks"]["maxItems"] == 18


@pytest.mark.parametrize(
    ("route", "invalid_field"),
    [
        ("summary", "extra"),
        ("summary", "invalid_status"),
        ("summary", "negative_count"),
        ("summary", "location_mismatch"),
        ("modules", "nested_extra"),
        ("modules", "invalid_category"),
        ("modules", "location_mismatch"),
    ],
)
def test_extension_learning_rejects_invalid_success_projection(
    monkeypatch, route, invalid_field
):
    from services.gateway.extension_learning_routes import register_extension_learning_routes

    payload = _summary_payload() if route == "summary" else _module_page()
    if invalid_field == "extra":
        payload["farmer_names"] = ["private"]
    elif invalid_field == "invalid_status":
        payload["content_delivery"][0]["delivery_status"] = "unknown"
    elif invalid_field == "negative_count":
        payload["learning_progress"][0]["enrollment_count"] = -1
    elif invalid_field == "nested_extra":
        payload["items"][0]["content_url"] = "https://private.example/"
    elif invalid_field == "invalid_category":
        payload["items"][0]["category"] = "unknown"
    else:
        payload["location_id"] = "44444444-4444-4444-8444-444444444444"

    service_name = (
        "get_location_extension_learning_summary"
        if route == "summary"
        else "list_location_extension_modules"
    )
    monkeypatch.setattr(
        f"services.gateway.extension_learning_reads.{service_name}",
        lambda *_args, **_kwargs: payload,
    )
    app = FastAPI()
    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_extension_learning_routes(router, object(), run_in_threadpool, SimpleNamespace(Error=Exception))
    app.include_router(router)

    @app.middleware("http")
    async def add_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    path = (
        f"/operator/api/extension-learning/{LOCATION_ID}/summary"
        if route == "summary"
        else f"/operator/api/extension-learning/{LOCATION_ID}/modules"
    )
    with TestClient(app) as client:
        response = client.get(path)

    assert response.status_code == 500
    expected_message = (
        "Extension-learning summary unavailable"
        if route == "summary"
        else "Extension module catalog unavailable"
    )
    assert response.json() == {"error": expected_message}
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"


def test_http_route_fails_closed_on_missing_tenant_grant(monkeypatch):
    from services.gateway.extension_learning_routes import register_extension_learning_routes

    def deny(*_args, **_kwargs):
        raise TenantContextDenied("missing grant")

    monkeypatch.setattr(
        "services.gateway.extension_learning_reads.get_location_extension_learning_summary",
        deny,
    )
    app = FastAPI()
    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_extension_learning_routes(router, object(), run_in_threadpool, SimpleNamespace(Error=Exception))
    app.include_router(router)

    @app.middleware("http")
    async def add_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    with TestClient(app) as client:
        response = client.get(f"/operator/api/extension-learning/{LOCATION_ID}/summary")

    assert response.status_code == 403
    assert response.headers["cache-control"] == "no-store"
