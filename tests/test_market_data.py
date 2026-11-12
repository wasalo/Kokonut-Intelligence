"""
Market Data Tests

Unit tests for the market data ingestion module.
Does not require a running database.

Usage:
    python3 -m tests.test_market_data
    python3 -m pytest tests/test_market_data.py -v
"""

import os
import sys
from io import BytesIO
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.ingestion import market_data
from services.ingestion.market_data import (
    COMMODITY_SEED_DATA,
    CROP_ALIASES,
    find_crop_id,
    normalize_name,
    parse_pink_sheet,
)


def _xlsx_bytes(rows):
    import openpyxl

    workbook = openpyxl.Workbook()
    worksheet = workbook.active
    worksheet.title = "Monthly Prices"
    for row in rows:
        worksheet.append(row)
    output = BytesIO()
    workbook.save(output)
    workbook.close()
    return output.getvalue()


def test_resolve_pink_sheet_url_discovers_official_current_workbook(monkeypatch):
    monkeypatch.delenv("WORLD_BANK_PINK_SHEET_URL", raising=False)
    page = MagicMock()
    page.text = (
        '<a href="/en/doc/2026/related/CMO-Historical-Data-Monthly.xlsx">Monthly prices</a>'
    )
    monkeypatch.setattr(market_data.http, "get", MagicMock(return_value=page))

    url = market_data.resolve_pink_sheet_url()

    assert url == (
        "https://www.worldbank.org/en/doc/2026/related/CMO-Historical-Data-Monthly.xlsx"
    )
    market_data.http.get.assert_called_once_with(market_data.WORLD_BANK_LANDING_PAGE_URL, timeout=20)
    page.close.assert_called_once()


def test_resolve_pink_sheet_url_accepts_only_official_https_override(monkeypatch):
    override = (
        "https://thedocs.worldbank.org/en/doc/current/related/"
        "CMO-Historical-Data-Monthly.xlsx"
    )
    monkeypatch.setenv("WORLD_BANK_PINK_SHEET_URL", override)
    monkeypatch.setattr(market_data.http, "get", MagicMock())

    assert market_data.resolve_pink_sheet_url() == override
    market_data.http.get.assert_not_called()

    with pytest.raises(ValueError, match="HTTPS workbook link"):
        market_data.resolve_pink_sheet_url(
            "https://example.invalid/CMO-Historical-Data-Monthly.xlsx"
        )


