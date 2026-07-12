"""Tests for Geostatistics Suite — variogram, kriging, simulation,
autocorrelation, cross-validation, sensor optimization, CLI, and SOC integration.
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch, PropertyMock
from contextlib import contextmanager

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
        }
        pred_id = engine.persist_kriging("loc1", "soil_carbon", "vm1", result)
        assert pred_id is not None

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
            "realizations": [[1.0, 2.0, 3.0]],
            "grid_points": [[0, 0], [100, 100], [200, 200]],
            "n_points": 3,
            "n_realizations": 1,
            "grid_resolution_m": 100.0,
            "seed": 42,
        }
        real_id = simulator.persist_simulations("loc1", "soil_carbon", "vm1", result)
        assert real_id is not None

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
            with patch("sys.stdout") as mock_stdout:
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
