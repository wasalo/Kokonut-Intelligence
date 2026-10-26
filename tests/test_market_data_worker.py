"""Isolated World Bank market-data worker source contracts."""

from __future__ import annotations

import json
import sys
from unittest.mock import MagicMock, patch

import pytest

from services.ingestion import market_data_worker as worker


def _connection(inserted: int = 2):
    cursor = MagicMock()
    cursor.fetchone.return_value = (inserted,)
    connection = MagicMock()
    connection.cursor.return_value.__enter__.return_value = cursor
    return connection, cursor


def test_worker_is_default_off_before_provider_or_database_access():
    with patch.object(sys, "argv", ["market_data_worker"]), \
         patch.object(worker, "is_enabled", return_value=False), \
         patch.object(worker, "download_pink_sheet") as download, \
         patch.object(worker, "get_worker_db") as database:
        with pytest.raises(SystemExit):
            worker.main()

    download.assert_not_called()
    database.assert_not_called()


def test_worker_downloads_and_normalizes_before_opening_its_named_database():
    connection, cursor = _connection(inserted=3)
    parsed = [{
        "commodity_code": "COFFEE",
        "commodity_name": "Coffee (Arabica)",
        "price_date": "2026-06-01",
        "price_per_unit": 5.25,
    }]
    with patch.object(worker, "download_pink_sheet", return_value=b"fixture") as download, \
         patch.object(worker, "parse_pink_sheet", return_value=parsed) as parse, \
         patch.object(worker, "get_worker_db", return_value=connection) as database:
        inserted = worker.ingest(commodity="coffee", month=6, year=2026)

    assert inserted == 3
    download.assert_called_once_with()
    parse.assert_called_once_with(b"fixture", target_month=6, target_year=2026)
    database.assert_called_once_with("market_data")
    query, parameters = cursor.execute.call_args.args
    assert "store_world_bank_market_data" in query
    assert json.loads(parameters[0]) == [{
        "commodity_code": "COFFEE",
        "commodity_name": "Coffee (Arabica)",
        "price_date": "2026-06-01",
        "price_per_unit": 5.25,
    }]
    assert len(parameters[2]) == 64
    connection.commit.assert_called_once()
    connection.rollback.assert_not_called()
    connection.close.assert_called_once()


def test_empty_provider_result_fails_before_worker_database_access():
    with patch.object(worker, "download_pink_sheet", return_value=b"fixture"), \
         patch.object(worker, "parse_pink_sheet", return_value=[]), \
         patch.object(worker, "get_worker_db") as database:
        with pytest.raises(RuntimeError, match="no records"):
            worker.ingest()

    database.assert_not_called()


@pytest.mark.parametrize(
    ("commodity", "month", "year", "message"),
    [
        ("not-a-commodity", None, None, "Unknown commodity"),
        ("coffee", 0, 2026, "month must be between"),
        ("coffee", 1, 1959, "year must be between"),
        ("coffee", 1, None, "supplied together"),
    ],
)
def test_invalid_filters_fail_before_provider_or_database_access(
    commodity, month, year, message
):
    with patch.object(worker, "download_pink_sheet") as download, \
         patch.object(worker, "get_worker_db") as database:
        with pytest.raises(ValueError, match=message):
            worker.ingest(commodity=commodity, month=month, year=year)

    download.assert_not_called()
    database.assert_not_called()


def test_bounded_function_failure_rolls_back_and_closes_connection():
    connection, cursor = _connection()
    cursor.execute.side_effect = RuntimeError("synthetic database failure")
    parsed = [{
        "commodity_code": "COFFEE",
        "commodity_name": "Coffee (Arabica)",
        "price_date": "2026-06-01",
        "price_per_unit": 5.25,
    }]
    with patch.object(worker, "download_pink_sheet", return_value=b"fixture"), \
         patch.object(worker, "parse_pink_sheet", return_value=parsed), \
         patch.object(worker, "get_worker_db", return_value=connection):
        with pytest.raises(RuntimeError, match="synthetic database failure"):
            worker.ingest()

    connection.rollback.assert_called_once()
    connection.commit.assert_not_called()
    connection.close.assert_called_once()


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        (["market_data_worker", "--month", "1"], "supplied together"),
        (["market_data_worker", "--year", "2026"], "supplied together"),
    ],
)
def test_month_and_year_cli_filters_are_paired(arguments, message):
    with patch.object(sys, "argv", arguments), patch.object(worker, "is_enabled") as enabled:
        with pytest.raises(SystemExit):
            worker.main()
    enabled.assert_not_called()
