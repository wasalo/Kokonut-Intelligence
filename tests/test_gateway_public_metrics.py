"""Regression tests for the gateway's governed public metric read path."""

from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from services.gateway.app import create_app  # noqa: E402


def test_public_metrics_reads_verified_view_without_computing() -> None:
    conn = MagicMock()
    conn.cursor.return_value.fetchall.return_value = [
        ("yield", "Yield", "kg", 12.5, None),
    ]

    with patch("services.ingestion.base.get_db", return_value=conn), patch(
        "services.metrics.engine.compute_all"
    ) as compute_all:
        with TestClient(create_app()) as client:
            response = client.get("/api/metrics/location-1")

    assert response.status_code == 200
    assert response.json()["computed"][0]["metric_key"] == "yield"
    compute_all.assert_not_called()
    conn.cursor.return_value.execute.assert_called_once()
