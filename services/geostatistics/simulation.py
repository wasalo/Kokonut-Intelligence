"""Geostatistical Simulation — Sequential Gaussian Simulation (SGS).

Generates multiple equiprobable spatial realizations for uncertainty
quantification, enabling probabilistic forecasting of environmental outcomes.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import psycopg2
import psycopg2.extras

from .config import (
    DEFAULT_SGS_GRID_SIZE_M,
    DEFAULT_SGS_REALIZATIONS,
    DEFAULT_SGS_SEED,
    DEFAULT_MAX_NEIGHBORS,
    DEFAULT_SEARCH_RADIUS_M,
    SIMULATION_METHODS,
    PROPERTY_DEFAULTS,
)


class GeostatSimulator:
    """Sequential Gaussian Simulation for uncertainty quantification."""

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
        from gstools import Spherical, Exponential, Gaussian, Matern

        model_map = {
            "spherical": Spherical,
            "exponential": Exponential,
            "gaussian": Gaussian,
            "matern": Matern,
        }
        ModelClass = model_map.get(model_type, Exponential)
        return ModelClass(dim=2, var=sill - nugget, len_scale=range_m, nugget=nugget)

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

    def sequential_gaussian_simulation(
        self,
        coordinates: List[Tuple[float, float]],
        values: List[float],
        variogram_model: Dict[str, Any],
        n_realizations: int = DEFAULT_SGS_REALIZATIONS,
        grid_resolution_m: float = DEFAULT_SGS_GRID_SIZE_M,
        seed: int = DEFAULT_SGS_SEED,
    ) -> Dict[str, Any]:
        """Generate multiple SGS realizations.

        Args:
            coordinates: Observed (x, y) positions in meters.
            values: Observed values.
            variogram_model: Fitted variogram parameters.
            n_realizations: Number of realizations to generate.
            grid_resolution_m: Grid cell size in meters.
            seed: Random seed for reproducibility.

        Returns:
            Dict with realizations (list of arrays), grid, metadata.
        """
        pos = np.array(coordinates).T
        field = np.array(values, dtype=float)

        model = self._build_gstools_variogram(
            variogram_model["model_type"],
            variogram_model["sill"],
            variogram_model["range"],
            variogram_model["nugget"],
        )

        grid = self._build_grid(coordinates, grid_resolution_m)

        # Use gstools for conditional simulation via kriging + random field
        from gstools import krige

        realizations = []

        pos = np.array(coordinates).T
        field = np.array(values, dtype=float)

        # Pre-compute kriging once (same conditioning for all realizations)
        sk_model = self._build_gstools_variogram(
            variogram_model["model_type"],
            variogram_model["sill"],
            variogram_model["range"],
            variogram_model["nugget"],
        )
        sk = krige.Simple(sk_model, [pos[0].tolist(), pos[1].tolist()], field.tolist())
        cond_mean, cond_var = sk(grid.T)
        cond_std = np.sqrt(np.maximum(cond_var, 0))

        # Compute covariance matrix for unconditional field generation
        from scipy.spatial.distance import pdist, squareform
        dist_matrix = squareform(pdist(grid))
        sill_total = variogram_model["sill"]
        # Vectorized variogram evaluation
        flat_dists = dist_matrix.ravel()
        gamma_vals = sk_model.variogram(flat_dists)
        cov_matrix = (sill_total - gamma_vals).reshape(dist_matrix.shape)
        np.fill_diagonal(cov_matrix, sill_total)

        for i in range(n_realizations):
            rng_local = np.random.RandomState(seed + i)

            # Generate unconditional Gaussian field via Cholesky decomposition
            try:
                L = np.linalg.cholesky(cov_matrix + np.eye(len(grid)) * 1e-8)
                uncond_field = L @ rng_local.normal(0, 1, len(grid))
            except np.linalg.LinAlgError:
                uncond_field = rng_local.normal(0, np.sqrt(sill_total), len(grid))

            # Combine: conditional mean + scaled residual
            residual = uncond_field - np.mean(uncond_field)
            if np.std(residual) > 0:
                residual = residual / np.std(residual)
            combined = cond_mean + residual * cond_std

            realizations.append(combined.tolist())

        # Compute E-type (mean) and percentiles
        real_arr = np.array(realizations)
        e_type = np.mean(real_arr, axis=0)
        p10 = np.percentile(real_arr, 10, axis=0)
        p50 = np.percentile(real_arr, 50, axis=0)
        p90 = np.percentile(real_arr, 90, axis=0)

        return {
            "realizations": realizations,
            "n_realizations": n_realizations,
            "grid_points": grid.tolist(),
            "n_points": len(grid),
            "e_type": e_type.tolist(),
            "p10": p10.tolist(),
            "p50": p50.tolist(),
            "p90": p90.tolist(),
            "grid_resolution_m": grid_resolution_m,
            "seed": seed,
            "variogram_model": variogram_model,
        }

    def compute_e_type(self, realizations: List[List[float]]) -> List[float]:
        """Compute E-type (mean) map from realizations."""
        return np.mean(np.array(realizations), axis=0).tolist()

    def compute_percentiles(
        self,
        realizations: List[List[float]],
        percentiles: List[float] = [10, 50, 90],
    ) -> Dict[str, List[float]]:
        """Compute percentile maps from realizations."""
        arr = np.array(realizations)
        result = {}
        for p in percentiles:
            result[f"p{int(p)}"] = np.percentile(arr, p, axis=0).tolist()
        return result

    def simulation_from_db(
        self,
        location_id: str,
        property_key: str,
        n_realizations: int = DEFAULT_SGS_REALIZATIONS,
        grid_resolution_m: float = DEFAULT_SGS_GRID_SIZE_M,
        seed: int = DEFAULT_SGS_SEED,
        variogram_model_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Run SGS pipeline from database queries."""
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

        result = self.sequential_gaussian_simulation(
            coordinates, values, variogram_model,
            n_realizations=n_realizations,
            grid_resolution_m=grid_resolution_m,
            seed=seed,
        )
        result["location_id"] = location_id
        result["property_key"] = property_key
        return result

    def persist_simulations(
        self,
        location_id: str,
        property_key: str,
        variogram_model_id: str,
        result: Dict[str, Any],
        max_points: int = 2000,
        max_realizations: int = 10,
    ) -> Optional[str]:
        """Persist simulation results to the database.

        Caps at max_points per realization and max_realizations to avoid
        excessive storage.
        """
        if "error" in result:
            return None

        conn = self._get_conn()
        cur = conn.cursor()

        grid_pts = np.array(result["grid_points"])
        realizations = result["realizations"][:max_realizations]
        n_real = len(realizations)

        # Subsample points if needed
        if len(grid_pts) > max_points:
            point_indices = np.random.choice(len(grid_pts), max_points, replace=False)
        else:
            point_indices = np.arange(len(grid_pts))

        realization_ids = []
        for i, real in enumerate(realizations):
            real_id = str(uuid.uuid4())
            realization_ids.append(real_id)

            cur.execute("""
                INSERT INTO geostat_realization (
                    id, location_id, variogram_model_id, property_key,
                    realization_number, grid_resolution_m, n_points,
                    method, seed
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                real_id,
                location_id,
                variogram_model_id,
                property_key,
                i + 1,
                result.get("grid_resolution_m"),
                len(point_indices),
                "sgs",
                result.get("seed"),
            ))

            real_arr = np.array(real)
            for idx in point_indices:
                pt_id = str(uuid.uuid4())
                pt = grid_pts[idx]
                cur.execute("""
                    INSERT INTO geostat_realization_point (
                        id, realization_id, point_geometry, simulated_value
                    ) VALUES (
                        %s, %s,
                        ST_SetSRID(ST_MakePoint(%s, %s), 4326),
                        %s
                    )
                """, (
                    pt_id,
                    real_id,
                    float(pt[0]),
                    float(pt[1]),
                    float(real_arr[idx]),
                ))

        conn.commit()
        cur.close()
        return realization_ids[0] if realization_ids else None
