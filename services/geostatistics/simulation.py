"""Geostatistical simulation with seeded conditional Gaussian fields.

Generates multiple conditional spatial realizations for uncertainty
quantification without materializing a dense grid covariance matrix.
"""

from __future__ import annotations

import math
import uuid
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import psycopg2
import psycopg2.extras

from .config import (
    DEFAULT_SGS_GRID_SIZE_M,
    DEFAULT_SGS_MODE_NO,
    DEFAULT_SGS_REALIZATIONS,
    DEFAULT_SGS_SEED,
    MAX_SGS_GRID_POINTS,
    MAX_SGS_MODE_NO,
    MAX_SGS_OUTPUT_VALUES,
    MAX_SGS_REALIZATIONS,
)
from .data_sources import location_point_query, supports_database_property


class GeostatSimulator:
    """Seeded conditional Gaussian fields for uncertainty quantification."""

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

    def _build_grid(
        self,
        coordinates: List[Tuple[float, float]],
        resolution_m: float,
        padding_m: float = 100.0,
    ) -> np.ndarray:
        """Build a regular prediction grid while enforcing the kernel grid cap."""
        coords = np.asarray(coordinates, dtype=float)
        x_min, y_min = coords.min(axis=0) - padding_m
        x_max, y_max = coords.max(axis=0) + padding_m

        x_count = math.ceil((x_max - x_min) / resolution_m)
        y_count = math.ceil((y_max - y_min) / resolution_m)
        if x_count * y_count > MAX_SGS_GRID_POINTS:
            raise ValueError(
                f"Simulation grid exceeds the {MAX_SGS_GRID_POINTS}-point limit; "
                "increase grid resolution"
            )
        x_grid = x_min + np.arange(x_count) * resolution_m
        y_grid = y_min + np.arange(y_count) * resolution_m
        xx, yy = np.meshgrid(x_grid, y_grid)
        return np.column_stack([xx.ravel(), yy.ravel()])

    @staticmethod
    def _validate_inputs(
        coordinates: List[Tuple[float, float]],
        values: List[float],
        variogram_model: Dict[str, Any],
        n_realizations: int,
        grid_resolution_m: float,
        seed: int,
        mode_no: int,
    ) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, str]]]:
        try:
            coords = np.asarray(coordinates, dtype=float)
            field = np.asarray(values, dtype=float)
            model_type = variogram_model["model_type"]
            sill = float(variogram_model["sill"])
            range_m = float(variogram_model["range"])
            nugget = float(variogram_model["nugget"])
        except (KeyError, OverflowError, TypeError, ValueError):
            return None, {"error": "Invalid simulation input"}

        if field.ndim != 1 or len(field) < 3:
            return None, {
                "error": "Simulation requires at least three observations"
            }
        if coords.ndim != 2 or coords.shape != (len(field), 2):
            return None, {
                "error": "Coordinates and values must have matching 2D points"
            }
        if not np.isfinite(coords).all() or not np.isfinite(field).all():
            return None, {
                "error": "Coordinates and values must be finite"
            }
        settings, error = GeostatSimulator._validate_run_settings(
            n_realizations, grid_resolution_m, seed, mode_no
        )
        if error:
            return None, error
        if (
            not isinstance(model_type, str)
            or model_type not in {"spherical", "exponential", "gaussian", "matern"}
            or not np.isfinite([sill, range_m, nugget]).all()
            or sill <= 0
            or range_m <= 0
            or nugget < 0
            or nugget >= sill
        ):
            return None, {"error": "Invalid variogram model"}
        n_realizations, grid_resolution_m, seed, mode_no = settings
        return {
            "coordinates": coords,
            "values": field,
            "model_type": model_type,
            "sill": sill,
            "range": range_m,
            "nugget": nugget,
            "n_realizations": n_realizations,
            "grid_resolution_m": grid_resolution_m,
            "seed": seed,
            "mode_no": mode_no,
        }, None

    @staticmethod
    def _validate_run_settings(n_realizations, grid_resolution_m, seed, mode_no):
        try:
            resolution = float(grid_resolution_m)
        except (OverflowError, TypeError, ValueError):
            return None, {"error": "grid_resolution_m must be finite and greater than zero"}
        if (
            isinstance(n_realizations, bool)
            or not isinstance(n_realizations, (int, np.integer))
            or not 1 <= n_realizations <= MAX_SGS_REALIZATIONS
        ):
            return None, {
                "error": f"n_realizations must be an integer from 1 to {MAX_SGS_REALIZATIONS}"
            }
        if not np.isfinite(resolution) or resolution <= 0:
            return None, {"error": "grid_resolution_m must be finite and greater than zero"}
        if (
            isinstance(seed, bool)
            or not isinstance(seed, (int, np.integer))
            or not 0 <= seed <= 2**32 - 1
        ):
            return None, {"error": "seed must be an integer between 0 and 4294967295"}
        if (
            isinstance(mode_no, bool)
            or not isinstance(mode_no, (int, np.integer))
            or not 1 <= mode_no <= MAX_SGS_MODE_NO
        ):
            return None, {
                "error": f"mode_no must be an integer from 1 to {MAX_SGS_MODE_NO}"
            }
        return (int(n_realizations), resolution, int(seed), int(mode_no)), None

    def sequential_gaussian_simulation(
        self,
        coordinates: List[Tuple[float, float]],
        values: List[float],
        variogram_model: Dict[str, Any],
        n_realizations: int = DEFAULT_SGS_REALIZATIONS,
        grid_resolution_m: float = DEFAULT_SGS_GRID_SIZE_M,
        seed: int = DEFAULT_SGS_SEED,
        mode_no: int = DEFAULT_SGS_MODE_NO,
    ) -> Dict[str, Any]:
        """Generate seeded conditional Gaussian field realizations.

        Args:
            coordinates: Observed (x, y) positions in meters.
            values: Observed values.
            variogram_model: Fitted variogram parameters.
            n_realizations: Number of realizations to generate.
            grid_resolution_m: Grid cell size in meters.
            seed: Random seed for reproducibility.
            mode_no: GSTools random modes; lower values trade spectral fidelity
                for runtime and are recorded with persisted realizations.

        Returns:
            Dict with realizations (list of arrays), grid, metadata.
        """
        inputs, error = self._validate_inputs(
            coordinates, values, variogram_model, n_realizations,
            grid_resolution_m, seed, mode_no
        )
        if error:
            return error
        coords = inputs["coordinates"]
        field = inputs["values"]
        model_type = inputs["model_type"]
        sill = inputs["sill"]
        range_m = inputs["range"]
        nugget = inputs["nugget"]
        n_realizations = inputs["n_realizations"]
        grid_resolution_m = inputs["grid_resolution_m"]
        seed = inputs["seed"]
        mode_no = inputs["mode_no"]
        try:
            grid = self._build_grid(coords, grid_resolution_m)
        except ValueError as exc:
            return {"error": str(exc)}
        # Count the realization values, two coordinate values per grid point,
        # and four returned summary maps in the same aggregate budget.
        output_values = (n_realizations + 6) * len(grid)
        if len(grid) == 0 or output_values > MAX_SGS_OUTPUT_VALUES:
            return {
                "error": (
                    "Requested simulation output exceeds the "
                    f"{MAX_SGS_OUTPUT_VALUES}-value limit; reduce realizations "
                    "or increase grid resolution"
                )
            }

        import gstools as gs

        sk_model = self._build_gstools_variogram(
            model_type, sill, range_m, nugget
        )
        kriging = gs.krige.Ordinary(
            sk_model, [coords[:, 0], coords[:, 1]], field
        )
        conditional_srf = gs.CondSRF(
            kriging, mode_no=mode_no, sampling="auto"
        )
        conditional_srf.set_pos([grid[:, 0], grid[:, 1]])
        seed_stream = gs.random.MasterRNG(seed)
        real_arr = np.empty((n_realizations, len(grid)), dtype=float)
        for index in range(n_realizations):
            realization = np.asarray(
                conditional_srf(
                    seed=seed_stream(), store=False, krige_store=False
                ),
                dtype=float,
            ).reshape(-1)
            if realization.shape != (len(grid),) or not np.isfinite(realization).all():
                return {"error": "Conditional simulation returned invalid values"}
            real_arr[index] = realization

        # Compute E-type (mean) and percentiles.
        e_type = np.mean(real_arr, axis=0)
        p10 = np.percentile(real_arr, 10, axis=0)
        p50 = np.percentile(real_arr, 50, axis=0)
        p90 = np.percentile(real_arr, 90, axis=0)

        return {
            "realizations": real_arr.tolist(),
            "n_realizations": n_realizations,
            "grid_points": grid.tolist(),
            "n_points": len(grid),
            "e_type": e_type.tolist(),
            "p10": p10.tolist(),
            "p50": p50.tolist(),
            "p90": p90.tolist(),
            "grid_resolution_m": grid_resolution_m,
            "seed": seed,
            "mode_no": mode_no,
            "simulation_engine": "gstools_conditional_random_field",
            "simulation_generator": "RandMeth",
            "simulation_sampling": "auto",
            "gstools_version": getattr(gs, "__version__", "unknown"),
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
        mode_no: int = DEFAULT_SGS_MODE_NO,
    ) -> Dict[str, Any]:
        """Run conditional Gaussian field simulation from database sources."""
        if not supports_database_property(property_key):
            return {"error": f"Unsupported property_key: {property_key}"}
        settings, error = self._validate_run_settings(
            n_realizations, grid_resolution_m, seed, mode_no
        )
        if error:
            return error
        n_realizations, grid_resolution_m, seed, mode_no = settings

        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # Fetch or fit variogram
        if variogram_model_id:
            cur.execute(
                """
                SELECT model_type, sill, range, nugget
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
            }
        else:
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
            return {"error": f"Need >= 3 data points, got {len(rows)}"}

        # Convert to meters around the mean source coordinate.
        try:
            lats = np.array([float(r["lat"]) for r in rows])
            lons = np.array([float(r["lon"]) for r in rows])
            values = np.array([float(r["value"]) for r in rows])
        except (KeyError, OverflowError, TypeError, ValueError):
            return {"error": "Simulation source contains invalid coordinates or values"}
        if not np.isfinite([*lats, *lons, *values]).all():
            return {"error": "Simulation source contains non-finite coordinates or values"}
        if (
            np.any((lats < -90) | (lats > 90))
            or np.any((lons < -180) | (lons > 180))
        ):
            return {"error": "Simulation source contains out-of-range coordinates"}
        if np.any(np.abs(lats) >= 89.9):
            return {"error": "Simulation source is too close to a pole for local projection"}
        mean_lat, mean_lon = np.mean(lats), np.mean(lons)
        lat_to_m = 111320.0
        lon_to_m = 111320.0 * np.cos(np.radians(mean_lat))

        coordinates = [
            (float(lon - mean_lon) * lon_to_m, float(lat - mean_lat) * lat_to_m)
            for lat, lon in zip(lats, lons)
        ]
        result = self.sequential_gaussian_simulation(
            coordinates, values, variogram_model,
            n_realizations=n_realizations,
            grid_resolution_m=grid_resolution_m,
            seed=seed,
            mode_no=mode_no,
        )
        if "error" in result:
            return result
        result["location_id"] = location_id
        result["property_key"] = property_key
        result["coordinate_origin"] = {
            "latitude": float(mean_lat),
            "longitude": float(mean_lon),
        }
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

        origin = result.get("coordinate_origin")
        try:
            origin_lat = float(origin["latitude"])
            origin_lon = float(origin["longitude"])
            grid_pts = np.asarray(result["grid_points"], dtype=float)
            realizations = np.asarray(result["realizations"], dtype=float)
        except (KeyError, OverflowError, TypeError, ValueError):
            return None
        mode_no = result.get("mode_no")
        if mode_no is not None:
            if (
                isinstance(mode_no, bool)
                or not isinstance(mode_no, (int, np.integer))
                or not 1 <= mode_no <= MAX_SGS_MODE_NO
            ):
                return None
            mode_no = int(mode_no)
        if (
            not np.isfinite([origin_lat, origin_lon]).all()
            or not -89.9 < origin_lat < 89.9
            or not -180 <= origin_lon <= 180
            or grid_pts.ndim != 2
            or grid_pts.shape[1:] != (2,)
            or realizations.ndim != 2
            or realizations.shape[1:] != (len(grid_pts),)
            or isinstance(max_points, bool)
            or not isinstance(max_points, (int, np.integer))
            or max_points < 1
            or isinstance(max_realizations, bool)
            or not isinstance(max_realizations, (int, np.integer))
            or max_realizations < 1
        ):
            return None

        realizations = realizations[:max_realizations]
        if len(realizations) == 0:
            return None
        valid = np.isfinite(grid_pts).all(axis=1) & np.isfinite(realizations).all(axis=0)
        grid_pts = grid_pts[valid]
        realizations = realizations[:, valid]
        if len(grid_pts) == 0:
            return None

        # The simulation grid uses local meters; convert it back to WGS84 for
        # insertion into the schema's geometry(4326) column.
        lon_to_m = 111320.0 * np.cos(np.radians(origin_lat))
        grid_pts = np.column_stack(
            [origin_lon + grid_pts[:, 0] / lon_to_m, origin_lat + grid_pts[:, 1] / 111320.0]
        )
        grid_pts[:, 0] = ((grid_pts[:, 0] + 180.0) % 360.0) - 180.0
        valid_world = np.isfinite(grid_pts).all(axis=1) & (grid_pts[:, 1] >= -90) & (grid_pts[:, 1] <= 90)
        grid_pts = grid_pts[valid_world]
        realizations = realizations[:, valid_world]
        if len(grid_pts) == 0:
            return None

        point_count = min(len(grid_pts), int(max_points))
        point_indices = np.linspace(0, len(grid_pts) - 1, point_count, dtype=int)

        conn = self._get_conn()
        cur = conn.cursor()

        realization_ids = []
        for i, real_arr in enumerate(realizations):
            real_id = str(uuid.uuid4())
            realization_ids.append(real_id)

            cur.execute("""
                INSERT INTO geostat_realization (
                    id, location_id, variogram_model_id, property_key,
                    realization_number, grid_resolution_m, n_points,
                    method, seed, metadata
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
                psycopg2.extras.Json(
                    {
                        key: value
                        for key, value in {
                            "simulation_engine": result.get("simulation_engine"),
                            "simulation_generator": result.get("simulation_generator"),
                            "simulation_sampling": result.get("simulation_sampling"),
                            "gstools_version": result.get("gstools_version"),
                            "mode_no": mode_no,
                        }.items()
                        if value is not None
                    }
                ),
            ))

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
