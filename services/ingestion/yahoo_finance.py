"""Yahoo Finance commodity futures ingestion.

Fetches daily/real-time agricultural commodity futures prices
from Yahoo Finance. Free, no authentication required.

Usage:
    python3 -m services.ingestion.yahoo_finance
    python3 -m services.ingestion.yahoo_finance --commodity coffee
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ..common.logging import get_logger
from .base import log_ingestion, hash_payload
from .oracle_aggregator import PriceReading

logger = get_logger("ingestion.yahoo_finance")

# Yahoo Finance ticker mapping for agricultural commodities
YAHOO_TICKERS = {
    "COFFEE": "KC=F",      # Arabica Coffee Futures (ICE)
    "COCOA": "CC=F",       # Cocoa Futures (ICE)
    "PALM_OIL": "PO=F",    # Crude Palm Oil Futures (BMD)
    "RICE": "ZR=F",        # Rough Rice Futures (CBOT)
    "MAIZE": "ZC=F",       # Corn Futures (CBOT)
    "SUGAR": "SB=F",       # Sugar #11 Futures (ICE)
    # TEA and BANANA have no direct Yahoo Finance ticker
    # They fall back to World Bank data
}

# Valid commodities in our system
VALID_COMMODITIES = {"COFFEE", "COCOA", "PALM_OIL", "RICE", "MAIZE", "SUGAR", "TEA", "BANANA"}


def fetch_yahoo_price(commodity: str) -> Optional[PriceReading]:
    """Fetch current price for a commodity from Yahoo Finance.

    Args:
        commodity: Commodity name (e.g., 'COFFEE', 'COCOA').

    Returns:
        PriceReading or None if unavailable.
    """
    ticker = YAHOO_TICKERS.get(commodity)
    if not ticker:
        logger.info("No Yahoo Finance ticker for %s, falling back to World Bank", commodity)
        return None

    try:
        import yfinance as yf
    except ImportError:
        logger.warning("yfinance not installed. Run: pip install yfinance")
        return None

    try:
        ticker_obj = yf.Ticker(ticker)
        hist = ticker_obj.history(period="1d")

        if hist.empty:
            logger.warning("No data returned for %s (%s)", commodity, ticker)
            return None

        latest_price = float(hist["Close"].iloc[-1])
        latest_date = hist.index[-1].to_pydatetime().replace(tzinfo=timezone.utc)

        return PriceReading(
            source=f"yahoo_finance_{ticker}",
            price=latest_price,
            timestamp=latest_date,
            confidence=0.8,  # Yahoo Finance has ~15min delay for futures
            metadata={
                "ticker": ticker,
                "exchange": ticker.split("=")[1] if "=" in ticker else "unknown",
                "volume": int(hist["Volume"].iloc[-1]) if "Volume" in hist else 0,
            },
        )
    except Exception as e:
        logger.error("Yahoo Finance fetch failed for %s: %s", commodity, e)
        return None


def fetch_all_yahoo_prices() -> Dict[str, PriceReading]:
    """Fetch prices for all commodities with Yahoo Finance tickers.

    Returns:
        {commodity: PriceReading}
    """
    results = {}
    for commodity in YAHOO_TICKERS:
        reading = fetch_yahoo_price(commodity)
        if reading:
            results[commodity] = reading
            logger.info("Fetched %s: $%.2f from %s", commodity, reading.price, reading.source)
    return results


def run() -> Dict[str, Any]:
    """Main ingestion entry point. Fetches Yahoo Finance prices."""
    prices = fetch_all_yahoo_prices()
    success = 0
    errors = 0

    for commodity, reading in prices.items():
        try:
            log_ingestion(
                source_system="yahoo_finance",
                source_table="commodity_futures",
                source_id=reading.source,
                target_table="price_observation",
                target_id=None,
                operation="insert",
                payload_hash=hash_payload({"commodity": commodity, "price": reading.price}),
                status="success",
                rows_affected=1,
            )
            success += 1
        except Exception as e:
            errors += 1
            logger.error("Failed to log ingestion for %s: %s", commodity, e)

    logger.info("Yahoo Finance ingestion complete: %d success, %d errors", success, errors)
    return {"status": "success", "prices_fetched": success, "errors": errors}
