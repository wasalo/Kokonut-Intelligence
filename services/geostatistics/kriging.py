"""Kriging Engine — Ordinary, Simple, and Indicator kriging.

Interpolates spatial data at unsampled locations using fitted variogram
models, producing predictions with uncertainty estimates (kriging variance).
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import psycopg2
import psycopg2.extras
from scipy.spatial import cKDTree

from .config import (
    DEFAULT_MAX_NEIGHBORS,
    DEFAULT_SEARCH_RADIUS_M,
    KRIGING_METHODS,
)
from .data_sources import location_point_query, supports_database_property


class KrigingEngine:
    """Ordinary, Simple, and Indicator kriging interpolation."""

    def __init__(self, conn=None):
        self._conn = conn

    def _get_conn(self):
        if self._conn is None:
            from services.common.database import get_db
            self._conn = get_db()
        return self._conn

    def _build_gstools_variogram(
        self,
        model_type: str,
        sill: float,
        range_m: float,
        nugget: float,
    ):
        """Build a gstools variogram model from parameters."""
        from gstools import Exponential, Gaussian, Matern, Spherical

        model_map = {
            "spherical": Spherical,
            "exponential": Exponential,
            "gaussian": Gaussian,
            "matern": Matern,
        }
        ModelClass = model_map.get(model_type)
        if ModelClass is None:
            raise ValueError("Unsupported variogram model")
        return ModelClass(dim=2, var=sill - nugget, len_scale=range_m, nugget=nugget)

    @staticmethod
    def _validated_variogram_parameters(variogram_model):
        try:
            model_type = variogram_model["model_type"]
            sill = float(variogram_model["sill"])
            range_m = float(variogram_model["range"])
            nugget = float(variogram_model["nugget"])
        except (KeyError, TypeError, ValueError):
            return None, {"error": "Invalid variogram model"}
        if (
            not isinstance(model_type, str)
            or model_type not in {"spherical", "exponential", "gaussian", "matern"}
            or not np.isfinite([sill, range_m, nugget]).all()
            or sill <= 0
            or range_m <= 0
            or nugget < 0
            or nugget > sill
        ):
            return None, {"error": "Invalid variogram model"}
        return (model_type, sill, range_m, nugget), None

    @staticmethod
    def _validate_grid_and_neighborhood(
        coordinates: List[Tuple[float, float]],
        values: List[float],
        grid: Optional[np.ndarray],
        resolution_m: float,
        max_neighbors: int,
        search_radius: float,
    ):
        """Normalize and validate coordinates before constructing a GSTools solver."""
        try:
            coords = np.asarray(coordinates, dtype=float)
            field = np.asarray(values, dtype=float)
            resolution = float(resolution_m)
            radius = float(search_radius)
        except (TypeError, ValueError):
            return None, None, None, None, {"error": "Invalid kriging input"}

        if field.ndim != 1 or len(field) == 0:
            return None, None, None, None, {"error": "Kriging requires at least one point"}
        if coords.ndim != 2 or coords.shape[1:] != (2,) or len(coords) != len(field):
            return None, None, None, None, {
                "error": "Coordinates and values must have matching 2D points"
            }
        if not np.isfinite(coords).all() or not np.isfinite(field).all():
            return None, None, None, None, {"error": "Coordinates and values must be finite"}
        if (
            isinstance(max_neighbors, bool)
            or not isinstance(max_neighbors, (int, np.integer))
            or max_neighbors < 1
        ):
            return None, None, None, None, {"error": "max_neighbors must be a positive integer"}
        if not np.isfinite(radius) or radius <= 0:
            return None, None, None, None, {"error": "search_radius must be finite and greater than zero"}
        if grid is None:
            if not np.isfinite(resolution) or resolution <= 0:
                return None, None, None, None, {
                    "error": "resolution_m must be finite and greater than zero"
                }
            grid = KrigingEngine._build_grid(coords, resolution)
        else:
            try:
                grid = np.asarray(grid, dtype=float)
            except (TypeError, ValueError):
                return None, None, None, None, {"error": "Invalid prediction grid"}
        if grid.ndim != 2 or grid.shape[1:] != (2,) or not np.isfinite(grid).all():
            return None, None, None, None, {
                "error": "Prediction grid must contain finite 2D points"
            }
        return coords, field, grid, radius, None

    @staticmethod
    def _build_grid(
        coordinates: List[Tuple[float, float]],
        resolution_m: float,
        padding_m: float = 100.0,
    ) -> np.ndarray:
        """Build a regular prediction grid from point coordinates."""
        coords = np.asarray(coordinates, dtype=float)
        x_min, y_min = coords.min(axis=0) - padding_m
        x_max, y_max = coords.max(axis=0) + padding_m

        x_grid = np.arange(x_min, x_max, resolution_m)
        y_grid = np.arange(y_min, y_max, resolution_m)
        xx, yy = np.meshgrid(x_grid, y_grid)
        return np.column_stack([xx.ravel(), yy.ravel()])

    @staticmethod
    def _local_predictions(krig, coordinates, values, grid, max_neighbors, search_radius):
        """Evaluate each grid point with its nearest in-radius observations."""
        tree = cKDTree(coordinates)
        predictions = np.full(len(grid), np.nan, dtype=float)
        variances = np.full(len(grid), np.nan, dtype=float)
        neighbor_counts = np.zeros(len(grid), dtype=int)

        for grid_index, target in enumerate(grid):
            candidates = tree.query_ball_point(target, r=search_radius)
            if not candidates:
                continue
            candidate_indices = np.asarray(candidates, dtype=int)
            distances = np.linalg.norm(coordinates[candidate_indices] - target, axis=1)
            # Distance is primary and source row order breaks equal-distance ties.
            order = np.lexsort((candidate_indices, distances))[:max_neighbors]
            selected = candidate_indices[order]
            neighbor_counts[grid_index] = len(selected)
            krig.set_condition(
                cond_pos=[coordinates[selected, 0], coordinates[selected, 1]],
                cond_val=values[selected],
            )
            prediction, variance = krig(target.reshape(2, 1))
            predictions[grid_index] = float(np.asarray(prediction).reshape(-1)[0])
            variances[grid_index] = max(float(np.asarray(variance).reshape(-1)[0]), 0.0)
        return predictions, variances, neighbor_counts

    @staticmethod
    def _finite_list(values):
        return [float(value) if np.isfinite(value) else None for value in values]

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

        coords, field, grid, radius, error = self._validate_grid_and_neighborhood(
            coordinates, values, grid, resolution_m, max_neighbors, search_radius
        )
        if error:
            return error
        parameters, error = self._validated_variogram_parameters(variogram_model)
        if error:
            return error
        try:
            model = self._build_gstools_variogram(*parameters)
        except (TypeError, ValueError):
            return {"error": "Invalid variogram model"}

        solver = krige.Ordinary(model, [coords[:, 0], coords[:, 1]], field)
        pred, var, neighbor_counts = self._local_predictions(
            solver, coords, field, grid, max_neighbors, radius
        )

        return {
            "grid_points": grid.tolist(),
            "predicted_values": self._finite_list(pred),
            "prediction_variance": self._finite_list(var),
            "prediction_std": self._finite_list(np.sqrt(var)),
            "neighbor_counts": neighbor_counts.tolist(),
            "n_estimated_points": int(np.count_nonzero(neighbor_counts)),
            "n_points": len(grid),
            "method": "ordinary",
            "max_neighbors": int(max_neighbors),
            "search_radius_m": radius,
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

        coords, field, grid, radius, error = self._validate_grid_and_neighborhood(
            coordinates, values, grid, resolution_m, max_neighbors, search_radius
        )
        if error:
            return error
        parameters, error = self._validated_variogram_parameters(variogram_model)
        if error:
            return error
        if global_mean is None:
            global_mean = float(np.mean(field))
        try:
            global_mean = float(global_mean)
        except (TypeError, ValueError):
            return {"error": "global_mean must be finite"}
        if not np.isfinite(global_mean):
            return {"error": "global_mean must be finite"}
        try:
            model = self._build_gstools_variogram(*parameters)
        except (TypeError, ValueError):
            return {"error": "Invalid variogram model"}

        solver = krige.Simple(
            model, [coords[:, 0], coords[:, 1]], field, mean=global_mean
        )
        pred, var, neighbor_counts = self._local_predictions(
            solver, coords, field, grid, max_neighbors, radius
        )

        return {
            "grid_points": grid.tolist(),
            "predicted_values": self._finite_list(pred),
            "prediction_variance": self._finite_list(var),
            "prediction_std": self._finite_list(np.sqrt(var)),
            "neighbor_counts": neighbor_counts.tolist(),
            "n_estimated_points": int(np.count_nonzero(neighbor_counts)),
            "n_points": len(grid),
            "method": "simple",
            "global_mean": global_mean,
            "max_neighbors": int(max_neighbors),
            "search_radius_m": radius,
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
        max_neighbors: int = DEFAULT_MAX_NEIGHBORS,
        search_radius: float = DEFAULT_SEARCH_RADIUS_M,
    ) -> Dict[str, Any]:
        """Indicator kriging: probability that value exceeds threshold.

        Returns:
            Dict with grid_points, predicted_values (probability), metadata.
        """
        from gstools import krige

        coords, field, grid, radius, error = self._validate_grid_and_neighborhood(
            coordinates, values, grid, resolution_m, max_neighbors, search_radius
        )
        if error:
            return error
        parameters, error = self._validated_variogram_parameters(variogram_model)
        if error:
            return error
        try:
            threshold = float(threshold)
        except (TypeError, ValueError):
            return {"error": "threshold must be finite"}
        if not np.isfinite(threshold):
            return {"error": "threshold must be finite"}

        # Convert to indicator (binary) variable
        indicator = (field > threshold).astype(float)

        try:
            model = self._build_gstools_variogram(*parameters)
        except (TypeError, ValueError):
            return {"error": "Invalid variogram model"}

        solver = krige.Ordinary(model, [coords[:, 0], coords[:, 1]], indicator)
        pred, var, neighbor_counts = self._local_predictions(
            solver, coords, indicator, grid, max_neighbors, radius
        )

        # Clip probabilities to [0, 1]
        finite_predictions = np.isfinite(pred)
        pred[finite_predictions] = np.clip(pred[finite_predictions], 0.0, 1.0)

        return {
            "grid_points": grid.tolist(),
            "predicted_values": self._finite_list(pred),
            "prediction_variance": self._finite_list(var),
            "prediction_std": self._finite_list(np.sqrt(var)),
            "neighbor_counts": neighbor_counts.tolist(),
            "n_estimated_points": int(np.count_nonzero(neighbor_counts)),
            "n_points": len(grid),
            "method": "indicator",
            "threshold": threshold,
            "max_neighbors": int(max_neighbors),
            "search_radius_m": radius,
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
        max_neighbors: int = DEFAULT_MAX_NEIGHBORS,
        search_radius: float = DEFAULT_SEARCH_RADIUS_M,
    ) -> Dict[str, Any]:
        """Run kriging pipeline from database queries.

        Fetches point data, loads or fits variogram, runs kriging, and returns results.
        """
        if method not in KRIGING_METHODS:
            return {"error": f"Unknown method: {method}. Use one of {KRIGING_METHODS}"}
        if not supports_database_property(property_key):
            return {"error": f"Unsupported property_key: {property_key}"}
        if (
            isinstance(max_neighbors, bool)
            or not isinstance(max_neighbors, (int, np.integer))
            or max_neighbors < 1
        ):
            return {"error": "max_neighbors must be a positive integer"}
        try:
            search_radius = float(search_radius)
            resolution_m = float(resolution_m)
        except (TypeError, ValueError):
            return {"error": "Invalid kriging distance parameter"}
        if not np.isfinite(search_radius) or search_radius <= 0:
            return {"error": "search_radius must be finite and greater than zero"}
        if not np.isfinite(resolution_m) or resolution_m <= 0:
            return {"error": "resolution_m must be finite and greater than zero"}
        if method == "indicator":
            try:
                threshold = float(threshold)
            except (TypeError, ValueError):
                return {"error": "indicator kriging requires a finite threshold value"}
            if not np.isfinite(threshold):
                return {"error": "indicator kriging requires a finite threshold value"}

        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # Fetch variogram model from DB or fit fresh
        if variogram_model_id:
            cur.execute(
                """
                SELECT model_type, sill, range, nugget, partial_sill, r_squared
                  FROM variogram_model
                 WHERE id = %s
                   AND location_id = %s
                   AND property_key = %s
                """,
                (variogram_model_id, location_id, property_key),
            )
            vm_row = cur.fetchone()
            if vm_row is None:
                cur.close()
                return {"error": "Variogram model not found for requested location and property"}
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

        point_query, point_params = location_point_query(location_id, property_key)
        cur.execute(point_query, point_params)

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
            result = self.ordinary_kriging(
                coordinates,
                values,
                variogram_model,
                resolution_m=resolution_m,
                max_neighbors=max_neighbors,
                search_radius=search_radius,
            )
        elif method == "simple":
            result = self.simple_kriging(
                coordinates,
                values,
                variogram_model,
                resolution_m=resolution_m,
                max_neighbors=max_neighbors,
                search_radius=search_radius,
            )
        elif method == "indicator":
            result = self.indicator_kriging(
                coordinates,
                values,
                variogram_model,
                threshold,
                resolution_m=resolution_m,
                max_neighbors=max_neighbors,
                search_radius=search_radius,
            )
        else:
            return {"error": f"Unknown method: {method}"}

        result["location_id"] = location_id
        result["property_key"] = property_key
        result["resolution_m"] = resolution_m
        result["coordinate_origin"] = {
            "latitude": float(mean_lat),
            "longitude": float(mean_lon),
        }
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

        origin = result.get("coordinate_origin")
        try:
            origin_lat = float(origin["latitude"])
            origin_lon = float(origin["longitude"])
            grid_pts = np.asarray(result["grid_points"], dtype=float)
            pred_vals = np.asarray(result["predicted_values"], dtype=float)
            pred_var = np.asarray(result["prediction_variance"], dtype=float)
        except (KeyError, TypeError, ValueError):
            return None
        if (
            not np.isfinite([origin_lat, origin_lon]).all()
            or not -90 <= origin_lat <= 90
            or not -180 <= origin_lon <= 180
            or grid_pts.ndim != 2
            or grid_pts.shape[1:] != (2,)
            or pred_vals.shape != (len(grid_pts),)
            or pred_var.shape != (len(grid_pts),)
            or isinstance(max_points, bool)
            or not isinstance(max_points, (int, np.integer))
            or max_points < 1
        ):
            return None

        finite = np.isfinite(grid_pts).all(axis=1) & np.isfinite(pred_vals) & np.isfinite(pred_var)
        grid_pts = grid_pts[finite]
        pred_vals = pred_vals[finite]
        pred_var = np.maximum(pred_var[finite], 0.0)
        if len(grid_pts) == 0:
            return None

        # The computational grid is a local tangent approximation in meters;
        # transform it back to WGS84 before writing the geometry(4326) column.
        lon_to_m = 111320.0 * np.cos(np.radians(origin_lat))
        if lon_to_m <= 0:
            return None
        grid_pts = np.column_stack(
            [origin_lon + grid_pts[:, 0] / lon_to_m, origin_lat + grid_pts[:, 1] / 111320.0]
        )
        grid_pts[:, 0] = ((grid_pts[:, 0] + 180.0) % 360.0) - 180.0

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
        if len(grid_pts) > max_points:
            indices = np.linspace(0, len(grid_pts) - 1, max_points, dtype=int)
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
                float(pt[0]),
                float(pt[1]),
                float(val),
                float(var),
                float(np.sqrt(var)),
            ))

        conn.commit()
        cur.close()
        return prediction_id
