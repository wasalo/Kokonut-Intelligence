"""On-chain retirement failure details must not leak after human confirmation."""

from unittest.mock import MagicMock

from services.analytics import carbon_credits
from services.credit_class import chain_sync

SECRET = "credit-chain-rpc-secret"


def test_confirmed_retirement_redacts_nonblocking_chain_failure(monkeypatch):
    connection = MagicMock()
    cursor = connection.cursor.return_value
    cursor.fetchone.side_effect = [
        {
            "id": "retirement-id",
            "status": "submitted",
            "created_by": "requester-id",
            "retired_tonnes": 3.0,
            "credit_id": "credit-id",
        },
        {"id": "credit-id"},
    ]
    logger = MagicMock()
    monkeypatch.setattr(carbon_credits, "logger", logger)
    monkeypatch.setattr(
        chain_sync,
        "retire_onchain",
        lambda *_args: (_ for _ in ()).throw(RuntimeError(f"RPC endpoint contained {SECRET}")),
    )

    result = carbon_credits.review_retirement(
        connection,
        retirement_id="retirement-id",
        reviewer_id="independent-reviewer",
        decision="confirm",
    )

    assert result["status"] == "success"
    assert result["retirement_status"] == "verified"
    assert result["chain_sync"]["error"] == "on-chain retirement failed (RuntimeError)"
    assert SECRET not in str(result)
    assert SECRET not in str(logger.warning.call_args)
    assert "RuntimeError" in str(logger.warning.call_args)
    connection.commit.assert_called_once()
    connection.rollback.assert_not_called()
