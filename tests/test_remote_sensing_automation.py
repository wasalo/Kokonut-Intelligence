"""Remote sensing automation tests."""

from pathlib import Path

SCHEMA = Path("schemas/postgres/077_telemetry_infrastructure.sql")


def test_schema_file_exists() -> None:
    assert SCHEMA.exists()


def test_schema_has_remote_sensing_job() -> None:
    content = SCHEMA.read_text()
    assert "remote_sensing_job" in content
    assert "provider" in content
    assert "cadence_days" in content
    assert "cloud_max_pct" in content
    assert "next_run_at" in content


def test_schema_has_provider_constraint() -> None:
    content = SCHEMA.read_text()
    assert "chk_rs_job_provider" in content


def test_schema_has_status_constraint() -> None:
    content = SCHEMA.read_text()
    assert "chk_rs_job_status" in content


def test_fetcher_file_exists() -> None:
    assert Path("services/ingestion/remote_sensing_fetcher.py").exists()


def test_gee_adapter_file_exists() -> None:
    assert Path("services/ingestion/gee_remote_sensing.py").exists()


def test_copernicus_adapter_file_exists() -> None:
    assert Path("services/ingestion/copernicus_remote_sensing.py").exists()


def test_gee_computes_ndvi() -> None:
    from services.ingestion.gee_remote_sensing import _compute_indices
    bands = {"band_nir": 0.4, "band_red": 0.1}
    indices = _compute_indices(bands)
    assert "ndvi" in indices
    assert 0 < indices["ndvi"] < 1  # Positive NDVI


def test_gee_computes_ndvi_negative() -> None:
    from services.ingestion.gee_remote_sensing import _compute_indices
    bands = {"band_nir": 0.1, "band_red": 0.4}
    indices = _compute_indices(bands)
    assert "ndvi" in indices
    assert indices["ndvi"] < 0  # Negative NDVI (water/barren)


def test_gee_computes_evi() -> None:
    from services.ingestion.gee_remote_sensing import _compute_indices
    bands = {"band_nir": 0.4, "band_red": 0.1, "band_blue": 0.05}
    indices = _compute_indices(bands)
    assert "evi" in indices
    assert indices["evi"] > 0


def test_gee_computes_savi() -> None:
    from services.ingestion.gee_remote_sensing import _compute_indices
    bands = {"band_nir": 0.4, "band_red": 0.1}
    indices = _compute_indices(bands)
    assert "savi" in indices


def test_gee_computes_msavi() -> None:
    from services.ingestion.gee_remote_sensing import _compute_indices
    bands = {"band_nir": 0.4, "band_red": 0.1}
    indices = _compute_indices(bands)
    assert "msavi" in indices


def test_gee_computes_ndwi() -> None:
    from services.ingestion.gee_remote_sensing import _compute_indices
    bands = {"band_nir": 0.1, "band_green": 0.4}
    indices = _compute_indices(bands)
    assert "ndwi" in indices
    assert indices["ndwi"] > 0  # Water body


def test_gee_computes_bsi() -> None:
    from services.ingestion.gee_remote_sensing import _compute_indices
    bands = {"band_swir1": 0.3, "band_red": 0.1, "band_nir": 0.4, "band_blue": 0.05}
    indices = _compute_indices(bands)
    assert "bsi" in indices


def test_gee_computes_tasseled_cap() -> None:
    from services.ingestion.gee_remote_sensing import _compute_indices
    bands = {
        "band_blue": 0.05, "band_green": 0.1, "band_red": 0.1,
        "band_nir": 0.4, "band_swir1": 0.3, "band_swir2": 0.2,
    }
    indices = _compute_indices(bands)
    assert "tc_brightness" in indices
    assert "tc_greenness" in indices
    assert "tc_wetness" in indices


def test_gee_computes_all_indices_with_full_bands() -> None:
    from services.ingestion.gee_remote_sensing import _compute_indices
    bands = {
        "band_blue": 0.05, "band_green": 0.1, "band_red": 0.1,
        "band_nir": 0.4, "band_swir1": 0.3, "band_swir2": 0.2,
    }
    indices = _compute_indices(bands)
    # Should compute at least 10 indices
    assert len(indices) >= 10


def test_gee_handles_missing_bands() -> None:
    from services.ingestion.gee_remote_sensing import _compute_indices
    bands = {"band_nir": 0.4}  # Only one band
    indices = _compute_indices(bands)
    # Should not crash, may return partial results
    assert isinstance(indices, dict)


def test_gee_handles_empty_bands() -> None:
    from services.ingestion.gee_remote_sensing import _compute_indices
    indices = _compute_indices({})
    assert isinstance(indices, dict)
    assert len(indices) == 0


def test_copernicus_has_token_url() -> None:
    content = Path("services/ingestion/copernicus_remote_sensing.py").read_text()
    assert "identity.dataspace.copernicus.eu" in content


def test_copernicus_has_catalog_url() -> None:
    content = Path("services/ingestion/copernicus_remote_sensing.py").read_text()
    assert "catalogue.dataspace.copernicus.eu" in content


def test_fetcher_has_cli() -> None:
    content = Path("services/ingestion/remote_sensing_fetcher.py").read_text()
    assert 'if __name__' in content
    assert "--run-jobs" in content
    assert "--list-jobs" in content
    assert "--job-id" in content


def test_fetcher_queries_active_jobs() -> None:
    content = Path("services/ingestion/remote_sensing_fetcher.py").read_text()
    assert "remote_sensing_job" in content
    assert "status = 'active'" in content


def test_fetcher_dispatches_to_providers() -> None:
    content = Path("services/ingestion/remote_sensing_fetcher.py").read_text()
    assert "gee_remote_sensing" in content
    assert "copernicus_remote_sensing" in content


def test_seed_has_adelphi_job() -> None:
    seed = Path("schemas/seeds/077_telemetry_infrastructure.sql").read_text()
    assert "remote_sensing_job" in seed
    assert "gee" in seed


def test_gee_requires_earthengine_api() -> None:
    content = Path("services/ingestion/gee_remote_sensing.py").read_text()
    assert "earthengine-api" in content or "ee.Initialize" in content


def test_gee_uses_service_account() -> None:
    content = Path("services/ingestion/gee_remote_sensing.py").read_text()
    assert "GEE_SERVICE_ACCOUNT_KEY" in content
    assert "ServiceAccountCredentials" in content


def test_copernicus_uses_oauth() -> None:
    content = Path("services/ingestion/copernicus_remote_sensing.py").read_text()
    assert "client_credentials" in content
    assert "access_token" in content


def test_gee_inserts_both_pg_and_ch() -> None:
    content = Path("services/ingestion/gee_remote_sensing.py").read_text()
    assert "_insert_pg" in content
    assert "_insert_ch" in content


def test_copernicus_inserts_both_pg_and_ch() -> None:
    content = Path("services/ingestion/copernicus_remote_sensing.py").read_text()
    assert "_insert_pg" in content
    assert "_insert_ch" in content


def test_gee_logs_ingestion() -> None:
    content = Path("services/ingestion/gee_remote_sensing.py").read_text()
    assert "log_ingestion" in content
    assert "gee_api" in content


def test_copernicus_logs_ingestion() -> None:
    content = Path("services/ingestion/copernicus_remote_sensing.py").read_text()
    assert "log_ingestion" in content
    assert "copernicus_api" in content
