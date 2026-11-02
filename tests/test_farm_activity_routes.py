"""HTTP contract tests for the native Gateway farm-activity operations."""

from __future__ import annotations

from decimal import Decimal
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
EVENT_ID = "33333333-3333-4333-8333-333333333333"
FARM_TASK_ID = "44444444-4444-4444-8444-444444444444"


def _summary(**overrides):
    result = {
        "id": ACTIVITY_ID,
        "location_id": LOCATION_ID,
        "plot_id": None,
        "crop_cycle_id": None,
        "farm_task_id": None,
        "activity_type": "weeding",
        "activity_date": "2026-10-15",
        "status": "published",
        "source_system": "kokonut_gateway",
        "created_at": "2026-10-15T10:00:00+00:00",
        "updated_at": "2026-10-16T10:00:00+00:00",
    }
    return {**result, **overrides}


def _detail(**overrides):
    result = {
        **_summary(),
        "description": "Hand weeded the north plot",
        "labor_hours": Decimal("2.50"),
        "labor_cost": Decimal("15.00"),
        "materials_used": [],
        "evidence_urls": ["https://evidence.example/photo.jpg"],
        "notes": None,
        "operator_events": [
            {
                "action": "draft_created",
                "from_status": None,
                "to_status": "draft",
                "reason": None,
                "actor_operator_id": OPERATOR_ID,
                "changed_fields": None,
                "created_at": "2026-10-15T10:00:00+00:00",
            }
        ],
    }
    return {**result, **overrides}


def _draft_write(**overrides):
    result = {key: value for key, value in _detail().items() if key != "operator_events"}
    result.update(status="draft", event_id=EVENT_ID)
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
        lambda *args: calls.append(args) or _draft_write(),
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
    assert created.json()["data"]["event_id"] == EVENT_ID
    assert created.json()["data"]["status"] == "draft"
    assert created.headers["cache-control"] == "no-store"
    assert created.headers["vary"] == "Cookie"


def test_farm_activity_write_openapi_contracts_are_exact():
    with _client(object()) as client:
        schema = client.app.openapi()

    paths = schema["paths"]
    post = paths["/operator/api/farm-activity-records"]["post"]
    assert post["responses"]["201"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/FarmActivityDraftWriteResponse"
    }
    patch = paths["/operator/api/farm-activity-records/{activity_id}/draft"]["patch"]
    assert patch["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/FarmActivityDraftWriteResponse"
    }
    transition = paths[
        "/operator/api/farm-activity-records/{activity_id}/{action}"
    ]["post"]
    assert transition["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/FarmActivityTransitionResponse"
    }
    action_parameter = next(
        parameter for parameter in transition["parameters"] if parameter["name"] == "action"
    )
    assert action_parameter["schema"]["enum"] == [
        "submit",
        "verify",
        "reject",
        "request-rework",
        "publish",
        "close-exception",
    ]

    schemas = schema["components"]["schemas"]
    draft_fields = {
        "id",
        "location_id",
        "plot_id",
        "crop_cycle_id",
        "farm_task_id",
        "activity_type",
        "activity_date",
        "description",
        "labor_hours",
        "labor_cost",
        "materials_used",
        "evidence_urls",
        "notes",
        "status",
        "source_system",
        "created_at",
        "updated_at",
        "event_id",
    }
    assert set(schemas["FarmActivityDraftWriteResponseData"]["properties"]) == draft_fields
    assert schemas["FarmActivityDraftWriteResponse"]["additionalProperties"] is False
    assert schemas["FarmActivityDraftWriteResponseData"]["additionalProperties"] is False
    assert set(schemas["FarmActivityTransitionResponse"]["properties"]) == {
        "event_id",
        "activity_id",
        "location_id",
        "action",
        "from_status",
        "to_status",
        "reason",
        "created_at",
    }
    assert schemas["FarmActivityTransitionResponse"]["additionalProperties"] is False


def test_edit_draft_returns_exact_bound_write_response(monkeypatch):
    seen = []

    def edit(*args):
        seen.append(args)
        return _draft_write(notes="Updated field note")

    monkeypatch.setattr(farm_activity_records, "edit_farm_activity_record_draft", edit)
    with _client(object()) as client:
        response = client.patch(
            f"/operator/api/farm-activity-records/{ACTIVITY_ID}/draft",
            params={"location_id": LOCATION_ID},
            json={"content": {"notes": "Updated field note"}, "reason": "Corrected entry"},
        )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert response.json()["data"]["notes"] == "Updated field note"
    assert set(response.json()["data"]) == set(_draft_write())
    assert seen == [
        (OPERATOR_ID, ACTIVITY_ID, LOCATION_ID, {"notes": "Updated field note"}, "Corrected entry")
    ]


