"""Climate data ingestion tests."""

from pathlib import Path

SCHEMA = Path("schemas/postgres/077_telemetry_infrastructure.sql")
WORLDCLIM_SCHEMA = Path("schemas/postgres/074_dsm_soc_prediction.sql")
WORLDCLIM_KEY_MIGRATION = Path("schemas/postgres/397_worldclim_location_baseline_key.sql")
CLIMATE_KEY_MIGRATION = Path("schemas/postgres/428_climate_summary_idempotency.sql")
SIGNED_CLIMATE_MIGRATION = Path("schemas/postgres/713_signed_climate_summary_audit_parity.sql")
CLIMATE_V1_RETIREMENT_MIGRATION = Path("schemas/postgres/716_retire_climate_summary_v1_worker_grant.sql")


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


def test_climate_compatibility_selectors_use_the_signed_worker(monkeypatch) -> None:
    from services.ingestion import climate_data

    connection = object()
    worker_calls = []
    source_results = {
        "worldclim": {"status": "success", "record_id": "worldclim-id"},
        "era5_land": {"status": "success", "record_id": "era5-id"},
        "modis_lst": {"status": "success", "record_id": "modis-id"},
        "smap_moisture": {"status": "success", "record_id": "smap-id"},
        "sentinel1_sar": {"status": "success", "record_id": "sentinel-id"},
    }

    def dispatch(location_id, source=None):
        worker_calls.append((location_id, source))
        if source is None:
            return {
                "status": "success",
                "location_id": location_id,
                "results": {
                    key: source_results[key]
                    for key in climate_data._CLIMATE_SOURCE_KEYS
                },
                "success": 5,
                "skipped": 0,
                "failed": 0,
                "total": 5,
            }
        return {
            "status": "success",
            "location_id": location_id,
            "results": {source: source_results[source]},
        }

    monkeypatch.setattr(climate_data, "_dispatch_signed_climate_worker", dispatch)
    selectors = (
        (climate_data.fetch_worldclim, "worldclim"),
        (climate_data.fetch_ncep, "era5_land"),
        (climate_data.fetch_modis, "modis_lst"),
        (climate_data.fetch_smap, "smap_moisture"),
        (climate_data.fetch_sentinel1, "sentinel1_sar"),
    )
    for function, source in selectors:
        assert function(connection, "synthetic-location") == source_results[source]
    report = climate_data.run_all(connection, "synthetic-location")
    assert report["total"] == 5
    assert list(report["results"]) == ["worldclim", "ncep", "modis", "smap", "sentinel1"]
    assert report["results"]["ncep"] == source_results["era5_land"]
    assert worker_calls == [
        ("synthetic-location", "worldclim"),
        ("synthetic-location", "era5_land"),
        ("synthetic-location", "modis_lst"),
        ("synthetic-location", "smap_moisture"),
        ("synthetic-location", "sentinel1_sar"),
        ("synthetic-location", None),
    ]


def test_climate_application_modules_contain_no_summary_table_writers() -> None:
    climate_source = Path("services/ingestion/climate_data.py").read_text()
    gee_source = Path("services/ingestion/gee_climate.py").read_text()
    for table in (
        "worldclim_climate",
        "ncep_weather_summary",
        "modis_lst_summary",
        "smap_soil_moisture",
        "sentinel1_sar_summary",
    ):
        assert f"INSERT INTO {table}" not in climate_source
        assert f"INSERT INTO {table}" not in gee_source
        assert f"UPDATE {table}" not in climate_source
        assert f"UPDATE {table}" not in gee_source
    assert "get_db" not in climate_source
    assert "log_ingestion" not in gee_source


