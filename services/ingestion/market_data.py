#!/usr/bin/env python3
"""
Market Data Ingestion — Commodity Prices

Fetches commodity price data from the World Bank Pink Sheet (XLS downloads)
and routes writes through the isolated market-data worker.

The World Bank Commodity Price Data (Pink Sheet) covers 70+ commodities
with monthly prices. This module downloads the XLS file and extracts
prices for the 8 Kokonut commodities.

Usage:
    python3 -m services.ingestion.market_data --source world_bank
    python3 -m services.ingestion.market_data --source world_bank --month 6 --year 2026
    python3 -m services.ingestion.market_data --source seed
    python3 -m services.ingestion.market_data --commodity COFFEE
"""

import argparse
import os
import re
import sys
from io import BytesIO

from services.common.cli import print_json
from services.common.http import http
from services.core.features import is_enabled

from ..common.logging import get_logger

logger = get_logger("ingestion.market")

# World Bank Pink Sheet XLS URL pattern
# Updated periodically; the exact URL changes each month
WORLD_BANK_BASE_URL = "https://thedocs.worldbank.org/en/1c3f894e-2c54-48b5-a79d-2e6c9c47b3af"

# Fallback URL for the latest available Pink Sheet
WORLD_BANK_FALLBACK_URL = os.environ.get(
    "WORLD_BANK_PINK_SHEET_URL",
    f"{WORLD_BANK_BASE_URL}/CMO-Historical-Data-Monthly.xlsx",
)

# Commodity seed data (fallback when live download unavailable)
COMMODITY_SEED_DATA = {
    "COFFEE": {
        "name": "Coffee (Arabica)",
        "unit": "USD/kg",
        "prices": [
            {"date": "2024-01-01", "price": 5.23},
            {"date": "2024-04-01", "price": 6.12},
            {"date": "2024-07-01", "price": 5.87},
            {"date": "2024-10-01", "price": 6.45},
            {"date": "2025-01-01", "price": 7.89},
            {"date": "2025-04-01", "price": 8.52},
        ],
    },
    "COCOA": {
        "name": "Cocoa",
        "unit": "USD/kg",
        "prices": [
            {"date": "2024-01-01", "price": 4.12},
            {"date": "2024-04-01", "price": 4.89},
            {"date": "2024-07-01", "price": 5.23},
            {"date": "2024-10-01", "price": 6.01},
            {"date": "2025-01-01", "price": 7.15},
            {"date": "2025-04-01", "price": 7.89},
        ],
    },
    "PALM_OIL": {
        "name": "Palm Oil",
        "unit": "USD/tonne",
        "prices": [
            {"date": "2024-01-01", "price": 780},
            {"date": "2024-04-01", "price": 810},
            {"date": "2024-07-01", "price": 795},
            {"date": "2024-10-01", "price": 830},
            {"date": "2025-01-01", "price": 865},
            {"date": "2025-04-01", "price": 890},
        ],
    },
    "RICE": {
        "name": "Rice",
        "unit": "USD/tonne",
        "prices": [
            {"date": "2024-01-01", "price": 520},
            {"date": "2024-04-01", "price": 535},
            {"date": "2024-07-01", "price": 515},
            {"date": "2024-10-01", "price": 540},
            {"date": "2025-01-01", "price": 555},
            {"date": "2025-04-01", "price": 570},
        ],
    },
    "MAIZE": {
        "name": "Maize",
        "unit": "USD/tonne",
        "prices": [
            {"date": "2024-01-01", "price": 195},
            {"date": "2024-04-01", "price": 205},
            {"date": "2024-07-01", "price": 198},
            {"date": "2024-10-01", "price": 210},
            {"date": "2025-01-01", "price": 218},
            {"date": "2025-04-01", "price": 225},
        ],
    },
    "SUGAR": {
        "name": "Sugar",
        "unit": "USD/kg",
        "prices": [
            {"date": "2024-01-01", "price": 0.28},
            {"date": "2024-04-01", "price": 0.31},
            {"date": "2024-07-01", "price": 0.29},
            {"date": "2024-10-01", "price": 0.33},
            {"date": "2025-01-01", "price": 0.35},
            {"date": "2025-04-01", "price": 0.37},
        ],
    },
    "TEA": {
        "name": "Tea",
        "unit": "USD/kg",
        "prices": [
            {"date": "2024-01-01", "price": 2.45},
            {"date": "2024-04-01", "price": 2.58},
            {"date": "2024-07-01", "price": 2.52},
            {"date": "2024-10-01", "price": 2.65},
            {"date": "2025-01-01", "price": 2.78},
            {"date": "2025-04-01", "price": 2.85},
        ],
    },
    "BANANA": {
        "name": "Bananas",
        "unit": "USD/kg",
        "prices": [
            {"date": "2024-01-01", "price": 1.12},
            {"date": "2024-04-01", "price": 1.18},
            {"date": "2024-07-01", "price": 1.15},
            {"date": "2024-10-01", "price": 1.22},
            {"date": "2025-01-01", "price": 1.28},
            {"date": "2025-04-01", "price": 1.32},
        ],
    },
}