@pytest.mark.parametrize(
    "path,result",
    [
        ("create", _draft_write(location_id="99999999-9999-4999-8999-999999999999")),
        ("create", _draft_write(private_value="must not escape")),
        ("create", _draft_write(created_at="2026-10-15T10:00:00")),
        ("edit", _draft_write(id="99999999-9999-4999-8999-999999999999")),
        ("edit", _draft_write(status="submitted")),
    ],
)
def test_draft_write_rejects_mismatched_or_undeclared_projection(monkeypatch, path, result):
    service_name = (
        "create_farm_activity_record" if path == "create" else "edit_farm_activity_record_draft"
    )
    monkeypatch.setattr(farm_activity_records, service_name, lambda *_args: result)
    with _client(object()) as client:
        if path == "create":
            response = client.post(
                "/operator/api/farm-activity-records",
                params={"location_id": LOCATION_ID},
                json={"content": {"activity_type": "weeding"}},
            )
        else:
            response = client.patch(
                f"/operator/api/farm-activity-records/{ACTIVITY_ID}/draft",
                params={"location_id": LOCATION_ID},
                json={"content": {"notes": "Updated"}, "reason": "Correction"},
            )

    assert response.status_code == 500
    assert response.json() == {"error": "Farm activity records are unavailable"}
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert "must not escape" not in response.text


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
    "path,published_only",
    [
        (f"/operator/api/farm-activity-records/{ACTIVITY_ID}", False),
        (f"/operator/api/farm-activity-records/published/{ACTIVITY_ID}", True),
    ],
)
def test_detail_routes_validate_projection_and_bind_request_scope(
    monkeypatch, path, published_only
):
    seen = []

    def get_record(*args, **kwargs):
        seen.append((args, kwargs))
        return _detail()

    monkeypatch.setattr(farm_activity_records, "get_farm_activity_record", get_record)
    with _client(object()) as client:
        response = client.get(path, params={"location_id": LOCATION_ID})

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert response.json()["data"]["id"] == ACTIVITY_ID
    assert response.json()["data"]["operator_events"][0]["actor_operator_id"] == OPERATOR_ID
    assert "source_raw" not in response.json()["data"]
    assert seen == [
        ((OPERATOR_ID, ACTIVITY_ID, LOCATION_ID), {"published_only": True})
        if published_only
        else ((OPERATOR_ID, ACTIVITY_ID, LOCATION_ID), {})
    ]


@pytest.mark.parametrize(
    "record",
    [
        _detail(location_id="99999999-9999-4999-8999-999999999999"),
        _detail(id="99999999-9999-4999-8999-999999999999"),
        _detail(source_system="field_collector"),
        _detail(source_raw={"secret": "must not escape"}),
        _detail(operator_events=[{"action": "invented"}]),
        _detail(labor_hours="2.50"),
    ],
)
def test_detail_route_rejects_invalid_or_out_of_scope_projection(monkeypatch, record):
    monkeypatch.setattr(
        farm_activity_records,
        "get_farm_activity_record",
        lambda *_args, **_kwargs: record,
    )
    with _client(object()) as client:
        response = client.get(
            f"/operator/api/farm-activity-records/{ACTIVITY_ID}",
            params={"location_id": LOCATION_ID},
        )

    assert response.status_code == 500
    assert response.json() == {"error": "Farm activity records are unavailable"}
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert "must not escape" not in response.text


def test_published_detail_rejects_nonpublished_status(monkeypatch):
    monkeypatch.setattr(
        farm_activity_records,
        "get_farm_activity_record",
        lambda *_args, **_kwargs: _detail(status="draft"),
    )
    with _client(object()) as client:
        response = client.get(
            f"/operator/api/farm-activity-records/published/{ACTIVITY_ID}",
            params={"location_id": LOCATION_ID},
        )

    assert response.status_code == 500
    assert response.json() == {"error": "Farm activity records are unavailable"}
    assert response.headers["cache-control"] == "no-store"


def test_detail_tenant_denial_remains_forbidden_and_uncached(monkeypatch):
    monkeypatch.setattr(
        farm_activity_records,
        "get_farm_activity_record",
        lambda *_args, **_kwargs: _raise_tenant_denied(),
    )
    with _client(object()) as client:
        response = client.get(
            f"/operator/api/farm-activity-records/{ACTIVITY_ID}",
            params={"location_id": LOCATION_ID},
        )

    assert response.status_code == 403
    assert response.json() == {"error": "Tenant-qualified operator access is required"}
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"


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