def test_signed_climate_migration_preserves_audit_hash_and_runtime_read_boundary() -> None:
    migration = SIGNED_CLIMATE_MIGRATION.read_text()
    assert "store_climate_summary_v2" in migration
    assert "public.digest(convert_to(legacy_audit_payload, 'UTF8'), 'sha256')" in migration
    assert "execution_duration_ms" in migration
    assert "0, processing_time_ms, '1.0.0'" in migration
    assert "FROM kokonut_runtime" in migration
    assert "CREATE OR REPLACE FUNCTION kokonut_security.climate_location" in migration
    assert "AND (location.center IS NOT NULL" not in migration
    for table in (
        "worldclim_climate",
        "ncep_weather_summary",
        "modis_lst_summary",
        "smap_soil_moisture",
        "sentinel1_sar_summary",
    ):
        assert table in migration
    assert "GRANT EXECUTE ON FUNCTION kokonut_security.store_climate_summary_v2" in migration


def test_legacy_climate_writer_is_unavailable_to_application_roles() -> None:
    migration = CLIMATE_V1_RETIREMENT_MIGRATION.read_text()

    assert migration.count("BEGIN;") == 1
    assert migration.count("COMMIT;") == 1
    assert "store_climate_summary_v2" in migration
    assert "REVOKE ALL ON FUNCTION kokonut_security.store_climate_summary(" in migration
    assert "FROM PUBLIC, kokonut_worker_execution, kokonut_runtime" in migration
    assert "kokonut_directus_runtime" in migration
    assert "FROM kokonut_directus_runtime" in migration
    assert "REVOKE ALL ON FUNCTION kokonut_security.store_climate_summary_v2" not in migration


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
    content = Path("services/ingestion/freshness_worker.py").read_text()
    assert "kokonut_security.list_freshness_configs" in content
    assert "FROM public.data_freshness_config" not in content


def test_freshness_inserts_check_results() -> None:
    content = Path("services/ingestion/freshness_worker.py").read_text()
    assert "kokonut_security.create_freshness_check" in content
    assert "INSERT INTO public.data_freshness_check" not in content


def test_freshness_has_alert_channels() -> None:
    content = Path("services/ingestion/freshness_worker.py").read_text()
    assert "kokonut_security.enqueue_freshness_event" in content
    migration = Path("schemas/postgres/645_isolated_data_freshness_worker.sql").read_text()
    assert "data_stale" in migration


def test_climate_data_pipeline_targets_all_tables() -> None:
    entrypoint = Path("services/ingestion/climate_data.py").read_text()
    gee_fetchers = Path("services/ingestion/gee_climate.py").read_text()
    worker = Path("services/ingestion/climate_worker.py").read_text()
    migration = SIGNED_CLIMATE_MIGRATION.read_text()

    for table in (
        "worldclim_climate",
        "ncep_weather_summary",
        "modis_lst_summary",
        "smap_soil_moisture",
        "sentinel1_sar_summary",
    ):
        assert table in migration
    assert "persist_summary" in gee_fetchers
    assert "_dispatch_signed_climate_worker" in entrypoint
    assert "store_climate_summary_v2" in worker


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


def _install_fake_gee(monkeypatch):
    from services.ingestion import gee_climate

    monkeypatch.setattr(
        gee_climate,
        "_get_gee_client",
        lambda *, worker_credentials=False: _FakeEarthEngine if worker_credentials else None,
    )
    records = []
    def persist(summary, payload):
        records.append((summary, payload))
        return f"record-{summary['source_key']}"

    return gee_climate, records, persist