CROP_ALIASES = {
    "COFFEE": ["coffee", "arabica coffee"],
    "COCOA": ["cocoa", "cacao", "trinitario cacao"],
    "PALM_OIL": ["palm", "oil palm", "palm oil"],
    "RICE": ["rice"],
    "MAIZE": ["maize", "corn"],
    "SUGAR": ["sugar", "sugarcane", "sugar cane"],
    "TEA": ["tea"],
    "BANANA": ["banana", "bananas", "plantain"],
}

# Pink Sheet column headers we look for (case-insensitive partial matches)
_PINK_SHEET_MONTHS = [
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december",
]


def normalize_name(value: str) -> str:
    """Normalize crop and commodity names for forgiving matching."""
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def find_crop_id(crops: list[tuple], commodity_code: str, commodity_name: str):
    """Match commodity prices to local crop names using aliases and containment."""
    candidates = [commodity_code.replace("_", " "), commodity_name]
    candidates.extend(CROP_ALIASES.get(commodity_code, []))
    normalized_candidates = [normalize_name(candidate) for candidate in candidates]

    for crop_id, crop_name in crops:
        crop_norm = normalize_name(crop_name)
        for candidate in normalized_candidates:
            if candidate and (crop_norm == candidate or candidate in crop_norm or crop_norm in candidate):
                return crop_id
    return None


def download_pink_sheet(url: str = None) -> bytes:
    """Download the World Bank Pink Sheet XLS file.

    Returns the raw bytes of the XLS file.
    Raises requests.RequestException on network errors.
    """
    target_url = url or WORLD_BANK_FALLBACK_URL
    logger.info("Downloading Pink Sheet from %s...", target_url)

    resp = http.get(target_url, timeout=60)
    resp.raise_for_status()

    content_type = resp.headers.get("Content-Type", "")
    if "spreadsheet" not in content_type and "excel" not in content_type and "octet-stream" not in content_type:
        logger.warning("Unexpected Content-Type: %s (proceeding anyway)", content_type)

    logger.info("Downloaded %d bytes", len(resp.content))
    return resp.content


