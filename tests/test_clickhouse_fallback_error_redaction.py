"""Demo-only projection fallbacks must not expose ClickHouse exception text."""

from importlib import import_module
from unittest.mock import MagicMock, patch

import pytest

SECRET = "clickhouse-endpoint-secret"

FALLBACK_CASES = [
    (
        "services.ingestion.eas_indexer",
        "insert_clickhouse",
        ("celo", {"id": "uid", "schema": {"id": "schema"}, "time": "1"}, "published"),
    ),
    (
        "services.ingestion.gnosis_indexer",
        "insert_dlego_clickhouse",
        ({"usage_date": "2026-01-01", "chain": "gnosis", "tx_hash": "0xabc", "action_type": "vote"},),
    ),
    (
        "services.ingestion.gnosis_indexer",
        "insert_activity_clickhouse",
        ({"block_timestamp": "2026-01-01T00:00:00+00:00", "chain": "gnosis", "tx_hash": "0xabc", "event_type": "vote_cast"},),
    ),
    (
        "services.ingestion.remote_sensing",
        "insert_clickhouse",
        ({
            "id": "11111111-1111-1111-1111-111111111111",
            "location_id": "22222222-2222-2222-2222-222222222222",
            "plot_id": None,
            "observation_date": "2026-01-01",
            "source": "manual",
        },),
    ),
]


@pytest.mark.parametrize(
    ("module_name", "function_name", "args"),
    FALLBACK_CASES,
    ids=[f"{module.rsplit('.', 1)[-1]}-{function}" for module, function, _args in FALLBACK_CASES],
)
def test_demo_clickhouse_fallback_logs_only_exception_class(
    module_name, function_name, args, monkeypatch
):
    module = import_module(module_name)
    logger = MagicMock()
    monkeypatch.setattr(module, "logger", logger)

    with patch.object(
        module,
        "post_clickhouse_rows",
        side_effect=RuntimeError(f"ClickHouse endpoint contained {SECRET}"),
    ):
        getattr(module, function_name)(*args)

    assert SECRET not in str(logger.warning.call_args)
    assert "RuntimeError" in str(logger.warning.call_args)
