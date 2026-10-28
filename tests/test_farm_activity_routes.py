"""HTTP contract tests for the native Gateway farm-activity operations."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

pytest.importorskip("fastapi")
from fastapi import APIRouter, FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from services.common.tenant_context import TenantContextDenied  # noqa: E402
from services.gateway import farm_activity_records  # noqa: E402
from services.gateway.farm_activity_routes import register_farm_activity_record_routes  # noqa: E402

OPERATOR_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
ACTIVITY_ID = "22222222-2222-4222-8222-222222222222"
LOCATION_ID = "11111111-1111-4111-8111-111111111111"


def _summary(**overrides):
    result = {
        "id": ACTIVITY_ID,
        "location_id": LOCATION_ID,
        "plot_id": None,
        "crop_cycle_id": None,
        "activity_type": "weeding",
        "activity_date": "2026-10-15",
        "status": "published",
        "source_system": "kokonut_gateway",
        "created_at": "2026-10-15T10:00:00+00:00",
        "updated_at": "2026-10-16T10:00:00+00:00",
    }
    return {**result, **overrides}


def _client(provider):
    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    class DatabaseError(Exception):
        def __init__(self, message, *, pgcode):
            super().__init__(message)
            self.pgcode = pgcode

    register_farm_activity_record_routes(
        router,
        provider,
        run_in_threadpool,
        SimpleNamespace(Error=DatabaseError),
    )
    app = FastAPI()
    app.include_router(router)

    @app.middleware("http")
    async def operator_session(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    return TestClient(app)


def test_create_route_requires_content_wrapper_and_returns_no_store_response(monkeypatch):
    calls = []
    monkeypatch.setattr(
        farm_activity_records,
        "create_farm_activity_record",
        lambda *args: calls.append(args) or {"id": ACTIVITY_ID, "event_id": "event-1"},
    )
    with _client(object()) as client:
        invalid = client.post(
            "/operator/api/farm-activity-records",
            params={"location_id": LOCATION_ID},
            json={"activity_type": "weeding"},
        )
        created = client.post(
            "/operator/api/farm-activity-records",
            params={"location_id": LOCATION_ID},
            json={"content": {"activity_type": "weeding"}},
        )

    assert invalid.status_code == 422
    assert calls == [(OPERATOR_ID, LOCATION_ID, {"activity_type": "weeding"})]
    assert created.status_code == 201
    assert created.json()["data"]["id"] == ACTIVITY_ID
    assert created.headers["cache-control"] == "no-store"
    assert created.headers["vary"] == "Cookie"


def test_published_list_uses_analyst_safe_filter_and_tenant_denial_is_forbidden(monkeypatch):
    seen = []

    def list_records(*args, **kwargs):
        seen.append((args, kwargs))
        return [_summary()]

    monkeypatch.setattr(farm_activity_records, "list_farm_activity_records", list_records)
    with _client(object()) as client:
        response = client.get(
            "/operator/api/farm-activity-records/published",
            params={"location_id": LOCATION_ID, "limit": 10},
        )

    monkeypatch.setattr(
        farm_activity_records,
        "list_farm_activity_records",
        lambda *_args, **_kwargs: _raise_tenant_denied(),
    )
    with _client(object()) as client:
        denied = client.get(
            "/operator/api/farm-activity-records",
            params={"location_id": LOCATION_ID},
        )

    assert seen == [
        ((OPERATOR_ID, LOCATION_ID, 10), {"published_only": True})
    ]
    assert response.status_code == 200
    assert response.json()["data"][0]["status"] == "published"
    assert denied.status_code == 403
    assert denied.headers["cache-control"] == "no-store"


@pytest.mark.parametrize(
    "path,record",
    [
        ("/operator/api/farm-activity-records", _summary(private_value="must not escape")),
        (
            "/operator/api/farm-activity-records",
            _summary(location_id="99999999-9999-4999-8999-999999999999"),
        ),
        (
            "/operator/api/farm-activity-records",
            _summary(source_system="field_collector"),
        ),
        ("/operator/api/farm-activity-records/published", _summary(status="draft")),
    ],
)
def test_list_routes_reject_malformed_or_out_of_scope_service_projection(
    monkeypatch, path, record
):
    monkeypatch.setattr(
        farm_activity_records,
        "list_farm_activity_records",
        lambda *_args, **_kwargs: [record],
    )
    with _client(object()) as client:
        response = client.get(path, params={"location_id": LOCATION_ID})

    assert response.status_code == 500
    assert response.json() == {"error": "Farm activity records are unavailable"}
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert "must not escape" not in response.text


def test_list_routes_publish_exact_openapi_summary_contract():
    with _client(object()) as client:
        schema = client.app.openapi()

    for path in (
        "/operator/api/farm-activity-records",
        "/operator/api/farm-activity-records/published",
    ):
        operation = schema["paths"][path]["get"]
        assert operation["responses"]["200"]["content"]["application/json"]["schema"] == {
            "$ref": "#/components/schemas/FarmActivitySummaryListResponse"
        }
    assert schema["components"]["schemas"]["FarmActivitySummaryResponse"][
        "additionalProperties"
    ] is False
    assert schema["components"]["schemas"]["FarmActivitySummaryListResponse"][
        "additionalProperties"
    ] is False


@pytest.mark.parametrize(
    "path",
    [
        "/operator/api/farm-activity-records",
        "/operator/api/farm-activity-records/published",
    ],
)
def test_list_limits_are_advertised_and_rejected_before_service_access(monkeypatch, path):
    def unexpected_service(*_args, **_kwargs):
        raise AssertionError("FastAPI should reject the limit before service/database access")

    monkeypatch.setattr(farm_activity_records, "list_farm_activity_records", unexpected_service)
    with _client(object()) as client:
        operation = client.app.openapi()["paths"][path]["get"]
        limit = next(parameter for parameter in operation["parameters"] if parameter["name"] == "limit")
        assert limit["schema"] == {
            "type": "integer",
            "minimum": 1,
            "maximum": 100,
            "default": 50,
            "title": "Limit",
        }

        for invalid_limit in (0, 101):
            response = client.get(
                path,
                params={"location_id": LOCATION_ID, "limit": invalid_limit},
            )
            assert response.status_code == 422
            assert response.json()["detail"][0]["loc"] == ["query", "limit"]


def test_transition_maps_database_workflow_guard_to_conflict(monkeypatch):
    class DatabaseError(Exception):
        pgcode = "P0001"

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    router = APIRouter()
    fake_psycopg = SimpleNamespace(Error=DatabaseError)
    def reject_transition(*_args, **_kwargs):
        raise DatabaseError("guard rejected transition")

    monkeypatch.setattr(
        farm_activity_records,
        "transition_farm_activity_record",
        reject_transition,
    )
    register_farm_activity_record_routes(router, object(), run_in_threadpool, fake_psycopg)
    app = FastAPI()
    app.include_router(router)

    @app.middleware("http")
    async def operator_session(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    with TestClient(app) as client:
        response = client.post(
            f"/operator/api/farm-activity-records/{ACTIVITY_ID}/verify",
            params={"location_id": LOCATION_ID},
            json={"reason": "independent evidence review"},
        )

    assert response.status_code == 409
    assert "prevent this operation" in response.json()["error"]
    assert response.headers["cache-control"] == "no-store"


def test_routes_fail_closed_when_identity_provider_is_disabled(monkeypatch):
    with _client(None) as client:
        response = client.get(
            "/operator/api/farm-activity-records",
            params={"location_id": LOCATION_ID},
        )

    assert response.status_code == 404
    assert response.json() == {"error": "Operator OIDC is disabled"}
    assert response.headers["cache-control"] == "no-store"


def _raise_tenant_denied():
    raise TenantContextDenied("denied")
