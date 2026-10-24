"""Commodity price provider and Oracle sync failures must not expose secrets."""

import sys
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

from services.ingestion import oracle_price_sync, price_attestation, yahoo_finance
from services.ingestion.oracle_aggregator import PriceReading

SECRET = "price-provider-token-secret"


def test_yahoo_fetch_failure_logs_only_exception_class(monkeypatch):
    logger = MagicMock()
    fake_yfinance = SimpleNamespace(
        Ticker=lambda _ticker: SimpleNamespace(
            history=lambda **_kwargs: (_ for _ in ()).throw(
                RuntimeError(f"Yahoo URL included token={SECRET}")
            )
        )
    )
    monkeypatch.setitem(sys.modules, "yfinance", fake_yfinance)
    monkeypatch.setattr(yahoo_finance, "logger", logger)

    assert yahoo_finance.fetch_yahoo_price("COFFEE") is None
    assert SECRET not in str(logger.error.call_args)
    assert "RuntimeError" in str(logger.error.call_args)


def test_yahoo_audit_failure_logs_only_exception_class(monkeypatch):
    logger = MagicMock()
    reading = PriceReading(
        source="yahoo_finance_KC=F",
        price=100.0,
        timestamp=datetime.now(timezone.utc),
    )
    monkeypatch.setattr(yahoo_finance, "logger", logger)
    monkeypatch.setattr(yahoo_finance, "fetch_all_yahoo_prices", lambda: {"COFFEE": reading})
    monkeypatch.setattr(
        yahoo_finance,
        "log_ingestion",
        lambda **_kwargs: (_ for _ in ()).throw(
            RuntimeError(f"database URI included {SECRET}")
        ),
    )

    result = yahoo_finance.run()

    assert result == {"status": "success", "prices_fetched": 0, "errors": 1}
    assert SECRET not in str(logger.error.call_args)
    assert "RuntimeError" in str(logger.error.call_args)


def test_oracle_sync_result_and_log_redact_provider_failure(monkeypatch):
    logger = MagicMock()
    observation = {
        "id": "observation-1",
        "commodity": "COFFEE",
        "price": 100.0,
        "source": "yahoo_finance",
        "confidence": 80,
        "observed_at": datetime.now(timezone.utc),
    }
    connection = MagicMock()
    connection.execute.return_value.mappings.return_value.all.return_value = [observation]
    monkeypatch.setattr(oracle_price_sync, "logger", logger)
    monkeypatch.setattr(
        oracle_price_sync,
        "_update_onchain_price",
        lambda *_args: (_ for _ in ()).throw(
            RuntimeError(f"RPC URL included token={SECRET}")
        ),
    )

    result = oracle_price_sync.sync_prices_to_ethereum(connection)

    assert result["failed"] == 1
    assert result["results"][0]["error"] == "price sync failed (RuntimeError)"
    assert SECRET not in str(result)
    assert SECRET not in str(logger.error.call_args)


def test_price_attestation_redacts_eas_failure_and_remains_best_effort(monkeypatch):
    logger = MagicMock()
    connection = MagicMock()
    connection.cursor.return_value.fetchone.return_value = ("price-log-id",)
    monkeypatch.setattr(price_attestation, "logger", logger)
    monkeypatch.setitem(
        sys.modules,
        "services.attestation.eas_client",
        SimpleNamespace(
            get_eas_client=lambda _chain: (_ for _ in ()).throw(
                RuntimeError(f"RPC URL included token={SECRET}")
            )
        ),
    )

    result = price_attestation.attest_price(
        connection,
        commodity="COFFEE",
        price=100.0,
        source="manual",
    )

    assert result["status"] == "success"
    assert result["attestation_uid"] is None
    assert connection.commit.called
    assert SECRET not in str(logger.warning.call_args)
    assert "RuntimeError" in str(logger.warning.call_args)
