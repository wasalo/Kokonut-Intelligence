"""OIDC operator authorization for Field Collector administration."""

from dataclasses import dataclass
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

pytest.importorskip("fastapi")
from starlette.testclient import TestClient  # noqa: E402

from services.gateway import operator_auth  # noqa: E402
from services.gateway.app import create_app  # noqa: E402
from services.gateway.router import get_route_policy  # noqa: E402
from services.mobile import api as mobile_api  # noqa: E402

LOCATION_ID = "11111111-1111-4111-8111-111111111111"
OPERATOR_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"


@dataclass(frozen=True)
class _Principal:
    operator_id: str = OPERATOR_ID
    issuer: str = "https://identity.example"
    subject: str = "operator-subject"
    display_name: str | None = "Field reviewer"
    email: str | None = None


@dataclass(frozen=True)
class _Session:
    session_id: str = "session-id"
    csrf_token_hash: str = "not-used-by-fake"
    operator: _Principal = _Principal()
    session_token_hash: str = "a" * 64


class _FakeProvider:
    def __init__(self, *, allowed=True):
        self.allowed = allowed
        self.session = _Session()
        self.settings = SimpleNamespace(state_secret="test-state-secret-with-at-least-32-bytes")

    def authenticate_request(self, request):
        if request.cookies.get(operator_auth.SESSION_COOKIE) == "valid-session":
            return self.session
        return None

    def csrf_valid(self, request, _session):
        return (
            request.cookies.get(operator_auth.CSRF_COOKIE) == "valid-csrf"
            and request.headers.get("x-csrf-token") == "valid-csrf"
        )

    def has_scope(self, operator_id, resource, action, location_id):
        return (
            self.allowed
            and operator_id == OPERATOR_ID
            and resource == "mobile_device"
            and action == "enroll"
            and location_id == LOCATION_ID
        )

    def list_scopes(self, _operator_id):
        return []

    def revoke_session(self, _session_id):
        return None


class _MobileDeviceProvider(_FakeProvider):
    def __init__(self, *, allowed_actions=()):
        super().__init__(allowed=False)
        self.allowed_actions = set(allowed_actions)
        self.scopes_seen = []

    def has_scope(self, operator_id, resource, action, location_id):
        self.scopes_seen.append((operator_id, resource, action, location_id))
        return (
            operator_id == OPERATOR_ID
            and resource == "mobile_device"
            and action in self.allowed_actions
            and location_id == LOCATION_ID
        )


class _MobileParticipantProvider(_FakeProvider):
    def __init__(self, *, allowed_actions=()):
        super().__init__(allowed=False)
        self.allowed_actions = set(allowed_actions)
        self.scopes_seen = []

    def has_scope(self, operator_id, resource, action, location_id):
        self.scopes_seen.append((operator_id, resource, action, location_id))
        return (
            operator_id == OPERATOR_ID
            and resource == "mobile_participant"
            and action in self.allowed_actions
            and location_id == LOCATION_ID
        )


def test_operator_mobile_routes_require_location_scoped_actions():
    create_policy = operator_auth.auth_route_policy(
        "POST",
        f"/operator/api/mobile/locations/{LOCATION_ID}/enrollments",
        enabled=True,
    )
    revoke_enrollment_policy = operator_auth.auth_route_policy(
        "DELETE",
        f"/operator/api/mobile/locations/{LOCATION_ID}/enrollments/22222222-2222-4222-8222-222222222222",
        enabled=True,
    )
    revoke_device_policy = operator_auth.auth_route_policy(
        "POST",
        f"/operator/api/mobile/locations/{LOCATION_ID}/devices/field-phone/revoke",
        enabled=True,
    )

    assert create_policy["resource"] == "mobile_device"
    assert create_policy["action"] == "enroll"
    assert create_policy["location_id"] == LOCATION_ID
    assert revoke_enrollment_policy["action"] == "revoke"
    assert revoke_device_policy["action"] == "revoke"
    assert operator_auth.auth_route_policy(
        "POST",
        f"/operator/api/mobile/locations/{LOCATION_ID}/enrollments",
        enabled=False,
    ) is None


def test_operator_mobile_inventory_requires_device_and_collection_read_grants():
    path = f"/operator/api/mobile/locations/{LOCATION_ID}/inventory"
    policy = operator_auth.auth_route_policy("GET", path, enabled=True)

    assert policy["resource"] == "mobile_device"
    assert policy["action"] == "read"
    assert policy["location_id"] == LOCATION_ID
    assert policy["additional_scopes"] == [
        {"resource": "mobile_collection_review", "action": "read"}
    ]
    assert operator_auth.auth_route_policy("POST", path, enabled=True) is None
    assert operator_auth.auth_route_policy("GET", path, enabled=False) is None


def test_operator_participant_routes_require_location_scoped_actions():
    create_policy = operator_auth.auth_route_policy(
        "POST",
        f"/operator/api/mobile/locations/{LOCATION_ID}/participants",
        enabled=True,
    )
    revoke_policy = operator_auth.auth_route_policy(
        "POST",
        f"/operator/api/mobile/locations/{LOCATION_ID}/participants/revoke",
        enabled=True,
    )

    assert (create_policy["resource"], create_policy["action"]) == (
        "mobile_participant",
        "create",
    )
    assert (revoke_policy["resource"], revoke_policy["action"]) == (
        "mobile_participant",
        "revoke",
    )
    assert create_policy["location_id"] == revoke_policy["location_id"] == LOCATION_ID
    assert operator_auth.auth_route_policy(
        "POST", f"/api/mobile/locations/{LOCATION_ID}/participants", enabled=True
    ) is None
    legacy_policy = get_route_policy(
        "POST", f"/api/mobile/locations/{LOCATION_ID}/participants"
    )
    assert (legacy_policy["resource"], legacy_policy["action"]) == (
        "mobile_participant",
        "create",
    )
    assert legacy_policy["public"] is False


