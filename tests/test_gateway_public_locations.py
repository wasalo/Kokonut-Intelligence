"""Legacy public location routes use only the governed native projection."""

import json
from unittest.mock import Mock, call

import pytest

pytest.importorskip("fastapi")
from starlette.testclient import TestClient  # noqa: E402

from services.analytics.queries import (  # noqa: E402
    AnalyticsContext,
    PublicLocationDirectoryRequest,
    PublicLocationSummary,
    QueryId,
)
from services.common.http import http  # noqa: E402
from services.gateway import locations  # noqa: E402
from services.gateway.app import create_app  # noqa: E402

LOCATION_ID = "11111111-1111-4111-8111-111111111111"
PUBLIC_LOCATION = {
    "id": LOCATION_ID,
    "name": "Reference Farm",
    "country": "DO",
    "region": "North",
    "status": "active",
}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("KOKONUT_FEATURE_DIRECTUS", "true")
    monkeypatch.setenv(
        "KOKONUT_GATEWAY_AUDIT_SPOOL_PATH",
        str(tmp_path / "gateway-audit.sqlite3"),
    )
    with TestClient(create_app()) as test_client:
        yield test_client


def test_legacy_location_list_uses_public_projection_even_with_directus_enabled(
    client, monkeypatch
):
    native_read = Mock(return_value=[PUBLIC_LOCATION])
    directus_read = Mock(side_effect=AssertionError("Directus must not serve this public route"))
    monkeypatch.setattr(locations, "public_locations", native_read)
    monkeypatch.setattr(http, "get", directus_read)

    response = client.get("/api/locations")

    assert response.status_code == 200
    assert json.loads(response.json()["data"]) == {"data": [PUBLIC_LOCATION]}
    native_read.assert_called_once_with()
    directus_read.assert_not_called()


def test_legacy_location_detail_uses_public_projection_and_preserves_404(client, monkeypatch):
    native_read = Mock(side_effect=[[PUBLIC_LOCATION], []])
    monkeypatch.setattr(locations, "public_locations", native_read)

    response = client.get(f"/api/locations/{LOCATION_ID}")
    missing = client.get(f"/api/locations/{'22222222-2222-4222-8222-222222222222'}")

    assert response.status_code == 200
    assert json.loads(response.json()["data"]) == {"data": PUBLIC_LOCATION}
    assert missing.status_code == 404
    assert native_read.call_args_list == [
        call(LOCATION_ID),
        call("22222222-2222-4222-8222-222222222222"),
    ]


def test_legacy_location_detail_rejects_invalid_uuid_before_projection(client, monkeypatch):
    native_read = Mock()
    monkeypatch.setattr(locations, "public_locations", native_read)

    response = client.get("/api/locations/not-a-uuid")

    assert response.status_code == 400
    native_read.assert_not_called()


def test_public_location_service_uses_typed_analytics_query(monkeypatch):
    backend = Mock()
    backend.execute.return_value = (
        PublicLocationSummary(LOCATION_ID, "Reference Farm", "DO", "North", "active"),
    )
    monkeypatch.setattr(locations, "get_analytics_backend", lambda **_kwargs: backend)

    result = locations.public_locations(LOCATION_ID)

    assert result == [PUBLIC_LOCATION]
    backend.execute.assert_called_once_with(
        QueryId.PUBLIC_LOCATION_DIRECTORY,
        PublicLocationDirectoryRequest(LOCATION_ID),
        AnalyticsContext(location_id=LOCATION_ID, public=True),
    )