def test_gee_provider_summaries_keep_the_legacy_output_and_audit_payload(monkeypatch) -> None:
    gee_climate, persisted, persist = _install_fake_gee(monkeypatch)
    location_id = "11111111-1111-4111-8111-111111111111"
    bbox = {"west": -70.0, "south": 18.0, "east": -69.0, "north": 19.0}
    checks = [
        (gee_climate.fetch_modis_lst, "modis_lst", "MODIS/061/MOD11A2"),
        (gee_climate.fetch_smap_moisture, "smap_moisture", "NASA/SMAP/SPL3SMP_E/006"),
        (gee_climate.fetch_sentinel1_sar, "sentinel1_sar", "COPERNICUS/S1_GRD"),
        (gee_climate.fetch_era5_land, "era5_land", "ECMWF/ERA5_LAND/DAILY_AGGR"),
    ]

    for fetcher, source_key, provider_id in checks:
        result = fetcher(
            None,
            location_id,
            bbox,
            worker_credentials=True,
            persist_summary=persist,
        )
        assert result["status"] == "success"
        assert result["record_id"] == f"record-{source_key}"
    assert len(persisted) == 4
    assert [summary["source_key"] for summary, _ in persisted] == [item[1] for item in checks]
    assert [summary["source_id"] for summary, _ in persisted] == [item[2] for item in checks]
    metadata = [summary["metadata"] for summary, _ in persisted]
    assert [entry["temporal_reducer"] for entry in metadata] == [
        "mean", "mean", "median", "mean (temperature/soil); sum (precipitation)"
    ]
    assert [entry["spatial_reducer"] for entry in metadata] == ["mean"] * 4
    assert metadata[0]["value_units"]["lst_day_mean_6m"] == "degC"
    assert metadata[1]["value_units"]["soil_moisture_6m"] == "volume_fraction"
    assert metadata[2]["value_units"]["vh_median_6m"] == "dB"
    assert metadata[3]["value_units"]["precipitation_6m"] == "mm"
    assert persisted[0][1] == {"lst_day_mean_6m_c": 26.85, "lst_night_mean_6m_c": 6.85}
    assert persisted[1][1] == {"soil_moisture_6m_volume_fraction": 0.28}
    assert persisted[2][1] == {"vh_median_6m_db": -18.4, "vv_median_6m_db": -11.2}
    assert persisted[3][1] == {
        "soil_moisture_6m_volume_fraction": 0.25,
        "mean_temp_6m_c": 27.0,
        "max_temp_6m_c": 28.0,
        "min_temp_6m_c": 26.0,
        "precipitation_6m_mm": 120.0,
    }


def test_gee_provider_requires_the_signed_persistence_callback(monkeypatch) -> None:
    gee_climate, _persisted, persist = _install_fake_gee(monkeypatch)
    result = gee_climate.fetch_modis_lst(
        None,
        "11111111-1111-4111-8111-111111111111",
        {"west": -70.0, "south": 18.0, "east": -69.0, "north": 19.0},
        worker_credentials=True,
    )
    assert result["status"] == "error"
    result = gee_climate.fetch_modis_lst(
        None,
        "11111111-1111-4111-8111-111111111111",
        {"west": -70.0, "south": 18.0, "east": -69.0, "north": 19.0},
        worker_credentials=True,
        persist_summary=persist,
    )
    assert result["status"] == "success"


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


def test_climate_batch_reports_provider_errors_as_failed(monkeypatch) -> None:
    from services.ingestion import climate_data

    report = {
        "status": "error",
        "location_id": "synthetic-location",
        "results": {key: {"status": "error"} for key in climate_data._CLIMATE_SOURCE_KEYS},
        "success": 0,
        "skipped": 0,
        "failed": 5,
        "total": 5,
    }
    assert climate_data._valid_worker_report(
        report,
        location_id="synthetic-location",
        expected_sources=set(climate_data._CLIMATE_SOURCE_KEYS),
        exit_code=1,
    )
    monkeypatch.setattr(climate_data, "_dispatch_signed_climate_worker", lambda *_args: report)
    result = climate_data.run_all(object(), "synthetic-location")

    assert result["status"] == "error"
    assert result["failed"] == 5
    assert result["total"] == 5
    assert set(result["results"]) == {"worldclim", "ncep", "modis", "smap", "sentinel1"}


def test_climate_cli_returns_failure_for_provider_error(monkeypatch) -> None:
    from services.ingestion import climate_data

    monkeypatch.setattr(
        climate_data,
        "_dispatch_signed_climate_source",
        lambda *_args: {"status": "error", "message": "signed climate worker is disabled"},
    )
    monkeypatch.setattr(climate_data, "print_json", lambda _result: None)
    assert climate_data.main(["--modis", "--location-id", "12345678-1234-5678-1234-567812345678"]) == 1


def test_rs_job_schema_has_provider_constraint() -> None:
    content = SCHEMA.read_text()
    assert "chk_rs_job_provider" in content
    assert "'gee'" in content
    assert "'copernicus'" in content
