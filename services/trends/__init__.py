"""Trend Analysis — Statistical tools for time series pattern detection."""

from .estimator import TrendEstimator
from .significance import TrendSignificance
from .smoothing import TimeSeriesSmoothing
from .decomposer import SeasonalDecomposer
from .change_points import ChangePointDetector
from .forecasting import TimeSeriesForecaster
from .accuracy import ForecastAccuracy
from .dashboard import TrendDashboard

__all__ = [
    "TrendEstimator",
    "TrendSignificance",
    "TimeSeriesSmoothing",
    "SeasonalDecomposer",
    "ChangePointDetector",
    "TimeSeriesForecaster",
    "ForecastAccuracy",
    "TrendDashboard",
]
