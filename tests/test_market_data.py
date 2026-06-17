"""
Market Data Tests

Unit tests for the market data ingestion module.
Does not require a running database.

Usage:
    python3 -m tests.test_market_data
    python3 -m pytest tests/test_market_data.py -v
"""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.ingestion.market_data import (
    normalize_name,
    find_crop_id,
    COMMODITY_SEED_DATA,
    CROP_ALIASES,
)


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
