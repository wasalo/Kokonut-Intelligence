"""Focused tests for the field collector companion app and API surface."""

from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from starlette.testclient import TestClient  # noqa: E402

from services.gateway.app import create_app  # noqa: E402
from services.gateway.router import get_route_policy  # noqa: E402
from services.mobile.api import APP_PATH, CollectionRequest  # noqa: E402


def test_mobile_routes_are_explicitly_public_for_device_auth():
    assert get_route_policy("GET", "/mobile")["public"] is True
    assert get_route_policy("GET", "/api/mobile/forms")["public"] is True
    assert get_route_policy("POST", "/api/mobile/sync")["public"] is True


def test_gateway_serves_field_collector():
    with TestClient(create_app()) as client:
        response = client.get("/mobile")
        api_response = client.get("/api/mobile/app")

    assert response.status_code == 200
    assert api_response.status_code == 200
    assert "Kokonut Field Collector" in response.text
    assert "localStorage" in response.text


def test_field_collector_is_directly_openable():
    assert APP_PATH == Path(__file__).parents[1] / "services/mobile/field-collector.html"
    assert APP_PATH.read_text().startswith("<!doctype html>")


def test_collection_request_rejects_invalid_coordinates():
    with pytest.raises(ValueError):
        CollectionRequest(
            client_id="client-1",
            collection_type="field_note",
            latitude=91,
        )
