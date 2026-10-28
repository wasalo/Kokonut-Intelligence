"""Public driver inventory exposes only its display-safe catalog projection."""

from types import SimpleNamespace

import pytest

pytest.importorskip("fastapi")
from starlette.testclient import TestClient  # noqa: E402

from services.drivers.registry import DriverRegistry  # noqa: E402
from services.gateway.app import create_app  # noqa: E402
from services.gateway.router import get_route_policy  # noqa: E402


def test_anonymous_driver_catalog_omits_loader_and_registration_details(
    monkeypatch,
):
    monkeypatch.delenv("KOKONUT_API_KEYS", raising=False)

    class NoopAudit:
        def log(self, **_kwargs):
            return None

        def replay_pending(self, _limit):
            return 0

        def capture_status(self):
            return {"pending": 0}

    monkeypatch.setattr("services.gateway.audit.GatewayAudit", NoopAudit)
    requested_pages = []

    def list_public_drivers_page(_registry, *, limit, offset):
        requested_pages.append((limit, offset))
        return {
            "drivers": [
                {
                    "driver_name": "weather_openweathermap",
                    "driver_version": "1.2.0",
                    "driver_type": "weather",
                }
            ],
            "limit": limit,
            "offset": offset,
            "has_more": True,
        }

    monkeypatch.setattr(
        "services.drivers.registry.DriverRegistry.list_public_drivers_page",
        list_public_drivers_page,
    )

    assert get_route_policy("GET", "/api/drivers")["public"] is True
    app = create_app(
        rate_limiter=SimpleNamespace(
            check=lambda _caller: True,
            retry_after=lambda _caller: 0,
        )
    )
    with TestClient(app) as client:
        response = client.get("/api/drivers?limit=1&offset=4")
        over_limit_response = client.get("/api/drivers?limit=51")
        openapi = app.openapi()

    assert response.status_code == 200
    assert response.json() == {
        "drivers": [
            {
                "driver_name": "weather_openweathermap",
                "driver_version": "1.2.0",
                "driver_type": "weather",
            }
        ],
        "limit": 1,
        "offset": 4,
        "has_more": True,
    }
    assert requested_pages == [(1, 4)]
    assert over_limit_response.status_code == 422
    assert requested_pages == [(1, 4)]
    schema_ref = openapi["paths"]["/api/drivers"]["get"]["responses"]["200"][
        "content"
    ]["application/json"]["schema"]["$ref"]
    catalog_schema = openapi["components"]["schemas"][schema_ref.rsplit("/", 1)[-1]]
    assert set(catalog_schema["properties"]) == {
        "drivers",
        "limit",
        "offset",
        "has_more",
    }
    entry_ref = catalog_schema["properties"]["drivers"]["items"]["$ref"]
    entry_schema = openapi["components"]["schemas"][entry_ref.rsplit("/", 1)[-1]]
    assert set(entry_schema["properties"]) == {
        "driver_name",
        "driver_version",
        "driver_type",
    }


def test_public_driver_registry_page_is_bounded_and_stably_ordered():
    class Cursor:
        def __init__(self):
            self.query = ""
            self.params = ()

        def __enter__(self):
            return self

        def __exit__(self, *_exc):
            return False

        def execute(self, query, params):
            self.query = query
            self.params = params

        def fetchall(self):
            return [
                ("driver_a", "1.0", "sensor"),
                ("driver_b", "1.0", "sensor"),
                ("driver_c", "1.0", "weather"),
            ]

    class Connection:
        def __init__(self):
            self.cursor_instance = Cursor()

        def cursor(self):
            return self.cursor_instance

    connection = Connection()
    page = DriverRegistry(conn=connection).list_public_drivers_page(limit=2, offset=3)

    assert page == {
        "drivers": [
            {"driver_name": "driver_a", "driver_version": "1.0", "driver_type": "sensor"},
            {"driver_name": "driver_b", "driver_version": "1.0", "driver_type": "sensor"},
        ],
        "limit": 2,
        "offset": 3,
        "has_more": True,
    }
    query = connection.cursor_instance.query.lower()
    assert "where is_enabled = true" in query
    assert "order by driver_type, driver_name" in query
    assert "limit %s offset %s" in query
    assert connection.cursor_instance.params == (3, 3)
    assert "module_path" not in query
    assert "description" not in query


@pytest.mark.parametrize(
    ("offset", "has_more"),
    [(4950, True), (4951, False), (5000, False)],
)
def test_driver_catalog_does_not_advertise_an_unrequestable_next_page(offset, has_more):
    class Cursor:
        def __enter__(self):
            return self

        def __exit__(self, *_exc):
            return False

        def execute(self, _query, _params):
            return None

        def fetchall(self):
            return [("driver", "1.0", "weather")] * 51

    class Connection:
        def cursor(self):
            return Cursor()

    page = DriverRegistry(conn=Connection()).list_public_drivers_page(
        limit=50,
        offset=offset,
    )

    assert len(page["drivers"]) == 50
    assert page["has_more"] is has_more


@pytest.mark.parametrize("limit, offset", [(0, 0), (51, 0), (1, 5001)])
def test_public_driver_registry_rejects_out_of_range_pages(limit, offset):
    with pytest.raises(ValueError):
        DriverRegistry(conn=object()).list_public_drivers_page(limit=limit, offset=offset)


def test_versioned_public_driver_catalog_uses_stable_envelope_and_policy(monkeypatch):
    monkeypatch.delenv("KOKONUT_API_KEYS", raising=False)

    class NoopAudit:
        def log(self, **_kwargs):
            return None

        def replay_pending(self, _limit):
            return 0

        def capture_status(self):
            return {"pending": 0}

    monkeypatch.setattr("services.gateway.audit.GatewayAudit", NoopAudit)
    calls = []

    def list_public_drivers_page(_registry, *, limit, offset):
        calls.append((limit, offset))
        return {
            "drivers": [
                {
                    "driver_name": "weather_openweathermap",
                    "driver_version": "1.2.0",
                    "driver_type": "weather",
                }
            ],
            "limit": limit,
            "offset": offset,
            "has_more": False,
        }

    monkeypatch.setattr(
        "services.drivers.registry.DriverRegistry.list_public_drivers_page",
        list_public_drivers_page,
    )
    app = create_app(
        rate_limiter=SimpleNamespace(
            check=lambda _caller: True,
            retry_after=lambda _caller: 0,
        )
    )
    with TestClient(app) as client:
        response = client.get("/api/v1/drivers?limit=7&offset=12")
        invalid_page = client.get("/api/v1/drivers?limit=51")
        spec = app.openapi()

    assert get_route_policy("GET", "/api/v1/drivers") == {
        "resource": "driver",
        "action": "read",
        "public": True,
        "location_id": None,
    }
    assert response.status_code == 200
    assert response.json() == {
        "data": {
            "drivers": [
                {
                    "driver_name": "weather_openweathermap",
                    "driver_version": "1.2.0",
                    "driver_type": "weather",
                }
            ],
            "limit": 7,
            "offset": 12,
            "has_more": False,
        }
    }
    assert calls == [(7, 12)]
    assert invalid_page.status_code == 422
    assert calls == [(7, 12)]
    assert spec["paths"]["/api/v1/drivers"]["get"]["operationId"] == (
        "listPublicDriversV1"
    )
