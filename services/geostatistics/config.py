"""Shared constants and configuration for geostatistics."""
from __future__ import annotations

from typing import Dict, List

DEFAULT_VARIOGRAM_MODELS: List[str] = ["spherical", "exponential", "gaussian"]
DEFAULT_LAG_DISTANCE: float = 100.0  # meters
DEFAULT_LAG_TOLERANCE: float = 50.0  # meters
DEFAULT_BANDWIDTH: float = 1000.0  # meters

DEFAULT_MIN_SAMPLES: int = 10
DEFAULT_MAX_NEIGHBORS: int = 30
DEFAULT_SEARCH_RADIUS_M: float = 2000.0

DEFAULT_SGS_REALIZATIONS: int = 100
DEFAULT_SGS_GRID_SIZE_M: float = 10.0
DEFAULT_SGS_SEED: int = 42

SPATIAL_WEIGHTS_TYPES: List[str] = ["queen", "rook", "distance", "knn"]
DEFAULT_DISTANCE_THRESHOLD: float = 500.0  # meters
DEFAULT_K_NEIGHBORS: int = 8

KRIGING_METHODS: List[str] = ["ordinary", "simple", "indicator"]
SIMULATION_METHODS: List[str] = ["sgs", "sis", "turning_bands"]
CV_STRATEGIES: List[str] = ["spatial_block", "leave_one_out", "k_fold"]

PROPERTY_DEFAULTS: Dict[str, Dict] = {
    "soil_carbon": {
        "model_type": "exponential",
        "lag_distance": 50.0,
        "lag_tolerance": 25.0,
        "default_range_m": 500.0,
    },
    "soil_moisture": {
        "model_type": "spherical",
        "lag_distance": 25.0,
        "lag_tolerance": 12.5,
        "default_range_m": 300.0,
    },
    "soil_ph": {
        "model_type": "gaussian",
        "lag_distance": 100.0,
        "lag_tolerance": 50.0,
        "default_range_m": 800.0,
    },
    "ndvi": {
        "model_type": "exponential",
        "lag_distance": 200.0,
        "lag_tolerance": 100.0,
        "default_range_m": 2000.0,
    },
    "rainfall": {
        "model_type": "spherical",
        "lag_distance": 1000.0,
        "lag_tolerance": 500.0,
        "default_range_m": 10000.0,
    },
    "temperature": {
        "model_type": "gaussian",
        "lag_distance": 500.0,
        "lag_tolerance": 250.0,
        "default_range_m": 5000.0,
    },
}
