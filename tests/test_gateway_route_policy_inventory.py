"""Keep registered Gateway routes aligned with their reviewed auth policies."""

import re

import pytest

pytest.importorskip("fastapi")
from starlette.testclient import TestClient  # noqa: E402

from services.gateway.app import create_app  # noqa: E402
from services.gateway.router import get_route_policy  # noqa: E402
from services.gateway.router import router as gateway_router
from services.mobile.api import router as mobile_router  # noqa: E402

_LOCATION_ID = "11111111-1111-4111-8111-111111111111"
_PARAMETER_SAMPLES = {
    "location_id": _LOCATION_ID,
    "enrollment_id": "22222222-2222-4222-8222-222222222222",
    "device_id": "collector-1",
}

# These are the complete `/api` routes owned by the native and Field Collector
# routers. Additions require an explicit, reviewed resource/action/public tuple.
_EXPECTED_ROUTE_POLICIES = {
    ("GET", "/api/locations"): ("location", "read", True),
    ("GET", "/api/locations/{location_id}"): ("location", "read", True),
    ("GET", "/api/v1/locations"): ("location", "read", True),
    ("GET", "/api/v1/locations/{location_id}"): ("location", "read", True),
    ("GET", "/api/metrics/{location_id}"): ("metric", "read", True),
    ("GET", "/api/crisp/{location_id}"): ("crisp_risk_assessment", "read", True),
    ("GET", "/api/analytics/{location_id}/summary"): ("analytics", "read", True),
    ("GET", "/api/v1/metrics/{location_id}"): ("metric", "read", True),
    ("GET", "/api/v1/crisp/{location_id}"): ("crisp_risk_assessment", "read", True),
    ("GET", "/api/v1/analytics/{location_id}/summary"): ("analytics", "read", True),
    ("POST", "/api/data-stream/post"): ("data_stream_post", "create", False),
    ("GET", "/api/iri/resolve"): ("iri", "read", True),
    ("GET", "/api/federation/nodes"): ("federation_node", "read", True),
    ("GET", "/api/drivers"): ("driver", "read", True),
    ("GET", "/api/health/services"): ("service_health", "read", True),
    ("GET", "/api/mobile/app"): ("mobile_app", "read", True),
    ("GET", "/api/mobile/field-collector-vault.js"): ("mobile_app", "read", True),
    ("GET", "/api/mobile/field-collector-service-worker.js"): ("mobile_app", "read", True),
    ("POST", "/api/mobile/media/uploads"): ("mobile_media", "upload", True),
    ("GET", "/api/mobile/forms"): ("mobile_form", "read", True),
    ("POST", "/api/mobile/locations/{location_id}/participants"): ("mobile_participant", "create", False),
    ("POST", "/api/mobile/locations/{location_id}/participants/revoke"): ("mobile_participant", "revoke", False),
    ("POST", "/api/mobile/locations/{location_id}/enrollments"): ("mobile_device", "enroll", False),
    ("POST", "/api/mobile/register"): ("mobile_device", "register", True),
    ("DELETE", "/api/mobile/locations/{location_id}/enrollments/{enrollment_id}"): ("mobile_device", "revoke", False),
    ("POST", "/api/mobile/locations/{location_id}/devices/{device_id}/revoke"): ("mobile_device", "revoke", False),
    ("POST", "/api/mobile/sync"): ("offline_collection", "write", True),
    ("GET", "/api/mobile/sync/status"): ("offline_collection", "read", True),
}


def _concrete_path(path: str) -> str:
    return re.sub(
        r"\{([^{}]+)\}",
        lambda match: _PARAMETER_SAMPLES[match.group(1)],
        path,
    )


def test_registered_api_routes_have_exact_reviewed_policy_coverage():
    actual = {}
    for router in (gateway_router, mobile_router):
        for route in router.routes:
            for method in route.methods or ():
                path = "/api" + route.path
                policy = get_route_policy(method, _concrete_path(path))
                actual[(method, path)] = (
                    policy["resource"],
                    policy["action"],
                    policy["public"],
                )
                if "{location_id}" in path:
                    assert policy["location_id"] == _LOCATION_ID

    assert actual == _EXPECTED_ROUTE_POLICIES


def test_registered_private_api_routes_reject_anonymous_requests(tmp_path, monkeypatch):
    monkeypatch.setenv(
        "KOKONUT_GATEWAY_AUDIT_SPOOL_PATH",
        str(tmp_path / "gateway-audit.sqlite3"),
    )
    monkeypatch.setenv("KOKONUT_API_KEYS", "")
    monkeypatch.setenv("KOKONUT_API_KEY_SCOPES", "")
    monkeypatch.setenv("KOKONUT_OPERATOR_OIDC_ENABLED", "false")

    private_routes = []
    with TestClient(create_app()) as client:
        for route in (gateway_router, mobile_router):
            for registered_route in route.routes:
                for method in registered_route.methods or ():
                    path = "/api" + registered_route.path
                    concrete_path = _concrete_path(path)
                    policy = get_route_policy(method, concrete_path)
                    if policy["public"]:
                        continue
                    body = {"location_id": _LOCATION_ID} if path == "/api/data-stream/post" else None
                    response = client.request(method, concrete_path, json=body)
                    private_routes.append((method, concrete_path, response.status_code))

    assert private_routes
    assert all(status_code == 401 for _, _, status_code in private_routes), private_routes


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/not-registered"),
        ("POST", "/api/v1/locations"),
        ("GET", f"/api/v1/locations/{_LOCATION_ID}/extra"),
    ],
)
def test_unknown_path_or_method_stays_protected(method, path, tmp_path, monkeypatch):
    monkeypatch.setenv(
        "KOKONUT_GATEWAY_AUDIT_SPOOL_PATH",
        str(tmp_path / "gateway-audit.sqlite3"),
    )
    monkeypatch.setenv("KOKONUT_API_KEYS", "")
    monkeypatch.setenv("KOKONUT_API_KEY_SCOPES", "")
    monkeypatch.setenv("KOKONUT_OPERATOR_OIDC_ENABLED", "false")

    with TestClient(create_app()) as client:
        response = client.request(method, path)

    assert response.status_code == 401
