#!/usr/bin/env python3
"""
Market Data Ingestion — Commodity Prices

Fetches commodity price data from public APIs (FAO, World Bank)
and inserts into price_observation (PostgreSQL).

Usage:
    python -m services.ingestion.market_data
    python -m services.ingestion.market_data --commodity COFFEE
"""

import argparse
import json
import sys
import time
from datetime import datetime, timezone, timedelta

import requests

from .base import get_db, log_ingestion, hash_payload, retry

# FAO GIEWS Global Food Price Data (free, no API key)
FAO_API_BASE = "https://fpma.fao.org/giews/fpmat4/api/v1/price/dashboard"


# Commodity code mapping (Kokonut crops → FAO codes)
COMMODITY_MAP = {
    "COFFEE": {"fao_code": "061", "name": "Coffee", "unit": "USD/kg"},
    "COCOA": {"fao_code": "063", "name": "Cocoa", "unit": "USD/kg"},
    "BANANA": {"fao_code": "041", "name": "Bananas", "unit": "USD/kg"},
    "PALM_OIL": {"fao_code": "257", "name": "Palm oil", "unit": "USD/tonne"},
    "RICE": {"fao_code": "045", "name": "Rice", "unit": "USD/tonne"},
    "MAIZE": {"fao_code": "044", "name": "Maize", "unit": "USD/tonne"},
    "SUGAR": {"fao_code": "067", "name": "Sugar", "unit": "USD/kg"},
    "TEA": {"fao_code": "062", "name": "Tea", "unit": "USD/kg"},
}


@retry(max_retries=3, backoff=2.0)
def fetch_fao_prices(commodity_code: str, start_date: str, end_date: str) -> list:
    """Fetch prices from FAO GIEWS API."""
    resp = requests.get(
        FAO_API_BASE,
        params={
            "commodity": commodity_code,
            "start_date": start_date,
            "end_date": end_date,
        },
        timeout=15,
    )
    if resp.status_code == 200:
        return resp.json().get("data", [])
    return []


@retry(max_retries=3, backoff=2.0)
def fetch_world_bank_prices(indicator: str, start_date: int, end_date: int) -> list:
    """Fetch prices from World Bank Commodity Price Data."""
    resp = requests.get(
        f"https://api.worldbank.org/v2/country/WLD/indicator/{indicator}",
        params={
            "date": f"{start_date}:{end_date}",
            "format": "json",
            "per_page": 1000,
        },
        timeout=15,
    )
    if resp.status_code == 200:
        data = resp.json()
        if len(data) > 1:
            return data[1]
    return []


def insert_price(db, record: dict) -> str:
    """Insert price observation into PostgreSQL. Returns record ID."""
    with db.cursor() as cur:
        cur.execute(
            """
            INSERT INTO price_observation
                (crop_id, commodity_code, market_name, price_date,
                 price_per_unit, unit, currency, source, source_url, metadata)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
            ON CONFLICT DO NOTHING
            RETURNING id
            """,
            (
                record.get("crop_id"),
                record["commodity_code"],
                record.get("market_name", ""),
                record["price_date"],
                record["price_per_unit"],
                record["unit"],
                record.get("currency", "USD"),
                record["source"],
                record.get("source_url", ""),
                json.dumps(record.get("metadata", {})),
            ),
        )
        row = cur.fetchone()
        return str(row[0]) if row else None


def run(commodity: str = None):
    """Main ingestion entry point."""
    db = get_db()

    # Get active crops and map to commodity codes
    with db.cursor() as cur:
        cur.execute("SELECT id, name FROM crop")
        crops = {row[1].upper(): row[0] for row in cur.fetchall()}

    commodities = [commodity] if commodity else list(COMMODITY_MAP.keys())
    end_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    start_date = (datetime.now(timezone.utc) - timedelta(days=90)).strftime("%Y-%m-%d")

    print(f"[Market] Fetching prices for {len(commodities)} commodities...")
    success = 0
    errors = 0

    for code in commodities:
        if code not in COMMODITY_MAP:
            print(f"  ⊙ Unknown commodity: {code}")
            continue

        info = COMMODITY_MAP[code]
        try:
            start = time.time()
            data = fetch_fao_prices(info["fao_code"], start_date, end_date)
            elapsed_ms = int((time.time() - start) * 1000)

            if not data:
                print(f"  ⊙ {info['name']}: no data available")
                continue

            crop_id = crops.get(code)
            inserted = 0

            for item in data:
                record = {
                    "crop_id": crop_id,
                    "commodity_code": code,
                    "market_name": item.get("market", "Global"),
                    "price_date": item.get("date", end_date),
                    "price_per_unit": item.get("value"),
                    "unit": info["unit"],
                    "currency": "USD",
                    "source": "fao_giews",
                    "source_url": f"https://fpma.fao.org/giews/fpmat4/",
                    "metadata": json.dumps(item),
                }
                if record["price_per_unit"]:
                    insert_price(db, record)
                    inserted += 1

            log_ingestion(
                source_system="fao_giews",
                source_table="commodity_prices",
                source_id=code,
                target_table="price_observation",
                target_id=None,
                operation="batch_insert",
                payload_hash=hash_payload(data),
                status="success",
                rows_affected=inserted,
                processing_time_ms=elapsed_ms,
            )
            success += 1
            print(f"  ✓ {info['name']}: {inserted} price records")
            time.sleep(1)  # Rate limiting

        except Exception as e:
            errors += 1
            log_ingestion(
                source_system="fao_giews",
                source_table="commodity_prices",
                source_id=code,
                target_table="price_observation",
                target_id=None,
                operation="batch_insert",
                payload_hash="",
                status="failed",
                error_message=str(e),
            )
            print(f"  ✗ {info['name']}: {e}")

    db.commit()
    db.close()
    print(f"\n[Market] Done: {success} success, {errors} errors")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Market data ingestion")
    parser.add_argument("--commodity", help="Specific commodity code (e.g., COFFEE)")
    args = parser.parse_args()
    run(commodity=args.commodity)
