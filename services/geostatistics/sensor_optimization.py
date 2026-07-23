"""Sensor Network Design — optimal spacing from variogram parameters.

Uses variogram range to determine optimal sensor placement, assess
coverage gaps, and recommend network configurations.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import psycopg2
import psycopg2.extras

from .config import (
    PROPERTY_DEFAULTS,
)


class SensorNetworkDesigner:
    """Optimal sensor network design from variogram parameters."""

    def __init__(self, conn=None):
        self._conn = conn

    def _get_conn(self):
        if self._conn is None:
            from services.common.database import get_db
            self._conn = get_db()
        return self._conn

    def compute_optimal_spacing(
        self,
        variogram_range: float,
        confidence_level: float = 0.95,
    ) -> Dict[str, Any]:
        """Compute optimal sensor spacing from variogram range.

        At distance = range, spatial correlation drops to ~0.
        For higher coverage, use range * factor where factor < 1.

        Args:
            variogram_range: Range parameter from fitted variogram (meters).
            confidence_level: Target coverage confidence (0.90, 0.95, 0.99).

        Returns:
            Dict with optimal_spacing_m, coverage_radius_m, factor.
        """
        # Coverage factor based on confidence level
        # Higher confidence requires denser spacing
        factor_map = {
            0.80: 0.8,
            0.85: 0.75,
            0.90: 0.7,
            0.95: 0.5,
            0.99: 0.35,
        }

        factor = factor_map.get(confidence_level, 0.5)
        optimal_spacing = variogram_range * factor

        return {
            "optimal_spacing_m": round(optimal_spacing, 2),
            "coverage_radius_m": round(variogram_range, 2),
            "factor": factor,
            "confidence_level": confidence_level,
            "variogram_range_m": variogram_range,
        }

    def compute_coverage_map(
        self,
        sensor_positions: List[Tuple[float, float]],
        variogram_range: float,
        area_polygon: Optional[List[Tuple[float, float]]] = None,
        grid_resolution_m: float = 10.0,
    ) -> Dict[str, Any]:
        """Compute coverage quality map for a sensor network.

        Each grid cell gets a score based on the number of sensors
        within the variogram range.

        Returns:
            Dict with grid_points, coverage_scores, coverage_stats.
        """
        sensors = np.array(sensor_positions)

        if area_polygon is not None:
            poly = np.array(area_polygon)
            x_min, y_min = poly.min(axis=0)
            x_max, y_max = poly.max(axis=0)
        else:
            padding = variogram_range
            x_min, y_min = sensors.min(axis=0) - padding
            x_max, y_max = sensors.max(axis=0) + padding

        x_grid = np.arange(x_min, x_max, grid_resolution_m)
        y_grid = np.arange(y_min, y_max, grid_resolution_m)
        xx, yy = np.meshgrid(x_grid, y_grid)
        grid = np.column_stack([xx.ravel(), yy.ravel()])

        # Compute coverage: number of sensors within range for each grid cell
        from scipy.spatial.distance import cdist
        dists = cdist(grid, sensors)
        n_sensors_in_range = np.sum(dists <= variogram_range, axis=1)

        # Coverage quality: 0 (no coverage) to 1 (well covered)
        # A cell is "well covered" if at least 2 sensors are within range
        coverage_score = np.clip(n_sensors_in_range / 2.0, 0.0, 1.0)

        # Stats
        pct_fully_covered = float(np.mean(coverage_score >= 1.0) * 100)
        pct_partially_covered = float(np.mean(coverage_score > 0) * 100)
        pct_uncovered = float(np.mean(coverage_score == 0) * 100)

        return {
            "grid_points": grid.tolist(),
            "coverage_scores": coverage_score.tolist(),
            "n_sensors_in_range": n_sensors_in_range.tolist(),
            "grid_resolution_m": grid_resolution_m,
            "stats": {
                "pct_fully_covered": round(pct_fully_covered, 1),
                "pct_partially_covered": round(pct_partially_covered, 1),
                "pct_uncovered": round(pct_uncovered, 1),
                "total_grid_cells": len(grid),
            },
        }

    def assess_current_network(
        self,
        sensor_positions: List[Tuple[float, float]],
        variogram_range: float,
        area_polygon: List[Tuple[float, float]],
        property_key: str = "soil_moisture",
    ) -> Dict[str, Any]:
        """Assess the current sensor network and identify gaps.

        Returns:
            Dict with optimal_spacing, current_count, recommended_count,
            coverage_gap_pct, gap_locations, recommendations.
        """
        # Compute optimal spacing
        design = self.compute_optimal_spacing(variogram_range)

        # Compute area
        poly = np.array(area_polygon)
        # Simple polygon area using shoelace formula
        n = len(poly)
        area_m2 = 0.0
        for i in range(n):
            j = (i + 1) % n
            area_m2 += poly[i][0] * poly[j][1]
            area_m2 -= poly[j][0] * poly[i][1]
        area_m2 = abs(area_m2) / 2.0
        area_ha = area_m2 / 10000.0

        # Optimal number of sensors
        spacing = design["optimal_spacing_m"]
        # Hexagonal packing: sensors per hectare ≈ 1.155 / spacing²
        optimal_per_ha = 1.155 / (spacing ** 2) * 10000
        recommended_n = max(1, int(np.ceil(area_ha * optimal_per_ha)))

        # Coverage assessment
        coverage = self.compute_coverage_map(
            sensor_positions, variogram_range, area_polygon
        )

        # Find gap locations (uncovered grid cells)
        gap_points = [
            grid_pt
            for grid_pt, score in zip(
                coverage["grid_points"], coverage["coverage_scores"]
            )
            if score == 0
        ]

        # Sample up to 10 gap locations for recommendations
        if len(gap_points) > 10:
            indices = np.random.choice(len(gap_points), 10, replace=False)
            gap_samples = [gap_points[i] for i in indices]
        else:
            gap_samples = gap_points

        return {
            "property_key": property_key,
            "variogram_range_m": variogram_range,
            "optimal_spacing_m": design["optimal_spacing_m"],
            "coverage_radius_m": design["coverage_radius_m"],
            "area_ha": round(area_ha, 2),
            "current_n_sensors": len(sensor_positions),
            "recommended_n_sensors": recommended_n,
            "coverage_gap_pct": coverage["stats"]["pct_uncovered"],
            "pct_fully_covered": coverage["stats"]["pct_fully_covered"],
            "gap_locations": gap_samples,
            "recommendations": self._generate_recommendations(
                len(sensor_positions), recommended_n, coverage["stats"]["pct_uncovered"]
            ),
        }

    def _generate_recommendations(
        self,
        current_n: int,
        recommended_n: int,
        gap_pct: float,
    ) -> List[str]:
        """Generate actionable recommendations."""
        recs = []
        if current_n < recommended_n:
            deficit = recommended_n - current_n
            recs.append(
                f"Add {deficit} sensor(s) to reach recommended density."
            )
        if current_n > recommended_n * 1.5:
            recs.append(
                "Network is over-dense; consider removing redundant sensors "
                "to reduce cost."
            )
        if gap_pct > 20:
            recs.append(
                f"{gap_pct:.0f}% of the area is uncovered. Prioritize "
                "placing sensors in uncovered zones."
            )
        if gap_pct < 5:
            recs.append("Coverage is excellent. No immediate changes needed.")
        return recs

    def design_from_db(
        self,
        location_id: str,
        property_key: str = "soil_moisture",
    ) -> Dict[str, Any]:
        """Run sensor network design from database data.

        Fetches sensor positions and variogram model, then computes optimal design.
        """
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # Fetch variogram model
        cur.execute("""
            SELECT * FROM variogram_model
            WHERE location_id = %s AND property_key = %s
            ORDER BY fitted_at DESC LIMIT 1
        """, (location_id, property_key))
        vm_row = cur.fetchone()

        if vm_row is None:
            cur.close()
            return {"error": f"No variogram model found for {property_key} at {location_id}"}

        variogram_range = float(vm_row["range"])

        # Fetch sensor positions
        cur.execute("""
            SELECT sd.latitude, sd.longitude
            FROM sensor_device sd
            WHERE sd.location_id = %s
              AND sd.latitude IS NOT NULL
              AND sd.longitude IS NOT NULL
        """, (location_id,))
        sensors = cur.fetchall()

        # Fetch area polygon
        cur.execute("""
            SELECT ST_AsGeoJSON(boundary) AS boundary_geojson
            FROM location WHERE id = %s
        """, (location_id,))
        loc_row = cur.fetchone()

        cur.close()

        if not sensors:
            return {"error": f"No sensors found for location {location_id}"}

        # Convert sensor lat/lon to meters
        sensor_lats = np.array([float(s["latitude"]) for s in sensors])
        sensor_lons = np.array([float(s["longitude"]) for s in sensors])
        mean_lat, mean_lon = np.mean(sensor_lats), np.mean(sensor_lons)
        lat_to_m = 111320.0
        lon_to_m = 111320.0 * np.cos(np.radians(mean_lat))

        sensor_positions = [
            (float(lon - mean_lon) * lon_to_m, float(lat - mean_lat) * lat_to_m)
            for lat, lon in zip(sensor_lats, sensor_lons)
        ]

        # Parse area polygon
        area_polygon = None
        if loc_row and loc_row["boundary_geojson"]:
            import json
            geojson = json.loads(loc_row["boundary_geojson"])
            if geojson.get("type") == "Polygon":
                coords = geojson["coordinates"][0]
                area_polygon = [
                    (float(c[0] - mean_lon) * lon_to_m, float(c[1] - mean_lat) * lat_to_m)
                    for c in coords
                ]

        if area_polygon is None:
            # Create bounding box from sensors
            padding = variogram_range * 2
            area_polygon = [
                (sensor_positions[:, 0].min() - padding, sensor_positions[:, 1].min() - padding),
                (sensor_positions[:, 0].max() + padding, sensor_positions[:, 1].min() - padding),
                (sensor_positions[:, 0].max() + padding, sensor_positions[:, 1].max() + padding),
                (sensor_positions[:, 0].min() - padding, sensor_positions[:, 1].max() + padding),
            ]

        result = self.assess_current_network(
            sensor_positions, variogram_range, area_polygon, property_key
        )
        result["location_id"] = location_id
        result["variogram_model_id"] = str(vm_row["id"])
        return result

    def persist_design(
        self,
        location_id: str,
        property_key: str,
        result: Dict[str, Any],
    ) -> Optional[str]:
        """Persist sensor network design to the database."""
        if "error" in result:
            return None

        conn = self._get_conn()
        cur = conn.cursor()

        record_id = str(uuid.uuid4())
        cur.execute("""
            INSERT INTO sensor_network_design (
                id, location_id, property_key, variogram_model_id,
                optimal_spacing_m, coverage_radius_m,
                recommended_n_sensors, current_n_sensors,
                coverage_gap_pct, confidence_level, notes, computed_at, metadata
            ) VALUES (
                %s, %s, %s, %s,
                %s, %s,
                %s, %s,
                %s, %s, %s, NOW(), %s::jsonb
            )
        """, (
            record_id,
            location_id,
            property_key,
            result.get("variogram_model_id"),
            result["optimal_spacing_m"],
            result["coverage_radius_m"],
            result["recommended_n_sensors"],
            result["current_n_sensors"],
            result["coverage_gap_pct"],
            0.95,
            "\n".join(result.get("recommendations", [])),
            "{}",
        ))

        conn.commit()
        cur.close()
        return record_id
