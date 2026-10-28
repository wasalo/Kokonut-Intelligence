"""Keep registered Gateway routes aligned with their reviewed auth policies."""

import asyncio
import re
from types import SimpleNamespace
from unittest.mock import patch

import pytest

pytest.importorskip("fastapi")
from fastapi import APIRouter  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

from services.gateway.app import (
    _request_location,  # noqa: E402
    create_app,  # noqa: E402
)
from services.gateway.delphi_participant_routes import (  # noqa: E402
    register_delphi_participant_routes,
)
from services.gateway.router import get_route_policy  # noqa: E402
from services.gateway.router import router as gateway_router
from services.mobile.api import router as mobile_router  # noqa: E402

_LOCATION_ID = "11111111-1111-4111-8111-111111111111"
_PARAMETER_SAMPLES = {
    "location_id": _LOCATION_ID,
    "post_id": "33333333-3333-4333-8333-333333333333",
    "enrollment_id": "22222222-2222-4222-8222-222222222222",
    "device_id": "collector-1",
    "proposal_id": "17",
    "wallet": "0x1111111111111111111111111111111111111111",
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
    ("GET", "/api/v1/governance/baal/config"): ("governance", "read", False),
    ("GET", "/api/v1/governance/baal/proposals"): ("governance", "read", False),
    ("GET", "/api/v1/governance/baal/proposals/{proposal_id}"): ("governance", "read", False),
    ("GET", "/api/v1/governance/baal/members/{wallet}"): ("governance", "read", False),
    ("GET", "/api/data-stream/posts"): ("data_stream_post", "read", False),
    ("GET", "/api/data-stream/posts/{post_id}/files"): ("data_stream_file", "read", False),
    ("GET", "/api/data-stream/posts/{post_id}/attestation"): (
        "data_stream_proof",
        "read",
        False,
    ),
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
    ("POST", "/api/participation/delphi/preview"): ("delphi_participant", "preview", True),
    ("POST", "/api/participation/delphi/accept"): ("delphi_participant", "accept", True),
    ("POST", "/api/participation/delphi/withdraw"): ("delphi_participant", "withdraw", True),
    ("GET", "/api/participation/delphi"): ("delphi_participant_app", "read", True),
    ("GET", "/api/participation/delphi/app.js"): ("delphi_participant_app", "read", True),
    ("GET", "/api/participation/delphi/styles.css"): ("delphi_participant_app", "read", True),
    ("GET", "/api/participation/delphi/workspace"): ("delphi_participant", "read", True),
    ("POST", "/api/participation/delphi/contributions"): ("delphi_participant", "write", True),
    ("POST", "/api/participation/delphi/minority-reports"): ("delphi_participant", "write", True),
}

_participant_router = APIRouter()
register_delphi_participant_routes(_participant_router, None, __import__("psycopg2"))


def _concrete_path(path: str) -> str:
    return re.sub(
        r"\{([^{}]+)\}",
        lambda match: _PARAMETER_SAMPLES[match.group(1)],
        path,
    )


def test_registered_api_routes_have_exact_reviewed_policy_coverage():
    actual = {}
    for router in (gateway_router, mobile_router, _participant_router):
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


def test_federation_node_list_publishes_and_enforces_page_bounds(monkeypatch):
    schema = create_app().openapi()
    operation = schema["paths"]["/api/federation/nodes"]["get"]
    parameters = {parameter["name"]: parameter for parameter in operation["parameters"]}
    assert parameters["limit"]["schema"]["minimum"] == 1
    assert parameters["limit"]["schema"]["maximum"] == 100
    assert parameters["limit"]["schema"]["default"] == 50
    assert parameters["offset"]["schema"]["minimum"] == 0
    assert parameters["offset"]["schema"]["maximum"] == 10000
    response_schema = operation["responses"]["200"]["content"]["application/json"]["schema"]
    assert response_schema["$ref"].endswith("/FederationNodesPage")
    page_schema = schema["components"]["schemas"]["FederationNodesPage"]
    assert set(page_schema["properties"]) == {
        "nodes",
        "limit",
        "offset",
        "has_more",
        "next_offset",
        "continuation_capped",
    }

    with patch(
        "services.federation.node.FederationNode.list_nodes_page",
        return_value={
            "nodes": [],
            "limit": 20,
            "offset": 40,
            "has_more": False,
            "next_offset": None,
            "continuation_capped": False,
        },
    ) as list_nodes_page:
        with TestClient(create_app()) as client:
            valid = client.get("/api/federation/nodes", params={"limit": 20, "offset": 40})
            invalid = client.get("/api/federation/nodes", params={"limit": 101})

    assert valid.status_code == 200
    assert valid.json() == {
        "nodes": [],
        "limit": 20,
        "offset": 40,
        "has_more": False,
        "next_offset": None,
        "continuation_capped": False,
    }
    assert invalid.status_code == 422
    list_nodes_page.assert_called_once_with(limit=20, offset=40)


def test_catch_all_policy_log_does_not_include_unregistered_path():
    sensitive_path = "/api/private/participant/participant-name/secret-token"

    with patch("services.gateway.router.logger.warning") as warning:
        policy = get_route_policy("GET", sensitive_path)

    assert policy == {
        "resource": "gateway",
        "action": "get",
        "public": False,
        "location_id": None,
    }
    warning.assert_called_once_with("Catch-all route hit — no explicit policy defined")
    assert sensitive_path not in str(warning.call_args)


def test_data_stream_read_policy_extracts_and_normalizes_query_location():
    policy = get_route_policy("GET", "/api/data-stream/posts")
    request = SimpleNamespace(
        method="GET",
        query_params={"location_id": "11111111-1111-4111-8111-111111111111"},
    )

    assert asyncio.run(_request_location(request, policy)) == _LOCATION_ID


@pytest.mark.parametrize(
    ("path", "resource"),
    [
        ("/api/data-stream/posts/33333333-3333-4333-8333-333333333333/files", "data_stream_file"),
        (
            "/api/data-stream/posts/33333333-3333-4333-8333-333333333333/attestation",
            "data_stream_proof",
        ),
    ],
)
def test_data_stream_file_and_proof_policies_extract_query_location(path, resource):
    policy = get_route_policy("GET", path)
    request = SimpleNamespace(method="GET", query_params={"location_id": _LOCATION_ID})

    assert policy["resource"] == resource
    assert policy["location_id"] is None
    assert asyncio.run(_request_location(request, policy)) == _LOCATION_ID


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
