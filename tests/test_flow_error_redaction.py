"""Prefect adapters do not leak child-process stderr through failures."""

import subprocess

import pytest


@pytest.mark.parametrize(
    ("flow_name", "expected_message"),
    [
        ("health-check", "Health check failed (exit code 9)"),
        ("price-feed-ingestion", "Yahoo Finance fetch failed (exit code 9)"),
    ],
)
def test_legacy_prefect_flow_errors_exclude_child_stderr(
    monkeypatch, flow_name, expected_message
):
    from services.flows.health_check import health_check_flow
    from services.flows.price_feed import price_feed_flow

    flow_functions = {
        "health-check": health_check_flow.fn,
        "price-feed-ingestion": price_feed_flow.fn,
    }
    child_stderr = "provider response contained api_key=synthetic-do-not-log"
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args=args[0], returncode=9, stdout="", stderr=child_stderr
        ),
    )

    with pytest.raises(RuntimeError) as error:
        flow_functions[flow_name]()

    assert str(error.value) == expected_message
    assert child_stderr not in str(error.value)
