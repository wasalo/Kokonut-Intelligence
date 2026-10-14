"""Keep registered operator routes aligned with their OIDC auth policies."""

from functools import reduce
from types import SimpleNamespace

import pytest

pytest.importorskip("fastapi")
from starlette.testclient import TestClient  # noqa: E402

from services.gateway.app import create_app  # noqa: E402
from services.gateway.operator_auth import (  # noqa: E402
    auth_route_policy,
    create_auth_router,
)

_LOCATION_ID = "11111111-1111-4111-8111-111111111111"
_PARAMETER_SAMPLES = {
    "location_id": _LOCATION_ID,
    "enrollment_id": "22222222-2222-4222-8222-222222222222",
    "report_id": "33333333-3333-4333-8333-333333333333",
    "collection_id": "44444444-4444-4444-8444-444444444444",
    "activity_id": "55555555-5555-4555-8555-555555555555",
    "device_id": "collector-1",
}
_TRANSITION_ACTIONS = {
    "submit": "submit",
    "verify": "verify",
    "reject": "reject",
    "request-rework": "rework",
    "publish": "publish",
    "close-exception": "close_exception",
}


def _expected(
    resource,
    action,
    *,
    public=False,
    scoped=False,
    location_id=None,
    additional=(),
):
    return resource, action, public, scoped, location_id, tuple(sorted(additional))


_EXPECTED_OPERATOR_POLICIES = {
    ("GET", "/operator/"): _expected("operator_auth", "console", public=True),
    ("GET", "/operator/auth/login"): _expected("operator_auth", "login", public=True),
    ("GET", "/operator/auth/callback"): _expected("operator_auth", "callback", public=True),
    ("GET", "/operator/auth/session"): _expected("operator_auth", "read"),
    ("POST", "/operator/auth/logout"): _expected("operator_auth", "logout"),
    ("GET", "/operator/api/report-review-queue"): _expected("report_snapshot_review", "read", scoped=True),
    (
        "GET",
        "/operator/api/report-review-queue/33333333-3333-4333-8333-333333333333",
    ): _expected("report_snapshot_review", "read", scoped=True),
    ("GET", "/operator/api/mobile-collection-review-queue"): _expected("mobile_collection_review", "read", scoped=True),
    (
        "GET",
        "/operator/api/mobile-collection-review-queue/44444444-4444-4444-8444-444444444444",
    ): _expected("mobile_collection_review", "read_detail", scoped=True),
    (
        "GET",
        "/operator/api/mobile-collection-review-queue/44444444-4444-4444-8444-444444444444/disposition-inventory",
    ): _expected(
        "mobile_collection_retention",
        "inventory",
        scoped=True,
        additional=(("mobile_collection_review", "read"),),
    ),
    (
        "POST",
        "/operator/api/mobile-collection-review-queue/44444444-4444-4444-8444-444444444444/events",
    ): _expected(
        "mobile_collection_review",
        "review",
        scoped=True,
        additional=(("mobile_collection_review", "read_detail"),),
    ),
    ("GET", "/operator/api/farm-activity-intake-queue"): _expected("farm_activity", "read", scoped=True),
    (
        "GET",
        "/operator/api/farm-activity-intake-queue/44444444-4444-4444-8444-444444444444",
    ): _expected(
        "farm_activity",
        "read_detail",
        scoped=True,
        additional=(("mobile_collection_review", "read_detail"),),
    ),
    (
        "POST",
        "/operator/api/farm-activity-intake-queue/44444444-4444-4444-8444-444444444444/draft",
    ): _expected(
        "farm_activity",
        "create_draft",
        scoped=True,
        additional=(
            ("farm_activity", "read_detail"),
            ("mobile_collection_review", "read_detail"),
        ),
    ),
    ("GET", "/operator/api/farm-activities"): _expected("farm_activity", "read", scoped=True),
    (
        "GET",
        "/operator/api/farm-activities/55555555-5555-4555-8555-555555555555",
    ): _expected(
        "farm_activity",
        "read_detail",
        scoped=True,
        additional=(("mobile_collection_review", "read_detail"),),
    ),
    (
        "PATCH",
        "/operator/api/farm-activities/55555555-5555-4555-8555-555555555555/draft",
    ): _expected(
        "farm_activity",
        "edit_draft",
        scoped=True,
        additional=(
            ("farm_activity", "read_detail"),
            ("mobile_collection_review", "read_detail"),
        ),
    ),
    (
        "POST",
        "/operator/api/mobile/locations/11111111-1111-4111-8111-111111111111/participants",
    ): _expected("mobile_participant", "create", scoped=True, location_id=_LOCATION_ID),
    (
        "POST",
        "/operator/api/mobile/locations/11111111-1111-4111-8111-111111111111/participants/revoke",
    ): _expected("mobile_participant", "revoke", scoped=True, location_id=_LOCATION_ID),
    (
        "POST",
        "/operator/api/mobile/locations/11111111-1111-4111-8111-111111111111/enrollments",
    ): _expected("mobile_device", "enroll", scoped=True, location_id=_LOCATION_ID),
    (
        "DELETE",
        "/operator/api/mobile/locations/11111111-1111-4111-8111-111111111111/enrollments/22222222-2222-4222-8222-222222222222",
    ): _expected("mobile_device", "revoke", scoped=True, location_id=_LOCATION_ID),
    (
        "POST",
        "/operator/api/mobile/locations/11111111-1111-4111-8111-111111111111/devices/collector-1/revoke",
    ): _expected("mobile_device", "revoke", scoped=True, location_id=_LOCATION_ID),
}
for _route_action, _policy_action in _TRANSITION_ACTIONS.items():
    _EXPECTED_OPERATOR_POLICIES[
        (
            "POST",
            f"/operator/api/farm-activities/55555555-5555-4555-8555-555555555555/{_route_action}",
        )
    ] = _expected("farm_activity", _policy_action, scoped=True)


