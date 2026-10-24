"""Console contract for saved location-scoped spatial autocorrelation."""

from pathlib import Path

CONSOLE = Path(__file__).parents[1] / "apps/operator-console/index.html"


def test_spatial_autocorrelation_panel_requires_geostatistics_read_grant():
    source = CONSOLE.read_text(encoding="utf-8")
    assert 'id="geostatistics-autocorrelation" hidden' in source
    assert 'scope.resource === "geostatistics" && scope.action === "read"' in source
    assert 'geostatisticsAutocorrelation.hidden = false' in source
    assert "Read-only saved Moran's I, Geary's C, and join-count summaries" in source
    assert "Interpretive notes, metadata, and point coordinates are omitted" in source


def test_spatial_autocorrelation_reader_is_scoped_bounded_and_text_only():
    source = CONSOLE.read_text(encoding="utf-8")
    start = source.index("async function loadGeostatisticsAutocorrelation(")
    end = source.index("function yieldMonitoringValue(", start)
    reader = source[start:end]
    assert '`/operator/api/geostatistics/${encodeURIComponent(locationId)}/autocorrelation?${params}`' in reader
    assert 'new URLSearchParams({ limit: "25", offset: String(offset) })' in reader
    assert 'credentials: "same-origin"' in reader
    assert 'cache: "no-store"' in reader
    assert "geostatisticsAutocorrelationLocations.has(locationId)" in reader
    assert "result.location_id !== locationId" in reader
    assert "result.items.length > 25" in reader
    assert "requestVersion !== geostatisticsAutocorrelationRequestVersion" in reader
    assert "locationId !== geostatisticsAutocorrelationLocation.value" in reader
    for field in (
        "property_key", "metric", "statistic_value", "expected_value", "p_value",
        "z_score", "n_samples", "spatial_weights_type", "distance_threshold",
        "k_neighbors", "computed_at",
    ):
        assert field in reader
    assert "interpretation" not in reader and "metadata" not in reader
    assert "textContent" in reader
    assert "innerHTML" not in reader


def test_spatial_cross_validation_is_grant_gated_bounded_and_advisory():
    source = CONSOLE.read_text(encoding="utf-8")
    assert 'id="geostatistics-cross-validation-rows"' in source
    assert 'id="geostatistics-cross-validation-more"' in source
    start = source.index("async function loadGeostatisticsCrossValidation(")
    end = source.index("async function loadGeostatisticsLocation(", start)
    reader = source[start:end]
    assert '`/operator/api/geostatistics/${encodeURIComponent(locationId)}/cross-validation?${params}`' in reader
    assert 'new URLSearchParams({ limit: "25", offset: String(offset) })' in reader
    assert 'credentials: "same-origin"' in reader
    assert 'cache: "no-store"' in reader
    assert "geostatisticsAutocorrelationLocations.has(locationId)" in reader
    assert "result.location_id !== locationId" in reader
    assert "requestVersion !== geostatisticsCrossValidationRequestVersion" in reader
    assert "locationId !== geostatisticsAutocorrelationLocation.value" in reader
    for field in (
        "property_key", "cv_strategy", "n_folds", "block_size_m", "mean_error",
        "mean_squared_error", "root_mean_squared_error", "mean_absolute_error",
        "r_squared", "computed_at",
    ):
        assert field in reader
    assert "fold_results" not in reader and "metadata" not in reader
    assert "innerHTML" not in reader
    assert "textContent" in reader
