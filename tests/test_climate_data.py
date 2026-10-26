"""Climate data ingestion tests."""

from pathlib import Path

SCHEMA = Path("schemas/postgres/077_telemetry_infrastructure.sql")
WORLDCLIM_SCHEMA = Path("schemas/postgres/074_dsm_soc_prediction.sql")
WORLDCLIM_KEY_MIGRATION = Path("schemas/postgres/397_worldclim_location_baseline_key.sql")
CLIMATE_KEY_MIGRATION = Path("schemas/postgres/428_climate_summary_idempotency.sql")


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
        if "FROM location" in self.statement:
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
    assert "ST_Y(center)" in connection.cursors[0].statement
    assert "centroid" not in connection.cursors[0].statement
    assert "reference_period" not in columns
    assert "ON CONFLICT (location_id) WHERE plot_id IS NULL DO UPDATE SET" in sql
    assert connection.committed
    assert len(params) == 11
    assert json.loads(params[-1])["estimation_method"] == "latitude_proxy_v1"
    assert len(json.loads(params[-1])["estimated_bioclimatic_variables"]) == 19
    assert result["source"] == "latitude_proxy_v1"
    assert result["estimated"] is True
    assert ingestion_records[0]["source_system"] == "latitude_proxy"
    assert ingestion_records[0]["db"] is connection
    assert ingestion_records[0]["location_id"] == "synthetic-location"


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
    assert "_publish_alert_event" in content
    assert '"data_stale"' in content


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


class _FakeInfo:
    def __init__(self, value):
        self.value = value

    def getInfo(self):
        return self.value


class _FakeImage:
    def __init__(self, dataset, reducer):
        self.dataset = dataset
        self.reducer = reducer

    def reduceRegion(self, **_kwargs):
        return _FakeInfo(_GEE_STATS[self.dataset][self.reducer])


class _FakeCollection:
    def __init__(self, dataset):
        self.dataset = dataset

    def filterBounds(self, _geometry):
        return self

    def filterDate(self, _start, _end):
        return self

    def filter(self, _condition):
        return self

    def select(self, _bands):
        return self

    def mean(self):
        return _FakeImage(self.dataset, "mean")

    def median(self):
        return _FakeImage(self.dataset, "median")

    def sum(self):
        return _FakeImage(self.dataset, "sum")

    def size(self):
        return _FakeInfo(3)


_GEE_STATS = {
    "MODIS/061/MOD11A2": {
        "mean": {"LST_Day_1km": 15000, "LST_Night_1km": 14000},
    },
    "NASA/SMAP/SPL3SMP_E/006": {
        "mean": {"soil_moisture_pm": 0.28},
    },
    "COPERNICUS/S1_GRD": {
        "median": {"VH": -18.4, "VV": -11.2},
    },
    "ECMWF/ERA5_LAND/DAILY_AGGR": {
        "mean": {
            "temperature_2m": 300.15,
            "temperature_2m_max": 301.15,
            "temperature_2m_min": 299.15,
            "volumetric_soil_water_layer_1": 0.25,
        },
        "sum": {"total_precipitation_sum": 0.12},
    },
}


class _FakeEarthEngine:
    class Geometry:
        @staticmethod
        def Rectangle(_bounds):
            return "synthetic-bounds"

    class Reducer:
        @staticmethod
        def mean():
            return "mean"

    class Filter:
        @staticmethod
        def eq(_name, _value):
            return "synthetic-filter"

    @staticmethod
    def ImageCollection(dataset):
        return _FakeCollection(dataset)


class _ClimateCursor:
    def __init__(self, connection):
        self.connection = connection
        self.statement = ""
        self.parameters = None

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, statement, parameters=None):
        self.statement = statement
        self.parameters = parameters
        self.connection.statements.append((statement, parameters))
        if self.connection.fail_insert and "INSERT INTO" in statement:
            raise RuntimeError("synthetic write failure")

    def fetchone(self):
        return ("synthetic-climate-record",)


class _ClimateConnection:
    def __init__(self, fail_insert=False):
        self.statements = []
        self.commits = 0
        self.rollbacks = 0
        self.fail_insert = fail_insert

    def cursor(self, **_kwargs):
        return _ClimateCursor(self)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        pass


def _install_fake_gee(monkeypatch):
    from services.ingestion import gee_climate

    monkeypatch.setattr(gee_climate, "_get_gee_client", lambda: _FakeEarthEngine)
    records = []
    monkeypatch.setattr(gee_climate, "log_ingestion", lambda **record: records.append(record))
    return gee_climate, records


