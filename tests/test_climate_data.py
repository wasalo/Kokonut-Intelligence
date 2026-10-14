"""Climate data ingestion tests."""

from pathlib import Path

SCHEMA = Path("schemas/postgres/077_telemetry_infrastructure.sql")
WORLDCLIM_SCHEMA = Path("schemas/postgres/074_dsm_soc_prediction.sql")
WORLDCLIM_KEY_MIGRATION = Path("schemas/postgres/397_worldclim_location_baseline_key.sql")


def test_schema_file_exists() -> None:
    assert SCHEMA.exists()


def test_estimate_bioclim_tropical() -> None:
    from services.ingestion.climate_data import _estimate_bioclim

    # Tropical latitude (near equator)
    bio1 = _estimate_bioclim(0.0, 36.0, 1)
    assert bio1 is not None
    assert bio1 > 20  # Should be warm


def test_estimate_bioclim_temperate() -> None:
    from services.ingestion.climate_data import _estimate_bioclim

    # Temperate latitude
    bio1 = _estimate_bioclim(45.0, 0.0, 1)
    assert bio1 is not None
    assert bio1 < 25  # Should be cooler than tropical


def test_estimate_bioclim_arctic() -> None:
    from services.ingestion.climate_data import _estimate_bioclim

    # Arctic latitude
    bio1 = _estimate_bioclim(70.0, 0.0, 1)
    assert bio1 is not None
    assert bio1 < 5  # Should be cold


def test_estimate_bioclim_all_variables() -> None:
    from services.ingestion.climate_data import _estimate_bioclim

    for bio in range(1, 20):
        value = _estimate_bioclim(10.0, 36.0, bio)
        assert value is not None, f"bio_{bio} returned None"


def test_estimate_bioclim_temperature_range() -> None:
    from services.ingestion.climate_data import _estimate_bioclim

    # Temperature variables (bio 1-11) should be reasonable
    for bio in range(1, 12):
        value = _estimate_bioclim(10.0, 36.0, bio)
        if value is not None:
            assert -50 < value < 60, f"bio_{bio} = {value} outside reasonable range"


def test_estimate_bioclim_precipitation_range() -> None:
    from services.ingestion.climate_data import _estimate_bioclim

    # Precipitation variables (bio 12-19) should be non-negative
    for bio in range(12, 20):
        value = _estimate_bioclim(10.0, 36.0, bio)
        if value is not None:
            assert value >= 0, f"bio_{bio} = {value} is negative"


def test_worldclim_insert_pattern() -> None:
    """The location baseline upsert must match the partial unique index."""
    content = Path("services/ingestion/climate_data.py").read_text()
    assert "ON CONFLICT (location_id) WHERE plot_id IS NULL DO UPDATE SET" in content


class _WorldclimCursor:
    def __init__(self) -> None:
        self.statement = ""
        self.parameters = None

    def execute(self, statement, parameters=None) -> None:
        self.statement = statement
        self.parameters = parameters

    def fetchone(self):
        if "SELECT ST_Y(centroid)" in self.statement:
            return {"lat": 18.5, "lon": -69.9}
        return ("synthetic-worldclim-record",)

    def close(self) -> None:
        pass


class _WorldclimConnection:
    def __init__(self) -> None:
        self.cursors = []
        self.committed = False

    def cursor(self, **_kwargs):
        cursor = _WorldclimCursor()
        self.cursors.append(cursor)
        return cursor

    def commit(self) -> None:
        self.committed = True


def test_worldclim_proxy_write_matches_schema_and_records_provenance(monkeypatch) -> None:
    import json
    import re

    from services.ingestion import climate_data

    connection = _WorldclimConnection()
    ingestion_records = []
    monkeypatch.setattr(climate_data, "log_ingestion", lambda **record: ingestion_records.append(record))

    result = climate_data.fetch_worldclim(connection, "synthetic-location")

    sql = connection.cursors[1].statement
    params = connection.cursors[1].parameters
    insert_columns = re.search(r"INSERT INTO worldclim_climate\s*\((.*?)\)\s*VALUES", sql, re.DOTALL)
    assert insert_columns is not None
    columns = {column.strip() for column in insert_columns.group(1).split(",")}
    schema = WORLDCLIM_SCHEMA.read_text()
    table_ddl = re.search(r"CREATE TABLE IF NOT EXISTS worldclim_climate\s*\((.*?)\);", schema, re.DOTALL)
    assert table_ddl is not None
    schema_columns = set(re.findall(r"^\s{4}([a-z][a-z0-9_]*)\s+", table_ddl.group(1), re.MULTILINE))

    assert columns <= schema_columns
    assert "reference_period" not in columns
    assert "ON CONFLICT (location_id) WHERE plot_id IS NULL DO UPDATE SET" in sql
    assert connection.committed
    assert len(params) == 11
    assert json.loads(params[-1])["estimation_method"] == "latitude_proxy_v1"
    assert len(json.loads(params[-1])["estimated_bioclimatic_variables"]) == 19
    assert result["source"] == "latitude_proxy_v1"
    assert result["estimated"] is True
    assert ingestion_records[0]["source_system"] == "latitude_proxy"