def parse_pink_sheet(xls_bytes: bytes, target_month: int = None, target_year: int = None) -> list:
    """Parse the World Bank Pink Sheet XLS and extract commodity prices.

    Returns list of dicts with:
        commodity_code, commodity_name, price_date, price_per_unit, unit
    """
    try:
        import openpyxl
    except ImportError:
        raise RuntimeError(
            "openpyxl is required for World Bank Pink Sheet parsing"
        ) from None

    wb = openpyxl.load_workbook(BytesIO(xls_bytes), read_only=True, data_only=True)

    # Try common sheet names
    sheet_name = None
    for name in wb.sheetnames:
        name_lower = name.lower()
        if "monthly" in name_lower or "pink" in name_lower or "commodity" in name_lower:
            sheet_name = name
            break
    if not sheet_name:
        sheet_name = wb.sheetnames[0]

    ws = wb[sheet_name]
    rows = list(ws.iter_rows(values_only=True))
    wb.close()

    if not rows:
        logger.warning("Empty sheet: %s", sheet_name)
        return []

    # Find header row (contains "Commodity" or "Unit")
    header_idx = None
    for i, row in enumerate(rows):
        row_str = " ".join(str(c).lower() for c in row if c)
        if "commodity" in row_str or "unit" in row_str:
            header_idx = i
            break
    if header_idx is None:
        header_idx = 0

    headers = [str(c).strip() if c else "" for c in rows[header_idx]]

    # Find month columns
    month_cols = {}
    for col_idx, header in enumerate(headers):
        header_lower = header.lower()
        for m_idx, month_name in enumerate(_PINK_SHEET_MONTHS):
            if month_name in header_lower:
                month_cols[m_idx + 1] = col_idx
                break

    # Find year column
    year_col = None
    for col_idx, header in enumerate(headers):
        header_lower = header.lower()
        if "year" in header_lower or "date" in header_lower:
            year_col = col_idx
            break

    if not month_cols:
        logger.warning("Could not identify month columns in Pink Sheet")
        return []

    # Map commodity names to our codes
    COMMODITY_NAME_MAP = {
        "coffee": "COFFEE",
        "arabica": "COFFEE",
        "cocoa": "COCOA",
        "cacao": "COCOA",
        "palm oil": "PALM_OIL",
        "rice": "RICE",
        "maize": "MAIZE",
        "corn": "MAIZE",
        "sugar": "SUGAR",
        "tea": "TEA",
        "banana": "BANANA",
        "bananas": "BANANA",
    }

    records = []
    current_year = None

    for row in rows[header_idx + 1:]:
        if not row or all(c is None for c in row):
            continue

        # Check if this row has a year
        if year_col is not None and row[year_col] is not None:
            try:
                year_val = int(row[year_col])
                if 1960 <= year_val <= 2030:
                    current_year = year_val
            except (ValueError, TypeError):
                pass

        if current_year is None:
            continue

        # First column is typically the commodity name
        commodity_name = str(row[0]).strip() if row[0] else ""
        commodity_lower = commodity_name.lower()

        commodity_code = None
        for key, code in COMMODITY_NAME_MAP.items():
            if key in commodity_lower:
                commodity_code = code
                break

        if not commodity_code:
            continue

        # Extract prices from month columns
        for month_num, col_idx in month_cols.items():
            if target_month and month_num != target_month:
                continue
            if target_year and current_year != target_year:
                continue

            if col_idx >= len(row):
                continue

            val = row[col_idx]
            if val is None:
                continue

            try:
                price = float(val)
            except (ValueError, TypeError):
                continue

            if price <= 0:
                continue

            date_str = f"{current_year}-{month_num:02d}-01"
            records.append({
                "commodity_code": commodity_code,
                "commodity_name": commodity_name,
                "price_date": date_str,
                "price_per_unit": price,
            })

    return records


def prepare_world_bank_records(
    records: list[dict],
    commodity: str = None,
    source_url: str = None,
) -> list[dict]:
    """Normalize parsed World Bank rows to the canonical stored representation."""
    commodity = commodity.upper() if commodity else None
    if commodity and commodity not in COMMODITY_SEED_DATA:
        raise ValueError(f"Unknown commodity: {commodity}")

    selected = [
        record for record in records
        if commodity is None or record["commodity_code"] == commodity
    ]
    if not selected:
        raise RuntimeError(
            f"World Bank Pink Sheet returned no records for {commodity or 'supported commodities'}"
        )

    unit_map = {
        "COFFEE": "USD/kg",
        "COCOA": "USD/kg",
        "PALM_OIL": "USD/tonne",
        "RICE": "USD/tonne",
        "MAIZE": "USD/tonne",
        "SUGAR": "USD/kg",
        "TEA": "USD/kg",
        "BANANA": "USD/kg",
    }
    return [
        {
            "commodity_code": record["commodity_code"],
            "commodity_name": record["commodity_name"],
            "market_name": "World Bank Pink Sheet",
            "price_date": record["price_date"],
            "price_per_unit": record["price_per_unit"],
            "unit": unit_map[record["commodity_code"]],
            "currency": "USD",
            "source": "world_bank_pink_sheet",
            "source_url": source_url or WORLD_BANK_FALLBACK_URL,
            "metadata": {"source_type": "live_download"},
        }
        for record in selected
    ]


