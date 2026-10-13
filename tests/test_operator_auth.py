"""OIDC operator authorization for Field Collector administration."""

from dataclasses import dataclass
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

pytest.importorskip("fastapi")
from starlette.testclient import TestClient  # noqa: E402

from services.gateway import operator_auth  # noqa: E402
from services.gateway.app import create_app  # noqa: E402

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
    assert draft_policy["additional_scopes"] == detail_policy["additional_scopes"]
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


def test_farm_activity_intake_queue_uses_scoped_operator_and_no_store(monkeypatch):
    provider = _FarmActivityProvider(allowed_scopes={("farm_activity", "read")})
    monkeypatch.setattr(operator_auth, "create_provider", lambda: provider)
    monkeypatch.setattr("services.gateway.audit.GatewayAudit.log", lambda *_args, **_kwargs: None)
    queue_reader = MagicMock(return_value=[{"id": "collection-id", "activity_type": "weeding"}])
    monkeypatch.setattr(
        "services.gateway.farm_activity_workflow.list_farm_activity_intake",
        queue_reader,
    )

    with TestClient(create_app()) as client:
        _set_operator_cookies(client)
        response = client.get(
            "/operator/api/farm-activity-intake-queue",
            params={"location_id": LOCATION_ID, "limit": 9},
        )

    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert response.json()["data"] == [{"id": "collection-id", "activity_type": "weeding"}]
    queue_reader.assert_called_once_with(OPERATOR_ID, LOCATION_ID, 9)
    assert provider.scopes_seen == [(OPERATOR_ID, "farm_activity", "read", LOCATION_ID)]


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
    ("csrf", "content_reviewed", "status"),
    [(False, True, 403), (True, False, 422), (True, True, 201)],
)
def test_farm_activity_draft_route_requires_scope_csrf_and_review_acknowledgement(
    monkeypatch, csrf, content_reviewed, status
):
    provider = _FarmActivityProvider(
        allowed_scopes={
            ("farm_activity", "create_draft"),
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
    with TestClient(create_app()) as client:
        _set_operator_cookies(client, csrf=True)
        response = client.patch(
            path,
            params={"location_id": LOCATION_ID},
            headers={"X-CSRF-Token": "valid-csrf"},
            json={
                "content": {"activity_type": "planting"},
                "reason": "Corrected after review",
            },
        )

    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
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
    provider = _ReviewProvider(allowed_action="read")
    monkeypatch.setattr(operator_auth, "create_provider", lambda: provider)
    audit_records = []
    monkeypatch.setattr(
        "services.gateway.audit.GatewayAudit.log",
        lambda _self, **record: audit_records.append(record),
    )
    queue_reader = MagicMock(return_value=[{"id": "collection-id", "payload": None}])
    monkeypatch.setattr(
        "services.gateway.operator_mobile_review.list_mobile_collections",
        queue_reader,
    )

    with TestClient(create_app()) as client:
        client.cookies.set(
            operator_auth.SESSION_COOKIE,
            "valid-session",
            path=operator_auth.SESSION_COOKIE_PATH,
        )
        response = client.get(
            "/operator/api/mobile-collection-review-queue",
            params={"location_id": LOCATION_ID, "limit": 7},
        )

    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert response.json()["data"] == [{"id": "collection-id", "payload": None}]
    queue_reader.assert_called_once_with(OPERATOR_ID, LOCATION_ID, 7)
    assert provider.scopes_seen == [
        (OPERATOR_ID, "mobile_collection_review", "read", LOCATION_ID)
    ]
    assert audit_records[-1]["caller"] == f"operator:{OPERATOR_ID}"
    assert audit_records[-1]["location_id"] == LOCATION_ID


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
    detail_reader = MagicMock(return_value={"id": "collection-id", "payload": {"note": "private"}})
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

    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
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
        assert cursor.execute.call_args.args[1][1:4] == (
            "collector-17",
            LOCATION_ID,
            f"operator:{OPERATOR_ID}",
        )
        connection.commit.assert_called_once()
        assert audit_records[-1]["caller"] == f"operator:{OPERATOR_ID}"
        assert audit_records[-1]["location_id"] == LOCATION_ID
    else:
        connection.cursor.assert_not_called()
        connection.commit.assert_not_called()