@pytest.mark.parametrize(
    ("action", "suffix", "body", "fetch_rows", "status_code"),
    [
        (
            "create",
            "",
            {
                "party_id": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
                "evidence": {"review": "identity confirmed"},
            },
            [(1,), ("link-id", datetime(2026, 10, 13, tzinfo=timezone.utc))],
            201,
        ),
        (
            "revoke",
            "/revoke",
            {"participant_ref": "x" * 40},
            [("link-id", datetime(2026, 10, 13, tzinfo=timezone.utc))],
            200,
        ),
    ],
)
def test_operator_participant_mutation_sets_context_before_sql_and_cleans_transaction(
    monkeypatch, action, suffix, body, fetch_rows, status_code
):
    from services.gateway.audit import GatewayAudit

    provider = _MobileParticipantProvider(allowed_actions={action})
    monkeypatch.setattr(operator_auth, "create_provider", lambda: provider)
    monkeypatch.setattr(GatewayAudit, "log", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(GatewayAudit, "reserve_mutation", lambda _self: "reservation")
    released_session_hashes = []

    def release_mutation(*_args):
        from services.common.tenant_context import current_operator_session_token_hash

        released_session_hashes.append(current_operator_session_token_hash())

    monkeypatch.setattr(GatewayAudit, "release_mutation", release_mutation)
    database = MagicMock()
    database.cursor.return_value.fetchone.side_effect = fetch_rows
    events = []
    context_calls = []
    session_hashes_seen = []

    def set_context(connection, **kwargs):
        from services.common.tenant_context import current_operator_session_token_hash

        events.append(("context", kwargs))
        context_calls.append((connection, kwargs))
        session_hashes_seen.append(current_operator_session_token_hash())

    def execute(sql, params=None):
        events.append(("sql", sql, params))

    database.cursor.return_value.execute.side_effect = execute
    monkeypatch.setattr(mobile_api, "get_db", lambda: database)
    monkeypatch.setattr(mobile_api, "set_operator_tenant_context", set_context)

    with TestClient(create_app()) as client:
        _set_operator_cookies(client, csrf=True)
        response = client.post(
            f"/operator/api/mobile/locations/{LOCATION_ID}/participants{suffix}",
            headers={"X-CSRF-Token": "valid-csrf"},
            json=body,
        )

    assert response.status_code == status_code, response.text
    assert response.headers["cache-control"] == "no-store"
    assert provider.scopes_seen == [(OPERATOR_ID, "mobile_participant", action, LOCATION_ID)]
    assert context_calls == [
        (
            database,
            {
                "operator_id": OPERATOR_ID,
                "location_id": LOCATION_ID,
                "resource": "mobile_participant",
                "action": action,
            },
        )
    ]
    assert session_hashes_seen == ["a" * 64]
    assert released_session_hashes == [None]
    assert events[0][0] == "context"
    assert any(event[0] == "sql" for event in events)
    assert database.commit.called
    assert not database.rollback.called
    database.close.assert_called_once()


@pytest.mark.parametrize(
    ("action", "suffix", "body"),
    [
        (
            "create",
            "",
            {
                "party_id": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
                "evidence": {"review": "identity confirmed"},
            },
        ),
        ("revoke", "/revoke", {"participant_ref": "x" * 40}),
    ],
)
def test_operator_participant_cross_tenant_denial_returns_403_before_query(
    monkeypatch, action, suffix, body
):
    from services.common.tenant_context import TenantContextDenied
    from services.gateway.audit import GatewayAudit

    provider = _MobileParticipantProvider(allowed_actions={action})
    monkeypatch.setattr(operator_auth, "create_provider", lambda: provider)
    monkeypatch.setattr(GatewayAudit, "log", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(GatewayAudit, "reserve_mutation", lambda _self: "reservation")
    monkeypatch.setattr(GatewayAudit, "release_mutation", lambda *_args: None)
    database = MagicMock()
    context = MagicMock(side_effect=TenantContextDenied("tenant mismatch"))
    monkeypatch.setattr(mobile_api, "get_db", lambda: database)
    monkeypatch.setattr(mobile_api, "set_operator_tenant_context", context)

    with TestClient(create_app()) as client:
        _set_operator_cookies(client, csrf=True)
        response = client.post(
            f"/operator/api/mobile/locations/{LOCATION_ID}/participants{suffix}",
            headers={"X-CSRF-Token": "valid-csrf"},
            json=body,
        )

    assert response.status_code == 403, response.text
    assert response.headers["cache-control"] == "no-store"
    context.assert_called_once_with(
        database,
        operator_id=OPERATOR_ID,
        location_id=LOCATION_ID,
        resource="mobile_participant",
        action=action,
    )
    database.cursor.return_value.execute.assert_not_called()
    database.rollback.assert_called_once()
    database.close.assert_called_once()


def test_mobile_collection_review_routes_use_separate_location_read_actions():
    queue_policy = operator_auth.auth_route_policy(
        "GET",
        "/operator/api/mobile-collection-review-queue",
        enabled=True,
    )
    detail_policy = operator_auth.auth_route_policy(
        "GET",
        "/operator/api/mobile-collection-review-queue/22222222-2222-4222-8222-222222222222",
        enabled=True,
    )

    assert queue_policy["resource"] == "mobile_collection_review"
    assert queue_policy["action"] == "read"
    assert queue_policy["scope_required"] is True
    assert detail_policy["resource"] == "mobile_collection_review"
    assert detail_policy["action"] == "read_detail"
    assert detail_policy["scope_required"] is True
    assert operator_auth.auth_route_policy(
        "GET", "/operator/api/mobile-collection-review-queue", enabled=False
    ) is None
    event_policy = operator_auth.auth_route_policy(
        "POST",
        "/operator/api/mobile-collection-review-queue/22222222-2222-4222-8222-222222222222/events",
        enabled=True,
    )
    assert event_policy["action"] == "review"
    assert event_policy["additional_scopes"] == [
        {"resource": "mobile_collection_review", "action": "read_detail"}
    ]


def test_mobile_disposition_inventory_requires_retention_and_queue_read_scopes():
    path = (
        "/operator/api/mobile-collection-review-queue/"
        "22222222-2222-4222-8222-222222222222/disposition-inventory"
    )
    policy = operator_auth.auth_route_policy("GET", path, enabled=True)

    assert policy["resource"] == "mobile_collection_retention"
    assert policy["action"] == "inventory"
    assert policy["additional_scopes"] == [
        {"resource": "mobile_collection_review", "action": "read"}
    ]
    assert policy["location_id"] is None
    assert policy["scope_required"] is True
    assert policy["public"] is False
    assert operator_auth.auth_route_policy("POST", path, enabled=True) is None
    assert operator_auth.auth_route_policy("GET", path, enabled=False) is None


def test_farm_activity_intake_routes_require_oidc_and_separate_detail_grants():
    queue_policy = operator_auth.auth_route_policy(
        "GET", "/operator/api/farm-activity-intake-queue", enabled=True
    )
    detail_policy = operator_auth.auth_route_policy(
        "GET",
        "/operator/api/farm-activity-intake-queue/22222222-2222-4222-8222-222222222222",
        enabled=True,
    )
    draft_policy = operator_auth.auth_route_policy(
        "POST",
        "/operator/api/farm-activity-intake-queue/22222222-2222-4222-8222-222222222222/draft",
        enabled=True,
    )

    assert queue_policy["resource"] == "farm_activity"
    assert queue_policy["action"] == "read"
    assert detail_policy["action"] == "read_detail"
    assert detail_policy["additional_scopes"] == [
        {"resource": "mobile_collection_review", "action": "read_detail"}
    ]
    assert draft_policy["action"] == "create_draft"
    assert draft_policy["additional_scopes"] == [
        {"resource": "farm_activity", "action": "read_detail"},
        {"resource": "mobile_collection_review", "action": "read_detail"},
    ]
    assert operator_auth.auth_route_policy(
        "POST",
        "/operator/api/farm-activity-intake-queue/22222222-2222-4222-8222-222222222222/draft",
        enabled=False,
    ) is None


@pytest.mark.parametrize(
    ("route_action", "scope_action"),
    [
        ("submit", "submit"),
        ("verify", "verify"),
        ("reject", "reject"),
        ("request-rework", "rework"),
        ("publish", "publish"),
        ("close-exception", "close_exception"),
    ],
)
def test_farm_activity_lifecycle_routes_require_location_scoped_action(route_action, scope_action):
    path = f"/operator/api/farm-activities/{'33333333-3333-4333-8333-333333333333'}/{route_action}"
    policy = operator_auth.auth_route_policy("POST", path, enabled=True)

    assert policy["resource"] == "farm_activity"
    assert policy["action"] == scope_action
    assert policy["scope_required"] is True
    assert policy["public"] is False
    assert operator_auth.auth_route_policy("GET", path, enabled=True) is None
    assert operator_auth.auth_route_policy(
        "DELETE",
        "/operator/api/farm-activity-intake-queue/22222222-2222-4222-8222-222222222222",
        enabled=True,
    ) is None


def test_farm_activity_draft_edit_route_requires_edit_and_both_detail_scopes():
    path = "/operator/api/farm-activities/33333333-3333-4333-8333-333333333333/draft"
    policy = operator_auth.auth_route_policy("PATCH", path, enabled=True)

    assert policy["resource"] == "farm_activity"
    assert policy["action"] == "edit_draft"
    assert policy["additional_scopes"] == [
        {"resource": "farm_activity", "action": "read_detail"},
        {"resource": "mobile_collection_review", "action": "read_detail"},
    ]
    assert policy["scope_required"] is True
    assert policy["public"] is False
    assert operator_auth.auth_route_policy("PATCH", path, enabled=False) is None
    assert operator_auth.auth_route_policy("POST", path, enabled=True) is None


@pytest.mark.parametrize(
    ("path", "action"),
    [
        ("/operator/api/farm-activities/published", "read_published"),
        (
            "/operator/api/farm-activities/published/33333333-3333-4333-8333-333333333333",
            "read_published_detail",
        ),
    ],
)
def test_analyst_farm_activity_routes_have_approved_data_scopes(path, action):
    policy = operator_auth.auth_route_policy("GET", path, enabled=True)

    assert policy["resource"] == "farm_activity"
    assert policy["action"] == action
    assert policy["scope_required"] is True
    assert policy["public"] is False
    assert operator_auth.auth_route_policy("POST", path, enabled=True) is None
    assert operator_auth.auth_route_policy("GET", path, enabled=False) is None


class _ReviewProvider(_FakeProvider):
    def __init__(self, *, allowed_action=None, allowed_actions=None):
        super().__init__(allowed=False)
        self.allowed_actions = set(allowed_actions or ())
        if allowed_action:
            self.allowed_actions.add(allowed_action)
        self.scopes_seen = []

    def has_scope(self, operator_id, resource, action, location_id):
        self.scopes_seen.append((operator_id, resource, action, location_id))
        return (
            operator_id == OPERATOR_ID
            and resource == "mobile_collection_review"
            and action in self.allowed_actions
            and location_id == LOCATION_ID
        )


class _DispositionProvider(_FakeProvider):
    def __init__(self, *, allowed_scopes=()):
        super().__init__(allowed=False)
        self.allowed_scopes = set(allowed_scopes)
        self.scopes_seen = []

    def has_scope(self, operator_id, resource, action, location_id):
        scope = (operator_id, resource, action, location_id)
        self.scopes_seen.append(scope)
        return (
            operator_id == OPERATOR_ID
            and (resource, action) in self.allowed_scopes
            and location_id == LOCATION_ID
        )


class _FarmActivityProvider(_FakeProvider):
    def __init__(self, *, allowed_scopes=()):
        super().__init__(allowed=False)
        self.allowed_scopes = set(allowed_scopes)
        self.scopes_seen = []

    def has_scope(self, operator_id, resource, action, location_id):
        self.scopes_seen.append((operator_id, resource, action, location_id))
        return (
            operator_id == OPERATOR_ID
            and (resource, action) in self.allowed_scopes
            and location_id == LOCATION_ID
        )


def _set_operator_cookies(client, *, csrf=False):
    client.cookies.set(
        operator_auth.SESSION_COOKIE,
        "valid-session",
        path=operator_auth.SESSION_COOKIE_PATH,
    )
    if csrf:
        client.cookies.set(
            operator_auth.CSRF_COOKIE,
            "valid-csrf",
            path=operator_auth.SESSION_COOKIE_PATH,
        )


def test_operator_list_routes_publish_and_enforce_pagination_bounds_before_service(
    monkeypatch,
):
    class _ScopedProvider(_FakeProvider):
        def has_scope(self, operator_id, _resource, _action, location_id):
            return operator_id == OPERATOR_ID and location_id == LOCATION_ID

    provider = _ScopedProvider()
    monkeypatch.setattr(operator_auth, "create_provider", lambda: provider)
    monkeypatch.setattr("services.gateway.audit.GatewayAudit.log", lambda *_args, **_kwargs: None)

    service_paths = (
        "services.gateway.operator_review.list_submitted_reports",
        "services.gateway.operator_mobile_review.list_mobile_collections",
        "services.gateway.farm_activity_workflow.list_farm_activity_intake",
        "services.gateway.farm_activity_lifecycle.list_farm_activities",
        "services.gateway.operator_mobile_review.get_mobile_operations_inventory",
    )
    services = {
        path: MagicMock(side_effect=AssertionError("invalid limit must fail before service access"))
        for path in service_paths
    }
    for path, service in services.items():
        monkeypatch.setattr(path, service)

    route_cases = (
        ("/operator/api/report-review-queue", "/operator/api/report-review-queue", "limit"),
        (
            "/operator/api/mobile-collection-review-queue",
            "/operator/api/mobile-collection-review-queue",
            "limit",
        ),
        (
            "/operator/api/farm-activity-intake-queue",
            "/operator/api/farm-activity-intake-queue",
            "limit",
        ),
        ("/operator/api/farm-activities", "/operator/api/farm-activities", "limit"),
        (
            "/operator/api/farm-activities/published",
            "/operator/api/farm-activities/published",
            "limit",
        ),
        (
            "/operator/api/mobile/locations/{location_id}/inventory",
            f"/operator/api/mobile/locations/{LOCATION_ID}/inventory",
            "device_limit",
        ),
    )

    with TestClient(create_app()) as client:
        _set_operator_cookies(client)
        schema = client.app.openapi()
        for schema_path, request_path, parameter_name in route_cases:
            parameter = next(
                item
                for item in schema["paths"][schema_path]["get"]["parameters"]
                if item["name"] == parameter_name
            )
            assert parameter["schema"]["minimum"] == 1, schema_path
            assert parameter["schema"]["maximum"] == 100, schema_path
            assert parameter["schema"]["default"] == 50, schema_path

            params = {"location_id": LOCATION_ID} if parameter_name == "limit" else {}
            for invalid_limit in (0, 101):
                response = client.get(
                    request_path,
                    params={**params, parameter_name: invalid_limit},
                )
                assert response.status_code == 422, (
                    request_path,
                    invalid_limit,
                    response.text,
                )
                assert response.json()["detail"][0]["loc"] == ["query", parameter_name]

    for service in services.values():
        service.assert_not_called()


def test_farm_activity_intake_queue_uses_scoped_operator_and_no_store(monkeypatch):
    monkeypatch.setenv("KOKONUT_GATEWAY_CORS_ORIGINS", "https://operator.example")
    provider = _FarmActivityProvider(allowed_scopes={("farm_activity", "read")})
    monkeypatch.setattr(operator_auth, "create_provider", lambda: provider)
    monkeypatch.setattr("services.gateway.audit.GatewayAudit.log", lambda *_args, **_kwargs: None)
    queue_record = {
        "id": "22222222-2222-4222-8222-222222222222",
        "location_id": LOCATION_ID,
        "form_id": "farm_activity_v1",
        "form_version": "1.2.0",
        "collected_at": "2026-10-28T10:00:00+00:00",
        "synced_at": "2026-10-28T11:00:00+00:00",
        "activity_type": "weeding",
        "activity_date": "2026-10-27",
        "eligible_for_use": True,
    }
    queue_reader = MagicMock(return_value=[queue_record])
    monkeypatch.setattr(
        "services.gateway.farm_activity_workflow.list_farm_activity_intake",
        queue_reader,
    )

    with TestClient(create_app(), base_url="https://operator.example") as client:
        _set_operator_cookies(client)
        response = client.get(
            "/operator/api/farm-activity-intake-queue",
            params={"location_id": LOCATION_ID, "limit": 9},
            headers={"Origin": "https://operator.example"},
        )

    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    assert {value.strip() for value in response.headers["vary"].split(",")} == {"Cookie", "Origin"}
    assert response.json()["data"] == [queue_record]
    queue_reader.assert_called_once_with(OPERATOR_ID, LOCATION_ID, 9)
    assert provider.scopes_seen == [(OPERATOR_ID, "farm_activity", "read", LOCATION_ID)]


@pytest.mark.parametrize(
    ("path", "scope", "service_name", "result"),
    [
        (
            "/operator/api/farm-activities/published",
            "read_published",
            "list_farm_activities",
            [{"id": "activity-id", "status": "published"}],
        ),
        (
            "/operator/api/farm-activities/published/33333333-3333-4333-8333-333333333333",
            "read_published_detail",
            "get_farm_activity",
            {"id": "activity-id", "status": "published"},
        ),
    ],
)
def test_analyst_routes_call_consent_and_status_filtered_queries(
    monkeypatch, path, scope, service_name, result
):
    provider = _FarmActivityProvider(allowed_scopes={("farm_activity", scope)})
    monkeypatch.setattr(operator_auth, "create_provider", lambda: provider)
    monkeypatch.setattr("services.gateway.audit.GatewayAudit.log", lambda *_args, **_kwargs: None)
    reader = MagicMock(return_value=result)
    monkeypatch.setattr(
        f"services.gateway.farm_activity_lifecycle.{service_name}", reader
    )

    with TestClient(create_app()) as client:
        _set_operator_cookies(client)
        response = client.get(path, params={"location_id": LOCATION_ID})

    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    assert reader.call_args.kwargs == {"grant_action": scope, "published_only": True}
    assert provider.scopes_seen == [(OPERATOR_ID, "farm_activity", scope, LOCATION_ID)]


def test_farm_activity_detail_requires_both_detail_grants(monkeypatch):
    provider = _FarmActivityProvider(allowed_scopes={("farm_activity", "read_detail")})
    monkeypatch.setattr(operator_auth, "create_provider", lambda: provider)
    monkeypatch.setattr("services.gateway.audit.GatewayAudit.log", lambda *_args, **_kwargs: None)
    detail_reader = MagicMock(return_value={"id": "collection-id"})
    monkeypatch.setattr(
        "services.gateway.farm_activity_workflow.get_farm_activity_intake",
        detail_reader,
    )

    with TestClient(create_app()) as client:
        _set_operator_cookies(client)
        response = client.get(
            "/operator/api/farm-activity-intake-queue/22222222-2222-4222-8222-222222222222",
            params={"location_id": LOCATION_ID},
        )

    assert response.status_code == 403
    assert provider.scopes_seen == [
        (OPERATOR_ID, "farm_activity", "read_detail", LOCATION_ID),
        (OPERATOR_ID, "mobile_collection_review", "read_detail", LOCATION_ID),
    ]
    detail_reader.assert_not_called()


@pytest.mark.parametrize(
    ("path", "service_function"),
    [
        ("/operator/api/report-review-queue", "list_submitted_reports"),
        (
            "/operator/api/report-review-queue/22222222-2222-4222-8222-222222222222",
            "get_submitted_report",
        ),
    ],
)
def test_report_review_routes_require_tenant_qualified_context(
    monkeypatch, path, service_function
):
    from services.common.tenant_context import TenantContextDenied

    provider = _FarmActivityProvider(
        allowed_scopes={("report_snapshot_review", "read")}
    )
    monkeypatch.setattr(operator_auth, "create_provider", lambda: provider)
    monkeypatch.setattr(
        "services.gateway.audit.GatewayAudit.log",
        lambda *_args, **_kwargs: None,
    )
    reader = MagicMock(side_effect=TenantContextDenied("tenant-qualified grant required"))
    monkeypatch.setattr(
        f"services.gateway.operator_review.{service_function}", reader
    )

    with TestClient(create_app()) as client:
        _set_operator_cookies(client)
        response = client.get(
            path,
            params={"location_id": LOCATION_ID},
        )

    assert response.status_code == 403
    assert response.json() == {
        "error": "Tenant-qualified operator access is required"
    }
    assert response.headers["cache-control"] == "no-store"
    assert provider.scopes_seen == [
        (OPERATOR_ID, "report_snapshot_review", "read", LOCATION_ID)
    ]
    reader.assert_called_once()


@pytest.mark.parametrize(
    ("path", "service_function", "scope_action"),
    [
        (
            "/operator/api/mobile-collection-review-queue",
            "list_mobile_collections",
            "read",
        ),
        (
            "/operator/api/mobile-collection-review-queue/22222222-2222-4222-8222-222222222222",
            "get_mobile_collection",
            "read_detail",
        ),
    ],
)
def test_mobile_collection_routes_require_tenant_qualified_context(
    monkeypatch, path, service_function, scope_action
):
    from services.common.tenant_context import TenantContextDenied

    provider = _FarmActivityProvider(
        allowed_scopes={("mobile_collection_review", scope_action)}
    )
    monkeypatch.setattr(operator_auth, "create_provider", lambda: provider)
    monkeypatch.setattr(
        "services.gateway.audit.GatewayAudit.log",
        lambda *_args, **_kwargs: None,
    )
    reader = MagicMock(side_effect=TenantContextDenied("tenant-qualified grant required"))
    monkeypatch.setattr(
        f"services.gateway.operator_mobile_review.{service_function}", reader
    )

    with TestClient(create_app()) as client:
        _set_operator_cookies(client)
        response = client.get(path, params={"location_id": LOCATION_ID})

    assert response.status_code == 403
    assert response.json() == {
        "error": "Tenant-qualified operator access is required"
    }
    assert response.headers["cache-control"] == "no-store"
    assert provider.scopes_seen == [
        (OPERATOR_ID, "mobile_collection_review", scope_action, LOCATION_ID)
    ]
    reader.assert_called_once()


@pytest.mark.parametrize(
    ("csrf", "content_reviewed", "status"),
    [(False, True, 403), (True, False, 422), (True, True, 201)],
)
def test_farm_activity_draft_route_requires_scope_csrf_and_review_acknowledgement(
    monkeypatch, csrf, content_reviewed, status
):
    provider = _FarmActivityProvider(
        allowed_scopes={
            ("farm_activity", "create_draft"),
            ("farm_activity", "read_detail"),
            ("mobile_collection_review", "read_detail"),
        }
    )
    monkeypatch.setattr(operator_auth, "create_provider", lambda: provider)
    audit_records = []
    monkeypatch.setattr(
        "services.gateway.audit.GatewayAudit.log",
        lambda _self, **record: audit_records.append(record),
    )
    monkeypatch.setattr(
        "services.gateway.audit.GatewayAudit.reserve_mutation",
        lambda _self: "test-reservation",
    )
    monkeypatch.setattr(
        "services.gateway.audit.GatewayAudit.release_mutation",
        lambda _self, _reservation: None,
    )
    draft_writer = MagicMock(
        return_value={"id": "activity-id", "status": "draft", "created": True}
    )
    monkeypatch.setattr(
        "services.gateway.farm_activity_workflow.create_farm_activity_draft",
        draft_writer,
    )

    headers = {"X-CSRF-Token": "valid-csrf"} if csrf else {}
    with TestClient(create_app()) as client:
        _set_operator_cookies(client, csrf=csrf)
        response = client.post(
            "/operator/api/farm-activity-intake-queue/22222222-2222-4222-8222-222222222222/draft",
            params={"location_id": LOCATION_ID},
            headers=headers,
            json={"content_reviewed": content_reviewed},
        )

    assert response.status_code == status, response.text
    if status == 201:
        assert response.headers["cache-control"] == "no-store"
        assert response.json()["data"]["status"] == "draft"
        draft_writer.assert_called_once_with(
            OPERATOR_ID,
            "22222222-2222-4222-8222-222222222222",
            LOCATION_ID,
            content_reviewed=True,
        )
        assert audit_records[-1]["caller"] == f"operator:{OPERATOR_ID}"
        assert audit_records[-1]["location_id"] == LOCATION_ID
    else:
        draft_writer.assert_not_called()


@pytest.mark.parametrize(
    ("method", "path", "scopes", "service_path", "body"),
    [
        (
            "GET",
            "/operator/api/farm-activity-intake-queue",
            {("farm_activity", "read")},
            "services.gateway.farm_activity_workflow.list_farm_activity_intake",
            None,
        ),
        (
            "GET",
            "/operator/api/farm-activity-intake-queue/22222222-2222-4222-8222-222222222222",
            {
                ("farm_activity", "read_detail"),
                ("mobile_collection_review", "read_detail"),
            },
            "services.gateway.farm_activity_workflow.get_farm_activity_intake",
            None,
        ),
        (
            "POST",
            "/operator/api/farm-activity-intake-queue/22222222-2222-4222-8222-222222222222/draft",
            {
                ("farm_activity", "create_draft"),
                ("farm_activity", "read_detail"),
                ("mobile_collection_review", "read_detail"),
            },
            "services.gateway.farm_activity_workflow.create_farm_activity_draft",
            {"content_reviewed": True},
        ),
        (
            "GET",
            "/operator/api/farm-activities",
            {("farm_activity", "read")},
            "services.gateway.farm_activity_lifecycle.list_farm_activities",
            None,
        ),
        (
            "GET",
            "/operator/api/farm-activities/33333333-3333-4333-8333-333333333333",
            {("farm_activity", "read_detail")},
            "services.gateway.farm_activity_lifecycle.get_farm_activity",
            None,
        ),
        (
            "POST",
            "/operator/api/farm-activities/33333333-3333-4333-8333-333333333333/reject",
            {("farm_activity", "reject")},
            "services.gateway.farm_activity_lifecycle.transition_farm_activity",
            {"reason": "Reviewed the source and rejected it for rework."},
        ),
        (
            "PATCH",
            "/operator/api/farm-activities/33333333-3333-4333-8333-333333333333/draft",
            {
                ("farm_activity", "edit_draft"),
                ("farm_activity", "read_detail"),
                ("mobile_collection_review", "read_detail"),
            },
            "services.gateway.farm_activity_lifecycle.edit_farm_activity_draft",
            {"content": {"activity_type": "planting"}, "reason": "Corrected after review."},
        ),
    ],
)
def test_farm_activity_context_denial_returns_403(
    monkeypatch, method, path, scopes, service_path, body
):
    from services.common.tenant_context import TenantContextDenied

    provider = _FarmActivityProvider(allowed_scopes=scopes)
    monkeypatch.setattr(operator_auth, "create_provider", lambda: provider)
    monkeypatch.setattr("services.gateway.audit.GatewayAudit.log", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        "services.gateway.audit.GatewayAudit.reserve_mutation",
        lambda _self: "test-reservation",
    )
    monkeypatch.setattr(
        "services.gateway.audit.GatewayAudit.release_mutation",
        lambda *_args: None,
    )
    service = MagicMock(side_effect=TenantContextDenied("grants resolve to different tenants"))
    monkeypatch.setattr(service_path, service)

    headers = {"X-CSRF-Token": "valid-csrf"} if method != "GET" else {}
    with TestClient(create_app()) as client:
        _set_operator_cookies(client, csrf=method != "GET")
        response = client.request(
            method,
            path,
            params={"location_id": LOCATION_ID},
            headers=headers,
            json=body,
        )

    assert response.status_code == 403, response.text
    assert response.headers["cache-control"] == "no-store"
    assert "Cookie" in {value.strip() for value in response.headers["vary"].split(",")}
    service.assert_called_once()


def test_farm_activity_lifecycle_route_requires_scope_csrf_and_passes_reason(monkeypatch):
    provider = _FarmActivityProvider(allowed_scopes={("farm_activity", "reject")})
    monkeypatch.setattr(operator_auth, "create_provider", lambda: provider)
    audit_records = []
    monkeypatch.setattr(
        "services.gateway.audit.GatewayAudit.log",
        lambda _self, **record: audit_records.append(record),
    )
    monkeypatch.setattr(
        "services.gateway.audit.GatewayAudit.reserve_mutation",
        lambda _self: "test-reservation",
    )
    monkeypatch.setattr(
        "services.gateway.audit.GatewayAudit.release_mutation",
        lambda _self, _reservation: None,
    )
    transition = MagicMock(
        return_value={
            "event_id": "event-id",
            "activity_id": "33333333-3333-4333-8333-333333333333",
            "location_id": LOCATION_ID,
            "action": "rejected",
            "from_status": "submitted",
            "to_status": "rejected",
            "reason": "The activity date needs correction",
        }
    )
    monkeypatch.setattr(
        "services.gateway.farm_activity_lifecycle.transition_farm_activity",
        transition,
    )

    headers = {"X-CSRF-Token": "valid-csrf"}
    path = "/operator/api/farm-activities/33333333-3333-4333-8333-333333333333/reject"
    with TestClient(create_app()) as client:
        _set_operator_cookies(client, csrf=True)
        response = client.post(
            path,
            params={"location_id": LOCATION_ID},
            headers=headers,
            json={"reason": "The activity date needs correction"},
        )

    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["data"]["action"] == "rejected"
    transition.assert_called_once_with(
        OPERATOR_ID,
        "33333333-3333-4333-8333-333333333333",
        LOCATION_ID,
        "reject",
        "The activity date needs correction",
    )
    assert provider.scopes_seen == [(OPERATOR_ID, "farm_activity", "reject", LOCATION_ID)]
    assert audit_records[-1]["location_id"] == LOCATION_ID


def test_farm_activity_lifecycle_route_rejects_unknown_body_fields(monkeypatch):
    provider = _FarmActivityProvider(allowed_scopes={("farm_activity", "submit")})
    monkeypatch.setattr(operator_auth, "create_provider", lambda: provider)
    monkeypatch.setattr(
        "services.gateway.audit.GatewayAudit.log",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        "services.gateway.audit.GatewayAudit.reserve_mutation",
        lambda _self: "test-reservation",
    )
    monkeypatch.setattr(
        "services.gateway.audit.GatewayAudit.release_mutation",
        lambda _self, _reservation: None,
    )
    transition = MagicMock()
    monkeypatch.setattr(
        "services.gateway.farm_activity_lifecycle.transition_farm_activity",
        transition,
    )
    path = "/operator/api/farm-activities/33333333-3333-4333-8333-333333333333/submit"

    with TestClient(create_app()) as client:
        _set_operator_cookies(client, csrf=True)
        response = client.post(
            path,
            params={"location_id": LOCATION_ID},
            headers={"X-CSRF-Token": "valid-csrf"},
            json={"verified": True},
        )

    assert response.status_code == 422
    transition.assert_not_called()


def test_farm_activity_draft_edit_route_requires_scope_csrf_and_passes_reason(monkeypatch):
    monkeypatch.setenv("KOKONUT_GATEWAY_CORS_ORIGINS", "https://operator.example")
    provider = _FarmActivityProvider(
        allowed_scopes={
            ("farm_activity", "edit_draft"),
            ("farm_activity", "read_detail"),
            ("mobile_collection_review", "read_detail"),
        }
    )
    monkeypatch.setattr(operator_auth, "create_provider", lambda: provider)
    monkeypatch.setattr("services.gateway.audit.GatewayAudit.log", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        "services.gateway.audit.GatewayAudit.reserve_mutation",
        lambda _self: "test-reservation",
    )
    monkeypatch.setattr(
        "services.gateway.audit.GatewayAudit.release_mutation",
        lambda _self, _reservation: None,
    )
    editor = MagicMock(return_value={"activity_id": "activity-id", "action": "draft_edited"})
    monkeypatch.setattr(
        "services.gateway.farm_activity_lifecycle.edit_farm_activity_draft",
        editor,
    )

    path = "/operator/api/farm-activities/33333333-3333-4333-8333-333333333333/draft"
    with TestClient(create_app(), base_url="https://operator.example") as client:
        _set_operator_cookies(client, csrf=True)
        response = client.patch(
            path,
            params={"location_id": LOCATION_ID},
            headers={
                "X-CSRF-Token": "valid-csrf",
                "Origin": "https://operator.example",
            },
            json={
                "content": {"activity_type": "planting"},
                "reason": "Corrected after review",
            },
        )

    assert response.status_code == 200, response.text
    assert response.headers["access-control-allow-origin"] == "https://operator.example"
    assert response.headers["access-control-allow-credentials"] == "true"
    assert response.headers["cache-control"] == "no-store"
    assert {value.strip() for value in response.headers["vary"].split(",")} == {"Cookie", "Origin"}
    assert response.json()["data"]["action"] == "draft_edited"
    assert provider.scopes_seen == [
        (OPERATOR_ID, "farm_activity", "edit_draft", LOCATION_ID),
        (OPERATOR_ID, "farm_activity", "read_detail", LOCATION_ID),
        (OPERATOR_ID, "mobile_collection_review", "read_detail", LOCATION_ID),
    ]
    editor.assert_called_once_with(
        OPERATOR_ID,
        "33333333-3333-4333-8333-333333333333",
        LOCATION_ID,
        {"activity_type": "planting"},
        "Corrected after review",
    )


def test_operator_cors_preflight_allows_cookie_authenticated_patch(monkeypatch):
    monkeypatch.setenv("KOKONUT_GATEWAY_CORS_ORIGINS", "https://operator.example")
    provider = _FakeProvider()
    monkeypatch.setattr(operator_auth, "create_provider", lambda: provider)

    path = "/operator/api/farm-activities/33333333-3333-4333-8333-333333333333/draft"
    with TestClient(create_app()) as client:
        response = client.options(
            path,
            headers={
                "Origin": "https://operator.example",
                "Access-Control-Request-Method": "PATCH",
                "Access-Control-Request-Headers": "content-type,x-csrf-token",
            },
        )

    assert response.status_code == 200, response.text
    assert response.headers["access-control-allow-origin"] == "https://operator.example"
    assert response.headers["access-control-allow-credentials"] == "true"
    assert "PATCH" in response.headers["access-control-allow-methods"]


@pytest.mark.parametrize(
    ("csrf", "allowed_scopes", "body", "status"),
    [
        (
            False,
            {
                ("farm_activity", "edit_draft"),
                ("farm_activity", "read_detail"),
                ("mobile_collection_review", "read_detail"),
            },
            {"content": {"activity_type": "planting"}, "reason": "Correction"},
            403,
        ),
        (
            True,
            {("farm_activity", "edit_draft"), ("farm_activity", "read_detail")},
            {"content": {"activity_type": "planting"}, "reason": "Correction"},
            403,
        ),
        (
            True,
            {
                ("farm_activity", "edit_draft"),
                ("farm_activity", "read_detail"),
                ("mobile_collection_review", "read_detail"),
            },
            {
                "content": {"activity_type": "planting"},
                "reason": "Correction",
                "actor_operator_id": OPERATOR_ID,
            },
            422,
        ),
    ],
)
def test_farm_activity_draft_edit_route_denies_missing_authority_or_invalid_body(
    monkeypatch, csrf, allowed_scopes, body, status
):
    provider = _FarmActivityProvider(allowed_scopes=allowed_scopes)
    monkeypatch.setattr(operator_auth, "create_provider", lambda: provider)
    monkeypatch.setattr("services.gateway.audit.GatewayAudit.log", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        "services.gateway.audit.GatewayAudit.reserve_mutation",
        lambda _self: "test-reservation",
    )
    monkeypatch.setattr(
        "services.gateway.audit.GatewayAudit.release_mutation",
        lambda _self, _reservation: None,
    )
    editor = MagicMock()
    monkeypatch.setattr(
        "services.gateway.farm_activity_lifecycle.edit_farm_activity_draft",
        editor,
    )

    headers = {"X-CSRF-Token": "valid-csrf"} if csrf else {}
    with TestClient(create_app()) as client:
        _set_operator_cookies(client, csrf=csrf)
        response = client.patch(
            "/operator/api/farm-activities/33333333-3333-4333-8333-333333333333/draft",
            params={"location_id": LOCATION_ID},
            headers=headers,
            json=body,
        )

    assert response.status_code == status, response.text
    editor.assert_not_called()


def test_mobile_collection_queue_uses_location_scope_and_returns_no_store(monkeypatch):
    monkeypatch.setenv("KOKONUT_GATEWAY_CORS_ORIGINS", "https://operator.example")
    provider = _ReviewProvider(allowed_action="read")
    monkeypatch.setattr(operator_auth, "create_provider", lambda: provider)
    audit_records = []
    monkeypatch.setattr(
        "services.gateway.audit.GatewayAudit.log",
        lambda _self, **record: audit_records.append(record),
    )
    queue_record = {
        "id": "22222222-2222-4222-8222-222222222222",
        "location_id": LOCATION_ID,
        "form_id": "field_activity",
        "form_version": "2.1.0",
        "collection_type": "farm_activity",
        "collected_at": "2026-10-28T10:00:00+00:00",
        "synced_at": "2026-10-28T11:00:00+00:00",
        "form_validation_status": "active",
        "consent_validation_status": "granted",
        "form_review_required": True,
        "form_revision_id": "33333333-3333-4333-8333-333333333333",
        "form_name": "Field Activity",
        "form_revision_status": "active",
        "eligible_for_use": False,
        "eligibility_reason": "review_required",
        "review_state": "pending_review",
    }
    queue_reader = MagicMock(return_value=[queue_record])
    monkeypatch.setattr(
        "services.gateway.operator_mobile_review.list_mobile_collections",
        queue_reader,
    )

    with TestClient(create_app(), base_url="https://operator.example") as client:
        client.cookies.set(
            operator_auth.SESSION_COOKIE,
            "valid-session",
            path=operator_auth.SESSION_COOKIE_PATH,
        )
        response = client.get(
            "/operator/api/mobile-collection-review-queue",
            params={"location_id": LOCATION_ID, "limit": 7},
            headers={"Origin": "https://operator.example"},
        )

    assert response.status_code == 200, response.text
    assert response.headers["access-control-allow-origin"] == "https://operator.example"
    assert response.headers["access-control-allow-credentials"] == "true"
    assert response.headers["cache-control"] == "no-store"
    assert {value.strip() for value in response.headers["vary"].split(",")} == {"Cookie", "Origin"}
    assert response.json()["data"] == [queue_record]
    queue_reader.assert_called_once_with(OPERATOR_ID, LOCATION_ID, 7)
    assert provider.scopes_seen == [
        (OPERATOR_ID, "mobile_collection_review", "read", LOCATION_ID)
    ]
    assert audit_records[-1]["caller"] == f"operator:{OPERATOR_ID}"
    assert audit_records[-1]["location_id"] == LOCATION_ID


def test_mobile_operations_inventory_requires_both_grants_and_returns_no_store(monkeypatch):
    monkeypatch.setenv("KOKONUT_GATEWAY_CORS_ORIGINS", "https://operator.example")
    provider = _DispositionProvider(
        allowed_scopes={
            ("mobile_device", "read"),
            ("mobile_collection_review", "read"),
        }
    )
    monkeypatch.setattr(operator_auth, "create_provider", lambda: provider)
    monkeypatch.setattr(
        "services.gateway.audit.GatewayAudit.log",
        lambda *_args, **_kwargs: None,
    )
    inventory = {
        "location_id": LOCATION_ID,
        "devices": [
            {
                "device_id": "collector-7",
                "status": "active",
                "last_seen_at": "2026-10-28T10:00:00+00:00",
                "last_sync_at": "2026-10-28T09:00:00+00:00",
            }
        ],
        "queue_summary": {
            "device_count": 2,
            "active_device_count": 1,
            "pending_sync_count": 2,
            "synced_record_count": 8,
            "form_review_required_count": 3,
            "ineligible_synced_count": 1,
        },
    }
    reader = MagicMock(return_value=inventory)
    monkeypatch.setattr(
        "services.gateway.operator_mobile_review.get_mobile_operations_inventory",
        reader,
    )

    with TestClient(create_app(), base_url="https://operator.example") as client:
        _set_operator_cookies(client)
        response = client.get(
            f"/operator/api/mobile/locations/{LOCATION_ID}/inventory",
            params={"device_limit": 7},
            headers={"Origin": "https://operator.example"},
        )

    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["access-control-allow-credentials"] == "true"
    assert response.json() == inventory
    assert reader.call_args.args == (OPERATOR_ID, LOCATION_ID, 7)
    assert provider.scopes_seen == [
        (OPERATOR_ID, "mobile_device", "read", LOCATION_ID),
        (OPERATOR_ID, "mobile_collection_review", "read", LOCATION_ID),
    ]


def test_mobile_operations_inventory_denies_missing_secondary_grant_before_query(monkeypatch):
    provider = _DispositionProvider(
        allowed_scopes={("mobile_device", "read")}
    )
    monkeypatch.setattr(operator_auth, "create_provider", lambda: provider)
    monkeypatch.setattr(
        "services.gateway.audit.GatewayAudit.log",
        lambda *_args, **_kwargs: None,
    )
    reader = MagicMock()
    monkeypatch.setattr(
        "services.gateway.operator_mobile_review.get_mobile_operations_inventory",
        reader,
    )

    with TestClient(create_app()) as client:
        _set_operator_cookies(client)
        response = client.get(
            f"/operator/api/mobile/locations/{LOCATION_ID}/inventory"
        )

    assert response.status_code == 403
    assert response.headers["cache-control"] == "no-store"
    assert provider.scopes_seen == [
        (OPERATOR_ID, "mobile_device", "read", LOCATION_ID),
        (OPERATOR_ID, "mobile_collection_review", "read", LOCATION_ID),
    ]
    reader.assert_not_called()


def test_mobile_collection_detail_does_not_accept_list_read_grant(monkeypatch):
    provider = _ReviewProvider(allowed_action="read")
    monkeypatch.setattr(operator_auth, "create_provider", lambda: provider)
    monkeypatch.setattr(
        "services.gateway.audit.GatewayAudit.log",
        lambda *_args, **_kwargs: None,
    )
    detail_reader = MagicMock(return_value={"id": "unused"})
    monkeypatch.setattr(
        "services.gateway.operator_mobile_review.get_mobile_collection",
        detail_reader,
    )

    with TestClient(create_app()) as client:
        client.cookies.set(
            operator_auth.SESSION_COOKIE,
            "valid-session",
            path=operator_auth.SESSION_COOKIE_PATH,
        )
        response = client.get(
            "/operator/api/mobile-collection-review-queue/22222222-2222-4222-8222-222222222222",
            params={"location_id": LOCATION_ID},
        )

    assert response.status_code == 403
    assert provider.scopes_seen == [
        (OPERATOR_ID, "mobile_collection_review", "read_detail", LOCATION_ID)
    ]
    detail_reader.assert_not_called()


def test_mobile_collection_detail_uses_separate_grant_and_is_audited(monkeypatch):
    provider = _ReviewProvider(allowed_action="read_detail")
    monkeypatch.setattr(operator_auth, "create_provider", lambda: provider)
    audit_records = []
    monkeypatch.setattr(
        "services.gateway.audit.GatewayAudit.log",
        lambda _self, **record: audit_records.append(record),
    )
    detail_reader = MagicMock(
        return_value={
            "id": "22222222-2222-4222-8222-222222222222",
            "location_id": LOCATION_ID,
            "form_id": "field_activity",
            "form_version": "2.1.0",
            "collection_type": "farm_activity",
            "collected_at": "2026-10-29T12:00:00+00:00",
            "synced_at": "2026-10-29T12:01:00+00:00",
            "form_validation_status": "active",
            "consent_validation_status": "granted",
            "form_review_required": True,
            "form_revision_id": None,
            "form_name": None,
            "form_revision_status": None,
            "consent_policy_status": "required",
            "eligible_for_use": False,
            "eligibility_reason": "review_required",
            "review_state": "pending_review",
            "photo_count": 0,
            "payload": {"note": "private"},
            "review_events": [],
        }
    )
    monkeypatch.setattr(
        "services.gateway.operator_mobile_review.get_mobile_collection",
        detail_reader,
    )

    with TestClient(create_app()) as client:
        client.cookies.set(
            operator_auth.SESSION_COOKIE,
            "valid-session",
            path=operator_auth.SESSION_COOKIE_PATH,
        )
        response = client.get(
            "/operator/api/mobile-collection-review-queue/22222222-2222-4222-8222-222222222222",
            params={"location_id": LOCATION_ID},
        )

    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["data"]["payload"] == {"note": "private"}
    detail_reader.assert_called_once_with(
        OPERATOR_ID,
        "22222222-2222-4222-8222-222222222222",
        LOCATION_ID,
    )
    assert provider.scopes_seen == [
        (OPERATOR_ID, "mobile_collection_review", "read_detail", LOCATION_ID)
    ]
    assert audit_records[-1]["caller"] == f"operator:{OPERATOR_ID}"
    assert audit_records[-1]["location_id"] == LOCATION_ID


def test_mobile_disposition_inventory_requires_both_grants_and_is_audited(monkeypatch):
    monkeypatch.setenv("KOKONUT_GATEWAY_CORS_ORIGINS", "https://operator.example")
    provider = _DispositionProvider(
        allowed_scopes={
            ("mobile_collection_retention", "inventory"),
            ("mobile_collection_review", "read"),
        }
    )
    monkeypatch.setattr(operator_auth, "create_provider", lambda: provider)
    audit_records = []
    monkeypatch.setattr(
        "services.gateway.audit.GatewayAudit.log",
        lambda _self, **record: audit_records.append(record),
    )
    reader = MagicMock(
        return_value={
            "collection_id": "22222222-2222-4222-8222-222222222222",
            "inventory_scope": "known_direct_lineage_only",
        }
    )
    monkeypatch.setattr(
        "services.gateway.operator_mobile_review.get_mobile_collection_disposition_inventory",
        reader,
    )

    with TestClient(create_app(), base_url="https://operator.example") as client:
        client.cookies.set(
            operator_auth.SESSION_COOKIE,
            "valid-session",
            path=operator_auth.SESSION_COOKIE_PATH,
        )
        response = client.get(
            "/operator/api/mobile-collection-review-queue/"
            "22222222-2222-4222-8222-222222222222/disposition-inventory",
            params={"location_id": LOCATION_ID},
            headers={"Origin": "https://operator.example"},
        )

    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    assert {value.strip() for value in response.headers["vary"].split(",")} == {"Cookie", "Origin"}
    assert response.json()["data"]["inventory_scope"] == "known_direct_lineage_only"
    assert provider.scopes_seen == [
        (OPERATOR_ID, "mobile_collection_retention", "inventory", LOCATION_ID),
        (OPERATOR_ID, "mobile_collection_review", "read", LOCATION_ID),
    ]
    reader.assert_called_once_with(
        OPERATOR_ID,
        "22222222-2222-4222-8222-222222222222",
        LOCATION_ID,
    )
    assert audit_records[-1]["caller"] == f"operator:{OPERATOR_ID}"
    assert audit_records[-1]["location_id"] == LOCATION_ID


def test_mobile_disposition_inventory_denies_when_grants_resolve_to_different_tenants(
    monkeypatch,
):
    from services.common.tenant_context import TenantContextDenied

    provider = _DispositionProvider(
        allowed_scopes={
            ("mobile_collection_retention", "inventory"),
            ("mobile_collection_review", "read"),
        }
    )
    monkeypatch.setattr(operator_auth, "create_provider", lambda: provider)
    monkeypatch.setattr(
        "services.gateway.audit.GatewayAudit.log",
        lambda *_args, **_kwargs: None,
    )
    reader = MagicMock(
        side_effect=TenantContextDenied("required grants resolve to different tenants")
    )
    monkeypatch.setattr(
        "services.gateway.operator_mobile_review.get_mobile_collection_disposition_inventory",
        reader,
    )

    with TestClient(create_app()) as client:
        _set_operator_cookies(client)
        response = client.get(
            "/operator/api/mobile-collection-review-queue/"
            "22222222-2222-4222-8222-222222222222/disposition-inventory",
            params={"location_id": LOCATION_ID},
        )

    assert response.status_code == 403
    assert response.json() == {
        "error": "Tenant-qualified operator access is required"
    }
    assert response.headers["cache-control"] == "no-store"
    reader.assert_called_once()


@pytest.mark.parametrize(
    "allowed_scopes",
    [
        {("mobile_collection_retention", "inventory")},
        {("mobile_collection_review", "read")},
    ],
)
def test_mobile_disposition_inventory_denies_when_either_grant_is_missing(
    monkeypatch, allowed_scopes
):
    provider = _DispositionProvider(allowed_scopes=allowed_scopes)
    monkeypatch.setattr(operator_auth, "create_provider", lambda: provider)
    monkeypatch.setattr("services.gateway.audit.GatewayAudit.log", lambda *_args, **_kwargs: None)
    reader = MagicMock()
    monkeypatch.setattr(
        "services.gateway.operator_mobile_review.get_mobile_collection_disposition_inventory",
        reader,
    )

    with TestClient(create_app()) as client:
        client.cookies.set(
            operator_auth.SESSION_COOKIE,
            "valid-session",
            path=operator_auth.SESSION_COOKIE_PATH,
        )
        response = client.get(
            "/operator/api/mobile-collection-review-queue/"
            "22222222-2222-4222-8222-222222222222/disposition-inventory",
            params={"location_id": LOCATION_ID},
        )

    assert response.status_code == 403
    reader.assert_not_called()


def test_mobile_review_event_requires_detail_grant_and_csrf(monkeypatch):
    provider = _ReviewProvider(allowed_actions={"review"})
    monkeypatch.setattr(operator_auth, "create_provider", lambda: provider)
    monkeypatch.setattr(
        "services.gateway.audit.GatewayAudit.log",
        lambda *_args, **_kwargs: None,
    )
    event_writer = MagicMock(return_value={"id": "event-id"})
    monkeypatch.setattr(
        "services.gateway.operator_mobile_review.record_mobile_review_event",
        event_writer,
    )

    with TestClient(create_app()) as client:
        client.cookies.set(
            operator_auth.SESSION_COOKIE,
            "valid-session",
            path=operator_auth.SESSION_COOKIE_PATH,
        )
        response = client.post(
            "/operator/api/mobile-collection-review-queue/22222222-2222-4222-8222-222222222222/events",
            params={"location_id": LOCATION_ID},
            json={
                "decision": "reviewed",
                "reason": "Checked the evidence.",
                "evidence": [{"source": "field-review", "basis": "Observed the submitted entry."}],
            },
        )

    assert response.status_code == 403
    assert provider.scopes_seen == [
        (OPERATOR_ID, "mobile_collection_review", "review", LOCATION_ID),
        (OPERATOR_ID, "mobile_collection_review", "read_detail", LOCATION_ID),
    ]
    event_writer.assert_not_called()


def test_mobile_review_event_route_requires_csrf_and_returns_no_store(monkeypatch):
    provider = _ReviewProvider(allowed_actions={"review", "read_detail"})
    monkeypatch.setattr(operator_auth, "create_provider", lambda: provider)
    audit_records = []
    monkeypatch.setattr(
        "services.gateway.audit.GatewayAudit.log",
        lambda _self, **record: audit_records.append(record),
    )
    monkeypatch.setattr(
        "services.gateway.audit.GatewayAudit.reserve_mutation",
        lambda _self: "test-reservation",
    )
    monkeypatch.setattr(
        "services.gateway.audit.GatewayAudit.release_mutation",
        lambda _self, _reservation: None,
    )
    event_writer = MagicMock(return_value={"id": "event-id", "decision": "reviewed"})
    monkeypatch.setattr(
        "services.gateway.operator_mobile_review.record_mobile_review_event",
        event_writer,
    )

    with TestClient(create_app()) as client:
        client.cookies.set(
            operator_auth.SESSION_COOKIE,
            "valid-session",
            path=operator_auth.SESSION_COOKIE_PATH,
        )
        client.cookies.set(
            operator_auth.CSRF_COOKIE,
            "valid-csrf",
            path=operator_auth.SESSION_COOKIE_PATH,
        )
        response = client.post(
            "/operator/api/mobile-collection-review-queue/22222222-2222-4222-8222-222222222222/events",
            params={"location_id": LOCATION_ID},
            headers={"X-CSRF-Token": "valid-csrf"},
            json={
                "decision": "reviewed",
                "reason": "Checked the evidence.",
                "evidence": [{"source": "field-review", "basis": "Observed the submitted entry."}],
            },
        )

    assert response.status_code == 201, response.text
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["data"]["id"] == "event-id"
    event_writer.assert_called_once()
    assert audit_records[-1]["caller"] == f"operator:{OPERATOR_ID}"
    assert audit_records[-1]["location_id"] == LOCATION_ID


def test_mobile_review_event_route_denies_cross_tenant_context(monkeypatch):
    from services.common.tenant_context import TenantContextDenied

    provider = _ReviewProvider(allowed_actions={"review", "read_detail"})
    monkeypatch.setattr(operator_auth, "create_provider", lambda: provider)
    monkeypatch.setattr(
        "services.gateway.audit.GatewayAudit.log",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        "services.gateway.audit.GatewayAudit.reserve_mutation",
        lambda _self: "test-reservation",
    )
    monkeypatch.setattr(
        "services.gateway.audit.GatewayAudit.release_mutation",
        lambda *_args: None,
    )
    event_writer = MagicMock(
        side_effect=TenantContextDenied(
            "required tenant-qualified grants resolve to different tenants"
        )
    )
    monkeypatch.setattr(
        "services.gateway.operator_mobile_review.record_mobile_review_event",
        event_writer,
    )

    with TestClient(create_app()) as client:
        client.cookies.set(
            operator_auth.SESSION_COOKIE,
            "valid-session",
            path=operator_auth.SESSION_COOKIE_PATH,
        )
        client.cookies.set(
            operator_auth.CSRF_COOKIE,
            "valid-csrf",
            path=operator_auth.SESSION_COOKIE_PATH,
        )
        response = client.post(
            "/operator/api/mobile-collection-review-queue/22222222-2222-4222-8222-222222222222/events",
            params={"location_id": LOCATION_ID},
            headers={"X-CSRF-Token": "valid-csrf"},
            json={
                "decision": "reviewed",
                "reason": "Checked the evidence.",
                "evidence": [{"source": "field-review", "basis": "Observed the submitted entry."}],
            },
        )

    assert response.status_code == 403
    assert response.headers["cache-control"] == "no-store"
    assert "Cookie" in {value.strip() for value in response.headers["vary"].split(",")}
    event_writer.assert_called_once()


@pytest.mark.parametrize(
    ("session", "scope", "csrf", "status"),
    [
        (False, True, True, 401),
        (True, False, True, 403),
        (True, True, False, 403),
        (True, True, True, 201),
    ],
)
def test_oidc_operator_can_issue_enrollment_only_with_session_scope_and_csrf(
    monkeypatch, session, scope, csrf, status
):
    provider = _FakeProvider(allowed=scope)
    monkeypatch.setattr(operator_auth, "create_provider", lambda: provider)
    connection = MagicMock()
    cursor = connection.cursor.return_value
    cursor.fetchone.return_value = (
        "33333333-3333-4333-8333-333333333333",
        "2030-01-01T00:00:00+00:00",
    )
    monkeypatch.setattr("services.mobile.api.get_db", lambda: connection)
    context_calls = []
    monkeypatch.setattr(
        "services.mobile.api.set_operator_tenant_context",
        lambda conn, **kwargs: context_calls.append((conn, kwargs)),
    )
    audit_records = []
    monkeypatch.setattr(
        "services.gateway.audit.GatewayAudit.reserve_mutation",
        lambda _self: "test-reservation",
    )
    monkeypatch.setattr(
        "services.gateway.audit.GatewayAudit.release_mutation",
        lambda _self, _reservation: None,
    )
    monkeypatch.setattr(
        "services.gateway.audit.GatewayAudit.log",
        lambda _self, **record: audit_records.append(record),
    )

    headers = {}
    with TestClient(create_app()) as client:
        if session:
            client.cookies.set(
                operator_auth.SESSION_COOKIE,
                "valid-session",
                path=operator_auth.SESSION_COOKIE_PATH,
            )
        if csrf:
            client.cookies.set(
                operator_auth.CSRF_COOKIE,
                "valid-csrf",
                path=operator_auth.SESSION_COOKIE_PATH,
            )
            headers["X-CSRF-Token"] = "valid-csrf"
        response = client.post(
            f"/operator/api/mobile/locations/{LOCATION_ID}/enrollments",
            headers=headers,
            json={"user_id": "collector-17", "expires_in_minutes": 60},
        )

    assert response.status_code == status, response.text
    if status == 201:
        assert response.headers["cache-control"] == "no-store"
        assert len(response.json()["enrollment_code"]) >= 32
        assert cursor.execute.call_args.args[1][1:5] == (
            "collector-17",
            LOCATION_ID,
            "33333333-3333-4333-8333-333333333333",
            f"operator:{OPERATOR_ID}",
        )
        assert context_calls == [
            (
                connection,
                {
                    "operator_id": OPERATOR_ID,
                    "location_id": LOCATION_ID,
                    "resource": "mobile_device",
                    "action": "enroll",
                },
            )
        ]
        connection.commit.assert_called_once()
        assert audit_records[-1]["caller"] == f"operator:{OPERATOR_ID}"
        assert audit_records[-1]["location_id"] == LOCATION_ID
    else:
        connection.cursor.assert_not_called()
        connection.commit.assert_not_called()


@pytest.mark.parametrize(
    ("method", "path", "action", "body", "row"),
    [
        (
            "POST",
            f"/operator/api/mobile/locations/{LOCATION_ID}/enrollments",
            "enroll",
            {"user_id": "collector-17", "expires_in_minutes": 60},
            ("33333333-3333-4333-8333-333333333333", "2030-01-01T00:00:00+00:00"),
        ),
        (
            "DELETE",
            f"/operator/api/mobile/locations/{LOCATION_ID}/enrollments/22222222-2222-4222-8222-222222222222",
            "revoke",
            None,
            ("22222222-2222-4222-8222-222222222222",),
        ),
        (
            "POST",
            f"/operator/api/mobile/locations/{LOCATION_ID}/devices/collector-17/revoke",
            "revoke",
            None,
            ("revoked", "collector-17"),
        ),
    ],
)
def test_operator_mobile_mutations_set_tenant_context(
    monkeypatch, method, path, action, body, row
):
    provider = _MobileDeviceProvider(allowed_actions={action})
    monkeypatch.setattr(operator_auth, "create_provider", lambda: provider)
    connection = MagicMock()
    connection.cursor.return_value.fetchone.return_value = row
    monkeypatch.setattr("services.mobile.api.get_db", lambda: connection)
    context_calls = []
    monkeypatch.setattr(
        "services.mobile.api.set_operator_tenant_context",
        lambda conn, **kwargs: context_calls.append((conn, kwargs)),
    )
    monkeypatch.setattr(
        "services.gateway.audit.GatewayAudit.reserve_mutation",
        lambda _self: "test-reservation",
    )
    monkeypatch.setattr(
        "services.gateway.audit.GatewayAudit.release_mutation",
        lambda *_args: None,
    )
    monkeypatch.setattr(
        "services.gateway.audit.GatewayAudit.log",
        lambda *_args, **_kwargs: None,
    )

    with TestClient(create_app()) as client:
        _set_operator_cookies(client, csrf=True)
        response = client.request(
            method,
            path,
            headers={"X-CSRF-Token": "valid-csrf"},
            json=body,
        )

    assert response.status_code == (201 if action == "enroll" else 200), response.text
    assert context_calls == [
        (
            connection,
            {
                "operator_id": OPERATOR_ID,
                "location_id": LOCATION_ID,
                "resource": "mobile_device",
                "action": action,
            },
        )
    ]
    if "/devices/" in path:
        assert "kokonut_security.revoke_mobile_device" in connection.cursor.return_value.execute.call_args.args[0]
        assert connection.cursor.return_value.execute.call_args.args[1] == (
            LOCATION_ID,
            "collector-17",
            None,
            None,
            OPERATOR_ID,
            "a" * 64,
        )
    assert connection.commit.call_count == 1


@pytest.mark.parametrize(
    ("method", "path", "action", "body"),
    [
        (
            "POST",
            f"/operator/api/mobile/locations/{LOCATION_ID}/enrollments",
            "enroll",
            {"user_id": "collector-17", "expires_in_minutes": 60},
        ),
        (
            "DELETE",
            f"/operator/api/mobile/locations/{LOCATION_ID}/enrollments/22222222-2222-4222-8222-222222222222",
            "revoke",
            None,
        ),
        (
            "POST",
            f"/operator/api/mobile/locations/{LOCATION_ID}/devices/collector-17/revoke",
            "revoke",
            None,
        ),
    ],
)
def test_operator_mobile_mutations_deny_unverified_tenant_context(
    monkeypatch, method, path, action, body
):
    from services.common.tenant_context import TenantContextDenied

    provider = _MobileDeviceProvider(allowed_actions={action})
    monkeypatch.setattr(operator_auth, "create_provider", lambda: provider)
    connection = MagicMock()
    monkeypatch.setattr("services.mobile.api.get_db", lambda: connection)
    monkeypatch.setattr(
        "services.mobile.api.set_operator_tenant_context",
        MagicMock(side_effect=TenantContextDenied("tenant-qualified grant required")),
    )
    monkeypatch.setattr(
        "services.gateway.audit.GatewayAudit.reserve_mutation",
        lambda _self: "test-reservation",
    )
    monkeypatch.setattr(
        "services.gateway.audit.GatewayAudit.release_mutation",
        lambda *_args: None,
    )
    monkeypatch.setattr(
        "services.gateway.audit.GatewayAudit.log",
        lambda *_args, **_kwargs: None,
    )

    with TestClient(create_app()) as client:
        _set_operator_cookies(client, csrf=True)
        response = client.request(
            method,
            path,
            headers={"X-CSRF-Token": "valid-csrf"},
            json=body,
        )

    assert response.status_code == 403
    assert response.headers["cache-control"] == "no-store"
    assert "Cookie" in response.headers["vary"]
    connection.commit.assert_not_called()
