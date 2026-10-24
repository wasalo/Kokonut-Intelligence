"""Variogram Analysis — empirical variogram computation and model fitting.

Computes experimental semi-variograms from spatial point data and fits
parametric models (spherical, exponential, Gaussian, Matérn) using gstools.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import psycopg2
import psycopg2.extras
from scipy.spatial.distance import pdist

from services.common.errors import safe_exception_class

from .config import (
    DEFAULT_BANDWIDTH,
    DEFAULT_LAG_DISTANCE,
    DEFAULT_LAG_TOLERANCE,
    DEFAULT_MIN_SAMPLES,
    PROPERTY_DEFAULTS,
)
from .data_sources import location_point_query, supports_database_property


class VariogramAnalyzer:
    """Empirical variogram computation and parametric model fitting."""

    def __init__(self, conn=None):
        self._conn = conn

    def _get_conn(self):
        if self._conn is None:
            from services.common.database import get_db
            self._conn = get_db()
        return self._conn

    def compute_empirical_variogram(
        self,
        values: List[float],
        coordinates: List[Tuple[float, float]],
        lag_distance: float = DEFAULT_LAG_DISTANCE,
        lag_tolerance: float = DEFAULT_LAG_TOLERANCE,
        bandwidth: float = DEFAULT_BANDWIDTH,
    ) -> Dict[str, Any]:
        """Compute empirical semi-variogram from point data.

        Args:
            values: Measured values at each location.
            coordinates: List of (x, y) pairs in meters (projected CRS).
            lag_distance: Width of each fixed lag bin in meters.
            lag_tolerance: Half-width around each bin center, at most half
                the bin width so bins cannot overlap.
            bandwidth: Maximum pair separation searched, in meters. The
                omnidirectional search is also capped at half the largest
                observed pair distance.

        Returns:
            Dict with lags, semivariances, pair counts, and parameters.
        """
        try:
            values_arr = np.asarray(values, dtype=float)
            coords_arr = np.asarray(coordinates, dtype=float)
            lag_distance = float(lag_distance)
            lag_tolerance = float(lag_tolerance)
            bandwidth = float(bandwidth)
        except (TypeError, ValueError):
            return {"error": "Invalid variogram input"}

        if values_arr.ndim != 1 or coords_arr.shape != (len(values_arr), 2):
            return {"error": "Coordinates and values must have matching 2D points"}
        if not np.isfinite(values_arr).all() or not np.isfinite(coords_arr).all():
            return {"error": "Coordinates and values must be finite"}
        if len(values_arr) < DEFAULT_MIN_SAMPLES:
            return {
                "error": f"Need >= {DEFAULT_MIN_SAMPLES} samples, got {len(values_arr)}",
                "n_samples": len(values_arr),
            }
        if (
            not np.isfinite(lag_distance)
            or lag_distance <= 0
            or not np.isfinite(lag_tolerance)
            or lag_tolerance < 0
            or lag_tolerance > lag_distance / 2
            or not np.isfinite(bandwidth)
            or bandwidth <= 0
        ):
            return {"error": "Invalid lag distance, tolerance, or bandwidth"}

        pair_distances = pdist(coords_arr)
        pair_value_differences = pdist(values_arr[:, np.newaxis])
        pair_semivariances = 0.5 * np.square(pair_value_differences)
        positive_distance = pair_distances > 0
        pair_distances = pair_distances[positive_distance]
        pair_semivariances = pair_semivariances[positive_distance]
        if len(pair_distances) == 0:
            return {"error": "No non-zero-distance point pairs available"}

        search_distance = min(float(np.max(pair_distances)) / 2, bandwidth)
        if search_distance <= 0:
            return {"error": "No point pairs within the configured bandwidth"}

        n_bins = int(np.ceil(search_distance / lag_distance))
        bin_centres: List[float] = []
        gamma: List[float] = []
        n_pairs: List[int] = []
        for bin_index in range(n_bins):
            lower = bin_index * lag_distance
            upper = min((bin_index + 1) * lag_distance, search_distance)
            centre = (lower + upper) / 2
            in_interval = (pair_distances >= lower) & (pair_distances < upper)
            if bin_index == n_bins - 1:
                in_interval |= pair_distances == upper
            in_tolerance = np.abs(pair_distances - centre) <= lag_tolerance
            selected = in_interval & in_tolerance & (pair_distances <= bandwidth)
            count = int(np.count_nonzero(selected))
            if count == 0:
                continue
            bin_centres.append(float(np.mean(pair_distances[selected])))
            gamma.append(float(np.mean(pair_semivariances[selected])))
            n_pairs.append(count)

        if not n_pairs:
            return {"error": "No point pairs matched the configured lag bins"}

        return {
            "lags": bin_centres,
            "semivariances": gamma,
            "n_pairs": n_pairs,
            "lag_distance": lag_distance,
            "lag_tolerance": lag_tolerance,
            "bandwidth": bandwidth,
            "n_samples": len(values_arr),
        }

    def fit_variogram_model(
        self,
        empirical: Dict[str, Any],
        model_type: str = "exponential",
    ) -> Dict[str, Any]:
        """Fit a parametric variogram model to an empirical variogram.

        Args:
            empirical: Output from compute_empirical_variogram.
            model_type: One of 'spherical', 'exponential', 'gaussian', 'matern'.

        Returns:
            Dict with sill, range, nugget, partial_sill, r_squared, model_type.
        """
        from gstools import Exponential, Gaussian, Matern, Spherical

        if "error" in empirical:
            return empirical

        model_map = {
            "spherical": Spherical,
            "exponential": Exponential,
            "gaussian": Gaussian,
            "matern": Matern,
        }

        ModelClass = model_map.get(model_type)
        if ModelClass is None:
            return {"error": f"Unknown model_type: {model_type}"}

        try:
            lags = np.asarray(empirical["lags"], dtype=float)
            gamma = np.asarray(empirical["semivariances"], dtype=float)
        except (KeyError, TypeError, ValueError):
            return {"error": "Invalid empirical variogram data"}

        if lags.ndim != 1 or gamma.ndim != 1 or lags.shape != gamma.shape:
            return {"error": "Invalid empirical variogram data"}
        valid = np.isfinite(lags) & np.isfinite(gamma) & (lags >= 0) & (gamma >= 0)
        lags = lags[valid]
        gamma = gamma[valid]
        if len(lags) < 3:
            return {"error": "Need >= 3 lag bins to fit a variogram model"}

        # Initial parameter estimates from data
        sill_est = float(np.max(gamma))
        range_est = float(lags[np.argmax(gamma >= 0.95 * sill_est)]) if np.any(gamma >= 0.95 * sill_est) else float(lags[-1] / 2)
        nugget_est = float(np.min(gamma[:3])) if len(gamma) >= 3 else 0.0

        # Fit using least-squares on the empirical variogram
        try:
            model = ModelClass(
                dim=2,
                var=sill_est - nugget_est,
                len_scale=range_est,
                nugget=nugget_est,
            )

            # Fit the model parameters instead of reporting the initial guess.
            # The database schema does not store Matérn smoothness, so retain
            # GSTools' default value instead of fitting an unpersisted field.
            fit_options = {"nu": False} if model_type == "matern" else {}
            _, _, r_squared = model.fit_variogram(
                lags,
                gamma,
                method="trf",
                loss="soft_l1",
                return_r2=True,
                **fit_options,
            )
            parameters = (model.var, model.len_scale, model.nugget, r_squared)
            if not all(np.isfinite(value) for value in parameters):
                return {"error": "Model fitting produced non-finite parameters"}

            return {
                "model_type": model_type,
                "sill": float(model.var + model.nugget),
                "range": float(model.len_scale),
                "nugget": float(model.nugget),
                "partial_sill": float(model.var),
                "r_squared": round(float(r_squared), 4),
                "n_lags": len(lags),
            }
        except Exception as exc:
            return {
                "error": f"Model fitting failed ({safe_exception_class(exc)})"
            }

    def fit_variogram(
        self,
        values: List[float],
        coordinates: List[Tuple[float, float]],
        model_type: str = "exponential",
        lag_distance: float = DEFAULT_LAG_DISTANCE,
        lag_tolerance: float = DEFAULT_LAG_TOLERANCE,
        bandwidth: float = DEFAULT_BANDWIDTH,
    ) -> Dict[str, Any]:
        """Compute empirical variogram and fit a parametric model in one step.

        Returns:
            Dict with empirical variogram data and fitted model parameters.
        """
        empirical = self.compute_empirical_variogram(
            values, coordinates, lag_distance, lag_tolerance, bandwidth
        )
        if "error" in empirical:
            return empirical

        fitted = self.fit_variogram_model(empirical, model_type)
        if "error" in fitted:
            return fitted

        return {**empirical, **fitted}

    def fit_from_db(
        self,
        location_id: str,
        property_key: str,
        lag_distance: Optional[float] = None,
        lag_tolerance: Optional[float] = None,
        bandwidth: float = DEFAULT_BANDWIDTH,
        model_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Fit a variogram from stored point data in the database.

        Fetches soil properties from soil_sample and NDVI from
        remote_sensing_observation, always filtered by location_id.
        """
        if not supports_database_property(property_key):
            return {"error": f"Unsupported property_key: {property_key}"}

        defaults = PROPERTY_DEFAULTS.get(property_key, {})
        if lag_distance is None:
            lag_distance = defaults.get("lag_distance", DEFAULT_LAG_DISTANCE)
        if lag_tolerance is None:
            lag_tolerance = defaults.get("lag_tolerance", DEFAULT_LAG_TOLERANCE)
        if model_type is None:
            model_type = defaults.get("model_type", "exponential")

        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        point_query, point_params = location_point_query(location_id, property_key)
        cur.execute(point_query, point_params)

        rows = cur.fetchall()
        cur.close()

        if len(rows) < DEFAULT_MIN_SAMPLES:
            return {
                "error": f"Need >= {DEFAULT_MIN_SAMPLES} samples, got {len(rows)}",
                "n_samples": len(rows),
            }

        # Convert lat/lon to approximate meters using simple projection
        # (center the coordinates on the mean position)
        lats = np.array([float(r["lat"]) for r in rows])
        lons = np.array([float(r["lon"]) for r in rows])
        mean_lat = np.mean(lats)
        mean_lon = np.mean(lons)

        # Approximate meter conversion at mean latitude
        lat_to_m = 111320.0
        lon_to_m = 111320.0 * np.cos(np.radians(mean_lat))

        coordinates = [
            (float(lon - mean_lon) * lon_to_m, float(lat - mean_lat) * lat_to_m)
            for lat, lon in zip(lats, lons)
        ]
        values = [float(r["value"]) for r in rows]

        result = self.fit_variogram(
            values, coordinates, model_type, lag_distance, lag_tolerance, bandwidth
        )
        result["location_id"] = location_id
        result["property_key"] = property_key
        result["n_samples"] = len(rows)
        return result

    def persist_variogram(
        self,
        location_id: str,
        property_key: str,
        fit_result: Dict[str, Any],
    ) -> Optional[str]:
        """Persist a fitted variogram model to the database.

        Returns the variogram_model UUID, or None on error.
        """
        if "error" in fit_result:
            return None

        conn = self._get_conn()
        cur = conn.cursor()

        model_id = str(uuid.uuid4())
        cur.execute("""
            INSERT INTO variogram_model (
                id, location_id, property_key, model_type,
                sill, range, nugget, partial_sill,
                lag_distance, lag_tolerance, bandwidth,
                n_pairs, r_squared, fitted_at, metadata
            ) VALUES (
                %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s, NOW(), %s::jsonb
            )
        """, (
            model_id,
            location_id,
            property_key,
            fit_result["model_type"],
            fit_result["sill"],
            fit_result["range"],
            fit_result["nugget"],
            fit_result.get("partial_sill"),
            fit_result.get("lag_distance"),
            fit_result.get("lag_tolerance"),
            fit_result.get("bandwidth"),
            fit_result.get("n_pairs", [0])[-1] if fit_result.get("n_pairs") else None,
            fit_result["r_squared"],
            "{}",
        ))

        conn.commit()
        cur.close()
        return model_id
