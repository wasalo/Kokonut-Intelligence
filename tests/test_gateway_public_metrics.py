"""Regression tests for the gateway's governed public metric read path."""

from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("fastapi")
from starlette.testclient import TestClient  # noqa: E402

from services.analytics.queries import MetricSummary  # noqa: E402
from services.gateway.app import create_app  # noqa: E402


def test_public_metrics_reads_verified_view_without_computing() -> None:
    location_id = "11111111-1111-4111-8111-111111111111"
    backend = MagicMock()
    backend.execute.return_value = (MetricSummary("yield", "Yield", "kg", 12.5, None),)

    with patch("services.analytics.backend.get_analytics_backend", return_value=backend), patch(
        "services.metrics.engine.compute_all"
    ) as compute_all:
        with TestClient(create_app()) as client:
            response = client.get(f"/api/metrics/{location_id}")

    assert response.status_code == 200
    assert response.json()["computed"][0]["metric_key"] == "yield"
    compute_all.assert_not_called()
    backend.execute.assert_called_once()


def test_create_app_returns_fastapi_instance() -> None:
    app = create_app()
    assert app is not None
    assert app.title == "Kokonut Intelligence Gateway"


def test_public_metrics_empty_result() -> None:
    location_id = "22222222-2222-4222-8222-222222222222"
    backend = MagicMock()
    backend.execute.return_value = ()

    with patch("services.analytics.backend.get_analytics_backend", return_value=backend):
        with TestClient(create_app()) as client:
            response = client.get(f"/api/metrics/{location_id}")

    assert response.status_code == 200
    assert response.json()["computed"] == []
