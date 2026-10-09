"""Spatial Autocorrelation — Moran's I, Geary's C.

Tests whether spatial patterns in measured properties are clustered,
dispersed, or random, providing validation that spatial structure exists
before applying kriging or simulation.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import psycopg2
import psycopg2.extras

from .config import (
    DEFAULT_DISTANCE_THRESHOLD,
    DEFAULT_K_NEIGHBORS,
    SPATIAL_WEIGHTS_TYPES,
    PROPERTY_DEFAULTS,
)


class SpatialAutocorrelation:
    """Spatial autocorrelation statistics (Moran's I, Geary's C)."""

    def __init__(self, conn=None):
        self._conn = conn

    def _get_conn(self):
        if self._conn is None:
            from services.common.database import get_db
            self._conn = get_db()
        return self._conn

    def build_spatial_weights(
        self,
        coordinates: List[Tuple[float, float]],
        weights_type: str = "queen",
        distance_threshold: float = DEFAULT_DISTANCE_THRESHOLD,
        k_neighbors: int = DEFAULT_K_NEIGHBORS,
    ) -> np.ndarray:
        """Build a spatial weights matrix from coordinates.

        Args:
            coordinates: List of (x, y) positions.
            weights_type: 'queen', 'rook', 'distance', or 'knn'.
            distance_threshold: Max distance for distance-based weights (meters).
            k_neighbors: Number of nearest neighbors for KNN weights.

        Returns:
            Binary weight matrix (n x n).
        """
        coords = np.array(coordinates)
        n = len(coords)
        W = np.zeros((n, n))

        if weights_type in ("queen", "rook", "distance"):
            from scipy.spatial.distance import pdist, squareform
            dist_matrix = squareform(pdist(coords))

            if weights_type == "distance":
                W = (dist_matrix < distance_threshold) & (dist_matrix > 0)
            else:
                # Queen/rook: connect all neighbors within threshold
                W = (dist_matrix < distance_threshold) & (dist_matrix > 0)

        elif weights_type == "knn":
            from scipy.spatial.distance import pdist, squareform
            dist_matrix = squareform(pdist(coords))
            for i in range(n):
                distances = dist_matrix[i]
                nearest = np.argsort(distances)[1:k_neighbors + 1]
                W[i, nearest] = 1

        return W.astype(float)

    def compute_morans_i(
        self,
        values: List[float],
        coordinates: List[Tuple[float, float]],
        weights_type: str = "queen",
        distance_threshold: float = DEFAULT_DISTANCE_THRESHOLD,
        k_neighbors: int = DEFAULT_K_NEIGHBORS,
    ) -> Dict[str, Any]:
        """Compute Moran's I statistic.

        Returns:
            Dict with statistic_value, expected_value, z_score, p_value, interpretation.
        """
        z = np.array(values, dtype=float)
        n = len(z)

        if n < 3:
            return {"error": f"Need >= 3 samples, got {n}"}

        W = self.build_spatial_weights(
            coordinates, weights_type, distance_threshold, k_neighbors
        )

        # Row-standardize
        row_sums = W.sum(axis=1)
        row_sums[row_sums == 0] = 1.0
        W_std = W / row_sums[:, np.newaxis]

        z_mean = np.mean(z)
        z_centered = z - z_mean

        # Moran's I
        numerator = float(n) * float(np.sum(W_std * np.outer(z_centered, z_centered)))
        denominator = float(np.sum(W_std)) * float(np.sum(z_centered ** 2))

        if denominator == 0:
            return {"error": "Zero denominator: all values identical"}

        I = numerator / denominator

        # Expected value under null
        expected = -1.0 / (n - 1)

        # Approximate z-score using the variance under randomness
        # Simplified variance approximation
        w_sum = float(np.sum(W_std))
        w2_sum = float(np.sum(W_std ** 2))
        s2 = float(np.var(z_centered))
        var_i = (n * w2_sum - w_sum) / ((n - 1) * w_sum) + (2 * w_sum - n * w2_sum) / ((n - 1) * w_sum * (n - 2)) * (n * s2 / (s2 + 1e-10))

        if var_i > 0:
            z_score = (I - expected) / np.sqrt(var_i)
        else:
            z_score = 0.0

        # Two-tailed p-value approximation
        from scipy.stats import norm
        p_value = 2.0 * (1.0 - norm.cdf(abs(z_score)))

        # Interpretation
        if I > expected and p_value < 0.05:
            interpretation = "clustered"
        elif I < expected and p_value < 0.05:
            interpretation = "dispersed"
        else:
            interpretation = "random"

        return {
            "statistic_value": round(I, 6),
            "expected_value": round(expected, 6),
            "z_score": round(float(z_score), 4),
            "p_value": round(float(p_value), 6),
            "n_samples": n,
            "interpretation": interpretation,
            "weights_type": weights_type,
        }

    def compute_gearys_c(
        self,
        values: List[float],
        coordinates: List[Tuple[float, float]],
        weights_type: str = "queen",
        distance_threshold: float = DEFAULT_DISTANCE_THRESHOLD,
        k_neighbors: int = DEFAULT_K_NEIGHBORS,
    ) -> Dict[str, Any]:
        """Compute Geary's C statistic.

        Returns:
            Dict with statistic_value, expected_value, z_score, p_value, interpretation.
        """
        z = np.array(values, dtype=float)
        n = len(z)

        if n < 3:
            return {"error": f"Need >= 3 samples, got {n}"}

        W = self.build_spatial_weights(
            coordinates, weights_type, distance_threshold, k_neighbors
        )

        # Row-standardize
        row_sums = W.sum(axis=1)
        row_sums[row_sums == 0] = 1.0
        W_std = W / row_sums[:, np.newaxis]

        z_mean = np.mean(z)
        z_centered = z - z_mean

        # Geary's C
        n_val = float(n)
        w_sum = float(np.sum(W_std))
        s2 = float(np.sum(z_centered ** 2)) / (n_val - 1) if n_val > 1 else 1e-10

        diff_matrix = np.subtract.outer(z, z) ** 2
        numerator = (n_val - 1) * float(np.sum(W_std * diff_matrix))
        denominator = 2 * w_sum * float(np.sum(z_centered ** 2))

        if denominator == 0:
            return {"error": "Zero denominator: all values identical"}

        C = numerator / denominator

        # Expected value under null
        expected = 1.0

        # Approximate z-score
        var_c = 2.0 / (n_val * (n_val - 2)) if n_val > 2 else 1.0
        z_score = (C - expected) / np.sqrt(var_c) if var_c > 0 else 0.0

        from scipy.stats import norm
        p_value = 2.0 * (1.0 - norm.cdf(abs(z_score)))

        # Interpretation: C < 1 = positive autocorrelation (clustered)
        # C > 1 = negative autocorrelation (dispersed)
        # C ≈ 1 = random
        if C < 1.0 and p_value < 0.05:
            interpretation = "clustered"
        elif C > 1.0 and p_value < 0.05:
            interpretation = "dispersed"
        else:
            interpretation = "random"

        return {
            "statistic_value": round(C, 6),
            "expected_value": round(expected, 6),
            "z_score": round(float(z_score), 4),
            "p_value": round(float(p_value), 6),
            "n_samples": n,
            "interpretation": interpretation,
            "weights_type": weights_type,
        }

    def autocorrelation_from_db(
        self,
        location_id: str,
        property_key: str,
        weights_type: str = "queen",
        distance_threshold: float = DEFAULT_DISTANCE_THRESHOLD,
        k_neighbors: int = DEFAULT_K_NEIGHBORS,
    ) -> Dict[str, Any]:
        """Run spatial autocorrelation from database point data."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # Fetch point data
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
            return {"error": f"Unsupported property_key: {property_key}"}

        rows = cur.fetchall()
        cur.close()

        if len(rows) < 3:
            return {"error": f"Need >= 3 data points, got {len(rows)}"}

        # Convert to meters
        lats = np.array([float(r["lat"]) for r in rows])
        lons = np.array([float(r["lon"]) for r in rows])
        mean_lat, mean_lon = np.mean(lats), np.mean(lons)
        lat_to_m = 111320.0
        lon_to_m = 111320.0 * np.cos(np.radians(mean_lat))

        coordinates = [
            (float(lon - mean_lon) * lon_to_m, float(lat - mean_lat) * lat_to_m)
            for lat, lon in zip(lats, lons)
        ]
        values = [float(r["value"]) for r in rows]

        # Compute both statistics
        morans = self.compute_morans_i(
            values, coordinates, weights_type, distance_threshold, k_neighbors
        )
        gearys = self.compute_gearys_c(
            values, coordinates, weights_type, distance_threshold, k_neighbors
        )

        return {
            "location_id": location_id,
            "property_key": property_key,
            "n_samples": len(rows),
            "morans_i": morans,
            "gearys_c": gearys,
        }

    def persist_results(
        self,
        location_id: str,
        property_key: str,
        result: Dict[str, Any],
    ) -> List[str]:
        """Persist autocorrelation results to the database.

        Returns list of inserted record UUIDs.
        """
        if "error" in result:
            return []

        conn = self._get_conn()
        cur = conn.cursor()
        ids = []

        for metric_key in ("morans_i", "gearys_c"):
            data = result.get(metric_key, {})
            if "error" in data:
                continue

            record_id = str(uuid.uuid4())
            ids.append(record_id)

            cur.execute("""
                INSERT INTO spatial_autocorrelation (
                    id, location_id, property_key, metric,
                    statistic_value, expected_value, p_value, z_score,
                    n_samples, spatial_weights_type, distance_threshold,
                    k_neighbors, interpretation, computed_at, metadata
                ) VALUES (
                    %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, NOW(), %s::jsonb
                )
            """, (
                record_id,
                location_id,
                property_key,
                metric_key,
                data["statistic_value"],
                data["expected_value"],
                data["p_value"],
                data["z_score"],
                data["n_samples"],
                data.get("weights_type"),
                result.get("distance_threshold"),
                result.get("k_neighbors"),
                data["interpretation"],
                "{}",
            ))

        conn.commit()
        cur.close()
        return ids
