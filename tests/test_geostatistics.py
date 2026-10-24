"""Tests for Geostatistics Suite — variogram, kriging, simulation,
autocorrelation, cross-validation, sensor optimization, CLI, and SOC integration.
"""

from __future__ import annotations

import importlib
import uuid
from unittest.mock import MagicMock, patch

import numpy as np
import pytest


def _make_mock_conn(mock_cursor):
    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    return mock_conn


def _make_spatial_data(n=30, seed=42):
    """Generate synthetic spatial data with known structure."""
    rng = np.random.RandomState(seed)
    coords = rng.uniform(0, 1000, (n, 2))
    # Spatially correlated field: values = f(distance from center) + noise
    center = np.array([500.0, 500.0])
    dists = np.sqrt(np.sum((coords - center) ** 2, axis=1))
    values = 10.0 * np.exp(-dists / 500.0) + rng.normal(0, 0.5, n)
    return coords.tolist(), values.tolist()


@pytest.mark.parametrize(
    ("property_key", "column"),
    [
        ("soil_carbon", "organic_carbon_pct"),
        ("soil_moisture", "moisture_pct"),
        ("soil_ph", "ph"),
    ],
)
def test_shared_geostat_source_query_uses_fixed_soil_columns(property_key, column):
    from services.geostatistics.data_sources import location_point_query

    query, params = location_point_query("location-a", property_key)

    assert f"ss.{column} AS value" in query
    assert "ss.location_id = %s" in query
    assert params == ("location-a",)


def test_shared_geostat_source_query_uses_location_scoped_ndvi():
    from services.geostatistics.data_sources import location_point_query

    query, params = location_point_query("location-a", "ndvi")

    assert "remote_sensing_observation rso" in query
    assert "rso.location_id = %s" in query
    assert "rso.ndvi AS value" in query
    assert params == ("location-a",)


@pytest.mark.parametrize(
    ("module_name", "class_name", "method_name"),
    [
        ("services.geostatistics.variogram", "VariogramAnalyzer", "fit_from_db"),
        ("services.geostatistics.autocorrelation", "SpatialAutocorrelation", "autocorrelation_from_db"),
        ("services.geostatistics.kriging", "KrigingEngine", "kriging_from_db"),
        ("services.geostatistics.simulation", "GeostatSimulator", "simulation_from_db"),
        ("services.geostatistics.cross_validation", "SpatialCrossValidator", "cross_validate_from_db"),
    ],
)
def test_geostat_database_pipelines_reject_unknown_property_before_connecting(
    module_name, class_name, method_name
):
    module = importlib.import_module(module_name)
    connection = MagicMock()
    service = getattr(module, class_name)(conn=connection)

    result = getattr(service, method_name)("location-a", "soil_nitrogen")

    assert result == {"error": "Unsupported property_key: soil_nitrogen"}
    connection.cursor.assert_not_called()


@pytest.mark.parametrize(
    ("module_name", "class_name", "method_name"),
    [
        ("services.geostatistics.kriging", "KrigingEngine", "kriging_from_db"),
        ("services.geostatistics.simulation", "GeostatSimulator", "simulation_from_db"),
    ],
)
def test_explicit_variogram_selection_is_location_and_property_scoped(
    module_name, class_name, method_name
):
    module = importlib.import_module(module_name)
    connection = MagicMock()
    cursor = connection.cursor.return_value
    cursor.fetchone.return_value = None
    service = getattr(module, class_name)(conn=connection)

    result = getattr(service, method_name)(
        "location-a", "soil_carbon", variogram_model_id="model-from-other-scope"
    )

    query, params = cursor.execute.call_args.args
    assert "FROM variogram_model" in query
    assert "WHERE id = %s" in query
    assert "AND location_id = %s" in query
    assert "AND property_key = %s" in query
    assert params == ("model-from-other-scope", "location-a", "soil_carbon")
    assert result == {
        "error": "Variogram model not found for requested location and property"
    }
    assert cursor.execute.call_count == 1
    cursor.close.assert_called_once()


