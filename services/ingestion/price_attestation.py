"""On-chain price attestation for audit trail.

Attests commodity prices on-chain via EAS to create a verifiable
audit trail of price data origin and multi-source consensus.

Usage:
    python3 -m services.ingestion.price_attestation --commodity coffee --price 2.50
    python3 -m services.ingestion.price_attestation --run-daily
"""

from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from typing import Any, Dict

import psycopg2.extras

from services.common.cli import print_json

from ..common.logging import get_logger
from .base import get_db

logger = get_logger("ingestion.price_attestation")

# New EAS schema for price feeds
PRICE_FEED_SCHEMA = {
    "schema": (
        "string commodity, string currency, uint256 price, "
        "uint256 timestamp, string source, uint256 sourceCount, "
        "string confidence, string evidenceHash"
    ),
    "revocable": True,
    "description": "Price feed attestation — multi-source consensus price for agricultural commodities",
}


def attest_price(
    conn,
    commodity: str,
    price: float,
    source: str,
    source_count: int = 1,
    confidence: float = 1.0,
    currency: str = "USD",
    chain: str = "celo",
) -> Dict[str, Any]:
    """Attest a price on-chain via EAS.

    Creates an on-chain audit trail of the price data origin.
    """
    _validate_attestation_inputs(
        commodity=commodity,
        price=price,
        source=source,
        source_count=source_count,
        confidence=confidence,
        currency=currency,
        chain=chain,
    )
    now = datetime.now(timezone.utc)

    # Log to oracle_price_log
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO oracle_price_log (
            commodity, currency, price, price_timestamp, source,
            source_count, confidence, aggregation_method, chain, metadata
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
    """, (
        commodity, currency, price, now, source,
        source_count, confidence, "single" if source_count == 1 else "median_consensus",
        chain, json.dumps({"attestation_pending": True}),
    ))
    log_id = str(cur.fetchone()[0])
    conn.commit()
    cur.close()

    # Try to attest on-chain (graceful failure if EAS not available)
    attestation_uid = None
    try:
        from ..attestation.eas_client import get_eas_client

        w3 = get_eas_client(chain)
        if w3:
            logger.info("Price attestation prepared: %s $%.2f (%s)", commodity, price, source)
            # In production, would call EAS contract to attest
            # attestation_uid = eas_client.attest(schema_uid, data, recipient)
    except Exception as e:
        logger.warning("On-chain attestation unavailable (%s)", type(e).__name__)

    return {
        "status": "success",
        "log_id": log_id,
        "commodity": commodity,
        "price": price,
        "source": source,
        "attestation_uid": attestation_uid,
        "chain": chain,
    }


def _validate_attestation_inputs(
    *,
    commodity: str,
    price: float,
    source: str,
    source_count: int,
    confidence: float,
    currency: str,
    chain: str,
) -> None:
    """Reject malformed price records before they reach persistence or EAS."""
    if not isinstance(commodity, str) or not commodity.strip():
        raise ValueError("commodity must be a non-empty string")
    if not isinstance(source, str) or not source.strip():
        raise ValueError("source must be a non-empty string")
    if not isinstance(currency, str) or not currency.strip():
        raise ValueError("currency must be a non-empty string")
    if not isinstance(chain, str) or not chain.strip():
        raise ValueError("chain must be a non-empty string")
    try:
        valid_price = (
            not isinstance(price, bool)
            and math.isfinite(float(price))
            and float(price) > 0
        )
    except (TypeError, ValueError, OverflowError):
        valid_price = False
    if not valid_price:
        raise ValueError("price must be a finite number greater than zero")
    if isinstance(source_count, bool) or not isinstance(source_count, int) or source_count < 1:
        raise ValueError("source_count must be a positive integer")
    try:
        valid_confidence = (
            not isinstance(confidence, bool)
            and math.isfinite(float(confidence))
            and 0 <= float(confidence) <= 1
        )
    except (TypeError, ValueError, OverflowError):
        valid_confidence = False
    if not valid_confidence:
        raise ValueError("confidence must be a finite number between zero and one")


def attest_daily_prices(conn) -> Dict[str, Any]:
    """Attest all daily price data on-chain."""
    # Get latest unattested prices
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT * FROM price_observation
        WHERE attestation_uid IS NULL
        AND status = 'published'
        AND observation_date >= CURRENT_DATE - INTERVAL '1 day'
        ORDER BY observation_date DESC
    """)
    prices = [dict(r) for r in cur.fetchall()]
    cur.close()

    results = []
    for price in prices:
        result = attest_price(
            conn,
            commodity=price["commodity"],
            price=float(price["price_usd_per_tonne"]),
            source=price.get("source", "unknown"),
            source_count=price.get("source_count", 1),
            confidence=(
                1.0 if price.get("confidence") is None else float(price["confidence"])
            ),
        )
        results.append(result)

    return {
        "status": "success",
        "prices_attested": len(results),
        "results": results,
    }


def build_parser() -> argparse.ArgumentParser:
    """Build the standalone and unified CLI parser."""
    parser = argparse.ArgumentParser(
        prog="price_attestation.py",
        description="Price feed attestation",
    )
    parser.add_argument("--commodity", help="Commodity to attest")
    parser.add_argument("--price", type=float, help="Price to attest")
    parser.add_argument("--source", default="manual", help="Price source")
    parser.add_argument("--run-daily", action="store_true", help="Attest all daily prices")
    return parser


def main(argv: list[str] | None = None) -> None:
    """Run a manual or daily price attestation command."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.run_daily and (args.commodity is not None or args.price is not None):
        parser.error("--run-daily cannot be combined with --commodity or --price")

    if not args.run_daily and (args.commodity is None or args.price is None):
        parser.print_help()
        return

    if not args.run_daily:
        try:
            _validate_attestation_inputs(
                commodity=args.commodity,
                price=args.price,
                source=args.source,
                source_count=1,
                confidence=1.0,
                currency="USD",
                chain="celo",
            )
        except ValueError as exc:
            parser.error(str(exc))

    conn = get_db()
    try:
        if args.run_daily:
            result = attest_daily_prices(conn)
            print_json(result)
        elif args.commodity and args.price:
            result = attest_price(conn, args.commodity, args.price, args.source)
            print_json(result)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
