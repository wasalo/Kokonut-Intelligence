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
    assert "fold_diagnostics" in reader
    assert "fold.test_samples < 5" in reader
    assert "Show ${item.fold_diagnostics.length} spatial fold aggregates" in reader
    assert "Spatial-block fold aggregates" in source
    assert "held-out samples" in reader
    assert "innerHTML" not in reader
    assert "textContent" in reader


def test_variogram_panel_is_grant_gated_bounded_and_fixed_projection_only():
    source = CONSOLE.read_text(encoding="utf-8")
    assert 'id="geostatistics-variogram-rows"' in source
    assert "Stored spherical, exponential, Gaussian, and Matérn fit parameters" in source
    start = source.index("async function loadGeostatisticsVariograms(")
    end = source.index("function yieldMonitoringValue(", start)
    reader = source[start:end]
    assert '`/operator/api/geostatistics/${encodeURIComponent(locationId)}/variogram-models?${params}`' in reader
    assert 'new URLSearchParams({ limit: "25", offset: String(offset) })' in reader
    assert 'credentials: "same-origin"' in reader
    assert 'cache: "no-store"' in reader
    assert "geostatisticsAutocorrelationLocations.has(locationId)" in reader
    assert "result.location_id !== locationId" in reader
    assert "requestVersion !== geostatisticsVariogramRequestVersion" in reader
    assert "locationId !== geostatisticsAutocorrelationLocation.value" in reader
    for field in (
        "property_key", "model_type", "sill", "range", "nugget", "partial_sill",
        "lag_distance", "lag_tolerance", "bandwidth", "n_pairs", "r_squared", "fitted_at",
    ):
        assert field in reader
    assert "metadata" not in reader and "variogram_model_id" not in reader
    assert "innerHTML" not in reader
    assert "textContent" in reader


def test_sensor_network_panel_is_grant_gated_bounded_and_advisory():
    source = CONSOLE.read_text(encoding="utf-8")
    assert 'id="geostatistics-sensor-design-rows"' in source
    assert "Saved spacing and coverage estimates by measured property" in source
    start = source.index("async function loadGeostatisticsSensorDesigns(")
    end = source.index("function yieldMonitoringValue(", start)
    reader = source[start:end]
    assert '`/operator/api/geostatistics/${encodeURIComponent(locationId)}/sensor-network-designs?${params}`' in reader
    assert 'new URLSearchParams({ limit: "25", offset: String(offset) })' in reader
    assert 'credentials: "same-origin"' in reader
    assert 'cache: "no-store"' in reader
    assert "geostatisticsAutocorrelationLocations.has(locationId)" in reader
    assert "result.location_id !== locationId" in reader
    assert "requestVersion !== geostatisticsSensorDesignRequestVersion" in reader
    assert "locationId !== geostatisticsAutocorrelationLocation.value" in reader
    for field in (
        "property_key", "optimal_spacing_m", "coverage_radius_m",
        "recommended_n_sensors", "current_n_sensors", "coverage_gap_pct",
        "confidence_level", "computed_at",
    ):
        assert field in reader
    assert "notes" not in reader and "metadata" not in reader
    assert "variogram_model_id" not in reader
    assert "innerHTML" not in reader
    assert "textContent" in reader


def test_kriging_panel_is_grant_gated_bounded_and_aggregate_only():
    source = CONSOLE.read_text(encoding="utf-8")
    assert 'id="geostatistics-kriging-rows"' in source
    assert "Individual predictions, uncertainty point records, coordinates, and model identifiers are omitted" in source
    start = source.index("async function loadGeostatisticsKrigingSummaries(")
    end = source.index("function yieldMonitoringValue(", start)
    reader = source[start:end]
    assert '`/operator/api/geostatistics/${encodeURIComponent(locationId)}/kriging-summaries?${params}`' in reader
    assert 'new URLSearchParams({ limit: "25", offset: String(offset) })' in reader
    assert 'credentials: "same-origin"' in reader
    assert 'cache: "no-store"' in reader
    assert "geostatisticsAutocorrelationLocations.has(locationId)" in reader
    assert "result.location_id !== locationId" in reader
    assert "requestVersion !== geostatisticsKrigingRequestVersion" in reader
    assert "locationId !== geostatisticsAutocorrelationLocation.value" in reader
    for field in (
        "property_key", "method", "grid_resolution_m", "n_points",
        "result_point_count", "mean_predicted", "mean_variance", "mean_std",
        "min_predicted", "max_predicted", "created_at",
    ):
        assert field in reader
    assert "point_geometry" not in reader and "metadata" not in reader
    assert "innerHTML" not in reader
    assert "textContent" in reader


def test_realization_panel_is_grant_gated_bounded_and_aggregate_only():
    source = CONSOLE.read_text(encoding="utf-8")
    assert 'id="geostatistics-realization-rows"' in source
    assert "Point pages are available on demand" in source
    start = source.index("async function loadGeostatisticsRealizationSummaries(")
    end = source.index("function yieldMonitoringValue(", start)
    reader = source[start:end]
    assert '`/operator/api/geostatistics/${encodeURIComponent(locationId)}/realization-summaries?${params}`' in reader
    assert 'new URLSearchParams({ limit: "25", offset: String(offset) })' in reader
    assert 'credentials: "same-origin"' in reader
    assert 'cache: "no-store"' in reader
    assert "geostatisticsAutocorrelationLocations.has(locationId)" in reader
    assert "result.location_id !== locationId" in reader
    assert "requestVersion !== geostatisticsRealizationRequestVersion" in reader
    assert "locationId !== geostatisticsAutocorrelationLocation.value" in reader
    for field in (
        "property_key", "realization_number", "method", "grid_resolution_m",
        "n_points", "result_point_count", "mean_simulated_value",
        "stddev_simulated_value", "min_simulated_value", "max_simulated_value",
        "created_at",
    ):
        assert field in reader
    assert "point_geometry" not in reader and "metadata" not in reader
    assert "innerHTML" not in reader
    assert "textContent" in reader


def test_realization_point_reader_is_bounded_scoped_and_text_only():
    source = CONSOLE.read_text(encoding="utf-8")
    assert 'id="geostatistics-realization-points" hidden' in source
    assert 'id="geostatistics-realization-points-more"' in source
    assert 'pointsButton.textContent = "View points"' in source
    start = source.index("async function loadGeostatisticsRealizationPoints(")
    end = source.index("function yieldMonitoringValue(", start)
    reader = source[start:end]
    assert '`/operator/api/geostatistics/${encodeURIComponent(locationId)}/realizations/${encodeURIComponent(realizationId)}/points?${params}`' in reader
    assert 'new URLSearchParams({ limit: "50", offset: String(offset) })' in reader
    assert 'credentials: "same-origin"' in reader
    assert 'cache: "no-store"' in reader
    assert "geostatisticsAutocorrelationLocations.has(locationId)" in reader
    assert "result.location_id !== locationId" in reader
    assert "result.realization_id !== realizationId" in reader
    assert "requestVersion !== geostatisticsRealizationPointRequestVersion" in reader
    assert "locationId !== geostatisticsAutocorrelationLocation.value" in reader
    assert "realizationId !== geostatisticsSelectedRealizationId" in reader
    for field in ("point_number", "longitude", "latitude", "simulated_value"):
        assert field in reader
    assert "innerHTML" not in reader
    assert "textContent" in reader
