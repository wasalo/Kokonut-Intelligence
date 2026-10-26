"""GEE climate failures must not expose credentials or request details."""

import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from services.ingestion import gee_climate

SECRET = "earth-engine-provider-secret"
BBOX = {"west": -70.0, "south": 18.0, "east": -69.0, "north": 19.0}


@pytest.mark.parametrize(
    ("fetcher", "summary"),
    [
        (gee_climate.fetch_modis_lst, "MODIS LST fetch failed (RuntimeError)"),
        (gee_climate.fetch_smap_moisture, "SMAP fetch failed (RuntimeError)"),
        (
            gee_climate.fetch_sentinel1_sar,
            "Sentinel-1 SAR fetch failed (RuntimeError)",
        ),
        (gee_climate.fetch_era5_land, "ERA5 Land fetch failed (RuntimeError)"),
    ],
)
def test_provider_failure_is_sanitized_and_rolls_back(monkeypatch, fetcher, summary):
    connection = MagicMock()
    logger = MagicMock()
    monkeypatch.setattr(gee_climate, "_get_gee_client", lambda: object())
    monkeypatch.setattr(
        gee_climate,
        "_period",
        lambda _days: (_ for _ in ()).throw(
            RuntimeError(f"request URL included token={SECRET}")
        ),
    )
    monkeypatch.setattr(gee_climate, "logger", logger)

    result = fetcher(connection, "synthetic-location", BBOX)

    assert result == {"status": "error", "message": summary}
    assert SECRET not in str(result)
    assert SECRET not in str(logger.error.call_args)
    connection.rollback.assert_called_once_with()


def test_service_account_initialization_error_is_sanitized(monkeypatch):
    logger = MagicMock()

    def fail_credentials(*_args):
        raise RuntimeError(f"credentials file URL included token={SECRET}")

    fake_ee = SimpleNamespace(ServiceAccountCredentials=fail_credentials)
    monkeypatch.setitem(sys.modules, "ee", fake_ee)
    monkeypatch.setenv("GEE_SERVICE_ACCOUNT_KEY", "/tmp/synthetic-gee-key.json")
    monkeypatch.setattr(gee_climate, "logger", logger)

    assert gee_climate._get_gee_client() is None
    assert SECRET not in str(logger.error.call_args)
    assert "RuntimeError" in str(logger.error.call_args)


def test_default_initialization_error_is_sanitized(monkeypatch):
    logger = MagicMock()
    fake_ee = SimpleNamespace(
        Initialize=lambda: (_ for _ in ()).throw(
            RuntimeError(f"provider endpoint included token={SECRET}")
        )
    )
    monkeypatch.setitem(sys.modules, "ee", fake_ee)
    monkeypatch.delenv("GEE_SERVICE_ACCOUNT_KEY", raising=False)
    monkeypatch.setattr(gee_climate, "logger", logger)

    assert gee_climate._get_gee_client() is None
    assert SECRET not in str(logger.error.call_args)
    assert "RuntimeError" in str(logger.error.call_args)
