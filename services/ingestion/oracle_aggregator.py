"""Multi-source oracle aggregation with median consensus.

Aggregates price data from multiple sources, rejects outliers,
and produces consensus prices with confidence scoring.

Usage:
    from services.ingestion.oracle_aggregator import median_consensus, PriceReading
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from statistics import median, stdev
from typing import Any, Dict, List, Optional

from ..common.logging import get_logger

logger = get_logger("ingestion.oracle_aggregator")


@dataclass
class PriceReading:
    """A price reading from a single source."""
    source: str
    price: float
    timestamp: datetime
    confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConsensusResult:
    """Result of multi-source consensus aggregation."""
    commodity: str
    price: float
    source: str
    timestamp: datetime
    confidence: float
    source_count: int
    deviation_pct: float
    aggregation_method: str
    sources_used: List[str]
    sources_rejected: List[str]
    metadata: Dict[str, Any] = field(default_factory=dict)


def median_consensus(
    readings: List[PriceReading],
    max_deviation_pct: float = 15.0,
    commodity: str = "",
) -> Optional[ConsensusResult]:
    """Compute median price from multiple sources, rejecting outliers.

    Implements a 3-source median consensus:
    - If all sources agree within max_deviation_pct, return the median.
    - If one source deviates > max_deviation_pct, flag as outlier.
    - If 2/3 agree, use their median.
    - If all disagree, return median with low confidence.

    Args:
        readings: List of PriceReading from different sources.
        max_deviation_pct: Maximum allowed deviation from median (%).
        commodity: Commodity name for the result.

    Returns:
        ConsensusResult or None if no readings.
    """
    if not readings:
        return None

    prices = [r.price for r in readings]
    med = median(prices)

    if med <= 0:
        logger.warning("Median price is zero or negative for %s", commodity)
        return None

    # Filter to sources within deviation threshold
    inliers = []
    outliers = []
    for r in readings:
        deviation = abs(r.price - med) / med * 100
        if deviation <= max_deviation_pct:
            inliers.append(r)
        else:
            outliers.append(r)
            logger.info(
                "Outlier rejected: %s price %.2f deviates %.1f%% from median %.2f",
                r.source, r.price, deviation, med,
            )

    if len(inliers) >= 2:
        inlier_prices = [r.price for r in inliers]
        consensus_price = median(inlier_prices)
        confidence = min(1.0, len(inliers) / 3.0)

        # Compute deviation among inliers
        if len(inlier_prices) > 1:
            dev_pct = round(stdev(inlier_prices) / consensus_price * 100, 4)
        else:
            dev_pct = 0.0

        return ConsensusResult(
            commodity=commodity,
            price=round(consensus_price, 6),
            source="consensus",
            timestamp=max(r.timestamp for r in inliers),
            confidence=round(confidence, 4),
            source_count=len(inliers),
            deviation_pct=dev_pct,
            aggregation_method="median_consensus",
            sources_used=[r.source for r in inliers],
            sources_rejected=[r.source for r in outliers],
            metadata={
                "inlier_count": len(inliers),
                "outlier_count": len(outliers),
                "max_deviation_pct": max_deviation_pct,
            },
        )
    else:
        # All sources disagree significantly
        return ConsensusResult(
            commodity=commodity,
            price=round(med, 6),
            source="consensus_low_confidence",
            timestamp=max(r.timestamp for r in readings),
            confidence=0.3,
            source_count=len(readings),
            deviation_pct=round(stdev(prices) / med * 100, 4) if len(prices) > 1 else 0.0,
            aggregation_method="median_consensus",
            sources_used=[r.source for r in readings],
            sources_rejected=[],
            metadata={
                "warning": "high_deviation",
                "all_sources_disagree": True,
            },
        )


def weighted_average_consensus(
    readings: List[PriceReading],
    commodity: str = "",
) -> Optional[ConsensusResult]:
    """Compute weighted average price from multiple sources.

    Weight = source confidence (0-1).
    """
    if not readings:
        return None

    total_weight = sum(r.confidence for r in readings)
    if total_weight <= 0:
        return None

    weighted_price = sum(r.price * r.confidence for r in readings) / total_weight
    confidence = min(1.0, total_weight / len(readings))

    prices = [r.price for r in readings]
    dev_pct = round(stdev(prices) / weighted_price * 100, 4) if len(prices) > 1 and weighted_price > 0 else 0.0

    return ConsensusResult(
        commodity=commodity,
        price=round(weighted_price, 6),
        source="weighted_consensus",
        timestamp=max(r.timestamp for r in readings),
        confidence=round(confidence, 4),
        source_count=len(readings),
        deviation_pct=dev_pct,
        aggregation_method="weighted_average",
        sources_used=[r.source for r in readings],
        sources_rejected=[],
        metadata={"total_weight": round(total_weight, 4)},
    )


def aggregate_prices(
    readings_by_commodity: Dict[str, List[PriceReading]],
    method: str = "median",
    max_deviation_pct: float = 15.0,
) -> Dict[str, ConsensusResult]:
    """Aggregate prices for multiple commodities.

    Args:
        readings_by_commodity: {commodity: [PriceReading, ...]}
        method: 'median' or 'weighted'
        max_deviation_pct: Max deviation for median consensus.

    Returns:
        {commodity: ConsensusResult}
    """
    results = {}
    for commodity, readings in readings_by_commodity.items():
        if method == "weighted":
            result = weighted_average_consensus(readings, commodity)
        else:
            result = median_consensus(readings, max_deviation_pct, commodity)
        if result:
            results[commodity] = result
    return results