def _concrete_paths(route_path):
    path = reduce(
        lambda current, item: current.replace("{" + item[0] + "}", item[1]),
        _PARAMETER_SAMPLES.items(),
        route_path,
    )
    if "{action}" in path:
        return [path.replace("{action}", action) for action in _TRANSITION_ACTIONS]
    return [path]


def test_registered_operator_routes_have_exact_reviewed_policy_coverage():
    provider = SimpleNamespace(settings=SimpleNamespace(state_secret="test-state-secret-with-at-least-32-bytes"))
    router = create_auth_router(provider)
    actual = {}

    for route in router.routes:
        for method in route.methods or ():
            for path in _concrete_paths(route.path):
                policy = auth_route_policy(method, path, enabled=True)
                assert policy is not None, (method, route.path, path)
                assert policy["operator_auth"] is True
                additional = tuple(
                    sorted((scope["resource"], scope["action"]) for scope in policy.get("additional_scopes", ()))
                )
                actual[(method, path)] = (
                    policy["resource"],
                    policy["action"],
                    policy["public"],
                    policy["scope_required"],
                    policy["location_id"],
                    additional,
                )

    assert actual == _EXPECTED_OPERATOR_POLICIES


def test_unknown_operator_path_and_method_are_protected(tmp_path, monkeypatch):
    monkeypatch.setenv("KOKONUT_GATEWAY_AUDIT_SPOOL_PATH", str(tmp_path / "gateway-audit.sqlite3"))
    monkeypatch.setenv("KOKONUT_API_KEYS", "")
    monkeypatch.setenv("KOKONUT_API_KEY_SCOPES", "")
    monkeypatch.setenv("KOKONUT_OPERATOR_OIDC_ENABLED", "false")

    with TestClient(create_app()) as client:
        unknown = client.get("/operator/api/not-registered")
        wrong_method = client.post("/operator/")

    assert unknown.status_code == 401
    assert wrong_method.status_code == 401