def test_gee_provider_upserts_match_canonical_schema_and_audit_transaction(monkeypatch) -> None:
    import json
    import re

    gee_climate, audits = _install_fake_gee(monkeypatch)
    connection = _ClimateConnection()
    bbox = {"west": -70.0, "south": 18.0, "east": -69.0, "north": 19.0}
    schema = WORLDCLIM_SCHEMA.read_text()
    checks = [
        (gee_climate.fetch_modis_lst, "modis_lst_summary", "modis_lst_summary"),
        (gee_climate.fetch_smap_moisture, "smap_soil_moisture", "smap_soil_moisture"),
        (gee_climate.fetch_sentinel1_sar, "sentinel1_sar_summary", "sentinel1_sar_summary"),
        (gee_climate.fetch_era5_land, "ncep_weather_summary", "ncep_weather_summary"),
    ]

    for fetcher, table, expected_insert_table in checks:
        result = fetcher(connection, "synthetic-location", bbox)
        assert result["status"] == "success"
        statement, parameters = connection.statements[-1]
        insert = re.search(
            rf"INSERT INTO {expected_insert_table}\s*\((.*?)\)\s*VALUES",
            statement,
            re.DOTALL,
        )
        assert insert is not None, table
        columns = {column.strip() for column in insert.group(1).split(",")}
        table_ddl = re.search(
            rf"CREATE TABLE IF NOT EXISTS {table}\s*\((.*?)\);", schema, re.DOTALL
        )
        assert table_ddl is not None, table
        schema_columns = set(
            re.findall(r"^\s{4}([a-z][a-z0-9_]*)\s+", table_ddl.group(1), re.MULTILINE)
        )
        assert columns <= schema_columns, (table, columns - schema_columns)
        assert "ON CONFLICT (location_id, target_date, source)" in statement
        assert "WHERE plot_id IS NULL AND source IS NOT NULL" in statement
        assert parameters[0] == "synthetic-location"

    assert connection.commits == 4
    assert len(audits) == 4
    assert all(audit["db"] is connection for audit in audits)
    assert all(audit["location_id"] == "synthetic-location" for audit in audits)
    assert audits[0]["source_id"] == "MODIS/061/MOD11A2"
    assert audits[1]["source_id"] == "NASA/SMAP/SPL3SMP_E/006"
    assert audits[2]["source_id"] == "COPERNICUS/S1_GRD"
    assert audits[3]["source_id"] == "ECMWF/ERA5_LAND/DAILY_AGGR"

    modis_params = connection.statements[0][1]
    smap_params = connection.statements[1][1]
    sentinel_params = connection.statements[2][1]
    era5_params = connection.statements[3][1]
    assert modis_params[4:6] == (26.85, 6.85)
    assert smap_params[4] == 0.28
    assert sentinel_params[4:6] == (-18.4, -11.2)
    assert era5_params[4:9] == (0.25, 27.0, 28.0, 26.0, 120.0)
    metadata = [
        json.loads(modis_params[6]),
        json.loads(smap_params[5]),
        json.loads(sentinel_params[6]),
        json.loads(era5_params[9]),
    ]
    assert [entry["temporal_reducer"] for entry in metadata] == [
        "mean", "mean", "median", "mean (temperature/soil); sum (precipitation)"
    ]
    assert [entry["spatial_reducer"] for entry in metadata] == ["mean"] * 4
    assert metadata[0]["value_units"]["lst_day_mean_6m"] == "degC"
    assert metadata[1]["value_units"]["soil_moisture_6m"] == "volume_fraction"
    assert metadata[2]["value_units"]["vh_median_6m"] == "dB"
    assert metadata[3]["value_units"]["precipitation_6m"] == "mm"


def test_gee_provider_write_failure_rolls_back_and_returns_error(monkeypatch) -> None:
    gee_climate, _audits = _install_fake_gee(monkeypatch)
    connection = _ClimateConnection(fail_insert=True)
    result = gee_climate.fetch_modis_lst(
        connection,
        "synthetic-location",
        {"west": -70.0, "south": 18.0, "east": -69.0, "north": 19.0},
    )
    assert result["status"] == "error"
    assert connection.commits == 0
    assert connection.rollbacks == 1


def test_climate_summary_migration_refuses_duplicates_and_adds_partial_keys() -> None:
    migration = CLIMATE_KEY_MIGRATION.read_text()
    assert migration.count("HAVING COUNT(*) > 1") == 4
    assert migration.count("WHERE plot_id IS NULL") == 8
    assert migration.count("CREATE UNIQUE INDEX IF NOT EXISTS") == 4
    assert "RAISE EXCEPTION" in migration
    assert "DELETE FROM" not in migration
    for index_name in (
        "uq_ncep_weather_location_source_date",
        "uq_modis_lst_location_source_date",
        "uq_smap_soil_moisture_location_source_date",
        "uq_sentinel1_sar_location_source_date",
    ):
        assert index_name in migration


def test_climate_batch_reports_provider_errors_as_failed() -> None:
    from services.ingestion import climate_data

    names = ("fetch_worldclim", "fetch_ncep", "fetch_modis", "fetch_smap", "fetch_sentinel1")
    originals = {name: getattr(climate_data, name) for name in names}
    try:
        for name in names:
            setattr(climate_data, name, lambda *_args: {"status": "error"})
        result = climate_data.run_all(object(), "synthetic-location")
    finally:
        for name, function in originals.items():
            setattr(climate_data, name, function)

    assert result["status"] == "error"
    assert result["failed"] == 5
    assert result["success"] == 0


def test_climate_cli_returns_failure_for_provider_error(monkeypatch) -> None:
    from services.ingestion import climate_data

    monkeypatch.setattr(climate_data, "get_db", lambda: _ClimateConnection())
    monkeypatch.setattr(climate_data, "print_json", lambda _result: None)
    monkeypatch.setattr(climate_data, "fetch_modis", lambda *_args: {"status": "error"})
    assert climate_data.main(["--modis", "--location-id", "12345678-1234-5678-1234-567812345678"]) == 1


def test_rs_job_schema_has_provider_constraint() -> None:
    content = SCHEMA.read_text()
    assert "chk_rs_job_provider" in content
    assert "'gee'" in content
    assert "'copernicus'" in content