def validate_world_bank_filters(
    commodity: str | None = None,
    month: int | None = None,
    year: int | None = None,
) -> str | None:
    """Validate commodity and date-filter bounds shared by both entrypoints."""
    normalized_commodity = commodity.upper() if commodity else None
    if normalized_commodity and normalized_commodity not in COMMODITY_SEED_DATA:
        raise ValueError(f"Unknown commodity: {normalized_commodity}")
    if month is not None and not 1 <= month <= 12:
        raise ValueError("month must be between 1 and 12")
    if year is not None and not 1960 <= year <= 2030:
        raise ValueError("year must be between 1960 and 2030")
    return normalized_commodity


def insert_price(db, record: dict) -> tuple[str | None, bool]:
    """Reject legacy direct writes; use the isolated market-data operations."""
    del db, record
    raise RuntimeError(
        "direct price_observation writes are retired; use the isolated market-data worker"
    )


def run_seed_data(commodity: str = None):
    """Insert reference samples through the dedicated bounded writer."""
    from services.ingestion.market_data_worker import seed_reference_data

    inserted = seed_reference_data(commodity)
    logger.info("Done: %d reference price observations inserted", inserted)
    return inserted


def run_world_bank(commodity: str = None, month: int = None, year: int = None):
    """Compatibility entrypoint; writes go through the isolated worker."""
    from services.ingestion.market_data_worker import ingest

    inserted = ingest(commodity, month, year)
    logger.info("Done: %d new price observations inserted", inserted)
    return inserted


def run(commodity: str = None, source: str = "world_bank", month: int = None, year: int = None):
    """Keep the legacy command shape while requiring isolated write authority."""
    from services.ingestion.market_data_worker import run_source

    if source not in {"world_bank", "seed"}:
        logger.error("Unknown source: %s. Use 'world_bank' or 'seed'.", source)
        sys.exit(1)
    return run_source(commodity, source, month, year)


def build_parser() -> argparse.ArgumentParser:
    """Build the standalone and unified CLI parser."""
    parser = argparse.ArgumentParser(
        prog="market_data.py",
        description="Market data ingestion",
    )
    parser.add_argument("--commodity", help="Specific commodity code (e.g., COFFEE)")
    parser.add_argument(
        "--source",
        default="world_bank",
        choices=["world_bank", "seed"],
        help="Data source (default: world_bank)",
    )
    parser.add_argument("--month", type=int, help="Month (1-12) to fetch from Pink Sheet")
    parser.add_argument("--year", type=int, help="Year to fetch from Pink Sheet")
    return parser


def main(argv: list[str] | None = None) -> None:
    """Run market-data ingestion through a callable CLI entry point."""
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        validate_world_bank_filters(
            args.commodity,
            args.month if args.source == "world_bank" else None,
            args.year if args.source == "world_bank" else None,
        )
    except ValueError as exc:
        parser.error(str(exc))
    if args.source == "seed" and (args.month is not None or args.year is not None):
        parser.error("month and year filters are only valid for world_bank")
    if not is_enabled("isolated_market_data_worker"):
        print_json({
            "status": "skipped",
            "reason": "isolated_market_data_worker_disabled",
        })
        return
    run(commodity=args.commodity, source=args.source, month=args.month, year=args.year)


if __name__ == "__main__":
    main()
