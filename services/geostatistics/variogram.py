"""Variogram Analysis — empirical variogram computation and model fitting.

Computes experimental semi-variograms from spatial point data and fits
parametric models (spherical, exponential, Gaussian, Matérn) using gstools.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import psycopg2
import psycopg2.extras

from .config import (
    DEFAULT_LAG_DISTANCE,
    DEFAULT_LAG_TOLERANCE,
    DEFAULT_MIN_SAMPLES,
    PROPERTY_DEFAULTS,
)


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
        bandwidth: float = 1000.0,
    ) -> Dict[str, Any]:
        """Compute empirical semi-variogram from point data.

        Args:
            values: Measured values at each location.
            coordinates: List of (x, y) pairs in meters (projected CRS).
            lag_distance: Width of each lag bin in meters.
            lag_tolerance: Half-width of lag tolerance in meters.
            bandwidth: Maximum search bandwidth for pairing.

        Returns:
            Dict with lags, semivariances, pair counts, and parameters.
        """
        from gstools import vario_estimate

        if len(values) < DEFAULT_MIN_SAMPLES:
            return {
                "error": f"Need >= {DEFAULT_MIN_SAMPLES} samples, got {len(values)}",
                "n_samples": len(values),
            }

        coords_arr = np.array(coordinates, dtype=float)
        pos_x = coords_arr[:, 0]
        pos_y = coords_arr[:, 1]
        field = np.array(values, dtype=float)

        # Build bin edges from lag_distance
        max_dist = float(np.max(np.sqrt(
            (pos_x[:, np.newaxis] - pos_x[np.newaxis, :]) ** 2
            + (pos_y[:, np.newaxis] - pos_y[np.newaxis, :]) ** 2
        ))) / 2
        n_bins = max(3, int(max_dist / lag_distance))
        bin_edges = np.linspace(0, max_dist, n_bins + 1)

        bin_centres, gamma = vario_estimate(
            (pos_x, pos_y),
            field,
            bin_edges=bin_edges,
        )

        # Count pairs per lag bin
        n_pairs = []
        dists = np.sqrt(
            (pos_x[:, np.newaxis] - pos_x[np.newaxis, :]) ** 2
            + (pos_y[:, np.newaxis] - pos_y[np.newaxis, :]) ** 2
        )
        for i in range(len(bin_edges) - 1):
            lo, hi = bin_edges[i], bin_edges[i + 1]
            n_pairs.append(int(np.sum(
                (dists >= lo) & (dists < hi) & (dists > 0)
            ) // 2))

        return {
            "lags": bin_centres.tolist(),
            "semivariances": gamma.tolist(),
            "n_pairs": n_pairs,
            "lag_distance": lag_distance,
            "lag_tolerance": lag_tolerance,
            "bandwidth": bandwidth,
            "n_samples": len(values),
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
        from gstools import Spherical, Exponential, Gaussian, Matern

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

        lags = np.array(empirical["lags"])
        gamma = np.array(empirical["semivariances"])

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

            # Goodness-of-fit: r-squared between model and empirical
            model_values = model.variogram(lags)
            ss_res = float(np.sum((gamma - model_values) ** 2))
            ss_tot = float(np.sum((gamma - np.mean(gamma)) ** 2))
            r_squared = 1.0 - (ss_res / ss_tot) if ss_tot > 0 else 0.0

            return {
                "model_type": model_type,
                "sill": float(model.var + model.nugget),
                "range": float(model.len_scale),
                "nugget": float(model.nugget),
                "partial_sill": float(model.var),
                "r_squared": round(r_squared, 4),
                "n_lags": len(lags),
            }
        except Exception as e:
            return {"error": f"Model fitting failed: {e}"}

    def fit_variogram(
        self,
        values: List[float],
        coordinates: List[Tuple[float, float]],
        model_type: str = "exponential",
        lag_distance: float = DEFAULT_LAG_DISTANCE,
        lag_tolerance: float = DEFAULT_LAG_TOLERANCE,
        bandwidth: float = 1000.0,
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
        bandwidth: float = 1000.0,
        model_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Fit a variogram from stored point data in the database.

        Fetches coordinates and values from soil_sample, sensor_reading,
        or remote_sensing_observation depending on property_key.
        """
        defaults = PROPERTY_DEFAULTS.get(property_key, {})
        if lag_distance is None:
            lag_distance = defaults.get("lag_distance", DEFAULT_LAG_DISTANCE)
        if lag_tolerance is None:
            lag_tolerance = defaults.get("lag_tolerance", DEFAULT_LAG_TOLERANCE)
        if model_type is None:
            model_type = defaults.get("model_type", "exponential")

        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # Build query based on property_key
        if property_key.startswith("soil_"):
            col_map = {
                "soil_carbon": "organic_carbon_pct",
                "soil_moisture": "moisture_pct",
                "soil_ph": "ph",
            }
            val_col = col_map.get(property_key, "organic_carbon_pct")
            cur.execute(f"""
                SELECT ss.gps_latitude AS lat, ss.gps_longitude AS lon,
                       ss.{val_col} AS value
                FROM soil_sample ss
                WHERE ss.location_id = %s
                  AND ss.gps_latitude IS NOT NULL
                  AND ss.gps_longitude IS NOT NULL
                  AND ss.{val_col} IS NOT NULL
            """, (location_id,))
        elif property_key == "ndvi":
            cur.execute("""
                SELECT ST_Y(rso.centroid) AS lat, ST_X(rso.centroid) AS lon,
                       rso.ndvi AS value
                FROM remote_sensing_observation rso
                WHERE rso.location_id = %s
                  AND rso.centroid IS NOT NULL
                  AND rso.ndvi IS NOT NULL
            """, (location_id,))
        else:
            cur.close()
            return {"error": f"Unsupported property_key for DB query: {property_key}"}

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
