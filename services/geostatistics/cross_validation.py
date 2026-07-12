"""Spatial Cross-Validation — block CV, leave-one-out, k-fold.

Validates geostatistical models by holding out spatial blocks or points
to prevent spatial leakage in prediction accuracy assessment.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import psycopg2
import psycopg2.extras

from .config import (
    CV_STRATEGIES,
    DEFAULT_MAX_NEIGHBORS,
    DEFAULT_SEARCH_RADIUS_M,
    PROPERTY_DEFAULTS,
)


class SpatialCrossValidator:
    """Spatial cross-validation for geostatistical models."""

    def __init__(self, conn=None):
        self._conn = conn

    def _get_conn(self):
        if self._conn is None:
            from services.common.env import get_db
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
        from gstools import Spherical, Exponential, Gaussian, Matern

        model_map = {
            "spherical": Spherical,
            "exponential": Exponential,
            "gaussian": Gaussian,
            "matern": Matern,
        }
        ModelClass = model_map.get(model_type, Exponential)
        return ModelClass(dim=2, var=sill - nugget, len_scale=range_m, nugget=nugget)

    def _kriging_predict(
        self,
        train_coords: List[Tuple[float, float]],
        train_values: List[float],
        test_coords: List[Tuple[float, float]],
        variogram_model: Dict[str, Any],
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Run kriging prediction at test points using training data."""
        from gstools import krige

        pos = np.array(train_coords).T
        field = np.array(train_values, dtype=float)
        test_pos = np.array(test_coords)

        model = self._build_gstools_variogram(
            variogram_model["model_type"],
            variogram_model["sill"],
            variogram_model["range"],
            variogram_model["nugget"],
        )

        krig = krige.Ordinary(model, [pos[0].tolist(), pos[1].tolist()], field.tolist())
        pred, var = krig(test_pos.T)

        return pred, var

    def spatial_block_cv(
        self,
        coordinates: List[Tuple[float, float]],
        values: List[float],
        variogram_model: Dict[str, Any],
        block_size_m: float = 200.0,
    ) -> Dict[str, Any]:
        """Spatial block cross-validation.

        Partitions the study area into spatial blocks and holds out each block
        in turn, predicting from the remaining data. This prevents spatial
        leakage that would occur with random CV.

        Returns:
            Dict with fold_results, aggregate metrics, metadata.
        """
        coords = np.array(coordinates)
        vals = np.array(values, dtype=float)
        n = len(vals)

        if n < 6:
            return {"error": f"Need >= 6 samples for spatial block CV, got {n}"}

        # Create spatial blocks
        x_min, y_min = coords.min(axis=0)
        x_max, y_max = coords.max(axis=0)

        block_ids = np.zeros(n, dtype=int)
        x_blocks = np.ceil((coords[:, 0] - x_min) / block_size_m).astype(int)
        y_blocks = np.ceil((coords[:, 1] - y_min) / block_size_m).astype(int)
        block_ids = x_blocks * 1000 + y_blocks  # Unique block ID

        unique_blocks = np.unique(block_ids)
        n_blocks = len(unique_blocks)

        if n_blocks < 2:
            return {"error": f"Only {n_blocks} unique block(s) with block_size={block_size_m}m. Try smaller block size."}

        fold_results = []
        all_predictions = []
        all_actuals = []

        for i, block_id in enumerate(unique_blocks):
            test_mask = block_ids == block_id
            train_mask = ~test_mask

            if np.sum(test_mask) == 0 or np.sum(train_mask) == 0:
                continue

            train_coords = coords[train_mask].tolist()
            train_values = vals[train_mask].tolist()
            test_coords = coords[test_mask].tolist()
            test_values = vals[test_mask].tolist()

            try:
                pred, var = self._kriging_predict(
                    train_coords, train_values, test_coords, variogram_model
                )
                errors = pred - np.array(test_values)

                fold_result = {
                    "fold": i + 1,
                    "block_id": int(block_id),
                    "train_samples": int(np.sum(train_mask)),
                    "test_samples": int(np.sum(test_mask)),
                    "mean_error": round(float(np.mean(errors)), 4),
                    "mean_squared_error": round(float(np.mean(errors ** 2)), 4),
                    "rmse": round(float(np.sqrt(np.mean(errors ** 2))), 4),
                    "mae": round(float(np.mean(np.abs(errors))), 4),
                    "r_squared": round(float(1 - np.sum(errors ** 2) / np.sum((np.array(test_values) - np.mean(test_values)) ** 2)), 4) if np.sum((np.array(test_values) - np.mean(test_values)) ** 2) > 0 else 0.0,
                }
                fold_results.append(fold_result)
                all_predictions.extend(pred.tolist())
                all_actuals.extend(test_values)
            except Exception as e:
                fold_results.append({
                    "fold": i + 1,
                    "block_id": int(block_id),
                    "error": str(e),
                })

        if not all_predictions:
            return {"error": "No successful folds", "fold_results": fold_results}

        all_pred = np.array(all_predictions)
        all_act = np.array(all_actuals)
        errors = all_pred - all_act

        return {
            "cv_strategy": "spatial_block",
            "block_size_m": block_size_m,
            "n_folds": len(fold_results),
            "n_successful_folds": len([f for f in fold_results if "error" not in f]),
            "fold_results": fold_results,
            "mean_error": round(float(np.mean(errors)), 4),
            "mean_squared_error": round(float(np.mean(errors ** 2)), 4),
            "root_mean_squared_error": round(float(np.sqrt(np.mean(errors ** 2))), 4),
            "mean_absolute_error": round(float(np.mean(np.abs(errors))), 4),
            "r_squared": round(float(1 - np.sum(errors ** 2) / np.sum((all_act - np.mean(all_act)) ** 2)), 4) if np.sum((all_act - np.mean(all_act)) ** 2) > 0 else 0.0,
        }

    def leave_one_out_cv(
        self,
        coordinates: List[Tuple[float, float]],
        values: List[float],
        variogram_model: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Leave-one-out cross-validation.

        For each point, hold it out and predict from all others.
        Computationally expensive but thorough.
        """
        coords = np.array(coordinates)
        vals = np.array(values, dtype=float)
        n = len(vals)

        if n < 4:
            return {"error": f"Need >= 4 samples for LOO-CV, got {n}"}

        fold_results = []
        all_predictions = []

        for i in range(n):
            test_coord = coords[i].tolist()
            test_val = float(vals[i])

            train_mask = np.arange(n) != i
            train_coords = coords[train_mask].tolist()
            train_values = vals[train_mask].tolist()

            try:
                pred, var = self._kriging_predict(
                    train_coords, train_values, [test_coord], variogram_model
                )
                error = float(pred[0] - test_val)
                all_predictions.append(float(pred[0]))

                fold_results.append({
                    "fold": i + 1,
                    "held_out_index": i,
                    "predicted": round(float(pred[0]), 4),
                    "actual": test_val,
                    "error": round(error, 4),
                    "variance": round(float(var[0]), 4),
                })
            except Exception as e:
                fold_results.append({
                    "fold": i + 1,
                    "held_out_index": i,
                    "error": str(e),
                })

        if not all_predictions:
            return {"error": "No successful folds", "fold_results": fold_results}

        all_pred = np.array(all_predictions)
        errors = all_pred - vals[:len(all_predictions)]

        return {
            "cv_strategy": "leave_one_out",
            "n_folds": len(fold_results),
            "n_successful_folds": len([f for f in fold_results if "predicted" in f]),
            "fold_results": fold_results,
            "mean_error": round(float(np.mean(errors)), 4),
            "mean_squared_error": round(float(np.mean(errors ** 2)), 4),
            "root_mean_squared_error": round(float(np.sqrt(np.mean(errors ** 2))), 4),
            "mean_absolute_error": round(float(np.mean(np.abs(errors))), 4),
            "r_squared": round(float(1 - np.sum(errors ** 2) / np.sum((vals[:len(all_pred)] - np.mean(vals[:len(all_pred)])) ** 2)), 4) if np.sum((vals[:len(all_pred)] - np.mean(vals[:len(all_pred)])) ** 2) > 0 else 0.0,
        }

    def cross_validate_from_db(
        self,
        location_id: str,
        property_key: str,
        cv_strategy: str = "spatial_block",
        block_size_m: float = 200.0,
        variogram_model_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Run spatial cross-validation from database point data."""
        if cv_strategy not in CV_STRATEGIES:
            return {"error": f"Unknown cv_strategy: {cv_strategy}. Use one of {CV_STRATEGIES}"}

        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # Fetch or fit variogram
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
            }
        else:
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

        if len(rows) < 4:
            return {"error": f"Need >= 4 data points, got {len(rows)}"}

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

        # Run CV
        if cv_strategy == "spatial_block":
            result = self.spatial_block_cv(
                coordinates, values, variogram_model, block_size_m
            )
        elif cv_strategy == "leave_one_out":
            result = self.leave_one_out_cv(
                coordinates, values, variogram_model
            )
        else:
            return {"error": f"CV strategy '{cv_strategy}' not yet implemented for DB pipeline"}

        result["location_id"] = location_id
        result["property_key"] = property_key
        return result

    def persist_cv_results(
        self,
        location_id: str,
        property_key: str,
        variogram_model_id: Optional[str],
        result: Dict[str, Any],
    ) -> Optional[str]:
        """Persist cross-validation results to the database."""
        if "error" in result:
            return None

        conn = self._get_conn()
        cur = conn.cursor()

        record_id = str(uuid.uuid4())
        cur.execute("""
            INSERT INTO geostat_cv_result (
                id, location_id, property_key, variogram_model_id,
                cv_strategy, n_folds, block_size_m,
                mean_error, mean_squared_error, root_mean_squared_error,
                mean_absolute_error, r_squared, fold_results, computed_at, metadata
            ) VALUES (
                %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s::jsonb, NOW(), %s::jsonb
            )
        """, (
            record_id,
            location_id,
            property_key,
            variogram_model_id,
            result["cv_strategy"],
            result["n_folds"],
            result.get("block_size_m"),
            result.get("mean_error"),
            result.get("mean_squared_error"),
            result.get("root_mean_squared_error"),
            result.get("mean_absolute_error"),
            result.get("r_squared"),
            __import__("json").dumps(result.get("fold_results", [])),
            "{}",
        ))

        conn.commit()
        cur.close()
        return record_id
