"""Gateway response validation for JSONB-backed federation capabilities."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from services.gateway.router import router


def _app() -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="/api")
    return app


def _node(shared_capabilities):
    return {
        "node_id": "11111111-1111-4111-8111-111111111111",
        "node_name": "Kokonut peer",
        "node_url": "https://peer.example",
        "trust_level": "trusted",
        "shared_capabilities": shared_capabilities,
        "last_sync_at": None,
        "status": "active",
        "created_at": "2026-10-28T12:00:00+00:00",
    }


def _page(node):
    return {
        "nodes": [node],
        "limit": 50,
        "offset": 0,
        "has_more": False,
        "next_offset": None,
        "continuation_capped": False,
    }


def test_federation_gateway_preserves_nested_json_capabilities(monkeypatch):
    capabilities = [
        {
            "data_types": ["metrics", "harvest"],
            "constraints": {
                "aggregation": "monthly",
                "fields": ["total", "period"],
            },
            "enabled": True,
        },
        {"name": "versioned-profile", "version": 2},
    ]
    monkeypatch.setattr(
        "services.federation.node.FederationNode.list_nodes_page",
        lambda _self, **_kwargs: _page(_node(capabilities)),
    )

    with TestClient(_app()) as client:
        response = client.get("/api/federation/nodes")

    assert response.status_code == 200
    assert response.json() == _page(_node(capabilities))


def test_federation_openapi_references_recursive_json_capabilities_schema():
    schema = _app().openapi()
    operation = schema["paths"]["/api/federation/nodes"]["get"]
    page_ref = operation["responses"]["200"]["content"]["application/json"]["schema"]["$ref"]
    page_name = page_ref.rsplit("/", 1)[-1]
    node_ref = schema["components"]["schemas"][page_name]["properties"]["nodes"]["items"]["$ref"]
    node_name = node_ref.rsplit("/", 1)[-1]

    assert schema["components"]["schemas"][node_name]["properties"]["shared_capabilities"] == {
        "$ref": "#/components/schemas/JsonValue",
    }


def test_federation_gateway_rejects_non_json_capability_objects(monkeypatch):
    monkeypatch.setattr(
        "services.federation.node.FederationNode.list_nodes_page",
        lambda _self, **_kwargs: _page(_node(object())),
    )

    with TestClient(_app(), raise_server_exceptions=False) as client:
        response = client.get("/api/federation/nodes")

    assert response.status_code == 500
    assert response.text == "Internal Server Error"