def test_detail_routes_publish_exact_openapi_contract():
    with _client(object()) as client:
        schema = client.app.openapi()

    for path in (
        "/operator/api/farm-activity-records/{activity_id}",
        "/operator/api/farm-activity-records/published/{activity_id}",
    ):
        operation = schema["paths"][path]["get"]
        assert operation["responses"]["200"]["content"]["application/json"]["schema"] == {
            "$ref": "#/components/schemas/FarmActivityDetailResponse"
        }
    assert schema["components"]["schemas"]["FarmActivityDetailResponse"][
        "additionalProperties"
    ] is False
    assert schema["components"]["schemas"]["FarmActivityDetailResponseData"][
        "additionalProperties"
    ] is False
    assert schema["components"]["schemas"]["FarmActivityOperatorEventResponse"][
        "additionalProperties"
    ] is False
    assert set(schema["components"]["schemas"]["FarmActivityDetailResponseData"]["properties"]) == {
        "id",
        "location_id",
        "plot_id",
        "crop_cycle_id",
        "farm_task_id",
        "activity_type",
        "activity_date",
        "description",
        "labor_hours",
        "labor_cost",
        "materials_used",
        "evidence_urls",
        "notes",
        "status",
        "source_system",
        "created_at",
        "updated_at",
        "operator_events",
    }


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


def _transition_result(action, from_status, to_status, reason=None, **overrides):
    result = {
        "event_id": EVENT_ID,
        "activity_id": ACTIVITY_ID,
        "location_id": LOCATION_ID,
        "action": action,
        "from_status": from_status,
        "to_status": to_status,
        "reason": reason,
        "created_at": "2026-10-16T10:00:00+00:00",
    }
    return {**result, **overrides}


@pytest.mark.parametrize(
    "route_action,event_action,from_status,to_status,reason",
    [
        ("submit", "submitted", "draft", "submitted", None),
        ("verify", "verified", "submitted", "verified", None),
        ("reject", "rejected", "verified", "rejected", "Evidence needs correction"),
        ("request-rework", "rework_requested", "rejected", "draft", "Rework requested"),
        ("publish", "published", "verified", "published", None),
        ("close-exception", "exception_closed", "rejected", "rejected", "Exception resolved"),
    ],
)
def test_transition_returns_exact_bound_lifecycle_response(
    monkeypatch, route_action, event_action, from_status, to_status, reason
):
    seen = []

    def transition(*args):
        seen.append(args)
        return _transition_result(event_action, from_status, to_status, reason)

    monkeypatch.setattr(farm_activity_records, "transition_farm_activity_record", transition)
    with _client(object()) as client:
        response = client.post(
            f"/operator/api/farm-activity-records/{ACTIVITY_ID}/{route_action}",
            params={"location_id": LOCATION_ID},
            json={"reason": reason} if reason is not None else {},
        )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert set(response.json()) == {
        "event_id",
        "activity_id",
        "location_id",
        "action",
        "from_status",
        "to_status",
        "reason",
        "created_at",
    }
    assert response.json()["action"] == event_action
    assert response.json()["from_status"] == from_status
    assert response.json()["to_status"] == to_status
    assert seen == [(OPERATOR_ID, ACTIVITY_ID, LOCATION_ID, route_action, reason)]


@pytest.mark.parametrize(
    "route_action,result",
    [
        ("verify", _transition_result("submitted", "draft", "submitted")),
        (
            "verify",
            _transition_result(
                "verified", "draft", "verified", location_id="99999999-9999-4999-8999-999999999999"
            ),
        ),
        (
            "verify",
            _transition_result(
                "verified", "submitted", "verified", activity_id="99999999-9999-4999-8999-999999999999"
            ),
        ),
        ("verify", _transition_result("verified", "draft", "verified")),
        (
            "reject",
            _transition_result("rejected", "submitted", "rejected", private_value="must not escape"),
        ),
        ("reject", _transition_result("rejected", "submitted", "rejected")),
        ("verify", _transition_result("draft_edited", "draft", "submitted")),
        (
            "reject",
            _transition_result("rejected", "submitted", "rejected", "   "),
        ),
        (
            "verify",
            _transition_result("verified", "submitted", "verified", created_at="2026-10-16T10:00:00"),
        ),
    ],
)
def test_transition_rejects_mismatched_or_invalid_projection(monkeypatch, route_action, result):
    monkeypatch.setattr(
        farm_activity_records,
        "transition_farm_activity_record",
        lambda *_args: result,
    )
    with _client(object()) as client:
        response = client.post(
            f"/operator/api/farm-activity-records/{ACTIVITY_ID}/{route_action}",
            params={"location_id": LOCATION_ID},
            json={"reason": "Required review reason"} if route_action == "reject" else {},
        )

    assert response.status_code == 500
    assert response.json() == {"error": "Farm activity records are unavailable"}
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert "must not escape" not in response.text


def test_transition_rejects_undeclared_action_before_service_access(monkeypatch):
    def unexpected_service(*_args, **_kwargs):
        raise AssertionError("FastAPI should reject the transition action before service access")

    monkeypatch.setattr(
        farm_activity_records,
        "transition_farm_activity_record",
        unexpected_service,
    )
    with _client(object()) as client:
        response = client.post(
            f"/operator/api/farm-activity-records/{ACTIVITY_ID}/invented",
            params={"location_id": LOCATION_ID},
            json={},
        )

    assert response.status_code == 422


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
