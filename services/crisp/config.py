"""CRISP scoring configuration."""

from __future__ import annotations

from datetime import datetime, timezone

from ..common.db import PG_DB, PG_HOST, PG_PASSWORD, PG_PORT, PG_USER

CRISP_VERSION = f"v{datetime.now(timezone.utc).strftime('%Y.%m')}"

# Default dimension weights (sum to 1.0)
DEFAULT_WEIGHTS = {
    "carbon_yield": 0.40,
    "climate": 0.25,
    "policy": 0.15,
    "financial": 0.10,
    "implementation": 0.10,
}

# Risk score ranges (0-100, higher = more risk)
RISK_SCORE_MIN = 0.0
RISK_SCORE_MAX = 100.0

# Rating bands (composite score -> rating)
# Bands use [low, high) — exclusive upper bound
RATING_BANDS = {
    "AAA": (91, 101),  # 91-100 inclusive
    "AA": (80, 91),    # 80-90 inclusive
    "A": (69, 80),     # 69-79 inclusive
    "B": (44, 69),     # 44-68 inclusive
    "C": (20, 44),     # 20-43 inclusive
    "D": (0, 20),      # 0-19 inclusive (fallback catches rest)
}

# Confidence thresholds based on evidence maturity
CONFIDENCE_THRESHOLDS = {
    6: "high",
    5: "high",
    4: "moderate",
    3: "moderate",
    2: "low",
    1: "insufficient_evidence",
}
