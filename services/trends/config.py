"""Shared constants and configuration for trend analysis."""

from __future__ import annotations

from typing import Dict, List, Optional

# ---------------------------------------------------------------------------
# Default Parameters
# ---------------------------------------------------------------------------

DEFAULT_MIN_DATA_POINTS = 10
DEFAULT_TREND_WINDOW_DAYS = 90
DEFAULT_SMOOTHING_WINDOW = 7
DEFAULT_SMOOTHING_ALPHA = 0.3
DEFAULT_SIGNIFICANCE_THRESHOLD = 0.05
DEFAULT_CHANGE_POINT_SENSITIVITY = 0.5
DEFAULT_FORECAST_HORIZON = 30

# ---------------------------------------------------------------------------
# Time Unit Mappings (days per unit)
# ---------------------------------------------------------------------------

TIME_UNIT_DAYS = {
    "hour": 1 / 24,
    "day": 1,
    "week": 7,
    "month": 30.44,
    "quarter": 91.3,
    "year": 365.25,
}

# ---------------------------------------------------------------------------
# Seasonal Periods (in time units)
# ---------------------------------------------------------------------------

SEASONAL_PERIODS = {
    "hourly_daily": 24,          # 24-hour cycle in hourly data
    "daily_weekly": 7,           # 7-day cycle in daily data
    "daily_monthly": 30,         # ~30-day cycle in daily data
    "weekly_yearly": 52,         # 52-week cycle in weekly data
    "monthly_yearly": 12,        # 12-month cycle in monthly data
}

# ---------------------------------------------------------------------------
# Metric-to-Seasonal-Period Mapping
# ---------------------------------------------------------------------------

METRIC_SEASONAL_MAP: Dict[str, Optional[int]] = {
    "soil_moisture": 365,        # Annual rainfall cycle
    "air_temperature": 365,      # Annual temperature cycle
    "rainfall": 365,             # Annual rainfall cycle
    "humidity": 365,             # Annual humidity cycle
    "crop_revenue": 12,          # Monthly revenue cycle
    "harvest_yield": 4,          # Quarterly harvest cycle
    "soil_carbon": None,         # No strong seasonality
    "biodiversity_delta": None,  # No strong seasonality
    "value_flowed": 12,          # Monthly financial cycle
}

# ---------------------------------------------------------------------------
# Confidence Levels
# ---------------------------------------------------------------------------

CONFIDENCE_LEVELS = {
    "high": 0.01,      # p < 0.01
    "moderate": 0.05,  # p < 0.05
    "low": 0.10,       # p < 0.10
}

# ---------------------------------------------------------------------------
# Trend Direction Thresholds
# ---------------------------------------------------------------------------

DIRECTION_THRESHOLDS = {
    "slope_epsilon": 0.001,    # Minimum slope to be non-zero
    "r_squared_min": 0.3,      # Minimum r-squared for "moderate" confidence
    "r_squared_high": 0.7,     # Minimum r-squared for "high" confidence
}

# ---------------------------------------------------------------------------
# Change-Point Detection Defaults
# ---------------------------------------------------------------------------

CHANGE_POINT_METHODS = ["cusum", "pelt", "binary_segmentation"]
CUSUM_THRESHOLD = 5.0
CUSUM_DRIFT = 0.5
PELT_PENALTY = 10.0

# ---------------------------------------------------------------------------
# ARIMA Defaults
# ---------------------------------------------------------------------------

ARIMA_MAX_P = 3
ARIMA_MAX_D = 2
ARIMA_MAX_Q = 3
ARIMA_SEASONAL = False

# ---------------------------------------------------------------------------
# Dashboard Refresh Interval
# ---------------------------------------------------------------------------

DASHBOARD_REFRESH_HOURS = 6
