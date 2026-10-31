"""Geostatistics pagination validation matches service-side bounds."""

from uuid import uuid4

import pytest

pytest.importorskip("fastapi")
from fastapi import APIRouter, FastAPI  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

from services.gateway.geostatistics_routes import register_geostatistics_routes  # noqa: E402

PAGINATED_ROUTES = (
    (
        "/operator/api/geostatistics/{location_id}/autocorrelation",
        "services.gateway.geostatistics_reads.list_location_spatial_autocorrelation",
        25,
    ),
    (
        "/operator/api/geostatistics/{location_id}/cross-validation",
        "services.gateway.geostatistics_reads.list_location_cross_validation",
        25,
    ),
    (
        "/operator/api/geostatistics/{location_id}/variogram-models",
        "services.gateway.geostatistics_reads.list_location_variogram_models",
        25,
    ),
    (
        "/operator/api/geostatistics/{location_id}/sensor-network-designs",
        "services.gateway.geostatistics_reads.list_location_sensor_network_designs",
        25,
    ),
    (
        "/operator/api/geostatistics/{location_id}/kriging-summaries",
        "services.gateway.geostatistics_reads.list_location_kriging_summaries",
        25,
    ),
    (
        "/operator/api/geostatistics/{location_id}/kriging/{prediction_id}/points",
        "services.gateway.geostatistics_reads.list_location_kriging_points",
        50,
    ),
    (
        "/operator/api/geostatistics/{location_id}/realization-summaries",
        "services.gateway.geostatistics_reads.list_location_realization_summaries",
        25,
    ),
    (
        "/operator/api/geostatistics/{location_id}/realizations/{realization_id}/points",
        "services.gateway.geostatistics_reads.list_location_realization_points",
        50,
    ),
)
LOCATION_ID = str(uuid4())


@pytest.fixture
def isolated_gateway(monkeypatch):
    import services.gateway.geostatistics_reads as reads

    for _path_template, service_path, _default in PAGINATED_ROUTES:
        service_name = service_path.rsplit(".", maxsplit=1)[-1]

        def unexpected_service(*_args, _name=service_name, **_kwargs):
            raise AssertionError(f"FastAPI invoked {_name} for invalid pagination")

        monkeypatch.setattr(reads, service_name, unexpected_service)

    app = FastAPI()
    router = APIRouter()
    register_geostatistics_routes(
        router,
        object(),
        run_in_threadpool=lambda *_args, **_kwargs: None,
        psycopg2=type("PsycopgErrors", (), {"Error": Exception}),
    )
    app.include_router(router)
    return app


def _path(template: str) -> str:
    return (
        template.replace("{location_id}", LOCATION_ID)
        .replace("{prediction_id}", str(uuid4()))
        .replace("{realization_id}", str(uuid4()))
    )


@pytest.mark.parametrize("path_template, _service_path, default", PAGINATED_ROUTES)
def test_openapi_pagination_contract_matches_geostatistics_service_bounds(
    isolated_gateway, path_template, _service_path, default
):
    operation = isolated_gateway.openapi()["paths"][path_template]["get"]
    parameters = {parameter["name"]: parameter["schema"] for parameter in operation["parameters"]}

    assert parameters["limit"] == {
        "type": "integer",
        "maximum": 50,
        "minimum": 1,
        "default": default,
        "title": "Limit",
    }
    assert parameters["offset"] == {
        "type": "integer",
        "maximum": 10_000,
        "minimum": 0,
        "default": 0,
        "title": "Offset",
    }


@pytest.mark.parametrize("path_template, service_path, _default", PAGINATED_ROUTES)
@pytest.mark.parametrize("parameter, value", [("limit", 0), ("limit", 51), ("offset", -1), ("offset", 10_001)])
def test_out_of_range_pagination_is_rejected_before_service_access(
    monkeypatch,
    isolated_gateway,
    path_template,
    service_path,
    _default,
    parameter,
    value,
):
    with TestClient(isolated_gateway) as client:
        response = client.get(_path(path_template), params={parameter: value})

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["query", parameter]