def test_worldclim_baseline_migration_refuses_unreviewed_duplicate_rows() -> None:
    migration = WORLDCLIM_KEY_MIGRATION.read_text()

    assert "GROUP BY location_id" in migration
    assert "HAVING COUNT(*) > 1" in migration
    assert "RAISE EXCEPTION" in migration
    assert "CREATE UNIQUE INDEX uq_worldclim_climate_location_baseline" in migration
    assert "WHERE plot_id IS NULL" in migration
    assert "DELETE FROM" not in migration
    assert "UPDATE public.worldclim_climate" not in migration


def test_worldclim_location_baseline_falls_back_for_plot_consumers() -> None:
    migration = WORLDCLIM_KEY_MIGRATION.read_text()
    prediction = Path("services/analytics/soc_prediction.py").read_text()

    assert "CREATE OR REPLACE VIEW public.v_dsm_feature_set" in migration
    assert "LEFT JOIN LATERAL" in migration
    assert "(baseline.plot_id = rsl.plot_id OR baseline.plot_id IS NULL)" in migration
    assert "ORDER BY (baseline.plot_id = rsl.plot_id) DESC NULLS LAST" in migration
    assert "(baseline.plot_id = scm.plot_id OR baseline.plot_id IS NULL)" in prediction
    assert "ORDER BY (baseline.plot_id = scm.plot_id) DESC NULLS LAST" in prediction


def test_climate_data_has_cli() -> None:
    content = Path("services/ingestion/climate_data.py").read_text()
    assert 'if __name__ == "__main__":' in content
    assert "--worldclim" in content
    assert "--location-id" in content


def test_freshness_has_cli() -> None:
    content = Path("services/ingestion/data_freshness.py").read_text()
    assert 'if __name__ == "__main__":' in content
    assert "--check" in content
    assert "--summary" in content


def test_freshness_uses_logging() -> None:
    content = Path("services/ingestion/data_freshness.py").read_text()
    assert "get_logger" in content


def test_climate_data_uses_logging() -> None:
    content = Path("services/ingestion/climate_data.py").read_text()
    assert "get_logger" in content


def test_freshness_queries_config_table() -> None:
    content = Path("services/ingestion/data_freshness.py").read_text()
    assert "data_freshness_config" in content


def test_freshness_inserts_check_results() -> None:
    content = Path("services/ingestion/data_freshness.py").read_text()
    assert "data_freshness_check" in content


def test_freshness_has_alert_channels() -> None:
    content = Path("services/ingestion/data_freshness.py").read_text()
    assert "webhook" in content or "ALERT_WEBHOOK_URL" in content
    assert "email" in content or "ALERT_SMTP" in content


def test_climate_data_pipeline_targets_all_tables() -> None:
    entrypoint = Path("services/ingestion/climate_data.py").read_text()
    gee_fetchers = Path("services/ingestion/gee_climate.py").read_text()

    assert "worldclim_climate" in entrypoint
    assert "return fetch_era5_land" in entrypoint
    assert "return fetch_modis_lst" in entrypoint
    assert "return fetch_smap_moisture" in entrypoint
    assert "return fetch_sentinel1_sar" in entrypoint
    assert "ncep_weather_summary" in gee_fetchers
    assert "modis_lst_summary" in gee_fetchers
    assert "smap_soil_moisture" in gee_fetchers
    assert "sentinel1_sar_summary" in gee_fetchers


def test_rs_job_schema_has_provider_constraint() -> None:
    content = SCHEMA.read_text()
    assert "chk_rs_job_provider" in content
    assert "'gee'" in content
    assert "'copernicus'" in content