def test_download_pink_sheet_resolves_link_then_downloads_workbook(monkeypatch):
    monkeypatch.delenv("WORLD_BANK_PINK_SHEET_URL", raising=False)
    landing = MagicMock()
    landing.text = (
        '<a href="https://thedocs.worldbank.org/en/doc/2026/related/'
        'CMO-Historical-Data-Monthly.xlsx">Monthly prices</a>'
    )
    workbook = MagicMock()
    workbook.content = b"PK workbook"
    workbook.headers = {"Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}
    monkeypatch.setattr(market_data.http, "get", MagicMock(side_effect=[landing, workbook]))

    assert market_data.download_pink_sheet() == b"PK workbook"
    assert [call.args[0] for call in market_data.http.get.call_args_list] == [
        market_data.WORLD_BANK_LANDING_PAGE_URL,
        "https://thedocs.worldbank.org/en/doc/2026/related/CMO-Historical-Data-Monthly.xlsx",
    ]
    landing.close.assert_called_once()
    workbook.close.assert_called_once()


def test_resolve_pink_sheet_url_fails_closed_when_official_link_is_missing(monkeypatch):
    monkeypatch.delenv("WORLD_BANK_PINK_SHEET_URL", raising=False)
    page = MagicMock()
    page.text = '<a href="https://example.invalid/CMO-Historical-Data-Monthly.xlsx">file</a>'
    monkeypatch.setattr(market_data.http, "get", MagicMock(return_value=page))

    with pytest.raises(RuntimeError, match="workbook link was not found"):
        market_data.resolve_pink_sheet_url()

    page.close.assert_called_once()


def test_normalize_name():
    """Test name normalization for forgiving matching."""
    assert normalize_name("Coffee (Arabica)") == "coffee arabica"
    assert normalize_name("Palm Oil") == "palm oil"
    assert normalize_name("  MAIZE  ") == "maize"
    assert normalize_name("Sugar-Cane!") == "sugar cane"


def test_find_crop_id_exact_match():
    """Test crop ID lookup with exact name match."""
    crops = [("uuid-1", "Coffee"), ("uuid-2", "Maize"), ("uuid-3", "Cassava")]
    assert find_crop_id(crops, "COFFEE", "Coffee (Arabica)") == "uuid-1"
    assert find_crop_id(crops, "MAIZE", "Maize") == "uuid-2"


def test_find_crop_id_alias_match():
    """Test crop ID lookup using aliases."""
    crops = [("uuid-1", "Coffee"), ("uuid-2", "Corn")]
    assert find_crop_id(crops, "COFFEE", "Coffee") == "uuid-1"
    assert find_crop_id(crops, "MAIZE", "Corn") == "uuid-2"


def test_find_crop_id_no_match():
    """Test crop ID lookup returns None when no match found."""
    crops = [("uuid-1", "Cassava"), ("uuid-2", "Yam")]
    assert find_crop_id(crops, "COFFEE", "Coffee") is None


def test_seed_data_completeness():
    """Test that seed data covers all 8 commodities."""
    expected = {"COFFEE", "COCOA", "PALM_OIL", "RICE", "MAIZE", "SUGAR", "TEA", "BANANA"}
    assert set(COMMODITY_SEED_DATA.keys()) == expected


def test_parse_current_world_bank_monthly_sheet_layout():
    workbook = _xlsx_bytes([
        ("World Bank Commodity Price Data (The Pink Sheet)",),
        ("monthly prices in nominal US dollars, 1960 to present",),
        ("Updated on November 03, 2026",),
        (
            None, "Cocoa", "Coffee, Arabica", "Tea, avg 3 auctions", "Palm oil",
            "Maize", "Rice, Thai A.1", "Sugar, world", "Banana, US",
        ),
        (
            None, "($/kg)", "($/kg)", "($/kg)", "($/mt)",
            "($/mt)", "($/mt)", "($/kg)", "($/kg)",
        ),
        ("2025M01", 8.1, 7.4, 2.6, 920.0, 190.0, 520.0, 0.41, 1.2),
        ("2025M02", 8.2, 7.5, 2.7, 930.0, 195.0, 525.0, 0.42, 1.3),
    ])

    records = parse_pink_sheet(workbook, target_month=2, target_year=2025)

    assert {record["commodity_code"] for record in records} == {
        "COCOA", "COFFEE", "TEA", "PALM_OIL", "MAIZE", "RICE", "SUGAR", "BANANA",
    }
    assert len(records) == 8
    assert all(record["price_date"] == "2025-02-01" for record in records)
    assert next(record for record in records if record["commodity_code"] == "COFFEE") == {
        "commodity_code": "COFFEE",
        "commodity_name": "Coffee, Arabica",
        "price_date": "2025-02-01",
        "price_per_unit": 7.5,
    }


def test_parse_legacy_world_bank_month_column_layout_remains_supported():
    workbook = _xlsx_bytes([
        (
            "Commodity", "Year", "January", "February", "March", "April", "May",
            "June", "July", "August", "September", "October", "November", "December",
        ),
        ("Coffee Arabica", 2025, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0, 12.0),
    ])

    records = parse_pink_sheet(workbook, target_year=2025)

    assert len(records) == 12
    assert records[0]["commodity_code"] == "COFFEE"
    assert records[0]["price_date"] == "2025-01-01"
    assert records[-1]["price_date"] == "2025-12-01"


def test_seed_data_price_points():
    """Test that each commodity has at least 4 price points."""
    for code, info in COMMODITY_SEED_DATA.items():
        assert len(info["prices"]) >= 4, f"{code} has fewer than 4 price points"
        assert info["unit"], f"{code} missing unit"
        assert info["name"], f"{code} missing name"


def test_crop_aliases_completeness():
    """Test that crop aliases cover all commodities."""
    for code in COMMODITY_SEED_DATA:
        assert code in CROP_ALIASES, f"{code} missing from CROP_ALIASES"
        assert len(CROP_ALIASES[code]) >= 1, f"{code} has no aliases"


def test_find_crop_id_forgiving():
    """Test forgiving matching with partial containment."""
    crops = [("uuid-1", "Arabica Coffee Beans"), ("uuid-2", "Sweet Corn")]
    assert find_crop_id(crops, "COFFEE", "Coffee") == "uuid-1"
    assert find_crop_id(crops, "MAIZE", "Maize") == "uuid-2"