class TestVariogramAnalyzer:
    def _make_analyzer(self):
        from services.geostatistics.variogram import VariogramAnalyzer
        mock_cursor = MagicMock()
        mock_conn = _make_mock_conn(mock_cursor)
        return VariogramAnalyzer(conn=mock_conn), mock_cursor

    def test_compute_empirical_variogram_returns_structure(self):
        analyzer, _ = self._make_analyzer()
        coords, values = _make_spatial_data()
        result = analyzer.compute_empirical_variogram(values, coords, lag_distance=100.0)
        assert "lags" in result
        assert "semivariances" in result
        assert "n_pairs" in result
        assert len(result["lags"]) == len(result["semivariances"])

    def test_empirical_variogram_uses_lag_distance_bins_and_pair_counts(self):
        from services.geostatistics.variogram import VariogramAnalyzer

        coordinates = [(float(x), 0.0) for x in range(0, 100, 10)]
        values = [float(x // 10) for x in range(0, 100, 10)]
        result = VariogramAnalyzer(conn=MagicMock()).compute_empirical_variogram(
            values, coordinates, lag_distance=20, lag_tolerance=10, bandwidth=1000
        )

        assert result["lags"] == pytest.approx([10.0, 24.6666667, 40.0])
        assert result["semivariances"] == pytest.approx([0.5, 3.1666667, 8.0])
        assert result["n_pairs"] == [9, 15, 6]

    def test_empirical_variogram_tolerance_filters_pairs_around_bin_center(self):
        from services.geostatistics.variogram import VariogramAnalyzer

        coordinates = [(float(x), 0.0) for x in range(0, 100, 10)]
        values = [float(x // 10) for x in range(0, 100, 10)]
        result = VariogramAnalyzer(conn=MagicMock()).compute_empirical_variogram(
            values, coordinates, lag_distance=20, lag_tolerance=2.0, bandwidth=1000
        )

        assert result["lags"] == pytest.approx([10.0, 30.0])
        assert result["n_pairs"] == [9, 7]

    def test_empirical_variogram_bandwidth_caps_pair_distance(self):
        from services.geostatistics.variogram import VariogramAnalyzer

        coordinates = [(float(x), 0.0) for x in range(0, 100, 10)]
        values = [float(x // 10) for x in range(0, 100, 10)]
        result = VariogramAnalyzer(conn=MagicMock()).compute_empirical_variogram(
            values, coordinates, lag_distance=20, lag_tolerance=10, bandwidth=25
        )

        assert result["lags"] == pytest.approx([10.0, 20.0])
        assert result["n_pairs"] == [9, 8]

    def test_empirical_variogram_rejects_overlapping_tolerance(self):
        from services.geostatistics.variogram import VariogramAnalyzer

        result = VariogramAnalyzer(conn=MagicMock()).compute_empirical_variogram(
            [float(i) for i in range(10)],
            [(float(i), 0.0) for i in range(10)],
            lag_distance=20,
            lag_tolerance=10.1,
        )

        assert result == {"error": "Invalid lag distance, tolerance, or bandwidth"}

    def test_compute_empirical_variogram_insufficient_samples(self):
        analyzer, _ = self._make_analyzer()
        coords, values = _make_spatial_data(n=5)
        result = analyzer.compute_empirical_variogram(values, coords)
        assert "error" in result

    def test_fit_variogram_model_exponential(self):
        from services.geostatistics.variogram import VariogramAnalyzer
        analyzer = VariogramAnalyzer(conn=MagicMock())
        coords, values = _make_spatial_data()
        empirical = analyzer.compute_empirical_variogram(values, coords, lag_distance=100.0)
        result = analyzer.fit_variogram_model(empirical, model_type="exponential")
        assert "sill" in result
        assert "range" in result
        assert "nugget" in result
        assert result["model_type"] == "exponential"
        assert result["sill"] >= 0
        assert result["range"] > 0

    def test_fit_variogram_model_spherical(self):
        from services.geostatistics.variogram import VariogramAnalyzer
        analyzer = VariogramAnalyzer(conn=MagicMock())
        coords, values = _make_spatial_data()
        empirical = analyzer.compute_empirical_variogram(values, coords, lag_distance=100.0)
        result = analyzer.fit_variogram_model(empirical, model_type="spherical")
        assert result["model_type"] == "spherical"
        assert result["sill"] >= 0

    def test_fit_variogram_model_gaussian(self):
        from services.geostatistics.variogram import VariogramAnalyzer
        analyzer = VariogramAnalyzer(conn=MagicMock())
        coords, values = _make_spatial_data()
        empirical = analyzer.compute_empirical_variogram(values, coords, lag_distance=100.0)
        result = analyzer.fit_variogram_model(empirical, model_type="gaussian")
        assert result["model_type"] == "gaussian"

    @pytest.mark.parametrize("model_type", ["spherical", "exponential", "gaussian", "matern"])
    def test_fit_variogram_model_recovers_synthetic_parameters(self, model_type):
        import gstools

        from services.geostatistics.variogram import VariogramAnalyzer

        model_classes = {
            "spherical": gstools.Spherical,
            "exponential": gstools.Exponential,
            "gaussian": gstools.Gaussian,
            "matern": gstools.Matern,
        }
        expected = {"sill": 4.3, "range": 250.0, "nugget": 0.3}
        truth = model_classes[model_type](
            dim=2,
            var=expected["sill"] - expected["nugget"],
            len_scale=expected["range"],
            nugget=expected["nugget"],
        )
        lags = np.linspace(20.0, 1000.0, 40)
        empirical = {"lags": lags, "semivariances": truth.variogram(lags)}

        result = VariogramAnalyzer(conn=MagicMock()).fit_variogram_model(
            empirical, model_type=model_type
        )

        assert result["model_type"] == model_type
        assert result["sill"] == pytest.approx(expected["sill"], rel=1e-4)
        assert result["range"] == pytest.approx(expected["range"], rel=1e-4)
        assert result["nugget"] == pytest.approx(expected["nugget"], rel=1e-4)
        assert result["r_squared"] == pytest.approx(1.0)

    def test_fit_variogram_model_discards_nonfinite_bins(self):
        import gstools

        from services.geostatistics.variogram import VariogramAnalyzer

        lags = np.linspace(20.0, 1000.0, 10)
        semivariances = gstools.Exponential(
            dim=2, var=4.0, len_scale=250.0, nugget=0.3
        ).variogram(lags)
        semivariances[4] = np.nan
        result = VariogramAnalyzer(conn=MagicMock()).fit_variogram_model(
            {"lags": lags, "semivariances": semivariances},
            model_type="exponential",
        )

        assert result["n_lags"] == 9
        assert np.isfinite(result["r_squared"])

    def test_fit_variogram_model_unknown_type(self):
        from services.geostatistics.variogram import VariogramAnalyzer
        analyzer = VariogramAnalyzer(conn=MagicMock())
        empirical = {"lags": [1, 2, 3], "semivariances": [1, 2, 3], "error": None}
        result = analyzer.fit_variogram_model(empirical, model_type="unknown")
        assert "error" in result

    def test_fit_variogram_one_step(self):
        from services.geostatistics.variogram import VariogramAnalyzer
        analyzer = VariogramAnalyzer(conn=MagicMock())
        coords, values = _make_spatial_data()
        result = analyzer.fit_variogram(values, coords, model_type="exponential")
        assert "sill" in result
        assert "range" in result
        assert "lags" in result

    def test_fit_variogram_returns_r_squared(self):
        from services.geostatistics.variogram import VariogramAnalyzer
        analyzer = VariogramAnalyzer(conn=MagicMock())
        coords, values = _make_spatial_data()
        result = analyzer.fit_variogram(values, coords)
        assert "r_squared" in result
        assert isinstance(result["r_squared"], float)

    def test_persist_variogram_returns_id(self):
        analyzer, mock_cursor = self._make_analyzer()
        mock_cursor.execute = MagicMock()
        result = {
            "model_type": "exponential",
            "sill": 2.5,
            "range": 500.0,
            "nugget": 0.1,
            "partial_sill": 2.4,
            "r_squared": 0.85,
        }
        model_id = analyzer.persist_variogram(
            str(uuid.uuid4()), "soil_carbon", result
        )
        assert model_id is not None
        assert len(model_id) == 36  # UUID format

    def test_persist_variogram_error_returns_none(self):
        analyzer, _ = self._make_analyzer()
        result = {"error": "something failed"}
        model_id = analyzer.persist_variogram("loc1", "soil_carbon", result)
        assert model_id is None


class TestKrigingEngine:
    def _make_engine(self):
        from services.geostatistics.kriging import KrigingEngine
        mock_cursor = MagicMock()
        mock_conn = _make_mock_conn(mock_cursor)
        return KrigingEngine(conn=mock_conn), mock_cursor

    def test_ordinary_kriging_returns_predictions(self):
        engine, _ = self._make_engine()
        coords, values = _make_spatial_data()
        variogram = {"model_type": "exponential", "sill": 2.5, "range": 500.0, "nugget": 0.1}
        result = engine.ordinary_kriging(coords, values, variogram, resolution_m=200.0)
        assert "predicted_values" in result
        assert "prediction_variance" in result
        assert result["method"] == "ordinary"
        assert len(result["predicted_values"]) > 0

    def test_ordinary_kriging_prediction_variance_nonnegative(self):
        engine, _ = self._make_engine()
        coords, values = _make_spatial_data()
        variogram = {"model_type": "exponential", "sill": 2.5, "range": 500.0, "nugget": 0.1}
        result = engine.ordinary_kriging(coords, values, variogram, resolution_m=200.0)
        variances = np.array(result["prediction_variance"])
        assert np.all(variances >= -1e-10)  # Allow tiny floating point errors

    def test_simple_kriging_returns_predictions(self):
        engine, _ = self._make_engine()
        coords, values = _make_spatial_data()
        variogram = {"model_type": "exponential", "sill": 2.5, "range": 500.0, "nugget": 0.1}
        result = engine.simple_kriging(coords, values, variogram, resolution_m=200.0)
        assert "predicted_values" in result
        assert result["method"] == "simple"
        assert "global_mean" in result

    def test_indicator_kriging_returns_probabilities(self):
        engine, _ = self._make_engine()
        coords, values = _make_spatial_data()
        variogram = {"model_type": "exponential", "sill": 2.5, "range": 500.0, "nugget": 0.1}
        result = engine.indicator_kriging(coords, values, variogram, threshold=5.0, resolution_m=200.0)
        assert "predicted_values" in result
        assert result["method"] == "indicator"
        preds = np.array(result["predicted_values"])
        assert np.all(preds >= 0.0)
        assert np.all(preds <= 1.0)

    def test_ordinary_kriging_custom_grid(self):
        engine, _ = self._make_engine()
        coords, values = _make_spatial_data()
        variogram = {"model_type": "exponential", "sill": 2.5, "range": 500.0, "nugget": 0.1}
        custom_grid = np.array([[0, 0], [500, 500], [1000, 1000]])
        result = engine.ordinary_kriging(coords, values, variogram, grid=custom_grid)
        assert len(result["predicted_values"]) == 3

    @pytest.mark.parametrize("method", ["ordinary", "simple", "indicator"])
    def test_kriging_honors_max_neighbors_and_search_radius(self, method):
        engine, _ = self._make_engine()
        coords = [(0.0, 0.0), (10.0, 0.0), (100.0, 0.0)]
        values = [0.0, 10.0, 100.0]
        variogram = {"model_type": "exponential", "sill": 2.5, "range": 100.0, "nugget": 0.1}
        grid = np.asarray([[5.0, 0.0], [1000.0, 0.0]])
        krige = getattr(engine, f"{method}_kriging")
        extra = {"threshold": 5.0} if method == "indicator" else {}

        limited = krige(
            coords, values, variogram, grid=grid, max_neighbors=1,
            search_radius=5.0, **extra,
        )
        expanded = krige(
            coords, values, variogram, grid=grid, max_neighbors=2,
            search_radius=5.0, **extra,
        )

        assert limited["neighbor_counts"] == [1, 0]
        assert expanded["neighbor_counts"] == [2, 0]
        assert limited["n_estimated_points"] == expanded["n_estimated_points"] == 1
        assert limited["predicted_values"][1] is None
        assert limited["prediction_variance"][1] is None
        if method in {"ordinary", "indicator"}:
            assert limited["predicted_values"][0] != pytest.approx(
                expanded["predicted_values"][0]
            )

    @pytest.mark.parametrize(
        ("kwargs", "message"),
        [
            ({"max_neighbors": 0}, "max_neighbors must be a positive integer"),
            ({"max_neighbors": 1.5}, "max_neighbors must be a positive integer"),
            ({"search_radius": float("inf")}, "search_radius must be finite and greater than zero"),
            ({"resolution_m": 0}, "resolution_m must be finite and greater than zero"),
        ],
    )
    def test_kriging_rejects_invalid_controls(self, kwargs, message):
        engine, _ = self._make_engine()
        coords, values = _make_spatial_data()
        variogram = {"model_type": "exponential", "sill": 2.5, "range": 500.0, "nugget": 0.1}

        result = engine.ordinary_kriging(coords, values, variogram, **kwargs)

        assert result == {"error": message}

    def test_ordinary_kriging_accepts_a_pure_nugget_model(self):
        engine, _ = self._make_engine()

        result = engine.ordinary_kriging(
            [(0.0, 0.0), (10.0, 0.0)],
            [1.0, 2.0],
            {"model_type": "exponential", "sill": 1.0, "range": 10.0, "nugget": 1.0},
            grid=[[5.0, 0.0]],
            max_neighbors=2,
            search_radius=20.0,
        )

        assert result["predicted_values"] == pytest.approx([1.5])
        assert result["neighbor_counts"] == [2]

    def test_ordinary_kriging_rejects_unknown_variogram_type(self):
        engine, _ = self._make_engine()
        coords, values = _make_spatial_data()

        result = engine.ordinary_kriging(
            coords,
            values,
            {"model_type": "unknown", "sill": 2.5, "range": 500.0, "nugget": 0.1},
        )

        assert result == {"error": "Invalid variogram model"}

    def test_persist_kriging_returns_id(self):
        engine, mock_cursor = self._make_engine()
        mock_cursor.execute = MagicMock()
        result = {
            "predicted_values": [1.0, 2.0, 3.0],
            "prediction_variance": [0.1, 0.2, 0.3],
            "grid_points": [[0, 0], [100, 100], [200, 200]],
            "n_points": 3,
            "method": "ordinary",
            "resolution_m": 10.0,
            "coordinate_origin": {"latitude": 18.5, "longitude": -69.9},
        }
        pred_id = engine.persist_kriging("loc1", "soil_carbon", "vm1", result)
        assert pred_id is not None
        point_insert = next(
            call for call in mock_cursor.execute.call_args_list
            if "ST_SetSRID" in call.args[0]
        )
        assert point_insert.args[1][2:4] == pytest.approx((-69.9, 18.5))

    def test_persist_kriging_requires_geographic_origin_before_database_access(self):
        engine, _ = self._make_engine()
        result = {
            "predicted_values": [1.0],
            "prediction_variance": [0.1],
            "grid_points": [[0.0, 0.0]],
            "n_points": 1,
            "method": "ordinary",
            "resolution_m": 10.0,
        }

        assert engine.persist_kriging("loc1", "soil_carbon", "vm1", result) is None
        engine._conn.cursor.assert_not_called()

    def test_persist_kriging_skips_cells_without_local_estimates(self):
        engine, mock_cursor = self._make_engine()
        result = {
            "predicted_values": [1.0, None],
            "prediction_variance": [0.1, None],
            "grid_points": [[0.0, 0.0], [1000.0, 1000.0]],
            "n_points": 2,
            "method": "ordinary",
            "resolution_m": 10.0,
            "coordinate_origin": {"latitude": 18.5, "longitude": -69.9},
        }

        assert engine.persist_kriging("loc1", "soil_carbon", "vm1", result)
        point_inserts = [
            call for call in mock_cursor.execute.call_args_list
            if "ST_SetSRID" in call.args[0]
        ]
        assert len(point_inserts) == 1

    def test_persist_kriging_error_returns_none(self):
        engine, _ = self._make_engine()
        result = {"error": "failed"}
        pred_id = engine.persist_kriging("loc1", "soil_carbon", "vm1", result)
        assert pred_id is None

    def test_invalid_method_returns_error(self):
        engine, _ = self._make_engine()
        coords, values = _make_spatial_data()
        variogram = {"model_type": "exponential", "sill": 2.5, "range": 500.0, "nugget": 0.1}
        result = engine.ordinary_kriging(coords, values, variogram)
        # Should work; invalid method check is at kriging_from_db level
        assert "predicted_values" in result


class TestGeostatSimulator:
    def _make_simulator(self):
        from services.geostatistics.simulation import GeostatSimulator
        mock_cursor = MagicMock()
        mock_conn = _make_mock_conn(mock_cursor)
        return GeostatSimulator(conn=mock_conn), mock_cursor

    def test_sgs_returns_realizations(self):
        simulator, _ = self._make_simulator()
        coords, values = _make_spatial_data(n=15)
        variogram = {"model_type": "exponential", "sill": 2.5, "range": 500.0, "nugget": 0.1}
        result = simulator.sequential_gaussian_simulation(
            coords, values, variogram, n_realizations=2, grid_resolution_m=300.0
        )
        assert "realizations" in result
        assert result["n_realizations"] == 2
        assert len(result["realizations"]) == 2

    def test_sgs_returns_e_type(self):
        simulator, _ = self._make_simulator()
        coords, values = _make_spatial_data(n=15)
        variogram = {"model_type": "exponential", "sill": 2.5, "range": 500.0, "nugget": 0.1}
        result = simulator.sequential_gaussian_simulation(
            coords, values, variogram, n_realizations=2, grid_resolution_m=300.0
        )
        assert "e_type" in result
        assert "p10" in result
        assert "p50" in result
        assert "p90" in result

    def test_sgs_realizations_consistent_shape(self):
        simulator, _ = self._make_simulator()
        coords, values = _make_spatial_data(n=15)
        variogram = {"model_type": "exponential", "sill": 2.5, "range": 500.0, "nugget": 0.1}
        result = simulator.sequential_gaussian_simulation(
            coords, values, variogram, n_realizations=2, grid_resolution_m=300.0
        )
        n_points = result["n_points"]
        for real in result["realizations"]:
            assert len(real) == n_points

    def test_sgs_reproducible_with_seed(self):
        simulator, _ = self._make_simulator()
        coords, values = _make_spatial_data(n=15)
        variogram = {"model_type": "exponential", "sill": 2.5, "range": 500.0, "nugget": 0.1}
        r1 = simulator.sequential_gaussian_simulation(
            coords, values, variogram, n_realizations=2, seed=123, grid_resolution_m=300.0
        )
        r2 = simulator.sequential_gaussian_simulation(
            coords, values, variogram, n_realizations=2, seed=123, grid_resolution_m=300.0
        )
        assert r1["realizations"][0] == r2["realizations"][0]

    def test_sgs_synthetic_conditional_moments_match_ordinary_kriging_reference(self):
        import gstools as gs

        simulator, _ = self._make_simulator()
        coordinates = np.asarray(
            [[0.0, 0.0], [100.0, 0.0], [0.0, 100.0], [100.0, 100.0]]
        )
        values = np.asarray([1.0, 2.0, 3.0, 4.0])
        variogram = {
            "model_type": "exponential",
            "sill": 2.5,
            "range": 100.0,
            "nugget": 0.0,
        }
        n_realizations = 512
        result = simulator.sequential_gaussian_simulation(
            coordinates.tolist(),
            values.tolist(),
            variogram,
            n_realizations=n_realizations,
            grid_resolution_m=100.0,
            seed=20261024,
        )

        assert "error" not in result
        grid = np.asarray(result["grid_points"])
        simulated = np.asarray(result["realizations"])
        model = simulator._build_gstools_variogram(
            variogram["model_type"], variogram["sill"],
            variogram["range"], variogram["nugget"],
        )
        kriging = gs.krige.Ordinary(
            model, [coordinates[:, 0], coordinates[:, 1]], values
        )
        expected_mean, expected_variance = kriging([grid[:, 0], grid[:, 1]])
        sample_mean = simulated.mean(axis=0)
        sample_variance = simulated.var(axis=0, ddof=1)

        assert simulated.shape == (n_realizations, len(grid))
        assert np.all(np.isfinite(simulated))
        mean_tolerance = 4 * np.sqrt(expected_variance / n_realizations) + 1e-8
        np.testing.assert_array_less(
            np.abs(sample_mean - expected_mean), mean_tolerance
        )
        variance_relative_tolerance = 4 * np.sqrt(2 / (n_realizations - 1))
        variance_tolerance = variance_relative_tolerance * expected_variance + 1e-8
        np.testing.assert_array_less(
            np.abs(sample_variance - expected_variance), variance_tolerance
        )

        for coordinate, observed_value in zip(coordinates, values):
            matching = np.flatnonzero(np.all(np.isclose(grid, coordinate), axis=1))
            assert len(matching) == 1
            np.testing.assert_allclose(
                simulated[:, matching[0]], observed_value, rtol=0, atol=2e-7
            )
        np.testing.assert_allclose(result["e_type"], sample_mean, rtol=0, atol=1e-12)
        np.testing.assert_allclose(
            result["p10"], np.percentile(simulated, 10, axis=0), rtol=0, atol=1e-12
        )
        np.testing.assert_allclose(
            result["p50"], np.percentile(simulated, 50, axis=0), rtol=0, atol=1e-12
        )
        np.testing.assert_allclose(
            result["p90"], np.percentile(simulated, 90, axis=0), rtol=0, atol=1e-12
        )

    def test_sgs_uses_conditional_random_fields_without_dense_grid_cholesky(self, monkeypatch):
        simulator, _ = self._make_simulator()
        coords, values = _make_spatial_data(n=15)
        variogram = {"model_type": "exponential", "sill": 2.5, "range": 500.0, "nugget": 0.1}

        def forbid_dense_cholesky(*_args, **_kwargs):
            raise AssertionError("dense grid covariance decomposition was called")

        monkeypatch.setattr(np.linalg, "cholesky", forbid_dense_cholesky)
        result = simulator.sequential_gaussian_simulation(
            coords, values, variogram, n_realizations=2, grid_resolution_m=300.0
        )

        assert "error" not in result
        assert result["simulation_engine"] == "gstools_conditional_random_field"
        assert len(result["realizations"]) == 2

    @pytest.mark.parametrize(
        ("kwargs", "message"),
        [
            ({"n_realizations": 0}, "n_realizations must be an integer from 1 to 1000"),
            ({"n_realizations": 1001}, "n_realizations must be an integer from 1 to 1000"),
            ({"grid_resolution_m": 0}, "grid_resolution_m must be finite and greater than zero"),
            ({"seed": -1}, "seed must be an integer between 0 and 4294967295"),
        ],
    )
    def test_sgs_rejects_invalid_settings(self, kwargs, message):
        simulator, _ = self._make_simulator()
        coords, values = _make_spatial_data(n=15)
        variogram = {"model_type": "exponential", "sill": 2.5, "range": 500.0, "nugget": 0.1}

        result = simulator.sequential_gaussian_simulation(
            coords, values, variogram, **kwargs
        )

        assert result == {"error": message}

    def test_sgs_caps_grid_size_before_random_field_generation(self, monkeypatch):
        import services.geostatistics.simulation as simulation_module

        simulator, _ = self._make_simulator()
        coords, values = _make_spatial_data(n=15)
        variogram = {"model_type": "exponential", "sill": 2.5, "range": 500.0, "nugget": 0.1}
        monkeypatch.setattr(simulation_module, "MAX_SGS_GRID_POINTS", 1)

        result = simulator.sequential_gaussian_simulation(
            coords, values, variogram, n_realizations=1, grid_resolution_m=300.0
        )

        assert "grid exceeds the 1-point limit" in result["error"]

    def test_sgs_caps_realization_output_size(self, monkeypatch):
        import services.geostatistics.simulation as simulation_module

        simulator, _ = self._make_simulator()
        coords, values = _make_spatial_data(n=15)
        variogram = {"model_type": "exponential", "sill": 2.5, "range": 500.0, "nugget": 0.1}
        monkeypatch.setattr(simulation_module, "MAX_SGS_OUTPUT_VALUES", 1)

        result = simulator.sequential_gaussian_simulation(
            coords, values, variogram, n_realizations=1, grid_resolution_m=300.0
        )

        assert "output exceeds the 1-value limit" in result["error"]

    @pytest.mark.parametrize(
        "variogram",
        [
            {"model_type": "unknown", "sill": 2.5, "range": 500.0, "nugget": 0.1},
            {"model_type": "exponential", "sill": 0.1, "range": 500.0, "nugget": 0.1},
        ],
    )
    def test_sgs_rejects_unsupported_or_degenerate_variogram(self, variogram):
        simulator, _ = self._make_simulator()
        coords, values = _make_spatial_data(n=15)

        result = simulator.sequential_gaussian_simulation(coords, values, variogram)

        assert result == {"error": "Invalid variogram model"}

    def test_compute_e_type(self):
        simulator, _ = self._make_simulator()
        realizations = [[1.0, 2.0, 3.0], [2.0, 3.0, 4.0], [3.0, 4.0, 5.0]]
        e_type = simulator.compute_e_type(realizations)
        assert e_type == [2.0, 3.0, 4.0]

    def test_compute_percentiles(self):
        simulator, _ = self._make_simulator()
        realizations = [[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]]
        pcts = simulator.compute_percentiles(realizations, [10, 50, 90])
        assert "p10" in pcts
        assert "p50" in pcts
        assert "p90" in pcts

    def test_persist_simulations_returns_id(self):
        simulator, mock_cursor = self._make_simulator()
        mock_cursor.execute = MagicMock()
        result = {
            "realizations": [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]],
            "grid_points": [[0, 0], [100, 100], [200, 200]],
            "n_points": 3,
            "n_realizations": 2,
            "grid_resolution_m": 100.0,
            "seed": 42,
            "coordinate_origin": {"latitude": 18.5, "longitude": -69.9},
        }
        real_id = simulator.persist_simulations(
            "loc1", "soil_carbon", "vm1", result,
            max_points=2, max_realizations=1,
        )
        assert real_id is not None
        run_inserts = [
            call for call in mock_cursor.execute.call_args_list
            if "INSERT INTO geostat_realization (" in call.args[0]
        ]
        point_inserts = [
            call for call in mock_cursor.execute.call_args_list
            if "ST_SetSRID" in call.args[0]
        ]
        assert len(run_inserts) == 1
        assert len(point_inserts) == 2
        assert point_inserts[0].args[1][2:4] == pytest.approx((-69.9, 18.5))
        assert point_inserts[1].args[1][2:4] == pytest.approx(
            (-69.9 + 200.0 / (111320.0 * np.cos(np.radians(18.5))), 18.5 + 200.0 / 111320.0)
        )

    def test_persist_simulations_requires_origin_before_database_access(self):
        simulator, _ = self._make_simulator()
        result = {
            "realizations": [[1.0]],
            "grid_points": [[0.0, 0.0]],
        }

        assert simulator.persist_simulations("loc1", "soil_carbon", "vm1", result) is None
        simulator._conn.cursor.assert_not_called()

    def test_persist_simulations_rejects_polar_projection_before_database_access(self):
        simulator, _ = self._make_simulator()
        result = {
            "realizations": [[1.0]],
            "grid_points": [[0.0, 0.0]],
            "coordinate_origin": {"latitude": 89.95, "longitude": 0.0},
        }

        assert simulator.persist_simulations("loc1", "soil_carbon", "vm1", result) is None
        simulator._conn.cursor.assert_not_called()

    def test_persist_simulations_error_returns_none(self):
        simulator, _ = self._make_simulator()
        result = {"error": "failed"}
        real_id = simulator.persist_simulations("loc1", "soil_carbon", "vm1", result)
        assert real_id is None


class TestSpatialAutocorrelation:
    def _make_sac(self):
        from services.geostatistics.autocorrelation import SpatialAutocorrelation
        mock_cursor = MagicMock()
        mock_conn = _make_mock_conn(mock_cursor)
        return SpatialAutocorrelation(conn=mock_conn), mock_cursor

    def test_build_spatial_weights_distance(self):
        sac, _ = self._make_sac()
        coords = [(0, 0), (100, 0), (200, 0), (1000, 1000)]
        W = sac.build_spatial_weights(coords, weights_type="distance", distance_threshold=300)
        assert W.shape == (4, 4)
        assert W[0, 1] == 1.0  # Within threshold
        assert W[0, 3] == 0.0  # Beyond threshold

    def test_build_spatial_weights_knn(self):
        sac, _ = self._make_sac()
        coords = [(0, 0), (100, 0), (200, 0), (300, 0)]
        W = sac.build_spatial_weights(coords, weights_type="knn", k_neighbors=2)
        assert W.shape == (4, 4)
        # Each point should have exactly 2 neighbors
        for i in range(4):
            assert np.sum(W[i]) == 2

    def test_compute_morans_i_clustered(self):
        sac, _ = self._make_sac()
        # Clustered data: nearby values are similar
        coords = [(0, 0), (100, 0), (200, 0), (0, 100), (100, 100), (200, 100)]
        values = [10, 10, 10, 20, 20, 20]
        result = sac.compute_morans_i(values, coords, weights_type="distance", distance_threshold=250)
        assert "statistic_value" in result
        assert result["interpretation"] in ("clustered", "random")

    def test_compute_morans_i_dispersed(self):
        sac, _ = self._make_sac()
        # Dispersed data: nearby values alternate
        coords = [(0, 0), (100, 0), (200, 0), (300, 0)]
        values = [10, 30, 10, 30]
        result = sac.compute_morans_i(values, coords, weights_type="distance", distance_threshold=150)
        assert "statistic_value" in result
        # Should be dispersed or random depending on threshold

    def test_compute_morans_i_insufficient_samples(self):
        sac, _ = self._make_sac()
        result = sac.compute_morans_i([1, 2], [(0, 0), (100, 0)])
        assert "error" in result

    def test_compute_gearys_c(self):
        sac, _ = self._make_sac()
        coords = [(0, 0), (100, 0), (200, 0), (0, 100), (100, 100), (200, 100)]
        values = [10, 10, 10, 20, 20, 20]
        result = sac.compute_gearys_c(values, coords, weights_type="distance", distance_threshold=250)
        assert "statistic_value" in result
        assert result["interpretation"] in ("clustered", "dispersed", "random")

    def test_persist_results(self):
        sac, mock_cursor = self._make_sac()
        mock_cursor.execute = MagicMock()
        result = {
            "morans_i": {
                "statistic_value": 0.45,
                "expected_value": -0.125,
                "z_score": 2.5,
                "p_value": 0.012,
                "n_samples": 10,
                "interpretation": "clustered",
                "weights_type": "queen",
            },
            "gearys_c": {
                "statistic_value": 0.6,
                "expected_value": 1.0,
                "z_score": -2.0,
                "p_value": 0.045,
                "n_samples": 10,
                "interpretation": "clustered",
                "weights_type": "queen",
            },
        }
        ids = sac.persist_results("loc1", "soil_carbon", result)
        assert len(ids) == 2

    def test_persist_results_error_returns_empty(self):
        sac, _ = self._make_sac()
        ids = sac.persist_results("loc1", "soil_carbon", {"error": "failed"})
        assert ids == []


class TestSpatialCrossValidator:
    def _make_cv(self):
        from services.geostatistics.cross_validation import SpatialCrossValidator
        mock_cursor = MagicMock()
        mock_conn = _make_mock_conn(mock_cursor)
        return SpatialCrossValidator(conn=mock_conn), mock_cursor

    def test_cross_validation_requires_variogram_model_location_and_property_match(self):
        cv, mock_cursor = self._make_cv()
        mock_cursor.fetchone.return_value = None

        result = cv.cross_validate_from_db(
            "location-a", "soil_carbon", variogram_model_id="model-from-other-scope"
        )

        query, params = mock_cursor.execute.call_args.args
        assert "WHERE id = %s" in query
        assert "AND location_id = %s" in query
        assert "AND property_key = %s" in query
        assert params == ("model-from-other-scope", "location-a", "soil_carbon")
        assert result == {
            "error": "Variogram model not found for requested location and property"
        }
        assert mock_cursor.execute.call_count == 1
        mock_cursor.close.assert_called_once()


    def test_cross_validation_uses_matching_model_and_location_scoped_points(self):
        cv, mock_cursor = self._make_cv()
        mock_cursor.fetchone.return_value = {
            "model_type": "exponential",
            "sill": 2.5,
            "range": 500.0,
            "nugget": 0.1,
        }
        mock_cursor.fetchall.return_value = [
            {"lat": 18.5 + index / 1000, "lon": -69.9 + index / 1000, "value": 1.0 + index}
            for index in range(4)
        ]
        cv.spatial_block_cv = MagicMock(return_value={"cv_strategy": "spatial_block"})

        result = cv.cross_validate_from_db(
            "location-a", "soil_carbon", variogram_model_id="model-a"
        )

        calls = mock_cursor.execute.call_args_list
        model_query, model_params = calls[0].args
        point_query, point_params = calls[1].args
        assert "AND location_id = %s" in model_query
        assert model_params == ("model-a", "location-a", "soil_carbon")
        assert "WHERE ss.location_id = %s" in point_query
        assert point_params == ("location-a",)
        assert result["location_id"] == "location-a"
        assert result["property_key"] == "soil_carbon"
        cv.spatial_block_cv.assert_called_once()
        mock_cursor.close.assert_called_once()

    def test_cross_validation_rejects_unknown_soil_property_before_connecting(self):
        cv, _ = self._make_cv()

        result = cv.cross_validate_from_db(
            "location-a", "soil_nitrogen", variogram_model_id="model-a"
        )

        assert result == {"error": "Unsupported property_key: soil_nitrogen"}
        cv._conn.cursor.assert_not_called()

    @pytest.mark.parametrize(
        ("property_key", "column"),
        [("soil_moisture", "moisture_pct"), ("soil_ph", "ph")],
    )
    def test_cross_validation_uses_the_selected_soil_property_column(self, property_key, column):
        cv, mock_cursor = self._make_cv()
        mock_cursor.fetchone.return_value = {
            "model_type": "exponential",
            "sill": 2.5,
            "range": 500.0,
            "nugget": 0.1,
        }
        mock_cursor.fetchall.return_value = [
            {"lat": 18.5 + index / 1000, "lon": -69.9 + index / 1000, "value": 1.0 + index}
            for index in range(4)
        ]
        cv.spatial_block_cv = MagicMock(return_value={"cv_strategy": "spatial_block"})

        result = cv.cross_validate_from_db(
            "location-a", property_key, variogram_model_id="model-a"
        )

        point_query, point_params = mock_cursor.execute.call_args_list[1].args
        assert f"ss.{column} AS value" in point_query
        assert "ss.organic_carbon_pct AS value" not in point_query
        assert point_params == ("location-a",)
        assert result["property_key"] == property_key

    def test_spatial_block_cv_returns_metrics(self):
        cv, _ = self._make_cv()
        coords, values = _make_spatial_data(n=30)
        variogram = {"model_type": "exponential", "sill": 2.5, "range": 500.0, "nugget": 0.1}
        result = cv.spatial_block_cv(coords, values, variogram, block_size_m=300.0)
        assert "root_mean_squared_error" in result
        assert "r_squared" in result
        assert result["cv_strategy"] == "spatial_block"

    def test_spatial_block_cv_insufficient_samples(self):
        cv, _ = self._make_cv()
        coords, values = _make_spatial_data(n=4)
        variogram = {"model_type": "exponential", "sill": 2.5, "range": 500.0, "nugget": 0.1}
        result = cv.spatial_block_cv(coords, values, variogram)
        assert "error" in result

    def test_leave_one_out_cv_returns_metrics(self):
        cv, _ = self._make_cv()
        coords, values = _make_spatial_data(n=10)
        variogram = {"model_type": "exponential", "sill": 2.5, "range": 500.0, "nugget": 0.1}
        result = cv.leave_one_out_cv(coords, values, variogram)
        assert "root_mean_squared_error" in result
        assert result["cv_strategy"] == "leave_one_out"

    def test_leave_one_out_aggregates_only_successful_prediction_pairs(self, monkeypatch):
        cv, _ = self._make_cv()
        coords, values = _make_spatial_data(n=5)
        coordinate_indexes = {tuple(coordinate): index for index, coordinate in enumerate(coords)}

        def predict(_train_coords, _train_values, test_coords, _variogram):
            index = coordinate_indexes[tuple(test_coords[0])]
            if index == 2:
                raise RuntimeError("synthetic middle-fold failure")
            return np.array([values[index] + 1.0]), np.array([0.25])

        monkeypatch.setattr(cv, "_kriging_predict", predict)
        result = cv.leave_one_out_cv(
            coords,
            values,
            {"model_type": "exponential", "sill": 2.5, "range": 500.0, "nugget": 0.1},
        )

        successful_actuals = np.array([value for index, value in enumerate(values) if index != 2])
        expected_r_squared = 1 - 4 / np.sum((successful_actuals - successful_actuals.mean()) ** 2)
        assert result["n_successful_folds"] == 4
        assert result["mean_error"] == 1.0
        assert result["mean_squared_error"] == 1.0
        assert result["root_mean_squared_error"] == 1.0
        assert result["mean_absolute_error"] == 1.0
        assert result["r_squared"] == round(float(expected_r_squared), 4)
        assert result["fold_results"][2]["error"] == (
            "spatial cross-validation fold failed (RuntimeError)"
        )

    def test_leave_one_out_cv_insufficient_samples(self):
        cv, _ = self._make_cv()
        coords, values = _make_spatial_data(n=3)
        variogram = {"model_type": "exponential", "sill": 2.5, "range": 500.0, "nugget": 0.1}
        result = cv.leave_one_out_cv(coords, values, variogram)
        assert "error" in result

    def test_persist_cv_results(self):
        cv, mock_cursor = self._make_cv()
        mock_cursor.execute = MagicMock()
        result = {
            "cv_strategy": "spatial_block",
            "n_folds": 5,
            "block_size_m": 200.0,
            "root_mean_squared_error": 1.23,
            "mean_absolute_error": 0.98,
            "r_squared": 0.75,
            "mean_error": 0.01,
        }
        record_id = cv.persist_cv_results("loc1", "soil_carbon", "vm1", result)
        assert record_id is not None

    def test_persist_cv_results_error_returns_none(self):
        cv, _ = self._make_cv()
        record_id = cv.persist_cv_results("loc1", "soil_carbon", None, {"error": "failed"})
        assert record_id is None


@pytest.mark.parametrize(
    "kwargs",
    [
        {"max_neighbors": 0},
        {"search_radius": 0},
        {"resolution_m": float("nan")},
        {"method": "indicator", "threshold": float("nan")},
    ],
)
def test_kriging_database_pipeline_rejects_invalid_settings_before_connecting(kwargs):
    from services.geostatistics.kriging import KrigingEngine

    connection = MagicMock()
    result = KrigingEngine(conn=connection).kriging_from_db(
        "location-a", "soil_carbon", **kwargs
    )

    assert "error" in result
    connection.cursor.assert_not_called()


def test_kriging_database_pipeline_forwards_neighborhood_settings():
    from services.geostatistics.kriging import KrigingEngine

    connection = MagicMock()
    cursor = connection.cursor.return_value
    cursor.fetchone.return_value = {
        "model_type": "exponential",
        "sill": 2.5,
        "range": 100.0,
        "nugget": 0.1,
        "partial_sill": 2.4,
        "r_squared": 0.8,
    }
    cursor.fetchall.return_value = [
        {"lat": 18.5, "lon": -69.9, "value": 1.0},
        {"lat": 18.501, "lon": -69.901, "value": 2.0},
        {"lat": 18.502, "lon": -69.902, "value": 3.0},
    ]
    engine = KrigingEngine(conn=connection)
    engine.ordinary_kriging = MagicMock(return_value={"n_points": 3})

    result = engine.kriging_from_db(
        "location-a", "soil_carbon", variogram_model_id="model-a",
        max_neighbors=7, search_radius=125.5,
    )

    engine.ordinary_kriging.assert_called_once()
    assert engine.ordinary_kriging.call_args.kwargs["max_neighbors"] == 7
    assert engine.ordinary_kriging.call_args.kwargs["search_radius"] == 125.5
    assert result["coordinate_origin"] == pytest.approx(
        {"latitude": 18.501, "longitude": -69.901}
    )


@pytest.mark.parametrize(
    "kwargs",
    [
        {"n_realizations": 0},
        {"n_realizations": 1001},
        {"grid_resolution_m": 0},
        {"seed": -1},
    ],
)
def test_simulation_database_pipeline_rejects_invalid_settings_before_connecting(kwargs):
    from services.geostatistics.simulation import GeostatSimulator

    connection = MagicMock()
    result = GeostatSimulator(conn=connection).simulation_from_db(
        "location-a", "soil_carbon", **kwargs
    )

    assert "error" in result
    connection.cursor.assert_not_called()


def test_simulation_database_pipeline_forwards_settings_and_geographic_origin():
    from services.geostatistics.simulation import GeostatSimulator

    connection = MagicMock()
    cursor = connection.cursor.return_value
    cursor.fetchone.return_value = {
        "model_type": "exponential", "sill": 2.5, "range": 100.0, "nugget": 0.1
    }
    cursor.fetchall.return_value = [
        {"lat": 18.5, "lon": -69.9, "value": 1.0},
        {"lat": 18.501, "lon": -69.901, "value": 2.0},
        {"lat": 18.502, "lon": -69.902, "value": 3.0},
    ]
    simulator = GeostatSimulator(conn=connection)
    simulator.sequential_gaussian_simulation = MagicMock(return_value={"n_points": 5})

    result = simulator.simulation_from_db(
        "location-a", "soil_carbon", variogram_model_id="model-a",
        n_realizations=7, grid_resolution_m=125.5, seed=44,
    )

    simulator.sequential_gaussian_simulation.assert_called_once()
    assert simulator.sequential_gaussian_simulation.call_args.kwargs == {
        "n_realizations": 7, "grid_resolution_m": 125.5, "seed": 44,
    }
    assert result["coordinate_origin"] == pytest.approx(
        {"latitude": 18.501, "longitude": -69.901}
    )


@pytest.mark.parametrize(
    ("invalid_fields", "error"),
    [
        ({"value": "invalid"}, "Simulation source contains invalid coordinates or values"),
        ({"lat": 90.1}, "Simulation source contains out-of-range coordinates"),
        ({"lat": 89.95}, "Simulation source is too close to a pole for local projection"),
    ],
)
def test_simulation_database_pipeline_rejects_invalid_source_before_simulation(
    invalid_fields, error
):
    from services.geostatistics.simulation import GeostatSimulator

    connection = MagicMock()
    cursor = connection.cursor.return_value
    cursor.fetchone.return_value = {
        "model_type": "exponential", "sill": 2.5, "range": 100.0, "nugget": 0.1
    }
    source_rows = [
        {"lat": 18.5, "lon": -69.9, "value": 1.0},
        {"lat": 18.501, "lon": -69.901, "value": 2.0},
        {"lat": 18.502, "lon": -69.902, "value": 3.0},
    ]
    source_rows[1].update(invalid_fields)
    cursor.fetchall.return_value = source_rows
    simulator = GeostatSimulator(conn=connection)
    simulator.sequential_gaussian_simulation = MagicMock()

    result = simulator.simulation_from_db(
        "location-a", "soil_carbon", variogram_model_id="model-a"
    )

    assert result == {"error": error}
    simulator.sequential_gaussian_simulation.assert_not_called()


class TestSensorNetworkDesigner:
    def _make_designer(self):
        from services.geostatistics.sensor_optimization import SensorNetworkDesigner
        mock_cursor = MagicMock()
        mock_conn = _make_mock_conn(mock_cursor)
        return SensorNetworkDesigner(conn=mock_conn), mock_cursor

    def test_compute_optimal_spacing(self):
        designer, _ = self._make_designer()
        result = designer.compute_optimal_spacing(500.0, confidence_level=0.95)
        assert "optimal_spacing_m" in result
        assert "coverage_radius_m" in result
        assert result["optimal_spacing_m"] < result["coverage_radius_m"]

    def test_compute_optimal_spacing_higher_confidence(self):
        designer, _ = self._make_designer()
        r95 = designer.compute_optimal_spacing(500.0, confidence_level=0.95)
        r99 = designer.compute_optimal_spacing(500.0, confidence_level=0.99)
        assert r99["optimal_spacing_m"] < r95["optimal_spacing_m"]

    def test_compute_coverage_map(self):
        designer, _ = self._make_designer()
        sensors = [(0, 0), (500, 0), (0, 500), (500, 500)]
        result = designer.compute_coverage_map(sensors, 300.0, grid_resolution_m=100.0)
        assert "coverage_scores" in result
        assert "stats" in result
        assert result["stats"]["total_grid_cells"] > 0

    def test_assess_current_network(self):
        designer, _ = self._make_designer()
        sensors = [(0, 0), (500, 0)]
        area = [(0, 0), (1000, 0), (1000, 1000), (0, 1000)]
        result = designer.assess_current_network(sensors, 500.0, area)
        assert "optimal_spacing_m" in result
        assert "recommended_n_sensors" in result
        assert "coverage_gap_pct" in result
        assert "recommendations" in result

    def test_generate_recommendations_add_sensors(self):
        designer, _ = self._make_designer()
        recs = designer._generate_recommendations(current_n=2, recommended_n=5, gap_pct=30)
        assert any("Add" in r for r in recs)

    def test_generate_recommendations_excellent_coverage(self):
        designer, _ = self._make_designer()
        recs = designer._generate_recommendations(current_n=5, recommended_n=5, gap_pct=2)
        assert any("excellent" in r.lower() for r in recs)

    def test_persist_design(self):
        designer, mock_cursor = self._make_designer()
        mock_cursor.execute = MagicMock()
        result = {
            "optimal_spacing_m": 250.0,
            "coverage_radius_m": 500.0,
            "recommended_n_sensors": 8,
            "current_n_sensors": 4,
            "coverage_gap_pct": 25.0,
            "variogram_model_id": "vm1",
        }
        record_id = designer.persist_design("loc1", "soil_moisture", result)
        assert record_id is not None


class TestCLI:
    def test_cli_help(self):
        """CLI should print help without error."""
        from services.geostatistics.cli import main
        with patch("sys.argv", ["geostatistics", "--help"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0

    def test_cli_no_command(self):
        """CLI with no command should print help."""
        from services.geostatistics.cli import main
        with patch("sys.argv", ["geostatistics"]):
            with patch("sys.stdout"):
                main()

    def test_cli_variogram_parser(self):
        """Variogram subcommand should parse arguments."""
        from services.geostatistics.cli import main
        with patch("sys.argv", ["geostatistics", "variogram", "--location-id", "test-loc", "--property", "soil_carbon"]):
            with patch("services.ingestion.base.get_db") as mock_db:
                mock_conn = MagicMock()
                mock_cursor = MagicMock()
                mock_cursor.fetchall.return_value = []
                mock_conn.cursor.return_value = mock_cursor
                mock_db.return_value = mock_conn
                with patch("sys.stdout"):
                    try:
                        main()
                    except Exception:
                        pass  # Expected when DB returns empty

    def test_cli_variogram_forwards_lag_settings(self):
        from services.geostatistics.cli import main
        from services.geostatistics.variogram import VariogramAnalyzer

        argv = [
            "geostatistics", "variogram", "--location-id", "test-loc",
            "--property", "soil_carbon", "--lag-distance", "20",
            "--lag-tolerance", "5", "--bandwidth", "200",
        ]
        with patch("sys.argv", argv), patch(
            "services.common.database.get_db", return_value=MagicMock()
        ), patch.object(
            VariogramAnalyzer, "fit_from_db", return_value={"error": "synthetic"}
        ) as fit_from_db, patch("services.geostatistics.cli.print_json"):
            main()

        fit_from_db.assert_called_once_with(
            "test-loc", "soil_carbon", model_type=None,
            lag_distance=20.0, lag_tolerance=5.0, bandwidth=200.0,
        )

    def test_cli_variogram_rejects_invalid_tolerance_before_database(self):
        from services.geostatistics.cli import main

        argv = [
            "geostatistics", "variogram", "--location-id", "test-loc",
            "--property", "soil_carbon", "--lag-distance", "20",
            "--lag-tolerance", "10.1",
        ]
        with patch("sys.argv", argv), patch(
            "services.common.database.get_db"
        ) as get_db:
            with pytest.raises(SystemExit) as exc_info:
                main()

        assert exc_info.value.code == 2
        get_db.assert_not_called()

    def test_cli_kriging_parser(self):
        """Kriging subcommand should parse arguments."""
        from services.geostatistics.cli import main
        with patch("sys.argv", ["geostatistics", "kriging", "--location-id", "test-loc", "--property", "soil_carbon", "--method", "ordinary"]):
            with patch("services.ingestion.base.get_db") as mock_db:
                mock_db.return_value = MagicMock()
                with patch("sys.stdout"):
                    try:
                        main()
                    except Exception:
                        pass

    def test_cli_kriging_forwards_neighborhood_settings(self):
        from services.geostatistics.cli import main
        from services.geostatistics.kriging import KrigingEngine

        argv = [
            "geostatistics", "kriging", "--location-id", "test-loc",
            "--property", "soil_carbon", "--method", "ordinary",
            "--max-neighbors", "7", "--search-radius", "125.5",
        ]
        with patch("sys.argv", argv), patch(
            "services.common.database.get_db", return_value=MagicMock()
        ), patch.object(
            KrigingEngine, "kriging_from_db", return_value={"error": "synthetic"}
        ) as run_kriging, patch("services.geostatistics.cli.print_json"):
            main()

        run_kriging.assert_called_once_with(
            "test-loc", "soil_carbon", method="ordinary", resolution_m=10.0,
            variogram_model_id=None, threshold=None, max_neighbors=7,
            search_radius=125.5,
        )

    @pytest.mark.parametrize(
        "argv",
        [
            ["geostatistics", "kriging", "--location-id", "test-loc", "--property", "soil_carbon", "--search-radius", "0"],
            ["geostatistics", "kriging", "--location-id", "test-loc", "--property", "soil_carbon", "--max-neighbors", "0"],
            ["geostatistics", "kriging", "--location-id", "test-loc", "--property", "soil_carbon", "--method", "indicator"],
        ],
    )
    def test_cli_kriging_rejects_invalid_controls_before_database(self, argv):
        from services.geostatistics.cli import main

        with patch("sys.argv", argv), patch(
            "services.common.database.get_db"
        ) as get_db:
            with pytest.raises(SystemExit) as exc_info:
                main()

        assert exc_info.value.code == 2
        get_db.assert_not_called()

    def test_cli_simulate_parser(self):
        """Simulate subcommand should parse arguments."""
        from services.geostatistics.cli import main
        with patch("sys.argv", ["geostatistics", "simulate", "--location-id", "test-loc", "--property", "soil_carbon", "--realizations", "10"]):
            with patch("services.ingestion.base.get_db") as mock_db:
                mock_db.return_value = MagicMock()
                with patch("sys.stdout"):
                    try:
                        main()
                    except Exception:
                        pass

    def test_cli_simulation_forwards_resource_settings(self):
        from services.geostatistics.cli import main
        from services.geostatistics.simulation import GeostatSimulator

        argv = [
            "geostatistics", "--json", "simulate", "--location-id", "test-loc",
            "--property", "soil_carbon", "--realizations", "7",
            "--resolution", "125.5", "--seed", "44",
        ]
        with patch("sys.argv", argv), patch(
            "services.common.database.get_db", return_value=MagicMock()
        ), patch.object(
            GeostatSimulator, "simulation_from_db", return_value={"error": "synthetic"}
        ) as run_simulation, patch("services.geostatistics.cli.print_json"):
            main()

        run_simulation.assert_called_once_with(
            "test-loc", "soil_carbon", n_realizations=7,
            grid_resolution_m=125.5, seed=44, variogram_model_id=None,
        )

    @pytest.mark.parametrize(
        "argv",
        [
            ["geostatistics", "simulate", "--location-id", "test-loc", "--property", "soil_carbon", "--realizations", "0"],
            ["geostatistics", "simulate", "--location-id", "test-loc", "--property", "soil_carbon", "--realizations", "1001"],
            ["geostatistics", "simulate", "--location-id", "test-loc", "--property", "soil_carbon", "--resolution", "0"],
            ["geostatistics", "simulate", "--location-id", "test-loc", "--property", "soil_carbon", "--seed", "-1"],
            ["geostatistics", "simulate", "--location-id", "test-loc", "--property", "soil_nitrogen"],
        ],
    )
    def test_cli_simulation_rejects_invalid_settings_before_database(self, argv):
        from services.geostatistics.cli import main

        with patch("sys.argv", argv), patch(
            "services.common.database.get_db"
        ) as get_db:
            with pytest.raises(SystemExit) as exc_info:
                main()

        assert exc_info.value.code == 2
        get_db.assert_not_called()

    def test_cli_autocorrelation_parser(self):
        """Autocorrelation subcommand should parse arguments."""
        from services.geostatistics.cli import main
        with patch("sys.argv", ["geostatistics", "autocorrelation", "--location-id", "test-loc", "--property", "soil_carbon"]):
            with patch("services.ingestion.base.get_db") as mock_db:
                mock_db.return_value = MagicMock()
                with patch("sys.stdout"):
                    try:
                        main()
                    except Exception:
                        pass

    def test_cli_json_flag(self):
        """--json flag should be accepted."""
        from services.geostatistics.cli import main
        with patch("sys.argv", ["geostatistics", "--json", "variogram", "--location-id", "test-loc", "--property", "soil_carbon"]):
            with patch("services.ingestion.base.get_db") as mock_db:
                mock_db.return_value = MagicMock()
                with patch("sys.stdout"):
                    try:
                        main()
                    except Exception:
                        pass


class TestSOCIntegration:
    def test_residual_kriging_insufficient_data(self):
        from services.analytics.soc_prediction import residual_kriging_correction
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.cursor.return_value = mock_cursor
        result = residual_kriging_correction(mock_conn, "test-loc")
        assert "error" in result

    def test_spatial_block_cv_insufficient_data(self):
        from services.analytics.soc_prediction import spatial_block_cv_for_soc
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.cursor.return_value = mock_cursor
        result = spatial_block_cv_for_soc(mock_conn, "test-loc")
        assert "error" in result
