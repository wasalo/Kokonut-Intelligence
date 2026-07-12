"""Kriging Engine — Ordinary, Simple, and Indicator kriging.

Interpolates spatial data at unsampled locations using fitted variogram
models, producing predictions with uncertainty estimates (kriging variance).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import psycopg2
import psycopg2.extras

from .config import (
    DEFAULT_MAX_NEIGHBORS,
    DEFAULT_SEARCH_RADIUS_M,
    KRIGING_METHODS,
    PROPERTY_DEFAULTS,
)


class KrigingEngine:
    """Ordinary, Simple, and Indicator kriging interpolation."""

    def __init__(self, conn=None):
        self._conn = conn

    def _get_conn(self):
        if self._conn is None:
            from services.common.env import get_db
            self._conn = get_db()
        return self._conn

    def _build_grid(
        self,
        coordinates: List[Tuple[float, float]],
        resolution_m: float,
        padding_m: float = 100.0,
    ) -> np.ndarray:
        """Build a regular prediction grid from point coordinates."""
        coords = np.array(coordinates)
        x_min, y_min = coords.min(axis=0) - padding_m
        x_max, y_max = coords.max(axis=0) + padding_m

        x_grid = np.arange(x_min, x_max, resolution_m)
        y_grid = np.arange(y_min, y_max, resolution_m)
        xx, yy = np.meshgrid(x_grid, y_grid)
        return np.column_stack([xx.ravel(), yy.ravel()])

    def _build_gstools_variogram(
        self,
        model_type: str,
        sill: float,
        range_m: float,
        nugget: float,
    ):
        """Build a gstools variogram model from parameters."""
        from gstools import Spherical, Exponential, Gaussian, Matern

        model_map = {
            "spherical": Spherical,
            "exponential": Exponential,
            "gaussian": Gaussian,
            "matern": Matern,
        }
        ModelClass = model_map.get(model_type, Exponential)
        return ModelClass(dim=2, var=sill - nugget, len_scale=range_m, nugget=nugget)

    def ordinary_kriging(
        self,
        coordinates: List[Tuple[float, float]],
        values: List[float],
        variogram_model: Dict[str, Any],
        grid: Optional[np.ndarray] = None,
        resolution_m: float = 10.0,
        max_neighbors: int = DEFAULT_MAX_NEIGHBORS,
        search_radius: float = DEFAULT_SEARCH_RADIUS_M,
    ) -> Dict[str, Any]:
        """Ordinary kriging: unknown but constant local mean.

        Returns:
            Dict with grid_points, predicted_values, prediction_variance, metadata.
        """
        from gstools import krige

        pos = np.array(coordinates).T
        field = np.array(values, dtype=float)

        model = self._build_gstools_variogram(
            variogram_model["model_type"],
            variogram_model["sill"],
            variogram_model["range"],
            variogram_model["nugget"],
        )

        if grid is None:
            grid = self._build_grid(coordinates, resolution_m)

        krig = krige.Ordinary(model, [pos[0].tolist(), pos[1].tolist()], field.tolist())
        pred, var = krig(grid.T)

        return {
            "grid_points": grid.tolist(),
            "predicted_values": pred.tolist(),
            "prediction_variance": var.tolist(),
            "prediction_std": np.sqrt(var).tolist(),
            "n_points": len(grid),
            "method": "ordinary",
            "variogram_model": variogram_model,
        }

    def simple_kriging(
        self,
        coordinates: List[Tuple[float, float]],
        values: List[float],
        variogram_model: Dict[str, Any],
        global_mean: Optional[float] = None,
        grid: Optional[np.ndarray] = None,
        resolution_m: float = 10.0,
        max_neighbors: int = DEFAULT_MAX_NEIGHBORS,
        search_radius: float = DEFAULT_SEARCH_RADIUS_M,
    ) -> Dict[str, Any]:
        """Simple kriging: known constant global mean.

        Returns:
            Dict with grid_points, predicted_values, prediction_variance, metadata.
        """
        from gstools import krige

        pos = np.array(coordinates).T
        field = np.array(values, dtype=float)

        model = self._build_gstools_variogram(
            variogram_model["model_type"],
            variogram_model["sill"],
            variogram_model["range"],
            variogram_model["nugget"],
        )

        if global_mean is None:
            global_mean = float(np.mean(field))

        if grid is None:
            grid = self._build_grid(coordinates, resolution_m)

        krig = krige.Simple(model, [pos[0].tolist(), pos[1].tolist()], field.tolist(), mean=global_mean)
        pred, var = krig(grid.T)

        return {
            "grid_points": grid.tolist(),
            "predicted_values": pred.tolist(),
            "prediction_variance": var.tolist(),
            "prediction_std": np.sqrt(var).tolist(),
            "n_points": len(grid),
            "method": "simple",
            "global_mean": global_mean,
            "variogram_model": variogram_model,
        }

    def indicator_kriging(
        self,
        coordinates: List[Tuple[float, float]],
        values: List[float],
        variogram_model: Dict[str, Any],
        threshold: float,
        grid: Optional[np.ndarray] = None,
        resolution_m: float = 10.0,
    ) -> Dict[str, Any]:
        """Indicator kriging: probability that value exceeds threshold.

        Returns:
            Dict with grid_points, predicted_values (probability), metadata.
        """
        from gstools import krige

        pos = np.array(coordinates).T
        field = np.array(values, dtype=float)

        # Convert to indicator (binary) variable
        indicator = (field > threshold).astype(float)

        model = self._build_gstools_variogram(
            variogram_model["model_type"],
            variogram_model["sill"],
            variogram_model["range"],
            variogram_model["nugget"],
        )

        if grid is None:
            grid = self._build_grid(coordinates, resolution_m)

        krig = krige.Ordinary(model, [pos[0].tolist(), pos[1].tolist()], indicator.tolist())
        pred, var = krig(grid.T)

        # Clip probabilities to [0, 1]
        pred = np.clip(pred, 0.0, 1.0)

        return {
            "grid_points": grid.tolist(),
            "predicted_values": pred.tolist(),
            "prediction_variance": var.tolist(),
            "prediction_std": np.sqrt(var).tolist(),
            "n_points": len(grid),
            "method": "indicator",
            "threshold": threshold,
            "variogram_model": variogram_model,
        }

    def kriging_from_db(
        self,
        location_id: str,
        property_key: str,
        method: str = "ordinary",
        resolution_m: float = 10.0,
        variogram_model_id: Optional[str] = None,
        threshold: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Run kriging pipeline from database queries.

        Fetches point data, loads or fits variogram, runs kriging, and returns results.
        """
        if method not in KRIGING_METHODS:
            return {"error": f"Unknown method: {method}. Use one of {KRIGING_METHODS}"}

        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # Fetch variogram model from DB or fit fresh
        if variogram_model_id:
            cur.execute(
                "SELECT * FROM variogram_model WHERE id = %s",
                (variogram_model_id,),
            )
            vm_row = cur.fetchone()
            if vm_row is None:
                cur.close()
                return {"error": f"Variogram model {variogram_model_id} not found"}
            variogram_model = {
                "model_type": vm_row["model_type"],
                "sill": float(vm_row["sill"]),
                "range": float(vm_row["range"]),
                "nugget": float(vm_row["nugget"]),
                "partial_sill": float(vm_row["partial_sill"]) if vm_row["partial_sill"] else None,
                "r_squared": float(vm_row["r_squared"]) if vm_row["r_squared"] else None,
            }
        else:
            # Fit variogram from DB data
            from .variogram import VariogramAnalyzer
            va = VariogramAnalyzer(conn=conn)
            vm_result = va.fit_from_db(location_id, property_key)
            if "error" in vm_result:
                cur.close()
                return vm_result
            variogram_model = vm_result

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
            return {"error": f"Need >= 3 data points for kriging, got {len(rows)}"}

        # Convert to meter coordinates
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

        # Run kriging
        if method == "ordinary":
            result = self.ordinary_kriging(coordinates, values, variogram_model, resolution_m=resolution_m)
        elif method == "simple":
            result = self.simple_kriging(coordinates, values, variogram_model, resolution_m=resolution_m)
        elif method == "indicator":
            if threshold is None:
                return {"error": "indicator kriging requires a threshold value"}
            result = self.indicator_kriging(
                coordinates, values, variogram_model, threshold, resolution_m=resolution_m
            )
        else:
            return {"error": f"Unknown method: {method}"}

        result["location_id"] = location_id
        result["property_key"] = property_key
        result["resolution_m"] = resolution_m
        return result

    def persist_kriging(
        self,
        location_id: str,
        property_key: str,
        variogram_model_id: str,
        result: Dict[str, Any],
        max_points: int = 5000,
    ) -> Optional[str]:
        """Persist kriging results to the database.

        Caps at max_points to avoid excessive storage. Returns prediction UUID.
        """
        if "error" in result:
            return None

        conn = self._get_conn()
        cur = conn.cursor()

        prediction_id = str(uuid.uuid4())
        cur.execute("""
            INSERT INTO kriging_prediction (
                id, location_id, variogram_model_id, property_key,
                grid_resolution_m, n_points, method, threshold_value
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            prediction_id,
            location_id,
            variogram_model_id,
            property_key,
            result.get("resolution_m"),
            result["n_points"],
            result["method"],
            result.get("threshold"),
        ))

        # Persist points (cap at max_points for storage efficiency)
        grid_pts = np.array(result["grid_points"])
        pred_vals = np.array(result["predicted_values"])
        pred_var = np.array(result["prediction_variance"])

        if len(grid_pts) > max_points:
            indices = np.random.choice(len(grid_pts), max_points, replace=False)
            grid_pts = grid_pts[indices]
            pred_vals = pred_vals[indices]
            pred_var = pred_var[indices]

        for pt, val, var in zip(grid_pts, pred_vals, pred_var):
            point_id = str(uuid.uuid4())
            cur.execute("""
                INSERT INTO kriging_point (
                    id, prediction_id, point_geometry,
                    predicted_value, prediction_variance, prediction_std
                ) VALUES (
                    %s, %s,
                    ST_SetSRID(ST_MakePoint(%s, %s), 4326),
                    %s, %s, %s
                )
            """, (
                point_id,
                prediction_id,
                float(pt[0]),  # Note: these are meter coords, not lat/lon
                float(pt[1]),
                float(val),
                float(var),
                float(np.sqrt(var)),
            ))

        conn.commit()
        cur.close()
        return prediction_id
